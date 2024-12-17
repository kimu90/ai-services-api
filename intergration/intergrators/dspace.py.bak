import aiohttp
from .base import BaseIntegrator

class DSpaceIntegrator(BaseIntegrator):
    def __init__(self, db, base_url, api_key):
        super().__init__(db)
        self.base_url = base_url
        self.headers = {"X-API-Key": api_key}
    
    async def fetch_publications(self):
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get(f"{self.base_url}/api/core/items") as response:
                return await response.json()
    
    async def process_publication(self, pub_data):
        processed_data = {
            "doi": pub_data.get("doi"),
            "title": pub_data.get("title"),
            "authors": pub_data.get("authors"),
            "source": "dspace"
        }
        if processed_data["doi"]:  # Only insert if DOI exists
            self.db.insert_publication(processed_data)