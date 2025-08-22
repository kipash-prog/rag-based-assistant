from rest_framework import serializers
from .models import PortfolioItem
import json
import os
from django.conf import settings

class PortfolioItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioItem
        fields = ['id', 'title', 'content', 'source_type', 'source_url', 'created_at', 'updated_at', 'metadata']
        read_only_fields = ['id', 'content', 'vector_id', 'created_at', 'updated_at']

    def validate_metadata(self, value):
        if isinstance(value, dict):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            raise serializers.ValidationError("Metadata must be a valid JSON object")

    def validate_source_type(self, value):
        valid_types = [choice[0] for choice in PortfolioItem.SOURCE_TYPE_CHOICES]
        if value not in valid_types:
            raise serializers.ValidationError(f"Source type must be one of: {', '.join(valid_types)}")
        return value

    def validate_source_url(self, value):
        if not value:
            return value
        if self.initial_data.get('source_type') == 'pdf':
            # Allow relative paths like 'media/AboutMe.pdf'
            if not os.path.exists(os.path.join(settings.MEDIA_ROOT, value.replace('media/', ''))):
                raise serializers.ValidationError(f"PDF file {value} does not exist in media directory")
        else:
            # Validate as URL for social_media or website
            from django.core.validators import URLValidator
            try:
                URLValidator()(value)
            except Exception:
                raise serializers.ValidationError("Invalid URL for social_media or website")
        return value

class QuerySerializer(serializers.Serializer):
    query = serializers.CharField(max_length=500, required=True)

    def validate_query(self, value):
        if not value.strip():
            raise serializers.ValidationError("Query cannot be empty")
        return value

class UploadPDFSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_file(self, value):
        if not value.name.endswith('.pdf'):
            raise serializers.ValidationError("File must be a PDF")
        if value.size > 10 * 1024 * 1024:  # Limit to 10MB
            raise serializers.ValidationError("File size must not exceed 10MB")
        return value

    def validate_metadata(self, value):
        if isinstance(value, dict):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            raise serializers.ValidationError("Metadata must be a valid JSON object")

class AddWebContentSerializer(serializers.Serializer):
    url = serializers.URLField(required=True)
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    source_type = serializers.ChoiceField(choices=['website', 'social_media'], default='website')
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_metadata(self, value):
        if isinstance(value, dict):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            raise serializers.ValidationError("Metadata must be a valid JSON object")

class AddExistingPDFSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=255, required=True)
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_filename(self, value):
        file_path = os.path.join(settings.MEDIA_ROOT, value.replace('media/', ''))
        if not os.path.exists(file_path):
            raise serializers.ValidationError(f"File {value} does not exist in media directory")
        if not value.endswith('.pdf'):
            raise serializers.ValidationError("File must be a PDF")
        return value

    def validate_metadata(self, value):
        if isinstance(value, dict):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            raise serializers.ValidationError("Metadata must be a valid JSON object")