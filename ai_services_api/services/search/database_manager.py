import os
import logging
from typing import List, Dict, Any, Tuple, Optional
from dotenv import load_dotenv
from ai_services_api.services.data.database_setup import get_db_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        """Initialize database connection and cursor."""
        self.conn = get_db_connection()
        self.cur = self.conn.cursor()

    def execute(self, query: str, params: tuple = None) -> List[Tuple[Any, ...]]:
        """Execute a query and return results if any."""
        try:
            self.cur.execute(query, params)
            self.conn.commit()
            if self.cur.description:  # If the query returns results
                return self.cur.fetchall()
            return []
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Query execution failed: {str(e)}\nQuery: {query}\nParams: {params}")
            raise

    def add_expert(self, firstname: str, lastname: str, 
                  knowledge_expertise: List[str] = None,
                  domains: List[str] = None,
                  fields: List[str] = None,
                  subfields: List[str] = None,
                  orcid: str = None) -> str:
        """Add or update an expert in the database."""
        try:
            # Convert empty strings to None
            orcid = orcid if orcid and orcid.strip() else None
            
            self.cur.execute("""
                INSERT INTO experts_expert 
                (firstname, lastname, knowledge_expertise, domains, fields, subfields, orcid)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (orcid) 
                WHERE orcid IS NOT NULL AND orcid != ''
                DO UPDATE SET
                    firstname = EXCLUDED.firstname,
                    lastname = EXCLUDED.lastname,
                    knowledge_expertise = EXCLUDED.knowledge_expertise,
                    domains = EXCLUDED.domains,
                    fields = EXCLUDED.fields,
                    subfields = EXCLUDED.subfields
                RETURNING id
            """, (firstname, lastname, 
                  knowledge_expertise or [], 
                  domains or [], 
                  fields or [], 
                  subfields or [], 
                  orcid))
            
            expert_id = self.cur.fetchone()[0]
            self.conn.commit()
            logger.info(f"Added/updated expert data for {firstname} {lastname}")
            return expert_id
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error adding expert {firstname} {lastname}: {e}")
            raise

    def add_publication(self, doi: str, title: str, abstract: str, summary: str) -> None:
        """Add or update a publication in the database."""
        try:
            self.execute("""
                INSERT INTO resources_resource (doi, title, abstract, summary)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (doi) DO UPDATE 
                SET title = EXCLUDED.title,
                    abstract = EXCLUDED.abstract,
                    summary = EXCLUDED.summary
            """, (doi, title, abstract, summary))
            logger.info(f"Added/updated publication: {title}")
        except Exception as e:
            logger.error(f"Error adding publication: {e}")
            raise

    def add_author(self, name: str, orcid: Optional[str] = None, 
                  author_identifier: Optional[str] = None) -> int:
        """Add an author and return their ID."""
        try:
            result = self.execute("""
                INSERT INTO authors (name, orcid, author_identifier)
                VALUES (%s, %s, %s)
                ON CONFLICT (orcid) 
                WHERE orcid IS NOT NULL
                DO UPDATE SET
                    name = EXCLUDED.name,
                    author_identifier = EXCLUDED.author_identifier
                RETURNING author_id
            """, (name, orcid, author_identifier))
            
            return result[0][0]
        except Exception as e:
            logger.error(f"Error adding author {name}: {e}")
            raise

    def add_tag(self, tag_name: str, tag_type: str) -> int:
        """Add a tag and return its ID."""
        try:
            result = self.execute("""
                INSERT INTO tags (tag_name)
                VALUES (%s)
                ON CONFLICT (tag_name) DO UPDATE
                SET tag_name = EXCLUDED.tag_name
                RETURNING tag_id
            """, (tag_name,))
            
            return result[0][0]
        except Exception as e:
            logger.error(f"Error adding tag {tag_name}: {e}")
            raise

    def link_author_publication(self, author_id: int, doi: str) -> None:
        """Link an author to a publication."""
        try:
            self.execute("""
                INSERT INTO publication_authors (doi, author_id)
                VALUES (%s, %s)
                ON CONFLICT (doi, author_id) DO NOTHING
            """, (doi, author_id))
        except Exception as e:
            logger.error(f"Error linking author {author_id} to publication {doi}: {e}")
            raise

    def link_publication_tag(self, doi: str, tag_id: int) -> None:
        """Link a tag to a publication."""
        try:
            self.execute("""
                INSERT INTO publication_tags (doi, tag_id)
                VALUES (%s, %s)
                ON CONFLICT (doi, tag_id) DO NOTHING
            """, (doi, tag_id))
        except Exception as e:
            logger.error(f"Error linking tag {tag_id} to publication {doi}: {e}")
            raise

    def update_expert(self, expert_id: str, updates: Dict[str, Any]) -> None:
        """Update expert information."""
        try:
            set_clauses = []
            params = []
            for key, value in updates.items():
                set_clauses.append(f"{key} = %s")
                params.append(value)
            
            params.append(expert_id)
            query = f"""
                UPDATE experts_expert 
                SET {', '.join(set_clauses)}
                WHERE id = %s
            """
            
            self.execute(query, tuple(params))
            logger.info(f"Expert {expert_id} updated successfully")
            
        except Exception as e:
            logger.error(f"Error updating expert {expert_id}: {e}")
            raise

    def get_expert_by_name(self, firstname: str, lastname: str) -> Optional[Tuple]:
        """Get expert by firstname and lastname."""
        try:
            result = self.execute("""
                SELECT id, firstname, lastname, knowledge_expertise, domains, fields, subfields, orcid
                FROM experts_expert
                WHERE firstname = %s AND lastname = %s
            """, (firstname, lastname))
            
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Error retrieving expert {firstname} {lastname}: {e}")
            raise

    def get_recent_queries(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get most recent search queries."""
        try:
            result = self.execute("""
                SELECT query_id, query, timestamp, result_count, search_type
                FROM query_history_ai
                ORDER BY timestamp DESC
                LIMIT %s
            """, (limit,))
            
            return [{
                'query_id': row[0],
                'query': row[1],
                'timestamp': row[2].isoformat(),
                'result_count': row[3],
                'search_type': row[4]
            } for row in result]
            
        except Exception as e:
            logger.error(f"Error getting recent queries: {e}")
            return []

    def get_term_frequencies(self, expert_id: Optional[int] = None) -> Dict[str, int]:
        """Get term frequency dictionary"""
        try:
            if expert_id:
                result = self.execute("""
                    SELECT term, frequency 
                    FROM term_frequencies 
                    WHERE expert_id = %s AND last_updated >= NOW() - INTERVAL '30 days'
                """, (expert_id,))
            else:
                result = self.execute("""
                    SELECT term, SUM(frequency) as total_frequency
                    FROM term_frequencies 
                    WHERE last_updated >= NOW() - INTERVAL '30 days'
                    GROUP BY term
                """)
            
            return dict(result) if result else {}
            
        except Exception as e:
            logger.error(f"Error getting term frequencies: {e}")
            return {}

    def get_popular_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most popular search queries."""
        try:
            result = self.execute("""
                SELECT query, COUNT(*) as count
                FROM query_history_ai
                GROUP BY query
                ORDER BY count DESC
                LIMIT %s
            """, (limit,))
            
            return [{
                'query': row[0],
                'count': row[1]
            } for row in result]
            
        except Exception as e:
            logger.error(f"Error getting popular queries: {e}")
            return []

    def get_user_queries(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent queries for a specific user."""
        try:
            result = self.execute("""
                SELECT query_id, query, timestamp, result_count, search_type
                FROM query_history_ai
                WHERE user_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """, (user_id, limit))
            
            return [{
                'query_id': row[0],
                'query': row[1],
                'timestamp': row[2].isoformat(),
                'result_count': row[3],
                'search_type': row[4]
            } for row in result]
            
        except Exception as e:
            logger.error(f"Error getting user queries: {e}")
            return []

    def add_query(self, query: str, result_count: int, search_type: str = 'semantic', 
                 user_id: Optional[str] = None) -> Optional[int]:
        """Add a search query to history."""
        try:
            result = self.execute("""
                INSERT INTO query_history_ai (query, result_count, search_type, user_id)
                VALUES (%s, %s, %s, %s)
                RETURNING query_id
            """, (query, result_count, search_type, user_id))
            
            return result[0][0] if result else None
            
        except Exception as e:
            logger.error(f"Error adding query to history: {e}")
            raise

    def close(self):
        """Close database connection."""
        if hasattr(self, 'cur') and self.cur:
            self.cur.close()
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def __del__(self):
        """Destructor to ensure connection is closed."""
        self.close()