from django.urls import path
from .views import AgentQueryView, DataReloadView, SessionClearView, HealthView

urlpatterns = [
    path('ask/',                    AgentQueryView.as_view(),   name='agent-ask'),
    path('reload-data/',            DataReloadView.as_view(),   name='data-reload'),
    path('session/<str:session_id>/', SessionClearView.as_view(), name='session-clear'),
    path('health/',                 HealthView.as_view(),       name='health'),
]
