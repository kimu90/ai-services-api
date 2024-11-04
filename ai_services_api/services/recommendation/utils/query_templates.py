class QueryTemplates:
    @staticmethod
    def get_author_details():
        return """
        MATCH (a:Author {author_id: $author_id})
        RETURN a.author_name, a.work_count, a.total_citations, a.avg_citations
        """

    @staticmethod
    def get_work_details():
        return """
        MATCH (w:Work {work_id: $work_id})
        OPTIONAL MATCH (w)-[:RELATED_TO]->(t:Topic)
        RETURN w.title, w.impact_score, COLLECT(t.topic_name) as topics
        """

# utils/score_calculator.py
class ScoreCalculator:
    @staticmethod
    def calculate_recommendation_score(citation_count, topic_overlap, author_impact):
        """Calculate recommendation score based on multiple factors"""
        citation_weight = 0.4
        topic_weight = 0.3
        author_weight = 0.3
        
        normalized_citations = min(1.0, citation_count / 100)
        normalized_topic_overlap = topic_overlap / 10
        normalized_author_impact = min(1.0, author_impact / 50)
        
        return (citation_weight * normalized_citations +
                topic_weight * normalized_topic_overlap +
                author_weight * normalized_author_impact)