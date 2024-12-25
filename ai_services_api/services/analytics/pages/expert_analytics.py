# pages/expert_analytics.py
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from .base_page import BasePage

class ExpertAnalyticsPage(BasePage):
    def render(self):
        st.title("Expert Analytics")
        
        # Get expert metrics
        expert_metrics = self._get_expert_metrics()
        
        # Display overview metrics
        self._display_overview(expert_metrics)
        
        # Display detailed analytics
        col1, col2 = st.columns(2)
        with col1:
            self._display_performance_matrix(expert_metrics)
        with col2:
            self._display_engagement_trends(expert_metrics)
        
        # Display recommendation network
        self._display_recommendation_network()
    
    def _get_expert_metrics(self):
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
                        SUM(CASE WHEN expert_searches.clicked THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as search_click_rate
                    FROM expert_searches
                    JOIN search_logs sl ON expert_searches.search_id = sl.id
                    WHERE sl.timestamp BETWEEN %s AND %s
                    GROUP BY expert_id
                )
                SELECT 
                    e.id,
                    e.first_name || ' ' || e.last_name as expert_name,
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
            """, (self.date_range['start'], self.date_range['end']) * 2)
            
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
        finally:
            cursor.close()
    
    def _display_overview(self, expert_metrics):
        total_interactions = expert_metrics['chat_matches'].sum() + expert_metrics['search_matches'].sum()
        avg_similarity = expert_metrics['chat_similarity'].mean()
        avg_click_rate = (expert_metrics['chat_click_rate'] + expert_metrics['search_click_rate']).mean() / 2
        
        metrics_data = [
            ("Total Interactions", f"{total_interactions:,}", None),
            ("Average Similarity", f"{avg_similarity:.2%}", None),
            ("Average Click Rate", f"{avg_click_rate:.2%}", None),
            ("Active Experts", f"{len(expert_metrics)}", None)
        ]
        self.create_metric_cards(metrics_data)
    
    def _display_performance_matrix(self, expert_metrics):
        fig = go.Figure(data=go.Heatmap(
            z=[
                expert_metrics['chat_similarity'],
                expert_metrics['chat_click_rate'],
                expert_metrics['search_click_rate']
            ],
            x=expert_metrics['expert_name'],
            y=['Similarity Score', 'Chat CTR', 'Search CTR'],
            colorscale='Viridis'
        ))
        fig.update_layout(title='Expert Performance Matrix')
        self.create_plotly_chart(fig)
    
    def _display_engagement_trends(self, expert_metrics):
        fig = px.scatter(
            expert_metrics,
            x='chat_matches',
            y='search_matches',
            size='chat_similarity',
            color='unit',
            hover_data=['expert_name'],
            title='Expert Engagement Distribution'
        )
        self.create_plotly_chart(fig)
    
    def _display_recommendation_network(self):
        st.subheader("Expert Recommendation Network")
        # Implementation of network visualization...

# pages/content_analytics.py
class ContentAnalyticsPage(BasePage):
    def render(self):
        st.title("Content Analytics")
        # Implementation...

# pages/user_engagement.py
class UserEngagementPage(BasePage):
    def render(self):
        st.title("User Engagement Analytics")
        # Implementation...

# pages/ai_insights.py
class AIInsightsPage(BasePage):
    def render(self):
        st.title("AI-Driven Insights")
        # Implementation...
