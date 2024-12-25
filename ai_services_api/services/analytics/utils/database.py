# utils/database.py
import psycopg2
from config.settings import DATABASE_CONFIG
import logging

class DatabaseConnector:
    def __init__(self):
        self.config = DATABASE_CONFIG
        self._connection = None
        
    def get_connection(self):
        if self._connection is None or self._connection.closed:
            try:
                self._connection = psycopg2.connect(**self.config)
            except Exception as e:
                logging.error(f"Database connection error: {e}")
                raise
        return self._connection
    
    def close_connection(self):
        if self._connection is not None:
            self._connection.close()
