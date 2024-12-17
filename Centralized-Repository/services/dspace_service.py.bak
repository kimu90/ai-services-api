import requests

def fetch_dspace_publications(base_url, page=0, size=20):
    """
    Fetch publications from a DSpace repository
    
    Args:
        base_url: The base URL of your DSpace installation
        page: Page number for pagination
        size: Number of items per page
    """
    # Try DSpace 7.x endpoint first
    endpoint = f"{base_url}/server/api/core/items"
    
    try:
        response = requests.get(
            endpoint,
            params={
                'page': page,
                'size': size,
                'embed': 'bundles,metadata'
            },
            headers={'Accept': 'application/json'}
        )
        
        if response.status_code == 404:
            # Try DSpace 6.x endpoint if 7.x fails
            endpoint = f"{base_url}/rest/items"
            response = requests.get(
                endpoint,
                params={
                    'limit': size,
                    'offset': page * size,
                    'expand': 'metadata,bitstreams'
                },
                headers={'Accept': 'application/json'}
            )
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching publications: {e}")
        return None

def get_all_publications(base_url):
    """
    Fetch all publications using pagination
    """
    all_publications = []
    page = 0
    while True:
        publications = fetch_dspace_publications(base_url, page)
        if not publications or len(publications) == 0:
            break
        all_publications.extend(publications)
        page += 1
    return all_publications