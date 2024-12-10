import logging
from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load environment variables and configure Gemini
load_dotenv()
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

class Neo4jDatabase:
    def __init__(self):
        self._driver = GraphDatabase.driver(
            os.getenv('NEO4J_URI'),
            auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
        )
        self._logger = logging.getLogger(__name__)
        self._create_indexes()

    @contextmanager
    def _get_session(self):
        """Context manager for Neo4j session handling"""
        session = None
        try:
            session = self._driver.session()
            yield session
        except Exception as e:
            self._logger.error(f"Neo4j session error: {e}")
            raise
        finally:
            if session:
                session.close()

    def _create_indexes(self):
        """Create indexes for performance optimization"""
        index_queries = [
            "CREATE INDEX expert_id IF NOT EXISTS FOR (e:Expert) ON (e.id)",
            "CREATE INDEX domain_name IF NOT EXISTS FOR (d:Domain) ON (d.name)",
            "CREATE INDEX field_name IF NOT EXISTS FOR (f:Field) ON (f.name)",
            "CREATE INDEX expertise_name IF NOT EXISTS FOR (ex:Expertise) ON (ex.name)",
            "CREATE INDEX skill_name IF NOT EXISTS FOR (s:Skill) ON (s.name)"
        ]
        
        with self._get_session() as session:
            for query in index_queries:
                try:
                    session.run(query)
                    self._logger.info(f"Index created: {query}")
                except Exception as e:
                    self._logger.warning(f"Error creating index: {e}")

    async def get_similar_experts(self, expert_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find similar experts using a sophisticated matching algorithm
        that considers multiple relationship types and weights
        """
        query = """
        MATCH (e1:Expert {id: $expert_id})
        MATCH (e2:Expert)
        WHERE e1 <> e2
        
        // Calculate domain overlap
        OPTIONAL MATCH (e1)-[:HAS_DOMAIN]->(d:Domain)<-[:HAS_DOMAIN]-(e2)
        WITH e1, e2, COLLECT(d.name) as shared_domains, COUNT(d) as domain_count
        
        // Calculate field overlap
        OPTIONAL MATCH (e1)-[:HAS_FIELD]->(f:Field)<-[:HAS_FIELD]-(e2)
        WITH e1, e2, shared_domains, domain_count, 
             COLLECT(f.name) as shared_fields, COUNT(f) as field_count
        
        // Calculate skill overlap
        OPTIONAL MATCH (e1)-[:HAS_SKILL]->(s:Skill)<-[:HAS_SKILL]-(e2)
        WITH e1, e2, shared_domains, domain_count, 
             shared_fields, field_count,
             COLLECT(s.name) as shared_skills, COUNT(s) as skill_count
        
        // Calculate weighted similarity score
        WITH e2, shared_domains, domain_count, 
             shared_fields, field_count,
             shared_skills, skill_count,
             (domain_count * 3 + field_count * 2 + skill_count) / 
             (CASE WHEN domain_count + field_count + skill_count = 0 
                   THEN 1 
                   ELSE domain_count + field_count + skill_count 
              END) as similarity_score
        
        WHERE similarity_score > 0
        
        RETURN e2.id as expert_id,
               e2.name as name,
               shared_domains,
               shared_fields,
               shared_skills,
               similarity_score
        ORDER BY similarity_score DESC
        LIMIT $limit
        """
        
        try:
            with self._get_session() as session:
                result = session.run(query, {
                    "expert_id": expert_id,
                    "limit": limit
                })
                
                similar_experts = []
                for record in result:
                    expert = {
                        "expert_id": record["expert_id"],
                        "name": record["name"],
                        "shared_domains": record["shared_domains"],
                        "shared_fields": record["shared_fields"],
                        "shared_skills": record["shared_skills"],
                        "similarity_score": record["similarity_score"]
                    }
                    similar_experts.append(expert)
                
                return similar_experts
                
        except Exception as e:
            self._logger.error(f"Error finding similar experts: {e}")
            return []

    async def get_expert_clusters(self, min_cluster_size: int = 3) -> List[Dict[str, Any]]:
        """
        Find clusters of experts with similar expertise
        """
        query = """
        CALL gds.graph.project(
            'expertise_graph',
            ['Expert'],
            {
                HAS_DOMAIN: {
                    type: 'HAS_DOMAIN',
                    projection: 'UNDIRECTED'
                },
                HAS_FIELD: {
                    type: 'HAS_FIELD',
                    projection: 'UNDIRECTED'
                },
                HAS_SKILL: {
                    type: 'HAS_SKILL',
                    projection: 'UNDIRECTED'
                }
            }
        )
        
        CALL gds.louvain.stream('expertise_graph')
        YIELD nodeId, communityId
        WITH gds.util.asNode(nodeId) as expert, communityId
        WITH communityId, 
             COLLECT({id: expert.id, name: expert.name}) as members
        WHERE size(members) >= $min_cluster_size
        RETURN communityId, members
        ORDER BY size(members) DESC
        """
        
        try:
            with self._get_session() as session:
                result = session.run(query, {"min_cluster_size": min_cluster_size})
                clusters = []
                for record in result:
                    cluster = {
                        "cluster_id": record["communityId"],
                        "members": record["members"]
                    }
                    clusters.append(cluster)
                return clusters
        except Exception as e:
            self._logger.error(f"Error finding expert clusters: {e}")
            return []

    async def get_expertise_summary(self, expert_id: str) -> Dict[str, Any]:
        """
        Get a comprehensive summary of an expert's expertise and connections
        """
        query = """
        MATCH (e:Expert {id: $expert_id})
        
        // Get domains
        OPTIONAL MATCH (e)-[:HAS_DOMAIN]->(d:Domain)
        WITH e, COLLECT(d.name) as domains
        
        // Get fields
        OPTIONAL MATCH (e)-[:HAS_FIELD]->(f:Field)
        WITH e, domains, COLLECT(f.name) as fields
        
        // Get skills
        OPTIONAL MATCH (e)-[:HAS_SKILL]->(s:Skill)
        WITH e, domains, fields, COLLECT(s.name) as skills
        
        // Get collaboration network
        OPTIONAL MATCH (e)-[r]->(n)<-[]-(other:Expert)
        WHERE type(r) IN ['HAS_DOMAIN', 'HAS_FIELD', 'HAS_SKILL']
        WITH e, domains, fields, skills,
             COLLECT(DISTINCT {
                 expert_id: other.id,
                 name: other.name,
                 shared_expertise: n.name,
                 relationship_type: type(r)
             }) as collaborators
        
        RETURN {
            expert_id: e.id,
            name: e.name,
            domains: domains,
            fields: fields,
            skills: skills,
            collaborators: collaborators
        } as summary
        """
        
        try:
            with self._get_session() as session:
                result = session.run(query, {"expert_id": expert_id})
                summary = result.single()
                if summary:
                    return summary["summary"]
                return {}
        except Exception as e:
            self._logger.error(f"Error getting expertise summary: {e}")
            return {}

    async def find_expertise_paths(self, expert_id1: str, expert_id2: str, max_depth: int = 3) -> List[Dict[str, Any]]:
        """
        Find all expertise connection paths between two experts
        """
        query = """
        MATCH p = shortestPath(
            (e1:Expert {id: $expert_id1})-[*1..$max_depth]-(e2:Expert {id: $expert_id2})
        )
        WHERE ALL(r IN relationships(p) WHERE type(r) IN ['HAS_DOMAIN', 'HAS_FIELD', 'HAS_SKILL'])
        WITH p, 
             [n IN nodes(p) | CASE WHEN n:Expert THEN n.name 
                                  ELSE n.name END] as path_nodes,
             [r IN relationships(p) | type(r)] as path_rels
        RETURN {
            path_length: length(p),
            nodes: path_nodes,
            relationships: path_rels
        } as path
        ORDER BY path.path_length
        LIMIT 5
        """
        
        try:
            with self._get_session() as session:
                result = session.run(query, {
                    "expert_id1": expert_id1,
                    "expert_id2": expert_id2,
                    "max_depth": max_depth
                })
                return [record["path"] for record in result]
        except Exception as e:
            self._logger.error(f"Error finding expertise paths: {e}")
            return []

    def close(self):
        """Close the Neo4j driver connection"""
        if self._driver:
            try:
                self._driver.close()
                self._logger.info("Closed Neo4j driver connection")
            except Exception as e:
                self._logger.error(f"Error closing Neo4j connection: {e}")