import pandas as pd
import requests
import asyncio
import aiohttp
import json

# Load the CSV file
df = pd.read_csv("sme.csv")

# Add new columns for ORCID and OpenAlex ID
df['ORCID'] = ''
df['OpenAlex_ID'] = ''

# Function to fetch ORCID and OpenAlex ID using Firstname and Lastname
def get_openalex_data(firstname, lastname):
    base_url = "https://api.openalex.org/authors"
    params = {"search": f"{firstname} {lastname}"}
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        if response.status_code == 200:
            results = response.json().get('results', [])
            if results:
                # Assume the first result is the correct author
                author = results[0]
                orcid = author.get('orcid', '')
                openalex_id = author.get('id', '').split('/')[-1]
                return orcid, openalex_id
            else:
                print(f"No results found for {firstname} {lastname}")
    except requests.RequestException as e:
        print(f"Error fetching data for {firstname} {lastname}: {e}")
    return '', ''

# Asynchronous function to fetch works with detailed logging
async def get_expert_works(session, openalex_id, retries=3, delay=5):
    works_url = "https://api.openalex.org/works"
    params = {'filter': f"authorships.author.id:https://openalex.org/A{openalex_id}", 'per-page': 50}
    
    print(f"Fetching works for OpenAlex_ID: {openalex_id}")
    print(f"Works API URL: {works_url}")
    print(f"Params: {params}")

    attempt = 0
    while attempt < retries:
        try:
            async with session.get(works_url, params=params) as response:
                print(f"Response status: {response.status}")
                
                if response.status == 200:
                    works_data = await response.json()
                    
                    # Debug: Print entire works data
                    print("Works Data (first work):")
                    print(json.dumps(works_data.get('results', [])[:1], indent=2))
                    
                    return works_data.get('results', [])
                
                elif response.status == 429:  # Rate limit error
                    print("Rate limit hit, retrying...")
                    await asyncio.sleep(delay * (attempt + 1))
                else:
                    print(f"Error fetching works for OpenAlex_ID {openalex_id}: {response.status}")
                    break
        except Exception as e:
            print(f"Error fetching works for OpenAlex_ID {openalex_id}: {e}")
        
        attempt += 1
        await asyncio.sleep(delay)
    
    return []

# Asynchronous function to extract domains, fields, and subfields
async def get_expert_domains(session, firstname, lastname, openalex_id):
    works = await get_expert_works(session, openalex_id)
    
    # Initialize lists to hold the domains, fields, and subfields
    domains = []
    fields = []
    subfields = []

    for work in works:
        # Check if 'topics' exist in the work
        topics = work.get('topics', [])
        
        if not topics:
            print(f"No topics found for work by {firstname} {lastname}")
            continue

        for topic in topics:
            domain = topic.get('domain', {})
            field = topic.get('field', {})
            subfields_list = topic.get('subfields', [])

            domain_name = domain.get('display_name', 'Unknown Domain')
            field_name = field.get('display_name', 'Unknown Field')
            
            domains.append(domain_name)
            fields.append(field_name)

            # Handle subfields, and limit to first 10 subfields if more exist
            subfields.extend([subfield.get('display_name', 'Unknown Subfield') for subfield in subfields_list[:10]])

    return domains, fields, subfields

# Main function to orchestrate the workflow
async def main():
    # Update ORCID and OpenAlex_ID first
    for index, row in df.iterrows():
        firstname = row['Firstname']
        lastname = row['Lastname']
        orcid, openalex_id = get_openalex_data(firstname, lastname)
        df.at[index, 'ORCID'] = orcid
        df.at[index, 'OpenAlex_ID'] = openalex_id

    # Save updated DataFrame
    df.to_csv("updated_sme.csv", index=False)

    # Prepare lists to hold data for each domain, field, and subfield
    all_domains = []
    all_fields = []
    all_subfields = []

    # Fetch domains, fields, and subfields using async session
    async with aiohttp.ClientSession() as session:
        tasks = []
        for _, row in df.iterrows():
            if row['OpenAlex_ID']:
                tasks.append(get_expert_domains(session, row['Firstname'], row['Lastname'], row['OpenAlex_ID']))
        
        results = await asyncio.gather(*tasks)

        # Process the results
        for domains, fields, subfields in results:
            all_domains.append(domains)
            all_fields.append(fields)
            all_subfields.append(subfields)

    # Convert the lists into a DataFrame, grouping domains, fields, and subfields into single columns
    expert_data = []
    for i in range(len(all_domains)):
        expert_info = {
            'ORCID': df.loc[i, 'ORCID'],
            'Firstname': df.loc[i, 'Firstname'],
            'Lastname': df.loc[i, 'Lastname'],
            'Domains': ', '.join(all_domains[i]),
            'Fields': ', '.join(all_fields[i]),
            'Subfields': ', '.join(all_subfields[i]),
        }
        expert_data.append(expert_info)

   