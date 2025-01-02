import pandas as pd
import plotly.express as px
import streamlit as st
import time
import logging
from typing import Dict, Optional
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('analytics_dashboard')

def setup_database_connection(conn) -> None:
    cursor = conn.cursor()
    try:
        cursor.execute("SET statement_timeout = '30s';")
        cursor.execute("SET work_mem = '50MB';")
    except Exception as e:
        logger.warning(f"Failed to set database parameters: {str(e)}")
    finally:
        cursor.close()

def get_content_metrics(
    conn,
    start_date: datetime,
    end_date: datetime,
    page_size: int = 10,
    offset: int = 0
) -> Dict[str, pd.DataFrame]:
    start_time = time.time()
    cursor = conn.cursor()
    
    try:
        setup_database_connection(conn)
        
        cursor.execute("""
            WITH ResourceMetrics AS (
                SELECT 
                    r.type as resource_type,
                    r.collection,
                    COUNT(DISTINCT r.id) as total_resources,
                    COUNT(DISTINCT s.user_id) as unique_users,
                    COUNT(s.id) as total_views
                FROM resources_resource r
                LEFT JOIN search_logs s ON s.query LIKE '%' || r.doi || '%'
                WHERE s.timestamp BETWEEN %s AND %s
                GROUP BY r.type, r.collection
            ),
            PopularResources AS (
                SELECT 
                    r.title,
                    r.type,
                    COUNT(s.id) as view_count,
                    COUNT(DISTINCT s.user_id) as unique_viewers,
                    r.citation,
                    array_agg(DISTINCT t.tag_name) as tags
                FROM resources_resource r
                LEFT JOIN search_logs s ON s.query LIKE '%' || r.doi || '%'
                LEFT JOIN publication_tags pt ON r.doi = pt.doi
                LEFT JOIN tags t ON pt.tag_id = t.tag_id
                WHERE s.timestamp BETWEEN %s AND %s
                GROUP BY r.title, r.type, r.citation
                ORDER BY view_count DESC
                OFFSET %s
                LIMIT %s
            ),
            TagMetrics AS (
                SELECT 
                    t.tag_name,
                    t.tag_type,
                    COUNT(DISTINCT pt.doi) as resource_count,
                    COUNT(DISTINCT s.user_id) as user_count
                FROM tags t
                LEFT JOIN publication_tags pt ON t.tag_id = pt.tag_id
                LEFT JOIN search_logs s ON s.query LIKE '%' || pt.doi || '%'
                WHERE s.timestamp BETWEEN %s AND %s
                GROUP BY t.tag_name, t.tag_type
                ORDER BY resource_count DESC
                LIMIT 20
            )
            SELECT 
                json_build_object(
                    'resource_metrics', (SELECT json_agg(row_to_json(ResourceMetrics)) FROM ResourceMetrics),
                    'popular_resources', (SELECT json_agg(row_to_json(PopularResources)) FROM PopularResources),
                    'tag_metrics', (SELECT json_agg(row_to_json(TagMetrics)) FROM TagMetrics)
                ) as metrics
        """, (start_date, end_date, start_date, end_date, offset, page_size, start_date, end_date))
        
        query_time = time.time() - start_time
        if query_time > 5:
            logger.warning(f"Slow query detected: {query_time:.2f} seconds")
        
        raw_result = cursor.fetchone()
        logger.info(f"Query result: {raw_result}")
        
        try:
            metrics_json = raw_result[0] if raw_result else None
        except (IndexError, TypeError) as e:
            logger.error(f"Invalid query result format: {raw_result}, Error: {str(e)}")
            return {
                'resource_metrics': pd.DataFrame(),
                'popular_resources': pd.DataFrame(),
                'tag_metrics': pd.DataFrame()
            }
        if not metrics_json:
            logger.info("No data found - empty metrics")
            return {
                'resource_metrics': pd.DataFrame(),
                'popular_resources': pd.DataFrame(),
                'tag_metrics': pd.DataFrame()
            }
            
        result = raw_result[0]
        return {
            'resource_metrics': pd.DataFrame(result.get('resource_metrics', [])),
            'popular_resources': pd.DataFrame(result.get('popular_resources', [])),
            'tag_metrics': pd.DataFrame(result.get('tag_metrics', []))
        }
        
    except Exception as e:
        logger.error(f"Error retrieving content metrics: {str(e)}")
        return {
            'resource_metrics': pd.DataFrame(),
            'popular_resources': pd.DataFrame(),
            'tag_metrics': pd.DataFrame()
        }
    finally:
        cursor.close()

def display_content_analytics(metrics: Dict[str, pd.DataFrame], conn=None) -> None:
    try:
        st.subheader("Content Analytics")
        
        resource_metrics = metrics['resource_metrics']
        popular_resources = metrics['popular_resources']
        tag_metrics = metrics['tag_metrics']
        
        if resource_metrics.empty and popular_resources.empty and tag_metrics.empty:
            st.warning("No data available for the selected date range. Please adjust your filters and try again.")
            return
            
        col1, col2, col3 = st.columns(3)
        with col1:
            total_resources = resource_metrics['total_resources'].sum() if not resource_metrics.empty else 0
            st.metric("Total Resources", f"{total_resources:,}")
        with col2:
            total_views = resource_metrics['total_views'].sum() if not resource_metrics.empty else 0
            st.metric("Total Views", f"{total_views:,}")
        with col3:
            unique_users = resource_metrics['unique_users'].max() if not resource_metrics.empty else 0
            st.metric("Unique Users", f"{unique_users:,}")
        
        if not resource_metrics.empty and total_resources > 0:
            col1, col2 = st.columns(2)
            with col1:
                st.plotly_chart(
                    px.pie(
                        resource_metrics,
                        values='total_resources',
                        names='resource_type',
                        title='Resource Distribution by Type'
                    ),
                    use_container_width=True
                )
            
            with col2:
                st.plotly_chart(
                    px.bar(
                        resource_metrics,
                        x='collection',
                        y=['total_views', 'unique_users'],
                        title='Resource Usage by Collection',
                        barmode='group',
                        labels={
                            'value': 'Count',
                            'variable': 'Metric',
                            'collection': 'Collection'
                        }
                    ).update_layout(
                        xaxis_tickangle=-45,
                        height=400
                    ),
                    use_container_width=True
                )
        
        if not popular_resources.empty:
            st.subheader("Most Popular Resources")
            st.dataframe(
                popular_resources[['title', 'type', 'view_count', 'unique_viewers', 'tags']]
                .sort_values('view_count', ascending=False)
                .style.background_gradient(subset=['view_count'], cmap='Blues')
            )
        
        if not tag_metrics.empty:
            st.subheader("Content Tag Analysis")
            st.plotly_chart(
                px.scatter(
                    tag_metrics,
                    x='resource_count',
                    y='user_count',
                    color='tag_type',
                    hover_data=['tag_name'],
                    title='Tag Usage Analysis',
                    labels={
                        'resource_count': 'Number of Resources',
                        'user_count': 'Number of Users',
                        'tag_type': 'Tag Type'
                    }
                ).update_layout(height=500),
                use_container_width=True
            )
            
            st.subheader("Top Content Tags")
            st.dataframe(
                tag_metrics[['tag_name', 'tag_type', 'resource_count', 'user_count']]
                .sort_values('resource_count', ascending=False)
                .style.background_gradient(subset=['resource_count'], cmap='Blues')
            )
            
    except Exception as e:
        logger.error(f"Error displaying analytics: {str(e)}")
        st.error("An error occurred while displaying analytics. Please try again later or contact support if the problem persists.")
