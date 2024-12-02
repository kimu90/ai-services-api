from fastapi import FastAPI, Query, APIRouter
from typing import List, Optional
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor

router = APIRouter()

class Publication(BaseModel):
    doi: str
    title: str
    abstract: Optional[str]
    summary: Optional[str]
    author: str
    domain: Optional[str]
    field: Optional[str]
    subfield: Optional[str]

def get_db_connection():
    conn = psycopg2.connect(
        dbname="yourdbname",
        user="youruser",
        password="yourpassword",
        host="localhost",  # or your database host
        port="5432"        # or your database port
    )
    return conn

@router.get("/", response_model=List[Publication])
async def get_filtered_content(
    domain: Optional[str] = Query(None),
    author: Optional[str] = Query(None),
    field: Optional[str] = Query(None),
    subfield: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        query = """
            WITH filtered_pubs AS (
                SELECT DISTINCT
                    p.doi,
                    p.title,
                    p.abstract,
                    p.summary,
                    a.name as author,
                    MAX(CASE WHEN t.tag_name LIKE 'Domain:%' THEN SUBSTRING(t.tag_name FROM 8) END) as domain,
                    MAX(CASE WHEN t.tag_name LIKE 'Field:%' THEN SUBSTRING(t.tag_name FROM 7) END) as field,
                    MAX(CASE WHEN t.tag_name LIKE 'Subfield:%' THEN SUBSTRING(t.tag_name FROM 10) END) as subfield
                FROM publications p
                LEFT JOIN author_publication ap ON p.doi = ap.doi
                LEFT JOIN authors a ON ap.author_id = a.author_id
                LEFT JOIN publication_tag pt ON p.doi = pt.publication_doi
                LEFT JOIN tags t ON pt.tag_id = t.tag_id
                WHERE 1=1
        """
        
        params = []
        
        # Add filters
        if domain:
            query += " AND EXISTS (SELECT 1 FROM publication_tag pt2 JOIN tags t2 ON pt2.tag_id = t2.tag_id WHERE pt2.publication_doi = p.doi AND t2.tag_name = %s)"
            params.append(f"Domain:{domain}")
        
        if field:
            query += " AND EXISTS (SELECT 1 FROM publication_tag pt2 JOIN tags t2 ON pt2.tag_id = t2.tag_id WHERE pt2.publication_doi = p.doi AND t2.tag_name = %s)"
            params.append(f"Field:{field}")
        
        if subfield:
            query += " AND EXISTS (SELECT 1 FROM publication_tag pt2 JOIN tags t2 ON pt2.tag_id = t2.tag_id WHERE pt2.publication_doi = p.doi AND t2.tag_name = %s)"
            params.append(f"Subfield:{subfield}")
        
        if search:
            query += " AND (p.title ILIKE %s OR p.abstract ILIKE %s OR p.summary ILIKE %s)"
            params.extend([f"%{search}%" for _ in range(3)])

        query += " GROUP BY p.doi, p.title, p.abstract, p.summary, a.name"

        cur.execute(query, params)
        rows = cur.fetchall()

        return rows
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
