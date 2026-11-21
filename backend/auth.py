import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Request
from . import db as m

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ":" + hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 210000).hex()

def verify_password(password, stored):
    return hmac.compare_digest(hash_password(password, stored.split(":")[0]), stored)

def user_from_request(db, request: Request):
    token = request.cookies.get("labeltrace_session", "")
    session = m.latest(db, m.LoginSession, hashlib.sha256(token.encode()).hexdigest()) if token else None
    if not session or session.data["expires"] < datetime.now(timezone.utc).isoformat():
        raise HTTPException(401, "Sign in to continue")
    return db.get(m.User, session.data["user_id"])

def login(db, email, password):
    user = m.latest(db, m.User, email)
    if not user or not verify_password(password, user.data["password_hash"]):
        raise HTTPException(401, "Incorrect email or password")
    token = secrets.token_urlsafe(40)
    m.add(db, m.LoginSession, hashlib.sha256(token.encode()).hexdigest(), {
        "user_id": user.id, "expires": (datetime.now(timezone.utc)+timedelta(hours=8)).isoformat()}, user.id)
    m.audit(db, "SIGNED_IN", user.id, user.id)
    return token, user
