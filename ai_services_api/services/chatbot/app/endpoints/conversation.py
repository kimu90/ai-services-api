from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Depends
from typing import Optional, Dict, List
from pydantic import BaseModel
from datetime import datetime
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
import time
from ai_services_api.services.chatbot.utils.llm_manager import GeminiLLMManager
from ai_services_api.services.chatbot.utils.message_handler import MessageHandler
from ai_services_api.services.chatbot.utils.db_utils import DatabaseConnector
from uuid import uuid4

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# Initialize managers
llm_manager = GeminiLLMManager()
message_handler = MessageHandler(llm_manager)
db_connector = DatabaseConnector()

# Response Models
class ContentMatchMetrics(BaseModel):
    content_id: str
    content_type: str
    title: str
    similarity_score: float
    rank: int
    clicked: bool = False

class ChatMetrics(BaseModel):
    session_id: str
    total_interactions: int
    avg_response_time: float
    success_rate: float
    content_matches: Dict[str, List[ContentMatchMetrics]]

class ChatResponse(BaseModel):
    response: str
    timestamp: datetime
    user_id: str
    session_id: str
    metrics: Optional[Dict] = None

@router.get("/chat/{query}")
@limiter.limit("5/minute")
async def chat_endpoint(
    query: str,
    request: Request,
    background_tasks: BackgroundTasks
):
    """Main chat endpoint with full analytics tracking."""
    db_conn = db_connector.get_connection()
    cursor = db_conn.cursor()
    start_time = datetime.utcnow()
    
    try:
        # Generate a random user_id
        user_id = str(uuid4())
        
        # Create a new session
        session_id = await message_handler.start_chat_session(user_id)
        
        # Process message and collect response
        response_parts = []
        response_metadata = None
        
        async for part in message_handler.send_message_async(
            message=query,
            user_id=user_id,
            session_id=session_id
        ):
            if isinstance(part, dict) and part.get('is_metadata'):
                response_metadata = part.get('metadata')
            else:
                if isinstance(part, bytes):
                    part = part.decode('utf-8')
                response_parts.append(part)
        
        complete_response = ''.join(response_parts)
        
        # Record interaction and update session
        if response_metadata:
            interaction_id = await message_handler.record_interaction(
                session_id=session_id,
                user_id=user_id,
                query=query,
                response_data={
                    'response': complete_response,
                    **response_metadata
                }
            )
            
            await message_handler.update_session_stats(
                session_id=session_id,
                successful=not response_metadata.get('error_occurred', False)
            )
            
            # Prepare metrics for response
            metrics = {
                'response_time': response_metadata.get('metrics', {}).get('response_time', 0.0),
                'intent': response_metadata.get('metrics', {}).get('intent', {}),
                'content_matches': {
                    'navigation': response_metadata.get('metrics', {}).get('content_types', {}).get('navigation', 0),
                    'publication': response_metadata.get('metrics', {}).get('content_types', {}).get('publication', 0)
                },
                'error_occurred': response_metadata.get('error_occurred', False)
            }
        else:
            metrics = None
        
        return ChatResponse(
            response=complete_response,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            session_id=session_id,
            metrics=metrics
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        # Record error if we have a session
        if session_id:
            await message_handler.record_interaction(
                session_id=session_id,
                user_id=user_id,
                query=query,
                response_data={
                    'response': str(e),
                    'intent_type': None,
                    'intent_confidence': 0.0,
                    'navigation_matches': 0,
                    'publication_matches': 0,
                    'response_time': (datetime.utcnow() - start_time).total_seconds(),
                    'error_occurred': True
                }
            )
            await message_handler.update_session_stats(
                session_id=session_id,
                successful=False
            )
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        db_conn.close()

@router.get("/chat/metrics/{session_id}")
async def get_chat_metrics(session_id: str):
    """Get metrics for a specific chat session."""
    db_conn = db_connector.get_connection()
    cursor = db_conn.cursor()
    
    try:
        # Get session metrics
        cursor.execute("""
            SELECT 
                s.session_id,
                COUNT(i.id) as total_interactions,
                AVG(i.response_time) as avg_response_time,
                SUM(CASE WHEN NOT i.error_occurred THEN 1 ELSE 0 END)::FLOAT / COUNT(i.id) as success_rate,
                SUM(i.navigation_matches) as total_navigation_matches,
                SUM(i.publication_matches) as total_publication_matches
            FROM chat_sessions s
            LEFT JOIN chat_interactions i ON s.session_id = i.session_id
            WHERE s.session_id = %s
            GROUP BY s.session_id
        """, (session_id,))
        
        session_metrics = cursor.fetchone()
        if not session_metrics:
            raise HTTPException(status_code=404, detail="Session not found")
            
        # Get content matches for the session
        cursor.execute("""
            SELECT 
                a.content_id,
                a.content_type,
                CASE 
                    WHEN a.content_type = 'navigation' THEN 
                        (SELECT title FROM navigation_content WHERE id = a.content_id::integer)
                    WHEN a.content_type = 'publication' THEN 
                        (SELECT title FROM resources_resource WHERE id = a.content_id::integer)
                END as title,
                a.similarity_score,
                a.rank_position,
                a.clicked
            FROM chat_analytics a
            JOIN chat_interactions i ON a.interaction_id = i.id
            WHERE i.session_id = %s
            ORDER BY i.timestamp DESC, a.rank_position
        """, (session_id,))
        
        content_matches = {}
        for row in cursor.fetchall():
            match = ContentMatchMetrics(
                content_id=row[0],
                content_type=row[1],
                title=row[2],
                similarity_score=row[3],
                rank=row[4],
                clicked=row[5]
            )
            
            if row[1] not in content_matches:
                content_matches[row[1]] = []
            content_matches[row[1]].append(match)
        
        return ChatMetrics(
            session_id=session_metrics[0],
            total_interactions=session_metrics[1],
            avg_response_time=session_metrics[2],
            success_rate=session_metrics[3],
            content_matches=content_matches
        )
        
    finally:
        cursor.close()
        db_conn.close()

@router.post("/chat/content-click")
async def record_content_click(
    interaction_id: int,
    content_id: str,
    content_type: str
):
    """Record when a user clicks on a content match."""
    db_conn = db_connector.get_connection()
    cursor = db_conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE chat_analytics
            SET clicked = true,
                updated_at = CURRENT_TIMESTAMP
            WHERE interaction_id = %s 
            AND content_id = %s 
            AND content_type = %s
            RETURNING id
        """, (interaction_id, content_id, content_type))
        
        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Content match not found for this interaction"
            )
            
        db_conn.commit()
        return {"message": "Click recorded successfully"}
        
    finally:
        cursor.close()
        db_conn.close()

@router.get("/chat/analytics")
async def get_chat_analytics(
    start_date: datetime,
    end_date: datetime = None,
    user_id: Optional[str] = None
):
    """Get detailed chat analytics."""
    if end_date is None:
        end_date = datetime.utcnow()
        
    db_conn = db_connector.get_connection()
    cursor = db_conn.cursor()
    
    try:
        # Build query conditions
        conditions = ["timestamp BETWEEN %s AND %s"]
        params = [start_date, end_date]
        
        if user_id:
            conditions.append("user_id = %s")
            params.append(user_id)
            
        where_clause = " AND ".join(conditions)
        
        # Get overall metrics
        cursor.execute(f"""
            WITH InteractionMetrics AS (
                SELECT 
                    COUNT(*) as total_interactions,
                    COUNT(DISTINCT session_id) as total_sessions,
                    COUNT(DISTINCT user_id) as unique_users,
                    AVG(response_time) as avg_response_time,
                    SUM(navigation_matches) as total_navigation_matches,
                    SUM(publication_matches) as total_publication_matches,
                    SUM(CASE WHEN error_occurred THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as error_rate
                FROM chat_interactions
                WHERE {where_clause}
            ),
            ContentMetrics AS (
                SELECT 
                    content_type,
                    COUNT(*) as total_matches,
                    AVG(similarity_score) as avg_similarity,
                    SUM(CASE WHEN clicked THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as click_through_rate
                FROM chat_analytics a
                JOIN chat_interactions i ON a.interaction_id = i.id
                WHERE {where_clause}
                GROUP BY content_type
            ),
            IntentMetrics AS (
                SELECT 
                    intent_type,
                    COUNT(*) as count,
                    AVG(intent_confidence) as avg_confidence
                FROM chat_interactions
                WHERE {where_clause}
                GROUP BY intent_type
            )
            SELECT 
                im.*,
                json_agg(DISTINCT jsonb_build_object(
                    'content_type', cm.content_type,
                    'total_matches', cm.total_matches,
                    'avg_similarity', cm.avg_similarity,
                    'click_through_rate', cm.click_through_rate
                )) as content_metrics,
                json_agg(DISTINCT jsonb_build_object(
                    'intent_type', intm.intent_type,
                    'count', intm.count,
                    'avg_confidence', intm.avg_confidence
                )) as intent_metrics
            FROM InteractionMetrics im
            CROSS JOIN ContentMetrics cm
            CROSS JOIN IntentMetrics intm
            GROUP BY 
                im.total_interactions, im.total_sessions, im.unique_users,
                im.avg_response_time, im.error_rate,
                im.total_navigation_matches, im.total_publication_matches
        """, params)
        
        analytics = cursor.fetchone()
        
        return {
            "period": {
                "start": start_date,
                "end": end_date
            },
            "interactions": {
                "total": analytics[0],
                "sessions": analytics[1],
                "unique_users": analytics[2],
                "avg_response_time": analytics[3],
                "navigation_matches": analytics[4],
                "publication_matches": analytics[5],
                "error_rate": analytics[6]
            },
            "content_matching": analytics[7],
            "intents": analytics[8]
        }
        
    finally:
        cursor.close()
        db_conn.close()

@router.post("/chat/end-session/{session_id}")
async def end_chat_session(session_id: str):
    """End a chat session and calculate final metrics."""
    db_conn = db_connector.get_connection()
    cursor = db_conn.cursor()
    
    try:
        # Update session end time
        cursor.execute("""
            UPDATE chat_sessions
            SET end_time = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE session_id = %s
            RETURNING id
        """, (session_id,))
        
        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Session not found"
            )
            
        db_conn.commit()
        
        # Get session summary metrics
        cursor.execute("""
            SELECT 
                total_messages,
                successful,
                EXTRACT(EPOCH FROM (end_time - start_time)) as duration_seconds
            FROM chat_sessions
            WHERE session_id = %s
        """, (session_id,))
        
        metrics = cursor.fetchone()
        
        return {
            "session_id": session_id,
            "total_messages": metrics[0],
            "successful": metrics[1],
            "duration_seconds": metrics[2]
        }
        
    finally:
        cursor.close()
        db_conn.close()
