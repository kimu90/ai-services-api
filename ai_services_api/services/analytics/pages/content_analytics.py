# pages/content_analytics.py
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from .base_page import BasePage
from config.settings import CONTENT_TYPES, ANALYTICS_SETTINGS

class ContentAnalyticsPage(BasePage):
    def render(self):
        st.title("Content Analytics")
        
        # Add filters
        self._add_filters()
        
        # Display overview metrics
        self._display_overview_metrics()
        
        # Display main analysis sections
        col1, col2 = st.columns(2)
        
        with col1:
            self._display_content_distribution()
            self._display_trending_topics()
        
        with col2:
            self._display_engagement_metrics()
            self._display_download_trends()
        
        # Display detailed content performance
        self._display_content_performance()
        
        # Display geographical distribution
        self._display_geographical_distribution()
    
    def _add_filters(self):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            self.selected_content_types = st.multiselect(
                "Content Types",
                options=list(CONTENT_TYPES.values()),
                default=list(CONTENT_TYPES.values())
            )
        
        with col2:
            self.min_engagement = st.slider(
                "Minimum Engagement Score",
                0.0, 1.0, 0.2
            )
        
        with col3:
            self.top_n = st.number_input(
                "Top N Items",
                min_value=5,
                max_value=50,
                value=20
            )
    
    def _get_content_metrics(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                WITH ContentMetrics AS (
                    SELECT 
                        c.id,
                        c.title,
                        c.content_type,
                        c.publication_date,
                        COUNT(DISTINCT v.user_id) as unique_views,
                        COUNT(DISTINCT d.user_id) as unique_downloads,
                        COUNT(DISTINCT s.user_id) as unique_shares,
                        AVG(COALESCE(r.rating, 0)) as avg_rating,
                        COUNT(DISTINCT cm.citation_id) as citation_count
                    FROM content c
                    LEFT JOIN content_views v ON c.id = v.content_id 
                        AND v.view_date BETWEEN %s AND %s
                    LEFT JOIN content_downloads d ON c.id = d.content_id 
                        AND d.download_date BETWEEN %s AND %s
                    LEFT JOIN content_shares s ON c.id = s.content_id 
                        AND s.share_date BETWEEN %s AND %s
                    LEFT JOIN content_ratings r ON c.id = r.content_id 
                        AND r.rating_date BETWEEN %s AND %s
                    LEFT JOIN content_citations cm ON c.id = cm.content_id
                    WHERE c.content_type = ANY(%s)
                    GROUP BY c.id, c.title, c.content_type, c.publication_date
                ),
                ContentEngagement AS (
                    SELECT 
                        *,
                        (unique_views + unique_downloads * 2 + unique_shares * 3 + 
                         avg_rating * 10 + citation_count * 5) / 100.0 as engagement_score
                    FROM ContentMetrics
                )
                SELECT * FROM ContentEngagement
                WHERE engagement_score >= %s
                ORDER BY engagement_score DESC
                LIMIT %s
            """, (
                self.date_range['start'], self.date_range['end'],
                self.date_range['start'], self.date_range['end'],
                self.date_range['start'], self.date_range['end'],
                self.date_range['start'], self.date_range['end'],
                self.selected_content_types,
                self.min_engagement,
                self.top_n
            ))
            
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
        finally:
            cursor.close()
    
    def _get_overview_metrics(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                WITH CurrentPeriod AS (
                    SELECT 
                        COUNT(*) as total_content,
                        COUNT(*) FILTER (WHERE publication_date >= %s) as new_content,
                        SUM(view_count) as total_views,
                        AVG(rating) as avg_rating,
                        COUNT(DISTINCT citation_id) as total_citations
                    FROM content c
                    LEFT JOIN content_metrics cm ON c.id = cm.content_id
                    WHERE c.publication_date <= %s
                    AND c.content_type = ANY(%s)
                ),
                PreviousPeriod AS (
                    SELECT 
                        SUM(view_count) as prev_views,
                        AVG(rating) as prev_rating,
                        COUNT(DISTINCT citation_id) as prev_citations
                    FROM content c
                    LEFT JOIN content_metrics cm ON c.id = cm.content_id
                    WHERE c.publication_date BETWEEN 
                        %s - INTERVAL '1 month' AND %s
                    AND c.content_type = ANY(%s)
                )
                SELECT 
                    cp.*,
                    ((cp.total_views - pp.prev_views)::float / 
                     NULLIF(pp.prev_views, 0) * 100) as view_change,
                    ((cp.avg_rating - pp.prev_rating)::float / 
                     NULLIF(pp.prev_rating, 0) * 100) as rating_change,
                    ((cp.total_citations - pp.prev_citations)::float / 
                     NULLIF(pp.prev_citations, 0) * 100) as citation_change
                FROM CurrentPeriod cp, PreviousPeriod pp
            """, (
                self.date_range['start'],
                self.date_range['end'],
                self.selected_content_types,
                self.date_range['start'],
                self.date_range['end'],
                self.selected_content_types
            ))
            
            return cursor.fetchone()
        finally:
            cursor.close()
    
    def _get_trending_topics(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                WITH TopicTrends AS (
                    SELECT 
                        t.topic_name as topic,
                        COUNT(*) as current_count,
                        LAG(COUNT(*)) OVER (
                            PARTITION BY t.topic_name 
                            ORDER BY DATE_TRUNC('month', c.publication_date)
                        ) as previous_count
                    FROM content c
                    JOIN content_topics ct ON c.id = ct.content_id
                    JOIN topics t ON ct.topic_id = t.id
                    WHERE c.publication_date BETWEEN %s AND %s
                    AND c.content_type = ANY(%s)
                    GROUP BY t.topic_name, DATE_TRUNC('month', c.publication_date)
                )
                SELECT 
                    topic,
                    current_count as count,
                    COALESCE(
                        (current_count - previous_count)::float / 
                        NULLIF(previous_count, 0) * 100, 
                        0
                    ) as trend,
                    current_count * 1.0 / SUM(current_count) OVER () as score
                FROM TopicTrends
                ORDER BY score DESC
                LIMIT %s
            """, (
                self.date_range['start'],
                self.date_range['end'],
                self.selected_content_types,
                self.top_n
            ))
            
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
        finally:
            cursor.close()
    
    def _get_download_trends(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    DATE_TRUNC('day', d.download_date) as date,
                    c.content_type,
                    COUNT(*) as downloads
                FROM content_downloads d
                JOIN content c ON d.content_id = c.id 
                WHERE d.download_date BETWEEN %s AND %s
                AND c.content_type = ANY(%s)
                GROUP BY DATE_TRUNC('day', d.download_date), c.content_type
                ORDER BY date
            """, (
                self.date_range['start'],
                self.date_range['end'],
                self.selected_content_types
            ))
            
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
        finally:
            cursor.close()

    def _get_geographical_data(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    g.country_code,
                    g.country_name,
                    COUNT(DISTINCT v.user_id) as unique_viewers,
                    COUNT(DISTINCT d.user_id) as unique_downloaders,
                    AVG(COALESCE(r.rating, 0)) as avg_rating,
                    (COUNT(DISTINCT v.user_id) + 
                     COUNT(DISTINCT d.user_id) * 2 + 
                     AVG(COALESCE(r.rating, 0)) * 10) / 100.0 as engagement_score
                FROM geographical_data g
                LEFT JOIN content_views v 
                    ON g.id = v.geo_id 
                    AND v.view_date BETWEEN %s AND %s
                LEFT JOIN content_downloads d 
                    ON g.id = d.geo_id 
                    AND d.download_date BETWEEN %s AND %s
                LEFT JOIN content_ratings r 
                    ON g.id = r.geo_id 
                    AND r.rating_date BETWEEN %s AND %s
                JOIN content c ON v.content_id = c.id
                WHERE c.content_type = ANY(%s)
                GROUP BY g.country_code, g.country_name
            """, (
                self.date_range['start'], self.date_range['end'],
                self.date_range['start'], self.date_range['end'],
                self.date_range['start'], self.date_range['end'],
                self.selected_content_types
            ))
            
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
        finally:
            cursor.close()

    def _get_engagement_data(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    DATE_TRUNC('day', engagement_date) as date,
                    SUM(views) as views,
                    SUM(downloads) as downloads,
                    SUM(shares) as shares
                FROM (
                    SELECT 
                        date as engagement_date,
                        COUNT(*) as views,
                        0 as downloads,
                        0 as shares
                    FROM content_views cv
                    JOIN content c ON cv.content_id = c.id
                    WHERE date BETWEEN %s AND %s
                    AND c.content_type = ANY(%s)
                    GROUP BY date
                    UNION ALL
                    SELECT 
                        date,
                        0,
                        COUNT(*),
                        0
                    FROM content_downloads cd
                    JOIN content c ON cd.content_id = c.id
                    WHERE date BETWEEN %s AND %s
                    AND c.content_type = ANY(%s)
                    GROUP BY date
                    UNION ALL
                    SELECT 
                        date,
                        0,
                        0,
                        COUNT(*)
                    FROM content_shares cs
                    JOIN content c ON cs.content_id = c.id
                    WHERE date BETWEEN %s AND %s
                    AND c.content_type = ANY(%s)
                    GROUP BY date
                ) engagement
                GROUP BY DATE_TRUNC('day', engagement_date)
                ORDER BY date
            """, (
                self.date_range['start'], self.date_range['end'], self.selected_content_types,
                self.date_range['start'], self.date_range['end'], self.selected_content_types,
                self.date_range['start'], self.date_range['end'], self.selected_content_types
            ))
            
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
        finally:
            cursor.close()

    def _display_overview_metrics(self):
        metrics = self._get_overview_metrics()
        
        metrics_data = [
            ("Total Content", f"{metrics['total_content']:,}", 
             f"+{metrics['new_content']} new"),
            ("Total Views", f"{metrics['total_views']:,}", 
             f"{metrics['view_change']:.1f}%"),
            ("Avg. Rating", f"{metrics['avg_rating']:.2f}", 
             f"{metrics['rating_change']:.1f}%"),
            ("Citations", f"{metrics['total_citations']:,}", 
             f"{metrics['citation_change']:.1f}%")
        ]
        self.create_metric_cards(metrics_data)

    def _display_content_performance(self):
        st.subheader("Content Performance")
        
        performance_data = self._get_content_metrics()
        
        # Create performance table with formatted columns
        st.dataframe(
            performance_data[[
                'title', 'content_type', 'unique_views', 'unique_downloads',
                'avg_rating', 'citation_count', 'engagement_score'
            ]].style.format({
                'unique_views': '{:,.0f}',
                'unique_downloads': '{:,.0f}',
                'avg_rating': '{:.2f}',
                'citation_count': '{:,.0f}',
                'engagement_score': '{:.2f}'
            }),
            use_container_width=True
        )

    def _display_geographical_distribution(self):
        st.subheader("Geographical Distribution")
        
        geo_data = self._get_geographical_data()
        
        fig = px.choropleth(
            geo_data,
            locations='country_code',
            color='engagement_score',
            hover_name='country_name',
            hover_data=['unique_viewers', 'unique_downloaders', 'avg_rating'],
            color_continuous_scale=px.colors.sequential.Viridis,
            title='Global Content Engagement'
        )
        
        self.create_plotly_chart(fig)
        
        # Add detailed country breakdown
        with st.expander("View Detailed Country Breakdown"):
            st.dataframe(
                geo_data.sort_values('engagement_score', ascending=False),
                use_container_width=True
            )

if __name__ == "__main__":
    st.set_page_config(page_title="Content Analytics", layout="wide")
    content_page = ContentAnalyticsPage()
    content_page.render()
