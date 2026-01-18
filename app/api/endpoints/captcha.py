# app/api/endpoints/captcha.py

from fastapi import APIRouter, Response, Request
from captcha.image import ImageCaptcha
import random
import string
import hashlib
import base64
from io import BytesIO  # <--- IMPORT BytesIO
from PIL import Image   # <--- IMPORT Image from Pillow
from app.core.config import settings
from app.core.rate_limiter import limiter

router = APIRouter(prefix="/api/captcha", tags=["Captcha"])

# We don't instantiate a global generator here anymore because
# we need to manipulate the image size dynamically.

def hash_captcha(text: str) -> str:
    normalized = text.strip().upper()
    raw_str = f"{normalized}{settings.SECRET_KEY}"
    return hashlib.sha256(raw_str.encode()).hexdigest()

@router.get("/generate")
@limiter.limit("10/minute")
async def generate_captcha(request: Request):
    """
    Generates a Centered CAPTCHA image.
    Strategy: Generate a smaller image that fits the text tightly, 
    then paste it into the center of the final 280x90 canvas.
    """
    # 1. Generate Text
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    
    # --- CENTERING LOGIC START ---
    
    # A. Define dimensions
    final_width, final_height = 280, 90
    
    # Calculate a "tight" width based on char count to force them together.
    # For height 90, font size is usually ~70. 5 chars need approx 180-200px.
    tight_width = 250 
    
    # B. Generate the tight captcha image (PIL Image object)
    # This forces the library to use the available space, reducing side gaps.
    generator = ImageCaptcha(width=tight_width, height=final_height)
    tight_image = generator.generate_image(captcha_text)
    
    # C. Create the final background canvas (White)
    final_image = Image.new('RGB', (final_width, final_height), (255, 255, 255))
    
    # D. Calculate center position (x, y)
    center_x = (final_width - tight_width) // 2
    center_y = 0 # Heights match, so 0 offset
    
    # E. Paste the tight captcha into the center
    final_image.paste(tight_image, (center_x, center_y))
    
    # F. Save to BytesIO buffer
    buffer = BytesIO()
    final_image.save(buffer, format='PNG')
    buffer.seek(0)
    
    # --- CENTERING LOGIC END ---

    # 2. Convert to Base64
    base64_image = base64.b64encode(buffer.read()).decode('utf-8')
    
    # 3. Generate Hash
    secure_hash = hash_captcha(captcha_text)
    
    # 4. Return JSON
    return {
        "image": f"data:image/png;base64,{base64_image}",
        "captcha_hash": secure_hash
    }