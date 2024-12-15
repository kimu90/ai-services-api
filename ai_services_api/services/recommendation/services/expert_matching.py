import logging
from typing import List, Dict, Any, Optional
import os
import google.generativeai as genai
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

class ExpertMatchingService:
    def __init__(self):
        self._neo4j = GraphDatabase.driver(
            os.getenv('NEO4J_URI'),
            auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
        )

    async def analyze_expertise(self, expertise_list: List[str]) -> Dict[str, Any]:
        """Analyze expertise with more detailed categorization."""
        try:
            response = self.model.generate_content(prompt)
            analysis = eval(response.text)
            
            # Calculate additional metrics
            analysis["total_items"] = len(expertise_list)
            analysis["domain_distribution"] = {
                domain: expertise_list.count(domain) 
                for domain in analysis["domains"]
            }
            
            return analysis
            
        except Exception as e:
            self._logger.error(f"Error analyzing expertise: {e}")
            return {
                "domains": expertise_list[:2],
                "research_areas": expertise_list[2:4],
                "technical_skills": expertise_list[4:],
                "applications": [],
                "related_fields": [],
                "total_items": len(expertise_list),
                "domain_distribution": {}
            }

    async def find_similar_experts(self, expert_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Find similar experts with detailed analytics tracking."""
        query = """
        MATCH (e1:Expert {id: $expert_id})
        MATCH (e2:Expert)
        WHERE e1 <> e2
        
        // Calculate domain overlap
        OPTIONAL MATCH (e1)-[:HAS_DOMAIN]->(d:Domain)<-[:HAS_DOMAIN]-(e2)
        WITH e1, e2, COLLECT(DISTINCT d.name) as shared_domains, COUNT(DISTINCT d) as domain_count
        
        // Calculate field overlap
        OPTIONAL MATCH (e1)-[:HAS_FIELD]->(f:Field)<-[:HAS_FIELD]-(e2)
        WITH e1, e2, shared_domains, domain_count, 
             COLLECT(DISTINCT f.name) as shared_fields, COUNT(DISTINCT f) as field_count
        
        // Calculate skill overlap
        OPTIONAL MATCH (e1)-[:HAS_SKILL]->(s:Skill)<-[:HAS_SKILL]-(e2)
        WITH e1, e2, shared_domains, domain_count, 
             shared_fields, field_count,
             COLLECT(DISTINCT s.name) as shared_skills, COUNT(DISTINCT s) as skill_count
        
        // Calculate weighted similarity score
        WITH e2, 
             shared_domains, domain_count,
             shared_fields, field_count,
             shared_skills, skill_count,
             (domain_count * 3 + field_count * 2 + skill_count) / 
             (CASE WHEN domain_count + field_count + skill_count = 0 
                   THEN 1 
                   ELSE domain_count + field_count + skill_count 
              END) as similarity_score
        
        WHERE similarity_score > 0
        
        RETURN {
            id: e2.id,
            name: e2.name,
            shared_domains: shared_domains,
            shared_fields: shared_fields,
            shared_skills: shared_skills,
            domain_count: domain_count,
            field_count: field_count,
            skill_count: skill_count,
            similarity_score: similarity_score
        } as result
        ORDER BY similarity_score DESC
        LIMIT $limit
        """
        
        try:
            with self._neo4j.session() as session:
                result = session.run(query, {
                    "expert_id": expert_id,
                    "limit": limit
                })
                
                similar_experts = []
                for record in result:
                    expert_data = record["result"]
                    similar_experts.append({
                        "id": expert_data["id"],
                        "name": expert_data["name"],
                        "similarity_score": expert_data["similarity_score"],
                        "shared_domains": expert_data["shared_domains"],
                        "shared_fields": expert_data["shared_fields"],
                        "shared_skills": expert_data["shared_skills"],
                        "match_details": {
                            "domains": expert_data["domain_count"],
                            "fields": expert_data["field_count"],
                            "skills": expert_data["skill_count"]
                        }
                    })
                
                return similar_experts
                
        except Exception as e:
            self._logger.error(f"Error finding similar experts: {e}")
            return []

    async def get_collaboration_recommendations(self, expert_id: str) -> List[Dict[str, Any]]:
        """Get recommendations with detailed collaboration metrics."""
        try:
            with self._neo4j.session() as session:
                # First get expert's current expertise
                expertise_query = """
                MATCH (e:Expert {id: $expert_id})
                OPTIONAL MATCH (e)-[:HAS_DOMAIN]->(d:Domain)
                OPTIONAL MATCH (e)-[:HAS_FIELD]->(f:Field)
                OPTIONAL MATCH (e)-[:HAS_SKILL]->(s:Skill)
                RETURN {
                    domains: collect(DISTINCT d.name),
                    fields: collect(DISTINCT f.name),
                    skills: collect(DISTINCT s.name)
                } as expertise
                """
                
                expertise = session.run(expertise_query, {"expert_id": expert_id}).single()["expertise"]
                
                # Find potential collaborators
                collab_query = """
                MATCH (e1:Expert {id: $expert_id})
                MATCH (e2:Expert)
                WHERE e1 <> e2
                
                // Find complementary expertise
                OPTIONAL MATCH (e2)-[:HAS_DOMAIN]->(d:Domain)
                WHERE NOT (e1)-[:HAS_DOMAIN]->(d)
                WITH e1, e2, COLLECT(DISTINCT d.name) as complementary_domains
                
                // Find shared domains for context
                OPTIONAL MATCH (e1)-[:HAS_DOMAIN]->(sd:Domain)<-[:HAS_DOMAIN]-(e2)
                WITH e1, e2, complementary_domains, 
                     COLLECT(DISTINCT sd.name) as shared_domains,
                     COUNT(DISTINCT sd) as domain_overlap
                
                // Calculate collaboration score
                WITH e2, 
                     complementary_domains,
                     shared_domains,
                     domain_overlap,
                     (domain_overlap * 0.6 + size(complementary_domains) * 0.4) as collaboration_score
                WHERE collaboration_score > 0
                
                RETURN {
                    id: e2.id,
                    name: e2.name,
                    complementary_domains: complementary_domains,
                    shared_domains: shared_domains,
                    collaboration_score: collaboration_score,
                    domain_overlap: domain_overlap
                } as recommendation
                ORDER BY collaboration_score DESC
                LIMIT 5
                """
                
                results = session.run(collab_query, {"expert_id": expert_id})
                recommendations = []
                
                for record in results:
                    rec = record["recommendation"]
                    recommendations.append({
                        "id": rec["id"],
                        "name": rec["name"],
                        "collaboration_score": rec["collaboration_score"],
                        "matched_domains": rec["domain_overlap"],
                        "shared_domains": rec["shared_domains"],
                        "complementary_expertise": rec["complementary_domains"]
                    })
                
                return recommendations
                
        except Exception as e:
            self._logger.error(f"Error getting collaboration recommendations: {e}")
            return []

    def close(self):
        """Close Neo4j connection"""
        if self._neo4j:
            self._neo4j.close()
