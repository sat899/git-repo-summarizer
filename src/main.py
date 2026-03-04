from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from src.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient() as client:
        app.state.httpx_client = client
        yield


app = FastAPI(lifespan=lifespan)
app.include_router(router)