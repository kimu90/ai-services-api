from abc import ABC, abstractmethod

class BaseIntegrator(ABC):
    def __init__(self, db):
        self.db = db
    
    @abstractmethod
    async def fetch_publications(self):
        pass
    
    @abstractmethod
    async def process_publication(self, pub_data):
        pass