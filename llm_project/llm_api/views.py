import logging
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .agent import run_agent
from .data_loader import reload_data

logger = logging.getLogger(__name__)

APP_AUTH_TOKEN = getattr(settings, 'APP_AUTH_TOKEN', '')


def _check_auth(request):
    if not APP_AUTH_TOKEN:
        return None
    auth = request.headers.get('Authorization', '').strip()
    if auth.lower().startswith('bearer ') and auth[7:] == APP_AUTH_TOKEN:
        return None
    return Response({'error': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

# in-memory session store — replace with Redis/DB for production
_sessions: dict[str, list] = {}


def _get_provider_api_key(request) -> str:
    auth_header = request.headers.get('Authorization', '').strip()
    if auth_header.lower().startswith('bearer '):
        return auth_header[7:].strip()
    return request.headers.get('X-Api-Key', '').strip()


class AgentQueryView(APIView):
    """
    POST /api/ask/
    Body: { "query": "...", "session_id": "optional" }
    Returns: { "answer", "tools_used", "session_id" }
    """

    def post(self, request):
        err = _check_auth(request)
        if err:
            return err
        query = request.data.get('query', '').strip()
        session_id = request.data.get('session_id', '')

        if not query:
            return Response({'error': 'query is required'}, status=status.HTTP_400_BAD_REQUEST)

        history = _sessions.get(session_id, []) if session_id else []

        try:
            result = run_agent(query, conversation_history=history)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception('Agent error')
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # persist conversation for multi-turn
        if session_id:
            if session_id not in _sessions:
                _sessions[session_id] = []
            _sessions[session_id].append({'role': 'user', 'content': query})
            _sessions[session_id].append({'role': 'assistant', 'content': result['answer']})
            # cap history at 20 turns to avoid token overflow
            _sessions[session_id] = _sessions[session_id][-20:]

        return Response({
            'answer':      result['answer'],
            'tools_used':  result['tools_used'],
            'session_id':  session_id,
            'error':       result.get('error'),
        })


class DataReloadView(APIView):
    """
    POST /api/reload-data/
    Force reload Excel files from disk (call after updating the Excel files).
    """

    def post(self, request):
        err = _check_auth(request)
        if err:
            return err
        try:
            so, sod, inv = reload_data()
            return Response({
                'status': 'reloaded',
                'so_rows': len(so),
                'sod_rows': len(sod),
                'inv_rows': len(inv),
            })
        except Exception as e:
            logger.exception('Reload error')
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SessionClearView(APIView):
    """
    DELETE /api/session/<session_id>/
    Clear conversation history for a session.
    """

    def delete(self, request, session_id):
        err = _check_auth(request)
        if err:
            return err
        if session_id in _sessions:
            del _sessions[session_id]
        return Response({'status': 'cleared', 'session_id': session_id})


class HealthView(APIView):
    """GET /api/health/ — quick sanity check"""

    def get(self, request):
        err = _check_auth(request)
        if err:
            return err
        from .data_loader import load_data
        try:
            so, sod, inv = load_data()
            return Response({
                'status': 'ok',
                'data': {
                    'sales_orders': len(so),
                    'order_details': len(sod),
                    'invoice_lines': len(inv),
                },
            })
        except Exception as e:
            return Response({'status': 'error', 'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
