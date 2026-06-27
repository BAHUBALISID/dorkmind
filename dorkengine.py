import aiohttp
import asyncio
import random
import re
import time
from fake_useragent import UserAgent

class DorkEngine:
    def __init__(self, proxy_list=None, delay_range=(2, 5)):
        self.ua = UserAgent()
        self.proxies = proxy_list if proxy_list else []
        self.delay_range = delay_range
        self.session = None
        self.engines = {
            "duckduckgo": "https://html.duckduckgo.com/html/?q={query}",
            "bing": "https://www.bing.com/search?q={query}&count=50",
            "yahoo": "https://search.yahoo.com/search?p={query}&n=50",
            "google": "https://www.google.com/search?q={query}&num=50"
        }

    def _get_headers(self):
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

    def _random_delay(self):
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)

    async def fetch(self, url, proxy=None, retries=3):
        headers = self._get_headers()
        for attempt in range(retries):
            try:
                async with self.session.get(url, proxy=proxy, headers=headers, timeout=15) as resp:
                    if resp.status == 200:
                        return await resp.text()
                    elif resp.status == 403:
                        return None
                    else:
                        await asyncio.sleep(2 ** attempt)
            except Exception:
                await asyncio.sleep(1)
        return None

    def extract_urls(self, html):
        if not html:
            return []
        urls = re.findall(r'https?://[^\s"\'<>]+', html)
        return urls

    async def search_one(self, dork, engine="duckduckgo"):
        if engine not in self.engines:
            engine = "duckduckgo"
        query_url = self.engines[engine].format(query=dork)
        proxy = None
        if self.proxies:
            proxy = f"http://{random.choice(self.proxies)}"
        self._random_delay()
        html = await self.fetch(query_url, proxy)
        return self.extract_urls(html)

    async def run(self, dorks, engine="duckduckgo", concurrency=5):
        self.session = aiohttp.ClientSession()
        semaphore = asyncio.Semaphore(concurrency)

        async def bound_search(dork):
            async with semaphore:
                return await self.search_one(dork, engine)

        tasks = [bound_search(d) for d in dorks]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        await self.session.close()
        final_results = []
        for res in results:
            if isinstance(res, Exception):
                final_results.append([])
            else:
                final_results.append(res)
        return final_results

    def search_sync(self, dorks, engine="duckduckgo", concurrency=5):
        return asyncio.run(self.run(dorks, engine, concurrency))

if __name__ == "__main__":
    engine = DorkEngine()
    test_dorks = ['intitle:"index of" "backup"', 'inurl:admin/login']
    results = engine.search_sync(test_dorks, engine="duckduckgo", concurrency=2)
    for dork, urls in zip(test_dorks, results):
        print(f"\n[Dork] {dork}")
        for u in urls[:5]:
            print(f"  {u}")
