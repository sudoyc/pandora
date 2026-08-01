from fastapi import APIRouter
from pandora_daemon.routes.bookmarks import router as bookmarks_router
from pandora_daemon.routes.browse import router as browse_router
from pandora_daemon.routes.config import router as config_router
from pandora_daemon.routes.downloads import router as downloads_router
from pandora_daemon.routes.favorites import router as favorites_router
from pandora_daemon.routes.filters import router as filters_router
from pandora_daemon.routes.gallery import router as gallery_router
from pandora_daemon.routes.history import router as history_router
from pandora_daemon.routes.library import router as library_router
from pandora_daemon.routes.local_favorites import router as local_favorites_router
from pandora_daemon.routes.quick_search import router as quick_search_router
from pandora_daemon.routes.readiness import router as readiness_router
from pandora_daemon.routes.tags import router as tags_router
from pandora_daemon.routes.user import router as user_router

router = APIRouter()
router.include_router(browse_router)
router.include_router(favorites_router)
router.include_router(gallery_router)
router.include_router(downloads_router)
router.include_router(config_router)
router.include_router(readiness_router)
router.include_router(tags_router)
router.include_router(user_router)
router.include_router(library_router)
router.include_router(history_router)
router.include_router(local_favorites_router)
router.include_router(bookmarks_router)
router.include_router(quick_search_router)
router.include_router(filters_router)
