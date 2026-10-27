
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine
from app import models
from app.routes import accounts, transactions
from app.routes import accounts, transactions


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Banking API",
    description="Account and transaction management API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(accounts.router)
app.include_router(transactions.router)
app.include_router(accounts.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
