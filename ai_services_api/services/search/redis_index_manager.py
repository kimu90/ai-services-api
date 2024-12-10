import logging
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
import redis
from dotenv import load_dotenv
from ai_services_api.services.data.database_setup import get_db_connection
import os
import time
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class ExpertRedisIndexManager:
    def __init__(self):
        """Initialize Redis index manager for experts."""
        try:
            load_dotenv()
            self.embedding_model = SentenceTransformer(
                os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
            )
            self.setup_redis_connections()
            logger.info("ExpertRedisIndexManager initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing ExpertRedisIndexManager: {e}")
            raise

    def setup_redis_connections(self):
        """Setup Redis connections with retry logic."""
        max_retries = 5
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
                
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

    def fetch_experts(self) -> List[Dict[str, Any]]:
        """Fetch all expert data."""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            conn = None
            cur = None
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                
                # Check if table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'experts_expert'
                    );
                """)
                if not cur.fetchone()[0]:
                    logger.warning("experts_expert table does not exist yet")
                    return []
                
                # Fetch all expert data
                cur.execute("""
                    SELECT 
                        id,
                        email,
                        knowledge_expertise,
                        is_active,
                        is_staff,
                        created_at,
                        updated_at,
                        bio,
                        orcid,
                        fields,
                        subfields,
                        domains,
                        firstname,
                        lastname,
                        contact_details,
                        unit,
                        normalized_domains,
                        normalized_fields,
                        normalized_skills,
                        keywords
                    FROM experts_expert
                    WHERE id IS NOT NULL
                """)
                
                experts = [{
                    'id': row[0],
                    'email': row[1],
                    'knowledge_expertise': row[2] if row[2] else [],
                    'is_active': row[3],
                    'is_staff': row[4],
                    'created_at': row[5].isoformat() if row[5] else None,
                    'updated_at': row[6].isoformat() if row[6] else None,
                    'bio': row[7] or '',
                    'orcid': row[8],
                    'fields': row[9] if row[9] else [],
                    'subfields': row[10] if row[10] else [],
                    'domains': row[11] if row[11] else [],
                    'firstname': row[12] or '',
                    'lastname': row[13] or '',
                    'contact_details': row[14],
                    'unit': row[15] or '',
                    'normalized_domains': row[16] if row[16] else [],
                    'normalized_fields': row[17] if row[17] else [],
                    'normalized_skills': row[18] if row[18] else [],
                    'keywords': row[19] if row[19] else []
                } for row in cur.fetchall()]
                
                logger.info(f"Fetched {len(experts)} experts from database")
                return experts
                
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    logger.error("All retry attempts failed")
                    raise
            finally:
                if cur:
                    cur.close()
                if conn:
                    conn.close()

    def create_redis_index(self) -> bool:
        """Create Redis indexes for experts."""
        try:
            logger.info("Creating Redis indexes for experts...")
            experts = self.fetch_experts()
            
            if not experts:
                logger.warning("No experts found to index")
                return False
            
            for expert in experts:
                try:
                    # Create combined text for embedding
                    text_content = self._create_text_content(expert)
                    
                    # Generate embedding
                    embedding = self.embedding_model.encode(text_content)
                    
                    # Store in Redis
                    self._store_expert_data(expert, text_content, embedding)
                    
                    logger.info(f"Indexed expert: {expert['firstname']} {expert['lastname']}")
                    
                except Exception as e:
                    logger.error(f"Error indexing expert {expert.get('id', 'Unknown ID')}: {e}")
                    continue
            
            logger.info(f"Successfully created Redis indexes for {len(experts)} experts")
            return True
            
        except Exception as e:
            logger.error(f"Error creating Redis indexes: {e}")
            return False

    def _create_text_content(self, expert: Dict[str, Any]) -> str:
        """Create combined text content for embedding."""
        text_parts = [
            f"Name: {expert['firstname']} {expert['lastname']}",
            f"Email: {expert['email']}" if expert['email'] else "",
            f"Unit: {expert['unit']}" if expert['unit'] else "",
            f"Bio: {expert['bio']}" if expert['bio'] else "",
            f"ORCID: {expert['orcid']}" if expert['orcid'] else "",
            f"Expertise: {' | '.join(expert['knowledge_expertise'])}",
            f"Fields: {' | '.join(expert['fields'])}",
            f"Subfields: {' | '.join(expert['subfields'])}",
            f"Domains: {' | '.join(expert['domains'])}",
            f"Normalized Domains: {' | '.join(expert['normalized_domains'])}",
            f"Normalized Fields: {' | '.join(expert['normalized_fields'])}",
            f"Technical Skills: {' | '.join(expert['normalized_skills'])}",
            f"Keywords: {' | '.join(expert['keywords'])}"
        ]
            
        return '\n'.join(filter(None, text_parts))

    def _store_expert_data(self, expert: Dict[str, Any], text_content: str, 
                          embedding: np.ndarray) -> None:
        """Store expert data in Redis."""
        base_key = f"expert:{expert['id']}"
        
        pipeline = self.redis_text.pipeline()
        try:
            # Store text content
            pipeline.set(f"text:{base_key}", text_content)
            
            # Store embedding as binary
            self.redis_binary.set(
                f"emb:{base_key}", 
                embedding.astype(np.float32).tobytes()
            )
            
            # Store metadata
            metadata = {
                'id': expert['id'],
                'email': expert['email'],
                'name': f"{expert['firstname']} {expert['lastname']}",
                'unit': expert['unit'],
                'bio': expert['bio'],
                'orcid': expert['orcid'],
                'expertise': json.dumps(expert['knowledge_expertise']),
                'fields': json.dumps(expert['fields']),
                'domains': json.dumps(expert['domains']),
                'normalized_skills': json.dumps(expert['normalized_skills']),
                'keywords': json.dumps(expert['keywords']),
                'is_active': json.dumps(expert['is_active']),
                'updated_at': expert['updated_at']
            }
            pipeline.hset(f"meta:{base_key}", mapping=metadata)
            
            pipeline.execute()
            
        except Exception as e:
            pipeline.reset()
            raise e

    def clear_redis_indexes(self) -> bool:
        """Clear all expert Redis indexes."""
        try:
            patterns = ['text:expert:*', 'emb:expert:*', 'meta:expert:*']
            for pattern in patterns:
                cursor = 0
                while True:
                    cursor, keys = self.redis_text.scan(cursor, match=pattern, count=100)
                    if keys:
                        self.redis_text.delete(*keys)
                    if cursor == 0:
                        break
            
            logger.info("Cleared all expert Redis indexes")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing Redis indexes: {e}")
            return False

    def get_expert_embedding(self, expert_id: str) -> Optional[np.ndarray]:
        """Retrieve expert embedding from Redis."""
        try:
            embedding_bytes = self.redis_binary.get(f"emb:expert:{expert_id}")
            if embedding_bytes:
                return np.frombuffer(embedding_bytes, dtype=np.float32)
            return None
        except Exception as e:
            logger.error(f"Error retrieving expert embedding: {e}")
            return None

    def get_expert_metadata(self, expert_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve expert metadata from Redis."""
        try:
            metadata = self.redis_text.hgetall(f"meta:expert:{expert_id}")
            if metadata:
                # Parse JSON fields
                for field in ['expertise', 'fields', 'domains', 'normalized_skills', 'keywords']:
                    if metadata.get(field):
                        metadata[field] = json.loads(metadata[field])
                return metadata
            return None
        except Exception as e:
            logger.error(f"Error retrieving expert metadata: {e}")
            return None

    def close(self):
        """Close Redis connections."""
        try:
            if hasattr(self, 'redis_text'):
                self.redis_text.close()
            if hasattr(self, 'redis_binary'):
                self.redis_binary.close()
            logger.info("Redis connections closed")
        except Exception as e:
            logger.error(f"Error closing Redis connections: {e}")

    def __del__(self):
        """Ensure connections are closed on deletion."""
        self.close()