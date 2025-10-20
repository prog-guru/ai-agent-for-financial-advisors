# app/security.py
import os, time
from jose import jwt, JWTError

JWT_SECRET = os.getenv("JWT_SECRET", "dev-session-secret")
JWT_ISS    = os.getenv("JWT_ISS", "ai-agent-backend")
JWT_AUD    = os.getenv("JWT_AUD", "ai-agent-frontend")
JWT_EXPIRES_MIN = int(os.getenv("JWT_EXPIRES_MIN", "43200"))  # 30 days

def make_session_jwt(*, sub: str, email: str, name: str, picture: str) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "name": name,
        "picture": picture,
        "iss": JWT_ISS,
        "aud": JWT_AUD,
        "iat": now,
        "exp": now + JWT_EXPIRES_MIN * 60,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_session_jwt(token: str):
    try:
        data = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            issuer=JWT_ISS,
            audience=JWT_AUD,
        )
        return data
    except JWTError:
        return None
