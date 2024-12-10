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
        """
        Use Gemini to analyze and categorize expertise
        """
        prompt = f"""
        Analyze these areas of expertise: {', '.join(expertise_list)}
        
        Please provide:
        1. Main research domains
        2. Specific research areas
        3. Technical skills
        4. Potential applications
        5. Related fields
        
        Return as a JSON structure with these exact keys:
        {{
            "domains": [],
            "research_areas": [],
            "technical_skills": [],
            "applications": [],
            "related_fields": []
        }}
        """

        try:
            response = model.generate_content(prompt)
            analysis = eval(response.text)
            logger.info(f"Successfully analyzed expertise using Gemini")
            return analysis
        except Exception as e:
            logger.error(f"Error analyzing expertise with Gemini: {e}")
            return {
                "domains": expertise_list[:2],
                "research_areas": expertise_list[2:4],
                "technical_skills": expertise_list[4:],
                "applications": [],
                "related_fields": []
            }

    async def find_similar_experts(self, expert_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find similar experts using both graph analysis and semantic similarity
        """
        # First, get the expert's expertise
        query = """
        MATCH (e:Expert {id: $expert_id})
        OPTIONAL MATCH (e)-[:HAS_DOMAIN]->(d:Domain)
        OPTIONAL MATCH (e)-[:HAS_FIELD]->(f:Field)
        OPTIONAL MATCH (e)-[:HAS_SKILL]->(s:Skill)
        RETURN {
            id: e.id,
            name: e.name,
            domains: collect(DISTINCT d.name),
            fields: collect(DISTINCT f.name),
            skills: collect(DISTINCT s.name)
        } as expert
        """

        try:
            with self._neo4j.session() as session:
                result = session.run(query, {"expert_id": expert_id})
                expert_data = result.single()["expert"]
                
                if not expert_data:
                    logger.warning(f"No data found for expert {expert_id}")
                    return []

                # Get all expertise items
                expertise_items = (
                    expert_data["domains"] +
                    expert_data["fields"] +
                    expert_data["skills"]
                )

                # Use Gemini to analyze expertise
                expertise_analysis = await self.analyze_expertise(expertise_items)

                # Use the analysis to find similar experts
                similar_experts_query = """
                MATCH (e:Expert)
                WHERE e.id <> $expert_id
                
                // Match against analyzed domains
                OPTIONAL MATCH (e)-[:HAS_DOMAIN]->(d:Domain)
                WHERE d.name IN $domains
                WITH e, COUNT(DISTINCT d) as domain_matches
                
                // Match against research areas
                OPTIONAL MATCH (e)-[:HAS_FIELD]->(f:Field)
                WHERE f.name IN $research_areas
                WITH e, domain_matches, COUNT(DISTINCT f) as field_matches
                
                // Match against skills
                OPTIONAL MATCH (e)-[:HAS_SKILL]->(s:Skill)
                WHERE s.name IN $skills
                WITH e, domain_matches, field_matches, COUNT(DISTINCT s) as skill_matches
                
                // Calculate weighted score
                WITH e,
                     domain_matches * 3 + 
                     field_matches * 2 + 
                     skill_matches as score
                WHERE score > 0
                
                RETURN {
                    id: e.id,
                    name: e.name,
                    similarity_score: score,
                    matched_domains: domain_matches,
                    matched_fields: field_matches,
                    matched_skills: skill_matches
                } as similar_expert
                ORDER BY score DESC
                LIMIT $limit
                """

                result = session.run(similar_experts_query, {
                    "expert_id": expert_id,
                    "domains": expertise_analysis["domains"],
                    "research_areas": expertise_analysis["research_areas"],
                    "skills": expertise_analysis["technical_skills"],
                    "limit": limit
                })

                similar_experts = [record["similar_expert"] for record in result]
                return similar_experts

        except Exception as e:
            logger.error(f"Error finding similar experts: {e}")
            return []

    async def get_collaboration_recommendations(self, expert_id: str) -> List[Dict[str, Any]]:
        """
        Get recommendations for potential collaborations based on expertise overlap
        and research complementarity
        """
        try:
            # Get expert's current expertise
            with self._neo4j.session() as session:
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
                
                result = session.run(expertise_query, {"expert_id": expert_id})
                expertise = result.single()["expertise"]

                # Use Gemini to analyze potential collaboration opportunities
                prompt = f"""
                Given an expert with:
                Domains: {expertise['domains']}
                Fields: {expertise['fields']}
                Skills: {expertise['skills']}

                Please suggest complementary expertise that would be valuable for collaboration.
                Return as a JSON structure with:
                {{
                    "complementary_domains": [],
                    "complementary_skills": [],
                    "collaboration_potential": []
                }}
                """

                response = model.generate_content(prompt)
                suggestions = eval(response.text)

                # Find experts matching the suggestions
                recommendations_query = """
                MATCH (e:Expert)
                WHERE e.id <> $expert_id
                
                // Match suggested complementary domains
                OPTIONAL MATCH (e)-[:HAS_DOMAIN]->(d:Domain)
                WHERE d.name IN $complementary_domains
                WITH e, COUNT(DISTINCT d) as domain_matches
                
                // Match suggested complementary skills
                OPTIONAL MATCH (e)-[:HAS_SKILL]->(s:Skill)
                WHERE s.name IN $complementary_skills
                WITH e, domain_matches, COUNT(DISTINCT s) as skill_matches
                
                WHERE domain_matches > 0 OR skill_matches > 0
                
                RETURN {
                    id: e.id,
                    name: e.name,
                    matched_domains: domain_matches,
                    matched_skills: skill_matches,
                    collaboration_score: domain_matches * 2 + skill_matches
                } as recommendation
                ORDER BY recommendation.collaboration_score DESC
                LIMIT 5
                """

                result = session.run(recommendations_query, {
                    "expert_id": expert_id,
                    "complementary_domains": suggestions["complementary_domains"],
                    "complementary_skills": suggestions["complementary_skills"]
                })

                recommendations = [record["recommendation"] for record in result]
                return recommendations

        except Exception as e:
            logger.error(f"Error getting collaboration recommendations: {e}")
            return []

    def close(self):
        """Close Neo4j connection"""
        if self._neo4j:
            self._neo4j.close()