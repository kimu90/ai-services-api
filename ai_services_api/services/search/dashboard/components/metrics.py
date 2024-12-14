import streamlit as st
from typing import Dict
from typing import List, Dict, Any
def display_key_metrics(metrics: Dict[str, Any]):
    """Display key metrics in a streamlit dashboard"""
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Total Searches",
            f"{metrics['total_searches']:,}",
            delta=None
        )
        
    with col2:
        st.metric(
            "Unique Users",
            f"{metrics['unique_users']:,}",
            delta=None
        )
        
    with col3:
        st.metric(
            "Avg Response Time",
            f"{metrics['avg_response_time']:.2f}s",
            delta=None
        )
        
    col4, col5 = st.columns(2)
    
    with col4:
        st.metric(
            "Click-through Rate",
            f"{metrics['click_through_rate']:.2%}",
            delta=None
        )
        
    with col5:
        st.metric(
            "Success Rate",
            f"{metrics['avg_success_rate']:.2%}",
            delta=None
        )
