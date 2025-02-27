import os
import requests
from dotenv import load_dotenv
import google.generativeai as genai
from typing import Optional, Dict, Any, List, Tuple
import logging
import csv
import asyncio
import aiohttp
import pandas as pd
import json
from ai_services_api.services.data.db_utils import get_db_connection

load_dotenv()

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def setup_gemini():
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-pro')

def summarize(title: str, abstract: str) -> Optional[str]:
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

def categorize_expertise(expertise_list: List[str]) -> Optional[Dict[str, Any]]:
    try:
        if not expertise_list:
            return None
            
        model = setup_gemini()
        prompt = f"""
        Given these areas of expertise: {', '.join(expertise_list)}
        
        Please categorize each expertise into academic domains, fields, and subfields.
        Format the response as JSON with this structure:
        {{
            "categorized_expertise": [
                {{
                    "original_term": "original expertise term",
                    "domain": "broader domain category",
                    "field": "specific field",
                    "subfield": "specific subfield if applicable, or null"
                }}
            ]
        }}
        
        Be specific and consistent with academic categorization.
        """
        response = model.generate_content(prompt)
        return json.loads(response.text)
    except Exception as e:
        logger.error(f"Error in expertise categorization: {e}")
        return None

def convert_inverted_index_to_text(inverted_index: Dict) -> str:
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
    return str(value) if value is not None else "N/A"

class DatabaseManager:
    def __init__(self):
        self.conn = get_db_connection()
        self.cur = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        try:
            # Add expertise column to experts_ai if it doesn't exist
            self.cur.execute("""
                ALTER TABLE experts_ai
                ADD COLUMN IF NOT EXISTS expertise TEXT[]
            """)
            
            # Create expertise_categories table if it doesn't exist
            self.cur.execute("""
                CREATE TABLE IF NOT EXISTS expertise_categories (
                    id SERIAL PRIMARY KEY,
                    expert_orcid TEXT REFERENCES experts_ai(orcid),
                    original_term TEXT,
                    domain TEXT,
                    field TEXT,
                    subfield TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.conn.commit()
            logger.info("Database tables initialized successfully")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error creating tables: {e}")
            raise

    def add_tag(self, tag_name: str, tag_type: str = 'general') -> int:
        try:
            full_tag_name = f"{tag_type}:{tag_name}"
            self.cur.execute(
                "SELECT tag_id FROM tags_ai WHERE tag_name = %s",
                (full_tag_name,)
            )
            result = self.cur.fetchone()
            if result:
                return result[0]
            
            self.cur.execute(
                "INSERT INTO tags_ai (tag_name) VALUES (%s) RETURNING tag_id",
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
        try:
            self.cur.execute("""
                SELECT author_id FROM authors_ai 
                WHERE name = %s AND (orcid = %s OR author_identifier = %s)
            """, (name, orcid, author_identifier))
            result = self.cur.fetchone()
            if result:
                return result[0]
            
            self.cur.execute("""
                INSERT INTO authors_ai (name, orcid, author_identifier)
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
        try:
            self.cur.execute("""
                INSERT INTO publications_ai (doi, title, abstract, summary)
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

    def add_expert(self, orcid: str, first_name: str, last_name: str, 
                  domains: List[str], fields: List[str], subfields: List[str],
                  expertise: List[str] = None) -> None:
        try:
            self.cur.execute("""
                INSERT INTO experts_ai 
                (orcid, first_name, last_name, domains, fields, subfields, expertise)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (orcid) DO UPDATE 
                SET first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    domains = EXCLUDED.domains,
                    fields = EXCLUDED.fields,
                    subfields = EXCLUDED.subfields,
                    expertise = EXCLUDED.expertise
            """, (orcid, first_name, last_name, domains, fields, subfields, expertise))
            self.conn.commit()
            logger.info(f"Expert {first_name} {last_name} added/updated successfully")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error adding expert: {e}")
            raise

    def add_expertise_categories(self, expert_orcid: str, categorized_expertise: Dict[str, Any]) -> None:
        try:
            if not categorized_expertise or 'categorized_expertise' not in categorized_expertise:
                return

            for item in categorized_expertise['categorized_expertise']:
                self.cur.execute("""
                    INSERT INTO expertise_categories 
                    (expert_orcid, original_term, domain, field, subfield)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    expert_orcid,
                    item['original_term'],
                    item['domain'],
                    item['field'],
                    item.get('subfield')
                ))
            
            self.conn.commit()
            logger.info(f"Added expertise categories for expert {expert_orcid}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error adding expertise categories: {e}")
            raise

    def link_publication_tag(self, doi: str, tag_id: int) -> None:
        try:
            self.cur.execute("""
                INSERT INTO publication_tag_ai (publication_doi, tag_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (doi, tag_id))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error linking publication and tag: {e}")
            raise

    def link_author_publication(self, author_id: int, doi: str) -> None:
        try:
            self.cur.execute("""
                INSERT INTO author_publication_ai (author_id, doi)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (author_id, doi))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error linking author and publication: {e}")
            raise

    def close(self):
        self.cur.close()
        self.conn.close()

