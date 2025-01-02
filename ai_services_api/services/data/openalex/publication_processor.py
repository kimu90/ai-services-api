import logging
from typing import Dict, Optional, List, Any
from ai_services_api.services.data.openalex.database_manager import DatabaseManager
from ai_services_api.services.data.openalex.ai_summarizer import TextSummarizer
from ai_services_api.services.data.openalex.text_processor import (
    safe_str, 
    convert_inverted_index_to_text, 
    truncate_text
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class PublicationProcessor:
    def __init__(self, db: DatabaseManager, summarizer: TextSummarizer):
        """
        Initialize PublicationProcessor.
        
        Args:
            db: Database manager instance
            summarizer: Text summarizer instance
        """
        self.db = db
        self.summarizer = summarizer
        self._setup_database_indexes()

    def _setup_database_indexes(self) -> None:
        """Create necessary database indexes if they don't exist."""
        try:
            indexes = [
                """
                CREATE INDEX IF NOT EXISTS idx_resources_doi 
                ON resources_resource(doi);
                """,
                """
                CREATE INDEX IF NOT EXISTS idx_authors_name 
                ON authors_ai(name);
                """,
                """
                CREATE INDEX IF NOT EXISTS idx_author_publication 
                ON author_publication_ai(doi, author_id);
                """,
                """
                CREATE INDEX IF NOT EXISTS idx_publication_tags 
                ON publication_tags(doi, tag_id);
                """
            ]
            
            for index_sql in indexes:
                self.db.execute(index_sql)
            logger.info("Database indexes verified/created successfully")
        except Exception as e:
            logger.error(f"Error setting up database indexes: {e}")

    def _doi_exists(self, doi: str) -> bool:
        """
        Check if a DOI already exists in the database.
        
        Args:
            doi: Digital Object Identifier to check
            
        Returns:
            bool: True if DOI exists, False otherwise
        """
        try:
            result = self.db.execute("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM resources_resource 
                    WHERE doi = %s
                )
            """, (doi,))
            return result[0][0] if result else False
        except Exception as e:
            logger.error(f"Error checking DOI existence: {e}")
            return False

    def _clean_and_validate_work(self, work: Dict) -> tuple[Optional[str], Optional[str]]:
        """
        Clean and validate work data.
        
        Args:
            work: Publication work dictionary
            
        Returns:
            tuple: (doi, title) if valid, (None, None) if invalid
        """
        try:
            doi = safe_str(work.get('doi'))
            if not doi or doi == "N/A":
                logger.warning("Invalid DOI")
                return None, None

            title = safe_str(work.get('title'))
            if not title:
                logger.warning(f"Invalid title for DOI: {doi}")
                return None, None

            return doi, title
        except Exception as e:
            logger.error(f"Error in work validation: {e}")
            return None, None

    def process_single_work(self, work: Dict, source: str = 'openalex') -> bool:
        """
        Process a single publication work.
        
        Args:
            work: Publication work dictionary
            source: Source of the publication (default: 'openalex')
            
        Returns:
            bool: True if processing successful, False otherwise
        """
        try:
            # Clean and validate work
            doi, title = self._clean_and_validate_work(work)
            if not doi or not title:
                return False

            # Check for existing DOI
            if self._doi_exists(doi):
                logger.info(f"Publication with DOI {doi} already exists. Skipping.")
                return False

            # Process abstract
            abstract_index = work.get('abstract_inverted_index')
            abstract = convert_inverted_index_to_text(abstract_index)
            if not abstract:
                abstract = "No abstract available."

            # Generate summary
            try:
                logger.info(f"Generating summary for: {title}")
                summary = self.summarizer.summarize(title, abstract)
            except Exception as e:
                logger.error(f"Error generating summary: {e}")
                summary = "Summary generation failed."

            # Truncate texts
            title = truncate_text(title, max_length=500)
            abstract = truncate_text(abstract, max_length=5000)
            summary = truncate_text(summary, max_length=1000)

            # Extract additional metadata
            metadata = self._extract_metadata(work)

            # Add publication to database with transaction
            try:
                self.db.execute("BEGIN")
                
                # Add main publication record
                self.db.add_publication(
                    doi=doi,
                    title=title,
                    abstract=abstract,
                    summary=summary,
                    source=source,
                    **metadata
                )

                # Process authors
                for authorship in work.get('authorships', []):
                    self._process_author(authorship, doi)

                # Process concepts/tags
                for concept in work.get('concepts', []):
                    self._process_tag(concept, doi)

                self.db.execute("COMMIT")
                logger.info(f"Successfully processed publication: {title}")
                return True

            except Exception as e:
                self.db.execute("ROLLBACK")
                logger.error(f"Error in database transaction: {e}")
                return False

        except Exception as e:
            logger.error(f"Error processing work: {e}")
            return False

    def _extract_metadata(self, work: Dict) -> Dict[str, Any]:
        """
        Extract additional metadata from work.
        
        Args:
            work: Publication work dictionary
            
        Returns:
            dict: Extracted metadata
        """
        try:
            return {
                'type': safe_str(work.get('type')),
                'publication_year': work.get('publication_year'),
                'citation_count': work.get('cited_by_count'),
                'language': safe_str(work.get('language')),
                'publisher': safe_str(work.get('publisher')),
                'journal': safe_str(work.get('host_venue', {}).get('display_name')),
                'fields_of_study': work.get('fields_of_study', [])
            }
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            return {}

    def _process_author(self, authorship: Dict, doi: str) -> None:
        """
        Process a single author and link to publication.
        
        Args:
            authorship: Author information dictionary
            doi: Publication DOI
        """
        try:
            author = authorship.get('author', {})
            if not author:
                return

            author_name = author.get('display_name')
            if not author_name:
                return

            orcid = author.get('orcid')
            author_identifier = author.get('id')
            
            # Add author with additional information
            author_info = {
                'name': author_name,
                'orcid': orcid,
                'author_identifier': author_identifier,
                'affiliations': [
                    aff.get('display_name') 
                    for aff in authorship.get('institutions', [])
                ],
                'is_corresponding': authorship.get('is_corresponding', False)
            }

            try:
                author_id = self.db.add_author(author_info)
                self.db.link_author_publication(author_id, doi)
                logger.debug(f"Processed author: {author_name} for publication {doi}")
            except Exception as e:
                logger.error(f"Error adding author to database: {e}")

        except Exception as e:
            logger.error(f"Error processing author for publication {doi}: {e}")

    def _process_tag(self, concept: Dict, doi: str) -> None:
        """
        Process a single concept/tag and link to publication.
        
        Args:
            concept: Concept information dictionary
            doi: Publication DOI
        """
        try:
            tag_name = concept.get('display_name')
            if not tag_name:
                return

            tag_info = {
                'name': tag_name,
                'type': 'concept',
                'score': concept.get('score'),
                'level': concept.get('level'),
                'wikidata_id': concept.get('wikidata')
            }

            try:
                tag_id = self.db.add_tag(tag_info)
                self.db.link_publication_tag(doi, tag_id)
                logger.debug(f"Processed tag: {tag_name} for publication {doi}")
            except Exception as e:
                logger.error(f"Error adding tag to database: {e}")

        except Exception as e:
            logger.error(f"Error processing tag for publication {doi}: {e}")

    def process_batch(self, works: List[Dict], source: str = 'openalex') -> int:
        """
        Process a batch of works.
        
        Args:
            works: List of publication work dictionaries
            source: Source of the publications (default: 'openalex')
            
        Returns:
            int: Number of successfully processed works
        """
        successful = 0
        for work in works:
            try:
                if self.process_single_work(work, source):
                    successful += 1
            except Exception as e:
                logger.error(f"Error processing work in batch: {e}")
                continue
        return successful

    def close(self) -> None:
        """Clean up resources."""
        try:
            if hasattr(self, 'db'):
                self.db.close()
            logger.info("PublicationProcessor resources cleaned up")
        except Exception as e:
            logger.error(f"Error closing resources: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
