# dashboard/pages/search_analytics.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from ai_services_api.services.search.dashboard.components.charts import create_time_series_chart
from ai_services_api.services.search.dashboard.components.metrics import display_key_metrics

def render_search_analytics(data_processor, metrics_calculator):
    st.title("Search Analytics")
    
    # Date filters
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            datetime.now() - timedelta(days=30)
        )
    with col2:
        end_date = st.date_input(
            "End Date",
            datetime.now()
        )
    
    # Get metrics
    metrics = metrics_calculator.get_search_metrics(
        start_date=start_date,
        end_date=end_date,
        search_types=["general", "expert"]
    )
    
    # Display metrics
    display_key_metrics(metrics)
    
    # Time series analysis
    st.subheader("Search Volume Over Time")
    daily_metrics = data_processor.get_daily_search_metrics(
        start_date=start_date,
        end_date=end_date
    )
    st.plotly_chart(
        create_time_series_chart(daily_metrics, "Daily Search Volume")
    )

# dashboard/pages/expert_analytics.py
def render_expert_analytics(data_processor, metrics_calculator):
    st.title("Expert Search Analytics")
    
    # Date filters
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            datetime.now() - timedelta(days=30)
        )
    with col2:
        end_date = st.date_input(
            "End Date",
            datetime.now()
        )
    
    # Get expert metrics
    expert_data = metrics_calculator.get_expert_metrics(
        start_date=start_date,
        end_date=end_date
    )
    
    # Display expert performance
    st.subheader("Expert Performance")
    st.plotly_chart(
        create_heatmap(
            expert_data,
            "Expert Click-through Rate by Search Type"
        )
    )

# dashboard/pages/performance_metrics.py
def render_performance_metrics(data_processor, metrics_calculator):
    st.title("Performance Metrics")
    
    # Date filters
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            datetime.now() - timedelta(days=30)
        )
    with col2:
        end_date = st.date_input(
            "End Date",
            datetime.now()
        )
    
    # Get performance metrics
    performance_data = metrics_calculator.get_performance_metrics(
        start_date=start_date,
        end_date=end_date
    )
    
    # Display metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Avg Response Time",
            f"{performance_data['avg_response_time'].mean():.2f}s"
        )
    
    with col2:
        st.metric(
            "Cache Hit Rate",
            f"{performance_data['cache_hit_rate'].mean():.2%}"
        )
    
    with col3:
        st.metric(
            "Error Rate",
            f"{performance_data['error_rate'].mean():.2%}"
        )
    
    # Time series charts
    st.plotly_chart(
        create_time_series_chart(
            performance_data,
            "Response Time Trend",
            y_column="avg_response_time"
        )
    )

# dashboard/pages/user_behavior.py
def render_user_behavior(data_processor, metrics_calculator):
    st.title("User Search Behavior")
    
    # Date filters
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            datetime.now() - timedelta(days=30)
        )
    with col2:
        end_date = st.date_input(
            "End Date",
            datetime.now()
        )
    
    # Get user behavior metrics
    behavior_metrics = metrics_calculator.get_user_behavior_metrics(
        start_date=start_date,
        end_date=end_date
    )
    
    # Display metrics
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(
            "Avg Session Duration",
            f"{behavior_metrics['avg_session_duration']:.1f}s"
        )
    
    with col2:
        st.metric(
            "Avg Queries per Session",
            f"{behavior_metrics['avg_queries_per_session']:.1f}"
        )
    
    # Session analysis
    st.subheader("Session Analysis")
    session_data = behavior_metrics['session_data']
    st.plotly_chart(
        create_bar_chart(
            session_data,
            "Session Duration Distribution",
            "user_id",
            "duration"
        )
    )
