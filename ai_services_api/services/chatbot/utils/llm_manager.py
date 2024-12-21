import logging
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import AsyncIterable, List, Dict, Tuple, Optional, Any
from enum import Enum
from langchain.schema.messages import HumanMessage, SystemMessage
from langchain.memory import ConversationBufferWindowMemory
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.callbacks import AsyncIteratorCallbackHandler
import redis
from dotenv import load_dotenv
import os
import time
import json
from datetime import datetime
import re

# Import the unified data manager
from .data_manager import APHRCDataManager  # Add this import
from .db_utils import DatabaseConnector

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class QueryIntent(Enum):
    NAVIGATION = "navigation"
    PUBLICATION = "publication"
    GENERAL = "general"

class CustomAsyncCallbackHandler(AsyncIteratorCallbackHandler):
    """Custom callback handler with all required methods implemented."""
    
    async def on_chat_model_start(self, *args, **kwargs):
        """Handle chat model start."""
        pass

    async def on_llm_start(self, *args, **kwargs):
        """Handle LLM start."""
        pass

    async def on_llm_new_token(self, token: str, *args, **kwargs):
        """Handle new token."""
        if token:
            self.queue.put_nowait(token)

    async def on_llm_end(self, *args, **kwargs):
        """Handle LLM end."""
        self.queue.put_nowait(None)

    async def on_llm_error(self, error: Exception, *args, **kwargs):
        """Handle LLM error."""
        self.queue.put_nowait(f"Error: {str(error)}")

