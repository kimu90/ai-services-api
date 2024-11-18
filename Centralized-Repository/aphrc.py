import os
import requests
import csv
from dotenv import load_dotenv
import google.generativeai as genai
from typing import Optional, Dict, List, Any

# Load environment variables
load_dotenv()

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
        print(f"Error in summarization: {e}")
        return "Failed to generate summary"

def convert_inverted_index_to_text(inverted_index: Dict) -> str:
    """Convert an inverted index to readable text."""
    if not inverted_index:
        return "N/A"
    
    try:
        # Create a list of tuples (position, word)
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        
        # Sort by position and join words
        return ' '.join(word for _, word in sorted(word_positions))
    except Exception as e:
        print(f"Error converting inverted index: {e}")
        return "N/A"

def safe_str(value: Any) -> str:
    """Convert a value to string, handling None values."""
    if value is None:
        return "N/A"
    return str(value)

class OpenAlexProcessor:
    def __init__(self):
        """Initialize the OpenAlex processor."""
        self.base_url = os.getenv('OPENALEX_API_URL', 'https://api.openalex.org')
        self.institution_id = 'I4210129448'  # APHRC institution ID
        self.csv_filename = "aphrc_publications.csv"
    
    def process_works(self):
        """Process all works and save to CSV."""
        url = f"{self.base_url}/works?filter=institutions.id:{self.institution_id}&per_page=200"
        
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
                            print(f"Generating summary for: {title}")
                            summary = summarize(title, abstract)
                            
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
                            
                            print(f"Processed work: {title}")
                            
                        except Exception as e:
                            print(f"Error processing work: {e}")
                            continue
                    
                    # Get next page URL
                    url = data.get('meta', {}).get('next_page')
                    if url:
                        print("Moving to next page...")
                    
                except requests.exceptions.RequestException as e:
                    print(f"Error fetching data: {e}")
                    break
                except Exception as e:
                    print(f"Unexpected error: {e}")
                    break
        
        print(f"\nProcessing complete. Data saved to {self.csv_filename}")

def main():
    """Main execution function."""
    try:
        print("Starting OpenAlex data processing...")
        processor = OpenAlexProcessor()
        processor.process_works()
    except Exception as e:
        print(f"Fatal error: {e}")

if __name__ == "__main__":
    main()