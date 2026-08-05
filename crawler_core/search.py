"""
Robust Multi-Engine Natural Language Search & Discovery Module
"""

import re
import logging
import urllib.parse
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict, Any

logger = logging.getLogger("CrawlETL.SearchEngine")

class IntentSearchEngine:
    @staticmethod
    async def find_top_source_urls(user_prompt: str, max_results: int = 10) -> Dict[str, Any]:
        """
        Interprets plain-text prompt, queries web search indices, and extracts top candidate source URLs.
        """
        query = user_prompt.strip()
        logger.info(f"Interpreting search requirement: '{query}'")

        discovered_urls: List[str] = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        }

        # 1. DuckDuckGo HTML Search
        try:
            encoded_query = urllib.parse.quote_plus(query)
            ddg_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(ddg_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        soup = BeautifulSoup(html, "html.parser")
                        for a in soup.find_all("a", href=True):
                            href = a["href"].strip()
                            if "/l/?" in href and "uddg=" in href:
                                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                                if "uddg" in parsed:
                                    href = parsed["uddg"][0]
                            if href.startswith("http") and not any(ignored in href for ignored in ["duckduckgo.com", "bing.com", "google.com"]):
                                if href not in discovered_urls:
                                    discovered_urls.append(href)
                                    if len(discovered_urls) >= max_results:
                                        break
        except Exception as e:
            logger.warning(f"DuckDuckGo search fallback: {e}")

        # 2. Bing Search Fallback if needed
        if len(discovered_urls) < max_results:
            try:
                bing_url = f"https://www.bing.com/search?q={urllib.parse.quote_plus(query)}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(bing_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            html = await resp.text()
                            soup = BeautifulSoup(html, "html.parser")
                            for a in soup.find_all("a", href=True):
                                href = a["href"].strip()
                                if href.startswith("http") and not any(ig in href for ig in ["bing.com", "microsoft.com", "msn.com", "duckduckgo.com"]):
                                    if href not in discovered_urls:
                                        discovered_urls.append(href)
                                        if len(discovered_urls) >= max_results:
                                            break
            except Exception as e:
                logger.warning(f"Bing search fallback: {e}")

        # Extract any embedded HTTP/HTTPS URLs present inside the prompt text
        embedded_urls = re.findall(r'https?://[^\s<>"]+', query)
        for url_match in embedded_urls:
            if url_match not in discovered_urls:
                discovered_urls.insert(0, url_match)

        # Final safety fallback: If no external URLs found, use clean keywords to query
        if not discovered_urls:
            clean_words = [w for w in query.split() if not w.startswith("http")]
            fallback_query = " ".join(clean_words[:5])
            logger.info(f"Fallback search query: '{fallback_query}'")

        logger.info(f"Discovered top {len(discovered_urls)} target URLs for prompt '{query}'")
        return {
            "prompt": query,
            "discovered_urls": discovered_urls[:max_results]
        }
