import faiss
import pickle
import numpy as np
from typing import List, Tuple
from ai_services_api.services.search.config import get_settings

settings = get_settings()

class SearchEngine:
    def __init__(self, embedding_model: EmbeddingModel):
        self.embedding_model = embedding_model
        self.index = None
        self.chunk_mapping = None
        self.load_index()
        
    def load_index(self):
        self.index = faiss.read_index(settings.INDEX_PATH)
        with open(settings.CHUNK_MAPPING_PATH, "rb") as f:
            self.chunk_mapping = pickle.load(f)
    
    def search(self, query: str, k: int = 5) -> List[Tuple[str, float]]:
        query_vector = self.embedding_model.get_embedding(query)
        D, I = self.index.search(query_vector, k)
        
        results = []
        for idx, score in zip(I[0], D[0]):
            if idx in self.chunk_mapping:
                results.append((self.chunk_mapping[idx], float(score)))
        
        return results