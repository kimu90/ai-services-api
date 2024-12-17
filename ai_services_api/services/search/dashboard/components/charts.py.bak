import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Dict, Any

def create_time_series_chart(data: pd.DataFrame, 
                           title: str,
                           x_column: str = 'date',
                           y_column: str = 'total_searches') -> go.Figure:
    """Create a time series chart using plotly"""
    fig = px.line(data, 
                  x=x_column, 
                  y=y_column,
                  title=title)
    
    fig.update_layout(
        template='plotly_white',
        xaxis_title='Date',
        yaxis_title='Value',
        height=400
    )
    
    return fig

def create_heatmap(data: pd.DataFrame, 
                   title: str,
                   x_column: str = 'expert_id',
                   y_column: str = 'search_type',
                   value_column: str = 'click_rate') -> go.Figure:
    """Create a heatmap using plotly"""
    pivot_data = data.pivot(
        index=y_column,
        columns=x_column,
        values=value_column
    )
    
    fig = go.Figure(data=go.Heatmap(
        z=pivot_data.values,
        x=pivot_data.columns,
        y=pivot_data.index,
        colorscale='Viridis'
    ))
    
    fig.update_layout(
        title=title,
        template='plotly_white',
        height=400
    )
    
    return fig

def create_bar_chart(data: pd.DataFrame,
                    title: str,
                    x_column: str,
                    y_column: str) -> go.Figure:
    """Create a bar chart using plotly"""
    fig = px.bar(data,
                 x=x_column,
                 y=y_column,
                 title=title)
    
    fig.update_layout(
        template='plotly_white',
        xaxis_title=x_column,
        yaxis_title=y_column,
        height=400
    )
    
    return fig
