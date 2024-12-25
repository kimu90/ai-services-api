# pages/overview.py
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from .base_page import BasePage

class OverviewPage(BasePage):
    def render(self):
        st.title("Overview Dashboard")
        
        # Get overall metrics
        metrics = self._get_overall_metrics()
        
        # Display metric cards
        metrics_data = [
            ("Total Interactions", f"{metrics[0] + metrics[1]:,}", None),
            ("Chat Interactions", f"{metrics[0]:,}", None),
            ("Unique Users", f"{metrics[2]:,}", None),
            ("Expert Clicks", f"{metrics[3]:,}", None)
        ]
        self.create_metric_cards(metrics_data)
        
        # Display main charts
        self._render_main_charts()
        
        # Display engagement metrics
        self._render_engagement_metrics()
    
    def _get_overall_metrics(self):
        cursor = self.conn.cursor()
        try:
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
            """, (self.date_range['start'], self.date_range['end']) * 4)
            
            return cursor.fetchone()
        finally:
            cursor.close()
    
    def _render_main_charts(self):
        col1, col2 = st.columns(2)
        
        with col1:
            chat_trend = self._get_chat_trend()
            fig = px.line(
                chat_trend,
                x="date",
                y=["total_interactions", "unique_users"],
                title="Daily Chat Volume"
            )
            self.create_plotly_chart(fig)
        
        with col2:
            search_trend = self._get_search_trend()
            fig = px.line(
                search_trend,
                x="date",
                y=["total_searches", "unique_users"],
                title="Daily Search Volume"
            )
            self.create_plotly_chart(fig)
    
    def _render_engagement_metrics(self):
        st.subheader("User Engagement")
        engagement_data = self._get_engagement_metrics()
        
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(
                engagement_data,
                x="category",
                y="value",
                title="Engagement by Category"
            )
            self.create_plotly_chart(fig)
        
        with col2:
            # Add engagement trends or other relevant metrics
            pass
    
    def _get_chat_trend(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    DATE(timestamp) as date,
                    COUNT(*) as total_interactions,
                    COUNT(DISTINCT user_id) as unique_users
                FROM chat_interactions
                WHERE timestamp BETWEEN %s AND %s
                GROUP BY DATE(timestamp)
                ORDER BY date
            """, (self.date_range['start'], self.date_range['end']))
            
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
        finally:
            cursor.close()
    
    def _get_search_trend(self):
        # Similar implementation for search trends
        pass
    
    def _get_engagement_metrics(self):
        # Implementation for engagement metrics
        pass
