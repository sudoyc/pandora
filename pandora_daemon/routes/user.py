"""User routes for pandora-daemon.

Provides endpoints for user home, profile, and tag management.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from pandora_daemon.dependencies import get_gallery_provider

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
async def get_home(provider=Depends(get_gallery_provider)):
    """Return user home detail including image limits."""
    detail = await provider.get_home_detail()
    return _home_detail_to_dict(detail)


@router.post("/home/reset_limit")
async def reset_limit(provider=Depends(get_gallery_provider)):
    """Reset the image limit and return updated home detail."""
    detail = await provider.reset_image_limit()
    return _home_detail_to_dict(detail)


@router.get("/profile")
async def get_profile(provider=Depends(get_gallery_provider)):
    """Return user profile information."""
    profile = await provider.get_profile()
    return _profile_to_dict(profile)


@router.get("/tags")
async def get_tags(provider=Depends(get_gallery_provider)):
    """Return the user's watched/hidden tag list."""
    tags = await provider.get_mytags()
    return [_watched_tag_to_dict(tag) for tag in tags]


@router.post("/tags")
async def add_tag(body: AddTagBody, provider=Depends(get_gallery_provider)):
    """Add a new tag to the user's tag list."""
    await provider.add_tag(
        body.name,
        watched=body.watched,
        hidden=body.hidden,
        color=body.color,
        weight=body.weight,
    )
    return {"ok": True}


@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: int, provider=Depends(get_gallery_provider)):
    """Delete a tag from the user's tag list by ID."""
    await provider.delete_tag(tag_id)
    return {"ok": True}
