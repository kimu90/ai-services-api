import os
import fitz  # PyMuPDF for extracting text from PDFs
from typing import List
from gemini import GeminiClient
from ai_services_api.services.search.models.search import SearchQuery, SearchResult, SearchResponse
from ai_services_api.services.search.models.document import Document
from ai_services_api.services.search.core.ai_predictor import AIPredictor
from ai_services_api.services.search.core.settings import Settings
from sklearn.metrics.pairwise import cosine_similarity
import faiss
import numpy as np
import pickle
import torch
from transformers import DistilBertTokenizer, DistilBertModel


# GLOBAL CONSTANTS
MODEL_PATH = 'distilbert-base-uncased'
DIMENSION = 768
NLIST = 2
INDEX_PATH = "faiss_index.idx"
CHUNK_MAPPING_PATH = "index_to_chunk.pkl"
MAX_CHUNK_SIZE = 64


# Initialization of model
TOKENIZER = DistilBertTokenizer.from_pretrained(MODEL_PATH)
MODEL = DistilBertModel.from_pretrained(MODEL_PATH)


class SearchService:
    def __init__(self, settings: Settings):
        self.gemini_client = GeminiClient(api_key=settings.gemini_api_key)
        # Load documents from PDF folder defined in settings
        self.document_store = self._load_documents(settings.PDF_FOLDER)  
        self.embedding_cache = {}
        self.ai_predictor = AIPredictor()  # Initialize AI predictor
        self.index = None
        self.index_to_chunk = None
        self._initialize_faiss_index(settings.PDF_FOLDER)  # Initialize FAISS index

    def _load_documents(self, pdf_folder: str) -> dict:
        """
        Load documents from the specified PDF folder.
        """
        document_store = {}
        pdf_folder_path = os.path.join(os.getcwd(), pdf_folder)  # Resolves full path from current working directory
        
        # Ensure the folder exists and is accessible
        if not os.path.exists(pdf_folder_path):
            raise FileNotFoundError(f"PDF folder not found: {pdf_folder_path}")
        
        for file_name in os.listdir(pdf_folder_path):
            if file_name.lower().endswith('.pdf'):
                file_path = os.path.join(pdf_folder_path, file_name)
                document = self._extract_pdf_text(file_path)
                document_store[document.id] = document
        return document_store

    def _extract_pdf_text(self, file_path: str) -> Document:
        """
        Extract text from a PDF file and create a Document instance.
        """
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text("text")
        
        # Create a document object
        return Document(
            id=os.path.basename(file_path),  # Use file name as the document ID
            title=os.path.basename(file_path),
            content=text,
            tags=[],  # You can add tags as needed
        )

    def _initialize_faiss_index(self, pdf_folder: str):
        """
        Initialize FAISS index for the documents in the specified folder.
        """
        index_to_chunk = {}

        # Create FAISS index
        quantizer = faiss.IndexHNSWFlat(DIMENSION, 32)
        self.index = faiss.IndexIVFFlat(quantizer, DIMENSION, NLIST, faiss.METRIC_L2)
        
        all_embeddings = []
        all_chunks = []

        for file_name in os.listdir(pdf_folder):
            if file_name.lower().endswith('.pdf'):
                file_path = os.path.join(pdf_folder, file_name)
                document = self._extract_pdf_text(file_path)
                content = document.content
                # Split content into chunks for better indexing
                for chunk in self.chunk_document(content):
                    embedding = self.get_embedding(chunk)
                    all_embeddings.append(embedding)
                    all_chunks.append(chunk)
        
        embeddings_np = np.vstack(all_embeddings)
        faiss.normalize_L2(embeddings_np)
        self.index.train(embeddings_np)

        for i, embedding in enumerate(all_embeddings):
            self.index.add(embedding)
            index_to_chunk[i] = all_chunks[i]

        # Save index and chunk mapping
        faiss.write_index(self.index, INDEX_PATH)
        with open(CHUNK_MAPPING_PATH, "wb") as f:
            pickle.dump(index_to_chunk, f)

    def chunk_document(self, document, max_size=MAX_CHUNK_SIZE):
        """
        Split the document into smaller chunks of maximum size.
        """
        words = document.split()
        for i in range(0, len(words), max_size):
            yield ' '.join(words[i:i+max_size])

    def get_embedding(self, text):
        """
        Compute the embeddings for a given text using DistilBert.
        """
        input_ids = TOKENIZER.encode(text, return_tensors="pt", truncation=True)
        with torch.no_grad():
            output = MODEL(input_ids)
        return output.last_hidden_state.mean(dim=1).numpy()

    async def search(self, query: SearchQuery) -> SearchResponse:
        """
        Perform search by generating embeddings for the query and comparing it with document embeddings.
        """
        # Generate query embedding
        query_embedding = await self._get_embedding(query.query)
        
        # Perform search using FAISS
        query_embedding_np = np.array(query_embedding).reshape(1, -1)
        faiss.normalize_L2(query_embedding_np)
        distances, indices = self.index.search(query_embedding_np, k=5)  # Get top 5 results
        
        # Retrieve results based on FAISS search
        results = []
        for idx in indices[0]:
            if idx != -1:  # Ignore invalid index
                chunk = self.index_to_chunk[idx]
                similarity = distances[0][idx]
                doc_id = chunk[:10]  # Just an example, you could use actual document ID here
                results.append(SearchResult(
                    id=doc_id,
                    title=f"Document {doc_id}",
                    content=chunk,
                    relevance_score=float(similarity),
                    tags=[]
                ))
        
        # Paginate results
        start_idx = (query.page - 1) * query.page_size
        end_idx = start_idx + query.page_size
        paginated_results = results[start_idx:end_idx]

        # Use AI predictor to suggest related completions based on query
        suggestions = await self._generate_suggestions(query.query)
        
        return SearchResponse(
            results=paginated_results,
            total=len(results),
            page=query.page,
            page_size=query.page_size,
            suggestions=suggestions
        )
    
    async def _get_embedding(self, text: str) -> List[float]:
        """
        Get the embedding for a given text using the Gemini API.
        """
        response = await self.gemini_client.embeddings.create(
            model="gemini-embedding-large",
            input=text
        )
        return response.data[0].embedding
    
    async def _generate_suggestions(self, query: str) -> List[str]:
        """
        Use the AI predictor to suggest related completions for a query.
        """
        completion, likelihood = self.ai_predictor.predict_completion(query)
        return [completion]  # Return as a single suggestion (can modify to return more)
