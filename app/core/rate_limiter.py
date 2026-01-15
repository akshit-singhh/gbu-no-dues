# app/core/rate_limiter.py

from slowapi import Limiter
from slowapi.util import get_remote_address

# We use get_remote_address to identify users by IP.
# If you are behind Nginx/Cloudflare later, this might need tweaking to look at X-Forwarded-For headers.
limiter = Limiter(key_func=get_remote_address)