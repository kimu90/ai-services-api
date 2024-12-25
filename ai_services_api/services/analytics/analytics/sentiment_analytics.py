import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

def get_sentiment_metrics(conn, start_date, end_date):
    """
    Retrieve sentiment metrics from the database for the specified date range.

    This function queries the database to fetch various sentiment metrics such as average sentiment score,
    satisfaction score, urgency score, clarity score, common emotion, and total interactions. The metrics are
    grouped by date and returned as a pandas DataFrame.

    The function handles the emotion labels stored as arrays in the database by unnesting them and identifying
    the most common emotion for each date.

    Parameters:
    - conn: psycopg2 connection object representing the database connection.
    - start_date (datetime): The start date of the date range.
    - end_date (datetime): The end date of the date range.

    Returns:
    - pandas.DataFrame: A DataFrame containing the sentiment metrics grouped by date.
    """
    cursor = conn.cursor()
    try:
        cursor.execute("""
            WITH DailyMetrics AS (
                SELECT 
                    DATE(sm.timestamp) as date,
                    AVG(sm.sentiment_score) as avg_sentiment,
                    AVG(sm.satisfaction_score) as satisfaction_score,
                    AVG(sm.urgency_score) as urgency_score,
                    AVG(sm.clarity_score) as clarity_score,
                    COUNT(*) as total_interactions
                FROM sentiment_metrics sm
                WHERE sm.timestamp BETWEEN %s AND %s
                GROUP BY DATE(sm.timestamp)
            ),
            DailyEmotions AS (
                SELECT 
                    DATE(sm.timestamp) as date,
                    emotion
                FROM sentiment_metrics sm,
                    LATERAL unnest(sm.emotion_labels) as emotion
                WHERE sm.timestamp BETWEEN %s AND %s
            ),
            CommonEmotion AS (
                SELECT 
                    date,
                    emotion as common_emotion,
                    emotion_count,
                    ROW_NUMBER() OVER (PARTITION BY date ORDER BY emotion_count DESC) as rn
                FROM (
                    SELECT 
                        date,
                        emotion,
                        COUNT(*) as emotion_count
                    FROM DailyEmotions
                    GROUP BY date, emotion
                ) counted
            )
            SELECT 
                dm.date,
                dm.avg_sentiment,
                dm.satisfaction_score,
                dm.urgency_score,
                dm.clarity_score,
                COALESCE(ce.common_emotion, 'neutral') as common_emotion,
                dm.total_interactions
            FROM DailyMetrics dm
            LEFT JOIN CommonEmotion ce ON dm.date = ce.date AND ce.rn = 1
            ORDER BY dm.date
        """, (start_date, end_date, start_date, end_date))
        
        columns = [desc[0] for desc in cursor.description]
        data = cursor.fetchall()
        return pd.DataFrame(data, columns=columns)
    finally:
        cursor.close()

