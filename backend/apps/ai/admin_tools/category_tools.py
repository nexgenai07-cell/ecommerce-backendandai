# PATH: apps/ai/admin_tools/category_tools.py
#
# Admin Operations Agent ke category tools — Day 2 REAL implementation.

from apps.ai.admin_tools.api_client import call_internal_api
from apps.ai.admin_tools.pending_actions import create_pending_action


def propose_create_category(session_key: str, name: str, description: str = "") -> dict:
    """
    Category creation ka preview. Note: CategorySerializer mein 'slug' ya
    'parent_category' fields nahi hain (jo PDF ne mention kiye thay) —
    actual model 'description' aur 'image' rakhta hai. Isi mutabiq bana rahe hain.
    """
    payload = {'name': name, 'description': description or ''}
    preview = {'action': 'create_category', **payload}
    action_id = create_pending_action(session_key, 'create_category', payload, preview)
    return {'requires_confirmation': True, 'action_id': action_id, 'preview': preview}


def execute_create_category(user, payload: dict) -> dict:
    result = call_internal_api(user, 'POST', '/api/v1/categories/', json_body=payload)
    if not result['success']:
        return {'success': False, 'error': result['error']}
    return {'success': True, 'category': result['data']}


def propose_update_category(session_key: str, category_id: int, fields: dict) -> dict:
    preview = {'action': 'update_category', 'category_id': category_id, 'fields': fields}
    pending_kwargs = {'category_id': category_id, 'fields': fields}
    action_id = create_pending_action(session_key, 'update_category', pending_kwargs, preview)
    return {'requires_confirmation': True, 'action_id': action_id, 'preview': preview}


def execute_update_category(user, payload: dict) -> dict:
    category_id = payload['category_id']
    fields = payload['fields']
    result = call_internal_api(user, 'PATCH', f'/api/v1/categories/{category_id}/', json_body=fields)
    if not result['success']:
        return {'success': False, 'error': result['error']}
    return {'success': True, 'category': result['data']}


def propose_delete_category(session_key: str, category_id: int) -> dict:
    preview = {'action': 'delete_category', 'category_id': category_id}
    action_id = create_pending_action(session_key, 'delete_category', {'category_id': category_id}, preview)
    return {'requires_confirmation': True, 'action_id': action_id, 'preview': preview}


def execute_delete_category(user, payload: dict) -> dict:
    category_id = payload['category_id']
    result = call_internal_api(user, 'DELETE', f'/api/v1/categories/{category_id}/')
    if not result['success']:
        return {'success': False, 'error': result['error']}
    return {'success': True, 'message': f'Category {category_id} deleted.'}


def get_categories(user) -> dict:
    """Read-only — confirmation ki zaroorat nahi. GET /api/v1/categories/ (koi pagination nahi)."""
    result = call_internal_api(user, 'GET', '/api/v1/categories/')
    if not result['success']:
        return {'success': False, 'error': result['error'], 'categories': []}
    return {'success': True, 'categories': result['data']}