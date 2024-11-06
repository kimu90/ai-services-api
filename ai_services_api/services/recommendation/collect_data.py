import requests
import pandas as pd
import os
import time

# Base URL for OpenAlex API
BASE_AUTHORS_URL = "https://api.openalex.org/authors"

# Create directories to save the data
data_dir = os.path.join('scripts', 'data')
os.makedirs(data_dir, exist_ok=True)

def fetch_orcids(total_authors=2000):
    """Fetch and clean ORCID identifiers for a sample of authors from OpenAlex with pagination."""
    orcids = []
    cursor = "*"  # Starting cursor for pagination
    
    while len(orcids) < total_authors:
        params = {
            'cursor': cursor,
            'per_page': 200,  # Number of authors per page
            'select': 'orcid'  # Only fetch the ORCID field
        }
        
        response = requests.get(BASE_AUTHORS_URL, params=params)
        
        if response.status_code == 200:
            data = response.json()
            if not data['results']:
                break  # Stop if no more authors are returned
            
            # Extract and clean ORCID values, ignoring entries without ORCID
            for author in data['results']:
                orcid = author.get('orcid')
                if orcid:
                    cleaned_orcid = orcid.replace("https://orcid.org/", "")
                    orcids.append(cleaned_orcid)
            
            cursor = data['meta'].get('next_cursor')  # Get cursor for next page
            
            # Add delay to respect rate limits
            time.sleep(0.1)
            
            print(f"Fetched {len(orcids)} ORCIDs so far...")
            
            if not cursor:
                break
        else:
            print(f"Failed to fetch authors: {response.status_code} - {response.text}")
            break

    return orcids[:total_authors]

def main():
    print("Starting data collection...")
    
    # Fetch and clean ORCID identifiers
    orcids = fetch_orcids(total_authors=2000)
    print(f"Successfully fetched {len(orcids)} cleaned ORCIDs")
    
    # Create a DataFrame from the collected and cleaned ORCIDs
    df = pd.DataFrame(orcids, columns=['ORCID'])
    
    # Save the DataFrame to a CSV file
    output_file = os.path.join(data_dir, 'orcid.csv')
    df.to_csv(output_file, index=False)
    print(f"Cleaned ORCID data extracted and saved to {output_file}")

if __name__ == "__main__":
    main()
