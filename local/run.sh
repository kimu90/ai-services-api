#! /bin/bash

poetry run uvicorn ai_services_api.app:app --reload --host 0.0.0.0 --port 8000
#! /bin/bash

poetry run uvicorn ai_services_api.app:app --reload --host 0.0.0.0 --port 8000
poetry run uvicorn ai_services_api.main:app --host 0.0.0.0 --port 8000 --reload

PYTHONPATH=$PYTHONPATH:. python ai_services_api/services/recommendation/scripts/initialize_db.py
# Execute the script inside the api container
docker exec api-standalone python /code/Centralized-Repository/aphrc_limit.py
docker exec api-standalone python /code/Centralized-Repository/Database/create_database.py
docker exec api-standalone python /code/ai_services_api/services/search/index_creator.py
