"""User routes for pandora-daemon.

Provides endpoints for user home, profile, and tag management.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from pandora_daemon.dependencies import get_api

router = APIRouter(prefix="/api", tags=["user"])


class AddTagBody(BaseModel):
    name: str
    watched: bool = False
    hidden: bool = False
    color: str = ""
    weight: int = 0


def _home_detail_to_dict(detail) -> dict:
    return {
        "image_used": detail.image_used,
        "image_total": detail.image_total,
        "reset_cost": detail.reset_cost,
    }


def _profile_to_dict(profile) -> dict:
    return {
        "display_name": profile.display_name,
        "avatar_url": profile.avatar_url,
    }


def _watched_tag_to_dict(tag) -> dict:
    return {
        "id": tag.id,
        "name": tag.name,
        "watched": tag.watched,
        "hidden": tag.hidden,
        "color": tag.color,
        "weight": tag.weight,
    }


@router.get("/home")
async def get_home(api=Depends(get_api)):
    """Return user home detail including image limits."""
    detail = await api.get_home_detail()
    return _home_detail_to_dict(detail)


@router.post("/home/reset_limit")
async def reset_limit(api=Depends(get_api)):
    """Reset the image limit and return updated home detail."""
    detail = await api.reset_image_limit()
    return _home_detail_to_dict(detail)


@router.get("/profile")
async def get_profile(api=Depends(get_api)):
    """Return user profile information."""
    profile = await api.get_profile()
    return _profile_to_dict(profile)


@router.get("/tags")
async def get_tags(api=Depends(get_api)):
    """Return the user's watched/hidden tag list."""
    tags = await api.get_mytags()
    return [_watched_tag_to_dict(tag) for tag in tags]


@router.post("/tags")
async def add_tag(body: AddTagBody, api=Depends(get_api)):
    """Add a new tag to the user's tag list."""
    await api.add_tag(
        body.name,
        watched=body.watched,
        hidden=body.hidden,
        color=body.color,
        weight=body.weight,
    )
    return {"ok": True}


@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: int, api=Depends(get_api)):
    """Delete a tag from the user's tag list by ID."""
    await api.delete_tag(tag_id)
    return {"ok": True}
