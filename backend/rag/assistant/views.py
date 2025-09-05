from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from .models import PortfolioItem
from .serializers import QuerySerializer, PortfolioItemSerializer, UploadPDFSerializer, AddWebContentSerializer, AddExistingPDFSerializer
from sentence_transformers import SentenceTransformer
import chromadb
import requests
import PyPDF2
import logging
import os
import base64
from django.core.files.base import ContentFile

# Configure logger
logger = logging.getLogger(__name__)

class QueryView(APIView):
    """Handles user queries by retrieving relevant portfolio items and generating responses via the Groq API."""

    def post(self, request):
        logger.info("Processing query request")
        serializer = QuerySerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Invalid query data: {serializer.errors}")
            return Response(
                {"error": "Invalid query data", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        query = serializer.validated_data['query']
        logger.debug(f"Received query: {query}")

        # Generate query embedding
        try:
            logger.info("Loading SentenceTransformer model: all-MiniLM-L6-v2")
            model = SentenceTransformer('all-MiniLM-L6-v2')
            query_embedding = model.encode(query).tolist()
            logger.debug("Query embedding generated successfully")
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {str(e)}")
            return Response(
                {"error": "Failed to generate query embedding", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Query ChromaDB
        try:
            logger.info(f"Connecting to ChromaDB at {settings.CHROMA_DB_PATH}")
            client = chromadb.PersistentClient(path=str(settings.CHROMA_DB_PATH))
            collection = client.get_or_create_collection("portfolio")
            results = collection.query(query_embeddings=[query_embedding], n_results=5)
            vector_ids = results['ids'][0]
            logger.info(f"Retrieved vector IDs: {vector_ids}")
            items = PortfolioItem.objects.filter(vector_id__in=vector_ids)
            context = [item.content for item in items]
            logger.debug(f"Context retrieved: {context[:100]}...")
        except Exception as e:
            logger.error(f"ChromaDB query failed: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to retrieve portfolio items", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Query Groq API
        try:
            logger.info(f"Sending request to Groq API with key: {settings.GROQ_API_KEY[:4]}...{settings.GROQ_API_KEY[-4:]}")
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a portfolio assistant. Provide accurate responses based solely on the provided portfolio context."
                        },
                        {"role": "user", "content": f"Query: {query}\nContext: {context}"}
                    ],
                    "max_tokens": 500
                },
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                timeout=10
            )
            llm_response = response.json()
            logger.debug(f"Groq API response: {llm_response}")

            if response.status_code != 200:
                logger.error(f"Groq API error: {llm_response.get('error', 'Unknown error')} (Status: {response.status_code})")
                return Response(
                    {"error": "Groq API request failed", "details": llm_response.get('error', 'Unknown error')},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            if 'choices' not in llm_response or not llm_response['choices']:
                logger.error(f"Invalid Groq API response: {llm_response}")
                return Response(
                    {"error": "Invalid response from Groq API", "details": str(llm_response)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            response_text = llm_response['choices'][0]['message']['content']
            logger.info("Groq API response received successfully")
        except requests.exceptions.RequestException as e:
            logger.error(f"Groq API request failed: {str(e)}", exc_info=True)
            return Response(
                {"error": "Groq API communication error", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        item_serializer = PortfolioItemSerializer(items, many=True)
        logger.info("Query processed successfully")
        return Response(
            {
                "response": response_text,
                "items": item_serializer.data
            },
            status=status.HTTP_200_OK
        )

class UploadPDFView(APIView):
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def post(self, request):
        logger.info("Processing PDF upload request")
        logger.info(f"Incoming Content-Type: {request.content_type or 'None'}")

        if request.content_type == 'application/json':
            logger.info("Processing JSON-based PDF upload")
            file_data = request.data.get('file')
            title = request.data.get('title', '')
            metadata = request.data.get('metadata', {})

            if not file_data:
                logger.error("File data is missing in JSON request")
                return Response(
                    {"error": "File data is required in JSON request"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate and decode base64 file data
            try:
                if not file_data.startswith("data:") or ";base64," not in file_data:
                    logger.error(f"Invalid file data received: {file_data[:100]}...")
                    raise ValueError(
                        "Invalid base64 format. Expected 'data:<mime-type>;base64,<data>'."
                    )

                format, file_str = file_data.split(';base64,', 1)
                ext = format.split('/')[-1]
                if not file_str.strip():
                    raise ValueError("Base64 data is empty.")
                file = ContentFile(base64.b64decode(file_str), name=f"uploaded_file.{ext}")
            except ValueError as ve:
                logger.error(f"Invalid base64 file format: {str(ve)}")
                return Response(
                    {"error": "Invalid base64 file format", "details": str(ve)},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                logger.error(f"Failed to decode base64 file: {str(e)}")
                return Response(
                    {"error": "Failed to decode base64 file", "details": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif request.content_type == 'multipart/form-data':
            logger.info("Processing multipart/form-data PDF upload")
            serializer = UploadPDFSerializer(data=request.data)
            if not serializer.is_valid():
                logger.error(f"Invalid PDF upload data: {serializer.errors}")
                return Response(
                    {"error": "Invalid PDF upload data", "details": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
            file = serializer.validated_data['file']
            title = serializer.validated_data['title']
            metadata = serializer.validated_data['metadata']
        else:
            logger.warning("Unsupported Media Type for PDF upload")
            return Response(
                {"error": "Unsupported Media Type. Use 'multipart/form-data' or 'application/json'."},
                status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            )

        # Save the file and process it as before
        fs = FileSystemStorage(location=settings.MEDIA_ROOT)
        filename = fs.save(file.name, file)
        file_path = os.path.join(settings.MEDIA_ROOT, filename)
        source_url = os.path.join('media', filename).replace('\\', '/')

        # Extract PDF content
        try:
            logger.info(f"Extracting text from PDF: {file_path}")
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                content = ""
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        content += text
                content = content.strip()
                if not content:
                    logger.warning(f"No text extracted from PDF: {file_path}")
                    return Response(
                        {"error": "No text could be extracted from the PDF"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                logger.debug(f"Extracted content (first 100 chars): {content[:100]}...")
        except Exception as e:
            logger.error(f"PDF extraction failed: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to extract PDF content", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Save PortfolioItem
        try:
            if PortfolioItem.objects.filter(source_url=source_url).exists():
                logger.error(f"PortfolioItem with source_url {source_url} already exists")
                return Response(
                    {"error": f"PortfolioItem with source_url {source_url} already exists"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            item = PortfolioItem(
                title=title or file.name,
                content=content,
                source_type='pdf',
                source_url=source_url,
                metadata=metadata
            )
            item.save()
            item_serializer = PortfolioItemSerializer(item)
            logger.info(f"PDF uploaded and saved as PortfolioItem: {item.id}")
            return Response(
                {
                    "message": "PDF uploaded and processed successfully",
                    "item": item_serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            logger.error(f"Failed to save PortfolioItem: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to save portfolio item", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class AddWebContentView(APIView):
    """Handles the addition of web content to the portfolio."""

    def post(self, request):
        """
        Adds web content as a PortfolioItem based on provided URL and metadata.

        Args:
            request: The HTTP POST request containing the URL, title, source type, and metadata.

        Returns:
            Response: JSON response with the saved item details or an error message.
        """
        logger.info("Processing web content addition request")
        serializer = AddWebContentSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Invalid web content data: {serializer.errors}")
            return Response(
                {"error": "Invalid web content data", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        url = serializer.validated_data['url']
        title = serializer.validated_data['title']
        source_type = serializer.validated_data['source_type']
        metadata = serializer.validated_data['metadata']
        logger.debug(f"Adding web content: URL={url}, Title={title}, Source Type={source_type}")

        try:
            if PortfolioItem.objects.filter(source_url=url).exists():
                logger.error(f"PortfolioItem with source_url {url} already exists")
                return Response(
                    {"error": f"PortfolioItem with source_url {url} already exists"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            item = PortfolioItem(
                title=title,
                source_type=source_type,
                source_url=url,
                metadata=metadata
            )
            item.save()
            item_serializer = PortfolioItemSerializer(item)
            logger.info(f"Web content saved as PortfolioItem: {item.id}")
            return Response(
                {
                    "message": f"{source_type.capitalize()} content added successfully",
                    "item": item_serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            logger.error(f"Failed to save web content: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Failed to process {source_type} content", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class AddExistingPDFView(APIView):
    """Handles the processing of existing PDF files for portfolio items."""

    def post(self, request):
        """
        Processes an existing PDF file and saves it as a PortfolioItem.

        Args:
            request: The HTTP POST request containing the filename, title, and metadata.

        Returns:
            Response: JSON response with the saved item details or an error message.
        """
        logger.info("Processing existing PDF request")
        serializer = AddExistingPDFSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Invalid existing PDF data: {serializer.errors}")
            return Response(
                {"error": "Invalid existing PDF data", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        filename = serializer.validated_data['filename']
        title = serializer.validated_data['title']
        metadata = serializer.validated_data['metadata']
        logger.debug(f"Processing existing PDF: {filename}, Title: {title}")

        source_url = os.path.join('media', filename).replace('\\', '/')
        file_path = os.path.join(settings.MEDIA_ROOT, filename.replace('media/', ''))

        if not os.path.exists(file_path):
            logger.error(f"File does not exist: {file_path}")
            return Response(
                {"error": f"File {file_path} does not exist"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Extract PDF content
        try:
            logger.info(f"Extracting text from existing PDF: {file_path}")
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                content = ""
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        content += text
                content = content.strip()
                if not content:
                    logger.warning(f"No text extracted from PDF: {file_path}")
                    return Response(
                        {"error": "No text could be extracted from the PDF"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                logger.debug(f"Extracted content (first 100 chars): {content[:100]}...")
        except Exception as e:
            logger.error(f"PDF extraction failed: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to extract PDF content", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Save PortfolioItem
        try:
            if PortfolioItem.objects.filter(source_url=source_url).exists():
                logger.error(f"PortfolioItem with source_url {source_url} already exists")
                return Response(
                    {"error": f"PortfolioItem with source_url {source_url} already exists"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            item = PortfolioItem(
                title=title or filename,
                content=content,
                source_type='pdf',
                source_url=source_url,
                metadata=metadata
            )
            item.save()
            item_serializer = PortfolioItemSerializer(item)
            logger.info(f"Existing PDF saved as PortfolioItem: {item.id}")
            return Response(
                {
                    "message": "Existing PDF processed successfully",
                    "item": item_serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            logger.error(f"Failed to save PortfolioItem: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to save portfolio item", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
