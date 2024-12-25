# app.py
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from pages.overview import OverviewPage
from pages.expert_analytics import ExpertAnalyticsPage
from pages.content_analytics import ContentAnalyticsPage
from pages.user_engagement import UserEngagementPage
from pages.ai_insights import AIInsightsPage
from utils.theme_manager import ThemeManager
from utils.database import DatabaseConnector
from utils.logger import setup_logger
from config.settings import APP_SETTINGS, ANALYTICS_SETTINGS

logger = setup_logger(__name__)

class KnowledgePortalAnalytics:
    def __init__(self):
        """Initialize the Knowledge Portal Analytics dashboard."""
        self.setup_environment()
        self.db = DatabaseConnector()
        self.theme_manager = ThemeManager()
        self.initialize_session_state()
        self.load_static_files()
        
    def setup_environment(self):
        """Configure the Streamlit environment."""
        st.set_page_config(
            page_title="Knowledge Management Analytics",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded",
            menu_items={
                'Get Help': 'https://support.aphrc.org',
                'Report a bug': 'https://github.com/aphrc/knowledge-portal/issues',
                'About': """
                # Knowledge Management Analytics Dashboard
                Version 1.0.0
                
                This dashboard provides comprehensive analytics for the APHRC Knowledge Portal.
                """
            }
        )

    def initialize_session_state(self):
        """Initialize session state variables."""
        if 'theme' not in st.session_state:
            st.session_state.theme = 'light'
        
        if 'date_range' not in st.session_state:
            st.session_state.date_range = {
                'start': datetime.now() - timedelta(days=30),
                'end': datetime.now()
            }
        
        if 'filters' not in st.session_state:
            st.session_state.filters = {
                'content_types': [],
                'expert_areas': [],
                'departments': []
            }

    def load_static_files(self):
        """Load custom CSS and JavaScript files."""
        try:
            self.load_custom_css()
            self.load_custom_js()
        except Exception as e:
            logger.error(f"Error loading static files: {e}")
            st.error("Some styling elements could not be loaded.")

    def load_custom_css(self):
        """Load custom CSS styles."""
        css_path = Path('static/css/custom.css')
        if css_path.exists():
            with open(css_path) as f:
                st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
        else:
            logger.warning("Custom CSS file not found")

    def load_custom_js(self):
        """Load custom JavaScript."""
        js_path = Path('static/js/custom.js')
        if js_path.exists():
            with open(js_path) as f:
                st.markdown(f'<script>{f.read()}</script>', unsafe_allow_html=True)
        else:
            logger.warning("Custom JavaScript file not found")

    def create_sidebar(self):
        """Create and configure the sidebar."""
        with st.sidebar:
            st.title("Dashboard Controls")
            
            # Theme toggle
            theme_label = "🌙 Dark Mode" if st.session_state.theme == 'light' else "☀️ Light Mode"
            if st.button(theme_label):
                self.theme_manager.toggle_theme()
            
            st.divider()
            
            # Date range selection
            st.subheader("Date Range")
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input(
                    "Start Date",
                    st.session_state.date_range['start']
                )
            with col2:
                end_date = st.date_input(
                    "End Date",
                    st.session_state.date_range['end']
                )
            
            # Update session state
            if start_date and end_date:
                st.session_state.date_range = {
                    'start': start_date,
                    'end': end_date
                }
            
            st.divider()
            
            # Global filters
            st.subheader("Filters")
            
            # Content type filter
            content_types = self.get_content_types()
            selected_types = st.multiselect(
                "Content Types",
                options=content_types,
                default=content_types
            )
            st.session_state.filters['content_types'] = selected_types
            
            # Expert areas filter
            expert_areas = self.get_expert_areas()
            selected_areas = st.multiselect(
                "Expert Areas",
                options=expert_areas
            )
            st.session_state.filters['expert_areas'] = selected_areas
            
            # Department filter
            departments = self.get_departments()
            selected_depts = st.multiselect(
                "Departments",
                options=departments
            )
            st.session_state.filters['departments'] = selected_depts
            
            st.divider()
            
            # Page selection
            st.subheader("Navigation")
            selected_page = st.radio(
                "Select Page",
                ["Overview", "Expert Analytics", "Content Analytics", 
                 "User Engagement", "AI Insights"]
            )
            
            # Export options
            if st.button("Export Data"):
                self.export_data()
            
            # Help and documentation
            with st.expander("Help & Documentation"):
                st.markdown("""
                    ### Quick Links
                    - [User Guide](https://docs.example.com/guide)
                    - [API Documentation](https://docs.example.com/api)
                    - [Support Portal](https://support.example.com)
                    
                    ### Need Help?
                    Contact support at support@example.com
                """)
            
            return selected_page

    def get_content_types(self):
        """Fetch available content types from database."""
        cursor = self.db.get_connection().cursor()
        try:
            cursor.execute("""
                SELECT DISTINCT content_type 
                FROM content 
                WHERE is_active = true
                ORDER BY content_type
            """)
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()

    def get_expert_areas(self):
        """Fetch available expert areas from database."""
        cursor = self.db.get_connection().cursor()
        try:
            cursor.execute("""
                SELECT DISTINCT area_name 
                FROM expert_areas 
                WHERE is_active = true
                ORDER BY area_name
            """)
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()

    def get_departments(self):
        """Fetch available departments from database."""
        cursor = self.db.get_connection().cursor()
        try:
            cursor.execute("""
                SELECT DISTINCT department_name 
                FROM departments 
                WHERE is_active = true
                ORDER BY department_name
            """)
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()

    def export_data(self):
        """Export dashboard data."""
        try:
            data = self.gather_export_data()
            
            # Create download button
            st.download_button(
                label="Download Data (CSV)",
                data=data.to_csv(index=False),
                file_name=f"dashboard_export_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        except Exception as e:
            logger.error(f"Export error: {e}")
            st.error("Failed to export data. Please try again.")

    def gather_export_data(self):
        """Gather data for export."""
        # Implement data gathering logic
        pass

    def main(self):
        """Main application entry point."""
        try:
            # Create sidebar and get selected page
            selected_page = self.create_sidebar()
            
            # Initialize pages
            pages = {
                "Overview": OverviewPage,
                "Expert Analytics": ExpertAnalyticsPage,
                "Content Analytics": ContentAnalyticsPage,
                "User Engagement": UserEngagementPage,
                "AI Insights": AIInsightsPage
            }
            
            # Render selected page
            page_instance = pages[selected_page](
                self.db,
                self.theme_manager,
                st.session_state.date_range,
                st.session_state.filters
            )
            page_instance.render()
            
        except Exception as e:
            logger.error(f"Application error: {e}")
            st.error("""
                An error occurred while loading the dashboard. 
                Please refresh the page or contact support if the problem persists.
            """)
            
            if APP_SETTINGS['debug']:
                st.exception(e)

    def __del__(self):
        """Cleanup resources."""
        try:
            if hasattr(self, 'db'):
                self.db.close_connection()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

if __name__ == "__main__":
    try:
        app = KnowledgePortalAnalytics()
        app.main()
    except Exception as e:
        logger.critical(f"Fatal application error: {e}")
        st.error("""
            The application encountered a critical error and cannot continue.
            Please contact support for assistance.
        """)
        if APP_SETTINGS['debug']:
            st.exception(e)
