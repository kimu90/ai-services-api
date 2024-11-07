import requests
import pandas as pd
import os

# Base URL for OpenAlex API
BASE_AUTHORS_URL = "https://api.openalex.org/authors"
BASE_WORKS_URL = "https://api.openalex.org/works"

# Set the parent directory
parent_dir = os.path.dirname(os.path.abspath(__file__))

# Create the 'data' directory inside the 'scripts' directory
data_dir = os.path.join(parent_dir, 'scripts', 'data')
os.makedirs(data_dir, exist_ok=True)

# File path for the CSV
output_file = os.path.join(data_dir, 'test5.csv')

def fetch_sample_authors(sample_size=3000):
    """Fetch a random sample of authors from OpenAlex."""
    authors = []
    params = {'sample': sample_size, 'select': 'id,display_name,orcid'}
    response = requests.get(BASE_AUTHORS_URL, params=params)

    if response.status_code == 200:
        data = response.json()
        authors = data['results']
    else:
        print(f"Failed to fetch authors: {response.status_code} - {response.text}")

    return authors

def fetch_works(author_id, per_page=100):
    """Fetch works for a given author ID."""
    works = []
    page = 1
    while True:
        params = {'filter': f'authorships.author.id:{author_id}', 'per_page': per_page, 'page': page}
        response = requests.get(BASE_WORKS_URL, params=params)

        if response.status_code == 200:
            data = response.json()
            works.extend(data['results'])
            if len(data['results']) < per_page:
                break  # No more pages
            page += 1
        else:
            print(f"Failed to fetch works for {author_id}: {response.status_code} - {response.text}")
            break

    return works

def extract_topic_domain_field_subfield(works):
    """Extracts the domain, field, and subfield from the topics of the works."""
    result = []
    for work in works:
        if 'topics' in work and work['topics']:
            for topic in work['topics']:
                # Assuming topics contain the domain, field, and subfield information
                domain_name = topic.get('domain', {}).get('display_name', 'Unknown Domain')
                field_name = topic.get('field', {}).get('display_name', 'Unknown Field')
                subfield_name = topic.get('subfield', {}).get('display_name', 'Unknown Subfield')
                
                result.append({
                    'domain': domain_name,
                    'field': field_name,
                    'subfield': subfield_name
                })
                break  # Only take the first domain, field, and subfield (optional, depending on your requirement)
        else:
            result.append({
                'domain': 'Unknown Domain',
                'field': 'Unknown Field',
                'subfield': 'Unknown Subfield'
            })
    return result

def load_existing_data():
    """Load the existing CSV data if it exists, and return it as a DataFrame."""
    if os.path.exists(output_file):
        return pd.read_csv(output_file)
    else:
        # Return an empty DataFrame with the expected columns if the file does not exist
        return pd.DataFrame(columns=['author_id', 'author_orcid', 'domain', 'field', 'subfield'])

def main():
    # Load existing data
    existing_data = load_existing_data()

    # Fetch a sample of authors
    authors = fetch_sample_authors(sample_size=3000)

    all_works = []

    for author in authors:
        author_id = author['id']
        orcid = author.get('orcid', 'N/A')  # Get ORCID if available
        works = fetch_works(author_id)

        # Extract domain, field, and subfield for the works fetched
        domain_field_subfield = extract_topic_domain_field_subfield(works)

        for data in domain_field_subfield:
            new_data = {
                'author_id': author_id,
                'author_orcid': orcid,
                'domain': data['domain'],
                'field': data['field'],
                'subfield': data['subfield']
            }

            # Only append new data if it's not already in the existing data
            if not ((existing_data['author_id'] == new_data['author_id']) & 
                    (existing_data['domain'] == new_data['domain']) & 
                    (existing_data['field'] == new_data['field']) & 
                    (existing_data['subfield'] == new_data['subfield'])).any():
                all_works.append(new_data)

    # Create a DataFrame from all works collected
    new_data_df = pd.DataFrame(all_works)

    # Append the new data to the existing CSV (or create it if not exists)
    if not new_data_df.empty:
        # Append new data without rewriting the existing data
        new_data_df.to_csv(output_file, mode='a', header=not os.path.exists(output_file), index=False)
        print(f"New data appended to {output_file}")
    else:
        print("No new data to append.")

if __name__ == "__main__":
    main()
