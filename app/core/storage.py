# app/core/storage.py

import os
import uuid
from supabase import create_client, Client
from fastapi import UploadFile, HTTPException

# 1. Load Config
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# 2. Init Client (Graceful Failure)
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
except Exception as e:
    print(f"⚠️ Supabase Init Failed: {e}")
    supabase = None

BUCKET_NAME = "application-docs"
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB Cap

async def upload_proof_document(file: UploadFile, student_id: uuid.UUID) -> str:
    """
    Uploads a PDF file to Supabase Storage.
    - Validates MIME type.
    - Ignores original filename (sanitizes input).
    - Returns internal storage path.
    """
    if not supabase:
        print("❌ Error: Supabase credentials missing in env vars.")
        raise HTTPException(500, "Storage service unavailable.")

    # 1. Strict PDF Validation
    if file.content_type != "application/pdf":
        raise HTTPException(400, "Only PDF files are allowed.")
    
    # 2. Size Validation
    # We read the file into memory to check size. 
    # For <10MB files, this is safe and fast.
    file_content = await file.read()
    
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB.")
    
    # Reset file cursor (Important because we just read it!)
    await file.seek(0)

    # 3. Generate SAFE Filename
    # Strategy: Ignore user's filename completely. Use UUID + .pdf
    # This prevents errors with spaces, emojis, or missing extensions.
    safe_filename = f"{uuid.uuid4()}.pdf"
    file_path = f"{student_id}/{safe_filename}"

    try:
        # 4. Upload to Supabase
        # 'upsert': 'true' overwrites if a file somehow has the exact same UUID (impossible, but safe)
        supabase.storage.from_(BUCKET_NAME).upload(
            path=file_path,
            file=file_content,
            file_options={"content-type": "application/pdf", "upsert": "true"}
        )
        
        return file_path

    except Exception as e:
        print(f"❌ Storage Upload Error: {e}")
        # Return generic error to user, log specific error to console
        raise HTTPException(500, "Failed to upload document to cloud storage.")

def get_signed_url(file_path: str, expiration=3600) -> str:
    """
    Generates a temporary public link for the private file.
    Valid for 1 hour by default.
    """
    if not file_path or not supabase:
        return None
        
    try:
        response = supabase.storage.from_(BUCKET_NAME).create_signed_url(file_path, expiration)
        
        # Handle different Supabase Python SDK response versions
        if isinstance(response, dict):
            return response.get("signedURL")
        elif hasattr(response, "signedURL"):
            return response.signedURL
        
        return str(response)  # Fallback
        
    except Exception as e:
        print(f"⚠️ Failed to sign URL for {file_path}: {e}")
        return None