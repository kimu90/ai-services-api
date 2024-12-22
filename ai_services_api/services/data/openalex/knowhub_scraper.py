import os
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
import re
import hashlib
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class KnowhubScraper:
    def __init__(self):
        """Initialize KnowhubScraper with DSpace repository configuration."""
        # Base URL configuration
        self.base_url = os.getenv('KNOWHUB_BASE_URL', "https://knowhub.aphrc.org")
        self.handle_url = os.getenv(
            'KNOWHUB_HANDLE_URL', 
            f"{self.base_url}/handle/123456789/1602"
        )
        
        # Authentication configuration
        self.username = os.getenv('KNOWHUB_USERNAME')
        self.password = os.getenv('KNOWHUB_PASSWORD')
        
        # Session for persistent authentication
        self.session = requests.Session()
        
        # Tracking to prevent duplicates
        self.seen_handles = set()
        self.seen_dois = set()
        self.seen_titles = set()
        
        # DSpace metadata field mappings
        self.metadata_mappings = {
            'title': ['dc.title'],
            'authors': ['dc.contributor.author', 'dc.creator'],
            'date': ['dc.date.issued', 'dc.date.available'],
            'abstract': ['dc.description.abstract', 'dc.description'],
            'keywords': ['dc.subject', 'dc.subject.keywords'],
            'doi': ['dc.identifier.doi'],
            'type': ['dc.type'],
            'journal': ['dc.source', 'dc.publisher.journal'],
            'citation': ['dc.identifier.citation'],
            'language': ['dc.language.iso'],
            'publisher': ['dc.publisher']
        }

    def _authenticate(self) -> bool:
        """
        Handle DSpace repository authentication.
        
        Returns:
            bool: Authentication success status
        """
        if not self.username or not self.password:
            logger.warning("Knowhub credentials not configured")
            return False
        
        login_url = f"{self.base_url}/password-login"
        
        try:
            # Prepare login data
            login_data = {
                'login_email': self.username,
                'login_password': self.password,
                'submit': 'Sign in'
            }
            
            # Attempt login
            response = self.session.post(login_url, data=login_data)
            
            # Check authentication success
            if response.status_code == 200 and 'Welcome' in response.text:
                logger.info("Successfully authenticated with Knowhub")
                return True
            
            logger.warning("Authentication failed")
            return False
        
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False

    def _generate_synthetic_doi(self, publication_data: Dict) -> str:
        """
        Generate a synthetic DOI for publications without a native DOI.
        
        Args:
            publication_data (Dict): Publication metadata
        
        Returns:
            str: Synthetic DOI
        """
        try:
            # Create a unique hash based on multiple attributes
            unique_string = f"{publication_data.get('title', '')}|" \
                            f"{';'.join(publication_data.get('authors', []))}"
            
            # Use SHA-256 to create a consistent hash
            hash_object = hashlib.sha256(unique_string.encode())
            hash_digest = hash_object.hexdigest()[:16]
            
            # Create a synthetic DOI with a unique prefix
            synthetic_doi = f"10.0000/knowhub-{hash_digest}"
            
            return synthetic_doi
        except Exception as e:
            logger.error(f"Error generating synthetic DOI: {e}")
            return f"10.0000/random-{hashlib.md5(unique_string.encode()).hexdigest()[:16]}"

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse date string into datetime object with multiple format support.
        
        Args:
            date_str (str): Date string to parse
        
        Returns:
            Optional[datetime]: Parsed datetime or None
        """
        if not date_str:
            return None
        
        # Date parsing formats
        date_formats = [
            '%Y-%m-%d',  # 2023-01-15
            '%d %B %Y',  # 15 January 2023
            '%B %d, %Y',  # January 15, 2023
            '%Y/%m/%d',  # 2023/01/15
            '%Y-%m',     # 2023-01
            '%Y'         # 2023
        ]
        
        date_str = date_str.strip()
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # Extract year if no full date match
        year_match = re.search(r'\d{4}', date_str)
        if year_match:
            return datetime(int(year_match.group(0)), 1, 1)
        
        return None

    def _extract_metadata(self, soup: BeautifulSoup) -> Dict:
        """
        Extract metadata using DSpace-specific metadata fields.
        
        Args:
            soup (BeautifulSoup): Parsed HTML soup
        
        Returns:
            Dict: Extracted metadata
        """
        metadata = {}
        
        # Find metadata tables
        metadata_tables = soup.select('table.detailtable, div.ds-table-responsive table')
        
        for table in metadata_tables:
            rows = table.select('tr')
            
            for row in rows:
                try:
                    label_elem = row.select_one('td.label-cell, td.label, th.label-cell')
                    value_elem = row.select_one('td.word-break, td:not(.label-cell)')
                    
                    if not label_elem or not value_elem:
                        continue
                    
                    label_text = label_elem.text.strip().lower()
                    value_text = value_elem.text.strip()
                    
                    # Check against metadata mappings
                    for key, mapping_fields in self.metadata_mappings.items():
                        for field in mapping_fields:
                            if field.lower() in label_text:
                                if key in ['authors', 'keywords']:
                                    # Split multiple values
                                    values = [v.strip() for v in value_text.split(';') if v.strip()]
                                    metadata[key] = list(dict.fromkeys(metadata.get(key, []) + values))
                                else:
                                    metadata[key] = value_text
                
                except Exception as e:
                    logger.error(f"Error processing metadata row: {e}")
        
        # Attempt to extract DOI from text if not found
        if not metadata.get('doi'):
            doi_match = re.search(r'10.\d{4,9}/[-._;()/:\w]+', metadata.get('abstract', ''))
            if doi_match:
                metadata['doi'] = doi_match.group(0)
        
        return metadata

    def _parse_publication(self, publication_element) -> Optional[Dict]:
        """
        Parse a publication item into a standardized dictionary.
        
        Args:
            publication_element: Publication HTML element
        
        Returns:
            Optional[Dict]: Parsed publication metadata
        """
        try:
            # Find publication URL and title
            title_elem = publication_element.select_one('a')
            if not title_elem:
                return None
            
            title = title_elem.text.strip()
            
            # Skip if title already seen
            if title in self.seen_titles:
                return None
            
            # Get publication URL
            url = title_elem.get('href', '')
            if not url.startswith('http'):
                url = self.base_url + url
            
            # Extract handle
            handle = url.split('handle/')[-1] if 'handle' in url else ''
            
            # Skip if handle already seen
            if handle in self.seen_handles:
                return None
            
            # Fetch detailed page
            try:
                response = self.session.get(url)
                response.raise_for_status()
                detail_soup = BeautifulSoup(response.text, 'html.parser')
            except Exception as e:
                logger.error(f"Error fetching detail page {url}: {e}")
                return None
            
            # Extract metadata
            metadata = self._extract_metadata(detail_soup)
            
            # Generate DOI if not present
            doi = metadata.get('doi', '')
            if not doi:
                doi = self._generate_synthetic_doi(metadata)
            
            # Prepare publication dictionary
            publication = {
                'title': title,
                'authors': metadata.get('authors', []),
                'date': self._parse_date(metadata.get('date', '')),
                'abstract': metadata.get('abstract', ''),
                'keywords': metadata.get('keywords', []),
                'url': url,
                'doi': doi,
                'handle': handle,
                'journal': metadata.get('journal', ''),
                'document_type': metadata.get('type', ''),
                'source': 'knowhub'
            }
            
            # Mark as seen to prevent duplicates
            self.seen_handles.add(handle)
            self.seen_titles.add(title)
            self.seen_dois.add(doi)
            
            return publication
            
        except Exception as e:
            logger.error(f"Error parsing publication: {e}")
            return None

    def fetch_publications(self, limit: int = 10) -> List[Dict]:
        """
        Fetch publications from Knowhub repository.
        
        Args:
            limit (int, optional): Maximum number of publications to fetch
        
        Returns:
            List[Dict]: List of publication dictionaries
        """
        # Authenticate first
        if not self._authenticate():
            logger.error("Authentication failed. Cannot fetch publications.")
            return []
        
        publications = []
        
        try:
            # Fetch repository page
            response = self.session.get(self.handle_url)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find publication elements
            publication_elements = soup.select('div.artifact-title')
            
            # Process publications
            for element in publication_elements[:limit]:
                pub = self._parse_publication(element)
                
                if pub:
                    publications.append(pub)
                    
                    if len(publications) >= limit:
                        break
        
        except Exception as e:
            logger.error(f"Error fetching publications: {e}")
        
        return publications

    def close(self):
        """
        Close session and cleanup resources.
        """
        self.session.close()
