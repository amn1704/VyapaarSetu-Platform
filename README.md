<div align="center">

# 🏛️ VyapaarSetu

### Unified Business Identity Platform for Karnataka

[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite)](https://sqlite.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**English | ಕನ್ನಡ (Kannada)**

</div>

---

VyapaarSetu (ವ್ಯಾಪಾರಸೇತು) is a production-ready business identity resolution platform designed for Karnataka's Department of Commerce & Industries. It unifies fragmented business records from multiple departmental sources (Municipal, Tax, Labour, Pollution Control, etc.) into canonical business identities with persistent UBIDs (Unified Business Identifiers).

## ✨ Key Features

### 🔗 Identity Resolution & Linking
- **Entity Matching Algorithm**: Fuzzy name matching, PAN/GSTIN anchoring, address similarity scoring
- **Confidence Scoring**: Explainable match confidence with audit trails
- **Automated Linking**: High-confidence matches auto-link; ambiguous cases route to review
- **UBID Generation**: Persistent unique identifiers for resolved business entities

### 👥 Human-in-the-Loop Review Queue
- **Review Interface**: Side-by-side comparison of suspected duplicate records
- **Officer Summary**: AI-generated plain-English explanation of match signals
- **One-Click Decisions**: Same Business / Different Businesses / Review Later
- **Audit Trail**: Complete decision history with reviewer attribution

### 📊 Business Directory
- **Unified Registry**: All businesses with their UBIDs and linked source records
- **Advanced Search**: Full-text search across names, PAN, GSTIN, addresses
- **Smart Filters**: Filter by status (Active/Dormant/Closed), sector, PAN/GSTIN availability
- **Export**: CSV export with all business attributes
- **Pagination**: Efficient loading for large datasets

### 🗺️ Geospatial Visualization
- **Interactive Map**: Map-based view of registered businesses across Karnataka
- **PIN Code Hotspots**: Identify business concentration areas
- **Status Indicators**: Color-coded by activity status (Green=Active, Yellow=Dormant, Red=Closed)
- **Click-through**: Navigate to business details from map markers

### 🤖 AI-Powered Query Engine
- **Natural Language Queries**: Ask questions in plain English/Kannada
- **Local LLM**: Uses Ollama with Llama 3.1 (no external API calls, data stays local)
- **Text-to-SQL**: Converts natural language to safe, read-only SQL queries
- **Governed Access**: Deterministic templates for high-value patterns; SQL validation blocks unsafe statements
- **Example Queries**:
  - "Find active factories in PIN 560058 with no inspection in last 18 months"
  - "PAN-anchored businesses missing GSTIN capture"
  - "Dormant entities showing recent department activity"

### 📈 Analytics Dashboard
- **Real-time Metrics**: Total records, linked businesses, pending reviews, duplicate reduction rate
- **Department Coverage**: Visual breakdown of records by source system
- **Business Type Distribution**: Pie chart of sectors (Engineering, Electronics/IT, Chemicals, Services)
- **Activity Status Breakdown**: Active, Dormant, Closed counts
- **Match Confidence Bands**: Auto-link ready, Keep separate, Human review bands
- **PIN Code Analysis**: Geographic hotspots of business concentration

### 🌐 Bilingual Support (English + Kannada)
- **Complete UI Translation**: All interface elements available in English and Kannada
- **One-Click Toggle**: Language switcher in the header
- **Native Kannada**: Professional translations for government use

### 🔒 Security & Governance
- **Read-Only Views**: Query engine uses read-only database views
- **PII Protection**: No raw PII sent to external LLMs; local inference only
- **Audit Logging**: All reviewer decisions logged with timestamps
- **CORS Protection**: Configurable allowed origins
- **JWT Authentication**: Secure API access

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │
│  │  Dashboard  │ │ Review Queue│ │   Business Directory │ │
│  └─────────────┘ └─────────────┘ └─────────────────────┘ │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │
│  │Query Engine │ │  Map View   │ │  Activity Status    │ │
│  └─────────────┘ └─────────────┘ └─────────────────────┘ │
│                                                             │
│  React 18 + Vite + TailwindCSS + Recharts + React-Leaflet │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ REST API
┌─────────────────────────────────────────────────────────────┐
│                        BACKEND                              │
│                                                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │
│  │ Entity      │ │  Review     │ │   AI/LLM Service    │ │
│  │ Resolution  │ │   Queue     │ │   (Local Ollama)    │ │
│  └─────────────┘ └─────────────┘ └─────────────────────┘ │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │
│  │  Business   │ │   Query     │ │   Data Ingestion    │ │
│  │  Directory  │ │   Engine    │ │   & Normalization   │ │
│  └─────────────┘ └─────────────┘ └─────────────────────┘ │
│                                                             │
│  FastAPI + Async SQLAlchemy + Pydantic + SQLite/PostgreSQL│
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Node.js 18+
- Python 3.11+
- Ollama (for local LLM inference)

### 1. Clone & Setup

```bash
git clone https://github.com/amn1704/VyapaarSetu-Platform.git
cd VyapaarSetu-Platform
```

### 2. Install Ollama & Models

```bash
# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Pull required models
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

### 3. Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Setup environment
cp backend/.env.example backend/.env
# Edit backend/.env with your settings

# Run database migrations (if any)
cd backend
alembic upgrade head  # if using Alembic
cd ..

# Start backend
uvicorn backend.main:app --reload --port 8000
```

### 4. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The app will be available at `http://localhost:5173` with API proxying to `http://localhost:8000`.

## 📁 Project Structure

```
VyapaarSetu-Platform/
├── backend/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Configuration settings
│   ├── schemas.py              # Pydantic models
│   ├── auth.py                 # JWT authentication
│   ├── routers/
│   │   ├── legacy.py           # Main API endpoints
│   │   └── admin.py            # Admin operations
│   ├── services/
│   │   ├── entity_resolution.py # Matching algorithm
│   │   └── llm_service.py      # Ollama integration
│   ├── worker.py               # Celery background tasks
│   ├── models/                 # SQLAlchemy models
│   ├── prompts/                # LLM prompts
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx        # Analytics dashboard
│   │   │   ├── ReviewQueue.jsx      # Review interface
│   │   │   ├── BusinessDirectory.jsx # Business registry
│   │   │   ├── QueryEngine.jsx      # AI query interface
│   │   │   ├── ActivityStatus.jsx   # Business timeline
│   │   │   └── LandingPage.jsx      # Public landing
│   │   ├── components/
│   │   │   └── Layout.jsx          # App shell
│   │   ├── utils/
│   │   │   └── translations.js     # English + Kannada
│   │   ├── lib/
│   │   │   └── api.js              # API client
│   │   └── App.jsx
│   ├── public/
│   └── package.json
│
├── docs/
│   └── DEPLOYMENT.md           # Deployment guide
│
├── README.md
└── LICENSE
```

## ⚙️ Configuration

### Backend (.env)

```env
# Database
DATABASE_URL=sqlite+aiosqlite:///./vyapaarsetu.db

# Security
JWT_SECRET_KEY=your-secret-key-here
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# AI/Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# Matching Thresholds
AUTO_MATCH_THRESHOLD=0.85
REVIEW_QUEUE_THRESHOLD=0.60

# Environment
DEBUG=true
LOG_LEVEL=INFO
```

### Frontend (.env)

```env
VITE_API_BASE_URL=             # Production API URL
VITE_DEV_API_PROXY_TARGET=http://localhost:8000  # Dev proxy
```

## 📊 Database Schema

The platform uses a graph-like relational schema:

- **ubid_registry**: Canonical business identities
- **raw_records**: Source system records
- **normalized_records**: Cleaned/standardized records
- **record_links**: Many-to-many UBID ↔ Raw record associations
- **review_queue**: Pending human review cases
- **review_decisions**: Audit log of reviewer actions
- **activity_events**: Business lifecycle events

## 🔧 Development

### Running Tests

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

### Code Quality

```bash
# Backend linting
flake8 backend/
black backend/

# Frontend linting
cd frontend
npm run lint
```

## 📦 Deployment

### Frontend (Vercel/Netlify)

1. Connect GitHub repo to Vercel
2. Set root directory to `frontend/`
3. Build command: `npm run build`
4. Output directory: `dist`
5. Set environment variable: `VITE_API_BASE_URL=https://your-api.com`

### Backend (Docker)

```bash
docker build -t vyapaarsetu-backend .
docker run -p 8000:8000 --env-file .env vyapaarsetu-backend
```

### Backend (VM/Cloud)

See `docs/DEPLOYMENT.md` for detailed production deployment instructions including:
- PostgreSQL setup
- Nginx reverse proxy
- SSL/TLS configuration
- Systemd service files
- Monitoring with Prometheus/Grafana

## 🎯 Use Cases

1. **Department Integration**: Unify records from Municipal, Tax, Labour, Pollution Control boards
2. **Duplicate Detection**: Identify businesses registered under slightly different names
3. **Compliance Monitoring**: Track inspection status, renewal dates, activity signals
4. **Investment Promotion**: Identify active manufacturing clusters by PIN code
5. **Policy Research**: Query business demographics for evidence-based policymaking

## 🤝 Contributing

We welcome contributions!

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 🙏 Acknowledgments

- Karnataka Department of Commerce & Industries for the use case and requirements
- Ollama team for local LLM inference capabilities
- FastAPI and React communities for excellent tooling

---

<div align="center">

**Made with ❤️ for Karnataka**

<a href="https://mail.google.com/mail/?view=cm&fs=1&to=amandell1705@gmail.com&su=Bug%20Report%20-%20VyapaarSetu">
Report Bug
</a>

</div>
