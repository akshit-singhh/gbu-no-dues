# app/api/endpoints/captcha.py

from fastapi import APIRouter, Response, Request  # <--- IMPORT Request
from captcha.image import ImageCaptcha
import random
import string
import hashlib
import base64
from app.core.config import settings
from app.core.rate_limiter import limiter  # <--- IMPORT LIMITER

router = APIRouter(prefix="/api/captcha", tags=["Captcha"])
image_generator = ImageCaptcha(width=280, height=90)

def hash_captcha(text: str) -> str:
    normalized = text.strip().upper()
    raw_str = f"{normalized}{settings.SECRET_KEY}"
    return hashlib.sha256(raw_str.encode()).hexdigest()

@router.get("/generate")
@limiter.limit("10/minute")  # <--- RATE LIMIT: 10 per minute per IP
async def generate_captcha(request: Request):  # <--- MANDATORY: 'request' arg required
    """
    Generates a CAPTCHA image and returns it as Base64 along with a cryptographic hash.
    Rate Limited to prevent CPU exhaustion attacks.
    """
    # 1. Generate Text (Reduced to 5 chars for readability)
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    
    # 2. Generate Image & Convert to Base64
    data = image_generator.generate(captcha_text)
    base64_image = base64.b64encode(data.read()).decode('utf-8')
    
    # 3. Generate Hash
    secure_hash = hash_captcha(captcha_text)
    
    # 4. Return JSON (No Cookies!)
    return {
        "image": f"data:image/png;base64,{base64_image}",
        "captcha_hash": secure_hash
    }