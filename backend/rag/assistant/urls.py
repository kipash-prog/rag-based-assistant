from django.urls import path
from .views import QueryView, UploadPDFView, AddWebContentView, AddExistingPDFView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('query/', QueryView.as_view(), name='query'),
    path('upload-pdf/', UploadPDFView.as_view(), name='upload-pdf'),
    path('add-web-content/', AddWebContentView.as_view(), name='add-web-content'),
    path('add-existing-pdf/', AddExistingPDFView.as_view(), name='add-existing-pdf'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)