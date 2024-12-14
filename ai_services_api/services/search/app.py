import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import List, Dict, Any
from utils.logger import setup_logger
from utils.db_utils import DatabaseConnector

logger = setup_logger(__name__)

class UnifiedAnalyticsDashboard:
    def __init__(self):
        self.db = DatabaseConnector()
        self.conn = self.db.get_connection()

    def main(self):
        st.set_page_config(page_title="APHRC Analytics Dashboard", layout="wide")
        st.title("APHRC Analytics Dashboard")

        # Sidebar filters
        self.create_sidebar_filters()

        # Top-level metrics
        self.display_overall_metrics()

        # Tabs for different analytics sections
        tabs = st.tabs(["Chat Analytics", "Search Analytics", "Expert Analytics", "User Behavior"])
        
        with tabs[0]:
            self.display_chat_analytics()
        with tabs[1]:
            self.display_search_analytics()
        with tabs[2]:
            self.display_expert_analytics()
        with tabs[3]:
            self.display_user_behavior()

    def create_sidebar_filters(self):
        st.sidebar.title("Filters")
        
        # Date range selector
        self.start_date = st.sidebar.date_input(
            "Start Date",
            datetime.now() - timedelta(days=30)
        )
        self.end_date = st.sidebar.date_input(
            "End Date",
            datetime.now()
        )

        # Analytics type filter
        self.analytics_type = st.sidebar.multiselect(
            "Analytics Type",
            ["chat", "search", "expert matching"],
            default=["chat", "search", "expert matching"]
        )

    def get_chat_metrics(self) -> Dict[str, Any]:
        cursor = self.conn.cursor()
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
            """, (self.start_date, self.end_date, self.start_date, self.end_date))
            
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            return pd.DataFrame(data, columns=columns)
        finally:
            cursor.close()

    def get_search_metrics(self) -> Dict[str, Any]:
        cursor = self.conn.cursor()
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
            """, (self.start_date, self.end_date))
            
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            return pd.DataFrame(data, columns=columns)
        finally:
            cursor.close()

    def get_expert_metrics(self) -> pd.DataFrame:
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                WITH ChatExperts AS (
                    SELECT 
                        a.expert_id,
                        COUNT(*) as chat_matches,
                        AVG(a.similarity_score) as chat_similarity,
                        SUM(CASE WHEN a.clicked THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as chat_click_rate
                    FROM chat_analytics a
                    JOIN chat_interactions i ON a.interaction_id = i.id
                    WHERE i.timestamp BETWEEN %s AND %s
                    GROUP BY a.expert_id
                ),
                SearchExperts AS (
                    SELECT 
                        expert_id,
                        COUNT(*) as search_matches,
                        AVG(rank_position) as avg_rank,
                        SUM(CASE WHEN clicked THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as search_click_rate
                    FROM expert_searches
                    JOIN search_logs sl ON expert_searches.search_id = sl.id
                    WHERE sl.timestamp BETWEEN %s AND %s
                    GROUP BY expert_id
                )
                SELECT 
                    e.firstname || ' ' || e.lastname as expert_name,
                    e.unit,
                    COALESCE(ce.chat_matches, 0) as chat_matches,
                    COALESCE(ce.chat_similarity, 0) as chat_similarity,
                    COALESCE(ce.chat_click_rate, 0) as chat_click_rate,
                    COALESCE(se.search_matches, 0) as search_matches,
                    COALESCE(se.avg_rank, 0) as search_avg_rank,
                    COALESCE(se.search_click_rate, 0) as search_click_rate
                FROM experts_expert e
                LEFT JOIN ChatExperts ce ON e.id::text = ce.expert_id
                LEFT JOIN SearchExperts se ON e.id::text = se.expert_id
                WHERE e.is_active = true
                ORDER BY (COALESCE(ce.chat_matches, 0) + COALESCE(se.search_matches, 0)) DESC
            """, (self.start_date, self.end_date, self.start_date, self.end_date))
            
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            return pd.DataFrame(data, columns=columns)
        finally:
            cursor.close()

    def display_overall_metrics(self):
        col1, col2, col3, col4 = st.columns(4)
        
        # Get overall metrics
        cursor = self.conn.cursor()
        try:
            # Combined chat and search metrics
            cursor.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM chat_interactions 
                     WHERE timestamp BETWEEN %s AND %s) as total_chat_interactions,
                    (SELECT COUNT(*) FROM search_logs 
                     WHERE timestamp BETWEEN %s AND %s) as total_searches,
                    (SELECT COUNT(DISTINCT user_id) FROM (
                        SELECT user_id FROM chat_interactions 
                        WHERE timestamp BETWEEN %s AND %s
                        UNION
                        SELECT user_id FROM search_logs 
                        WHERE timestamp BETWEEN %s AND %s
                    ) u) as unique_users,
                    (SELECT COUNT(*) FROM chat_analytics 
                     WHERE clicked = true) +
                    (SELECT COUNT(*) FROM expert_searches 
                     WHERE clicked = true) as total_expert_clicks
            """, (self.start_date, self.end_date) * 4)
            
            metrics = cursor.fetchone()
            
            with col1:
                st.metric("Total Interactions", f"{metrics[0] + metrics[1]:,}")
            with col2:
                st.metric("Chat Interactions", f"{metrics[0]:,}")
            with col3:
                st.metric("Unique Users", f"{metrics[2]:,}")
            with col4:
                st.metric("Expert Clicks", f"{metrics[3]:,}")
                
        finally:
            cursor.close()

    def display_chat_analytics(self):
        st.subheader("Chat Analytics")
        
        # Get chat metrics
        chat_metrics = self.get_chat_metrics()
        
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

    def display_search_analytics(self):
        st.subheader("Search Analytics")
        
        # Get search metrics
        search_metrics = self.get_search_metrics()
        
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

    def display_expert_analytics(self):
        st.subheader("Expert Analytics")
        
        # Get expert metrics
        expert_metrics = self.get_expert_metrics()
        
        # Expert performance heatmap
        fig = go.Figure(data=go.Heatmap(
            z=[
                expert_metrics.chat_similarity,
                expert_metrics.chat_click_rate,
                expert_metrics.search_click_rate
            ],
            x=expert_metrics.expert_name,
            y=['Similarity Score', 'Chat CTR', 'Search CTR'],
            colorscale='Viridis'
        ))
        fig.update_layout(title='Expert Performance Matrix')
        st.plotly_chart(fig)
        
        # Expert metrics table
        st.dataframe(
            expert_metrics[[
                'expert_name', 'unit', 'chat_matches', 'search_matches',
                'chat_click_rate', 'search_click_rate'
            ]].sort_values('chat_matches', ascending=False)
        )

    def display_user_behavior(self):
        st.subheader("User Behavior Analytics")
        
        # Get user behavior metrics
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                WITH UserMetrics AS (
                    SELECT 
                        user_id,
                        COUNT(*) as total_interactions,
                        COUNT(DISTINCT session_id) as total_sessions,
                        AVG(EXTRACT(EPOCH FROM (
                            SELECT MAX(timestamp) - MIN(timestamp) 
                            FROM chat_interactions ci2 
                            WHERE ci2.session_id = ci1.session_id
                        ))) as avg_session_duration
                    FROM chat_interactions ci1
                    WHERE timestamp BETWEEN %s AND %s
                    GROUP BY user_id
                )
                SELECT 
                    CASE 
                        WHEN total_interactions <= 5 THEN 'Low'
                        WHEN total_interactions <= 15 THEN 'Medium'
                        ELSE 'High'
                    END as engagement_level,
                    COUNT(*) as user_count,
                    AVG(total_sessions) as avg_sessions,
                    AVG(avg_session_duration) as avg_duration
                FROM UserMetrics
                GROUP BY 
                    CASE 
                        WHEN total_interactions <= 5 THEN 'Low'
                        WHEN total_interactions <= 15 THEN 'Medium'
                        ELSE 'High'
                    END
            """, (self.start_date, self.end_date))
            
            columns = [desc[0] for desc in cursor.description]
            behavior_data = pd.DataFrame(cursor.fetchall(), columns=columns)
            
            # User engagement distribution
            st.plotly_chart(
                px.bar(
                    behavior_data,
                    x='engagement_level',
                    y='user_count',
                    title='User Engagement Distribution'
                )
            )
            
            # Session metrics
            col1, col2 = st.columns(2)
            with col1:
                st.plotly_chart(
                    px.bar(
                        behavior_data,
                        x='engagement_level',
                        y='avg_sessions',
                        title='Average Sessions per User'
                    )
                )
            with col2:
                st.plotly_chart(
                    px.bar(
                        behavior_data,
                        x='engagement_level',
                        y='avg_duration',
                        title='Average Session Duration (seconds)'
                    )
                )
            
        finally:
            cursor.close()

if __name__ == "__main__":
    dashboard = UnifiedAnalyticsDashboard()
    dashboard.main()
