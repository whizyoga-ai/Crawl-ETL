# Expert Crawler & Media Intelligence (`Crawl-ETL`)

**Crawl-ETL** is a massive, unified web crawler and multimodal ETL engine capable of traversing diverse internet locations (dynamic SPAs, REST/GraphQL APIs, documents, videos, podcasts, RSS streams) and performing deep media interpretation using GPU-accelerated AI models.

Repository: [https://github.com/whizyoga-ai/Crawl-ETL](https://github.com/whizyoga-ai/Crawl-ETL)

---

## Key Features

1. **Universal Multi-Format Ingestion**:
   - Web SPAs & Static Pages (Playwright / Chromium headless rendering + async HTTP).
   - Documents: PDF (tables + layout text), Word (.docx), Excel (.xlsx / .csv).
   - Media: YouTube, Vimeo, MP4/WebM video streams, MP3/WAV podcasts.

2. **GPU Media Interpretation Pipeline**:
   - **Audio / Speech-to-Text**: Whisper speech-to-text with WebVTT timestamped subtitle generation.
   - **Video Processing**: FFmpeg frame extraction, keyframe sampling, video OCR text detection.
   - **Multimodal AI**: Aggregated document synthesis, entity extraction (emails, phones, URLs).

3. **Interactive Web Client Application**:
   - Built-in Glassmorphism dark mode UI dashboard.
   - Real-time job launcher & configuration modal.
   - Streaming WebSocket logs & active job monitors.
   - Rich media & document inspector (transcripts, tables, entity graphs).
   - One-click local file download (JSON, CSV, Markdown, ZIP bundle).

4. **Standalone GPU Pod Server**:
   - Deployment ready via `runner.py` / `runner.sh`.
   - `Dockerfile.gpu` with NVIDIA CUDA 12.1 runtime, FFmpeg, Tesseract OCR, and PyTorch.
   - `docker-compose.gpu.yml` & `k8s/gpu-pod.yaml` for Kubernetes deployments (`nvidia.com/gpu: 1`).

---

## Quickstart & Local Deployment

### 1. Install Dependencies & Run Diagnostics
```bash
pip install -r requirements.txt
python runner.py --check-only
```

### 2. Launch Server & Web Client
```bash
python runner.py --host 0.0.0.0 --port 8000
```
Open your browser and navigate to: **`http://localhost:8000`**

---

## GPU Pod Deployment

### Deploy via Docker Compose:
```bash
docker-compose -f docker-compose.gpu.yml up -d --build
```

### Deploy to Kubernetes Cluster:
```bash
kubectl apply -f k8s/gpu-pod.yaml
```

---

## API Endpoints

- `POST /api/crawl` - Schedule new crawl job
- `GET /api/jobs` - List all crawl jobs
- `GET /api/jobs/{job_id}/results` - Retrieve extracted documents & media items
- `GET /api/jobs/{job_id}/download/{format}` - Download scraped data (`json`, `csv`, `markdown`, `zip`)
- `GET /api/system/gpu` - Query CUDA GPU status & pod metrics
- `WS /ws/logs` - Live WebSocket log stream
