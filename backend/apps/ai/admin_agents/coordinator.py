# PATH: apps/ai/admin_agents/coordinator.py
#
# PDF section 4.1 Sample Internal Flow: "Receive message → Coordinator
# confirms intent = product management". Ye function decide karta hai
# ke message Operations Agent ke liye hai ya Analytics Agent ke liye —
# Day 1 mein simple keyword-based routing, chahe to Day 4-5 mein isay
# LLM-based classification se aur behtar bana sakte hain.

ANALYTICS_KEYWORDS = [
    'sales', 'revenue', 'report', 'analytics', 'best seller', 'bestseller',
    'best-selling', 'growth', 'customers grew', 'performance', 'income',
    'earnings', 'kitni sale', 'kitna revenue', 'top selling', 'kamai',
]


def route_intent(message: str) -> str:
    """
    Returns 'analytics' ya 'operations'.
    Simple keyword match — agar analytics-related word mile to Analytics
    Agent, warna default Operations Agent (product/category/inventory/order
    sab operations ka hissa hai).
    """
    lower_msg = message.lower()
    for keyword in ANALYTICS_KEYWORDS:
        if keyword in lower_msg:
            return 'analytics'
    return 'operations'