class GeminiLLMManager:
    def __init__(self):
        """Initialize the LLM manager with the unified APHRC data manager."""
        try:
            load_dotenv()
            self.api_key = os.getenv("GEMINI_API_KEY")
            self.callback = CustomAsyncCallbackHandler()
            self.confidence_threshold = 0.6
            
            # Initialize the unified data manager
            self.data_manager = APHRCDataManager()
            
            # Initialize context management
            self.context_window = []
            self.max_context_items = 5
            self.context_expiry = 1800  # 30 minutes
            
            # Initialize intent patterns for different content types
            self.intent_patterns = {
                QueryIntent.NAVIGATION: {
                    'patterns': [
                        (r'website', 1.0),
                        (r'page', 0.9),
                        (r'find', 0.8),
                        (r'where', 0.8),
                        (r'how to', 0.7),
                        (r'navigate', 0.9),
                        (r'section', 0.8),
                        (r'content', 0.7),
                        (r'information about', 0.7)
                    ],
                    'threshold': 0.6
                },
                QueryIntent.PUBLICATION: {
                    'patterns': [
                        (r'research', 1.0),
                        (r'paper', 1.0),
                        (r'publication', 1.0),
                        (r'study', 0.9),
                        (r'article', 0.9),
                        (r'journal', 0.8),
                        (r'doi', 0.9),
                        (r'published', 0.8),
                        (r'authors', 0.8),
                        (r'findings', 0.7)
                    ],
                    'threshold': 0.6
                }
            }
            
            logger.info("GeminiLLMManager initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing GeminiLLMManager: {e}")
            raise


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
        
        if max_intent[1] >= self.intent_patterns.get(max_intent[0], {}).get('threshold', 0.6):
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

    async def query_relevant_content(self, message: str, intent: QueryIntent) -> List[Dict[str, Any]]:
        """Query relevant content using the unified data manager."""
        try:
            results = await self.data_manager.query_content(message, intent)
            return results
        except Exception as e:
            logger.error(f"Error querying content: {e}")
            return []

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
        """Create context string from relevant content."""
        context_parts = []
        
        for item in relevant_data:
            text = item['text']
            metadata = item['metadata']
            content_type = metadata.get('type', 'unknown')
            
            if content_type == 'navigation':
                # Format website content
                context_parts.append(
                    f"Website Section: {metadata.get('title', 'Untitled')}\n"
                    f"URL: {metadata.get('url', 'No URL')}\n"
                    f"Content: {text[:300]}..."
                )
            elif content_type == 'publication':
                # Format publication content
                authors = json.loads(metadata.get('authors', '[]'))
                context_parts.append(
                    f"Publication: {metadata.get('title', 'Untitled')}\n"
                    f"Authors: {', '.join(authors) if authors else 'Unknown'}\n"
                    f"DOI: {metadata.get('doi', 'No DOI')}\n"
                    f"Content: {text[:300]}..."
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

    async def analyze_sentiment(self, message: str) -> Dict:
        """Analyze sentiment of a message using existing Gemini model."""
        try:
            # Construct prompt for sentiment analysis with explicit instruction
            prompt = """Analyze the sentiment of this message and return a JSON object. 
            Return ONLY the JSON object with no markdown formatting, no code blocks, and no additional text.
            
            Required format:
            {
                "sentiment_score": <float between -1 and 1>,
                "emotion_labels": [<array of emotion strings>],
                "confidence": <float between 0 and 1>,
                "aspects": {
                    "satisfaction": <float between 0 and 1>,
                    "urgency": <float between 0 and 1>,
                    "clarity": <float between 0 and 1>
                }
            }
            Message to analyze: """ + message
            
            response = await self.get_gemini_model().ainvoke(prompt)
            cleaned_response = response.content.strip()
            cleaned_response = cleaned_response.replace('```json', '').replace('```', '').strip()
            
            try:
                sentiment_data = json.loads(cleaned_response)
                logger.info(f"Sentiment analysis result: {sentiment_data}")
                return sentiment_data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse sentiment analysis response: {cleaned_response}")
                logger.error(f"JSON parse error: {e}")
                return {
                    'sentiment_score': 0.0,
                    'emotion_labels': ['neutral'],
                    'confidence': 0.0,
                    'aspects': {
                        'satisfaction': 0.0,
                        'urgency': 0.0,
                        'clarity': 0.0
                    }
                }
                
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {e}")
            return {
                'sentiment_score': 0.0,
                'emotion_labels': ['neutral'],
                'confidence': 0.0,
                'aspects': {
                    'satisfaction': 0.0,
                    'urgency': 0.0,
                    'clarity': 0.0
                }
            }

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

    def _create_system_message(self, intent: QueryIntent) -> str:
        """Create appropriate system message based on intent."""
        base_message = "You are an AI assistant for APHRC (African Population and Health Research Center). "
        
        if intent == QueryIntent.NAVIGATION:
            return base_message + """
            You help users navigate and understand APHRC's website content. 
            Focus on providing clear directions and explanations about where to find information.
            When referencing website sections, include the relevant URLs.
            """
        elif intent == QueryIntent.PUBLICATION:
            return base_message + """
            You help users find and understand APHRC's research publications. 
            Focus on summarizing research findings and providing citation information.
            Include DOIs when available and highlight key findings from the research.
            """
        else:
            return base_message + """
            You provide comprehensive information about APHRC's work, combining both 
            website navigation help and research publication information as needed.
            """

    async def generate_async_response(self, message: str) -> AsyncIterable[Dict[str, Any]]:
        """Generate async response with integrated content."""
        start_time = time.time()
        
        try:
            # Process message and detect intent
            message = self.handle_follow_up(message)
            intent, confidence = self.detect_intent(message)
            
            # Get relevant content using unified data manager
            relevant_data = await self.query_relevant_content(message, intent)
            
            # Add sentiment analysis
            sentiment_data = await self.analyze_sentiment(message)
            
            # Create context and manage window
            context = self.create_context(relevant_data)
            self.manage_context_window({'text': context, 'query': message})
            
            # Track content matches for analytics
            content_matches = []
            for data in relevant_data:
                content_matches.append({
                    'type': data['metadata'].get('type', 'unknown'),
                    'id': data['metadata'].get('id', 'unknown'),
                    'similarity_score': data['similarity'],
                    'rank_position': len(content_matches) + 1
                })

            # Prepare system message based on intent
            system_message = self._create_system_message(intent)
            
            # Generate response
            response_chunks = []
            buffer = ""
            
            messages = [
                SystemMessage(content=system_message),
                HumanMessage(content=f"Context: {context}\n\nQuery: {message}")
            ]
            
            async for token in self.get_gemini_model().astream(messages):
                if not token.content:
                    continue
                    
                buffer += token.content
                if self.should_yield_buffer(buffer):
                    formatted_chunk = self.format_response(buffer)
                    response_chunks.append(formatted_chunk)
                    yield {
                        'chunk': formatted_chunk.encode("utf-8", errors="replace"),
                        'is_metadata': False
                    }
                    buffer = ""
            
            # Handle remaining buffer
            if buffer:
                formatted_chunk = self.format_response(buffer)
                response_chunks.append(formatted_chunk)
                yield {
                    'chunk': formatted_chunk.encode("utf-8", errors="replace"),
                    'is_metadata': False
                }

            # Prepare final metadata
            final_response = ''.join(response_chunks)
            response_time = time.time() - start_time
            
            metadata = {
                'response': final_response,
                'timestamp': datetime.now().isoformat(),
                'metrics': {
                    'response_time': response_time,
                    'intent': {
                        'type': intent.value,
                        'confidence': confidence
                    },
                    'content_matches': len(content_matches),
                    'content_types': {
                        'navigation': sum(1 for m in content_matches if m['type'] == 'navigation'),
                        'publication': sum(1 for m in content_matches if m['type'] == 'publication')
                    },
                    'sentiment': sentiment_data
                },
                'error_occurred': False
            }
            
            yield {
                'is_metadata': True,
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            yield self._generate_error_response(start_time)
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
            if hasattr(self, 'db_conn'):
                self.db_conn.close()
        except:
            pass

    def should_yield_buffer(self, buffer: str) -> bool:
        """Determine if the buffer should be yielded."""
        return len(buffer) >= 100 or '.' in buffer or '\n' in buffer
