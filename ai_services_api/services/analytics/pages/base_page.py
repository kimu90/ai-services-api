# pages/base_page.py
import streamlit as st
from abc import ABC, abstractmethod

class BasePage(ABC):
    def __init__(self, db, theme_manager, date_range):
        self.db = db
        self.theme_manager = theme_manager
        self.date_range = date_range
        self.conn = self.db.get_connection()
    
    @abstractmethod
    def render(self):
        """Render the page content"""
        pass
    
    def create_metric_cards(self, metrics_data, columns=4):
        """Helper method to create metric cards"""
        cols = st.columns(columns)
        for i, (label, value, delta) in enumerate(metrics_data):
            with cols[i % columns]:
                st.metric(label, value, delta)
    
    def create_plotly_chart(self, fig, use_container_width=True):
        """Helper method to create themed plotly charts"""
        fig = self.theme_manager.update_plot_theme(fig)
        st.plotly_chart(fig, use_container_width=use_container_width)
    
    def format_number(self, number, decimal_places=0):
        """Helper method to format numbers"""
        return f"{number:,.{decimal_places}f}"
