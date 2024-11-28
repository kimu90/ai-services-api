import os
import pandas as pd
import numpy as np
import faiss
import pickle
from ai_services_api.services.search.config import get_settings
from ai_services_api.services.search.embedding_model import EmbeddingModel
from psycopg2.extras import RealDictCursor
from typing import Dict, List, Any

def get_publications_with_metadata():
    """
    Fetch publications with their associated tags and authors from the database.
    Returns a list of dictionaries containing publication data with metadata.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
            WITH publication_tags AS (
                SELECT 
                    pt.publication_doi,
                    t.tag_name,
                    t.tag_id
                FROM publication_tag pt
                JOIN tags t ON pt.tag_id = t.tag_id
            ),
            domain_tags AS (
                SELECT publication_doi, STRING_AGG(tag_name, ', ') as domains
                FROM publication_tags
                WHERE tag_id IN (SELECT tag_id FROM tags WHERE tag_name LIKE 'Domain:%')
                GROUP BY publication_doi
            ),
            field_tags AS (
                SELECT publication_doi, STRING_AGG(tag_name, ', ') as fields
                FROM publication_tags
                WHERE tag_id IN (SELECT tag_id FROM tags WHERE tag_name LIKE 'Field:%')
                GROUP BY publication_doi
            ),
            subfield_tags AS (
                SELECT publication_doi, STRING_AGG(tag_name, ', ') as subfields
                FROM publication_tags
                WHERE tag_id IN (SELECT tag_id FROM tags WHERE tag_name LIKE 'Subfield:%')
                GROUP BY publication_doi
            ),
            publication_authors AS (
                SELECT 
                    ap.doi,
                    STRING_AGG(a.name, ', ') as authors
                FROM author_publication ap
                JOIN authors a ON ap.author_id = a.author_id
                GROUP BY ap.doi
            )
            SELECT 
                p.doi,
                p.title,
                p.abstract,
                p.summary,
                COALESCE(d.domains, '') as domains,
                COALESCE(f.fields, '') as fields,
                COALESCE(sf.subfields, '') as subfields,
                COALESCE(pa.authors, '') as authors
            FROM publications p
            LEFT JOIN domain_tags d ON p.doi = d.publication_doi
            LEFT JOIN field_tags f ON p.doi = f.publication_doi
            LEFT JOIN subfield_tags sf ON p.doi = sf.publication_doi
            LEFT JOIN publication_authors pa ON p.doi = pa.doi;
            """
            cur.execute(query)
            return cur.fetchall()
    finally:
        conn.close()

def prepare_text_for_embedding(publication: Dict[str, Any]) -> str:
    """
    Prepare publication data for embedding by combining relevant fields.
    Args:
        publication: Dictionary containing publication data
    Returns:
        Combined text string for embedding
    """
    fields = [
        ('Title', publication['title']),
        ('Abstract', publication['abstract']),
        ('Summary', publication['summary']),
        ('Domains', publication['domains']),
        ('Fields', publication['fields']),
        ('Subfields', publication['subfields']),
        ('Authors', publication['authors'])
    ]
    
    # Combine fields, handling None values
    text_parts = [
        f"{field_name}: {content}" 
        for field_name, content in fields 
        if content is not None and content.strip()
    ]
    
    return ' | '.join(text_parts)

def create_faiss_index(model_path=None):
    """
    Create FAISS index and chunk mapping from database data.
    Args:
        model_path (str, optional): Path to embedding model. Defaults to config setting.
    """
    # Get settings
    settings = get_settings()
    model_path = model_path or settings.MODEL_PATH
    
    # Initialize embedding model
    embedding_model = EmbeddingModel(model_path)
    
    # Fetch publications with metadata
    publications = get_publications_with_metadata()
    
    if not publications:
        raise ValueError("No publications found in the database")
    
    # Prepare texts for embedding
    texts = [prepare_text_for_embedding(pub) for pub in publications]
    
    # Generate embeddings
    print("Generating embeddings...")
    embeddings = np.array([embedding_model.get_embedding(text)[0] for text in texts])
    
    # Create FAISS index
    print("Creating FAISS index...")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    
    # Ensure static directory exists
    os.makedirs(os.path.dirname(settings.INDEX_PATH), exist_ok=True)
    
    # Save FAISS index
    print("Saving FAISS index...")
    faiss.write_index(index, settings.INDEX_PATH)
    
    # Create chunk mapping using DOI as key
    chunk_mapping = {pub['doi']: pub for pub in publications}
    
    # Save chunk mapping
    print("Saving chunk mapping...")
    with open(settings.CHUNK_MAPPING_PATH, 'wb') as f:
        pickle.dump(chunk_mapping, f)
    
    print(f"Successfully created index with {len(publications)} publications!")
    print(f"Index saved to: {settings.INDEX_PATH}")
    print(f"Chunk mapping saved to: {settings.CHUNK_MAPPING_PATH}")

if __name__ == "__main__":
    try:
        create_faiss_index()
    except Exception as e:
        print(f"Error creating index: {e}")
        print("\nTroubleshooting steps:")
        print("1. Ensure the database is running and accessible")
        print("2. Check that all required tables exist and contain data")
        print("3. Verify the embedding model path is correct")
        print("4. Ensure you have write permissions for the output directories")