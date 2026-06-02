import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from api.internal.recognize_router import router as recognize_router
from api.internal.agent_router import router as agent_router
from api.search_router import router as search_router

# LangSmith 트레이싱 활성화 (LANGSMITH_API_KEY가 있을 때만)
if settings.LANGSMITH_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT

app = FastAPI(title="Cosmetic AI Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 운영 환경에서는 Spring Backend 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recognize_router, prefix="/internal")
app.include_router(agent_router, prefix="/internal")
app.include_router(search_router)


@app.on_event("startup")
async def startup_event():
    # bge-m3 사전 로드 — embedding_service 완성 후 아래 주석 해제
    # from services.embedding_service import warmup
    # await warmup()
    pass
