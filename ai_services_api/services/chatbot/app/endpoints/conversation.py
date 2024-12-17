from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Depends
from typing import Optional, Dict
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
class ChatResponse(BaseModel):
    response: str
    timestamp: datetime
    user_id: str
    session_id: str
    metrics: Optional[Dict] = None

class ExpertMatchMetrics(BaseModel):
    expert_id: str
    name: str
    similarity_score: float
    rank: int
    clicked: bool = False

class ChatMetrics(BaseModel):
    session_id: str
    total_interactions: int
    avg_response_time: float
    success_rate: float
    expert_matches: list[ExpertMatchMetrics]

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
            if isinstance(part, dict):
                response_metadata = part
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
                'response_time': response_metadata['response_time'],
                'intent': {
                    'type': response_metadata['intent_type'],
                    'confidence': response_metadata['intent_confidence']
                },
                'expert_matches': len(response_metadata['expert_matches']),
                'error_occurred': response_metadata['error_occurred']
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
                    'expert_matches': [],
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
                SUM(CASE WHEN NOT i.error_occurred THEN 1 ELSE 0 END)::FLOAT / COUNT(i.id) as success_rate
            FROM chat_sessions s
            LEFT JOIN chat_interactions i ON s.session_id = i.session_id
            WHERE s.session_id = %s
            GROUP BY s.session_id
        """, (session_id,))
        
        session_metrics = cursor.fetchone()
        if not session_metrics:
            raise HTTPException(status_code=404, detail="Session not found")
            
        # Get expert matches for the session
        cursor.execute("""
            SELECT 
                a.expert_id,
                e.first_name || ' ' || e.last_name as name,
                a.similarity_score,
                a.rank_position,
                a.clicked
            FROM chat_analytics a
            JOIN chat_interactions i ON a.interaction_id = i.id
            JOIN experts_expert e ON a.expert_id::integer = e.id
            WHERE i.session_id = %s
            ORDER BY i.timestamp DESC, a.rank_position
        """, (session_id,))
        
        expert_matches = [
            ExpertMatchMetrics(
                expert_id=row[0],
                name=row[1],
                similarity_score=row[2],
                rank=row[3],
                clicked=row[4]
            )
            for row in cursor.fetchall()
        ]
        
        return ChatMetrics(
            session_id=session_metrics[0],
            total_interactions=session_metrics[1],
            avg_response_time=session_metrics[2],
            success_rate=session_metrics[3],
            expert_matches=expert_matches
        )
        
    finally:
        cursor.close()
        db_conn.close()

@router.post("/chat/expert-click")
async def record_expert_click(
    interaction_id: int,
    expert_id: str
):
    """Record when a user clicks on an expert match."""
    db_conn = db_connector.get_connection()
    cursor = db_conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE chat_analytics
            SET clicked = true,
                updated_at = CURRENT_TIMESTAMP
            WHERE interaction_id = %s AND expert_id = %s
            RETURNING id
        """, (interaction_id, expert_id))
        
        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Expert match not found for this interaction"
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
                    SUM(CASE WHEN error_occurred THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as error_rate
                FROM chat_interactions
                WHERE {where_clause}
            ),
            ExpertMetrics AS (
                SELECT 
                    COUNT(*) as total_expert_matches,
                    AVG(similarity_score) as avg_similarity,
                    SUM(CASE WHEN clicked THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as click_through_rate
                FROM chat_analytics a
                JOIN chat_interactions i ON a.interaction_id = i.id
                WHERE {where_clause}
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
                em.*,
                json_agg(json_build_object(
                    'intent_type', intm.intent_type,
                    'count', intm.count,
                    'avg_confidence', intm.avg_confidence
                )) as intent_metrics
            FROM InteractionMetrics im
            CROSS JOIN ExpertMetrics em
            CROSS JOIN IntentMetrics intm
            GROUP BY 
                im.total_interactions, im.total_sessions, im.unique_users, 
                im.avg_response_time, im.error_rate,
                em.total_expert_matches, em.avg_similarity, em.click_through_rate
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
                "error_rate": analytics[4]
            },
            "expert_matching": {
                "total_matches": analytics[5],
                "avg_similarity": analytics[6],
                "click_through_rate": analytics[7]
            },
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
