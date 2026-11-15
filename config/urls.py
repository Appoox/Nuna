"""
URL routes for the whole project.

Only Wagtail's own routes exist so far. The project's own pages and the
public API are added by later changes.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

urlpatterns = [
    # The Wagtail admin, where editors log in and enter data.
    path("admin/", include(wagtailadmin_urls)),
    # Downloads of files held in Wagtail's document library.
    path("documents/", include(wagtaildocs_urls)),
]

if settings.DEBUG:
    # In development Django serves uploaded files itself.
    # In production the web server does this instead.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [
    # Wagtail's page routing. It matches every remaining address,
    # so it must stay last in the list.
    path("", include(wagtail_urls)),
]
