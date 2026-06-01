from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.internal.recognize_router import router as recognize_router
from api.internal.agent_router import router as agent_router

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


@app.on_event("startup")
async def startup_event():
    # bge-m3 사전 로드 — embedding_service 완성 후 아래 주석 해제
    # from services.embedding_service import warmup
    # await warmup()
    pass
