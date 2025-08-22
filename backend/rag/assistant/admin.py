from django.contrib import admin
from .models import PortfolioItem
from django.conf import settings
import os
import json

@admin.register(PortfolioItem)
class PortfolioItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'source_type', 'source_url', 'created_at', 'metadata')
    list_filter = ('source_type', 'created_at')
    search_fields = ('title', 'content', 'source_url')
    fields = ('title', 'source_type', 'source_url', 'content', 'metadata')
    readonly_fields = ('created_at', 'updated_at', 'vector_id')

    def save_model(self, request, obj, form, change):
        if obj.source_type == 'pdf' and obj.source_url:
            file_path = os.path.join(settings.MEDIA_ROOT, obj.source_url.replace('media/', ''))
            if not os.path.exists(file_path):
                self.message_user(request, f"Error: File {file_path} does not exist", level='error')
                return
        if obj.metadata and not isinstance(obj.metadata, dict):
            try:
                obj.metadata = json.loads(obj.metadata)
            except json.JSONDecodeError:
                self.message_user(request, "Error: Metadata must be a valid JSON object", level='error')
                return
        super().save_model(request, obj, form, change)
        self.message_user(request, f"Successfully saved {obj.title or obj.id}")

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['metadata'].widget.attrs['placeholder'] = '{"About_me": "AboutMe.pdf"}'
        return form