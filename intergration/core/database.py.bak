import psycopg2
from psycopg2.extras import DictCursor

class Database:
    def __init__(self, config):
        self.conn = psycopg2.connect(**config)
        
    def insert_publication(self, pub_data):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO publications (doi, title, authors, source)
                VALUES (%(doi)s, %(title)s, %(authors)s, %(source)s)
                ON CONFLICT (doi) DO UPDATE 
                SET title = EXCLUDED.title,
                    authors = EXCLUDED.authors,
                    updated_at = CURRENT_TIMESTAMP
            """, pub_data)
        self.conn.commit()