import os
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
from time import sleep
from datetime import datetime
import re
import hashlib
import json

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
        
        # Publication type mapping
        self.type_mapping = {
            'Annual Reports': 'report',
            'Briefing Papers': 'briefing',
            'comic': 'other',
            'Factsheet': 'factsheet',
            'Financial Report': 'report',
            'General': 'other',
            'Journal Articles': 'journal_article',
            'Multimedia': 'multimedia',
            'Newsletters': 'newsletter',
            'Policy brief': 'policy_brief',
            'Poster': 'poster',
            'Short Report': 'report',
            'Strategic Plan': 'plan',
            'Technical Reports': 'technical_report',
            'Working Paper': 'working_paper'
        }
        
        # Initialize summarizer
        self.summarizer = summarizer or TextSummarizer()
        
        # Tracking to prevent duplicates
        self.seen_titles = set()
        
        # Logging setup
        self.logger = logging.getLogger(__name__)

    def _generate_synthetic_doi(self, title: str, url: str) -> str:
        """Generate a synthetic DOI for website publications."""
        try:
            unique_string = f"{title}|{url}"
            hash_object = hashlib.sha256(unique_string.encode())
            hash_digest = hash_object.hexdigest()[:16]
            return f"10.0000/aphrc-{hash_digest}"
        except Exception as e:
            self.logger.error(f"Error generating synthetic DOI: {e}")
            return f"10.0000/random-{hashlib.md5(unique_string.encode()).hexdigest()[:16]}"

    def _extract_year_and_type(self, element: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
        """Extract publication year and type from element."""
        try:
            year = None
            pub_type = None
            
            # Extract year
            year_elem = element.select_one('.year, [class*="year"]')
            if year_elem:
                year_match = re.search(r'\d{4}', year_elem.text)
                if year_match:
                    year = year_match.group(0)
            
            # Extract type
            type_elem = element.select_one('.type, .category, [class*="type"]')
            if type_elem:
                pub_type = type_elem.text.strip()
                pub_type = self.type_mapping.get(pub_type, 'other')
            
            return year, pub_type
        except Exception as e:
            self.logger.error(f"Error extracting year and type: {e}")
            return None, None

    def fetch_content(self, limit: int = 10) -> List[Dict]:
        """Fetch content from specified URLs with publication-style formatting."""
        all_publications = []
        
        for section, url in self.urls.items():
            self.logger.info(f"Fetching {section} from {url}")
            try:
                response = self._make_request(url)
                if response.status_code != 200:
                    self.logger.error(f"Failed to access {section}: {response.status_code}")
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Handle different page structures
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
        """Handle infinite scroll or load more pagination."""
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
                sleep(1)  # Rate limiting
                
            except Exception as e:
                self.logger.error(f"Error loading more items: {str(e)}")
                break
                
        return publications

    def _fetch_with_pagination(self, url: str, section: str, limit: int) -> List[Dict]:
        """Handle traditional numbered pagination."""
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
                sleep(1)  # Rate limiting
                
            except Exception as e:
                self.logger.error(f"Error processing page {page}: {str(e)}")
                break
                
        return publications

    def _extract_publications(self, soup: BeautifulSoup, section: str) -> List[Dict]:
        """Extract publications from page."""
        publications = []
        
        # Updated selectors for APHRC website structure
        selectors = {
            'publications': ['article', '.publication-item', '.elementor-post'],
            'documents': ['article', '.document-item', '.elementor-post'],
            'ideas': ['article', '.post-item', '.elementor-post']
        }
        
        # Find elements using section-specific selectors
        elements = []
        for selector in selectors.get(section, []):
            elements.extend(soup.select(selector))
        
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
        """Parse a single publication item to match resources_resource table structure."""
        try:
            # Extract basic information
            title_elem = element.select_one('h1, h2, h3, h4, a')
            if not title_elem:
                return None
                
            title = safe_str(title_elem.text.strip())
            
            # Extract URL and generate DOI
            if title_elem.name == 'a':
                url = title_elem.get('href', '')
            else:
                link = element.find('a')
                url = link.get('href', '') if link else ''

            if not url.startswith('http'):
                url = self.base_url + url
            
            doi = self._generate_synthetic_doi(title, url)
            
            # Extract publication year and type
            year, pub_type = self._extract_year_and_type(element)
            
            # Extract date
            date_elem = element.select_one('.date, .elementor-post-date, time')
            date = None
            if date_elem:
                date_str = date_elem.get('datetime', '') or date_elem.text.strip()
                date = self._parse_date(date_str)
            elif year:
                date = datetime(int(year), 1, 1)
            
            # Extract description/abstract
            excerpt_elem = element.select_one('.excerpt, .description, p')
            excerpt = safe_str(excerpt_elem.text.strip()) if excerpt_elem else ''
            
            # Generate summary
            summary = self._generate_summary(title, excerpt)
            
            # Extract authors
            author_elem = element.select_one('.author, meta[name="author"], .elementor-post-author')
            authors = []
            if author_elem:
                author_names = author_elem.get('content', '') or author_elem.text.strip()
                if author_names:
                    authors = [name.strip() for name in author_names.split(',') if name.strip()]
            
            # Extract subtitle
            subtitle_elem = element.select_one('.subtitle, .elementor-post-subtitle')
            subtitles = {}
            if subtitle_elem:
                subtitles = {'main': subtitle_elem.text.strip()}
            
            # Extract keywords/tags
            keywords = []
            tag_elems = element.select('.tags a, .keywords a, .elementor-post-tags a')
            for tag in tag_elems:
                tag_text = tag.text.strip()
                if tag_text:
                    keywords.append(tag_text)
            
            # Construct complete publication record
            publication = {
                'doi': doi,
                'title': title,
                'abstract': excerpt,
                'summary': summary,
                'authors': authors,
                'description': excerpt,
                'expert_id': None,
                'type': pub_type or 'other',
                'subtitles': json.dumps(subtitles),
                'publishers': json.dumps({
                    'name': 'APHRC',
                    'url': self.base_url,
                    'type': section
                }),
                'collection': section,
                'date_issue': date.strftime('%Y-%m-%d') if date else None,
                'citation': None,
                'language': 'en',
                'identifiers': json.dumps({
                    'doi': doi,
                    'url': url,
                    'source_id': f"aphrc-{section}-{hashlib.md5(url.encode()).hexdigest()[:8]}",
                    'keywords': keywords
                }),
                'source': 'website'
            }
            
            return publication
            
        except Exception as e:
            self.logger.error(f"Error parsing publication: {str(e)}")
            return None

    def _generate_summary(self, title: str, abstract: str) -> str:
        """Generate a summary using the TextSummarizer."""
        try:
            title = truncate_text(title, max_length=200)
            abstract = truncate_text(abstract, max_length=1000)
            summary = self.summarizer.summarize(title, abstract)
            return truncate_text(summary, max_length=500)
        except Exception as e:
            self.logger.error(f"Summary generation error: {e}")
            return abstract[:500]  # Fallback to truncated abstract

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string into datetime object."""
        if not date_str:
            return None
            
        try:
            # Updated date formats for APHRC website
            formats = [
                '%Y-%m-%d',
                '%d/%m/%Y',
                '%B %d, %Y',
                '%d %B %Y',
                '%d.%m.%Y',
                '%Y/%m/%d'
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue
                    
            # Try to extract year if full date parsing fails
            year_match = re.search(r'\d{4}', date_str)
            if year_match:
                return datetime(int(year_match.group(0)), 1, 1)
                
            return None
            
        except Exception:
            return None

    def _has_load_more_button(self, soup: BeautifulSoup) -> bool:
        """Check if page has a load more button or infinite scroll."""
        load_more_selectors = [
            '.load-more',
            '.elementor-button-link',
            'button[data-page]',
            '.elementor-pagination',
            '.pagination'
        ]
        return any(bool(soup.select(selector)) for selector in load_more_selectors)

    def _make_request(self, url: str, method: str = 'get', **kwargs) -> requests.Response:
        """Make an HTTP request with error handling."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }
            
            headers.update(kwargs.get('headers', {}))
            kwargs['headers'] = headers
            
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response
            
        except requests.RequestException as e:
            self.logger.error(f"Request error for {url}: {e}")
            raise

    def close(self):
        """Close resources and perform cleanup."""
        try:
            if hasattr(self.summarizer, 'close'):
                self.summarizer.close()
            
            self.seen_titles.clear()
            
            self.logger.info("WebsiteScraper resources cleaned up")
        except Exception as e:
            self.logger.error(f"Error closing WebsiteScraper: {e}")
