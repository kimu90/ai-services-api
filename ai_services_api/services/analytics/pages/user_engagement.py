# pages/user_engagement.py
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from .base_page import BasePage

class UserEngagementPage(BasePage):
    def render(self):
        st.title("User Engagement Analytics")
        
        # Add filters
        self._add_filters()
        
        # Display overview metrics
        self._display_overview_metrics()
        
        # Display engagement analysis
        col1, col2 = st.columns(2)
        
        with col1:
            self._display_session_metrics()
            self._display_user_segments()
        
        with col2:
            self._display_interaction_patterns()
            self._display_retention_metrics()
        
        # Display detailed user journey
        self._display_user_journey()
        
        # Display cohort analysis
        self._display_cohort_analysis()
    
    def _add_filters(self):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            self.user_segment = st.selectbox(
                "User Segment",
                options=["All Users", "New Users", "Returning Users", "Power Users"]
            )
        
        with col2:
            self.interaction_type = st.multiselect(
                "Interaction Types",
                options=["Search", "Chat", "Downloads", "Expert Engagement"],
                default=["Search", "Chat", "Downloads", "Expert Engagement"]
            )
        
        with col3:
            self.min_interactions = st.number_input(
                "Minimum Interactions",
                min_value=1,
                max_value=100,
                value=5
            )

    def _get_user_metrics(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                WITH UserMetrics AS (
                    SELECT 
                        u.id as user_id,
                        COUNT(DISTINCT s.id) as total_sessions,
                        COUNT(DISTINCT c.id) as chat_interactions,
                        COUNT(DISTINCT sr.id) as search_interactions,
                        COUNT(DISTINCT d.id) as downloads,
                        COUNT(DISTINCT e.id) as expert_engagements,
                        MAX(s.timestamp) - MIN(s.timestamp) as engagement_period,
                        CASE 
                            WHEN COUNT(*) > 50 THEN 'Power User'
                            WHEN COUNT(*) > 20 THEN 'Active User'
                            ELSE 'Regular User'
                        END as user_segment
                    FROM users u
                    LEFT JOIN sessions s ON u.id = s.user_id
                    LEFT JOIN chat_interactions c ON s.id = c.session_id
                    LEFT JOIN search_logs sr ON s.id = sr.session_id
                    LEFT JOIN content_downloads d ON s.id = d.session_id
                    LEFT JOIN expert_engagements e ON s.id = e.session_id
                    WHERE s.timestamp BETWEEN %s AND %s
                    GROUP BY u.id
                )
                SELECT 
                    user_segment,
                    COUNT(*) as user_count,
                    AVG(total_sessions) as avg_sessions,
                    AVG(chat_interactions) as avg_chats,
                    AVG(search_interactions) as avg_searches,
                    AVG(downloads) as avg_downloads,
                    AVG(expert_engagements) as avg_expert_engagements,
                    AVG(EXTRACT(EPOCH FROM engagement_period))/86400 as avg_engagement_days
                FROM UserMetrics
                GROUP BY user_segment
            """, (self.date_range['start'], self.date_range['end']))
            
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
        finally:
            cursor.close()

    def _display_overview_metrics(self):
        metrics = self._get_overview_metrics()
        
        metrics_data = [
            ("Active Users", f"{metrics['active_users']:,}", 
             f"{metrics['user_growth']}%"),
            ("Avg. Session Duration", f"{metrics['avg_session_duration']:.1f}m", 
             f"{metrics['session_growth']}%"),
            ("Engagement Rate", f"{metrics['engagement_rate']:.1%}", 
             f"{metrics['engagement_growth']}%"),
            ("Retention Rate", f"{metrics['retention_rate']:.1%}", 
             f"{metrics['retention_growth']}%")
        ]
        self.create_metric_cards(metrics_data)

    def _display_session_metrics(self):
        session_data = self._get_session_metrics()
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=session_data['date'],
            y=session_data['total_sessions'],
            name='Total Sessions',
            mode='lines'
        ))
        
        fig.add_trace(go.Scatter(
            x=session_data['date'],
            y=session_data['unique_users'],
            name='Unique Users',
            mode='lines'
        ))
        
        fig.update_layout(title='Session Metrics Over Time')
        self.create_plotly_chart(fig)

    def _display_user_segments(self):
        segment_data = self._get_user_segments()
        
        fig = px.sunburst(
            segment_data,
            path=['segment', 'interaction_type'],
            values='count',
            title='User Segments and Interactions'
        )
        self.create_plotly_chart(fig)

    def _display_interaction_patterns(self):
        pattern_data = self._get_interaction_patterns()
        
        fig = px.density_heatmap(
            pattern_data,
            x='hour',
            y='day_of_week',
            z='interaction_count',
            title='Interaction Patterns'
        )
        self.create_plotly_chart(fig)

    def _display_retention_metrics(self):
        retention_data = self._get_retention_metrics()
        
        fig = px.imshow(
            retention_data,
            title='User Retention Matrix',
            aspect='auto'
        )
        self.create_plotly_chart(fig)

    def _display_user_journey(self):
        st.subheader("User Journey Analysis")
        
        journey_data = self._get_user_journey()
        
        # Sankey diagram for user flow
        fig = go.Figure(data=[go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color="black", width=0.5),
                label=journey_data['nodes'],
                color="blue"
            ),
            link=dict(
                source=journey_data['source'],
                target=journey_data['target'],
                value=journey_data['value']
            )
        )])
        
        fig.update_layout(title='User Journey Flow')
        self.create_plotly_chart(fig)

    def _display_cohort_analysis(self):
        st.subheader("Cohort Analysis")
        
        cohort_data = self._get_cohort_data()
        
        fig = px.imshow(
            cohort_data,
            title='Cohort Retention Analysis',
            aspect='auto'
        )
        self.create_plotly_chart(fig)

    def _get_overview_metrics(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                WITH CurrentMetrics AS (
                    SELECT 
                        COUNT(DISTINCT user_id) as active_users,
                        AVG(EXTRACT(EPOCH FROM (end_time - start_time))/60) as avg_session_duration,
                        COUNT(DISTINCT CASE WHEN interaction_count >= 5 THEN user_id END)::float / 
                            NULLIF(COUNT(DISTINCT user_id), 0) as engagement_rate,
                        COUNT(DISTINCT CASE WHEN return_count >= 2 THEN user_id END)::float /
                            NULLIF(COUNT(DISTINCT user_id), 0) as retention_rate
                    FROM (
                        SELECT 
                            s.user_id,
                            s.start_time,
                            s.end_time,
                            COUNT(*) as interaction_count,
                            COUNT(DISTINCT DATE(s.start_time)) as return_count
                        FROM sessions s
                        WHERE s.start_time BETWEEN %s AND %s
                        GROUP BY s.user_id, s.start_time, s.end_time
                    ) user_stats
                ),
                PreviousMetrics AS (
                    -- Similar query for previous period
                )
                SELECT 
                    cm.*,
                    -- Calculate growth rates
                FROM CurrentMetrics cm, PreviousMetrics pm
            """, (self.date_range['start'], self.date_range['end']))
            
            return cursor.fetchone()
        finally:
            cursor.close()

    def _get_session_metrics(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    DATE_TRUNC('day', start_time) as date,
                    COUNT(*) as total_sessions,
                    COUNT(DISTINCT user_id) as unique_users,
                    AVG(EXTRACT(EPOCH FROM (end_time - start_time))/60) as avg_duration
                FROM sessions
                WHERE start_time BETWEEN %s AND %s
                GROUP BY DATE_TRUNC('day', start_time)
                ORDER BY date
            """, (self.date_range['start'], self.date_range['end']))
            
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
        finally:
            cursor.close()
