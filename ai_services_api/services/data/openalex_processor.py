import os
import requests
from dotenv import load_dotenv
import google.generativeai as genai
from typing import Optional, Dict, Any, List, Tuple
import psycopg2
import logging
import csv
import asyncio
import aiohttp
import pandas as pd
import json

from ai_services_api.services.data.database_setup import get_db_connection

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

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
        if not abstract or abstract.strip() == "N/A":
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
    return str(value) if value is not None else "N/A"

class DatabaseManager:
    def __init__(self):
        self.conn = get_db_connection()
        self.cur = self.conn.cursor()

    def add_tag(self, tag_name: str, tag_type: str = 'general') -> int:
        """Add a tag and return its ID. If tag exists, return existing ID."""
        try:
            full_tag_name = f"{tag_type}:{tag_name}"
            self.cur.execute(
                "SELECT tag_id FROM tags WHERE tag_name = %s",
                (full_tag_name,)
            )
            result = self.cur.fetchone()
            if result:
                return result[0]
            
            self.cur.execute(
                "INSERT INTO tags (tag_name) VALUES (%s) RETURNING tag_id",
                (full_tag_name,)
            )
            tag_id = self.cur.fetchone()[0]
            self.conn.commit()
            return tag_id
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error adding tag: {e}")
            raise

    def add_author(self, name: str, orcid: str = None, author_identifier: str = None) -> int:
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

    def add_expert(self, orcid: str, firstname: str, lastname: str, 
                  domains: List[str], fields: List[str], subfields: List[str]) -> None:
        """Add or update an expert in the database."""
        try:
            self.cur.execute("""
                INSERT INTO experts (orcid, firstname, lastname, domains, fields, subfields)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (orcid) DO UPDATE 
                SET firstname = EXCLUDED.firstname,
                    lastname = EXCLUDED.lastname,
                    domains = EXCLUDED.domains,
                    fields = EXCLUDED.fields,
                    subfields = EXCLUDED.subfields
            """, (orcid, firstname, lastname, domains, fields, subfields))
            self.conn.commit()
            logger.info(f"Expert {firstname} {lastname} added/updated successfully")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error adding expert: {e}")
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
        self.institution_id = os.getenv('OPENALEX_INSTITUTION_ID', 'I4210129448')  # APHRC institution ID
        self.db = DatabaseManager()
    
    def _process_single_work(self, work: Dict) -> bool:
        """Process a single work and return True if successful."""
        try:
            doi = safe_str(work.get('doi'))
            if doi == "N/A":
                return False

            title = safe_str(work.get('title'))
            logger.info(f"Generating summary for: {title}")
            
            abstract_index = work.get('abstract_inverted_index')
            abstract = convert_inverted_index_to_text(abstract_index)
            summary = summarize(title, abstract)
            
            # Add publication to database
            self.db.add_publication(doi, title, abstract, summary)
            
            # Process authors
            for authorship in work.get('authorships', []):
                author_name = authorship.get('author', {}).get('display_name')
                orcid = authorship.get('author', {}).get('orcid')
                author_identifier = authorship.get('author', {}).get('id')
                
                if author_name:
                    author_id = self.db.add_author(author_name, orcid, author_identifier)
                    self.db.link_author_publication(author_id, doi)
            
            # Process tags/concepts
            for tag in work.get('concepts', []):
                tag_name = tag.get('display_name')
                if tag_name:
                    tag_id = self.db.add_tag(tag_name, 'field_of_study')
                    self.db.link_publication_tag(doi, tag_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing individual work: {e}")
            return False
    
    def process_works(self, max_publications: int = 4):
        """Process works and save to database."""
        if max_publications <= 0:
            logger.info("No publications requested")
            return

        processed_count = 0
        try:
            # Only fetch one page with exactly the number of items we need
            url = f"{self.base_url}/works?filter=institutions.id:{self.institution_id}&per_page=4"  # Hardcoded to exactly 4
            logger.info(f"Fetching data from: {url}")
            
            response = requests.get(url, headers={'User-Agent': 'APHRC Publication Processor/1.0'})
            response.raise_for_status()
            data = response.json()
            
            if not data.get('results'):
                logger.info("No results found")
                return

            # Only process up to max_publications results
            for i, work in enumerate(data['results']):
                if i >= max_publications:  # Zero-based index check
                    logger.info(f"Reached limit of {max_publications} publications")
                    break
                
                success = self._process_single_work(work)
                if success:
                    processed_count += 1
                    logger.info(f"Processed {processed_count}/4 publications")  # Hardcoded to exactly 4
                
                if processed_count >= max_publications:
                    logger.info(f"Successfully processed {max_publications} publications")
                    break

        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in process_works: {e}")
        finally:
            logger.info(f"Finished processing {processed_count} publications")

    async def get_expert_works(self, session: aiohttp.ClientSession, openalex_id: str, 
                             retries: int = 3, delay: int = 5) -> List[Dict]:
        """Fetch works for an expert with retries and rate limiting."""
        works_url = f"{self.base_url}/works"
        params = {
            'filter': f"authorships.author.id:https://openalex.org/A{openalex_id}",
            'per-page': 50
        }

        logger.info(f"Fetching works for OpenAlex_ID: {openalex_id}")
        logger.debug(f"Works API URL: {works_url}")
        logger.debug(f"Query params: {params}")

        attempt = 0
        while attempt < retries:
            try:
                async with session.get(works_url, params=params) as response:
                    logger.debug(f"Response status: {response.status}")

                    if response.status == 200:
                        works_data = await response.json()
                        logger.debug(f"Retrieved {len(works_data.get('results', []))} works")
                        return works_data.get('results', [])
                    
                    elif response.status == 429:  # Rate limit error
                        logger.warning(f"Rate limit hit, retrying... (attempt {attempt + 1}/{retries})")
                        await asyncio.sleep(delay * (attempt + 1))
                    else:
                        logger.error(f"Error fetching works: {response.status}")
                        break

            except Exception as e:
                logger.error(f"Error fetching works for {openalex_id}: {e}")
            
            attempt += 1
            await asyncio.sleep(delay)
        
        return []

    async def get_expert_domains(self, session: aiohttp.ClientSession, 
                               firstname: str, lastname: str, openalex_id: str) -> Tuple[List, List, List]:
        """Extract domains, fields, and subfields from expert's works."""
        works = await self.get_expert_works(session, openalex_id)
        
        domains = set()
        fields = set()
        subfields = set()

        logger.info(f"Processing {len(works)} works for {firstname} {lastname}")

        for work in works:
            topics = work.get('topics', [])
            
            if not topics:
                logger.debug(f"No topics found for work by {firstname} {lastname}")
                continue

            for topic in topics:
                domain = topic.get('domain', {}).get('display_name')
                field = topic.get('field', {}).get('display_name')
                topic_subfields = [sf.get('display_name') for sf in topic.get('subfields', [])]

                if domain:
                    domains.add(domain)
                if field:
                    fields.add(field)
                subfields.update(topic_subfields)

        logger.info(f"Found {len(domains)} domains, {len(fields)} fields, {len(subfields)} subfields for {firstname} {lastname}")
        return list(domains), list(fields), list(subfields)

    
    def get_expert_openalex_data(self, firstname: str, lastname: str) -> Tuple[str, str]:
        """Fetch ORCID and OpenAlex ID for an expert."""
        search_url = f"{self.base_url}/authors"
        params = {"search": f"{firstname} {lastname}"}
        
        logger.info(f"Searching for expert: {firstname} {lastname}")
        
        try:
            response = requests.get(search_url, params=params)
            response.raise_for_status()
            
            if response.status_code == 200:
                results = response.json().get('results', [])
                if results:
                    author = results[0]
                    orcid = author.get('orcid', '')
                    openalex_id = author.get('id', '').split('/')[-1]
                    
                    logger.info(f"Found ORCID: {orcid}, OpenAlex ID: {openalex_id}")
                    return orcid, openalex_id
                
                logger.warning(f"No results found for {firstname} {lastname}")
        except requests.RequestException as e:
            logger.error(f"Error fetching data for {firstname} {lastname}: {e}")
        return '', ''

    async def process_experts(self, csv_path: str):
        """Process experts from CSV and store in database."""
        try:
            # Read the CSV file
            df = pd.read_csv(csv_path)
            logger.info(f"Processing {len(df)} experts from {csv_path}")

            # Create async session for processing works
            async with aiohttp.ClientSession() as session:
                for _, row in df.iterrows():
                    firstname = row['Firstname']
                    lastname = row['Lastname']
                    
                    logger.info(f"Processing expert: {firstname} {lastname}")
                    
                    # Get ORCID and OpenAlex ID
                    orcid, openalex_id = self.get_expert_openalex_data(firstname, lastname)
                    
                    if openalex_id:
                        # Get domains, fields, and subfields
                        domains, fields, subfields = await self.get_expert_domains(
                            session, firstname, lastname, openalex_id
                        )
                        
                        if orcid:  # Only add experts with ORCID
                            self.db.add_expert(
                                orcid=orcid,
                                firstname=firstname,
                                lastname=lastname,
                                domains=domains,
                                fields=fields,
                                subfields=subfields
                            )
                            logger.info(f"Successfully processed expert: {firstname} {lastname}")
                        else:
                            logger.warning(f"No ORCID found for {firstname} {lastname}")
                    else:
                        logger.warning(f"No OpenAlex ID found for {firstname} {lastname}")

        except Exception as e:
            logger.error(f"Error processing experts: {e}")
            raise

    def close(self):
        """Close database connection and manager."""
        self.db.close()

async def main():
    processor = OpenAlexProcessor()
    try:
        # Process publications
        processor.process_works(max_publications=4)
        
        # Process experts
        await processor.process_experts("sme.csv")
        
    except Exception as e:
        logger.error(f"Error in main process: {e}")
    finally:
        processor.close()

if __name__ == "__main__":
    asyncio.run(main())