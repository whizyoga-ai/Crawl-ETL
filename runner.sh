#!/usr/bin/env bash
# Crawl-ETL Shell Launcher for GPU Pod
set -e

echo "=== Initializing Crawl-ETL Independent GPU Pod ==="
python3 runner.py --host 0.0.0.0 --port 8000
