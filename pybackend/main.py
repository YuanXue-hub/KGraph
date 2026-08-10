import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.extraction import router as extraction_router
from api.kos import router as kos_router
from api.dl import router as dl_router
from api.train import router as train_router
from core.graph_writer import GraphWriter
from core.llm_client import LLMClient

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_config() -> dict:
    with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
        return json.load(f)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    app.state.config = config
    app.state.llm_client = LLMClient(config)
    app.state.graph_writer = GraphWriter(config)
    try:
        yield
    finally:
        app.state.graph_writer.close()


app = FastAPI(title="KGraph Knowledge Extraction Backend", lifespan=lifespan)

# CORS 允许所有来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(extraction_router)
app.include_router(kos_router)
app.include_router(dl_router)
app.include_router(train_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
