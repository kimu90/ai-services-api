from typing import Dict, Any
import logging
from datetime import datetime, timedelta
from psycopg2.extras import Json

logger = logging.getLogger(__name__)

class RecommendationAnalytics:
    def __init__(self, db_connection):
        self.conn = db_connection
        
    async def record_expert_match(
        self,
        expert_id: str,
        matched_expert_id: str,
        similarity_score: float,
        shared_metrics: Dict[str, int],
        successful: bool = True
    ):
        """Record an expert matching interaction."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO expert_matching_logs (
                    expert_id, matched_expert_id, similarity_score,
                    shared_domains, shared_fields, shared_skills, successful
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                expert_id, matched_expert_id, similarity_score,
                shared_metrics['domains'], shared_metrics['fields'],
                shared_metrics['skills'], successful
            ))
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"Error recording expert match: {e}")
            self.conn.rollback()

    async def record_domain_interaction(self, domain_info: Dict[str, str]):
        """Update domain analytics."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO domain_analytics (
                    domain_name, field_name, subfield_name, expert_count, interaction_count
                ) VALUES (%s, %s, %s, 1, 1)
                ON CONFLICT (domain_name) DO UPDATE SET
                    interaction_count = domain_analytics.interaction_count + 1,
                    last_updated = CURRENT_TIMESTAMP
            """, (
                domain_info['domain'],
                domain_info.get('field'),
                domain_info.get('subfield')
            ))
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"Error recording domain interaction: {e}")
            self.conn.rollback()

    async def record_collaboration_suggestion(
        self,
        expert_id: str,
        suggested_expert_id: str,
        score: float,
        reason: str
    ):
        """Record a collaboration suggestion."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO collaboration_suggestions (
                    expert_id, suggested_expert_id, score, reason
                ) VALUES (%s, %s, %s, %s)
            """, (expert_id, suggested_expert_id, score, reason))
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"Error recording collaboration suggestion: {e}")
            self.conn.rollback()

    async def get_expert_metrics(self, expert_id: str) -> Dict[str, Any]:
        """Get comprehensive metrics for an expert."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                WITH ExpertMatches AS (
                    SELECT 
                        COUNT(*) as total_matches,
                        AVG(similarity_score) as avg_similarity,
                        SUM(shared_domains) as total_shared_domains,
                        SUM(shared_fields) as total_shared_fields
                    FROM expert_matching_logs
                    WHERE expert_id = %s
                ),
                Collaborations AS (
                    SELECT 
                        COUNT(*) as suggested_collabs,
                        AVG(score) as avg_collab_score,
                        SUM(CASE WHEN accepted THEN 1 ELSE 0 END) as accepted_collabs
                    FROM collaboration_suggestions
                    WHERE expert_id = %s
                )
                SELECT 
                    em.*, 
                    c.*
                FROM ExpertMatches em
                CROSS JOIN Collaborations c
            """, (expert_id, expert_id))
            
            result = cursor.fetchone()
            if result:
                return {
                    "matching_metrics": {
                        "total_matches": result[0],
                        "avg_similarity": result[1],
                        "total_shared_domains": result[2],
                        "total_shared_fields": result[3]
                    },
                    "collaboration_metrics": {
                        "suggested_collaborations": result[4],
                        "avg_collaboration_score": result[5],
                        "accepted_collaborations": result[6]
                    }
                }
            return {}
            
        except Exception as e:
            logger.error(f"Error getting expert metrics: {e}")
            return {}
    async def track_recommendation(self, source_expert: str, recommended_expert: str, metrics: Dict):
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO expert_matching_logs (
                    expert_id,
                    matched_expert_id,
                    similarity_score,
                    shared_domains,
                    shared_fields,
                    shared_skills,
                    successful
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                source_expert,
                recommended_expert,
                metrics['similarity_score'],
                metrics['shared_domains'],
                metrics['shared_fields'],
                metrics['shared_skills'],
                metrics.get('successful', True)
            ))
            self.conn.commit()
        finally:
            cursor.close()

    async def get_recommendation_metrics(self, expert_id: str, time_period: int = 30) -> Dict:
        cursor = self.conn.cursor()
        try:
            # Get basic metrics
            cursor.execute("""
                WITH RecentMatches AS (
                    SELECT *
                    FROM expert_matching_logs
                    WHERE expert_id = %s
                    AND timestamp >= NOW() - INTERVAL '%s days'
                )
                SELECT
                    COUNT(*) as total_matches,
                    AVG(similarity_score) as avg_similarity,
                    SUM(shared_domains) as total_shared_domains,
                    AVG(shared_domains) as avg_shared_domains,
                    COUNT(DISTINCT matched_expert_id) as unique_matches,
                    SUM(CASE WHEN successful THEN 1 ELSE 0 END)::float / 
                        NULLIF(COUNT(*), 0) as success_rate
                FROM RecentMatches
            """, (expert_id, time_period))
            
            basic_metrics = dict(zip(
                ['total_matches', 'avg_similarity', 'total_shared_domains', 
                 'avg_shared_domains', 'unique_matches', 'success_rate'],
                cursor.fetchone()
            ))

            # Get trend data
            cursor.execute("""
                SELECT 
                    DATE_TRUNC('day', timestamp) as date,
                    COUNT(*) as matches,
                    AVG(similarity_score) as avg_daily_similarity
                FROM expert_matching_logs
                WHERE expert_id = %s
                AND timestamp >= NOW() - INTERVAL '%s days'
                GROUP BY DATE_TRUNC('day', timestamp)
                ORDER BY date
            """, (expert_id, time_period))
            
            trend_data = [
                {
                    'date': row[0],
                    'matches': row[1],
                    'avg_similarity': row[2]
                }
                for row in cursor.fetchall()
            ]

            return {
                'basic_metrics': basic_metrics,
                'trends': trend_data
            }
        finally:
            cursor.close()

    async def get_domain_effectiveness(self) -> List[Dict]:
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    domain_name,
                    expert_count,
                    match_count,
                    match_count::float / NULLIF(expert_count, 0) as effectiveness_rate,
                    last_updated
                FROM domain_expertise_analytics
                WHERE match_count > 0
                ORDER BY effectiveness_rate DESC
            """)
            
            return [dict(zip(
                ['domain', 'experts', 'matches', 'effectiveness', 'last_updated'],
                row
            )) for row in cursor.fetchall()]
        finally:
            cursor.close()
    async def get_domain_analytics(self, time_period: int = 30) -> Dict[str, Any]:
        """Get domain-based analytics for a time period."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                WITH DomainStats AS (
                    SELECT 
                        d.domain_name,
                        d.expert_count,
                        d.interaction_count,
                        COUNT(DISTINCT em.expert_id) as matched_experts
                    FROM domain_analytics d
                    LEFT JOIN expert_matching_logs em ON 
                        em.timestamp >= NOW() - interval '%s days'
                    GROUP BY d.domain_name, d.expert_count, d.interaction_count
                )
                SELECT 
                    domain_name,
                    expert_count,
                    interaction_count,
                    matched_experts,
                    interaction_count::float / NULLIF(expert_count, 0) as engagement_rate
                FROM DomainStats
                ORDER BY interaction_count DESC
                LIMIT 10
            """, (time_period,))
            
            results = cursor.fetchall()
            return {
                "time_period_days": time_period,
                "domain_stats": [
                    {
                        "domain": row[0],
                        "expert_count": row[1],
                        "interaction_count": row[2],
                        "matched_experts": row[3],
                        "engagement_rate": row[4]
                    }
                    for row in results
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting domain analytics: {e}")
            return {}
