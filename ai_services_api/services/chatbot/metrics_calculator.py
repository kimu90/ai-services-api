from datetime import datetime
import time
from typing import Dict, Optional
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

Base = declarative_base()

class ChatMetrics(Base):
    __tablename__ = 'chat_metrics'
    
    id = sa.Column(sa.Integer, primary_key=True)
    timestamp = sa.Column(sa.DateTime, nullable=False)
    user_id = sa.Column(sa.String, nullable=False)
    session_id = sa.Column(sa.String)
    conversation_id = sa.Column(sa.String)
    query_length = sa.Column(sa.Integer)
    response_length = sa.Column(sa.Integer)
    response_time = sa.Column(sa.Float)  # in seconds
    intent_type = sa.Column(sa.String)
    intent_confidence = sa.Column(sa.Float)
    expert_matches = sa.Column(sa.Integer)
    average_similarity_score = sa.Column(sa.Float)
    error_occurred = sa.Column(sa.Boolean, default=False)

class MetricsCollector:
    def __init__(self, db_url: str):
        self.engine = sa.create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.logger = logging.getLogger(__name__)

    async def collect_metrics(
        self,
        start_time: float,
        user_id: str,
        session_id: Optional[str],
        conversation_id: Optional[str],
        query: str,
        response: str,
        intent_data: Dict,
        expert_data: Dict,
        error_occurred: bool = False
    ):
        """Collect and store metrics for a chat interaction."""
        try:
            end_time = time.time()
            response_time = end_time - start_time
            
            metrics = ChatMetrics(
                timestamp=datetime.now(),
                user_id=user_id,
                session_id=session_id,
                conversation_id=conversation_id,
                query_length=len(query),
                response_length=len(response),
                response_time=response_time,
                intent_type=intent_data.get('type', 'unknown'),
                intent_confidence=intent_data.get('confidence', 0.0),
                expert_matches=len(expert_data.get('matches', [])),
                average_similarity_score=expert_data.get('avg_similarity', 0.0),
                error_occurred=error_occurred
            )
            
            session = self.Session()
            try:
                session.add(metrics)
                session.commit()
            finally:
                session.close()
                
        except Exception as e:
            self.logger.error(f"Error collecting metrics: {e}")
