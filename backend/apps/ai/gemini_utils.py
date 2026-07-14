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


def call_with_fallback(attempt_fn):
    """
    Shared retry/fallback wrapper — customer aur admin dono side ke saare
    Gemini calls (Agent invoke ya embedding requests) isay istemal karte hain.

    Args:
        attempt_fn: koi bhi zero-argument function jo EK poori koshish
                    karta hai (Gemini ko call karta hai) aur result
                    return karta hai, ya exception raise karta hai.
                    Ye function khud gemini_keys.current_key use karega
                    (jaisa ke customer/admin agents pehle se karte hain).

    Behavior:
        - Same key se 503/overload par thodi dair ruk kar dobara try
        - 429/quota par agli key try (rotate)
        - Koi aur error ho to turant raise (chhupaya nahi jata)
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
                    continue  # samei key se dobara try

                if is_quota_error(e) or is_transient_error(e):
                    moved_to_next_key = True
                    break  # inner loop se bahar, agli key try karenge

                raise  # koi aur error — turant raise, chhupana nahi

        if moved_to_next_key:
            gemini_keys.rotate()

    raise Exception(
        f"Sari Gemini API keys ki quota khatam ho chuki hai ya Gemini abhi "
        f"overloaded hai. Last error: {last_error}"
    )