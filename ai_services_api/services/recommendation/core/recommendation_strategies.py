class RecommendationStrategies:
    def __init__(self, graph_connector):
        self.graph = graph_connector.graph

    def get_collaborative_recommendations(self, author_id, limit=5):
        """Get recommendations based on collaboration patterns"""
        query = """
        MATCH (a:Author {author_id: $author_id})-[:AUTHORED]->(w1:Work)
        MATCH (w1)-[:CITED_BY]->(w2:Work)<-[:AUTHORED]-(other:Author)
        WHERE other.author_id <> $author_id
        WITH other, COUNT(DISTINCT w2) as collaboration_strength
        ORDER BY collaboration_strength DESC, other.total_citations DESC
        LIMIT $limit
        MATCH (other)-[:AUTHORED]->(recommended:Work)
        WHERE NOT EXISTS((a)-[:AUTHORED]->(recommended))
        RETURN DISTINCT recommended.work_id, recommended.title, recommended.impact_score
        LIMIT $limit
        """
        result = self.graph.query(query, params={'author_id': author_id, 'limit': limit})
        return result.result_set

    def get_content_based_recommendations(self, work_id, limit=5):
        """Get recommendations based on topic similarity"""
        query = """
        MATCH (w:Work {work_id: $work_id})-[:RELATED_TO]->(t:Topic)
        MATCH (t)<-[:RELATED_TO]-(similar:Work)
        WHERE similar.work_id <> $work_id
        WITH similar, COUNT(DISTINCT t) as topic_overlap
        ORDER BY topic_overlap DESC, similar.impact_score DESC
        RETURN DISTINCT similar.work_id, similar.title, similar.impact_score
        LIMIT $limit
        """
        result = self.graph.query(query, params={'work_id': work_id, 'limit': limit})
        return result.result_set