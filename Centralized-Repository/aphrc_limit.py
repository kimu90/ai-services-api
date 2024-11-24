import os
import requests
from dotenv import load_dotenv
import google.generativeai as genai
from typing import Optional, Dict, Any
import psycopg2
from psycopg2 import sql
from urllib.parse import urlparse
import logging

# Set up logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def get_db_connection():
    """
    Create a connection to PostgreSQL database using environment variables,
    with fallback support for local development or Docker environments.
    """
    # Check if we're running in Docker
    in_docker = os.getenv('DOCKER_ENV', 'false').lower() == 'true'
    
    # Use DATABASE_URL if provided, else fallback to environment variables
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        parsed_url = urlparse(database_url)
        host = parsed_url.hostname
        port = parsed_url.port
        dbname = parsed_url.path[1:]  # Removing the leading '/'
        user = parsed_url.username
        password = parsed_url.password
    else:
        # Fallback to environment variables for local or Docker development
        host = 'postgres' if in_docker else 'localhost'
        port = '5432'
        dbname = os.getenv('POSTGRES_DB', 'aphrcdb')
        user = os.getenv('POSTGRES_USER', 'aphrcuser')
        password = os.getenv('POSTGRES_PASSWORD', 'kimu')

    try:
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Error connecting to the database: {e}")
        logger.error("\nConnection Details:")
        logger.error(f"Database: {dbname}")
        logger.error(f"User: {user}")
        logger.error(f"Host: {host}")
        logger.error(f"Port: {port}")
        raise

def setup_gemini():
    """Initialize the Gemini API with the API key."""
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-pro')

def summarize(title: str, abstract: str) -> Optional[str]:
    """Create a summary using Gemini AI."""
    try:
        if abstract == "N/A":
            return "No abstract available for summarization"
            
        model = setup_gemini()
        prompt = f"""
        Please create a concise summary combining the following title and abstract.
        Title: {title}
        Abstract: {abstract}
        
        Please provide a clear and concise summary in 2-3 sentences.
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error in summarization: {e}")
        return "Failed to generate summary"

def convert_inverted_index_to_text(inverted_index: Dict) -> str:
    """Convert an inverted index to readable text."""
    if not inverted_index:
        return "N/A"
    
    try:
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        return ' '.join(word for _, word in sorted(word_positions))
    except Exception as e:
        logger.error(f"Error converting inverted index: {e}")
        return "N/A"

def safe_str(value: Any) -> str:
    """Convert a value to string, handling None values."""
    if value is None:
        return "N/A"
    return str(value)

class DatabaseManager:
    def __init__(self):
        self.conn = get_db_connection()
        self.cur = self.conn.cursor()

    def add_tag(self, tag_name: str, tag_type: str) -> int:
        """Add a tag and return its ID. If tag exists, return existing ID."""
        try:
            self.cur.execute(
                "SELECT tag_id FROM tags WHERE tag_name = %s",
                (f"{tag_type}:{tag_name}",)
            )
            result = self.cur.fetchone()
            if result:
                return result[0]
            
            self.cur.execute(
                "INSERT INTO tags (tag_name) VALUES (%s) RETURNING tag_id",
                (f"{tag_type}:{tag_name}",)
            )
            tag_id = self.cur.fetchone()[0]
            self.conn.commit()
            return tag_id
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error adding tag: {e}")
            raise

    def add_author(self, name: str, orcid: str, author_identifier: str) -> int:
        """Add an author and return their ID. If author exists, return existing ID."""
        try:
            self.cur.execute("""
                SELECT author_id FROM authors 
                WHERE name = %s AND (orcid = %s OR author_identifier = %s)
            """, (name, orcid, author_identifier))
            result = self.cur.fetchone()
            if result:
                return result[0]
            
            self.cur.execute("""
                INSERT INTO authors (name, orcid, author_identifier)
                VALUES (%s, %s, %s) RETURNING author_id
            """, (name, orcid, author_identifier))
            author_id = self.cur.fetchone()[0]
            self.conn.commit()
            return author_id
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error adding author: {e}")
            raise

    def add_publication(self, doi: str, title: str, abstract: str, summary: str) -> None:
        """Add a publication to the database."""
        try:
            self.cur.execute("""
                INSERT INTO publications (doi, title, abstract, summary)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (doi) DO UPDATE 
                SET title = EXCLUDED.title,
                    abstract = EXCLUDED.abstract,
                    summary = EXCLUDED.summary
            """, (doi, title, abstract, summary))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error adding publication: {e}")
            raise

    def link_publication_tag(self, doi: str, tag_id: int) -> None:
        """Link a publication with a tag."""
        try:
            self.cur.execute("""
                INSERT INTO publication_tag (publication_doi, tag_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (doi, tag_id))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error linking publication and tag: {e}")
            raise

    def link_author_publication(self, author_id: int, doi: str) -> None:
        """Link an author with a publication."""
        try:
            self.cur.execute("""
                INSERT INTO author_publication (author_id, doi)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (author_id, doi))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error linking author and publication: {e}")
            raise

    def close(self):
        """Close database connection."""
        self.cur.close()
        self.conn.close()

class OpenAlexProcessor:
    def __init__(self):
        """Initialize the OpenAlex processor."""
        self.base_url = os.getenv('OPENALEX_API_URL', 'https://api.openalex.org')
        self.institution_id = 'I4210129448'  # APHRC institution ID
        self.db = DatabaseManager()
    
    def process_works(self):
        """Process works and save to database, limited to 10 publications."""
        url = f"{self.base_url}/works?filter=institutions.id:{self.institution_id}&per_page=200"
        processed_count = 0
        
        while url and processed_count < 10:
            try:
                logger.info(f"Fetching data from: {url}")
                response = requests.get(url, headers={'User-Agent': 'YourApp/1.0'})
                response.raise_for_status()
                data = response.json()
                
                if 'results' not in data:
                    logger.warning("No results found in response")
                    break
                
                for work in data['results']:
                    if processed_count >= 10:
                        break
                    try:
                        doi = safe_str(work.get('doi'))
                        if doi == "N/A":
                            continue
                            
                        title = safe_str(work.get('title'))
                        abstract_index = work.get('abstract_inverted_index')
                        abstract = convert_inverted_index_to_text(abstract_index)
                        
                        # Generate summary
                        logger.info(f"Generating summary for: {title}")
                        summary = summarize(title, abstract)
                        
                        # Add publication to database
                        self.db.add_publication(doi, title, abstract, summary)
                        
                        # Process authors
                        for authorship in work.get('authorships', []):
                            author_name = authorship.get('author', {}).get('display_name')
                            orcid = authorship.get('author', {}).get('orcid')
                            author_identifier = authorship.get('author', {}).get('author_identifier')
                            
                            author_id = self.db.add_author(author_name, orcid, author_identifier)
                            self.db.link_author_publication(author_id, doi)
                        
                        # Process tags
                        for tag in work.get('concepts', []):
                            tag_name = tag.get('display_name')
                            tag_id = self.db.add_tag(tag_name, 'field_of_study')
                            self.db.link_publication_tag(doi, tag_id)
                        
                        processed_count += 1
                        logger.info(f"Processed {processed_count} publications so far.")
                        
                    except Exception as e:
                        logger.error(f"Error processing work with DOI {doi}: {e}")
                
                # Check if there's a next page of results
                url = data.get('meta', {}).get('next')
                if not url:
                    break
            
            except requests.RequestException as e:
                logger.error(f"Request failed: {e}")
                break
        logger.info("Finished processing publications")

if __name__ == "__main__":
    processor = OpenAlexProcessor()
    processor.process_works()
    processor.db.close()
