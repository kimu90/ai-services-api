from redis.commands.graph import Graph
import redis
import pandas as pd
import os

class GraphConnector:
    def __init__(self, host='localhost', port=6379):
        self.redis_conn = redis.Redis(host=host, port=port)
        self.graph = Graph(self.redis_conn, 'literature_graph')

    def create_indices(self):
        """Create indices for better query performance"""
        try:
            self.graph.query("""
                CREATE INDEX ON :Author(author_id);
                CREATE INDEX ON :Work(work_id);
                CREATE INDEX ON :Topic(topic_id)
            """)
        except redis.exceptions.ResponseError as e:
            if "Index already exists" not in str(e):
                raise e

    def load_data(self, data_path):
        """Load data from CSV files and create graph"""
        # Load CSV files
        authors_df = pd.read_csv(os.path.join(data_path, 'authors.csv'))
        topics_df = pd.read_csv(os.path.join(data_path, 'topics.csv'))
        works_df = pd.read_csv(os.path.join(data_path, 'works.csv'))
        related_works_df = pd.read_csv(os.path.join(data_path, 'related_works.csv'))

        # Create nodes
        self._create_author_nodes(authors_df)
        self._create_topic_nodes(topics_df)
        self._create_work_nodes(works_df)

        # Create relationships
        self._create_authorship_edges(authors_df)
        self._create_topic_edges(works_df)
        self._create_citation_edges(related_works_df)

    def _create_author_nodes(self, authors_df):
        for _, row in authors_df.drop_duplicates('author_id').iterrows():
            self.graph.query(
                """
                MERGE (:Author {
                    author_id: $author_id,
                    author_name: $author_name
                })
                """,
                params={
                    'author_id': row['author_id'],
                    'author_name': row['author_name']
                }
            )

    def _create_topic_nodes(self, topics_df):
        for _, row in topics_df.iterrows():
            self.graph.query(
                """
                MERGE (:Topic {
                    topic_id: $topic_id,
                    topic_name: $topic_name
                })
                """,
                params={
                    'topic_id': row['topic_id'],
                    'topic_name': row['topic_name']
                }
            )

    def _create_work_nodes(self, works_df):
        for _, row in works_df.iterrows():
            self.graph.query(
                """
                MERGE (:Work {
                    work_id: $work_id,
                    title: $title
                })
                """,
                params={
                    'work_id': row['id'],
                    'title': row['title']
                }
            )

    def _create_authorship_edges(self, authors_df):
        for _, row in authors_df.iterrows():
            self.graph.query(
                """
                MATCH (a:Author {author_id: $author_id})
                MATCH (w:Work {work_id: $work_id})
                MERGE (a)-[:AUTHORED]->(w)
                """,
                params={
                    'author_id': row['author_id'],
                    'work_id': row['work_id']
                }
            )

    def _create_topic_edges(self, works_df):
        for _, row in works_df.iterrows():
            self.graph.query(
                """
                MATCH (w:Work {work_id: $work_id})
                MATCH (t:Topic {topic_id: $topic_id})
                MERGE (w)-[:RELATED_TO]->(t)
                """,
                params={
                    'work_id': row['id'],
                    'topic_id': row['topic_id']
                }
            )

    def _create_citation_edges(self, related_works_df):
        for _, row in related_works_df.iterrows():
            self.graph.query(
                """
                MATCH (w1:Work {work_id: $work_id})
                MATCH (w2:Work {work_id: $related_work_id})
                MERGE (w1)-[:CITED_BY]->(w2)
                """,
                params={
                    'work_id': row['work_id'],
                    'related_work_id': row['related_work_id']
                }
            )