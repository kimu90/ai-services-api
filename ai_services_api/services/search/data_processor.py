import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from utils.logger import setup_logger
from utils.db_utils import DatabaseConnector

logger = setup_logger(__name__)

class DataProcessor:
    def __init__(self, conn):
        self.db = DatabaseConnector()


    def get_daily_search_metrics(self, start_date: datetime, 
                               end_date: datetime) -> pd.DataFrame:
        query = """
        SELECT DATE(timestamp) as date,
               COUNT(*) as total_searches,
               COUNT(DISTINCT user_id) as unique_users,
               AVG(EXTRACT(EPOCH FROM response_time)) as avg_response_time_seconds,
               SUM(CASE WHEN clicked THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as ctr
        FROM search_logs
        WHERE timestamp BETWEEN %s AND %s
        GROUP BY DATE(timestamp)
        ORDER BY date;
        """
        return pd.read_sql(query, self.conn, params=[start_date, end_date])

    def get_expert_search_metrics(self, start_date: datetime, 
                                end_date: datetime) -> pd.DataFrame:
        query = """
        SELECT es.expert_id,
               sl.search_type,
               COUNT(*) as appearances,
               AVG(es.rank_position) as avg_rank,
               SUM(CASE WHEN es.clicked THEN 1 ELSE 0 END)::FLOAT / 
                   COUNT(*) as click_rate
        FROM expert_searches es
        JOIN search_logs sl ON es.search_id = sl.id
        WHERE sl.timestamp BETWEEN %s AND %s
        GROUP BY es.expert_id, sl.search_type;
        """
        return pd.read_sql(query, self.conn, params=[start_date, end_date])

    def get_user_session_data(self, start_date: datetime, 
                            end_date: datetime) -> pd.DataFrame:
        query = """
        SELECT user_id,
               start_timestamp,
               end_timestamp,
               query_count,
               successful_searches,
               EXTRACT(EPOCH FROM (end_timestamp - start_timestamp)) as duration
        FROM search_sessions
        WHERE start_timestamp BETWEEN %s AND %s;
        """
        return pd.read_sql(query, self.conn, params=[start_date, end_date])
