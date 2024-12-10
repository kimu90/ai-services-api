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
    EXPERT = "expert"
    FIELD = "field"
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
        
        # Initialize Redis connections with retry logic
        self.setup_redis_connections()
        
        # Load embedding model
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Initialize intent patterns
        self.intent_patterns = {
            QueryIntent.EXPERT: {
                'patterns': [
                    (r'expert', 1.0),
                    (r'researcher', 0.9),
                    (r'scientist', 0.9),
                    (r'professional', 0.8),
                    (r'specialist', 0.8),
                    (r'knowledge', 0.7),
                    (r'expertise', 0.7),
                    (r'field', 0.6),
                    (r'domain', 0.6),
                    (r'research area', 0.8)
                ],
                'threshold': 0.7
            },
            QueryIntent.FIELD: {
                'patterns': [
                    (r'field', 1.0),
                    (r'domain', 1.0),
                    (r'specialty', 0.9),
                    (r'subject', 0.8),
                    (r'area', 0.8),
                    (r'discipline', 0.8),
                    (r'expertise', 0.7),
                    (r'research', 0.7),
                    (r'study', 0.6)
                ],
                'threshold': 0.6
            }
        }

    def setup_redis_connections(self):
        """Setup Redis connections with retry logic."""
        max_retries = 5
        retry_delay = 2

        for attempt in range(max_retries):
            try:
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
                
                # Test connections
                self.redis_text.ping()
                self.redis_binary.ping()
                
                logger.info("Redis connections established successfully")
                return
                
            except redis.ConnectionError as e:
                if attempt == max_retries - 1:
                    logger.error("Failed to connect to Redis after maximum retries")
                    raise
                logger.warning(f"Redis connection attempt {attempt + 1} failed, retrying...")
                time.sleep(retry_delay)

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
        
        if max_intent[1] >= self.intent_patterns[max_intent[0]].get('threshold', 0.6):
            return max_intent[0], max_intent[1]
        
        return QueryIntent.GENERAL, 0.0

    def get_vector_from_message(self, message: str) -> np.ndarray:
        """Convert a message to a vector using the embedding model."""
        return self.embedding_model.encode(message)

    def calculate_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    def validate_source(self, metadata: Dict) -> Dict:
        """Validate and enhance source metadata."""
        validation_result = {
            'is_valid': True,
            'warnings': [],
            'last_updated': None,
            'source_type': 'expert',
            'reliability_score': 1.0
        }
        
        if 'updated_at' in metadata:
            try:
                last_updated = datetime.fromisoformat(metadata['updated_at'])
                age_days = (datetime.now() - last_updated).days
                
                if age_days > 365:
                    validation_result['warnings'].append('Expert data is more than a year old')
                    validation_result['reliability_score'] -= 0.2
                
                validation_result['last_updated'] = last_updated
            except (ValueError, TypeError):
                validation_result['warnings'].append('Invalid date format')
        
        if not metadata.get('specialties', {}).get('expertise'):
            validation_result['warnings'].append('No expertise data available')
            validation_result['reliability_score'] -= 0.3
        
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
        """Query Redis for relevant expert data with confidence scoring."""
        try:
            results = []
            
            # Define keys pattern based on intent
            if intent == QueryIntent.EXPERT:
                # Use patterns for expert-specific searches
                text_pattern = "text:expert:*"
                emb_pattern = "emb:expert:*"
                meta_pattern = "meta:expert:*"
            elif intent == QueryIntent.FIELD:
                # Use patterns for field-specific searches
                text_pattern = "text:expert:*"  # Still use expert pattern but will filter by fields
                emb_pattern = "emb:expert:*"
                meta_pattern = "meta:expert:*"
            else:
                # For general queries, search all expert data
                text_pattern = "text:expert:*"
                emb_pattern = "emb:expert:*"
                meta_pattern = "meta:expert:*"

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
                        
                        # Parse JSON fields
                        formatted_metadata = {
                            'id': metadata.get('id'),
                            'name': metadata.get('name'),
                            'specialties': {
                                'expertise': json.loads(metadata.get('expertise', '[]')),
                                'fields': json.loads(metadata.get('fields', '[]')),
                                'domains': json.loads(metadata.get('domains', '[]')),
                                'normalized_skills': json.loads(metadata.get('normalized_skills', '[]'))
                            },
                            'unit': metadata.get('unit'),
                            'updated_at': metadata.get('updated_at')
                        }
                        
                        # Additional field-specific filtering for FIELD intent
                        if intent == QueryIntent.FIELD:
                            fields = formatted_metadata['specialties']['fields']
                            domains = formatted_metadata['specialties']['domains']
                            if not any(field.lower() in query_vector.lower() 
                                     for field in fields + domains):
                                continue
                        
                        results.append({
                            'similarity': similarity,
                            'text': text,
                            'metadata': formatted_metadata,
                            'validation': self.validate_source(formatted_metadata),
                            'key': base_key
                        })

            results.sort(key=lambda x: x['similarity'] * x['validation']['reliability_score'], 
                        reverse=True)
            return results[:top_n]

        except redis.RedisError as e:
            logger.error(f"Error accessing Redis: {e}")
            return []

    def create_context(self, relevant_data: List[Dict]) -> str:
        """Create context string from relevant expert data with improved formatting."""
        context_parts = []
        
        for item in relevant_data:
            text = item['text']
            metadata = item['metadata']
            validation = item['validation']
            
            # Format expert reference
            expert_name = metadata.get('name', 'Unknown Expert')
            unit = metadata.get('unit', '')
            specialties = metadata.get('specialties', {})
            
            # Create a summary of expertise
            expertise_summary = []
            if specialties.get('expertise'):
                expertise_summary.extend(specialties['expertise'][:3])
            if specialties.get('fields'):
                expertise_summary.extend(specialties['fields'][:2])
            
            expertise_text = ', '.join(expertise_summary) if expertise_summary else 'No specific expertise listed'
            
            # Add validation warnings if any
            warnings = ""
            if validation['warnings']:
                warnings = f" (Note: {', '.join(validation['warnings'])})"
            
            context_parts.append(
                f"Expert: {expert_name} ({unit})\n"
                f"Expertise: {expertise_text}{warnings}\n"
                f"Details: {text[:300]}..."
            )
            
        return "\n\n".join(context_parts)

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
        
        # Format expert references
        expert_pattern = r'Expert:\s+([^(]+)\s*\(([^)]+)\)'
        cleaned = re.sub(expert_pattern, r'<strong>\1</strong> <em>(\2)</em>', cleaned)
        
        # Format expertise sections
        expertise_pattern = r'Expertise:\s+([^(]+)'
        cleaned = re.sub(expertise_pattern, r'<br>Expertise: <span class="expertise">\1</span>', cleaned)
        
        if not cleaned.startswith(('<ul>', '<p>', '<div')):
            cleaned = f'<p>{cleaned}</p>'
        
        return cleaned

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

        # Prepare system instruction based on intent
        system_instruction = (
            "I am an AI assistant specializing in providing information about APHRC experts and their work. "
            f"The user's query appears to be related to {intent.value}. Based on our expert database:\n{context}"
        )

        # Prepare messages
        message_list = [SystemMessage(content=system_instruction)]

        if history:
            message_list.extend(history)

        message_list.append(HumanMessage(content=message))
        
        try:
            # Initialize response tracking
            response = ""
            buffer = ""
            max_response_length = 800  # Increased for expert responses
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
            error_message = self.format_response(
                "I apologize, but I encountered an error while retrieving expert information. Please try rephrasing your question."
            )
            yield error_message.encode("utf-8", errors="replace")

    def get_gemini_model(self):
        """Initialize and return the Gemini model."""
        return ChatGoogleGenerativeAI(
            google_api_key=self.api_key,
            stream=True,
            model="gemini-pro",
            convert_system_message_to_human=True,
            callbacks=[self.callback],
            temperature=0.7,
            top_p=0.9,
            top_k=40,
        )

    def create_memory(self):
        """Create conversation memory."""
        return ConversationBufferWindowMemory(
            k=5,
            max_token_limit=4000,
            return_messages=True
        )

    def __del__(self):
        """Cleanup when the instance is deleted."""
        try:
            if hasattr(self, 'redis_text'):
                self.redis_text.close()
            if hasattr(self, 'redis_binary'):
                self.redis_binary.close()
        except:
            pass