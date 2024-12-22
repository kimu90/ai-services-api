import os
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from time import sleep
from datetime import datetime
import re
import hashlib

from ai_services_api.services.data.openalex.ai_summarizer import TextSummarizer
from ai_services_api.services.data.openalex.text_processor import safe_str, truncate_text

class WebsiteScraper:
    def __init__(self, summarizer: Optional[TextSummarizer] = None):
        """
        Initialize WebsiteScraper with summarization capability.
        
        Args:
            summarizer (Optional[TextSummarizer]): Summarization service
        """
        self.base_url = "https://aphrc.org"
        self.urls = {
            'publications': f"{self.base_url}/publications/",
            'documents': f"{self.base_url}/documents_reports/",
            'ideas': f"{self.base_url}/ideas/"
        }
        
        # Initialize summarizer
        self.summarizer = summarizer or TextSummarizer()
        
        # Tracking to prevent duplicates
        self.seen_titles = set()
        
        # Logging setup
        self.logger = logging.getLogger(__name__)

    def _generate_synthetic_doi(self, title: str, url: str) -> str:
        """
        Generate a synthetic DOI for website publications.
        
        Args:
            title (str): Publication title
            url (str): Publication URL
        
        Returns:
            str: Synthetic DOI
        """
        try:
            # Create a unique hash based on title and URL
            unique_string = f"{title}|{url}"
            
            # Use SHA-256 to create a consistent hash
            hash_object = hashlib.sha256(unique_string.encode())
            hash_digest = hash_object.hexdigest()[:16]
            
            # Create a synthetic DOI with a unique prefix
            synthetic_doi = f"10.0000/aphrc-{hash_digest}"
            
            return synthetic_doi
        except Exception as e:
            self.logger.error(f"Error generating synthetic DOI: {e}")
            return f"10.0000/random-{hashlib.md5(unique_string.encode()).hexdigest()[:16]}"

    def fetch_content(self, limit: int = 10) -> List[Dict]:
        """
        Fetch content from specified URLs with publication-style formatting.
        
        Args:
            limit (int): Maximum number of publications to fetch
        
        Returns:
            List[Dict]: List of publication dictionaries
        """
        all_publications = []
        
        for section, url in self.urls.items():
            self.logger.info(f"Fetching {section} from {url}")
            try:
                response = self._make_request(url)
                if response.status_code != 200:
                    self.logger.error(f"Failed to access {section}: {response.status_code}")
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Determine fetch method based on page structure
                if self._has_load_more_button(soup):
                    publications = self._fetch_with_load_more(url, section, limit)
                else:
                    publications = self._fetch_with_pagination(url, section, limit)
                
                all_publications.extend(publications)
                
                if limit and len(all_publications) >= limit:
                    all_publications = all_publications[:limit]
                    break
                    
            except Exception as e:
                self.logger.error(f"Error fetching {section}: {str(e)}")
                continue
                
        return all_publications

    def _fetch_with_load_more(self, url: str, section: str, limit: int) -> List[Dict]:
        """
        Handle infinite scroll or load more pagination.
        
        Args:
            url (str): Base URL
            section (str): Content section
            limit (int): Maximum publications to fetch
        
        Returns:
            List[Dict]: List of publication dictionaries
        """
        publications = []
        page = 1
        
        while True:
            try:
                next_page_url = f"{url}page/{page}/"
                response = self._make_request(next_page_url)
                if response.status_code != 200:
                    break
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                new_publications = self._extract_publications(soup, section)
                
                if not new_publications:
                    break
                    
                publications.extend(new_publications)
                
                if limit and len(publications) >= limit:
                    publications = publications[:limit]
                    break
                    
                page += 1
                sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error loading more items: {str(e)}")
                break
                
        return publications

    def _fetch_with_pagination(self, url: str, section: str, limit: int) -> List[Dict]:
        """
        Handle traditional numbered pagination.
        
        Args:
            url (str): Base URL
            section (str): Content section
            limit (int): Maximum publications to fetch
        
        Returns:
            List[Dict]: List of publication dictionaries
        """
        publications = []
        page = 1
        
        while True:
            try:
                page_url = f"{url}page/{page}/" if page > 1 else url
                response = self._make_request(page_url)
                
                if response.status_code != 200:
                    break
                    
                soup = BeautifulSoup(response.text, 'html.parser')
                new_publications = self._extract_publications(soup, section)
                
                if not new_publications:
                    break
                    
                publications.extend(new_publications)
                
                if limit and len(publications) >= limit:
                    publications = publications[:limit]
                    break
                    
                page += 1
                sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error processing page {page}: {str(e)}")
                break
                
        return publications

    def _extract_publications(self, soup: BeautifulSoup, section: str) -> List[Dict]:
        """
        Extract publications from page.
        
        Args:
            soup (BeautifulSoup): Parsed HTML
            section (str): Content section
        
        Returns:
            List[Dict]: List of publication dictionaries
        """
        publications = []
        
        # Selectors for different content types
        selectors = {
            'publications': ['.elementor-post', '.publication-item', 'article'],
            'documents': ['.document-item', '.report-item', 'article'],
            'ideas': ['.post', '.idea-item', 'article']
        }
        
        # Find elements
        for selector in selectors.get(section, []):
            elements = soup.select(selector)
            if elements:
                break
        
        for element in elements:
            try:
                publication = self._parse_publication(element, section)
                if publication and publication['title'] not in self.seen_titles:
                    self.seen_titles.add(publication['title'])
                    publications.append(publication)
            except Exception as e:
                self.logger.error(f"Error parsing item: {str(e)}")
                continue
                
        return publications

    def _parse_publication(self, element: BeautifulSoup, section: str) -> Optional[Dict]:
        """
        Parse a single publication item.
        
        Args:
            element (BeautifulSoup): HTML element
            section (str): Content section
        
        Returns:
            Optional[Dict]: Publication dictionary
        """
        try:
            # Extract title
            title_elem = element.select_one('h1, h2, h3, h4, a')
            if not title_elem:
                return None
                
            title = safe_str(title_elem.text.strip())
            
            # Extract URL
            if title_elem.name == 'a':
                url = title_elem.get('href', '')
            else:
                link = element.find('a')
                url = link.get('href', '') if link else ''

            if not url.startswith('http'):
                url = self.base_url + url
            
            # Extract date
            date_elem = element.select_one('.date, .elementor-post-date, time')
            date = None
            if date_elem:
                date_str = date_elem.get('datetime', '') or date_elem.text.strip()
                date = self._parse_date(date_str)
            
            # Extract excerpt/description
            excerpt_elem = element.select_one('.excerpt, .description, p')
            excerpt = safe_str(excerpt_elem.text.strip()) if excerpt_elem else ''
            
            # Generate synthetic DOI
            doi = self._generate_synthetic_doi(title, url)
            
            # Generate summary
            summary = self._generate_summary(title, excerpt)
            
            return {
                'title': title,
                'authors': [],  # No authors typically available
                'date_issue': date.strftime('%Y-%m-%d') if date else None,
                'abstract': excerpt,
                'summary': summary,
                'doi': doi,
                'url': url,
                'keywords': [],
                'source': 'website',  # Explicitly set source to 'website'
                'type': 'journal_article'  # Set type as journal_article
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing publication: {str(e)}")
            return None

    def _generate_summary(self, title: str, abstract: str) -> str:
        """
        Generate a summary using the TextSummarizer.
        
        Args:
            title (str): Publication title
            abstract (str): Publication excerpt/description
        
        Returns:
            str: Generated summary
        """
        try:
            # Truncate text to prevent overloading summarizer
            title = truncate_text(title, max_length=200)
            abstract = truncate_text(abstract, max_length=1000)
            
            # Generate summary
            summary = self.summarizer.summarize(title, abstract)
            
            return truncate_text(summary, max_length=500)
        
        except Exception as e:
            self.logger.error(f"Summary generation error: {e}")
            return excerpt[:500]  # Fallback to truncated excerpt

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse date string into datetime object.
        
        Args:
            date_str (str): Date string to parse
        
        Returns:
            Optional[datetime]: Parsed date or None
        """
        if not date_str:
            return None
            
        try:
            formats = [
                '%Y-%m-%d',
                '%B %d, %Y',
                '%d %B %Y',
                '%Y/%m/%d',
                '%d/%m/%Y'
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue
                    
            year_match = re.search(r'\d{4}', date_str)
            if year_match:
                return datetime(int(year_match.group(0)), 1, 1)
                
            return None
            
        except Exception:
            return None

    def _has_load_more_button(self, soup: BeautifulSoup) -> bool:
        """Check if page has a load more button or infinite scroll"""
        load_more_selectors = [
            '.load-more',
            '.elementor-button-link',
            'button[data-page]',
            '.elementor-pagination'
        ]
        return any(bool(soup.select(selector)) for selector in load_more_selectors)

    def _make_request(self, url: str, method: str = 'get', **kwargs):
        """
        Make an HTTP request with error handling.
        
        Args:
            url (str): Target URL
            method (str): HTTP method
            **kwargs: Additional request parameters
        
        Returns:
            requests.Response: Response object
        """
        try:
            # Default headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }
            
            # Merge default headers with any user-provided headers
            headers.update(kwargs.get('headers', {}))
            kwargs['headers'] = headers
            
            # Perform request
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        
        except requests.RequestException as e:
            self.logger.error(f"Request error for {url}: {e}")
            raise

    def close(self):
        """
        Close resources and perform cleanup.
        """
        try:
            # Close summarizer if it has a close method
            if hasattr(self.summarizer, 'close'):
                self.summarizer.close()
            
            # Clear seen titles to free memory
            self.seen_titles.clear()
            
            self.logger.info("WebsiteScraper resources cleaned up")
        except Exception as e:
            self.logger.error(f"Error closing WebsiteScraper: {e}")
