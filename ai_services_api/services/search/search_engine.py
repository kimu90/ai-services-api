import faiss
import pickle
import os
from pathlib import Path
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
from ai_services_api.services.search.config import get_settings
from ai_services_api.services.search.experts_manager import ExpertsManager

class EmbeddingModel:
    def __init__(self):
        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        
    def get_embedding(self, text: str) -> List[float]:
        embeddings = self.model.encode([text], convert_to_numpy=True)
        return embeddings

class SearchEngine:
    def __init__(self, embedding_model_path=None):
        self.embedding_model = EmbeddingModel()

        current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        models_dir = current_dir.parent / 'models'
        self.index_path = models_dir / 'faiss_index.idx'
        self.mapping_path = models_dir / 'chunk_mapping.pkl'

        if not os.path.isfile(self.index_path):
            raise FileNotFoundError(f"FAISS index not found at {self.index_path}")
        
        self.index = faiss.read_index(str(self.index_path))

        if not os.path.isfile(self.mapping_path):
            raise FileNotFoundError(f"Chunk mapping not found at {self.mapping_path}")
            
        with open(self.mapping_path, 'rb') as f:
            self.chunk_mapping = pickle.load(f)

        self.experts_manager = ExpertsManager()

    # Rest of the code remains unchanged
    def search(self, query: str, k: int = 5) -> List[Dict]:
        """
        Perform semantic search on the indexed documents.
        """
        query_vector = self.embedding_model.get_embedding(query)
        D, I = self.index.search(query_vector, k)

        results = []
        for idx, score in zip(I[0], D[0]):
            result = {
                'metadata': self.chunk_mapping[idx],
                'similarity_score': float(score)
            }
            
            domain = result['metadata'].get('Domain', ' ')
            result['experts'] = self.experts_manager.find_experts_by_domain(domain)[:3]
            
            results.append(result)

        return results

    def get_summary_by_title(self, title: str) -> Optional[Dict]:
        """
        Retrieve document details by exact title match.
        """
        for idx, doc in self.chunk_mapping.items():
            if doc['Title'].lower() == title.lower():
                return doc
        return None

    def search_by_title(self, title_query: str, k: int = 5) -> List[Dict]:
        """
        Search for documents with titles similar to the query.
        """
        matching_docs = []

        for idx, doc in self.chunk_mapping.items():
            if title_query.lower() in doc['Title'].lower():
                matching_docs.append({
                    'metadata': doc,
                    'similarity': 1.0
                })

        matching_docs.sort(key=lambda x: x['similarity'], reverse=True)
        return matching_docs[:k]
