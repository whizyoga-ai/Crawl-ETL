"""
Natural Language Intent Interpreter & Web Search Discovery Engine
Locates top candidate source URLs based on plain-text user requirements.
"""

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
        Interprets plain-text prompt, generates search queries, and fetches top candidate source URLs.
        """
        logger.info(f"Interpreting natural language request: '{user_prompt}'")
        
        # Build search query optimized for documents if prompt implies papers/docs
        query = user_prompt.strip()
        if any(w in query.lower() for w in ["pdf", "doc", "paper", "report", "file", "download"]):
            search_query = query
        else:
            search_query = f"{query} filetype:pdf OR doc"

        encoded_query = urllib.parse.quote_plus(search_query)
        # Use DuckDuckGo HTML search for unthrottled candidate discovery
        search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        discovered_urls: List[str] = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        soup = BeautifulSoup(html, "html.parser")
                        
                        for a in soup.find_all("a", class_="result__url", href=True):
                            href = a["href"].strip()
                            # Unpack DuckDuckGo redirect link if necessary
                            if "/l/?" in href and "uddg=" in href:
                                parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                                if "uddg" in parsed:
                                    href = parsed["uddg"][0]
                            
                            if href.startswith("http") and href not in discovered_urls:
                                discovered_urls.append(href)
                                if len(discovered_urls) >= max_results:
                                    break
        except Exception as e:
            logger.error(f"Search discovery error: {e}")

        # Fallback to direct prompt if search fails or returns fewer links
        if not discovered_urls:
            discovered_urls = [user_prompt] if user_prompt.startswith("http") else []

        logger.info(f"Discovered top {len(discovered_urls)} source URLs for prompt '{user_prompt}'")
        return {
            "prompt": user_prompt,
            "search_query": search_query,
            "discovered_urls": discovered_urls
        }
