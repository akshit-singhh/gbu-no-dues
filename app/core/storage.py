import os
import uuid
from supabase import create_client, Client
from fastapi import UploadFile, HTTPException

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

BUCKET_NAME = "application-docs"
MAX_FILE_SIZE = 10 * 1024 * 1024

async def upload_proof_document(file: UploadFile, student_id: uuid.UUID) -> str:
    """
    Uploads file and returns the INTERNAL STORAGE PATH (not the URL).
    Example return: "c553.../917c...pdf"
    """
    if not supabase:
        raise HTTPException(500, "Storage configuration missing.")

    if file.content_type != "application/pdf":
        raise HTTPException(400, "Only PDF files are allowed.")
    
    # ... (File size check remains same) ...
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large.")
    await file.seek(0)

    # Generate Path
    file_ext = file.filename.split(".")[-1]
    file_path = f"{student_id}/{uuid.uuid4()}.{file_ext}"

    try:
        supabase.storage.from_(BUCKET_NAME).upload(
            path=file_path,
            file=file_content,
            file_options={"content-type": "application/pdf"}
        )
        
        # ⚠️ CHANGE: We return the PATH, not the Public URL
        return file_path

    except Exception as e:
        print(f"❌ Storage Upload Error: {e}")
        raise HTTPException(500, "Failed to upload document.")

def get_signed_url(file_path: str, expiration=3600) -> str:
    """
    Generates a temporary Signed URL valid for 'expiration' seconds (default 1 hour).
    """
    if not file_path:
        return None
        
    try:
        # Ask Supabase for a temporary link
        response = supabase.storage.from_(BUCKET_NAME).create_signed_url(file_path, expiration)
        
        # Supabase returns a dict: {'signedURL': '...'} usually, or an object
        if isinstance(response, dict) and "signedURL" in response:
             return response["signedURL"]
        elif hasattr(response, "signedURL"): # Some SDK versions use attributes
             return response.signedURL
        # Fallback if the structure is different (debugging)
        return response['signedURL'] 
        
    except Exception as e:
        print(f"⚠️ Error generating signed URL: {e}")
        return None