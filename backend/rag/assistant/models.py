from django.db import models
import json
from sentence_transformers import SentenceTransformer
import PyPDF2
import requests
from bs4 import BeautifulSoup
from django.conf import settings
import os
import logging

logger = logging.getLogger(__name__)

class PortfolioItem(models.Model):
    SOURCE_TYPE_CHOICES = (
        ('pdf', 'PDF Document'),
        ('social_media', 'Social Media'),
        ('website', 'Personal Website'),
    )

    title = models.CharField(max_length=200, blank=True, null=True)
    content = models.TextField(blank=True, null=True)
    source_type = models.CharField(max_length=50, choices=SOURCE_TYPE_CHOICES, default='pdf')
    source_url = models.CharField(max_length=255, blank=True, null=True)
    vector_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(default=dict, blank=True)

    def extract_pdf_content(self, pdf_path):
        try:
            logger.info(f"Extracting content from PDF: {pdf_path}")
            if not os.path.exists(pdf_path):
                logger.error(f"File does not exist: {pdf_path}")
                raise FileNotFoundError(f"File does not exist: {pdf_path}")
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                content = ""
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        content += text
                content = content.strip()
                if not content:
                    logger.warning(f"No text extracted from PDF: {pdf_path}")
                    content = "No extractable text in PDF"
                logger.info(f"Extracted content (length={len(content)}): {content[:100]}...")
                return content
        except Exception as e:
            logger.error(f"PDF extraction failed for {pdf_path}: {str(e)}")
            raise

    def extract_web_content(self, url):
        try:
            logger.info(f"Scraping web content from: {url}")
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            for script in soup(["script", "style"]):
                script.decompose()
            content = ' '.join(soup.stripped_strings).strip()
            if not content:
                logger.warning(f"No content scraped from URL: {url}")
                content = "No extractable content from URL"
            logger.info(f"Scraped content (length={len(content)}): {content[:100]}...")
            return content
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            raise

    def save(self, *args, **kwargs):
        logger.info(f"Saving PortfolioItem: title={self.title}, source_url={self.source_url}, id={self.id}")
        if not self.content and self.source_url:
            try:
                if self.source_type == 'pdf':
                    file_path = str(self.source_url)  # Convert to string
                    if not file_path.startswith(str(settings.MEDIA_ROOT)):  # Convert MEDIA_ROOT to string
                        file_path = os.path.join(settings.MEDIA_ROOT, self.source_url.replace('media/', ''))
                        file_path = str(file_path)  # Ensure file_path is a string
                    self.content = self.extract_pdf_content(file_path)
                elif self.source_type in ['social_media', 'website']:
                    self.content = self.extract_web_content(self.source_url)
            except Exception as e:
                logger.error(f"Content extraction failed: {str(e)}")
                self.content = f"Error extracting content: {str(e)}"

        super().save(*args, **kwargs)  # Save to Django database to get an ID

        if not self.id:
            logger.error("No ID assigned after saving to database")
            raise ValueError("No ID assigned after saving to database")

        if self.content and not self.vector_id:
            try:
                global _cached_st_model
                if '_cached_st_model' not in globals() or _cached_st_model is None:
                    logger.info("Initializing SentenceTransformer model: all-MiniLM-L6-v2")
                    _cached_st_model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info(f"Generating embedding for content (length={len(self.content)})")
                embedding = _cached_st_model.encode(self.content).tolist()
                from chromadb import PersistentClient
                client = PersistentClient(path=str(settings.CHROMA_DB_PATH))  # Convert to string
                logger.info("Creating or accessing portfolio collection")
                collection = client.get_or_create_collection("portfolio")
                self.vector_id = f"item_{self.id}"  # Ensure consistent vector_id
                metadata_json = json.dumps(self.metadata) if self.metadata else "{}"
                logger.info(f"Upserting item {self.vector_id} to ChromaDB")
                collection.upsert(
                    ids=[self.vector_id],
                    embeddings=[embedding],
                    metadatas=[{
                        "title": self.title or "",
                        "content": self.content[:1000],
                        "source_type": self.source_type,
                        "source_url": self.source_url or "",
                        "metadata": metadata_json
                    }],
                    documents=[self.content]
                )
                logger.info(f"Successfully upserted item {self.vector_id}")
                super().save(*args, **kwargs)  # Save again to update vector_id
            except Exception as e:
                logger.error(f"ChromaDB upsert failed: {str(e)}")
                self.content = f"ChromaDB upsert failed: {str(e)}"
                super().save(*args, **kwargs)  # Save error message
        else:
            logger.info(f"Skipping ChromaDB upsert for item {self.id}: content={bool(self.content)}, vector_id={self.vector_id}")

    def __str__(self):
        return f"{self.source_type}: {self.title or self.id}"

    class Meta:
        indexes = [
            models.Index(fields=['source_type']),
            models.Index(fields=['created_at']),
        ]