class OpenAlexProcessor:
    def __init__(self):
        self.base_url = os.getenv('OPENALEX_API_URL', 'https://api.openalex.org')
        self.institution_id = os.getenv('OPENALEX_INSTITUTION_ID', 'I4210129448')
        self.db = DatabaseManager()
    
    def _process_single_work(self, work: Dict) -> bool:
        try:
            doi = safe_str(work.get('doi'))
            if doi == "N/A":
                return False

            title = safe_str(work.get('title'))
            logger.info(f"Generating summary for: {title}")
            
            abstract_index = work.get('abstract_inverted_index')
            abstract = convert_inverted_index_to_text(abstract_index)
            summary = summarize(title, abstract)
            
            self.db.add_publication(doi, title, abstract, summary)
            
            for authorship in work.get('authorships', []):
                author_name = authorship.get('author', {}).get('display_name')
                orcid = authorship.get('author', {}).get('orcid')
                author_identifier = authorship.get('author', {}).get('id')
                
                if author_name:
                    author_id = self.db.add_author(author_name, orcid, author_identifier)
                    self.db.link_author_publication(author_id, doi)
            
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
        if max_publications <= 0:
            logger.info("No publications requested")
            return

        processed_count = 0
        try:
            url = f"{self.base_url}/works?filter=institutions.id:{self.institution_id}&per_page=4"
            logger.info(f"Fetching data from: {url}")
            
            response = requests.get(url, headers={'User-Agent': 'APHRC Publication Processor/1.0'})
            response.raise_for_status()
            data = response.json()
            
            if not data.get('results'):
                logger.info("No results found")
                return

            for i, work in enumerate(data['results']):
                if i >= max_publications:
                    break
                
                success = self._process_single_work(work)
                if success:
                    processed_count += 1
                    logger.info(f"Processed {processed_count}/4 publications")
                
                if processed_count >= max_publications:
                    break

        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in process_works: {e}")
        finally:
            logger.info(f"Finished processing {processed_count} publications")

    async def get_expert_works(self, session: aiohttp.ClientSession, openalex_id: str, 
                             retries: int = 3, delay: int = 5) -> List[Dict]:
        works_url = f"{self.base_url}/works"
        params = {
            'filter': f"authorships.author.id:https://openalex.org/A{openalex_id}",
            'per-page': 50
        }

        logger.info(f"Fetching works for OpenAlex_ID: {openalex_id}")
        
        attempt = 0
        while attempt < retries:
            try:
                async with session.get(works_url, params=params) as response:
                    if response.status == 200:
                        works_data = await response.json()
                        return works_data.get('results', [])
                    
                    elif response.status == 429:
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
                               first_name: str, last_name: str, openalex_id: str) -> Tuple[List, List, List]:
        works = await self.get_expert_works(session, openalex_id)
        
        domains = set()
        fields = set()
        subfields = set()

        logger.info(f"Processing {len(works)} works for {first_name} {last_name}")

        for work in works:
            topics = work.get('topics', [])
            
            if not topics:
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

        return list(domains), list(fields), list(subfields)

    def get_expert_openalex_data(self, first_name: str, last_name: str) -> Tuple[str, str]:
        search_url = f"{self.base_url}/authors"
        params = {"search": f"{first_name} {last_name}"}
        
        try:
            response = requests.get(search_url, params=params)
            response.raise_for_status()
            
            if response.status_code == 200:
                results = response.json().get('results', [])
                if results:
                    author = results[0]
                    orcid = author.get('orcid', '')
                    openalex_id = author.get('id', '').split('/')[-1]
                    return orcid, openalex_id
                
        except requests.RequestException as e:
            logger.error(f"Error fetching data for {first_name} {last_name}: {e}")
        return '', ''

    async def process_expertise_csv(self, csv_path: str):
        try:
            df = pd.read_csv(csv_path)
            for _, row in df.iterrows():
                expertise_str = row['Knowledge and Expertise']
                if pd.isna(expertise_str):
                    continue

                # Clean and split expertise properly
                expertise_list = [
                    exp.strip() 
                    for exp in expertise_str.split(',') 
                    if exp and exp.strip()
                ]

                # Generate unique identifier from email
                email = row.get('Contact Details', '')
                expert_id = email.split('@')[0] if email else None

                if expert_id and expertise_list:
                    # Store expertise as array
                    self.db.add_expert(
                        orcid=expert_id,
                        first_name=row['first_name'],
                        last_name=row['last_name'],
                        domains=[],
                        fields=[],
                        subfields=[],
                        expertise=expertise_list  # This should now be clean
                    )
                    
                    # Get categorized expertise using Gemini
                    categorized = categorize_expertise(expertise_list)
                    
                    # Generate a unique identifier from email
                    email = row.get('Contact Details', '')
                    expert_id = email.split('@')[0] if email else None
                    
                    if expert_id and categorized:
                        # Update expert record with expertise array
                        self.db.add_expert(
                            orcid=expert_id,
                            first_name=row['first_name'],
                            last_name=row['last_name'],
                            domains=[],  # These will be populated from OpenAlex if available
                            fields=[],
                            subfields=[],
                            expertise=expertise_list
                        )
                    
                    # Add categorized expertise
                    self.db.add_expertise_categories(expert_id, categorized)
                    logger.info(f"Processed expertise for {row['first_name']} {row['last_name']}")

        except Exception as e:
            logger.error(f"Error processing expertise CSV: {e}")
            raise

    async def process_experts(self, csv_path: str):
        try:
            df = pd.read_csv(csv_path)
            logger.info(f"Processing {len(df)} experts from {csv_path}")

            async with aiohttp.ClientSession() as session:
                for _, row in df.iterrows():
                    first_name = row['first_name']
                    last_name = row['last_name']
                    
                    orcid, openalex_id = self.get_expert_openalex_data(first_name, last_name)
                    
                    if openalex_id:
                        domains, fields, subfields = await self.get_expert_domains(
                            session, first_name, last_name, openalex_id
                        )
                        
                        if orcid:
                            # Get existing expertise using the database manager
                            cur = self.db.conn.cursor()
                            cur.execute(
                                "SELECT expertise FROM experts_ai WHERE orcid = %s",
                                (orcid,)
                            )
                            result = cur.fetchone()
                            existing_expertise = result[0] if result else []
                            cur.close()

                            self.db.add_expert(
                                orcid=orcid,
                                first_name=first_name,
                                last_name=last_name,
                                domains=domains,
                                fields=fields,
                                subfields=subfields,
                                expertise=existing_expertise
                            )
                            logger.info(f"Successfully processed expert: {first_name} {last_name}")
                        else:
                            logger.warning(f"No ORCID found for {first_name} {last_name}")
                    else:
                        logger.warning(f"No OpenAlex ID found for {first_name} {last_name}")

        except Exception as e:
            logger.error(f"Error processing experts: {e}")
            raised

    def close(self):
        self.db.close()

async def main():
    processor = OpenAlexProcessor()
    try:
        # Process works
        processor.process_works(max_publications=4)
        
        # Process expertise data first
        await processor.process_expertise_csv("expertise.csv")
        
        # Then process OpenAlex data
        await processor.process_experts("sme.csv")
    except Exception as e:
        logger.error(f"Error in main process: {e}")
    finally:
        processor.close()

if __name__ == "__main__":
    asyncio.run(main())
