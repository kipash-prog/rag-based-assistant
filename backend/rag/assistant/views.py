from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.files.storage import FileSystemStorage
from .models import PortfolioItem
from .serializers import QuerySerializer, UploadPDFSerializer, AddWebContentSerializer, AddExistingPDFSerializer, PortfolioItemSerializer
from sentence_transformers import SentenceTransformer
import chromadb
import requests
import PyPDF2
import os
from django.conf import settings
from rest_framework.parsers import MultiPartParser, FormParser
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

class QueryView(APIView):
    def post(self, request):
        serializer = QuerySerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Serializer errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        query = serializer.validated_data['query']

        try:
            logger.info("Loading SentenceTransformer model")
            model = SentenceTransformer('all-MiniLM-L6-v2')
            query_embedding = model.encode(query).tolist()
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {str(e)}")
            return Response({"error": f"Failed to generate query embedding: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            logger.info("Connecting to ChromaDB")
            client = chromadb.PersistentClient(path=settings.CHROMA_DB_PATH)
            collection = client.get_or_create_collection("portfolio")
            results = collection.query(query_embeddings=[query_embedding], n_results=5)
            vector_ids = results['ids'][0]
            logger.info(f"Retrieved vector IDs: {vector_ids}")
            items = PortfolioItem.objects.filter(vector_id__in=vector_ids)
            context = [item.content for item in items]
        except Exception as e:
            logger.error(f"Retrieval failed: {str(e)}")
            return Response({"error": f"Retrieval failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            logger.info("Sending request to Groq API")
            if not GROQ_API_KEY:
                logger.error("GROQ_API_KEY is not set in .env")
                return Response({"error": "GROQ_API_KEY is not set in .env file"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={
                    "model": "mixtral-8x7b-32768",
                    "messages": [
                        {"role": "system", "content": "You are a portfolio assistant. Answer based on the provided context about the user's portfolio."},
                        {"role": "user", "content": f"Query: {query}\nContext: {context}"}
                    ],
                    "max_tokens": 500
                },
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                timeout=10  # Add timeout to prevent hanging
            )
            llm_response = response.json()
            logger.info(f"Groq API response: {llm_response}")
            if response.status_code != 200:
                logger.error(f"Groq API returned status {response.status_code}: {llm_response}")
                return Response({"error": f"Groq API error: {llm_response.get('error', 'Unknown error')} (Status: {response.status_code})"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            if 'choices' not in llm_response or not llm_response['choices']:
                logger.error(f"Invalid Groq API response: {llm_response}")
                return Response({"error": f"Invalid response from Groq API: {llm_response}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            response_text = llm_response['choices'][0]['message']['content']
        except requests.exceptions.RequestException as e:
            logger.error(f"Groq API request failed: {str(e)}")
            return Response({"error": f"Groq API request failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        item_serializer = PortfolioItemSerializer(items, many=True)
        return Response({
            "response": response_text,
            "items": item_serializer.data
        }, status=status.HTTP_200_OK)

class UploadPDFView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        serializer = UploadPDFSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        file = serializer.validated_data['file']
        title = serializer.validated_data['title']
        metadata = serializer.validated_data['metadata']

        fs = FileSystemStorage(location=settings.MEDIA_ROOT)
        filename = fs.save(file.name, file)
        file_path = os.path.join(settings.MEDIA_ROOT, filename)
        source_url = os.path.join('media', filename).replace('\\', '/')

        try:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                content = ""
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        content += text
                content = content.strip()
                if not content:
                    return Response({"error": "No text could be extracted from the PDF"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"PDF extraction failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            if PortfolioItem.objects.filter(source_url=source_url).exists():
                return Response({"error": f"PortfolioItem with source_url {source_url} already exists"}, status=status.HTTP_400_BAD_REQUEST)
            item = PortfolioItem(
                title=title or file.name,
                content=content,
                source_type='pdf',
                source_url=source_url,
                metadata=metadata
            )
            item.save()
            item_serializer = PortfolioItemSerializer(item)
            return Response({
                "message": "PDF uploaded and processed",
                "item": item_serializer.data
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": f"Failed to save item: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AddWebContentView(APIView):
    def post(self, request):
        serializer = AddWebContentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        url = serializer.validated_data['url']
        title = serializer.validated_data['title']
        source_type = serializer.validated_data['source_type']
        metadata = serializer.validated_data['metadata']

        try:
            if PortfolioItem.objects.filter(source_url=url).exists():
                return Response({"error": f"PortfolioItem with source_url {url} already exists"}, status=status.HTTP_400_BAD_REQUEST)
            item = PortfolioItem(
                title=title,
                source_type=source_type,
                source_url=url,
                metadata=metadata
            )
            item.save()
            item_serializer = PortfolioItemSerializer(item)
            return Response({
                "message": f"{source_type.capitalize()} content added",
                "item": item_serializer.data
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": f"Failed to process {source_type}: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AddExistingPDFView(APIView):
    def post(self, request):
        serializer = AddExistingPDFSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        filename = serializer.validated_data['filename']
        title = serializer.validated_data['title']
        metadata = serializer.validated_data['metadata']

        source_url = os.path.join('media', filename).replace('\\', '/')
        file_path = os.path.join(settings.MEDIA_ROOT, filename.replace('media/', ''))

        if not os.path.exists(file_path):
            return Response({"error": f"File {file_path} does not exist"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                content = ""
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        content += text
                content = content.strip()
                if not content:
                    return Response({"error": "No text could be extracted from the PDF"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"PDF extraction failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            if PortfolioItem.objects.filter(source_url=source_url).exists():
                return Response({"error": f"PortfolioItem with source_url {source_url} already exists"}, status=status.HTTP_400_BAD_REQUEST)
            item = PortfolioItem(
                title=title or filename,
                content=content,
                source_type='pdf',
                source_url=source_url,
                metadata=metadata
            )
            item.save()
            item_serializer = PortfolioItemSerializer(item)
            return Response({
                "message": "Existing PDF processed",
                "item": item_serializer.data
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": f"Failed to save item: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)