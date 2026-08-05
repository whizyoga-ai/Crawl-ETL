"""
Universal Async Web & Media Crawler Engine
"""

import os
import re
import asyncio
import logging
import uuid
import tempfile
import aiohttp
from typing import Dict, Any, List, Set, Optional
from urllib.parse import urlparse, urljoin

from .models import CrawlDocument, CrawlJobConfig, CrawlJobStatus, MediaItem
from .extractors import HTMLExtractor, DocumentExtractor
from media_engine.audio import AudioMediaEngine
from media_engine.video import VideoMediaEngine
from media_engine.multimodal import MultimodalSynthesisEngine

logger = logging.getLogger("CrawlETL.Engine")

class UniversalCrawler:
    def __init__(self, config: CrawlJobConfig, job_status: CrawlJobStatus):
        self.config = config
        self.status = job_status
        self.visited_urls: Set[str] = set()
        self.documents: List[CrawlDocument] = []
        self.audio_engine = AudioMediaEngine(use_gpu=True) if config.enable_whisper else None
        self.video_engine = VideoMediaEngine(use_gpu=True) if config.enable_media_ai else None

    def log(self, message: str):
        timestamp_msg = f"[{self.status.job_id}] {message}"
        logger.info(timestamp_msg)
        self.status.logs.append(timestamp_msg)

    async def fetch_url(self, session: aiohttp.ClientSession, url: str) -> Optional[Tuple[bytes, str, str]]:
        """Fetch URL content via async HTTP client with custom user-agent"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Crawl-ETL/1.0"
        }
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get("Content-Type", "").lower()
                    data = await resp.read()
                    return data, content_type, str(resp.url)
                else:
                    self.log(f"HTTP {resp.status} for {url}")
                    return None
        except Exception as e:
            self.log(f"Failed to fetch {url}: {e}")
            return None

    async def process_media_url(self, media_type: str, url: str) -> MediaItem:
        """Processes video or audio URL via GPU media engine"""
        media_item = MediaItem(media_type=media_type, url=url)
        if not self.config.enable_media_ai:
            return media_item

        self.log(f"Processing {media_type} asset: {url}")
        # If it's a direct file or playable stream, download temporary chunk and process
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        ext = ".mp4" if media_type == "video" else ".mp3"
                        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                            tmp.write(data)
                            tmp_path = tmp.name

                        try:
                            if media_type == "video" and self.video_engine:
                                res = self.video_engine.process_video_file(tmp_path, self.audio_engine)
                                media_item.transcript = res.get("transcript", "")
                                media_item.transcript_segments = res.get("transcript_segments", [])
                                media_item.metadata["keyframes"] = res.get("keyframes", [])
                            elif media_type == "audio" and self.audio_engine:
                                res = self.audio_engine.transcribe_audio(tmp_path)
                                media_item.transcript = res.get("transcript", "")
                                media_item.transcript_segments = res.get("segments", [])
                        finally:
                            if os.path.exists(tmp_path):
                                os.remove(tmp_path)
        except Exception as e:
            self.log(f"Media processing error for {url}: {e}")

        return media_item

    async def crawl(self) -> List[CrawlDocument]:
        """Main asynchronous crawl loop"""
        self.status.status = "running"
        self.log(f"Starting crawl job for {len(self.config.start_urls)} seed URL(s)...")

        allowed_domains = {urlparse(u).netloc for u in self.config.start_urls} if self.config.domain_restriction else set()
        queue: List[Tuple[str, int]] = [(u, 0) for u in self.config.start_urls]

        async with aiohttp.ClientSession() as session:
            while queue and len(self.documents) < self.config.max_pages:
                current_batch = queue[:self.config.concurrency]
                queue = queue[self.config.concurrency:]

                tasks = []
                for url, depth in current_batch:
                    if url in self.visited_urls:
                        continue
                    self.visited_urls.add(url)
                    tasks.append(self.process_page(session, url, depth, allowed_domains, queue))

                await asyncio.gather(*tasks, return_exceptions=True)

        self.status.status = "completed"
        self.status.pages_crawled = len(self.documents)
        self.log(f"Crawl completed. Total pages processed: {len(self.documents)}")
        return self.documents

    async def process_page(self, session: aiohttp.ClientSession, url: str, depth: int, allowed_domains: Set[str], queue: List[Tuple[str, int]]):
        self.log(f"Crawling [Depth {depth}]: {url}")
        res = await self.fetch_url(session, url)
        if not res:
            self.status.errors_count += 1
            return

        data, content_type, final_url = res
        parsed_url = urlparse(final_url)
        domain = parsed_url.netloc

        cleaned_text = ""
        title = final_url
        tables = []
        links = []
        media_items: List[MediaItem] = []
        doc_type = "html"

        if "pdf" in content_type or final_url.lower().endswith(".pdf"):
            doc_type = "pdf"
            pdf_res = DocumentExtractor.extract_pdf(data)
            cleaned_text = pdf_res["cleaned_text"]
            title = pdf_res["title"]
            tables = pdf_res["tables"]
        elif "word" in content_type or final_url.lower().endswith(".docx"):
            doc_type = "docx"
            docx_res = DocumentExtractor.extract_docx(data)
            cleaned_text = docx_res["cleaned_text"]
            tables = docx_res["tables"]
        elif "excel" in content_type or "spreadsheet" in content_type or final_url.lower().endswith((".xlsx", ".csv")):
            doc_type = "xlsx"
            excel_res = DocumentExtractor.extract_excel(data)
            cleaned_text = excel_res["cleaned_text"]
            tables = excel_res["tables"]
        else:
            # HTML content
            doc_type = "html"
            html_str = data.decode("utf-8", errors="ignore")
            extracted = HTMLExtractor.extract(html_str, final_url)
            title = extracted["title"]
            cleaned_text = extracted["cleaned_text"]
            links = extracted["links"]
            tables = extracted["tables"]

            # Process discovered media assets
            for m in extracted.get("media_urls", []):
                if m["type"] in ["video", "audio"]:
                    m_item = await self.process_media_url(m["type"], m["url"])
                    media_items.append(m_item)
                    self.status.media_processed += 1

        # Enqueue new links if depth limit not reached
        if depth < self.config.max_depth:
            for link in links:
                link_domain = urlparse(link).netloc
                if not self.config.domain_restriction or link_domain in allowed_domains:
                    if link not in self.visited_urls:
                        queue.append((link, depth + 1))

        summary = MultimodalSynthesisEngine.synthesize_document_summary(
            cleaned_text, tables, [m.transcript for m in media_items if m.transcript]
        )
        entities = MultimodalSynthesisEngine.extract_key_entities(cleaned_text)

        doc = CrawlDocument(
            id=str(uuid.uuid4()),
            url=final_url,
            domain=domain,
            title=title,
            content_type=doc_type,
            raw_text=cleaned_text,
            cleaned_text=cleaned_text,
            summary=summary,
            metadata={"entities": entities, "depth": depth},
            links=links,
            media_assets=media_items,
            tables=tables
        )

        self.documents.append(doc)
        self.status.pages_crawled = len(self.documents)
