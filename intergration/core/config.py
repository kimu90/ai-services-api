import os
import requests
import pandas as pd
from secret import baseURL, email, password, filePath, handlePrefix, skippedCollections

auth_url = f"{baseURL}/rest/login"
auth_response = requests.post(auth_url, data={'email': email, 'password': password})
auth_token = auth_response.json()['token']

communities_url = f"{baseURL}/rest/communities"
communities_response = requests.get(communities_url, headers={'Accept': 'application/json', 'rest-dspace-token': auth_token})
aphrc_communities = [c for c in communities_response.json() if c['name'].startswith('APHRC')]

data = []
for community in aphrc_communities:
    collections_url = f"{baseURL}/rest/communities/{community['uuid']}/collections"
    collections_response = requests.get(collections_url, headers={'Accept': 'application/json', 'rest-dspace-token': auth_token})
    aphrc_collections = [c for c in collections_response.json() if c['name'].startswith('APHRC')]

    for collection in aphrc_collections:
        items_url = f"{baseURL}/rest/collections/{collection['uuid']}/items"
        items_response = requests.get(items_url, headers={'Accept': 'application/json', 'rest-dspace-token': auth_token})
        items = items_response.json()

        for item in items:
            metadata_url = f"{baseURL}/rest/items/{item['uuid']}/metadata"
            metadata_response = requests.get(metadata_url, headers={'Accept': 'application/json', 'rest-dspace-token': auth_token})
            metadata = metadata_response.json()

            row = {
                'uuid': item['uuid'],
                'handle': item['handle'],
                'community_name': community['name'],
                'collection_name': collection['name'],
                'title': next((field['value'] for field in metadata if field['key'] == 'dc.title'), None),
                'author': next((field['value'] for field in metadata if field['key'] == 'dc.contributor.author'), None),
                'date': next((field['value'] for field in metadata if field['key'] == 'dc.date.issued'), None),
                'subject': next((field['value'] for field in metadata if field['key'] == 'dc.subject'), None),
                'description': next((field['value'] for field in metadata if field['key'] == 'dc.description.abstract'), None)
            }
            data.append(row)

df = pd.DataFrame(data)
df.to_csv(os.path.join(filePath, 'dspace.csv'), index=False)