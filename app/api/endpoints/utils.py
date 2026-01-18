from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request
from app.core.storage import upload_proof_document
from app.models.user import User, UserRole
from app.core.rbac import AllowRoles
from app.core.rate_limiter import limiter
# Added get_current_user for manual role inspection
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request
from app.core.storage import upload_proof_document
from app.models.user import User, UserRole
from app.core.rbac import AllowRoles
from app.core.rate_limiter import limiter
# Setup simple logger for this module

router = APIRouter(prefix="/api/utils", tags=["Utilities"])
# ----------------------------------------------------------------
# UPLOAD PROOF DOCUMENT (Protected with Rate Limit)
# ----------------------------------------------------------------
@router.post("/upload-proof")
@limiter.limit("5/minute")
async def upload_proof(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(AllowRoles(UserRole.Student))
):
    """
    Step 1 of Submission: Uploads the PDF to private storage.
    """
    if not current_user.student_id:
        raise HTTPException(400, "Student profile required.")

    try:
        file_path = await upload_proof_document(file, current_user.student_id)
        return {"path": file_path}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Upload Endpoint Error: {e}")
        raise HTTPException(500, "Failed to upload file (Internal Error).")