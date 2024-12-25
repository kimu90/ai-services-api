import pandas as pd
import plotly.express as px
import streamlit as st

def get_content_metrics(conn, start_date, end_date):
    """
    Retrieve content interaction metrics from the database.
    
    Parameters:
    - conn: Database connection object
    - start_date: Start date for the analysis
    - end_date: End date for the analysis
    
    Returns:
    - Dictionary containing content metrics DataFrames
    """
    cursor = conn.cursor()
    try:
        # Get resource interaction metrics
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
                LIMIT 10
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
        """, (start_date, end_date) * 3)
        
        result = cursor.fetchone()[0]
        
        return {
            'resource_metrics': pd.DataFrame(result['resource_metrics']),
            'popular_resources': pd.DataFrame(result['popular_resources']),
            'tag_metrics': pd.DataFrame(result['tag_metrics'])
        }
    finally:
        cursor.close()

def display_content_analytics(metrics):
    """
    Display content analytics visualizations.
    
    Parameters:
    - metrics: Dictionary containing content metrics DataFrames
    """
    st.subheader("Content Analytics")

    # Resource Type Distribution
    resource_metrics = metrics['resource_metrics']
    popular_resources = metrics['popular_resources']
    tag_metrics = metrics['tag_metrics']

    # Overview metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Total Resources", 
            f"{resource_metrics['total_resources'].sum():,}"
        )
    with col2:
        st.metric(
            "Total Views", 
            f"{resource_metrics['total_views'].sum():,}"
        )
    with col3:
        st.metric(
            "Unique Users", 
            f"{resource_metrics['unique_users'].sum():,}"
        )

    # Resource Type Analysis
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            px.pie(
                resource_metrics,
                values='total_resources',
                names='resource_type',
                title='Resource Distribution by Type'
            )
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
            ).update_layout(xaxis_tickangle=-45)
        )

    # Popular Resources
    st.subheader("Most Popular Resources")
    st.dataframe(
        popular_resources[['title', 'type', 'view_count', 'unique_viewers', 'tags']]
        .sort_values('view_count', ascending=False)
    )

    # Tag Analysis
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
        )
    )

    # Top Tags Table
    st.subheader("Top Content Tags")
    st.dataframe(
        tag_metrics[['tag_name', 'tag_type', 'resource_count', 'user_count']]
        .sort_values('resource_count', ascending=False)
    )
