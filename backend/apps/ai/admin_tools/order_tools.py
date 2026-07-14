# PATH: apps/ai/admin_tools/order_tools.py
#
# Admin Operations Agent ke order management tools — Day 1 STUBS.

from apps.ai.admin_tools.pending_actions import create_pending_action


def get_order_details_tool(order_id: str) -> dict:
    """STUB — Day 3. Read-only, confirmation ki zaroorat nahi."""
    return {'success': True, 'order': {}}


def update_order_tool(session_key: str, order_id: str, fields: dict) -> dict:
    """STUB — Day 3. Mutating, confirmation-gated."""
    preview = {'action': 'update_order', 'order_id': order_id, 'fields': fields}
    action_id = create_pending_action(session_key, 'update_order_tool', preview, preview)
    return {'requires_confirmation': True, 'action_id': action_id, 'preview': preview}


def cancel_order_tool(session_key: str, order_id: str, reason: str = "") -> dict:
    """STUB — Day 3. Mutating, confirmation-gated."""
    preview = {'action': 'cancel_order', 'order_id': order_id, 'reason': reason}
    action_id = create_pending_action(session_key, 'cancel_order_tool', preview, preview)
    return {'requires_confirmation': True, 'action_id': action_id, 'preview': preview}


def track_order_tool(order_id: str) -> dict:
    """STUB — Day 3. Read-only, confirmation ki zaroorat nahi."""
    return {'success': True, 'order_id': order_id, 'status': None, 'timeline': []}