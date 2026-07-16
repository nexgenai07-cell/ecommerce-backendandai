# PATH: apps/ai/admin_agents/coordinator.py
#
# PDF section 4.1 Sample Internal Flow: "Receive message → Coordinator
# confirms intent = product management". Ye function decide karta hai
# ke message Operations Agent ke liye hai ya Analytics Agent ke liye.
#
# Day 1-4 mein ye sirf keyword-matching thi, lekin admin har baar customer-
# related sawal alag phrasing mein poochta raha (e.g. "naye customers",
# "customer registration", "new customer accounts") aur keyword list har
# baar peeche reh jati thi — whack-a-mole ban gaya tha. Ab isay LLM-based
# classification se replace kar diya hai (jaisa PDF khud suggest karta hai:
# "Day 4-5 mein isay LLM-based classification se behtar bana sakte hain").
# Keyword heuristic ab sirf FALLBACK hai — agar LLM call fail ho jaye
# (network down, quota exhausted) tab bhi routing kaam karti rahe.
#
# DEBUG LOGGING — ye 3rd baar hai jo customer-growth routing fail hui hai
# bina live evidence dekhe. Ab har route_intent() call apna decision +
# wajah (llm ya fallback, aur fallback hua to LLM ka exact error) log
# karta hai, taake agli baar guess nahi karna pade — Django console/log
# file mein "route_intent:" prefix se dhoond len.

import logging

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from apps.ai.gemini_utils import gemini_keys

logger = logging.getLogger(__name__)


CLASSIFIER_SYSTEM_PROMPT = """You are an intent router for an e-commerce admin dashboard AI assistant.
Classify the admin's message into EXACTLY ONE of these two categories:

- "operations" — anything about products, categories, inventory/stock, or
  orders: creating, updating, deleting, listing, checking stock, tracking,
  or cancelling. This also covers questions about a SPECIFIC order's
  details (including the customer name/phone on that one order).

- "analytics" — anything about aggregate numbers: sales figures, revenue,
  best-selling products, or customer counts/growth/signups/registrations
  (e.g. "how many new customers", "customer growth this month", "total
  customers", "customer registrations").

Reply with ONLY one word, exactly: operations OR analytics
No explanation, no punctuation, no extra text."""


def _classify_intent_llm(message: str):
    """
    LLM se ek-word classification leta hai. Fail ho ya unexpected output aaye
    to None return karta hai — route_intent phir keyword fallback pe chala
    jata hai. Retry/key-rotation yahan jaan-boojh kar nahi hai (ye sirf ek
    chhota routing call hai, agar ye fail ho to fallback turant available
    hai — poori call_with_fallback machinery ki zaroorat nahi).
    """
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-3.5-flash",
            google_api_key=gemini_keys.current_key,
            temperature=0,
        )
        response = llm.invoke([
            SystemMessage(content=CLASSIFIER_SYSTEM_PROMPT),
            HumanMessage(content=message),
        ])
        raw = response.content
        result = (raw or "").strip().lower()

        if "analytics" in result:
            logger.info("route_intent: LLM classified as ANALYTICS (raw output: %r) for message: %r", raw, message)
            return "analytics"
        if "operations" in result:
            logger.info("route_intent: LLM classified as OPERATIONS (raw output: %r) for message: %r", raw, message)
            return "operations"

        logger.warning("route_intent: LLM returned unexpected output %r for message: %r — falling back to keywords", raw, message)
        return None  # unexpected output — fallback pe jao
    except Exception as e:
        logger.warning("route_intent: LLM classification call FAILED (%s: %s) for message: %r — falling back to keywords", type(e).__name__, e, message)
        return None


# ---- Keyword-based FALLBACK (sirf tab chalta hai jab LLM call fail ho) ----

ANALYTICS_KEYWORDS = [
    'sales', 'revenue', 'report', 'analytics', 'best seller', 'bestseller',
    'best-selling', 'growth', 'performance', 'income',
    'earnings', 'kitni sale', 'kitna revenue', 'top selling', 'kamai',
    'retention', 'signup', 'sign-up',
]

CUSTOMER_KEYWORDS = ['customer', 'customers']
OPERATIONS_SIGNAL_WORDS = [
    'order', 'stock', 'inventory', 'product', 'category', 'categories', 'sku',
]


def _keyword_route_intent(message: str) -> str:
    """Simple substring-match heuristic — LLM classification fail hone par
    aakhri safety net."""
    lower_msg = message.lower()

    for keyword in ANALYTICS_KEYWORDS:
        if keyword in lower_msg:
            return 'analytics'

    has_operations_signal = any(w in lower_msg for w in OPERATIONS_SIGNAL_WORDS)
    if not has_operations_signal:
        for keyword in CUSTOMER_KEYWORDS:
            if keyword in lower_msg:
                return 'analytics'

    return 'operations'


def route_intent(message: str) -> str:
    """
    Returns 'analytics' ya 'operations'.
    Primary: LLM classification (kisi bhi phrasing ko samajh leta hai).
    Fallback: keyword heuristic (agar LLM call fail ho jaye).
    """
    llm_result = _classify_intent_llm(message)
    if llm_result is not None:
        return llm_result
    return _keyword_route_intent(message)