import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union
import logging
from data_processor import DataProcessor
import psycopg2
from psycopg2.extras import RealDictCursor
import json

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class MetricsCalculator:
    def __init__(self, conn):
        """
        Initialize MetricsCalculator with database connection
        
        Args:
            conn: Database connection object
        """
        self.conn = conn
        self.data_processor = DataProcessor(conn)

    def get_search_metrics(self, start_date: datetime, end_date: datetime, 
                          search_types: List[str]) -> Dict:
        """
        Get search metrics for specified date range and search types
        
        Args:
            start_date: Start date for metrics calculation
            end_date: End date for metrics calculation
            search_types: List of search types to include
            
        Returns:
            Dictionary containing aggregated search metrics
        """
        try:
            query = """
            SELECT 
                COUNT(*) as total_searches,
                COUNT(DISTINCT user_id) as unique_users,
                AVG(EXTRACT(EPOCH FROM response_time)) as avg_response_time,
                SUM(CASE WHEN clicked THEN 1 ELSE 0 END)::FLOAT / 
                    COUNT(*) as click_through_rate,
                AVG(success_rate) as avg_success_rate,
                -- Additional metrics
                AVG(CASE WHEN success_rate >= 0.8 THEN 1 ELSE 0 END)::FLOAT 
                    as high_success_rate_percentage,
                COUNT(DISTINCT CASE WHEN clicked THEN user_id END)::FLOAT / 
                    NULLIF(COUNT(DISTINCT user_id), 0) as user_engagement_rate
            FROM search_logs
            WHERE timestamp BETWEEN %s AND %s
            AND search_type = ANY(%s);
            """
            
            df = pd.read_sql(query, self.conn, 
                           params=[start_date, end_date, search_types])
            
            # Add derived metrics
            metrics_dict = df.to_dict(orient='records')[0]
            metrics_dict['daily_active_users'] = self._calculate_daily_active_users(
                start_date, end_date
            )
            
            return metrics_dict
            
        except Exception as e:
            logger.error(f"Error getting search metrics: {e}")
            return {}

    def get_performance_metrics(self, start_date: datetime, 
                              end_date: datetime) -> pd.DataFrame:
        """
        Get system performance metrics
        
        Args:
            start_date: Start date for metrics
            end_date: End date for metrics
            
        Returns:
            DataFrame containing performance metrics over time
        """
        try:
            query = """
            SELECT 
                timestamp,
                avg_response_time,
                cache_hit_rate,
                error_rate,
                total_queries,
                unique_users,
                -- Additional performance metrics
                total_queries::FLOAT / 
                    EXTRACT(EPOCH FROM timestamp - LAG(timestamp) OVER (ORDER BY timestamp))
                    as queries_per_second,
                CASE 
                    WHEN error_rate > 0.05 THEN 'High'
                    WHEN error_rate > 0.01 THEN 'Medium'
                    ELSE 'Low'
                END as error_severity
            FROM search_performance
            WHERE timestamp BETWEEN %s AND %s
            ORDER BY timestamp;
            """
            
            df = pd.read_sql(query, self.conn, params=[start_date, end_date])
            
            # Add rolling averages
            df['response_time_ma'] = df['avg_response_time'].rolling(
                window=24, min_periods=1
            ).mean()
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return pd.DataFrame()

    def get_expert_metrics(self, start_date: datetime, 
                          end_date: datetime) -> pd.DataFrame:
        """
        Get expert search related metrics
        
        Args:
            start_date: Start date for metrics
            end_date: End date for metrics
            
        Returns:
            DataFrame containing expert search metrics
        """
        try:
            return self.data_processor.get_expert_search_metrics(start_date, end_date)
        except Exception as e:
            logger.error(f"Error getting expert metrics: {e}")
            return pd.DataFrame()

    def get_user_behavior_metrics(self, start_date: datetime, 
                                end_date: datetime) -> Dict:
        """
        Get user behavior metrics and patterns
        
        Args:
            start_date: Start date for metrics
            end_date: End date for metrics
            
        Returns:
            Dictionary containing user behavior metrics and session data
        """
        try:
            session_data = self.data_processor.get_user_session_data(
                start_date, end_date
            )
            
            # Calculate basic metrics
            metrics = {
                'avg_session_duration': session_data['duration'].mean(),
                'avg_queries_per_session': session_data['query_count'].mean(),
                'success_rate': (session_data['successful_searches'] / 
                               session_data['query_count']).mean(),
                'session_data': session_data
            }
            
            # Add advanced metrics
            metrics.update({
                'retention_rate': self._calculate_retention_rate(
                    start_date, end_date
                ),
                'user_segments': self._segment_users(session_data),
                'session_distribution': self._get_session_distribution(session_data)
            })
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting user behavior metrics: {e}")
            return {}

    def _calculate_daily_active_users(self, start_date: datetime, 
                                    end_date: datetime) -> float:
        """Calculate average daily active users"""
        try:
            query = """
            SELECT AVG(daily_users) as avg_daily_users
            FROM (
                SELECT DATE(timestamp) as date, 
                       COUNT(DISTINCT user_id) as daily_users
                FROM search_logs
                WHERE timestamp BETWEEN %s AND %s
                GROUP BY DATE(timestamp)
            ) daily
            """
            df = pd.read_sql(query, self.conn, params=[start_date, end_date])
            return float(df['avg_daily_users'].iloc[0])
        except Exception as e:
            logger.error(f"Error calculating daily active users: {e}")
            return 0.0

    def _calculate_retention_rate(self, start_date: datetime, 
                                end_date: datetime) -> float:
        """Calculate user retention rate"""
        try:
            query = """
            WITH user_activity AS (
                SELECT user_id,
                       MIN(DATE(timestamp)) as first_day,
                       MAX(DATE(timestamp)) as last_day
                FROM search_logs
                WHERE timestamp BETWEEN %s AND %s
                GROUP BY user_id
            )
            SELECT AVG(CASE 
                         WHEN last_day - first_day >= 7 THEN 1
                         ELSE 0
                      END)::FLOAT as retention_rate
            FROM user_activity
            """
            df = pd.read_sql(query, self.conn, params=[start_date, end_date])
            return float(df['retention_rate'].iloc[0])
        except Exception as e:
            logger.error(f"Error calculating retention rate: {e}")
            return 0.0

    def _segment_users(self, session_data: pd.DataFrame) -> Dict[str, int]:
        """Segment users based on their activity"""
        try:
            segments = {
                'power_users': len(session_data[
                    session_data['query_count'] > session_data['query_count'].quantile(0.9)
                ]),
                'regular_users': len(session_data[
                    (session_data['query_count'] <= session_data['query_count'].quantile(0.9)) &
                    (session_data['query_count'] >= session_data['query_count'].quantile(0.1))
                ]),
                'occasional_users': len(session_data[
                    session_data['query_count'] < session_data['query_count'].quantile(0.1)
                ])
            }
            return segments
        except Exception as e:
            logger.error(f"Error segmenting users: {e}")
            return {}

    def _get_session_distribution(self, session_data: pd.DataFrame) -> Dict[str, float]:
        """Calculate session duration distribution"""
        try:
            distribution = {
                'short_sessions': len(session_data[session_data['duration'] < 300]),  # < 5 min
                'medium_sessions': len(session_data[
                    (session_data['duration'] >= 300) & 
                    (session_data['duration'] < 900)
                ]),  # 5-15 min
                'long_sessions': len(session_data[session_data['duration'] >= 900])  # > 15 min
            }
            return distribution
        except Exception as e:
            logger.error(f"Error calculating session distribution: {e}")
            return {}
