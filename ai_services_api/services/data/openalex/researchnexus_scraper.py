import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException

class ResearchNexusScraper:
    """
    Scraper for Research Nexus publication data using Selenium with Chromium.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.institution_id = '9000041605'
        self.driver = None
        
    def setup_driver(self):
        """
        Sets up the Chromium driver with proper options for Docker environment.
        """
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-infobars')
        
        # Additional options for running in Docker
        chrome_options.add_argument('--remote-debugging-port=9222')
        chrome_options.add_argument('--disable-setuid-sandbox')
        
        service = Service('/usr/bin/chromedriver')  # Path in Docker
        
        try:
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except WebDriverException as e:
            self.logger.error(f"Failed to initialize Chrome driver: {str(e)}")
            raise
    
    def fetch_content(self, limit=10):
        """
        Fetches publications from Research Nexus using Selenium.
        """
        publications = []
        
        try:
            if not self.driver:
                self.setup_driver()
            
            url = (
                f"https://research-nexus.net/research/"
                f"?stp=broad&yrl=1999&yrh=2024"
                f"&ins={self.institution_id}"
                f"&limit={limit}&sort=score_desc"
            )
            
            self.logger.info(f"Fetching page: {url}")
            self.driver.get(url)
            
            # Wait for papers to load
            wait = WebDriverWait(self.driver, 20)  # Increased timeout
            try:
                papers = wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".research-paper, .paper-item"))
                )
                
                self.logger.info(f"Found {len(papers)} papers")
                
                # Extract data from each paper
                for paper in papers[:limit]:
                    try:
                        pub = self._extract_paper_data(paper)
                        if pub:
                            publications.append(pub)
                    except Exception as e:
                        self.logger.error(f"Error processing paper: {str(e)}")
                        continue
                        
            except TimeoutException:
                self.logger.error("Timeout waiting for papers to load")
                return []
            
            return publications
            
        except Exception as e:
            self.logger.error(f"Error fetching publications: {str(e)}")
            return []
            
        finally:
            self.close()
    
    def _extract_paper_data(self, paper_element):
        """
        Extracts data from a paper element.
        """
        try:
            # Extract basic information using various possible selectors
            title = self._get_text(paper_element, [
                ".paper-title", 
                ".title", 
                "h3", 
                ".paper-heading"
            ])
            
            abstract = self._get_text(paper_element, [
                ".paper-abstract",
                ".abstract",
                ".description"
            ])
            
            # Extract authors
            authors = self._get_authors(paper_element)
            
            # Try to get DOI
            doi = self._get_attribute(paper_element, [
                ".paper-doi",
                ".doi a",
                "[data-doi]"
            ], "href") or self._get_attribute(paper_element, [
                ".paper-doi",
                ".doi",
                "[data-doi]"
            ], "data-doi")
            
            # Try to get URL
            url = self._get_attribute(paper_element, [
                ".paper-link",
                ".title a",
                "h3 a"
            ], "href")
            
            # Create publication object
            pub = {
                'title': title,
                'abstract': abstract or '',
                'authors': authors,
                'url': url,
                'doi': doi,
                'source': 'researchnexus',
                'source_id': paper_element.get_attribute("data-id") or '',
                'date': None,
                'year': None,
                'journal': None,
                'citation_count': 0,
                'type': 'paper',
                'keywords': []
            }
            
            # Try to extract date/year
            date_text = self._get_text(paper_element, [
                ".paper-date",
                ".date",
                ".published-date"
            ])
            
            if date_text:
                pub['date'] = date_text
                try:
                    # Try different date formats
                    for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%B %Y', '%Y']:
                        try:
                            date_obj = datetime.strptime(date_text, fmt)
                            pub['year'] = date_obj.year
                            break
                        except ValueError:
                            continue
                except:
                    pass
            
            # Try to extract journal
            pub['journal'] = self._get_text(paper_element, [
                ".paper-journal",
                ".journal",
                ".publication-venue"
            ])
            
            return pub
            
        except Exception as e:
            self.logger.error(f"Error extracting paper data: {str(e)}")
            return None
    
    def _get_text(self, element, selectors):
        """
        Tries multiple selectors to get text content.
        """
        for selector in selectors:
            try:
                found = element.find_element(By.CSS_SELECTOR, selector)
                if found:
                    return found.text.strip()
            except:
                continue
        return ''
    
    def _get_attribute(self, element, selectors, attribute):
        """
        Tries multiple selectors to get an attribute.
        """
        for selector in selectors:
            try:
                found = element.find_element(By.CSS_SELECTOR, selector)
                if found:
                    return found.get_attribute(attribute)
            except:
                continue
        return None
    
    def _get_authors(self, element):
        """
        Extracts author information trying multiple selectors.
        """
        authors = []
        
        # Try different selectors for author elements
        selectors = [
            ".paper-authors a",
            ".authors a",
            ".author-list a",
            ".paper-authors .author",
            ".authors .author"
        ]
        
        for selector in selectors:
            try:
                author_elements = element.find_elements(By.CSS_SELECTOR, selector)
                if author_elements:
                    for author_el in author_elements:
                        authors.append({
                            'name': author_el.text.strip(),
                            'affiliations': [],
                            'orcid': None
                        })
                    break
            except:
                continue
        
        # If no authors found, try getting text content
        if not authors:
            author_text = self._get_text(element, [
                ".paper-authors",
                ".authors",
                ".author-list"
            ])
            if author_text:
                author_names = [name.strip() for name in author_text.split(',')]
                authors = [{'name': name, 'affiliations': [], 'orcid': None} 
                          for name in author_names if name]
        
        return authors
    
    def close(self):
        """
        Closes the browser.
        """
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
            except:
                pass
