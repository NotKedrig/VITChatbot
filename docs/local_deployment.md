# Local Deployment Guide

This guide explains how to deploy the VITian Chatbot Local POC on a local development machine. This deployment utilizes a completely local backend (FastAPI), database (SQLite), and frontend (React/Vite).

## Prerequisites
- Python 3.10+
- Node.js 18+
- Gemini API Key

## 1. Environment Setup

1. **Clone the repository.**
2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate  # Windows
   # source .venv/bin/activate # Linux/Mac
   ```
3. **Install backend dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure Environment Variables:**
   Create a `.env` file in the root directory:
   ```ini
   GEMINI_API_KEY=your_key_here
   LLM_PROVIDER=gemini
   APP_TIMEZONE=Asia/Kolkata
   ```

## 2. Backend Startup

The backend is built on FastAPI and utilizes LangGraph for orchestrating the multi-agent architecture.

1. **Start the API Server:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   *Note: Starting the application automatically initializes the SQLite database and the `APScheduler` background thread for local notifications.*

## 3. Frontend Setup & Startup

The frontend is a React application built with Vite and TypeScript, featuring a premium glassmorphism dark-mode UI.

1. **Install Node modules:**
   ```bash
   cd frontend
   npm install
   ```
2. **Start the Development Server:**
   ```bash
   npm run dev
   ```
3. **Access the UI:**
   Open your browser and navigate to `http://localhost:5173`.

## 4. RAG Ingestion (Optional)

To ingest documents into the local ChromaDB vector store:
```bash
python -m app.rag.ingest
```

## 5. Running Tests

To execute the automated regression suite (0 live API calls via mocking):
```bash
pytest tests/ -v
```

## 6. Core Demonstration Flows

Once the frontend and backend are running, you can test the following flows directly from the UI:

1. **Company Research**: Ask *"What are the eligibility requirements for Novatech?"* The Chat UI will show the `Supervisor → Company Research` routing and return a grounded answer with citations.
2. **Study Planning**: Ask *"Create a study plan for Novatech. I have 10 hours per week."* The Study Plan tab will illuminate green, and the generated JSON plan will be rendered visually.
3. **Adaptive Planning**: Ask *"I scored 40% in DSA."* The dashboard will update the Skill Mastery section to **Weak**, and the Study Plan view will highlight the adjusted priority with an alert icon.
4. **Notifications**: Ask *"Remind me tomorrow at 7 PM to revise DSA."* The dashboard will display the pending reminder, scheduled locally via `APScheduler`.
5. **Multi-Turn Memory**: Send a follow-up question. The LangGraph `MemorySaver` preserves the session thread seamlessly on the backend.
