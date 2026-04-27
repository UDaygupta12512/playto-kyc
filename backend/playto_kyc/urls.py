from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.http import FileResponse
from pathlib import Path


def serve_spa(request, *args, **kwargs):
    """Serve the React index.html for all non-API routes (client-side routing)."""
    index = Path(settings.BASE_DIR) / 'frontend_dist' / 'index.html'
    return FileResponse(open(index, 'rb'), content_type='text/html')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('kyc.urls')),
    re_path(r'^(?!api/|admin/|static/|media/).*$', serve_spa),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
