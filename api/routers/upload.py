"""File upload endpoints."""

from fastapi import APIRouter, UploadFile, HTTPException

from api.models import UploadResponse
from api.services import file_store

router = APIRouter(prefix="/api", tags=["upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile):
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(400, "Only .xlsx files are supported")
    data = await file.read()
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 50 MB)")
    file_id = file_store.save_file(file.filename, data)
    return UploadResponse(
        file_id=file_id,
        filename=file.filename,
        size_bytes=len(data),
    )


@router.delete("/upload/{file_id}")
async def delete_uploaded_file(file_id: str):
    if not file_store.delete_file(file_id):
        raise HTTPException(404, "File not found")
    return {"ok": True}
