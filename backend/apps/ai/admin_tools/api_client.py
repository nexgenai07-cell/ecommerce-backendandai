# PATH: apps/ai/admin_tools/api_client.py
#
# Admin tools ke liye shared HTTP client. PDF ka explicit requirement hai:
# "Every tool is a thin, validated wrapper around an existing Django REST
# endpoint. Tools never talk to the database directly." — isliye yahan
# hum seedha ORM use nahi kar rahe, balke apne hi Django REST API ko
# HTTP se call kar rahe hain, jaisa production mein hota.
#
# AUTHENTICATION: Admin ka WebSocket session sirf unka Django User object
# jaanta hai (JWT token store nahi karta — customer side mein bhi hum
# original JWT store nahi karte). Isliye har request se pehle, us admin
# user ke liye ek FRESH JWT access token mint karte hain (SimpleJWT ka
# AccessToken.for_user() — koi login/password ki zaroorat nahi, kyunke
# hum already jaante hain ke ye authenticated admin session hai).

import requests
from django.conf import settings
from rest_framework_simplejwt.tokens import AccessToken


def _get_base_url():
    return getattr(settings, 'INTERNAL_API_URL', 'http://localhost:8000')


def _mint_token_for_user(user):
    """Admin user ke liye server-side ek fresh short-lived JWT banata hai."""
    return str(AccessToken.for_user(user))


def call_internal_api(user, method: str, path: str, json_body: dict = None, params: dict = None) -> dict:
    """
    Django REST API ko authenticated HTTP request bhejta hai, jaise wo
    request khud admin user ne bheji ho (JWT ke sath).

    Args:
        user:      Django User object (admin) — jiski taraf se request jayegi
        method:    'GET', 'POST', 'PATCH', 'DELETE'
        path:      Endpoint path, jaise '/api/v1/products/'
        json_body: POST/PATCH ke liye request body
        params:    GET ke liye query params

    Returns:
        dict: {'success': bool, 'status_code': int, 'data': ..., 'error': ...}

    Ye function har real admin tool istemal karega — taake HTTP-calling
    logic, error handling, aur auth ek hi jagah likha ho.
    """
    token = _mint_token_for_user(user)
    url = f"{_get_base_url()}{path}"
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.request(
            method=method.upper(),
            url=url,
            json=json_body,
            params=params,
            headers=headers,
            timeout=15,
        )
    except requests.RequestException as e:
        return {'success': False, 'status_code': None, 'data': None, 'error': f'Request failed: {e}'}

    try:
        data = response.json() if response.content else None
    except ValueError:
        data = None

    if response.status_code >= 400:
        error_msg = data.get('error') if isinstance(data, dict) and 'error' in data else (data or response.text)
        return {'success': False, 'status_code': response.status_code, 'data': data, 'error': error_msg}

    return {'success': True, 'status_code': response.status_code, 'data': data, 'error': None}