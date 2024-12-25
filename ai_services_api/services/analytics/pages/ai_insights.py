# pages/ai_insights.py
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from .base_page import BasePage
from config.settings import ANALYTICS_SETTINGS, EXPERT_MATCHING

class AIInsightsPage(BasePage):
    def render(self):
        st.title("AI-Driven Insights")
        
        # Add filters
        self._add_filters()
        
        # Display AI summary
        self._display_ai_summary()
        
        # Main analysis sections
        col1, col2 = st.columns(2)
        
        with col1:
            self._display_trending_analysis()
            self._display_expert_recommendations()
        
        with col2:
            self._display_sentiment_analysis()
            self._display_content_gaps()
        
        # Display predictive insights
        self._display_predictive_insights()
        
        # Display optimization recommendations
        self._display_optimization_recommendations()

    def _add_filters(self):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            self.analysis_type = st.selectbox(
                "Analysis Type",
                options=["All", "Content", "User Behavior", "Expert Matching"]
            )
        
        with col2:
            self.confidence_threshold = st.slider(
                "Confidence Threshold",
                min_value=0.0,
                max_value=1.0,
                value=0.7
            )
        
        with col3:
            self.insight_count = st.number_input(
                "Number of Insights",
                min_value=5,
                max_value=50,
                value=10
            )

    def _get_ai_metrics(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                WITH TrendMetrics AS (
                    SELECT 
                        COUNT(*) as total_trends,
                        AVG(confidence_score) as avg_confidence,
                        SUM(CASE WHEN sentiment_score > 0.6 THEN 1 ELSE 0 END) as positive_trends,
                        SUM(CASE WHEN sentiment_score < 0.4 THEN 1 ELSE 0 END) as negative_trends
                    FROM ai_trends
                    WHERE detection_date BETWEEN %s AND %s
                    AND confidence_score >= %s
                ),
                RecommendationMetrics AS (
                    SELECT 
                        COUNT(*) as total_recommendations,
                        AVG(success_rate) as avg_success_rate
                    FROM ai_recommendations
                    WHERE generation_date BETWEEN %s AND %s
                    AND confidence_score >= %s
                ),
                PredictionMetrics AS (
                    SELECT 
                        AVG(accuracy_score) as avg_accuracy,
                        COUNT(*) as total_predictions
                    FROM ai_predictions
                    WHERE prediction_date BETWEEN %s AND %s
                    AND confidence_score >= %s
                )
                SELECT 
                    tm.*,
                    rm.*,
                    pm.*
                FROM TrendMetrics tm, RecommendationMetrics rm, PredictionMetrics pm
            """, (
                self.date_range['start'], self.date_range['end'], self.confidence_threshold,
                self.date_range['start'], self.date_range['end'], self.confidence_threshold,
                self.date_range['start'], self.date_range['end'], self.confidence_threshold
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
                        t.topic_name,
                        t.confidence_score,
                        t.sentiment_score,
                        t.growth_rate,
                        t.user_engagement,
                        t.expert_coverage,
                        ROW_NUMBER() OVER (
                            PARTITION BY t.topic_name 
                            ORDER BY t.detection_date DESC
                        ) as rn
                    FROM ai_trends t
                    WHERE t.detection_date BETWEEN %s AND %s
                    AND t.confidence_score >= %s
                )
                SELECT 
                    topic_name,
                    confidence_score,
                    sentiment_score,
                    growth_rate,
                    user_engagement,
                    expert_coverage
                FROM TopicTrends
                WHERE rn = 1
                ORDER BY growth_rate DESC
                LIMIT %s
            """, (
                self.date_range['start'],
                self.date_range['end'],
                self.confidence_threshold,
                self.insight_count
            ))
            
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
        finally:
            cursor.close()

    def _get_sentiment_trends(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    DATE_TRUNC('day', timestamp) as date,
                    AVG(sentiment_score) as avg_sentiment,
                    AVG(satisfaction_score) as avg_satisfaction,
                    STRING_AGG(DISTINCT primary_emotion, ', ') as emotions,
                    COUNT(*) as interaction_count
                FROM ai_sentiment_analysis
                WHERE timestamp BETWEEN %s AND %s
                AND confidence_score >= %s
                GROUP BY DATE_TRUNC('day', timestamp)
                ORDER BY date
            """, (
                self.date_range['start'],
                self.date_range['end'],
                self.confidence_threshold
            ))
            
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
        finally:
            cursor.close()

    def _get_expert_recommendations(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                WITH ExpertGaps AS (
                    SELECT 
                        topic_area,
                        current_coverage,
                        recommended_coverage,
                        confidence_score,
                        priority_score,
                        ROW_NUMBER() OVER (
                            PARTITION BY topic_area 
                            ORDER BY priority_score DESC
                        ) as rn
                    FROM ai_expert_recommendations
                    WHERE generation_date BETWEEN %s AND %s
                    AND confidence_score >= %s
                )
                SELECT 
                    topic_area,
                    current_coverage,
                    recommended_coverage,
                    confidence_score,
                    priority_score
                FROM ExpertGaps
                WHERE rn = 1
                ORDER BY priority_score DESC
                LIMIT %s
            """, (
                self.date_range['start'],
                self.date_range['end'],
                self.confidence_threshold,
                self.insight_count
            ))
            
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
        finally:
            cursor.close()

    def _get_content_gaps(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    content_area,
                    current_coverage,
                    demand_score,
                    gap_score,
                    confidence_score,
                    recommended_actions,
                    priority_level
                FROM ai_content_gaps
                WHERE detection_date BETWEEN %s AND %s
                AND confidence_score >= %s
                ORDER BY gap_score DESC
                LIMIT %s
            """, (
                self.date_range['start'],
                self.date_range['end'],
                self.confidence_threshold,
                self.insight_count
            ))
            
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
        finally:
            cursor.close()

    def _display_ai_summary(self):
        metrics = self._get_ai_metrics()
        
        # Display metrics cards
        metrics_data = [
            ("AI Insights Generated", f"{metrics['total_trends']:,}", 
             f"Avg. Confidence: {metrics['avg_confidence']:.1%}"),
            ("Successful Recommendations", f"{metrics['avg_success_rate']:.1%}", 
             f"Total: {metrics['total_recommendations']:,}"),
            ("Prediction Accuracy", f"{metrics['avg_accuracy']:.1%}", 
             f"Total: {metrics['total_predictions']:,}"),
            ("Trend Sentiment", f"+{metrics['positive_trends']} / -{metrics['negative_trends']}", None)
        ]
        self.create_metric_cards(metrics_data)

    def _display_trending_analysis(self):
        st.subheader("Trending Topics Analysis")
        
        trend_data = self._get_trending_topics()
        
        # Create bubble chart
        fig = px.scatter(
            trend_data,
            x='growth_rate',
            y='user_engagement',
            size='confidence_score',
            color='sentiment_score',
            hover_name='topic_name',
            title='Topic Growth vs Engagement',
            labels={
                'growth_rate': 'Growth Rate (%)',
                'user_engagement': 'User Engagement',
                'confidence_score': 'Confidence',
                'sentiment_score': 'Sentiment'
            }
        )
        self.create_plotly_chart(fig)
        
        # Display trending topics table
        with st.expander("View Detailed Topic Analysis"):
            st.dataframe(
                trend_data.style.format({
                    'confidence_score': '{:.1%}',
                    'sentiment_score': '{:.2f}',
                    'growth_rate': '{:.1%}',
                    'user_engagement': '{:.2f}',
                    'expert_coverage': '{:.1%}'
                }),
                use_container_width=True
            )

    def _display_sentiment_analysis(self):
        st.subheader("Sentiment Analysis")
        
        sentiment_data = self._get_sentiment_trends()
        
        # Create sentiment trend chart
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=sentiment_data['date'],
            y=sentiment_data['avg_sentiment'],
            name='Sentiment',
            line=dict(color='blue')
        ))
        
        fig.add_trace(go.Scatter(
            x=sentiment_data['date'],
            y=sentiment_data['avg_satisfaction'],
            name='Satisfaction',
            line=dict(color='green')
        ))
        
        fig.update_layout(
            title='Sentiment and Satisfaction Trends',
            xaxis_title='Date',
            yaxis_title='Score'
        )
        self.create_plotly_chart(fig)
        
        # Display emotion breakdown
        emotions_data = sentiment_data['emotions'].str.split(', ', expand=True).stack().value_counts()
        
        fig = px.pie(
            values=emotions_data.values,
            names=emotions_data.index,
            title='Emotion Distribution'
        )
        self.create_plotly_chart(fig)

    def _display_expert_recommendations(self):
        st.subheader("Expert Coverage Analysis")
        
        expert_data = self._get_expert_recommendations()
        
        # Create coverage gap chart
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            name='Current Coverage',
            x=expert_data['topic_area'],
            y=expert_data['current_coverage'],
            marker_color='blue'
        ))
        
        fig.add_trace(go.Bar(
            name='Recommended Coverage',
            x=expert_data['topic_area'],
            y=expert_data['recommended_coverage'],
            marker_color='red'
        ))
        
        fig.update_layout(
            title='Expert Coverage Analysis',
            barmode='group'
        )
        self.create_plotly_chart(fig)
        
        # Display recommendations
        with st.expander("View Expert Recommendations"):
            st.dataframe(expert_data, use_container_width=True)

    def _display_content_gaps(self):
        st.subheader("Content Gap Analysis")
        
        gap_data = self._get_content_gaps()
        
        # Create gap analysis chart
        fig = px.scatter(
            gap_data,
            x='current_coverage',
            y='demand_score',
            size='gap_score',
            color='priority_level',
            hover_name='content_area',
            title='Content Demand vs Coverage'
        )
        self.create_plotly_chart(fig)
        
        # Display gap analysis table
        with st.expander("View Content Gap Details"):
            st.dataframe(
                gap_data.style.format({
                    'current_coverage': '{:.1%}',
                    'demand_score': '{:.2f}',
                    'gap_score': '{:.2f}',
                    'confidence_score': '{:.1%}'
                }),
                use_container_width=True
            )

    def _display_predictive_insights(self):
        st.subheader("Predictive Insights")
        
        # Get predicted trends
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    prediction_type,
                    prediction_target,
                    prediction_value,
                    confidence_score,
                    supporting_factors,
                    prediction_date
                FROM ai_predictions
                WHERE prediction_date BETWEEN %s AND %s
                AND confidence_score >= %s
                ORDER BY confidence_score DESC
                LIMIT %s
            """, (
                self.date_range['start'],
                self.date_range['end'],
                self.confidence_threshold,
                self.insight_count
            ))
            
            predictions = cursor.fetchall()
            
            # Display predictions in an expandable card
            for pred_type, target, value, confidence, factors, date in predictions:
                with st.expander(f"Prediction: {pred_type} - {target}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Predicted Value", value)
                        st.metric("Confidence Score", f"{confidence:.1%}")
                    with col2:
                        st.write("Supporting Factors:")
                        for factor in factors.split(';'):
                            st.write(f"• {factor.strip()}")
                    st.write(f"Prediction Date: {date}")
        finally:
            cursor.close()

    # Continuing the AIInsightsPage class...

    def _display_optimization_recommendations(self):
        st.subheader("Optimization Recommendations")
        
        # Get optimization recommendations
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    recommendation_area,
                    current_metric,
                    target_metric,
                    improvement_potential,
                    priority_score,
                    recommended_actions,
                    implementation_difficulty,
                    expected_impact,
                    confidence_score
                FROM ai_optimization_recommendations
                WHERE generation_date BETWEEN %s AND %s
                AND confidence_score >= %s
                ORDER BY priority_score DESC
                LIMIT %s
            """, (
                self.date_range['start'],
                self.date_range['end'],
                self.confidence_threshold,
                self.insight_count
            ))
            
            columns = [desc[0] for desc in cursor.description]
            recommendations = pd.DataFrame(cursor.fetchall(), columns=columns)
            
            # Create priority matrix visualization
            fig = px.scatter(
                recommendations,
                x='implementation_difficulty',
                y='expected_impact',
                size='improvement_potential',
                color='priority_score',
                hover_name='recommendation_area',
                title='Optimization Priority Matrix',
                labels={
                    'implementation_difficulty': 'Implementation Difficulty',
                    'expected_impact': 'Expected Impact',
                    'improvement_potential': 'Improvement Potential',
                    'priority_score': 'Priority Score'
                }
            )
            self.create_plotly_chart(fig)
            
            # Display recommendations in expandable cards
            for _, row in recommendations.iterrows():
                with st.expander(f"📊 {row['recommendation_area']} (Priority: {row['priority_score']:.2f})"):
                    # Create three columns for metrics
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric(
                            "Current Metric",
                            f"{row['current_metric']:.2f}",
                            f"Target: {row['target_metric']:.2f}"
                        )
                    
                    with col2:
                        st.metric(
                            "Improvement Potential",
                            f"{row['improvement_potential']:.1%}",
                            f"Impact: {row['expected_impact']:.1%}"
                        )
                    
                    with col3:
                        st.metric(
                            "Confidence Score",
                            f"{row['confidence_score']:.1%}",
                            f"Difficulty: {row['implementation_difficulty']}/10"
                        )
                    
                    # Display recommended actions
                    st.subheader("Recommended Actions")
                    actions = row['recommended_actions'].split(';')
                    for i, action in enumerate(actions, 1):
                        st.write(f"{i}. {action.strip()}")
                    
                    # Create implementation timeline
                    st.subheader("Implementation Timeline")
                    timeline_data = self._generate_implementation_timeline(row)
                    fig = px.timeline(
                        timeline_data,
                        x_start='start_date',
                        x_end='end_date',
                        y='task',
                        color='phase',
                        title='Suggested Implementation Timeline'
                    )
                    self.create_plotly_chart(fig)
                    
                    # Add expected outcomes
                    st.subheader("Expected Outcomes")
                    outcomes = [
                        f"• {row['improvement_potential']:.1%} improvement in {row['recommendation_area']}",
                        f"• ROI potential: {row['expected_impact']:.1%}",
                        f"• Implementation timeframe: {self._calculate_timeframe(row['implementation_difficulty'])} weeks"
                    ]
                    for outcome in outcomes:
                        st.write(outcome)
        finally:
            cursor.close()
    
    def _generate_implementation_timeline(self, recommendation):
        """Generate implementation timeline based on recommendation difficulty"""
        today = datetime.now()
        difficulty = recommendation['implementation_difficulty']
        
        # Calculate phase durations based on difficulty
        planning_duration = timedelta(days=max(7, difficulty * 2))
        implementation_duration = timedelta(days=max(14, difficulty * 5))
        review_duration = timedelta(days=max(7, difficulty * 1))
        
        timeline_data = {
            'task': [],
            'start_date': [],
            'end_date': [],
            'phase': []
        }
        
        # Planning phase
        timeline_data['task'].append('Planning & Preparation')
        timeline_data['start_date'].append(today)
        timeline_data['end_date'].append(today + planning_duration)
        timeline_data['phase'].append('Planning')
        
        # Implementation phase
        impl_start = today + planning_duration
        timeline_data['task'].append('Implementation')
        timeline_data['start_date'].append(impl_start)
        timeline_data['end_date'].append(impl_start + implementation_duration)
        timeline_data['phase'].append('Implementation')
        
        # Review phase
        review_start = impl_start + implementation_duration
        timeline_data['task'].append('Review & Optimization')
        timeline_data['start_date'].append(review_start)
        timeline_data['end_date'].append(review_start + review_duration)
        timeline_data['phase'].append('Review')
        
        return pd.DataFrame(timeline_data)
    
    def _calculate_timeframe(self, difficulty):
        """Calculate implementation timeframe in weeks based on difficulty"""
        base_weeks = 2
        additional_weeks = difficulty // 2
        return base_weeks + additional_weeks
    
    def _get_historical_improvements(self):
        """Get historical improvement data for similar recommendations"""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    recommendation_area,
                    AVG(achieved_improvement) as avg_improvement,
                    AVG(implementation_time) as avg_implementation_time,
                    COUNT(*) as implementation_count
                FROM ai_recommendation_history
                WHERE implementation_date BETWEEN %s AND %s
                GROUP BY recommendation_area
                HAVING COUNT(*) >= 5
            """, (
                self.date_range['start'] - timedelta(days=365),
                self.date_range['end']
            ))
            
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
        finally:
            cursor.close()

if __name__ == "__main__":
    st.set_page_config(page_title="AI Insights", layout="wide")
    ai_page = AIInsightsPage()
    ai_page.render()
