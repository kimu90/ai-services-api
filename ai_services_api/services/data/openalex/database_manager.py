import os
import logging
from typing import List, Dict, Any, Tuple, Optional
from dotenv import load_dotenv
from ai_services_api.services.data.database_setup import get_db_connection
import json

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

    def execute(self, query: str, params: tuple = None) -> Any:
        """
        Execute a query and optionally return results if available.

        Args:
            query (str): The SQL query to execute.
            params (tuple, optional): Parameters to include in the query.

        Returns:
            Any: If the query returns results (e.g., SELECT), a list of tuples is returned.
                 Otherwise, None is returned for queries like INSERT, UPDATE, DELETE.
        """
        try:
            self.cur.execute(query, params)
            self.conn.commit()

            if self.cur.description:  # Checks if the query returns results
                return self.cur.fetchall()  # Return results for SELECT queries
            return None  # Return None for non-SELECT queries

        except Exception as e:
            self.conn.rollback()  # Rollback the transaction on error
            logger.error(f"Query execution failed: {str(e)}\nQuery: {query}\nParams: {params}")
            raise

    def add_expert(self, first_name: str, last_name: str, 
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
                (first_name, last_name, knowledge_expertise, domains, fields, subfields, orcid)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (orcid) 
                WHERE orcid IS NOT NULL AND orcid != ''
                DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    knowledge_expertise = EXCLUDED.knowledge_expertise,
                    domains = EXCLUDED.domains,
                    fields = EXCLUDED.fields,
                    subfields = EXCLUDED.subfields
                RETURNING id
            """, (first_name, last_name, 
                  knowledge_expertise or [], 
                  domains or [], 
                  fields or [], 
                  subfields or [], 
                  orcid))
            
            expert_id = self.cur.fetchone()[0]
            self.conn.commit()
            logger.info(f"Added initial expert data for {first_name} {last_name}")
            return expert_id
            
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error adding expert {first_name} {last_name}: {e}")
            raise

    # In DatabaseManager class:
    def add_publication(self, title: str, abstract: str, summary: str, source: str = 'openalex', 
                    doi: Optional[str] = None, **metadata) -> None:
        """Add or update a publication in the database."""
        try:
            if doi:
                # If DOI exists, use it as primary identifier
                existing = self.execute("""
                    SELECT doi FROM resources_resource WHERE doi = %s
                """, (doi,))
            else:
                # If no DOI, check by title
                existing = self.execute("""
                    SELECT doi FROM resources_resource WHERE title = %s
                """, (title,))

            # Build the complete publication data
            publication_data = {
                'doi': doi,
                'title': title,
                'abstract': abstract,
                'summary': summary,
                'authors': metadata.get('authors', []),
                'description': metadata.get('description', abstract),
                'expert_id': metadata.get('expert_id'),
                'type': metadata.get('type', 'unknown'),
                'subtitles': metadata.get('subtitles', '{}'),
                'publishers': metadata.get('publishers', '{}'),
                'collection': metadata.get('collection', 'default'),
                'date_issue': metadata.get('date_issue'),
                'citation': metadata.get('citation'),
                'language': metadata.get('language', 'en'),
                'identifiers': metadata.get('identifiers', '{}'),
                'source': source
            }

            if existing:
                # Update existing publication
                update_query = """
                    UPDATE resources_resource
                    SET title = %(title)s,
                        abstract = %(abstract)s,
                        summary = %(summary)s,
                        authors = %(authors)s,
                        description = %(description)s,
                        expert_id = %(expert_id)s,
                        type = %(type)s,
                        subtitles = %(subtitles)s,
                        publishers = %(publishers)s,
                        collection = %(collection)s,
                        date_issue = %(date_issue)s,
                        citation = %(citation)s,
                        language = %(language)s,
                        identifiers = %(identifiers)s,
                        source = %(source)s
                    WHERE {}
                """.format('doi = %(doi)s' if doi else 'title = %(title)s')
                
                self.execute(update_query, publication_data)
                logger.info(f"Updated publication: {title} (Source: {source})")
            else:
                # Insert new publication
                self.execute("""
                    INSERT INTO resources_resource 
                    (doi, title, abstract, summary, authors, description,
                    expert_id, type, subtitles, publishers, collection,
                    date_issue, citation, language, identifiers, source)
                    VALUES (
                        %(doi)s, %(title)s, %(abstract)s, %(summary)s, %(authors)s,
                        %(description)s, %(expert_id)s, %(type)s, %(subtitles)s,
                        %(publishers)s, %(collection)s, %(date_issue)s, %(citation)s,
                        %(language)s, %(identifiers)s, %(source)s
                    )
                """, publication_data)
                logger.info(f"Added publication: {title} (Source: {source})")

        except Exception as e:
            logger.error(f"Error adding/updating publication: {e}")
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

    def get_expert_by_name(self, first_name: str, last_name: str) -> Optional[Tuple]:
        """Get expert by first_name and last_name."""
        try:
            result = self.execute("""
                SELECT id, first_name, last_name, knowledge_expertise, domains, fields, subfields, orcid
                FROM experts_expert
                WHERE first_name = %s AND last_name = %s
            """, (first_name, last_name))
            
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Error retrieving expert {first_name} {last_name}: {e}")
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
    def add_tag(self, tag_info: Dict) -> int:
        """
        Add a tag to the database or return existing tag ID.
        
        Args:
            tag_info: Dictionary containing:
                - name: Name of the tag
                - tag_type: Type of tag (author/domain)
                - additional_metadata: JSON metadata for the tag
        
        Returns:
            int: ID of the added or existing tag
        """
        try:
            # First, check if the tag already exists
            result = self.execute("""
                SELECT tag_id FROM tags 
                WHERE tag_name = %s AND tag_type = %s
            """, (tag_info['name'], tag_info['tag_type']))
            
            if result:
                return result[0][0]
            
            # Insert new tag
            result = self.execute("""
                INSERT INTO tags (tag_name, tag_type, additional_metadata) 
                VALUES (%s, %s, %s)
                RETURNING tag_id
            """, (
                tag_info['name'],
                tag_info['tag_type'],
                tag_info.get('additional_metadata', '{}')
            ))
            
            if result:
                tag_id = result[0][0]
                logger.info(f"Added new tag: {tag_info['name']} (type: {tag_info['tag_type']})")
                return tag_id
            
            raise ValueError(f"Failed to add tag: {tag_info['name']}")
        
        except Exception as e:
            logger.error(f"Error adding tag {tag_info}: {e}")
            raise
    def link_publication_tag(self, identifier: str, tag_id: int) -> None:
        """
        Link a publication with a tag using either DOI or title.
        
        Args:
            identifier: Either DOI or title of the publication
            tag_id: ID of the tag
        """
        try:
            # Check if the link already exists
            result = self.execute("""
                SELECT 1 FROM publication_tags 
                WHERE (doi = %s OR title = %s) AND tag_id = %s
            """, (identifier, identifier, tag_id))
            
            if result:
                return
            
            # Create new link
            self.execute("""
                INSERT INTO publication_tags (doi, title, tag_id)
                VALUES (%s, %s, %s)
            """, (identifier if '10.' in identifier else None,  # Assume it's a DOI if it starts with '10.'
                identifier if '10.' not in identifier else None,
                tag_id))
            
            logger.info(f"Linked publication {identifier} with tag {tag_id}")
        
        except Exception as e:
            logger.error(f"Error linking publication {identifier} with tag {tag_id}: {e}")
            raise
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
    def add_author(self, author_name: str, orcid: Optional[str] = None, author_identifier: Optional[str] = None) -> int:
        """
        Add an author as a tag or return existing tag ID.
        
        Args:
            author_name (str): Name of the author.
            orcid (str, optional): ORCID identifier of the author.
            author_identifier (str, optional): Other identifier for the author.
        
        Returns:
            int: ID of the added or existing tag.
        """
        try:
            # First, check if the author tag already exists
            result = self.execute("""
                SELECT tag_id FROM tags 
                WHERE tag_name = %s AND tag_type = 'author'
            """, (author_name,))
            
            if result:
                # Author tag already exists, return its ID
                return result[0][0]
            
            # Insert new author tag
            result = self.execute("""
                INSERT INTO tags (tag_name, tag_type, additional_metadata) 
                VALUES (%s, 'author', %s)
                RETURNING tag_id
            """, (author_name, json.dumps({
                'orcid': orcid,
                'author_identifier': author_identifier
            })))
            
            if result:
                tag_id = result[0][0]
                logger.info(f"Added new author tag: {author_name}")
                return tag_id
            
            raise ValueError(f"Failed to add author tag: {author_name}")
        
        except Exception as e:
            logger.error(f"Error adding author tag {author_name}: {e}")
            raise

    def link_author_publication(self, author_id: int, identifier: str) -> None:
        """
        Link an author with a publication using either DOI or title.
        
        Args:
            author_id: ID of the author tag
            identifier: Either DOI or title of the publication
        """
        try:
            # Check if the link already exists
            result = self.execute("""
                SELECT 1 FROM publication_tags 
                WHERE (doi = %s OR title = %s) AND tag_id = %s
            """, (identifier, identifier, author_id))
            
            if result:
                return
            
            # Create new link
            self.execute("""
                INSERT INTO publication_tags (doi, title, tag_id)
                VALUES (%s, %s, %s)
            """, (identifier if '10.' in identifier else None,  # Assume it's a DOI if it starts with '10.'
                identifier if '10.' not in identifier else None,
                author_id))
            
            logger.info(f"Linked publication {identifier} with author tag {author_id}")
        
        except Exception as e:
            logger.error(f"Error linking publication {identifier} with author tag {author_id}: {e}")
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
