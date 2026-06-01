from fastapi import FastAPI

from api.internal.admin_router import router as admin_router
from api.search_router import router as search_router

app = FastAPI(title="BeautyMatch AI Server")

app.include_router(admin_router)
app.include_router(search_router)
