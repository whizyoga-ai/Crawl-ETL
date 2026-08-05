"""
FastAPI Server & Client Web UI Host for Crawl-ETL
"""

import os
import io
import json
import asyncio
import logging
import zipfile

from fastapi import FastAPI, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List
import pandas as pd
import torch

from crawler_core.models import CrawlJobConfig, CrawlJobStatus, CrawlDocument
from crawler_core.engine import UniversalCrawler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CrawlETL.Server")

app = FastAPI(title="Crawl-ETL Pod & Web Client", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JOBS_DB: Dict[str, CrawlJobStatus] = {}
RESULTS_DB: Dict[str, List[CrawlDocument]] = {}
ACTIVE_WEBSOCKETS: List[WebSocket] = []

async def broadcast_log(msg: str):
    for ws in list(ACTIVE_WEBSOCKETS):
        try:
            await ws.send_text(msg)
        except Exception:
            if ws in ACTIVE_WEBSOCKETS:
                ACTIVE_WEBSOCKETS.remove(ws)

def run_background_crawl(job_id: str, config: CrawlJobConfig):
    status = JOBS_DB[job_id]
    crawler = UniversalCrawler(config, status)
    
    # Run async crawler in event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    docs = loop.run_until_complete(crawler.crawl())
    RESULTS_DB[job_id] = docs
    loop.close()

@app.get("/api/system/gpu")
def get_gpu_status():
    cuda_available = torch.cuda.is_available()
    device_count = torch.cuda.device_count() if cuda_available else 0
    device_name = torch.cuda.get_device_name(0) if cuda_available else "CPU Mode (No CUDA)"
    
    return {
        "cuda_available": cuda_available,
        "device_count": device_count,
        "device_name": device_name,
        "status": "Ready",
        "pod_name": os.getenv("POD_NAME", "crawl-etl-standalone-gpu-0")
    }

from pydantic import BaseModel
from crawler_core.search import IntentSearchEngine

class SearchCrawlRequest(BaseModel):
    prompt: str
    max_results: int = 10
    max_depth: int = 2
    enable_media_ai: bool = True

@app.post("/api/search-and-crawl")
async def search_and_crawl(req: SearchCrawlRequest, background_tasks: BackgroundTasks):
    search_res = await IntentSearchEngine.find_top_source_urls(req.prompt, max_results=req.max_results)
    urls = search_res["discovered_urls"]
    if not urls:
        raise HTTPException(status_code=404, detail="No candidate source URLs discovered for your query.")

    import uuid
    job_id = str(uuid.uuid4())[:8]
    config = CrawlJobConfig(
        start_urls=urls,
        max_depth=req.max_depth,
        max_pages=req.max_results * 3,
        enable_media_ai=req.enable_media_ai
    )
    status = CrawlJobStatus(job_id=job_id, status="pending")
    JOBS_DB[job_id] = status
    RESULTS_DB[job_id] = []

    background_tasks.add_task(run_background_crawl, job_id, config)
    return {
        "job_id": job_id,
        "prompt": req.prompt,
        "discovered_urls": urls,
        "message": f"Interpreted requirement & discovered top {len(urls)} target sources."
    }

@app.post("/api/crawl")
def start_crawl(config: CrawlJobConfig, background_tasks: BackgroundTasks):
    import uuid
    job_id = str(uuid.uuid4())[:8]
    status = CrawlJobStatus(job_id=job_id, status="pending")
    JOBS_DB[job_id] = status
    RESULTS_DB[job_id] = []

    background_tasks.add_task(run_background_crawl, job_id, config)
    return {"job_id": job_id, "message": "Crawl job scheduled successfully", "config": config}

@app.get("/api/jobs")
def list_jobs():
    return list(JOBS_DB.values())

@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str):
    if job_id not in JOBS_DB:
        raise HTTPException(status_code=404, detail="Job not found")
    return JOBS_DB[job_id]

@app.get("/api/jobs/{job_id}/results")
def get_job_results(job_id: str):
    docs = RESULTS_DB.get(job_id, [])
    return [doc.dict() for doc in docs]

