import pandas as pd
import plotly.express as px
import streamlit as st
import time
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('analytics_dashboard')

def setup_database_connection(conn) -> None:
    cursor = conn.cursor()
    try:
        cursor.execute("SET statement_timeout = '30s';")
        cursor.execute("SET work_mem = '50MB';")
    except Exception as e:
        logger.warning(f"Failed to set database parameters: {str(e)}")
    finally:
        cursor.close()

def get_usage_metrics(
    conn,
    start_date: datetime,
    end_date: datetime
) -> Dict[str, pd.DataFrame]:
    start_time = time.time()
    cursor = conn.cursor()
    
    try:
        setup_database_connection(conn)
        
        cursor.execute("""
            WITH UserActivityMetrics AS (
                SELECT 
                    DATE(activity_date) as date,
                    total_users,
                    chat_users,
                    search_users,
                    total_interactions
                FROM (
                    SELECT 
                        COALESCE(c.date, s.date) as activity_date,
                        COUNT(DISTINCT COALESCE(c.user_id, s.user_id)) as total_users,
                        COUNT(DISTINCT c.user_id) as chat_users,
                        COUNT(DISTINCT s.user_id) as search_users,
                        COALESCE(c.chat_count, 0) + COALESCE(s.search_count, 0) as total_interactions
                    FROM (
                        SELECT 
                            DATE(timestamp) as date,
                            user_id,
                            COUNT(*) as chat_count
                        FROM chat_interactions
                        WHERE timestamp BETWEEN %s AND %s
                        GROUP BY DATE(timestamp), user_id
                    ) c
                    FULL OUTER JOIN (
                        SELECT 
                            DATE(timestamp) as date,
                            user_id,
                            COUNT(*) as search_count
                        FROM search_logs
                        WHERE timestamp BETWEEN %s AND %s
                        GROUP BY DATE(timestamp), user_id
                    ) s ON c.date = s.date AND c.user_id = s.user_id
                    GROUP BY COALESCE(c.date, s.date), c.chat_count, s.search_count
                ) daily_metrics
            ),
            SessionMetrics AS (
                SELECT 
                    DATE(start_time) as date,
                    COUNT(*) as total_sessions,
                    AVG(EXTRACT(epoch FROM (end_time - start_time))) as avg_session_duration,
                    AVG(total_messages) as avg_messages_per_session,
                    SUM(CASE WHEN successful THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate
                FROM chat_sessions
                WHERE start_time BETWEEN %s AND %s
                GROUP BY DATE(start_time)
            ),
            PerformanceMetrics AS (
                SELECT 
                    DATE(timestamp) as date,
                    AVG(EXTRACT(epoch FROM avg_response_time)) as avg_response_time,
                    cache_hit_rate,
                    error_rate
                FROM search_performance
                WHERE timestamp BETWEEN %s AND %s
                GROUP BY DATE(timestamp), cache_hit_rate, error_rate
            )
            SELECT 
                json_build_object(
                    'activity_metrics', (SELECT json_agg(row_to_json(UserActivityMetrics)) FROM UserActivityMetrics),
                    'sessions', (SELECT json_agg(row_to_json(SessionMetrics)) FROM SessionMetrics),
                    'performance', (SELECT json_agg(row_to_json(PerformanceMetrics)) FROM PerformanceMetrics)
                ) as metrics
        """, (start_date, end_date, start_date, end_date, start_date, end_date, start_date, end_date))
        
        query_time = time.time() - start_time
        if query_time > 5:
            logger.warning(f"Slow query detected: {query_time:.2f} seconds")
        
        raw_result = cursor.fetchone()
        logger.info(f"Query result: {raw_result}")
        
        if raw_result is None or raw_result[0] is None:
            logger.info("No data found for the specified date range")
            return {
                'activity_metrics': pd.DataFrame(),
                'sessions': pd.DataFrame(),
                'performance': pd.DataFrame()
            }
            
        result = raw_result[0]
        logger.info(f"Parsed result structure: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
        
        metrics = {
            'activity_metrics': pd.DataFrame(result.get('activity_metrics', [])),
            'sessions': pd.DataFrame(result.get('sessions', [])),
            'performance': pd.DataFrame(result.get('performance', []))
        }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error retrieving usage metrics: {str(e)}")
        return {
            'activity_metrics': pd.DataFrame(),
            'sessions': pd.DataFrame(),
            'performance': pd.DataFrame()
        }
    finally:
        cursor.close()

def display_usage_analytics(filters, metrics: Dict[str, pd.DataFrame]) -> None:
    try:
        st.subheader("Usage Analytics")
        
        activity_data = metrics.get('activity_metrics', pd.DataFrame())
        session_data = metrics.get('sessions', pd.DataFrame())
        perf_data = metrics.get('performance', pd.DataFrame())
        
        if activity_data.empty and session_data.empty and perf_data.empty:
            st.warning("No data available for the selected date range.")
            return
            
        # Overview metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            total_users = activity_data['total_users'].sum() if not activity_data.empty else 0
            st.metric("Total Users", f"{total_users:,}")
        with col2:
            total_sessions = session_data['total_sessions'].sum() if not session_data.empty else 0
            st.metric("Total Sessions", f"{total_sessions:,}")
        with col3:
            avg_success = session_data['success_rate'].mean() if not session_data.empty else 0
            st.metric("Average Success Rate", f"{avg_success:.1%}")
        
        # User Activity Trends
        if not activity_data.empty:
            st.plotly_chart(
                px.line(
                    activity_data,
                    x='date',
                    y=['chat_users', 'search_users'],
                    title='Daily Active Users by Type',
                    labels={'value': 'Users', 'variable': 'Type'}
                ).update_layout(height=400),
                use_container_width=True
            )
        
        # Session Analysis
        if not session_data.empty:
            col1, col2 = st.columns(2)
            with col1:
                st.plotly_chart(
                    px.line(
                        session_data,
                        x='date',
                        y='avg_session_duration',
                        title='Average Session Duration (seconds)'
                    ).update_layout(height=300),
                    use_container_width=True
                )
            
            with col2:
                st.plotly_chart(
                    px.line(
                        session_data,
                        x='date',
                        y='avg_messages_per_session',
                        title='Average Messages per Session'
                    ).update_layout(height=300),
                    use_container_width=True
                )
        
        # Performance Metrics
        if not perf_data.empty:
            st.subheader("System Performance")
            st.plotly_chart(
                px.line(
                    perf_data,
                    x='date',
                    y=['avg_response_time', 'error_rate'],
                    title='System Performance Over Time',
                    labels={
                        'value': 'Value',
                        'variable': 'Metric'
                    }
                ).update_layout(height=400),
                use_container_width=True
            )
            
    except Exception as e:
        logger.error(f"Error displaying analytics: {str(e)}")
        st.error("An error occurred while displaying the analytics. Please try again later.")
