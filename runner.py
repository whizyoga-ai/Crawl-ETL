#!/usr/bin/env python3
"""
Crawl-ETL Standalone GPU Pod Runner & Diagnostics
"""

import sys
import os
import argparse
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("CrawlETL.Runner")

def check_environment():
    logger.info("=== Crawl-ETL System Diagnostics ===")
    
    # Python Version
    logger.info(f"Python Version: {sys.version.split()[0]}")
    
    # CUDA / PyTorch Check
    try:
        import torch
        cuda_avail = torch.cuda.is_available()
        logger.info(f"PyTorch Version: {torch.__version__}")
        logger.info(f"CUDA Available: {cuda_avail}")
        if cuda_avail:
            logger.info(f"GPU Device Count: {torch.cuda.device_count()}")
            logger.info(f"GPU Device Name: {torch.cuda.get_device_name(0)}")
        else:
            logger.warning("CUDA not detected. Running in CPU mode.")
    except Exception as e:
        logger.error(f"PyTorch check failed: {e}")

    # FFmpeg Check
    try:
        res = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0:
            first_line = res.stdout.decode().splitlines()[0]
            logger.info(f"FFmpeg Status: Installed ({first_line})")
        else:
            logger.warning("FFmpeg binary not found in PATH.")
    except Exception:
        logger.warning("FFmpeg binary not found in PATH.")

    logger.info("====================================")

def main():
    parser = argparse.ArgumentParser(description="Crawl-ETL Pod Runner")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--check-only", action="store_true", help="Run system diagnostics and exit")
    args = parser.parse_args()

    check_environment()

    if args.check_only:
        sys.exit(0)

    logger.info(f"Starting Crawl-ETL Web Client & Server Pod on {args.host}:{args.port}...")
    
    import uvicorn
    # Add project root to sys.path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    uvicorn.run("server.app:app", host=args.host, port=args.port, reload=False)

if __name__ == "__main__":
    main()
