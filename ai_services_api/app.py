from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from fastapi.security import OAuth2PasswordBearer


app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# app.include_router(project_routes.router, prefix="/api/v1", tags=["projects"])



@app.get("/health")
def hello() -> str:
    return "Hello World!"