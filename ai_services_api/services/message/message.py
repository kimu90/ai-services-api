# app/api/endpoints/messages.py
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from ai_services_api.services.message.database import get_db_connection
from ai_services_api.services.message.config import get_settings
import google.generativeai as genai
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# app/api/endpoints/messages.py
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from ai_services_api.services.message.database import get_db_connection
from ai_services_api.services.message.config import get_settings
import google.generativeai as genai
from datetime import datetime
import logging
from psycopg2.extras import RealDictCursor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/draft")
async def create_message_draft(
    sender_id: int,
    receiver_id: int,
    content: str
):
    """
    Create an AI-assisted draft message between experts.
    
    Args:
        sender_id (int): ID of the sending expert
        receiver_id (int): ID of the receiving expert
        content (str): Context for the message
    
    Returns:
        dict: Created message details
    """
    logger.info(f"Creating draft message from expert {sender_id} to expert {receiver_id}")
    
    conn = get_db_connection()
    try:
        # Use RealDictCursor for dictionary-like row access
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get sender details with error handling
        try:
            cur.execute("""
                SELECT id, firstname, lastname, designation, theme, domains, fields 
                FROM experts_expert 
                WHERE id = %s AND is_active = true
            """, (sender_id,))
            sender = cur.fetchone()
            
            if not sender:
                logger.warning(f"Sender with ID {sender_id} not found or inactive")
                raise HTTPException(
                    status_code=404,
                    detail=f"Sender with ID {sender_id} not found or is inactive"
                )
        except Exception as e:
            logger.error(f"Database error while fetching sender: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Error fetching sender information"
            )
            
        # Get receiver details with error handling
        try:
            cur.execute("""
                SELECT id, firstname, lastname, designation, theme, domains, fields 
                FROM experts_expert 
                WHERE id = %s AND is_active = true
            """, (receiver_id,))
            receiver = cur.fetchone()
            
            if not receiver:
                logger.warning(f"Receiver with ID {receiver_id} not found or inactive")
                raise HTTPException(
                    status_code=404,
                    detail=f"Receiver with ID {receiver_id} not found or is inactive"
                )
        except Exception as e:
            logger.error(f"Database error while fetching receiver: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Error fetching receiver information"
            )

        # Initialize Gemini with error handling
        try:
            settings = get_settings()
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-pro')
        except Exception as e:
            logger.error(f"Error initializing Gemini AI: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Error initializing AI service"
            )

        # Generate draft using AI
        try:
            prompt = f"""
            Draft a professional message from {sender['firstname']} {sender['lastname']} ({sender['designation'] or 'Expert'}) 
            to {receiver['firstname']} {receiver['lastname']} ({receiver['designation'] or 'Expert'}).
            
            Context about sender:
            - Theme: {sender['theme'] or 'Not specified'}
            - Domains: {', '.join(sender['domains'] if sender.get('domains') else ['Not specified'])}
            - Fields: {', '.join(sender['fields'] if sender.get('fields') else ['Not specified'])}
            
            Context about receiver:
            - Theme: {receiver['theme'] or 'Not specified'}
            - Domains: {', '.join(receiver['domains'] if receiver.get('domains') else ['Not specified'])}
            - Fields: {', '.join(receiver['fields'] if receiver.get('fields') else ['Not specified'])}
            
            Additional context: {content}
            
            Please draft a message that:
            1. Introduces the sender professionally
            2. References shared research interests or potential collaboration areas
            3. Clearly states the purpose of connection
            4. Suggests specific next steps
            5. Maintains professional tone
            """
            
            logger.info("Generating AI content")
            response = model.generate_content(prompt)
            draft_content = response.text
            logger.info("AI content generated successfully")

        except Exception as e:
            logger.error(f"Error generating AI content: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Error generating message content"
            )

        # Save the draft message with error handling
        try:
            cur.execute("""
                INSERT INTO expert_messages 
                    (sender_id, receiver_id, content, draft, created_at, updated_at) 
                VALUES 
                    (%s, %s, %s, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING id, created_at
            """, (sender_id, receiver_id, draft_content))
            
            new_message = cur.fetchone()
            conn.commit()
            logger.info(f"Draft message created successfully with ID: {new_message['id']}")

            return {
                "id": new_message['id'],
                "content": draft_content,
                "sender_id": sender_id,
                "receiver_id": receiver_id,
                "created_at": new_message['created_at'],
                "draft": True,
                "sender_name": f"{sender['firstname']} {sender['lastname']}",
                "receiver_name": f"{receiver['firstname']} {receiver['lastname']}"
            }

        except Exception as e:
            logger.error(f"Error saving draft message: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Error saving draft message"
            )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        # Handle any unexpected errors
        conn.rollback()
        logger.error(f"Unexpected error in create_message_draft: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred"
        )

    finally:
        # Clean up resources
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
            logger.info("Database connection closed")

@router.put("/messages/{message_id}")
async def update_message(
    message_id: int,
    content: str,
    mark_as_sent: Optional[bool] = False
):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE expert_messages 
            SET content = %s,
                draft = CASE WHEN %s THEN false ELSE draft END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING *
        """, (content, mark_as_sent, message_id))
        
        updated_message = cur.fetchone()
        if not updated_message:
            raise HTTPException(status_code=404, detail="Message not found")
            
        conn.commit()
        return updated_message

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@router.delete("/messages/{message_id}")
async def delete_message(message_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("DELETE FROM expert_messages WHERE id = %s RETURNING id", (message_id,))
        deleted = cur.fetchone()
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Message not found")
            
        conn.commit()
        return {"message": "Message deleted successfully"}

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@router.get("/messages/thread/{other_user_id}")
async def get_message_thread(
    user_id: int,
    other_user_id: int,
    limit: int = 50
):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT m.*, 
                   s.firstname as sender_firstname, 
                   s.lastname as sender_lastname,
                   r.firstname as receiver_firstname, 
                   r.lastname as receiver_lastname
            FROM expert_messages m
            JOIN experts_expert s ON m.sender_id = s.id
            JOIN experts_expert r ON m.receiver_id = r.id
            WHERE (m.sender_id = %s AND m.receiver_id = %s)
               OR (m.sender_id = %s AND m.receiver_id = %s)
            ORDER BY m.created_at DESC
            LIMIT %s
        """, (user_id, other_user_id, other_user_id, user_id, limit))
        
        messages = cur.fetchall()
        
        return [{
            "id": msg['id'],
            "content": msg['content'],
            "sender_id": msg['sender_id'],
            "receiver_id": msg['receiver_id'],
            "sender_name": f"{msg['sender_firstname']} {msg['sender_lastname']}",
            "receiver_name": f"{msg['receiver_firstname']} {msg['receiver_lastname']}",
            "created_at": msg['created_at'],
            "draft": msg['draft']
        } for msg in messages]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()
