import pandas as pd
import plotly.express as px
import streamlit as st

def get_usage_metrics(conn, start_date, end_date):
    """
    Retrieve platform usage metrics from the database.
    
    Parameters:
    - conn: Database connection object
    - start_date: Start date for the analysis
    - end_date: End date for the analysis
    
    Returns:
    - Dictionary containing usage metrics DataFrames
    """
    cursor = conn.cursor()
    try:
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
                    AVG(EXTRACT(epoch FROM response_time)) as avg_response_time,
                    cache_hit_rate,
                    error_rate
                FROM search_performance
                WHERE timestamp BETWEEN %s AND %s
                GROUP BY DATE(timestamp), cache_hit_rate, error_rate
            )
            SELECT 
                json_build_object(
                    'user_activity', (SELECT json_agg(row_to_json(UserActivityMetrics)) FROM UserActivityMetrics),
                    'session_metrics', (SELECT json_agg(row_to_json(SessionMetrics)) FROM SessionMetrics),
                    'performance_metrics', (SELECT json_agg(row_to_json(PerformanceMetrics)) FROM PerformanceMetrics)
                ) as metrics
        """, (start_date, end_date) * 4)
        
        result = cursor.fetchone()[0]
        
        return {
            'user_activity': pd.DataFrame(result['user_activity']),
            'session_metrics': pd.DataFrame(result['session_metrics']),
            'performance_metrics': pd.DataFrame(result['performance_metrics'])
        }
    finally:
        cursor.close()

def display_usage_analytics(metrics):
    """
    Display usage analytics visualizations.
    
    Parameters:
    - metrics: Dictionary containing usage metrics DataFrames
    """
    st.subheader("Platform Usage Analytics")

    user_activity = metrics['user_activity']
    session_metrics = metrics['session_metrics']
    performance_metrics = metrics['performance_metrics']

    # User Activity Overview
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Total Users", 
            f"{user_activity['total_users'].sum():,}"
        )
    with col2:
        st.metric(
            "Total Interactions", 
            f"{user_activity['total_interactions'].sum():,}"
        )
    with col3:
        avg_success = session_metrics['success_rate'].mean()
        st.metric(
            "Average Success Rate", 
            f"{avg_success:.1%}"
        )

    # Daily User Activity
    st.plotly_chart(
        px.line(
            user_activity,
            x='date',
            y=['total_users', 'chat_users', 'search_users'],
            title='Daily Active Users by Type',
            labels={
                'value': 'Users',
                'variable': 'User Type',
                'date': 'Date'
            }
        )
    )

    # Session Analysis
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            px.line(
                session_metrics,
                x='date',
                y='avg_session_duration',
                title='Average Session Duration (seconds)',
                labels={
                    'avg_session_duration': 'Duration (s)',
                    'date': 'Date'
                }
            )
        )
    
    with col2:
        st.plotly_chart(
            px.line(
                session_metrics,
                x='date',
                y='avg_messages_per_session',
                title='Average Messages per Session',
                labels={
                    'avg_messages_per_session': 'Messages',
                    'date': 'Date'
                }
            )
        )

    # Performance Metrics
    st.subheader("Platform Performance")
    st.plotly_chart(
        px.line(
            performance_metrics,
            x='date',
            y=['avg_response_time', 'cache_hit_rate', 'error_rate'],
            title='Performance Metrics Over Time',
            labels={
                'value': 'Value',
                'variable': 'Metric',
                'date': 'Date'
            }
        )
    )
