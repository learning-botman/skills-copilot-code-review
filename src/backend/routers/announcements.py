"""Announcement management endpoints."""

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from ..database import announcements_collection, teachers_collection

router = APIRouter(prefix="/announcements", tags=["announcements"])


def _validate_dates(start_date: Optional[str], expiration_date: str) -> None:
    try:
        expiration = date.fromisoformat(expiration_date)
        start = date.fromisoformat(start_date) if start_date else None
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Dates must use YYYY-MM-DD format") from error

    if start and start > expiration:
        raise HTTPException(status_code=400, detail="Start date must be before expiration date")


def _require_teacher(username: Optional[str]) -> None:
    if not username or not teachers_collection.find_one({"_id": username}):
        raise HTTPException(status_code=401, detail="Teacher authentication required")


def _serialize(announcement: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": announcement["_id"],
        "message": announcement["message"],
        "start_date": announcement.get("start_date"),
        "expiration_date": announcement["expiration_date"],
    }


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Return announcements that are currently visible to visitors."""
    today = date.today().isoformat()
    query = {
        "expiration_date": {"$gte": today},
        "$or": [{"start_date": {"$exists": False}}, {"start_date": None}, {"start_date": {"$lte": today}}],
    }
    return [_serialize(item) for item in announcements_collection.find(query).sort("expiration_date", 1)]


@router.get("/manage", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """Return all announcements for authenticated teachers."""
    _require_teacher(teacher_username)
    return [_serialize(item) for item in announcements_collection.find().sort("expiration_date", 1)]


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    message: str,
    expiration_date: str,
    start_date: Optional[str] = None,
    teacher_username: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Create an announcement for an authenticated teacher."""
    _require_teacher(teacher_username)
    if not message.strip():
        raise HTTPException(status_code=400, detail="Announcement message is required")
    _validate_dates(start_date, expiration_date)

    announcement = {
        "_id": str(uuid4()),
        "message": message.strip(),
        "start_date": start_date,
        "expiration_date": expiration_date,
    }
    announcements_collection.insert_one(announcement)
    return _serialize(announcement)


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    message: str,
    expiration_date: str,
    start_date: Optional[str] = None,
    teacher_username: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Update an announcement for an authenticated teacher."""
    _require_teacher(teacher_username)
    if not message.strip():
        raise HTTPException(status_code=400, detail="Announcement message is required")
    _validate_dates(start_date, expiration_date)

    updated = {
        "message": message.strip(),
        "start_date": start_date,
        "expiration_date": expiration_date,
    }
    result = announcements_collection.update_one({"_id": announcement_id}, {"$set": updated})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return _serialize({"_id": announcement_id, **updated})


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    teacher_username: Optional[str] = Query(None),
) -> Dict[str, str]:
    """Delete an announcement for an authenticated teacher."""
    _require_teacher(teacher_username)
    result = announcements_collection.delete_one({"_id": announcement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return {"message": "Announcement deleted"}