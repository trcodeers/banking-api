
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine
from app import models


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Banking API",
    description="Account and transaction management API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health_check():
    return {"status": "ok"}
