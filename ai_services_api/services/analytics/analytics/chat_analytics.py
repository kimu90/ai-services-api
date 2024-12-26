import pandas as pd
import plotly.express as px
import streamlit as st

def get_chat_metrics(conn, start_date, end_date):
    """
    Retrieve chat metrics from the database for the specified date range.

    This function queries the database to fetch various chat metrics such as total interactions, unique sessions,
    unique users, average response time, error rate, total matches, average similarity, and click rate. The metrics
    are grouped by date and returned as a pandas DataFrame.

    Parameters:
    - conn: psycopg2 connection object representing the database connection.
    - start_date (datetime): The start date of the date range.
    - end_date (datetime): The end date of the date range.

    Returns:
    - pandas.DataFrame: A DataFrame containing the chat metrics grouped by date.
    """
    cursor = conn.cursor()
    try:
        cursor.execute("""
            WITH ChatMetrics AS (
                SELECT 
                    DATE(timestamp) as date,
                    COUNT(*) as total_interactions,
                    COUNT(DISTINCT session_id) as unique_sessions,
                    COUNT(DISTINCT user_id) as unique_users,
                    AVG(response_time) as avg_response_time,
                    SUM(CASE WHEN error_occurred THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as error_rate
                FROM chat_interactions
                WHERE timestamp BETWEEN %s AND %s
                GROUP BY DATE(timestamp)
            ),
            ExpertMatchMetrics AS (
                SELECT 
                    DATE(i.timestamp) as date,
                    COUNT(*) as total_matches,
                    AVG(a.similarity_score) as avg_similarity,
                    SUM(CASE WHEN a.clicked THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as click_rate
                FROM chat_analytics a
                JOIN chat_interactions i ON a.interaction_id = i.id
                WHERE i.timestamp BETWEEN %s AND %s
                GROUP BY DATE(i.timestamp)
            )
            SELECT 
                cm.*,
                em.total_matches,
                em.avg_similarity,
                em.click_rate
            FROM ChatMetrics cm
            LEFT JOIN ExpertMatchMetrics em ON cm.date = em.date
            ORDER BY cm.date
        """, (start_date, end_date, start_date, end_date))
        
        columns = [desc[0] for desc in cursor.description]
        data = cursor.fetchall()
        return pd.DataFrame(data, columns=columns)
    finally:
        cursor.close()

def display_chat_analytics(chat_metrics,filters):
    """
    Display chat analytics visualizations using the provided chat metrics DataFrame.

    This function creates various visualizations using the chat metrics data, including:
    1. Daily chat volume line chart showing total interactions and unique sessions over time.
    2. Average response time line chart.
    3. Error rate line chart.

    The visualizations are created using Plotly Express and displayed using Streamlit's `st.plotly_chart` function.

    Parameters:
    - chat_metrics (pandas.DataFrame): A DataFrame containing the chat metrics data.
    """
    st.subheader("Chat Analytics")
    
    # Daily chat volume
    st.plotly_chart(
        px.line(
            chat_metrics,
            x="date",
            y=["total_interactions", "unique_sessions"],
            title="Daily Chat Volume",
            labels={"value": "Count", "variable": "Metric"}
        )
    )
    
    # Response time and error rate
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            px.line(
                chat_metrics,
                x="date",
                y="avg_response_time",
                title="Average Response Time"
            )
        )
    with col2:
        st.plotly_chart(
            px.line(
                chat_metrics,
                x="date",
                y="error_rate",
                title="Error Rate"
            )
        )
