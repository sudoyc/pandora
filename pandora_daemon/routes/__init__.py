from fastapi import APIRouter
from pandora_daemon.routes.browse import router as browse_router
from pandora_daemon.routes.config_routes import router as config_router
from pandora_daemon.routes.downloads import router as downloads_router
from pandora_daemon.routes.favorites import router as favorites_router
from pandora_daemon.routes.gallery import router as gallery_router
from pandora_daemon.routes.tags import router as tags_router
from pandora_daemon.routes.user import router as user_router

router = APIRouter()
router.include_router(browse_router)
router.include_router(favorites_router)
router.include_router(gallery_router)
router.include_router(downloads_router)
router.include_router(user_router)
router.include_router(config_router)
router.include_router(tags_router)
