import requests
import csv
import random

def fetch_african_nexus(limit=20):
    url = "https://african-nexus.org/api/works"
    headers = {'Accept': 'application/json'}
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        works = random.sample(resp.json(), min(limit, len(resp.json())))
        return [{
            'Title': work.get('title', 'N/A'),
            'Author': ', '.join(author.get('name', 'N/A') for author in work.get('authors', [])),
            'Date': work.get('publicationDate', 'N/A'),
            'DOI': work.get('doi', 'N/A'),
            'URL': work.get('url', 'N/A')
        } for work in works]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching African Nexus data: {e}")
        return []

african_nexus_works = fetch_african_nexus()

with open('african_nexus_works.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['Title', 'Author', 'Date', 'DOI', 'URL'])
    writer.writeheader()
    writer.writerows(african_nexus_works)

print("African Nexus works saved to african_nexus_works.csv")