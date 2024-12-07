import logging
import os
import json
import numpy as np
import re
from datetime import datetime
import time
from typing import AsyncIterable, List, Dict, Tuple, Optional
from enum import Enum
from sentence_transformers import SentenceTransformer
from langchain.schema.messages import HumanMessage, SystemMessage
from langchain.memory import ConversationBufferWindowMemory
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.callbacks import AsyncIteratorCallbackHandler
import redis
from dotenv import load_dotenv

# Load environment variables
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
        # Initialize basic configurations
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.callback = AsyncIteratorCallbackHandler()
        self.confidence_threshold = 0.6
        
        # Initialize context management
        self.context_window = []
        self.max_context_items = 5
        self.context_expiry = 1800  # 30 minutes
        
        # Initialize Redis connections
        self.redis_text = redis.StrictRedis.from_url(
            self.redis_url, 
            decode_responses=True,
            db=0
        )
        self.redis_binary = redis.StrictRedis.from_url(
            self.redis_url, 
            decode_responses=False,
            db=0
        )
        
        # Load embedding model
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Initialize intent patterns with weights
        self.intent_patterns = {
            QueryIntent.PUBLICATION: {
                'patterns': [
                    (r'publication', 1.0),
                    (r'research', 0.8),
                    (r'paper', 0.8),
                    (r'report', 0.7),
                    (r'study', 0.7),
                    (r'document', 0.6),
                    (r'pdf', 0.6),
                    (r'read', 0.5),
                    (r'download', 0.6)
                ],
                'threshold': 0.7
            },
            QueryIntent.NAVIGATION: {
                'patterns': [
                    (r'where', 0.8),
                    (r'how to find', 1.0),
                    (r'navigate', 1.0),
                    (r'location', 0.8),
                    (r'page', 0.6),
                    (r'website', 0.7),
                    (r'link', 0.6),
                    (r'contact', 0.7),
                    (r'menu', 0.6)
                ],
                'threshold': 0.6
            }
        }

    def detect_follow_up(self, message: str) -> bool:
        """Detect if the message is a follow-up question."""
        follow_up_patterns = [
            r'what about',
            r'tell me more',
            r'could you explain',
            r'how does that',
            r'why is',
            r'and\?',
            r'but what'
        ]
        
        pronoun_patterns = [
            r'\bit\b',
            r'\bthis\b',
            r'\bthat\b',
            r'\bthese\b',
            r'\bthose\b'
        ]
        
        return (
            any(re.search(pattern, message.lower()) for pattern in follow_up_patterns) or
            any(re.search(pattern, message.lower()) for pattern in pronoun_patterns)
        )

    def handle_follow_up(self, message: str) -> str:
        """Enhance follow-up questions with context."""
        if not self.detect_follow_up(message):
            return message
            
        if not self.context_window:
            return message
            
        recent_context = self.context_window[-1]
        enhanced_message = f"{message} (Context: {recent_context['text'][:100]}...)"
        
        return enhanced_message

    def detect_intent(self, message: str) -> Tuple[QueryIntent, float]:
        """Detect intent with confidence scoring."""
        message = message.lower()
        intent_scores = {intent: 0.0 for intent in QueryIntent}
        
        for intent, config in self.intent_patterns.items():
            score = 0.0
            matches = 0
            
            for pattern, weight in config['patterns']:
                if re.search(pattern, message):
                    score += weight
                    matches += 1
            
            if matches > 0:
                intent_scores[intent] = score / matches
        
        max_intent = max(intent_scores.items(), key=lambda x: x[1])
        
        if max_intent[1] >= self.intent_patterns[max_intent[0]]['threshold']:
            return max_intent[0], max_intent[1]
        
        return QueryIntent.GENERAL, 0.0

    def get_vector_from_message(self, message: str) -> np.ndarray:
        """Convert a message to a vector using the embedding model."""
        vector = self.embedding_model.encode(message)
        return vector

    def calculate_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    def validate_source(self, metadata: Dict) -> Dict:
        """Validate and enhance source metadata."""
        validation_result = {
            'is_valid': True,
            'warnings': [],
            'last_updated': None,
            'source_type': None,
            'reliability_score': 1.0
        }
        
        if 'last_updated' in metadata:
            try:
                last_updated = datetime.fromisoformat(metadata['last_updated'])
                age_days = (datetime.now() - last_updated).days
                
                if age_days > 365:
                    validation_result['warnings'].append('Source is more than a year old')
                    validation_result['reliability_score'] -= 0.2
                
                validation_result['last_updated'] = last_updated
            except ValueError:
                validation_result['warnings'].append('Invalid date format')
        
        if 'url' in metadata:
            validation_result['source_type'] = 'web'
            if not metadata['url'].startswith('https://aphrc.org'):
                validation_result['is_valid'] = False
                validation_result['warnings'].append('Non-APHRC source')
        elif 'filename' in metadata:
            validation_result['source_type'] = 'document'
            if not metadata['filename'].endswith(('.pdf', '.doc', '.docx')):
                validation_result['warnings'].append('Unsupported document format')
        
        return validation_result

    def manage_context_window(self, new_context: Dict):
        """Manage sliding window of conversation context."""
        current_time = time.time()
        
        # Remove expired contexts
        self.context_window = [
            ctx for ctx in self.context_window 
            if current_time - ctx['timestamp'] < self.context_expiry
        ]
        
        # Add new context
        new_context['timestamp'] = current_time
        self.context_window.append(new_context)
        
        # Maintain maximum window size
        if len(self.context_window) > self.max_context_items:
            self.context_window.pop(0)

    def query_redis_data(self, query_vector: np.ndarray, intent: QueryIntent, top_n=3) -> List[Dict]:
        """Query Redis for relevant data with confidence scoring."""
        try:
            results = []
            
            # Define keys pattern based on intent
            if intent == QueryIntent.PUBLICATION:
                # Use the same patterns as used in RedisIndexManager
                text_pattern = "text:publication:*"
                emb_pattern = "emb:publication:*"
                meta_pattern = "meta:publication:*"
            elif intent == QueryIntent.NAVIGATION:
                text_pattern = "web:text:*"
                emb_pattern = "web:emb:*"
                meta_pattern = "meta:web:*"
            else:
                # For general queries, combine results from both types
                return (
                    self.query_redis_data(query_vector, QueryIntent.PUBLICATION, top_n=2) +
                    self.query_redis_data(query_vector, QueryIntent.NAVIGATION, top_n=2)
                )

            emb_keys = self.redis_binary.keys(emb_pattern)
            
            for emb_key in emb_keys:
                emb_key_str = emb_key.decode('utf-8')
                # Get the base key without the 'emb:' prefix
                base_key = emb_key_str.replace('emb:', '')
                
                # Construct related keys
                text_key = f"text:{base_key}"
                meta_key = f"meta:{base_key}"
                
                embedding_bytes = self.redis_binary.get(emb_key)
                if embedding_bytes:
                    embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
                    similarity = self.calculate_similarity(query_vector, embedding)
                    
                    if similarity >= self.confidence_threshold:
                        text = self.redis_text.get(text_key)
                        metadata = self.redis_text.hgetall(meta_key)
                        
                        # Validate source
                        validation = self.validate_source(metadata)
                        
                        results.append({
                            'similarity': similarity,
                            'text': text,
                            'metadata': metadata,
                            'validation': validation,
                            'key': base_key
                        })

            results.sort(key=lambda x: x['similarity'] * x['validation']['reliability_score'], reverse=True)
            return results[:top_n]

        except redis.RedisError as e:
            logger.error(f"Error accessing Redis: {e}")
            return []

    def format_response(self, response: str) -> str:
        """Format the response maintaining HTML structure and beautifying links."""
        # Clean up markdown and basic formatting
        cleaned = re.sub(r'[\*\[\]\(\)]', '', response)
        cleaned = cleaned.replace('\n', ' ').replace('\r', ' ').strip()
        
        # Format lists
        if '• ' in cleaned or '* ' in cleaned:
            items = re.split(r'[•*]\s+', cleaned)
            items = [item.strip() for item in items if item.strip()]
            cleaned = '<ul>' + ''.join([f'<li>{item}</li>' for item in items]) + '</ul>'
        
        # Format URLs
        url_pattern = r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)'
        
        def replace_url(match):
            url = match.group(0)
            display_url = url if len(url) <= 50 else url[:47] + '...'
            
            path_parts = url.split('/')
            title = path_parts[-1] if path_parts[-1] else path_parts[-2]
            title = title.replace('-', ' ').replace('_', ' ').title()
            title = re.sub(r'\.(pdf|doc|docx|html|php|aspx)$', '', title)
            title = re.sub(r'\?.*$', '', title)
            
            return f'<a href="{url}" class="inline-link" target="_blank">{title}</a>'
        
        cleaned = re.sub(url_pattern, replace_url, cleaned)
        
        if not cleaned.startswith(('<ul>', '<p>', '<div')):
            cleaned = f'<p>{cleaned}</p>'
        
        return cleaned

    def create_context(self, relevant_data: List[Dict]) -> str:
        """Create context string from relevant data with improved formatting."""
        context_parts = []
        
        for item in relevant_data:
            text = item['text']
            metadata = item['metadata']
            validation = item['validation']
            
            # Format source reference
            if metadata.get('filename'):
                source_name = metadata['filename'].replace('-', ' ').replace('_', ' ').title()
            else:
                source_name = metadata.get('title', metadata.get('url', 'Unknown source'))
            
            # Add validation warnings if any
            warnings = ""
            if validation['warnings']:
                warnings = f" (Note: {', '.join(validation['warnings'])})"
            
            context_parts.append(f"From '{source_name}'{warnings}: {text[:300]}...")
            
        return "\n\n".join(context_parts)

    async def generate_async_response(self, message: str) -> AsyncIterable[str]:
        """Generate async response with improved formatting and buffering."""
        model = self.get_gemini_model()
        memory = self.create_memory()
        chat_memory = memory.load_memory_variables({})
        history = chat_memory.get("chat_history", [])

        # Process message
        message = self.handle_follow_up(message)
        intent, confidence = self.detect_intent(message)
        query_vector = self.get_vector_from_message(message)
        relevant_data = self.query_redis_data(query_vector, intent)
        
        # Create and manage context
        context = self.create_context(relevant_data)
        self.manage_context_window({'text': context, 'query': message})

        # Prepare messages
        message_list = [
            SystemMessage(content=os.getenv("SYSTEM_INSTRUCTION", 
                "I am a bot that gives responses based on APHRC only and don't answer questions generally but rather in the context of aphrc.org.") + 
                f" The user's intent appears to be related to {intent.value}. Here is the relevant context:\n{context}")
        ]

        if history:
            message_list += history

        message_list.append(HumanMessage(content=message))
        
        try:
            # Initialize response tracking
            response = ""
            buffer = ""
            max_response_length = 500
            sentence_end_chars = {'.', '!', '?'}
            
            async for token in model.astream(input=message_list):
                if not token.content:
                    continue
                    
                buffer += token.content
                
                # Check if we have a complete chunk
                should_yield = (
                    any(char in buffer for char in sentence_end_chars) or
                    len(buffer) >= 100 or
                    '\n' in buffer
                )
                
                if should_yield:
                    formatted_chunk = self.format_response(buffer)
                    response += formatted_chunk
                    
                    if len(response) >= max_response_length:
                        yield formatted_chunk.encode("utf-8", errors="replace")
                        break
                        
                    yield formatted_chunk.encode("utf-8", errors="replace")
                    
                    buffer = ""
            
            # Yield any remaining content in buffer
            if buffer:
                formatted_chunk = self.format_response(buffer)
                yield formatted_chunk.encode("utf-8", errors="replace")
                
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            error_message = self.format_response("I apologize, but I encountered an error. Please try again.")
            yield error_message.encode("utf-8", errors="replace")

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