def display_sentiment_analytics(sentiment_data):
    """
    Display sentiment analytics visualizations using the provided sentiment metrics DataFrame.

    This function creates various visualizations to analyze sentiment trends, compare sentiment components,
    and gain insights into emotional distribution and correlations. The visualizations include:

    1. Overall metrics cards displaying average sentiment, satisfaction, clarity, and total interactions.
    2. Sentiment trend line chart with a range selector for different time periods.
    3. Radar chart comparing average sentiment component scores.
    4. Area chart showing the distribution of emotions over time.
    5. Heatmap displaying the correlation between sentiment metrics.
    6. Hourly sentiment analysis chart with average sentiment and interaction count.
    7. Recent sentiment trends table showcasing the latest sentiment data.

    The visualizations are created using Plotly Graph Objects and Plotly Express, and displayed using Streamlit's
    `st.plotly_chart` and `st.dataframe` functions.

    Parameters:
    - sentiment_data (pandas.DataFrame): A DataFrame containing the sentiment metrics data.
    """
    st.subheader("Sentiment Analytics")
    
    # 1. Overall Metrics Cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Average Sentiment",
            f"{sentiment_data['avg_sentiment'].mean():.2f}",
            f"{(sentiment_data['avg_sentiment'].diff().mean() * 100):.1f}%"
        )
    with col2:
        st.metric(
            "Average Satisfaction",
            f"{sentiment_data['satisfaction_score'].mean():.2f}",
            f"{(sentiment_data['satisfaction_score'].diff().mean() * 100):.1f}%"
        )
    with col3:
        st.metric(
            "Average Clarity",
            f"{sentiment_data['clarity_score'].mean():.2f}",
            f"{(sentiment_data['clarity_score'].diff().mean() * 100):.1f}%"
        )
    with col4:
        st.metric(
            "Total Interactions",
            f"{sentiment_data['total_interactions'].sum():,}",
            f"{(sentiment_data['total_interactions'].diff().mean()):.0f}/day"
        )

    # 2. Main Sentiment Trend with Range Selector
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sentiment_data['date'],
        y=sentiment_data['avg_sentiment'],
        mode='lines+markers',
        name='Sentiment',
        line=dict(color='rgb(49, 130, 189)'),
        fill='tonexty'
    ))
    fig.update_layout(
        title='Sentiment Trend Over Time',
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=7, label="1w", step="day", stepmode="backward"),
                    dict(count=1, label="1m", step="month", stepmode="backward"),
                    dict(count=3, label="3m", step="month", stepmode="backward"),
                    dict(step="all")
                ])
            )
        ),
        yaxis=dict(title='Average Sentiment Score')
    )
    st.plotly_chart(fig, use_container_width=True)

    # 3. Sentiment Components Comparison
    col1, col2 = st.columns(2)
    with col1:
        # Radar Chart for Average Scores
        categories = ['Sentiment', 'Satisfaction', 'Urgency', 'Clarity']
        values = [
            sentiment_data['avg_sentiment'].mean(),
            sentiment_data['satisfaction_score'].mean(),
            sentiment_data['urgency_score'].mean(),
            sentiment_data['clarity_score'].mean()
        ]
        fig = go.Figure(data=go.Scatterpolar(
            r=values,
            theta=categories,
            fill='toself'
        ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
            showlegend=False,
            title='Average Sentiment Components'
        )
        st.plotly_chart(fig)

    with col2:
        # Create emotion pivot table
        dates = sentiment_data['date']
        emotions = sentiment_data['common_emotion']
        emotion_pivot = pd.crosstab(
            dates,
            emotions,
            normalize='index'
        ).fillna(0)
        
        # Create the area plot
        fig = px.area(
            emotion_pivot,
            title='Emotion Distribution Trend',
            labels={'value': 'Proportion', 'variable': 'Emotion'}
        )
        st.plotly_chart(fig)

    # 4. Correlation Heatmap
    correlation_data = sentiment_data[[
        'avg_sentiment',
        'satisfaction_score',
        'urgency_score',
        'clarity_score',
        'total_interactions'
    ]].corr()

    fig = px.imshow(
        correlation_data,
        title='Correlation Between Metrics',
        color_continuous_scale='RdBu_r',
        aspect='auto'
    )
    st.plotly_chart(fig)

    # 5. Hourly Analysis
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                EXTRACT(HOUR FROM timestamp) as hour,
                AVG(sentiment_score) as avg_sentiment,
                AVG(satisfaction_score) as avg_satisfaction,
                COUNT(*) as interaction_count
            FROM sentiment_metrics
            WHERE timestamp BETWEEN %s AND %s
            GROUP BY EXTRACT(HOUR FROM timestamp)
            ORDER BY hour
        """, (start_date, end_date))
        
        hourly_data = pd.DataFrame(
            cursor.fetchall(),
            columns=['hour', 'avg_sentiment', 'avg_satisfaction', 'interaction_count']
        )

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hourly_data['hour'],
            y=hourly_data['avg_sentiment'],
            name='Sentiment',
            mode='lines+markers'
        ))
        fig.add_trace(go.Bar(
            x=hourly_data['hour'],
            y=hourly_data['interaction_count'],
            name='Interactions',
            yaxis='y2',
            opacity=0.3
        ))
        fig.update_layout(
            title='Hourly Sentiment Analysis',
            xaxis=dict(title='Hour of Day'),
            yaxis=dict(title='Average Sentiment'),
            yaxis2=dict(title='Number of Interactions', overlaying='y', side='right'),
            hovermode='x unified'
        )
        st.plotly_chart(fig)

    finally:
        cursor.close()

    # 6. Latest Sentiment Trends Table
    st.subheader("Recent Sentiment Trends")
    latest_data = sentiment_data.tail(10).sort_values('date', ascending=False)
    
    # Format the data
    display_cols = ['date', 'avg_sentiment', 'satisfaction_score', 'urgency_score', 
                    'clarity_score', 'common_emotion', 'total_interactions']
    display_data = latest_data[display_cols].copy()
    
    # Round numeric columns
    numeric_cols = ['avg_sentiment', 'satisfaction_score', 'urgency_score', 'clarity_score']
    display_data[numeric_cols] = display_data[numeric_cols].round(3)
    
    # Create styled dataframe
    st.dataframe(
        display_data,
        column_config={
            "date": st.column_config.DateColumn("Date"),
            "avg_sentiment": st.column_config.NumberColumn(
                "Average Sentiment",
                help="Average sentiment score",
                format="%.3f"
            ),
            "satisfaction_score": st.column_config.NumberColumn(
                "Satisfaction",
                help="Satisfaction score",
                format="%.3f"
            ),
            "urgency_score": st.column_config.NumberColumn(
                "Urgency",
                help="Urgency score",
                format="%.3f"
            ),
            "clarity_score": st.column_config.NumberColumn(
                "Clarity",
                help="Clarity score",
                format="%.3f"
            ),
            "common_emotion": "Common Emotion",
            "total_interactions": st.column_config.NumberColumn(
                "Total Interactions",
                help="Number of interactions"
            )
        },
        hide_index=True,
        use_container_width=True
    )
