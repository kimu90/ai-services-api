class DataEnricher:
    def __init__(self, graph_connector):
        self.graph = graph_connector.graph

    def calculate_work_metrics(self):
        """Calculate various metrics for works"""
        self.graph.query("""
            MATCH (w:Work)
            WITH w, SIZE((w)<-[:CITED_BY]-()) AS citation_count,
                 SIZE((w)-[:CITED_BY]->()) AS reference_count
            SET w.citation_count = citation_count,
                w.reference_count = reference_count,
                w.impact_score = CASE 
                    WHEN reference_count > 0 
                    THEN toFloat(citation_count) / reference_count 
                    ELSE 0 
                END
        """)

    def calculate_author_metrics(self):
        """Calculate metrics for authors"""
        self.graph.query("""
            MATCH (a:Author)-[:AUTHORED]->(w:Work)
            WITH a, COUNT(w) as work_count,
                 SUM(w.citation_count) as total_citations
            SET a.work_count = work_count,
                a.total_citations = total_citations,
                a.avg_citations = CASE 
                    WHEN work_count > 0 
                    THEN toFloat(total_citations) / work_count 
                    ELSE 0 
                END
        """)