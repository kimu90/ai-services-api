import os
import psycopg2
from psycopg2 import sql

def get_db_connection():
    """
    Establish a connection to the PostgreSQL database using environment variables or default values.
    """
    in_docker = os.getenv('DOCKER_ENV', 'false').lower() == 'true'
    
    host = 'postgres' if in_docker else 'localhost'
    port = '5432'
    dbname = os.getenv('POSTGRES_DB', 'aphrcdb')
    user = os.getenv('POSTGRES_USER', 'aphrcuser')
    password = os.getenv('POSTGRES_PASSWORD', 'kimu')

    try:
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error connecting to the database: {e}")
        raise

def drop_tables():
    """
    Drop all tables from the database.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Disable foreign key checks to avoid errors while dropping tables
        cur.execute("SET session_replication_role = 'replica';")
        
        # Fetch all table names
        cur.execute("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public';
        """)
        
        tables = cur.fetchall()
        for table in tables:
            table_name = table[0]
            cur.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE;").format(sql.Identifier(table_name)))
            print(f"Dropped table: {table_name}")
        
        # Re-enable foreign key checks
        cur.execute("SET session_replication_role = 'origin';")
        
        conn.commit()
        print("All tables dropped successfully.")
    except Exception as e:
        print(f"Error dropping tables: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def drop_database():
    """
    Drop the entire database (needs superuser privileges).
    """
    conn = psycopg2.connect(
        dbname='postgres',  # Connect to the default 'postgres' database
        user=os.getenv('POSTGRES_USER', 'aphrcuser'),
        password=os.getenv('POSTGRES_PASSWORD', 'kimu'),
        host='localhost'  # Change this if connecting remotely
    )
    conn.autocommit = True  # Required to drop a database
    
    cur = conn.cursor()
    dbname = os.getenv('POSTGRES_DB', 'aphrcdb')
    
    try:
        cur.execute(sql.SQL("DROP DATABASE IF EXISTS {};").format(sql.Identifier(dbname)))
        print(f"Database '{dbname}' dropped successfully.")
    except Exception as e:
        print(f"Error dropping database: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    try:
        drop_tables()  # Drop all tables first
        # Uncomment the next line to drop the entire database
        # drop_database()  
    except Exception as e:
        print(f"Failed to delete tables or database: {e}")
