from fastapi import APIRouter
from pandora_daemon.routes.browse import router as browse_router
from pandora_daemon.routes.downloads import router as downloads_router
from pandora_daemon.routes.favorites import router as favorites_router
from pandora_daemon.routes.gallery import router as gallery_router

router = APIRouter()
router.include_router(browse_router)
router.include_router(favorites_router)
router.include_router(gallery_router)
router.include_router(downloads_router)
