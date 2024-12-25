# utils/theme_manager.py
import streamlit as st

class ThemeManager:
    def __init__(self):
        if 'theme' not in st.session_state:
            st.session_state.theme = 'light'
            
    def toggle_theme(self):
        st.session_state.theme = 'dark' if st.session_state.theme == 'light' else 'light'
        self.apply_theme()
    
    def apply_theme(self):
        if st.session_state.theme == 'dark':
            self._apply_dark_theme()
        else:
            self._apply_light_theme()
    
    def _apply_dark_theme(self):
        st.markdown("""
            <style>
                /* Dark theme styles */
                .stApp {
                    background-color: #0E1117;
                    color: #FAFAFA;
                }
                .css-1d391kg {
                    background-color: #262730;
                }
                /* Add more dark theme styles */
            </style>
        """, unsafe_allow_html=True)
    
    def _apply_light_theme(self):
        st.markdown("""
            <style>
                /* Light theme styles */
                .stApp {
                    background-color: #FFFFFF;
                    color: #000000;
                }
                /* Add more light theme styles */
            </style>
        """, unsafe_allow_html=True)
    
    def update_plot_theme(self, fig):
        theme_colors = {
            'dark': {
                'paper_bgcolor': '#262730',
                'plot_bgcolor': '#262730',
                'font_color': '#FFFFFF',
                'grid_color': '#4F4F4F'
            },
            'light': {
                'paper_bgcolor': '#FFFFFF',
                'plot_bgcolor': '#FFFFFF',
                'font_color': '#000000',
                'grid_color': '#E5E5E5'
            }
        }
        
        colors = theme_colors[st.session_state.theme]
        fig.update_layout(
            paper_bgcolor=colors['paper_bgcolor'],
            plot_bgcolor=colors['plot_bgcolor'],
            font={'color': colors['font_color']},
            xaxis=dict(gridcolor=colors['grid_color']),
            yaxis=dict(gridcolor=colors['grid_color'])
        )
        return fig
