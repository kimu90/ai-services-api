import pandas as pd
import plotly.express as px

def get_search_metrics(conn, start_date, end_date):
    """
    Retrieve search metrics from the database for the specified date range.

    This function queries the database to fetch various search metrics such as total searches, unique users,
    average response time, and click-through rate. The metrics are grouped by date and returned as a pandas DataFrame.

    Parameters:
    - conn: psycopg2 connection object representing the database connection.
    - start_date (datetime): The start date of the date range.
    - end_date (datetime): The end date of the date range.

    Returns:
    - pandas.DataFrame: A DataFrame containing the search metrics grouped by date.
    """
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as total_searches,
                COUNT(DISTINCT user_id) as unique_users,
                AVG(EXTRACT(EPOCH FROM response_time)) as avg_response_time,
                SUM(CASE WHEN clicked THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as click_through_rate
            FROM search_logs
            WHERE timestamp BETWEEN %s AND %s
            GROUP BY DATE(timestamp)
            ORDER BY date
        """, (start_date, end_date))
        
        columns = [desc[0] for desc in cursor.description]
        data = cursor.fetchall()
        return pd.DataFrame(data, columns=columns)
    finally:
        cursor.close()

def display_search_analytics(search_metrics):
    """
    Display search analytics visualizations using the provided search metrics DataFrame.

    This function creates various visualizations to analyze search performance and user behavior, including:
    1. Daily search volume line chart showing total searches and unique users over time.
    2. Click-through rate line chart displaying the percentage of clicks on search results.

    The visualizations are created using Plotly Express and displayed using Streamlit's `st.plotly_chart` function.

    Parameters:
    - search_metrics (pandas.DataFrame): A DataFrame containing the search metrics data.
    """
    st.subheader("Search Analytics")
    
    # Daily search volume
    st.plotly_chart(
        px.line(
            search_metrics,
            x="date",
            y=["total_searches", "unique_users"],
            title="Daily Search Volume",
            labels={"value": "Count", "variable": "Metric"}
        )
    )
    
    # Click-through rate
    st.plotly_chart(
        px.line(
            search_metrics,
            x="date",
            y="click_through_rate",
            title="Click-through Rate"
        )
    )
