import os
import requests
import csv
from dotenv import load_dotenv
import google.generativeai as genai
from typing import Optional, Dict, List, Any
import time
from datetime import datetime

# Load environment variables
load_dotenv()

class RateLimiter:
    def __init__(self, requests_per_minute):
        self.requests_per_minute = requests_per_minute
        self.requests = []
        
    def wait_if_needed(self):
        """Wait if we've exceeded our rate limit."""
        now = time.time()
        
        # Remove requests older than 1 minute
        self.requests = [req_time for req_time in self.requests if now - req_time < 60]
        
        if len(self.requests) >= self.requests_per_minute:
            # Wait until we can make another request
            sleep_time = 60 - (now - self.requests[0])
            if sleep_time > 0:
                print(f"Rate limit reached. Waiting {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
        
        self.requests.append(now)

# Create a global rate limiter (50 requests per minute to be safe)
rate_limiter = RateLimiter(50)

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
        
        # Wait if needed before making API request
        rate_limiter.wait_if_needed()
            
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
        print(f"Error in summarization: {e}")
        if "429" in str(e):
            print("API quota exceeded. Waiting 60 seconds before retry...")
            time.sleep(60)  # Wait a minute before retrying
            try:
                # Try one more time
                rate_limiter.wait_if_needed()
                model = setup_gemini()
                response = model.generate_content(prompt)
                return response.text.strip()
            except Exception as retry_e:
                print(f"Retry failed: {retry_e}")
        return "Failed to generate summary"

class OpenAlexProcessor:
    def __init__(self):
        """Initialize the OpenAlex processor."""
        self.base_url = os.getenv('OPENALEX_API_URL', 'https://api.openalex.org')
        self.institution_id = 'I4210129448'  # APHRC institution ID
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.csv_filename = f"aphrc_publications_{timestamp}.csv"
        
    def process_works(self):
        """Process all works and save to CSV."""
        url = f"{self.base_url}/works?filter=institutions.id:{self.institution_id}&per_page=200"
        processed_count = 0
        
        with open(self.csv_filename, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                'DOI', 'Title', 'Authors', 'Abstract', 'Summary',
                'Author IDs', 'Author Names', 'ORCIDs'
            ])
            
            while url:
                try:
                    print(f"Fetching data from: {url}")
                    response = requests.get(url, headers={'User-Agent': 'YourApp/1.0'})
                    response.raise_for_status()
                    data = response.json()
                    
                    if 'results' not in data:
                        print("No results found in response")
                        break
                    
                    for work in data['results']:
                        try:
                            doi = safe_str(work.get('doi'))
                            title = safe_str(work.get('title'))
                            
                            print(f"\nProcessing work {processed_count + 1}")
                            print(f"Title: {title}")
                            
                            # Convert abstract inverted index to text
                            abstract_index = work.get('abstract_inverted_index')
                            abstract = convert_inverted_index_to_text(abstract_index)
                            
                            # Process authors with None handling
                            author_names = []
                            author_ids = []
                            orcids = []
                            
                            for authorship in work.get('authorships', []):
                                author = authorship.get('author', {})
                                if author:
                                    author_names.append(safe_str(author.get('display_name')))
                                    author_ids.append(safe_str(author.get('id')))
                                    orcids.append(safe_str(author.get('orcid')))
                            
                            # Filter out any "N/A" values before joining
                            author_names = [name for name in author_names if name != "N/A"]
                            author_ids = [aid for aid in author_ids if aid != "N/A"]
                            orcids = [orcid for orcid in orcids if orcid != "N/A"]
                            
                            # Prepare row data with fallbacks for empty lists
                            author_names_str = ', '.join(author_names) if author_names else "N/A"
                            author_ids_str = ', '.join(author_ids) if author_ids else "N/A"
                            orcids_str = ', '.join(orcids) if orcids else "N/A"
                            
                            # Generate summary
                            print("Generating summary...")
                            summary = summarize(title, abstract)
                            print("Summary generated successfully" if summary else "Failed to generate summary")
                            
                            # Write to CSV
                            writer.writerow([
                                doi,
                                title,
                                author_names_str,
                                abstract,
                                summary or "Failed to generate summary",
                                author_ids_str,
                                author_names_str,
                                orcids_str
                            ])
                            
                            processed_count += 1
                            print(f"Successfully processed work: {title}")
                            
                        except Exception as e:
                            print(f"Error processing work: {e}")
                            continue
                    
                    # Get next page URL
                    url = data.get('meta', {}).get('next_page')
                    if url:
                        print(f"\nMoving to next page... (Processed {processed_count} works so far)")
                    
                except requests.exceptions.RequestException as e:
                    print(f"Error fetching data: {e}")
                    break
                except Exception as e:
                    print(f"Unexpected error: {e}")
                    break
        
        print(f"\nProcessing complete. {processed_count} works processed.")
        print(f"Data saved to {self.csv_filename}")