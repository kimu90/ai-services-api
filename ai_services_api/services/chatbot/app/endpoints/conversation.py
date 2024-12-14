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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# Initialize managers
llm_manager = GeminiLLMManager()
message_handler = MessageHandler(llm_manager)
db_connector = DatabaseConnector()

# Request/Response Models
class ChatRequest(BaseModel):
    query: str
    user_id: str
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    context: Optional[Dict] = None

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

@router.post("/chat")
@limiter.limit("5/minute")
async def chat_endpoint(
    request: Request,
    chat_request: ChatRequest,
    background_tasks: BackgroundTasks
):
    """Main chat endpoint with full analytics tracking."""
    db_conn = db_connector.get_connection()
    cursor = db_conn.cursor()
    start_time = datetime.utcnow()
    
    try:
        # Get or create session
        session_id = chat_request.session_id
        if not session_id:
            session_id = await message_handler.start_chat_session(chat_request.user_id)
        
        # Process message and collect response
        response_parts = []
        response_metadata = None
        
        async for part in message_handler.send_message_async(
            message=chat_request.query,
            user_id=chat_request.user_id,
            session_id=session_id,
            conversation_id=chat_request.conversation_id,
            context=chat_request.context
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
                user_id=chat_request.user_id,
                query=chat_request.query,
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
            user_id=chat_request.user_id,
            session_id=session_id,
            metrics=metrics
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        # Record error if we have a session
        if session_id:
            await message_handler.record_interaction(
                session_id=session_id,
                user_id=chat_request.user_id,
                query=chat_request.query,
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
                e.firstname || ' ' || e.lastname as name,
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

@router.post("/test/chat")
async def test_chat_endpoint(
    request: Request,
    chat_request: ChatRequest,
    background_tasks: BackgroundTasks
):
    """Test endpoint for chat interactions with guaranteed data collection."""
    db_conn = db_connector.get_connection()
    cursor = db_conn.cursor()
    start_time = datetime.utcnow()
    
    try:
        # Force test user ID
        test_user_id = "test_user"
        
        # Create test session
        cursor.execute("""
            INSERT INTO chat_sessions (session_id, user_id, start_time)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            RETURNING session_id
        """, (f"test_session_{int(time.time())}", test_user_id))
        
        session_id = cursor.fetchone()[0]
        db_conn.commit()
        
        logger.info(f"Created test session: {session_id}")
        
        # Process chat request
        response_parts = []
        metadata = None
        
        async for part in message_handler.send_message_async(
            message=chat_request.query,
            user_id=test_user_id,
            session_id=session_id
        ):
            if isinstance(part, dict) and part.get('is_metadata'):
                metadata = part['metadata']
            else:
                if isinstance(part, bytes):
                    part = part.decode('utf-8')
                response_parts.append(part)
        
        complete_response = ''.join(response_parts)
        
        # Record interaction
        cursor.execute("""
            INSERT INTO chat_interactions (
                session_id, user_id, query, response, timestamp,
                response_time, intent_type, intent_confidence,
                expert_matches, error_occurred
            ) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            session_id,
            test_user_id,
            chat_request.query,
            complete_response,
            metadata.get('response_time', 0) if metadata else 0,
            metadata.get('intent_type', 'general') if metadata else 'general',
            metadata.get('intent_confidence', 0) if metadata else 0,
            len(metadata.get('expert_matches', [])) if metadata else 0,
            metadata.get('error_occurred', False) if metadata else False
        ))
        
        interaction_id = cursor.fetchone()[0]
        
        # Record expert matches if any
        if metadata and metadata.get('expert_matches'):
            for match in metadata['expert_matches']:
                cursor.execute("""
                    INSERT INTO chat_analytics (
                        interaction_id, expert_id, similarity_score,
                        rank_position, clicked
                    ) VALUES (%s, %s, %s, %s, false)
                """, (
                    interaction_id,
                    match['expert_id'],
                    match['similarity_score'],
                    match['rank_position']
                ))
        
        db_conn.commit()
        
        return ChatResponse(
            response=complete_response,
            timestamp=datetime.utcnow(),
            user_id=test_user_id,
            session_id=session_id,
            metrics={
                'response_time': metadata.get('response_time', 0) if metadata else 0,
                'intent': {
                    'type': metadata.get('intent_type', 'general') if metadata else 'general',
                    'confidence': metadata.get('intent_confidence', 0) if metadata else 0
                },
                'expert_matches': len(metadata.get('expert_matches', [])) if metadata else 0
            }
        )
        
    except Exception as e:
        logger.error(f"Error in test chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        db_conn.close()

@router.get("/test/verify-data/{session_id}")
async def verify_test_data(session_id: str):
    """Verify that test data was properly stored."""
    db_conn = db_connector.get_connection()
    cursor = db_conn.cursor()
    
    try:
        # Check session data
        cursor.execute("""
            SELECT 
                s.session_id,
                s.user_id,
                COUNT(i.id) as interaction_count,
                COUNT(a.id) as analytics_count
            FROM chat_sessions s
            LEFT JOIN chat_interactions i ON s.session_id = i.session_id
            LEFT JOIN chat_analytics a ON a.interaction_id = i.id
            WHERE s.session_id = %s
            GROUP BY s.session_id, s.user_id
        """, (session_id,))
        
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Test session not found")
            
        return {
            "session_id": result[0],
            "user_id": result[1],
            "stored_interactions": result[2],
            "stored_analytics": result[3],
            "verification": "Data successfully stored"
        }
        
    finally:
        cursor.close()
        db_conn.close()

@router.get("/test/metrics")
async def test_get_metrics(hours: int = 24):
    """Get metrics for test interactions."""
    db_conn = db_connector.get_connection()
    cursor = db_conn.cursor()
    
    try:
        cursor.execute("""
            WITH TestMetrics AS (
                SELECT 
                    COUNT(*) as total_interactions,
                    COUNT(DISTINCT session_id) as unique_sessions,
                    AVG(response_time) as avg_response_time,
                    SUM(CASE WHEN error_occurred THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as error_rate
                FROM chat_interactions
                WHERE user_id = 'test_user'
                AND timestamp >= NOW() - interval '%s hours'
            ),
            ExpertMetrics AS (
                SELECT 
                    COUNT(*) as total_matches,
                    AVG(similarity_score) as avg_similarity,
                    SUM(CASE WHEN clicked THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as click_rate
                FROM chat_analytics a
                JOIN chat_interactions i ON a.interaction_id = i.id
                WHERE i.user_id = 'test_user'
                AND i.timestamp >= NOW() - interval '%s hours'
            )
            SELECT * FROM TestMetrics, ExpertMetrics
        """, (hours, hours))
        
        result = cursor.fetchone()
        
        return {
            "time_period": f"Last {hours} hours",
            "interactions": {
                "total": result[0],
                "unique_sessions": result[1],
                "avg_response_time": result[2],
                "error_rate": result[3]
            },
            "expert_matching": {
                "total_matches": result[4],
                "avg_similarity": result[5],
                "click_rate": result[6]
            }
        }
        
    finally:
        cursor.close()
        db_conn.close()

# Add this function to test the entire flow
async def test_chat_flow():
    """Test the entire chat flow and data collection."""
    # Test chat request
    response = await test_chat_endpoint(
        request=Request,
        chat_request=ChatRequest(
            query="Who are the experts in public health?",
            user_id="test_user"
        ),
        background_tasks=BackgroundTasks()
    )
    
    # Verify data storage
    verification = await verify_test_data(response.session_id)
    
    # Get metrics
    metrics = await test_get_metrics(hours=1)
    
    return {
        "chat_response": response,
        "verification": verification,
        "metrics": metrics
    }

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
