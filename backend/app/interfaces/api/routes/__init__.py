from fastapi import APIRouter
from app.interfaces.api.routes.user import router as user_router
from app.interfaces.api.routes.agents import router as agents_router
from app.interfaces.api.routes.conversation import router as conversation_router

router = APIRouter()

router.include_router(user_router)
router.include_router(agents_router)
router.include_router(conversation_router)

__all__ = ["router"]
