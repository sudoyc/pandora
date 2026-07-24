from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Depends

from exhentai_api.exceptions import (
    AuthenticationError,
    ExhentaiError,
    NetworkError,
    ParseError,
    SessionError,
    UpstreamError,
)
from exhentai_api.models.search import SearchParams
from pandora_daemon.dependencies import get_state
from pandora_daemon.state import AppState


router = APIRouter(tags=["readiness"])
_READINESS_SEARCH_TERM = "pandora-readiness-probe"
_PROBE_TIMEOUT_SECONDS = 20.0


async def _run_probe(probe: Callable[[], Awaitable[Any]]) -> str:
    try:
        async with asyncio.timeout(_PROBE_TIMEOUT_SECONDS):
            await probe()
    except TimeoutError:
        return "network"
    except SessionError:
        return "session"
    except AuthenticationError:
        return "auth"
    except UpstreamError:
        return "upstream"
    except ParseError:
        return "parse"
    except NetworkError:
        return "network"
    except ExhentaiError:
        return "upstream"
    return "ok"


def _session_status(checks: dict[str, str]) -> str:
    statuses = set(checks.values())
    if statuses & {"auth", "session"}:
        return "invalid"
    if "ok" in statuses:
        return "valid"
    return "unknown"


@router.get("/api/readiness")
async def get_readiness(state: AppState = Depends(get_state)):
    credentials = state.config.credentials
    auth_configured = bool(credentials.igneous and credentials.ipb_member_id)
    if not auth_configured:
        return {
            "ready": False,
            "auth_configured": False,
            "session": "not_configured",
            "checks": {
                "homepage": "not_checked",
                "search": "not_checked",
                "popular": "not_checked",
                "home": "not_checked",
            },
        }

    probes = {
        "homepage": state.api.get_homepage,
        "search": lambda: state.api.search(
            SearchParams(f_search=_READINESS_SEARCH_TERM)
        ),
        "popular": state.api.get_popular,
        "home": state.api.get_home_detail,
    }
    statuses = await asyncio.gather(*(_run_probe(probe) for probe in probes.values()))
    checks = dict(zip(probes, statuses, strict=True))
    return {
        "ready": all(status == "ok" for status in checks.values()),
        "auth_configured": True,
        "session": _session_status(checks),
        "checks": checks,
    }
