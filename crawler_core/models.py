"""
Crawl-ETL Standard Data Models
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class MediaItem(BaseModel):
    media_type: str # 'video', 'audio', 'image', 'document'
    url: str
    title: Optional[str] = None
    duration_seconds: Optional[float] = None
    transcript: Optional[str] = None
    transcript_segments: Optional[List[Dict[str, Any]]] = None # timestamped segments
    visual_description: Optional[str] = None
    ocr_text: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class CrawlDocument(BaseModel):
    id: str
    url: str
    domain: str
    title: str
    content_type: str # 'html', 'pdf', 'docx', 'xlsx', 'api_json', 'video', 'podcast'
    raw_text: str
    cleaned_text: str
    summary: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    links: List[str] = Field(default_factory=list)
    media_assets: List[MediaItem] = Field(default_factory=list)
    tables: List[List[List[str]]] = Field(default_factory=list) # Extracted tabular data
    crawled_at: datetime = Field(default_factory=datetime.utcnow)

class CrawlJobConfig(BaseModel):
    start_urls: List[str]
    max_depth: int = 2
    max_pages: int = 50
    concurrency: int = 5
    enable_javascript: bool = True
    enable_media_ai: bool = True
    enable_ocr: bool = True
    enable_whisper: bool = True
    output_formats: List[str] = ["json", "csv", "markdown"]
    domain_restriction: bool = True

class CrawlJobStatus(BaseModel):
    job_id: str
    status: str # 'pending', 'running', 'completed', 'failed'
    pages_crawled: int = 0
    media_processed: int = 0
    errors_count: int = 0
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    logs: List[str] = Field(default_factory=list)
