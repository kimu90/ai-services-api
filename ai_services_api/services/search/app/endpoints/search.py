from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any
from pydantic import BaseModel
import logging
from datetime import datetime
from ai_services_api.services.search.index_creator import ExpertSearchIndexManager
from ai_services_api.services.search.ml_predictor import MLPredictor
from ai_services_api.services.search.database_manager import DatabaseManager

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize ML Predictor
ml_predictor = MLPredictor()

class ExpertSearchResult(BaseModel):
    id: str
    first_name: str
    last_name: str
    designation: str
    theme: str
    unit: str
    contact: str
    is_active: bool
    score: float = None
    bio: str = None  
    knowledge_expertise: List[str] = []

class SearchResponse(BaseModel):
    total_results: int
    experts: List[ExpertSearchResult]

class PredictionResponse(BaseModel):
    predictions: List[str]
    confidence_scores: List[float]

@router.get("/experts/search/{query}")
async def search_experts(query: str, active_only: bool = True):
    try:
        search_manager = ExpertSearchIndexManager()
        results = search_manager.search_experts(query, k=5, active_only=active_only)
        
        formatted_results = [
            ExpertSearchResult(
                id=str(result['id']),
                first_name=result['first_name'],
                last_name=result['last_name'],
                designation=result['designation'],
                theme=result['theme'],
                unit=result['unit'],
                contact=result['contact'],
                is_active=result['is_active'],
                score=result.get('score')
            )
            for result in results
        ]
        
        # Update ML predictor with successful query
        ml_predictor.update(query, user_id="default")
        
        return SearchResponse(
            total_results=len(formatted_results),
            experts=formatted_results
        )
        
    except Exception as e:
        logger.error(f"Error searching experts: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while searching experts"
        )

@router.get("/experts/predict/{partial_query}")
async def predict_query(partial_query: str):
    """Predict query completions based on partial input."""
    try:
        predictions = ml_predictor.predict(partial_query, user_id="default")
        scores = [1.0 - (i * 0.1) for i in range(len(predictions))]
        
        return PredictionResponse(
            predictions=predictions,
            confidence_scores=scores
        )
        
    except Exception as e:
        logger.error(f"Error predicting queries: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while predicting queries"
        )

@router.post("/experts/train-predictor")
async def train_predictor(background_tasks: BackgroundTasks, queries: List[str]):
    """Train the ML predictor with historical queries."""
    try:
        background_tasks.add_task(ml_predictor.train, queries, user_id="default")
        return {"message": "Predictor training initiated"}
    except Exception as e:
        logger.error(f"Error training predictor: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error initiating predictor training"
        )

@router.get("/experts/similar/{expert_id}")
async def find_similar_experts(expert_id: str, active_only: bool = True):
    """Find similar experts based on an expert's ID."""
    try:
        search_manager = ExpertSearchIndexManager()
        
        expert_data = await search_manager.get_expert_text_by_id(expert_id)
        if not expert_data:
            raise HTTPException(
                status_code=404,
                detail=f"Expert with ID {expert_id} not found"
            )
        
        results = search_manager.search_experts(expert_data, k=6, active_only=active_only)
        
        formatted_results = [
            ExpertSearchResult(
                id=str(result['id']),
                first_name=result['first_name'],
                last_name=result['last_name'],
                designation=result['designation'],
                theme=result['theme'],
                unit=result['unit'],
                contact=result['contact'],
                is_active=result['is_active'],
                score=result.get('score')
            )
            for result in results
            if str(result['id']) != expert_id
        ][:5]
        
        return SearchResponse(
            total_results=len(formatted_results),
            experts=formatted_results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding similar experts: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while finding similar experts"
        )

@router.get("/experts/{expert_id}")
async def get_expert_details(expert_id: str):
    try:
        search_manager = ExpertSearchIndexManager()
        expert_data = await search_manager.get_expert_metadata(expert_id)
        
        if not expert_data:
            raise HTTPException(
                status_code=404,
                detail=f"Expert with ID {expert_id} not found"
            )
        
        return ExpertSearchResult(
            id=str(expert_data['id']),
            first_name=expert_data['first_name'],
            last_name=expert_data['last_name'],
            designation=expert_data['designation'],
            theme=expert_data['theme'],
            unit=expert_data['unit'],
            contact=expert_data['contact'],
            is_active=expert_data['is_active']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting expert details: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while getting expert details"
        )

@router.get("/test/experts/search/{query}")
async def test_search_experts(
    query: str,
    active_only: bool = True,
    test_error: bool = False
):
    """Test endpoint for expert search with analytics tracking"""
    db = DatabaseManager()
    try:
        if test_error:
            raise Exception("Test error scenario")

        start_time = datetime.now()
        search_manager = ExpertSearchIndexManager()
        
        session_id = db.start_search_session("test_user")
        results = search_manager.search_experts(query, k=5, active_only=active_only)
        
        search_id = db.record_search_analytics(
            query=query,
            user_id="test_user",
            response_time=(datetime.now() - start_time).total_seconds(),
            result_count=len(results),
            search_type='test'
        )
        
        for idx, result in enumerate(results):
            db.record_expert_search(
                search_id=search_id,
                expert_id=result['id'],
                rank_position=idx + 1
            )
        
        db.update_search_session(session_id, successful=len(results) > 0)
        
        formatted_results = [
            ExpertSearchResult(
                id=str(result['id']),
                first_name=result['first_name'],
                last_name=result['last_name'],
                designation=result['designation'],
                theme=result['theme'],
                unit=result['unit'],
                contact=result['contact'],
                is_active=result['is_active'],
                score=result.get('score')
            )
            for result in results
        ]
        # Update ML predictor
        ml_predictor.update(query, user_id="test_user")
        
        return SearchResponse(
            total_results=len(formatted_results),
            experts=formatted_results
        )
        
    except Exception as e:
        logger.error(f"Test Error searching experts: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/test/experts/predict/{partial_query}")
async def test_predict_query(
    partial_query: str,
    test_error: bool = False
):
    """Test endpoint for query predictions with analytics"""
    try:
        if test_error:
            raise Exception("Test error scenario")
        
        logger.debug(f"Attempting prediction for partial query: {partial_query}")
        ml_predictor = MLPredictor()
        predictions = ml_predictor.predict(partial_query)
        logger.debug(f"Predictions returned: {predictions}")
        
        scores = [1.0 - (i * 0.1) for i in range(len(predictions))]
        
        return PredictionResponse(
            predictions=predictions,
            confidence_scores=scores
        )
    
    except Exception as e:
        logger.error(f"Test Error predicting queries: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test/analytics/metrics")
async def test_get_analytics():
    """Get test analytics data"""
    db = DatabaseManager()
    try:
        performance_metrics = db.get_performance_metrics(hours=24)
        search_metrics = db.get_search_metrics(
            start_date="NOW() - INTERVAL '24 HOURS'",
            end_date="NOW()",
            search_type=['test']
        )
        
        return {
            "performance_metrics": performance_metrics,
            "search_metrics": search_metrics,
            "user_id": "test_user"
        }
        
    except Exception as e:
        logger.error(f"Test Error getting analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.post("/test/record-click")
async def test_record_click(
    search_id: int,
    expert_id: str = None
):
    """Test endpoint for recording clicks"""
    db = DatabaseManager()
    try:
        db.record_click(search_id, expert_id)
        return {"message": "Test click recorded successfully"}
    except Exception as e:
        logger.error(f"Test Error recording click: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
