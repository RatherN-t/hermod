"""Doctor-facing pages: patient list, adherence timeline, open flags, add prescription."""
from fastapi import APIRouter

router = APIRouter(prefix="/doctor", tags=["dashboard"])
