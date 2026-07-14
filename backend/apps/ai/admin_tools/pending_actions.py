# PATH: apps/ai/admin_tools/pending_actions.py
#
# CONFIRMATION-GATING MECHANISM — PDF requirement: "No mutating action
# (create/update/delete/cancel) is ever executed without explicit admin
# confirmation in the same turn."
#
# Kaam kaise karta hai:
# 1. Jab admin koi mutating request kare (jaise "product add karo"), tool
#    turant DB change NAHI karta. Wo sirf ek "preview" banata hai, cache
#    (Redis, jaisa doc section 7.1 mein specify hai) mein store karta hai,
#    aur action_id + preview wapis Agent ko deta hai.
# 2. Agent admin ko preview dikha kar confirmation maangta hai.
# 3. Admin "haan/confirm" bole to Agent confirm_pending_action tool call
#    karta hai us action_id ke sath — TABHI asal DB change hota hai.
#
# Cache backend: settings.py mein agar REDIS_URL set hai to ye automatically
# Redis use karega (CACHES['default'] Redis backend hai), warna dev mein
# DummyCache use hoga (jo har cheez turant expire kar deta hai — production
# mein Redis zaroor honi chahiye taake ye mechanism kaam kare).

import uuid
from django.core.cache import cache

PENDING_ACTION_TTL_SECONDS = 600  # 10 minutes — itni dair mein confirm na kare to expire


def create_pending_action(session_key: str, tool_name: str, kwargs: dict, preview: dict) -> str:
    """
    Ek pending (abhi execute nahi hui) action ko cache mein store karta hai.
    Returns: action_id jo admin ko confirmation maangte waqt reference k liye diya jata hai.
    """
    action_id = uuid.uuid4().hex[:12]
    cache_key = f"pending_action:{session_key}:{action_id}"
    cache.set(cache_key, {
        'tool_name': tool_name,
        'kwargs': kwargs,
        'preview': preview,
    }, timeout=PENDING_ACTION_TTL_SECONDS)
    return action_id


def get_pending_action(session_key: str, action_id: str) -> dict | None:
    """Pending action ko cache se nikalta hai (confirm karte waqt use hota hai)."""
    cache_key = f"pending_action:{session_key}:{action_id}"
    return cache.get(cache_key)


def clear_pending_action(session_key: str, action_id: str):
    """Confirm/reject hone k baad cache se hata dete hain."""
    cache_key = f"pending_action:{session_key}:{action_id}"
    cache.delete(cache_key)