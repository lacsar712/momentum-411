import hashlib
import uuid
import json
import re
import redis
from datetime import datetime
from app.core.config import settings
from app.models import UserActionLog

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash

def check_password_strength(password: str) -> dict:
    score = 0
    feedback = []

    if len(password) >= 8:
        score += 1
    else:
        feedback.append("密码长度至少 8 位")

    if re.search(r'[a-z]', password):
        score += 1
    else:
        feedback.append("需要包含小写字母")

    if re.search(r'[A-Z]', password):
        score += 1
    else:
        feedback.append("需要包含大写字母")

    if re.search(r'[0-9]', password):
        score += 1
    else:
        feedback.append("需要包含数字")

    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        score += 1
    else:
        feedback.append("需要包含特殊字符")

    if score <= 2:
        level = "weak"
    elif score <= 3:
        level = "medium"
    else:
        level = "strong"

    return {"score": score, "level": level, "feedback": feedback, "passed": score >= 3}

def issue_token(username: str, role: str) -> str:
    token = str(uuid.uuid4())
    redis_client.setex(f"token:{token}", 86400, json.dumps({"username": username, "role": role}, ensure_ascii=False))
    redis_client.sadd(f"user_tokens:{username}", token)
    return token

def get_token_payload(token: str):
    value = redis_client.get(f"token:{token}")
    if not value:
        return None
    return json.loads(value)

def invalidate_user_tokens(username: str):
    tokens = redis_client.smembers(f"user_tokens:{username}")
    for token in tokens:
        redis_client.delete(f"token:{token}")
    redis_client.delete(f"user_tokens:{username}")

def log_user_action(session, user_id: int, action_type: str, action_detail: str = None, ip_address: str = None, user_agent: str = None):
    try:
        log = UserActionLog(
            user_id=user_id,
            action_type=action_type,
            action_detail=action_detail,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.utcnow()
        )
        session.add(log)
        session.commit()
    except Exception as e:
        print(f"Failed to log user action: {e}")
        session.rollback()
