from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from src.services.search.index_creator import SearchIndexManager

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'publication_processing',
    default_args=default_args,
    description='Process and index publications',
    schedule_interval='@daily',
    start_date=datetime(2024, 1, 1),
    catchup=False
)

def process_publications():
    manager = SearchIndexManager()
    success = manager.create_index()
    if not success:
        raise Exception("Failed to process publications")

process_task = PythonOperator(
    task_id='process_publications',
    python_callable=process_publications,
    dag=dag
)

process_task