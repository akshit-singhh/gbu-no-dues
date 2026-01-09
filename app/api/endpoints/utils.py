from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.core.storage import upload_proof_document
from app.models.user import User, UserRole
from app.core.rbac import AllowRoles

router = APIRouter(prefix="/api/utils", tags=["Utilities"])

@router.post("/upload-proof")
async def upload_proof(
    file: UploadFile = File(...),
    current_user: User = Depends(AllowRoles(UserRole.Student))
):
    """
    Step 1 of Submission:
    Uploads the PDF to private storage and returns the internal FILE PATH.
    """
    if not current_user.student_id:
        raise HTTPException(400, "Student profile required.")
    
    try:
        # Returns the internal path (e.g., "user_uuid/file_uuid.pdf")
        file_path = await upload_proof_document(file, current_user.student_id)
        return {"path": file_path}

    except HTTPException as e:
        # we re-raise it exactly so the user sees the real reason.
        raise e
        
    except Exception as e:
        # Only catch unexpected crashes here
        print(f"Upload Endpoint Error: {e}")
        raise HTTPException(500, "Failed to upload file (Internal Error).")