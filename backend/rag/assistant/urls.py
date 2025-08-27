from django.urls import path
from . import views

urlpatterns = [
    path('query/', views.QueryView.as_view(), name='query'),
    path('upload-pdf/', views.UploadPDFView.as_view(), name='upload_pdf'),
    path('add-web-content/', views.AddWebContentView.as_view(), name='add_web_content'),
    path('add-existing-pdf/', views.AddExistingPDFView.as_view(), name='add_existing_pdf'),
]