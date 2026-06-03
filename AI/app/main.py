from fastapi import FastAPI

from api.internal.admin_router import router as admin_router
from api.internal.review_admin_router import router as review_admin_router
from api.internal.agent_router import router as agent_router
from api.internal.recognize_router import router as recognize_router
from api.search_router import router as search_router

app = FastAPI(title="BeautyMatch AI Server")

app.include_router(admin_router)
app.include_router(review_admin_router)
app.include_router(agent_router, prefix="/internal")
app.include_router(recognize_router, prefix="/internal")
app.include_router(search_router, prefix="/internal")
