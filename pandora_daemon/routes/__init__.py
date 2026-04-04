from fastapi import APIRouter
from pandora_daemon.routes.browse import router as browse_router

router = APIRouter()
router.include_router(browse_router)
