import faiss
import pickle
import os
from typing import List, Dict, Optional
from ai_services_api.services.search.config import get_settings
from ai_services_api.services.search.embedding_model import EmbeddingModel
from ai_services_api.services.search.experts_manager import ExpertsManager

class SearchEngine:
    def __init__(self, embedding_model_path=None):
        """
        Initialize the search engine with embedding model and FAISS index.
        """
        settings = get_settings()

        # Use provided model path or default from settings
        model_path = embedding_model_path or settings.MODEL_PATH

        # Initialize embedding model
        self.embedding_model = EmbeddingModel(model_path)

        # Get the current file's directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Get the models folder path from the settings (changed from 'static' to 'models')
        models_dir = os.path.join(os.path.dirname(current_dir), 'models')

        # Get the index and mapping paths from settings
        index_path = settings.INDEX_PATH
        mapping_path = settings.CHUNK_MAPPING_PATH

        # Debugging: Print paths being used
        print(f"Current directory: {current_dir}")
        print(f"Models directory: {models_dir}")
        print(f"Index path: {index_path}")
        print(f"Mapping path: {mapping_path}")

        # Verify that the index and mapping files exist
        if not os.path.isfile(index_path):
            raise FileNotFoundError(
                f"FAISS index file not found at {index_path}. "
                f"Current directory: {current_dir}, "
                f"Models directory: {models_dir}"
            )
        
        # Load FAISS index
        self.index = faiss.read_index(index_path)

        # Load chunk mapping
        if not os.path.isfile(mapping_path):
            raise FileNotFoundError(f"Chunk mapping file not found at {mapping_path}")
            
        with open(mapping_path, 'rb') as f:
            self.chunk_mapping = pickle.load(f)

        # Initialize experts manager
        self.experts_manager = ExpertsManager()

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
