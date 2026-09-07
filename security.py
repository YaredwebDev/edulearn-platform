"""Authentication, password hashing, token signing and admin verification.

Secrets live ONLY on the server. Student tokens are HMAC-signed; passwords are
salted & hashed with PBKDF2 (stdlib). Admin access is gated by backend checks.
"""
import hashlib, hmac, os, base64, json, time, secrets, re

SECRET = os.environ.get("PLATFORM_SECRET", "change-me-to-a-long-random-secret-7f3c")
TOKEN_TTL = 60 * 60 * 24 * 30  # 30 days

def _rand_bytes(n=16):
    return secrets.token_bytes(n)

# ---------- passwords ----------
def hash_password(password: str) -> dict:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return {"salt": base64.b64encode(salt).decode(), "hash": base64.b64encode(dk).decode()}

def verify_password(password: str, salt_b64: str, hash_b64: str) -> bool:
    salt = base64.b64decode(salt_b64)
    expected = base64.b64decode(hash_b64)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return hmac.compare_digest(dk, expected)

# ---------- tokens ----------
def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

def sign(payload: dict, ttl=TOKEN_TTL) -> str:
    payload = dict(payload)
    payload["exp"] = int(time.time()) + ttl
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64e(hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest())
    return body + "." + sig

def verify_token(token: str):
    """Return payload dict or None."""
    try:
        body, sig = token.rsplit(".", 1)
        exp_sig = hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(exp_sig, _b64d(sig)):
            return None
        payload = json.loads(_b64d(body))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None

# ---------- admin secrets ----------
# Initial admin verification answers. Stored only as hashes.
ADMIN_SECRETS = {
    "name":     "Yared Tesfaye",
    "color":    "Red",
    "number":   "nine",
}

def admin_check(field: str, answer: str) -> bool:
    ans = (answer or "").strip().lower()
    expected = (ADMIN_SECRETS.get(field) or "").strip().lower()
    if not expected:
        return False
    return hmac.compare_digest(ans, expected)

def is_valid_phone(p):
    return bool(re.fullmatch(r"\+?[0-9][0-9 \-]{6,17}[0-9]", (p or "").strip()))
