from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Depends

from pandora_daemon.providers.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderNetworkError,
    ProviderParseError,
    ProviderSessionError,
    ProviderUpstreamError,
)
from pandora_daemon.dependencies import get_state
from pandora_daemon.providers import GallerySearchQuery
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
    except ProviderSessionError:
        return "session"
    except ProviderAuthenticationError:
        return "auth"
    except ProviderUpstreamError:
        return "upstream"
    except ProviderParseError:
        return "parse"
    except ProviderNetworkError:
        return "network"
    except ProviderError:
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
    auth_configured = state.provider.auth_configured
    if not auth_configured:
        return {
            "ready": False,
            "auth_configured": auth_configured,
            "session": "not_configured",
            "checks": {
                "homepage": "not_checked",
                "search": "not_checked",
                "popular": "not_checked",
                "home": "not_checked",
            },
        }

    probes = {
        "homepage": state.provider.get_homepage,
        "search": lambda: state.provider.search(
            GallerySearchQuery(keyword=_READINESS_SEARCH_TERM)
        ),
        "popular": state.provider.get_popular,
        "home": state.provider.get_home_detail,
    }
    statuses = await asyncio.gather(*(_run_probe(probe) for probe in probes.values()))
    checks = dict(zip(probes, statuses, strict=True))
    return {
        "ready": all(status == "ok" for status in checks.values()),
        "auth_configured": auth_configured,
        "session": _session_status(checks),
        "checks": checks,
    }
