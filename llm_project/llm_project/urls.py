"""
URL configuration for llm_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

import os
from pathlib import Path
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse


def _index_view(request):
    path = Path(__file__).resolve().parent.parent.parent / "index.html"
    try:
        return HttpResponse(path.read_text(encoding="utf-8"), content_type="text/html")
    except FileNotFoundError:
        return HttpResponse("index.html not found", status=404)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("llm_api.urls")),
    path("", _index_view),
]
