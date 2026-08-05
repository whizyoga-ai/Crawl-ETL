"""
Multimodal AI Analysis Engine for Crawl-ETL
Integrates text, audio transcriptions, document tables, and visual keyframes.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger("CrawlETL.Multimodal")

class MultimodalSynthesisEngine:
    @staticmethod
    def synthesize_document_summary(cleaned_text: str, 
                                     tables: List[List[List[str]]], 
                                     media_transcripts: List[str]) -> str:
        """
        Creates an aggregated intelligent summary of scraped content including text, 
        tabular structures, and video/audio transcriptions.
        """
        summary_parts = []

        if cleaned_text:
            text_snippet = cleaned_text[:500].replace('\n', ' ')
            summary_parts.append(f"Primary Text Content Overview: {text_snippet}...")

        if tables:
            summary_parts.append(f"Structured Data: Contains {len(tables)} tabular dataset(s).")

        if media_transcripts:
            valid_transcripts = [t for t in media_transcripts if t and not t.startswith("[")]
            if valid_transcripts:
                summary_parts.append(f"Media Audio Transcripts ({len(valid_transcripts)} tracks): {valid_transcripts[0][:300]}...")

        if not summary_parts:
            return "No readable text content extracted."

        return " | ".join(summary_parts)

    @staticmethod
    def extract_key_entities(text: str) -> Dict[str, List[str]]:
        """Lightweight regex & heuristic entity extractor for URLs, Emails, Numbers, Topics"""
        import re
        emails = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)))
        phones = list(set(re.findall(r'\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}', text)))
        urls = list(set(re.findall(r'https?://[^\s<>"]+', text)))

        return {
            "emails": emails[:10],
            "phone_numbers": phones[:10],
            "embedded_urls": urls[:20]
        }
