# Customer Support Call Quality Analyzer

## Overview
Customer Support Call Quality Analyzer is an AI-powered platform for analyzing, evaluating, and improving customer support calls. It leverages advanced language models and analytics to provide insights, sentiment analysis, and quality metrics for support conversations. The system features a FastAPI backend, a modern React (Vite) frontend, and a modular AI pipeline for evaluation and reporting.

## Features
- Upload and analyze customer support call transcripts
- Automated call chunking, embedding, and evaluation
- Sentiment and quality scoring using LLMs
- Interactive dashboard and insights for agents and managers
- Chatbot integration for Q&A and support
- Secure authentication and role-based access

## Project Structure
```
project/
├── backend/         # FastAPI backend, API, database, ETL, services
├── ai_pipeline/     # Core AI logic: evaluation, embeddings, chunking
├── chatbot/         # Chatbot logic, LLM pipelines, vector store
├── frontend/        # React + Vite frontend (dashboard, widgets)
├── data/            # Data storage (bronze, silver, gold layers)
├── requirements.txt # Python dependencies for backend/AI
```

## How It Works
1. **Transcript Upload:** Users upload call transcripts via the frontend.
2. **AI Pipeline:** The backend processes transcripts, chunks them, generates embeddings, and evaluates quality using LLMs.
3. **Database & ETL:** Results are stored, transformed, and made available for reporting and dashboarding.
4. **Frontend Dashboard:** Users view insights, metrics, and interact with the chatbot for further analysis.

## Backend Setup (FastAPI)
1. Install Python 3.9+ and create a virtual environment.
2. Install dependencies:
	```sh
	pip install -r requirements.txt
	```
3. Set up your environment variables in `backend/.env` (see template in the file, do not commit secrets).
4. Run the backend server:
	```sh
	uvicorn backend.main:app --reload
	```

## Frontend Setup (React + Vite)
1. Install Node.js (v18+) and npm.
2. Navigate to the `frontend/` folder:
	```sh
	cd frontend
	npm install
	npm run dev
	```

## Environment Variables
- Never commit real API keys or secrets. Use `.env` files locally and ensure they are in `.gitignore`.
- Example variables: `GROQ_API_KEY`, `DATABASE_URL`, `GEMINI_API_KEY`, etc.

## Contributing
- Fork the repo and create a feature branch.
- Submit pull requests with clear descriptions.

## License
This project is for educational and demonstration purposes.

---
For more details, see code comments and individual module READMEs (if available).