@app.get("/api/jobs/{job_id}/download/{fmt}")
def download_results(job_id: str, fmt: str):
    """
    Directly download crawled documents into local machine in JSON, CSV, Markdown, or ZIP bundle formats.
    """
    if job_id not in RESULTS_DB:
        raise HTTPException(status_code=404, detail="Job results not found")
    
    docs = RESULTS_DB[job_id]
    doc_dicts = [d.dict() for d in docs]

    if fmt == "json":
        buf = io.BytesIO(json.dumps(doc_dicts, indent=2, default=str).encode('utf-8'))
        return StreamingResponse(buf, media_type="application/json", headers={
            "Content-Disposition": f"attachment; filename=crawl_etl_{job_id}.json"
        })
    elif fmt == "csv":
        # Flatten documents for CSV export
        rows = []
        for d in docs:
            rows.append({
                "id": d.id,
                "url": d.url,
                "domain": d.domain,
                "title": d.title,
                "content_type": d.content_type,
                "cleaned_text": d.cleaned_text[:1000],
                "summary": d.summary,
                "media_count": len(d.media_assets),
                "crawled_at": str(d.crawled_at)
            })
        df = pd.DataFrame(rows)
        csv_str = df.to_csv(index=False)
        buf = io.BytesIO(csv_str.encode('utf-8'))
        return StreamingResponse(buf, media_type="text/csv", headers={
            "Content-Disposition": f"attachment; filename=crawl_etl_{job_id}.csv"
        })
    elif fmt == "markdown":
        md_content = [f"# Crawl-ETL Export (Job {job_id})\n"]
        for d in docs:
            md_content.append(f"## [{d.title}]({d.url})")
            md_content.append(f"**Domain:** {d.domain} | **Type:** {d.content_type}\n")
            md_content.append(f"### Summary\n{d.summary}\n")
            md_content.append(f"### Text Content\n{d.cleaned_text}\n")
            if d.media_assets:
                md_content.append("### Media Assets & Transcripts")
                for m in d.media_assets:
                    md_content.append(f"- **{m.media_type.upper()}:** {m.url}")
                    if m.transcript:
                        md_content.append(f"  > *Transcript:* {m.transcript}")
            md_content.append("\n---\n")
        
        full_md = "\n".join(md_content)
        buf = io.BytesIO(full_md.encode('utf-8'))
        return StreamingResponse(buf, media_type="text/markdown", headers={
            "Content-Disposition": f"attachment; filename=crawl_etl_{job_id}.md"
        })
    elif fmt == "zip":
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"crawl_etl_{job_id}.json", json.dumps(doc_dicts, indent=2, default=str))
            for idx, d in enumerate(docs):
                zf.writestr(f"docs/doc_{idx+1}_{d.domain}.txt", f"URL: {d.url}\nTitle: {d.title}\n\n{d.cleaned_text}")
            
            # Package any raw downloaded PDFs, DOCX, XLSX files saved on disk
            job_download_dir = os.path.join("downloads", job_id)
            if os.path.exists(job_download_dir):
                for root, _, files in os.walk(job_download_dir):
                    for f in files:
                        full_p = os.path.join(root, f)
                        zf.write(full_p, os.path.join("raw_documents", f))

        zip_buf.seek(0)
        return StreamingResponse(zip_buf, media_type="application/zip", headers={
            "Content-Disposition": f"attachment; filename=crawl_etl_{job_id}_raw_materials.zip"
        })
    else:
        raise HTTPException(status_code=400, detail="Unsupported format. Use json, csv, markdown, or zip")

@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ACTIVE_WEBSOCKETS.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in ACTIVE_WEBSOCKETS:
            ACTIVE_WEBSOCKETS.remove(websocket)

# Mount static web client assets
client_path = os.path.join(os.path.dirname(__file__), "..", "client")
if os.path.exists(client_path):
    app.mount("/", StaticFiles(directory=client_path, html=True), name="client")
