from fastapi import APIRouter
from app.api.routers.authentication import router as auth_router

http_router_v1 = APIRouter(prefix="/api/v1")


http_router_v1.include_router(auth_router)


@http_router_v1.get("/ping")
async def ping():
    return {"status": "ok"}
