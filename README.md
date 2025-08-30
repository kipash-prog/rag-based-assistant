# RAG-Based Portfolio Assistant

An end-to-end Retrieval-Augmented Generation (RAG) assistant that answers questions about a portfolio using PDFs and web content as a knowledge base. The stack includes:

- Backend: Django + Django REST Framework
- Vector DB: ChromaDB (persistent client)
- Embeddings: sentence-transformers (all-MiniLM-L6-v2)
- LLM: Groq Chat Completions API
- Frontend: React (CRA)

## Features
- Upload PDFs or register existing PDFs in `media/` and auto-extract text.
- Add web content (website or social media link); scrape and index content.
- Query endpoint retrieves relevant items from Chroma and asks the LLM.
- Manual refresh endpoint to re-scrape and re-embed a specific URL.
- Professional frontend (optional simplified Q&A-only mode).

## Project Structure
```
backend/
  rag/
    assistant/               # App: models, serializers, views, urls
    rag/                     # Django project (settings, urls, wsgi)
    media/                   # PDF storage (served in dev)
    chroma_data/             # ChromaDB persistent data
  requirements.txt           # Python dependencies
frontend/
  rag-assistant/             # React app (CRA)
README.md
```

## Prerequisites
- Python 3.10+
- Node.js 18+
- A Groq API key

## Backend Setup
1) Create virtual environment and install deps
```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) Environment variables
Create `backend/rag/.env` with:
```
GROQ_API_KEY=your_groq_api_key
CHROMA_DB_PATH=chroma_data
DJANGO_SECRET_KEY=dev-secret-key
DEBUG=True
```

3) Migrate and run server
```bash
cd backend/rag
python manage.py migrate
python manage.py runserver 8000
```

The API is mounted at `http://localhost:8000/api/` and serves media at `http://localhost:8000/media/...` in development.

## Frontend Setup
<img width="1185" height="687" alt="image" src="https://github.com/user-attachments/assets/c7f77b3c-56c3-4f0b-b53d-5bfee57d2219" />

```bash
cd frontend/rag-assistant
npm install
npm start
```

The app runs on `http://localhost:3000` and calls the backend at `http://localhost:8000/api/`.

## Core Endpoints
Base: `http://localhost:8000/api/`

- POST `query/`
  - Body: `{ "query": "Summarize my resume" }`
  - Returns: `{ response, items: [PortfolioItem...] }`

- POST `upload-pdf/`
  - Multipart: `file` (File), `title` (Text), `metadata` (JSON string)
  - JSON: `file` as data URL or raw base64, `title`, `metadata`

- POST `add-existing-pdf/`
  - JSON: `{ "filename": "resume.pdf", "title": "Resume", "metadata": {...} }`
  - Uses PDFs that already exist in `backend/rag/media/`

- POST `add-web-content/`
  - JSON: `{ "url": "https://...", "title": "My Link", "source_type": "website|social_media", "metadata": {...} }`

- POST `refresh-url/`
  - JSON: `{ "url": "https://...", "title": "Optional", "source_type": "website|social_media", "metadata": {...} }`
  - Re-scrapes the URL, updates content, and re-embeds.

## Postman Quickstart
- Add existing PDFs (skip base64):
  - POST `/api/add-existing-pdf/`
  - `{ "filename": "resume.pdf", "title": "Resume" }`

- Add web content:
  - POST `/api/add-web-content/`
  - `{ "url": "https://yoursite.com/about", "title": "About", "source_type": "website" }`

- Ask a question:
  - POST `/api/query/`
  - `{ "query": "What are my key skills from my resume?" }`

- Upload PDF via multipart:
  - `file` (File), `title` (Text), `metadata` (Text JSON)

## How It Works
1. Content ingestion
   - PDFs: text extracted with PyPDF2
   - Web: HTML fetched and cleaned via BeautifulSoup
2. Embeddings & Indexing
   - `all-MiniLM-L6-v2` generates embeddings
   - Items upserted into ChromaDB with metadata and documents
3. Query
   - User query embedded and matched in ChromaDB
   - Top results collected as context; Groq API produces final answer

## Configuration Details
- Settings: `backend/rag/rag/settings.py`
  - `.env` required (GROQ_API_KEY, CHROMA_DB_PATH, DEBUG, etc.)
  - CORS allows localhost:3000
  - Media served in dev via Django static route

## Troubleshooting
- 415 on upload: do not set Content-Type manually for multipart; let Postman/browser set it.
- “submitted data was not a file”: ensure `file` field type is File in Postman.
- “Invalid PDF file”: your base64 isn’t a real PDF. Prefer multipart, or regenerate base64 from a real PDF.
- Query returns no items: ensure content was saved and embedded (see logs). Try more specific query text.
- Groq errors: verify `GROQ_API_KEY` and internet access.

## Real-Time/On-Demand Updates
- Manual refresh: POST `/api/refresh-url/` to re-scrape and re-embed a given URL.
- Suggested next step: schedule periodic refresh (Celery + Redis) for website feeds and social profiles.

## Security Notes
- Keep `.env` out of version control.
- Avoid logging secrets; the code removes key fragments from logs.
- In production, enable HTTPS and secure cookies in settings.

## Development Scripts
```bash
# Backend
cd backend/rag
python manage.py runserver 8000

# Frontend
cd frontend/rag-assistant
npm start
```

## Requirements
Backend Python deps live in `backend/requirements.txt`.

## License
MIT (or your preferred license)



