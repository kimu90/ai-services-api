import requests
import csv

def fetch_orcid(ids):
    pubs = []
    for id in ids:
        url = f"https://pub.orcid.org/v3.0/{id}/works"
        resp = requests.get(url, headers={'Accept': 'application/json'})
        if resp.status_code != 200:
            print(f"Error fetching ORCID data for {id}")
            continue
        for work in resp.json().get('group', []):
            for item in work.get('works', []):
                pub = {
                    'Title': item.get('title', {}).get('value', 'N/A'),
                    'Author': ', '.join([c['creditName']['value'] for c in item.get('contributors', {}).get('contributor', [])]) or 'N/A',
                    'Date': item.get('publicationDate', {}).get('year', 'N/A'),
                    'DOI': item.get('doi', 'N/A'),
                    'URL': item.get('url', 'N/A')
                }
                pubs.append(pub)
    return pubs

def fetch_dspace(url, limit=100):
    pubs = []
    try:
        resp = requests.get(f"{url}/rest/items", headers={'Accept': 'application/json'}, params={'limit': limit})
        resp.raise_for_status()
        for item in resp.json():
            pub = {
                'Title': item.get('name', 'N/A'),
                'Author': item.get('author', 'N/A'),
                'Date': item.get('date', 'N/A'),
                'DOI': item.get('doi', 'N/A'),
                'URL': item.get('url', 'N/A')
            }
            pubs.append(pub)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching DSpace data: {e}")
    return pubs

orcid_ids = ['0000-0002-1825-0097', '0000-0002-1694-233X', '0000-0002-1825-0098']
dspace_url = 'https://dash.harvard.edu'

orcid_pubs = fetch_orcid(orcid_ids)
dspace_pubs = fetch_dspace(dspace_url)

with open('orcid_pubs.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['Title', 'Author', 'Date', 'DOI', 'URL'])
    writer.writeheader()
    writer.writerows(orcid_pubs)

with open('dspace_pubs.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['Title', 'Author', 'Date', 'DOI', 'URL'])
    writer.writeheader()
    writer.writerows(dspace_pubs)

print("ORCID data saved to orcid_pubs.csv")
print("DSpace data saved to dspace_pubs.csv")