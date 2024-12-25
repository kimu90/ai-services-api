import logging
from typing import Dict, Optional
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
        """Initialize PublicationProcessor."""
        self.db = db
        self.summarizer = summarizer

    def process_single_work(self, work: Dict, source: str = 'openalex') -> bool:
        """Process a single publication work."""
        try:
            # Extract and clean basic publication data
            doi = safe_str(work.get('doi'))
            if not doi or doi == "N/A":
                logger.warning("Skipping work with no DOI")
                return False

            title = safe_str(work.get('title'))
            if not title:
                logger.warning(f"Skipping work with no title (DOI: {doi})")
                return False

            # Process abstract
            abstract_index = work.get('abstract_inverted_index')
            abstract = convert_inverted_index_to_text(abstract_index)

            # Generate summary with retry logic
            logger.info(f"Generating summary for: {title}")
            summary = self.summarizer.summarize(title, abstract)

            # Truncate text to prevent database overflow
            title = truncate_text(title)
            abstract = truncate_text(abstract)
            summary = truncate_text(summary)

            # Add publication to database
            try:
                self.db.add_publication(
                    doi, 
                    title, 
                    abstract, 
                    summary, 
                    source=source  # Add source parameter
                )
            except Exception as e:
                logger.error(f"Error adding publication to database: {e}")
                return False

            # Process authors
            try:
                for authorship in work.get('authorships', []):
                    self._process_author(authorship, doi)
            except Exception as e:
                logger.error(f"Error processing authors: {e}")

            # Process concepts/tags
            try:
                for concept in work.get('concepts', []):
                    self._process_tag(concept, doi)
            except Exception as e:
                logger.error(f"Error processing concepts: {e}")

            logger.info(f"Successfully processed publication: {title}")
            return True

        except Exception as e:
            logger.error(f"Error processing work: {e}")
            return False

    def _process_author(self, authorship: Dict, doi: str) -> None:
        try:
            author = authorship.get('author', {})
            if not author:
                return

            author_name = author.get('display_name')
            if not author_name:
                return

            orcid = author.get('orcid')
            author_identifier = author.get('id')

            # Add author and create publication link
            try:
                tag_id = self.db.add_author(author_name, orcid, author_identifier)
                self.db.link_author_publication(tag_id, doi)
                logger.debug(f"Processed author: {author_name} for publication {doi}")
            except Exception as e:
                logger.error(f"Error adding author to database: {e}")

        except Exception as e:
            logger.error(f"Error processing author for publication {doi}: {e}")

    def _process_tag(self, concept: Dict, doi: str) -> None:
        """Process a single concept/tag."""
        try:
            tag_name = concept.get('display_name')
            if not tag_name:
                return

            # Add tag and create publication link
            try:
                tag_id = self.db.add_tag(tag_name, 'concept')
                self.db.link_publication_tag(doi, tag_id)
                logger.debug(f"Processed tag: {tag_name} for publication {doi}")
            except Exception as e:
                logger.error(f"Error adding tag to database: {e}")

        except Exception as e:
            logger.error(f"Error processing tag for publication {doi}: {e}")

    def close(self):
        """Clean up resources."""
        if hasattr(self, 'db'):
            self.db.close()
