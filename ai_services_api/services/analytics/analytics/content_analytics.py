import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import time
import logging
from typing import Dict, Optional
from datetime import datetime
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('analytics_dashboard')

def setup_database_connection(conn) -> None:
    """Set up database parameters for better query performance."""
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
                    r.source,
                    COUNT(DISTINCT r.id) as total_resources,
                    COUNT(DISTINCT s.user_id) as unique_users,
                    COUNT(s.id) as total_views,
                    COUNT(DISTINCT pt.tag_id) as unique_tags
                FROM resources_resource r
                LEFT JOIN search_logs s ON s.query LIKE '%' || COALESCE(r.doi, r.title) || '%'
                LEFT JOIN publication_tags pt ON (
                    CASE 
                        WHEN r.doi IS NOT NULL THEN r.doi = pt.doi 
                        ELSE r.title = pt.title
                    END
                )
                WHERE s.timestamp BETWEEN %s AND %s
                GROUP BY r.type, r.collection, r.source
            ),
            PopularResources AS (
                SELECT 
                    r.title,
                    r.type,
                    r.source,
                    COUNT(s.id) as view_count,
                    COUNT(DISTINCT s.user_id) as unique_viewers,
                    r.citation,
                    array_agg(DISTINCT t.tag_name) FILTER (WHERE t.tag_name IS NOT NULL) as tags,
                    array_agg(DISTINCT t.tag_type) FILTER (WHERE t.tag_type IS NOT NULL) as tag_types,
                    jsonb_object_agg(t.tag_type, COUNT(t.tag_id)) FILTER (WHERE t.tag_type IS NOT NULL) as tag_type_counts
                FROM resources_resource r
                LEFT JOIN search_logs s ON s.query LIKE '%' || COALESCE(r.doi, r.title) || '%'
                LEFT JOIN publication_tags pt ON (
                    CASE 
                        WHEN r.doi IS NOT NULL THEN r.doi = pt.doi 
                        ELSE r.title = pt.title
                    END
                )
                LEFT JOIN tags t ON pt.tag_id = t.tag_id
                WHERE s.timestamp BETWEEN %s AND %s
                GROUP BY r.title, r.type, r.source, r.citation
                ORDER BY view_count DESC
                OFFSET %s
                LIMIT %s
            ),
            TagMetrics AS (
                SELECT 
                    t.tag_name,
                    t.tag_type,
                    t.additional_metadata,
                    COUNT(DISTINCT COALESCE(pt.doi, pt.title)) as resource_count,
                    COUNT(DISTINCT s.user_id) as user_count,
                    array_agg(DISTINCT r.type) as resource_types,
                    array_agg(DISTINCT r.source) as sources
                FROM tags t
                LEFT JOIN publication_tags pt ON t.tag_id = pt.tag_id
                LEFT JOIN resources_resource r ON (
                    CASE 
                        WHEN pt.doi IS NOT NULL THEN r.doi = pt.doi 
                        ELSE r.title = pt.title
                    END
                )
                LEFT JOIN search_logs s ON s.query LIKE '%' || COALESCE(r.doi, r.title) || '%'
                WHERE s.timestamp BETWEEN %s AND %s
                  AND t.tag_name IS NOT NULL
                GROUP BY t.tag_name, t.tag_type, t.additional_metadata
                ORDER BY resource_count DESC
                LIMIT 20
            ),
            AuthorMetrics AS (
                SELECT 
                    t.tag_name as author_name,
                    COUNT(DISTINCT COALESCE(pt.doi, pt.title)) as publication_count,
                    array_agg(DISTINCT r.type) as publication_types,
                    COUNT(DISTINCT s.user_id) as reader_count
                FROM tags t
                LEFT JOIN publication_tags pt ON t.tag_id = pt.tag_id
                LEFT JOIN resources_resource r ON (
                    CASE 
                        WHEN pt.doi IS NOT NULL THEN r.doi = pt.doi 
                        ELSE r.title = pt.title
                    END
                )
                LEFT JOIN search_logs s ON s.query LIKE '%' || COALESCE(r.doi, r.title) || '%'
                WHERE t.tag_type = 'author'
                  AND s.timestamp BETWEEN %s AND %s
                GROUP BY t.tag_name
                ORDER BY publication_count DESC
                LIMIT 10
            ),
            DomainMetrics AS (
                SELECT 
                    t.tag_name as domain_name,
                    t.tag_type,
                    COUNT(DISTINCT COALESCE(pt.doi, pt.title)) as resource_count,
                    COUNT(DISTINCT s.user_id) as user_count,
                    array_agg(DISTINCT r.type) as resource_types
                FROM tags t
                LEFT JOIN publication_tags pt ON t.tag_id = pt.tag_id
                LEFT JOIN resources_resource r ON (
                    CASE 
                        WHEN pt.doi IS NOT NULL THEN r.doi = pt.doi 
                        ELSE r.title = pt.title
                    END
                )
                LEFT JOIN search_logs s ON s.query LIKE '%' || COALESCE(r.doi, r.title) || '%'
                WHERE t.tag_type = 'domain'
                  AND s.timestamp BETWEEN %s AND %s
                GROUP BY t.tag_name, t.tag_type
                ORDER BY resource_count DESC
                LIMIT 15
            )
            SELECT 
                json_build_object(
                    'resource_metrics', (SELECT json_agg(row_to_json(ResourceMetrics)) FROM ResourceMetrics),
                    'popular_resources', (SELECT json_agg(row_to_json(PopularResources)) FROM PopularResources),
                    'tag_metrics', (SELECT json_agg(row_to_json(TagMetrics)) FROM TagMetrics),
                    'author_metrics', (SELECT json_agg(row_to_json(AuthorMetrics)) FROM AuthorMetrics),
                    'domain_metrics', (SELECT json_agg(row_to_json(DomainMetrics)) FROM DomainMetrics)
                ) as metrics
        """, (start_date, end_date, start_date, end_date, offset, page_size, 
              start_date, end_date, start_date, end_date, start_date, end_date))
        
        query_time = time.time() - start_time
        if query_time > 5:
            logger.warning(f"Slow query detected: {query_time:.2f} seconds")
        
        raw_result = cursor.fetchone()
        
        # Handle case where we get no result
        if not raw_result:
            logger.warning("No results returned from query")
            return {
                'resource_metrics': pd.DataFrame(),
                'popular_resources': pd.DataFrame(),
                'tag_metrics': pd.DataFrame(),
                'author_metrics': pd.DataFrame(),
                'domain_metrics': pd.DataFrame()
            }
        
        result = raw_result[0]  # Get the first element only if we have results
        
        # Handle None result
        if not result:
            logger.warning("Query returned None")
            return {
                'resource_metrics': pd.DataFrame(),
                'popular_resources': pd.DataFrame(),
                'tag_metrics': pd.DataFrame(),
                'author_metrics': pd.DataFrame(),
                'domain_metrics': pd.DataFrame()
            }
            
        # Process results into DataFrames
        metrics = {}
        for key in ['resource_metrics', 'popular_resources', 'tag_metrics', 
                   'author_metrics', 'domain_metrics']:
            df = pd.DataFrame(result.get(key, []))
            if not df.empty:
                # Process JSON columns
                for col in df.columns:
                    if isinstance(df[col].iloc[0], str) and df[col].iloc[0].startswith('{'):
                        df[col] = df[col].apply(lambda x: json.loads(x) if x else {})
            metrics[key] = df
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error retrieving content metrics: {str(e)}")
        return {
            'resource_metrics': pd.DataFrame(),
            'popular_resources': pd.DataFrame(),
            'tag_metrics': pd.DataFrame(),
            'author_metrics': pd.DataFrame(),
            'domain_metrics': pd.DataFrame()
        }
    finally:
        cursor.close()

def display_content_analytics(metrics: Dict[str, pd.DataFrame], conn=None) -> None:
    """
    Display content analytics dashboard.
    
    Args:
        metrics: Dictionary of DataFrames containing metrics
        conn: Optional database connection
    """
    try:
        st.title("Content Analytics Dashboard")
        
        # Check if we have any data
        if all(df.empty for df in metrics.values()):
            st.warning("No data available for the selected date range. Please adjust your filters and try again.")
            return

        # 1. Overview Section
        st.header("Overview")
        resource_metrics = metrics['resource_metrics']
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            total_resources = resource_metrics['total_resources'].sum() if not resource_metrics.empty else 0
            st.metric("Total Resources", f"{total_resources:,}")
        with col2:
            total_views = resource_metrics['total_views'].sum() if not resource_metrics.empty else 0
            st.metric("Total Views", f"{total_views:,}")
        with col3:
            unique_users = resource_metrics['unique_users'].sum() if not resource_metrics.empty else 0
            st.metric("Unique Users", f"{unique_users:,}")
        with col4:
            total_tags = resource_metrics['unique_tags'].sum() if not resource_metrics.empty else 0
            st.metric("Total Tags", f"{total_tags:,}")

        # 2. Resource Distribution Section
        st.header("Resource Distribution")
        if not resource_metrics.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                fig_source = px.pie(
                    resource_metrics,
                    values='total_resources',
                    names='source',
                    title='Content Sources',
                    hole=0.4
                )
                fig_source.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_source, use_container_width=True)
            
            with col2:
                fig_type = px.pie(
                    resource_metrics,
                    values='total_resources',
                    names='resource_type',
                    title='Content Types',
                    hole=0.4
                )
                fig_type.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_type, use_container_width=True)

        # 3. Popular Content Section
        st.header("Popular Content")
        popular_resources = metrics['popular_resources']
        if not popular_resources.empty:
            # Resource popularity chart
            fig_popularity = px.bar(
                popular_resources.head(10),
                x='title',
                y=['view_count', 'unique_viewers'],
                title='Top 10 Most Viewed Resources',
                barmode='group'
            )
            fig_popularity.update_layout(
                xaxis_tickangle=-45,
                xaxis_title="",
                yaxis_title="Count",
                height=500
            )
            st.plotly_chart(fig_popularity, use_container_width=True)

            # Popular resources table
            st.subheader("Detailed Resource Metrics")
            df_display = popular_resources.copy()
            df_display['tags'] = df_display['tags'].apply(lambda x: ', '.join(x) if isinstance(x, list) else '')
            st.dataframe(
                df_display[['title', 'type', 'source', 'view_count', 'unique_viewers', 'tags']]
                .sort_values('view_count', ascending=False)
                .style.background_gradient(subset=['view_count', 'unique_viewers'], cmap='Blues')
            )

        # 4. Author Analytics Section
        st.header("Author Analytics")
        author_metrics = metrics['author_metrics']
        if not author_metrics.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                fig_authors = px.bar(
                    author_metrics.head(10),
                    x='author_name',
                    y='publication_count',
                    title='Top 10 Authors by Publication Count'
                )
                fig_authors.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_authors, use_container_width=True)
            
            with col2:
                fig_readers = px.bar(
                    author_metrics.head(10),
                    x='author_name',
                    y='reader_count',
                    title='Top 10 Authors by Reader Count'
                )
                fig_readers.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_readers, use_container_width=True)

        # 5. Domain Analytics Section
        st.header("Domain Analytics")
        domain_metrics = metrics['domain_metrics']
        if not domain_metrics.empty:
            # Domain popularity
            fig_domains = px.scatter(
                domain_metrics,
                x='resource_count',
                y='user_count',
                color='tag_type',
                hover_data=['domain_name'],
                title='Domain Popularity Analysis',
                size='resource_count'
            )
            st.plotly_chart(fig_domains, use_container_width=True)

            # Domain distribution table
            st.subheader("Top Domains")
            st.dataframe(
                domain_metrics[['domain_name', 'resource_count', 'user_count']]
                .sort_values('resource_count', ascending=False)
                .style.background_gradient(subset=['resource_count', 'user_count'], cmap='Blues')
            )

        # 6. Tag Analysis Section
        st.header("Tag Analysis")
        tag_metrics = metrics['tag_metrics']
        if not tag_metrics.empty:
            # Tag type distribution
            col1, col2 = st.columns(2)
            
            with col1:
                # Tag type distribution
                tag_type_dist = pd.DataFrame(tag_metrics['tag_type'].value_counts()).reset_index()
                tag_type_dist.columns = ['Tag Type', 'Count']
                
                fig_tag_types = px.pie(
                    tag_type_dist,
                    values='Count',
                    names='Tag Type',
                    title='Tag Type Distribution',
                    hole=0.4
                )
                st.plotly_chart(fig_tag_types, use_container_width=True)
            
            with col2:
                # Tag usage trends
                fig_tag_usage = px.scatter(
                    tag_metrics,
                    x='resource_count',
                    y='user_count',
                    color='tag_type',
                    size='resource_count',
                    hover_data=['tag_name'],
                    title='Tag Usage Analysis'
                )
                fig_tag_usage.update_layout(height=400)
                st.plotly_chart(fig_tag_usage, use_container_width=True)

            # Tag Detailed Analysis
            st.subheader("Tag Details")
            tab1, tab2, tab3 = st.tabs(["Most Used Tags", "By Source", "By Type"])
            
            with tab1:
                # Most used tags overall
                st.dataframe(
                    tag_metrics[['tag_name', 'tag_type', 'resource_count', 'user_count']]
                    .sort_values('resource_count', ascending=False)
                    .head(15)
                    .style.background_gradient(subset=['resource_count', 'user_count'], cmap='Blues')
                )

            with tab2:
                # Tags by source
                if 'sources' in tag_metrics.columns:
                    source_tags = tag_metrics.explode('sources')
                    source_pivot = pd.pivot_table(
                        source_tags,
                        values='resource_count',
                        index='tag_name',
                        columns='sources',
                        aggfunc='sum',
                        fill_value=0
                    ).reset_index()
                    
                    st.dataframe(
                        source_pivot.sort_values('tag_name', ascending=True)
                        .style.background_gradient(cmap='Blues')
                    )

            with tab3:
                # Tags by type with metadata
                if 'additional_metadata' in tag_metrics.columns:
                    st.write("Tag Type Analysis")
                    for tag_type in tag_metrics['tag_type'].unique():
                        with st.expander(f"{tag_type.title()} Tags"):
                            type_df = tag_metrics[tag_metrics['tag_type'] == tag_type].copy()
                            type_df['metadata'] = type_df['additional_metadata'].apply(
                                lambda x: json.dumps(x, indent=2) if isinstance(x, dict) else x
                            )
                            st.dataframe(
                                type_df[['tag_name', 'resource_count', 'user_count', 'metadata']]
                                .sort_values('resource_count', ascending=False)
                                .head(10)
                                .style.background_gradient(subset=['resource_count', 'user_count'], cmap='Blues')
                            )

        # 7. Cross-Analysis Section
        st.header("Cross Analysis")
        if not resource_metrics.empty and not tag_metrics.empty:
            # Source vs Tag Type Analysis
            source_tag_data = []
            for _, row in resource_metrics.iterrows():
                source = row['source']
                if 'tag_type_counts' in row:
                    for tag_type, count in row['tag_type_counts'].items():
                        source_tag_data.append({
                            'source': source,
                            'tag_type': tag_type,
                            'count': count
                        })
            
            if source_tag_data:
                source_tag_df = pd.DataFrame(source_tag_data)
                fig_heatmap = px.density_heatmap(
                    source_tag_df,
                    x='source',
                    y='tag_type',
                    z='count',
                    title='Tag Type Distribution Across Sources',
                    color_continuous_scale='Blues'
                )
                fig_heatmap.update_layout(height=400)
                st.plotly_chart(fig_heatmap, use_container_width=True)

        # 8. Content Growth Analysis
        st.header("Content Growth")
        if 'date_issue' in popular_resources.columns:
            # Convert date_issue to datetime if it's not
            popular_resources['date_issue'] = pd.to_datetime(popular_resources['date_issue'])
            
            # Group by month and source
            monthly_growth = popular_resources.groupby(
                [pd.Grouper(key='date_issue', freq='M'), 'source']
            ).size().reset_index(name='count')
            
            fig_growth = px.line(
                monthly_growth,
                x='date_issue',
                y='count',
                color='source',
                title='Content Growth Over Time by Source',
                labels={'date_issue': 'Date', 'count': 'Number of Publications'}
            )
            fig_growth.update_layout(height=400)
            st.plotly_chart(fig_growth, use_container_width=True)

        # 9. Engagement Metrics
        st.header("Engagement Metrics")
        if not popular_resources.empty:
            engagement_metrics = popular_resources.groupby('type').agg({
                'view_count': ['sum', 'mean', 'max'],
                'unique_viewers': ['sum', 'mean', 'max']
            }).round(2)
            
            engagement_metrics.columns = [
                f"{col[0]}_{col[1]}" for col in engagement_metrics.columns
            ]
            
            st.dataframe(
                engagement_metrics
                .style.background_gradient(cmap='Blues')
            )

    except Exception as e:
        logger.error(f"Error displaying analytics: {str(e)}")
        st.error("An error occurred while displaying analytics. Please try again later.")
