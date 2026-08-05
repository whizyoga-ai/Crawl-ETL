"""
Audio Processing & Speech-to-Text Engine (Whisper GPU Accelerated)
"""

import os
import logging
import tempfile
from typing import Dict, Any, List, Optional
import torch

logger = logging.getLogger("CrawlETL.MediaAudio")

class AudioMediaEngine:
    def __init__(self, use_gpu: bool = True, model_size: str = "base"):
        self.device = "cuda" if (use_gpu and torch.cuda.is_available()) else "cpu"
        self.model_size = model_size
        self._whisper_model = None
        logger.info(f"Initialized AudioMediaEngine on device: {self.device}")

    def _load_model(self):
        if self._whisper_model is None:
            try:
                import whisper
                logger.info(f"Loading Whisper model '{self.model_size}' on {self.device}...")
                self._whisper_model = whisper.load_model(self.model_size, device=self.device)
            except Exception as e:
                logger.warning(f"Failed to load whisper model: {e}")

    def transcribe_audio(self, audio_filepath: str) -> Dict[str, Any]:
        """
        Transcribes audio file to text with timestamped segments.
        """
        self._load_model()
        if self._whisper_model is None:
            return {
                "transcript": "[Whisper unavailable or failed to load]",
                "segments": [],
                "language": "unknown"
            }

        try:
            result = self._whisper_model.transcribe(audio_filepath)
            segments = []
            for seg in result.get("segments", []):
                segments.append({
                    "id": seg.get("id"),
                    "start": round(seg.get("start", 0), 2),
                    "end": round(seg.get("end", 0), 2),
                    "text": seg.get("text", "").strip()
                })

            return {
                "transcript": result.get("text", "").strip(),
                "segments": segments,
                "language": result.get("language", "en")
            }
        except Exception as e:
            logger.error(f"Error during audio transcription: {e}")
            return {
                "transcript": f"[Transcription error: {str(e)}]",
                "segments": [],
                "language": "unknown"
            }

    @staticmethod
    def generate_vtt(segments: List[Dict[str, Any]]) -> str:
        """Converts timestamped segments into WebVTT format for interactive HTML sub-titles."""
        vtt_lines = ["WEBVTT\n"]
        for seg in segments:
            start_m = int(seg['start'] // 60)
            start_s = int(seg['start'] % 60)
            start_ms = int((seg['start'] - int(seg['start'])) * 1000)
            
            end_m = int(seg['end'] // 60)
            end_s = int(seg['end'] % 60)
            end_ms = int((seg['end'] - int(seg['end'])) * 1000)

            time_str = f"00:{start_m:02d}:{start_s:02d}.{start_ms:03d} --> 00:{end_m:02d}:{end_s:02d}.{end_ms:03d}"
            vtt_lines.append(f"{time_str}\n{seg['text']}\n")

        return "\n".join(vtt_lines)
