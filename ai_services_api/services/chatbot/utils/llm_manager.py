import logging
import os
import json
import numpy as np
import re
from sentence_transformers import SentenceTransformer
from langchain.schema.messages import HumanMessage, SystemMessage
from langchain.memory import ConversationBufferWindowMemory
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.callbacks import AsyncIteratorCallbackHandler
import redis
from dotenv import load_dotenv
from typing import AsyncIterable, List, Dict
from enum import Enum

# Load environment variables from the .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class QueryIntent(Enum):
    PUBLICATION = "publication"
    NAVIGATION = "navigation"
    GENERAL = "general"

class GeminiLLMManager:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.callback = AsyncIteratorCallbackHandler()
        
        # Initialize Redis connections
        self.redis_text = redis.StrictRedis.from_url(
            self.redis_url, 
            decode_responses=True,
            db=0  # For text data
        )
        self.redis_binary = redis.StrictRedis.from_url(
            self.redis_url, 
            decode_responses=False,
            db=0  # For binary data (embeddings)
        )
        
        # Load embedding model
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Intent patterns
        self.intent_patterns = {
            QueryIntent.PUBLICATION: [
                r'publication',
                r'research',
                r'paper',
                r'study',
                r'report',
                r'pdf',
                r'document',
                r'read',
                r'download'
            ],
            QueryIntent.NAVIGATION: [
                r'where',
                r'how to find',
                r'navigate',
                r'location',
                r'page',
                r'website',
                r'link',
                r'contact',
                r'menu'
            ]
        }

    def detect_intent(self, message: str) -> QueryIntent:
        """Detect the intent of the user's query."""
        message = message.lower()
        
        # Check for publication intent
        for pattern in self.intent_patterns[QueryIntent.PUBLICATION]:
            if re.search(pattern, message):
                return QueryIntent.PUBLICATION
                
        # Check for navigation intent
        for pattern in self.intent_patterns[QueryIntent.NAVIGATION]:
            if re.search(pattern, message):
                return QueryIntent.NAVIGATION
        
        return QueryIntent.GENERAL

    def get_vector_from_message(self, message: str) -> np.ndarray:
        """Convert a message to a vector using the embedding model.""" 
        vector = self.embedding_model.encode(message)
        return vector

    def calculate_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    def query_redis_data(self, query_vector: np.ndarray, intent: QueryIntent, top_n=3, threshold=0.5) -> List[Dict]:
        """Query Redis based on intent and return relevant data."""
        try:
            results = []
            
            # Define keys pattern based on intent
            if intent == QueryIntent.PUBLICATION:
                text_pattern = "pdf:text:*"
                emb_pattern = "pdf:emb:*"
                meta_pattern = "meta:pdf:*"
            elif intent == QueryIntent.NAVIGATION:
                text_pattern = "web:text:*"
                emb_pattern = "web:emb:*"
                meta_pattern = "meta:web:*"
            else:
                # For general queries, search both
                return (
                    self.query_redis_data(query_vector, QueryIntent.PUBLICATION, top_n=2, threshold=threshold) +
                    self.query_redis_data(query_vector, QueryIntent.NAVIGATION, top_n=2, threshold=threshold)
                )

            # Get all embedding keys
            emb_keys = self.redis_binary.keys(emb_pattern)
            scores = [] 

            for emb_key in emb_keys:
                emb_key_str = emb_key.decode('utf-8')
                base_key = emb_key_str.split(':chunk_')[0]
                
                # Get corresponding text and metadata keys
                text_key = base_key.replace('emb:', 'text:')
                meta_key = base_key.replace('emb:', 'meta:')
                
                # Get embedding and calculate similarity
                embedding_bytes = self.redis_binary.get(emb_key)
                if embedding_bytes:
                    embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
                    similarity = self.calculate_similarity(query_vector, embedding)
                    
                    if similarity >= threshold:
                        # Get text and metadata
                        text = self.redis_text.get(text_key)
                        metadata = self.redis_text.hgetall(meta_key)
                        
                        scores.append({
                            'similarity': similarity,
                            'text': text,
                            'metadata': metadata,
                            'key': base_key
                        })

            # Sort by similarity and return top_n
            scores.sort(key=lambda x: x['similarity'], reverse=True)
            return scores[:top_n]

        except redis.RedisError as e:
            logger.error(f"Error accessing Redis: {e}")
            return []

    def format_response(self, response: str) -> str:
        """Format the response maintaining HTML structure."""
        # Remove markdown symbols
        cleaned = re.sub(r'[\*\[\]\(\)]', '', response)
        cleaned = cleaned.replace('\n', ' ').replace('\r', ' ').strip()
        
        # Format lists
        if '• ' in cleaned or '* ' in cleaned:
            items = re.split(r'[•*]\s+', cleaned)
            items = [item.strip() for item in items if item.strip()]
            cleaned = '<ul>' + ''.join([f'<li>{item}</li>' for item in items]) + '</ul>'
        
        return cleaned

    def create_context(self, relevant_data: List[Dict]) -> str:
        """Create a context string from relevant data."""
        context = []
        
        for item in relevant_data:
            text = item['text']
            metadata = item['metadata']
            
            if 'filename' in metadata:  # PDF context
                context.append(f"From document '{metadata['filename']}': {text[:300]}...")
            elif 'url' in metadata:  # Webpage context
                context.append(f"From page '{metadata['url']}': {text[:300]}...")
                
        return "\n\n".join(context)

    async def generate_async_response(self, message: str) -> AsyncIterable[str]:
        model = self.get_gemini_model()
        memory = self.create_memory()
        chat_memory = memory.load_memory_variables({})
        history = chat_memory.get("chat_history", [])

        # Detect intent and get query vector
        intent = self.detect_intent(message)
        query_vector = self.get_vector_from_message(message)
        
        # Get relevant data based on intent
        relevant_data = self.query_redis_data(query_vector, intent)
        
        # Create context from relevant data
        context = self.create_context(relevant_data)
        
        # Prepare message list
        # Prepare the message list with one SystemMessage that includes both the instruction and context
        message_list = [
            SystemMessage(content=os.getenv("SYSTEM_INSTRUCTION", 
                "I am a bot that gives responses based on APHRC only and don't answer questions generally but rather in the context of aphrc.org.") + 
                f" The user's intent appears to be related to {intent.value}. Here is the relevant context:\n{context}")
        ]

        # If there's any history, append it to the message list
        if history:
            message_list += history

        # Always append the HumanMessage at the end with the user's message
        message_list.append(HumanMessage(content=message))

        # Log the constructed message list for debugging purposes
        logger.debug(f"Constructed Message List: {message_list}")

        
        response = ""
        max_response_length = 500

        async for token in model.astream(input=message_list):
            formatted_token = self.format_response(token.content)
            response += formatted_token
            if len(response) >= max_response_length:
                break
            yield formatted_token.encode("utf-8", errors="replace")

    def get_gemini_model(self):
        """Initialize and return the Gemini model.""" 
        model = ChatGoogleGenerativeAI(
            google_api_key=self.api_key,
            stream=True,
            model="gemini-pro",
            convert_system_message_to_human=True,
            callbacks=[self.callback],
        )
        return model

    def create_memory(self):
        """Create conversation memory.""" 
        return ConversationBufferWindowMemory(max_token_limit=4000)
