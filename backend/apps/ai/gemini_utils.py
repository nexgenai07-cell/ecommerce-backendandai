# PATH: apps/ai/gemini_utils.py
#
# Gemini API key fallback manager + transient-error retry helper.
#
# Do tarah ke errors alag tarah handle hote hain:
#   - QUOTA errors (429) — is key ki quota khatam, AGLI KEY try karo
#   - TRANSIENT errors (503, overloaded) — Google ka server abhi busy hai,
#     SAMEI key se thodi dair baad DOBARA try karo (rotate karne ka koi
#     faida nahi, kyunke masla key ka nahi, Google ke server ka hai)

import time
from django.conf import settings


class GeminiKeyManager:
    def __init__(self, keys):
        if not keys:
            raise ValueError(
                "GEMINI_API_KEYS khali hai — settings mein kam az kam 1 API key honi chahiye."
            )
        self.keys = keys
        self.index = 0

    @property
    def current_key(self):
        return self.keys[self.index]

    def rotate(self):
        self.index = (self.index + 1) % len(self.keys)
        return self.current_key

    def total_keys(self):
        return len(self.keys)


gemini_keys = GeminiKeyManager(settings.GEMINI_API_KEYS)


def is_quota_error(exception) -> bool:
    """429 / RESOURCE_EXHAUSTED — is key ki quota khatam ho chuki hai."""
    msg = str(exception)
    return '429' in msg or 'RESOURCE_EXHAUSTED' in msg or 'quota' in msg.lower()


def is_transient_error(exception) -> bool:
    """
    503 / UNAVAILABLE / 'high demand' — Google ka server temporarily
    overloaded hai. Key ka koi qasoor nahi, isliye rotate nahi karte —
    thodi dair ruk kar SAMEI key se dobara try karte hain.
    """
    msg = str(exception)
    lower_msg = msg.lower()
    return '503' in msg or 'UNAVAILABLE' in msg or 'overloaded' in lower_msg or 'high demand' in lower_msg


TRANSIENT_RETRY_ATTEMPTS = 2       # 503 aane par samei key se kitni baar dobara try karein
TRANSIENT_RETRY_DELAY_SECONDS = 3  # har retry se pehle kitni dair rukein


def call_with_fallback(attempt_fn, groq_fallback_fn=None):
    """
    Args:
        attempt_fn:       Gemini ke sath ek koshish (rotate/retry logic pehle jaisi)
        groq_fallback_fn: OPTIONAL — sari Gemini keys exhaust hone ke baad
                          aakhri koshish ke tor par Groq se try karta hai.
                          Sirf chat/agent calls ke liye pass karein — embeddings
                          ke liye kabhi pass na karein (vector dimensions match
                          nahi karenge, Qdrant search break ho jayegi).
    """
    last_error = None

    for key_attempt in range(gemini_keys.total_keys()):
        moved_to_next_key = False

        for transient_attempt in range(TRANSIENT_RETRY_ATTEMPTS + 1):
            try:
                return attempt_fn()
            except Exception as e:
                last_error = e

                if is_transient_error(e) and transient_attempt < TRANSIENT_RETRY_ATTEMPTS:
                    time.sleep(TRANSIENT_RETRY_DELAY_SECONDS)
                    continue

                if is_quota_error(e) or is_transient_error(e):
                    moved_to_next_key = True
                    break

                raise

        if moved_to_next_key:
            gemini_keys.rotate()

    # Sari Gemini keys exhaust ho chuki hain — Groq try karo (agar diya gaya ho)
    if groq_fallback_fn is not None:
        try:
            return groq_fallback_fn()
        except Exception as groq_error:
            raise Exception(
                f"Sari Gemini API keys ki quota khatam ho chuki hai, aur Groq fallback "
                f"bhi fail ho gaya. Gemini error: {last_error} | Groq error: {groq_error}"
            )

    raise Exception(
        f"Sari Gemini API keys ki quota khatam ho chuki hai ya Gemini abhi "
        f"overloaded hai. Last error: {last_error}"
    )