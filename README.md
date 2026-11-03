# Vidyalankar Institute of Technology (VIT), Mumbai — AI College Enquiry Chatbot

A production-grade, AI-powered enquiry assistant and financial dashboard for **Vidyalankar Institute of Technology (VIT), Mumbai** (DTE Code: 3139). Grounded strictly in official records from [https://vit.edu.in/](https://vit.edu.in/) and Fee Regulating Authority (FRA) guidelines.

Built with Flask, Google Gemini API (with Anthropic Claude fallback support), Server-Sent Events (SSE) real-time streaming, light/dark theme switcher, and an interactive Financial Dashboard.

---

## 🌟 Key Features

1. **Official Google Gemini & Multi-Model Resilience**:
   - Primary AI inference via official `google-genai` SDK using fast low-latency models (`gemini-3.5-flash-lite`, `gemini-flash-lite-latest`, `gemini-3-flash-preview`).
   - Seamless token-by-token streaming over Server-Sent Events (SSE).
   - Multi-provider fallback to Anthropic Claude (`claude-3-5-sonnet`).

2. **Official vit.edu.in RAG Grounding & Anti-Hallucination**:
   - TF-IDF style vector similarity search over official syllabus, admissions, MHT-CET/JEE cutoffs, placements, and campus contact records.
   - Clickable source verification chips (`[Source Title](url)`) linking directly to official vit.edu.in pages.
   - Deterministic Metrics Query Engine for exact category-wise fees and year-wise branch cutoffs.

3. **Interactive Financial Dashboard Modal**:
   - Comprehensive fee structure for all B.Tech CAP categories: Open / General, OBC / EBC / EWS, SC / ST / VJ / NT, and TFWS.
   - Year-wise breakdown (Tuition Fee, Development Fee, Annual Fee, and Estimated 4-Year Total).
   - Scholarship cards (MahaDBT, Government Concessions, TFWS, Minority Scholarships).

4. **Light & Dark Theme Switcher**:
   - Modern theme switcher in both the desktop topbar and mobile drawer.
   - Adheres to Modern Web Guidance: `<meta name="color-scheme" content="light dark">`, CSS custom property sync, and inline FOUC prevention script.
   - Persists user preference in `localStorage` and synchronizes across open tabs.

5. **Production Ready & Serverless Compatible**:
   - Ready for Vercel deployment with `api/index.py` and `vercel.json`.
   - Adaptive database persistence: uses local SQLite on desktop, safe `/tmp` storage on serverless Lambdas.
   - In-memory sliding-window rate limiter protecting against API abuse.

---

## 📁 Project Structure

```text
VIT-College-Enquiry-Chatbot/
├── api/
│   └── index.py                # Vercel serverless function WSGI entry point
├── data/
│   ├── vit_knowledge_base.json # Grounded official VIT knowledge chunks & URLs
│   ├── vit_fees.json           # Approved category-wise fee records
│   └── vit_cutoffs.json        # Year-wise branch MHT-CET/JEE cutoffs
├── static/
│   ├── app.js                  # Frontend client: streaming, Markdown, theme, modal
│   └── style.css               # Navy & cyan design system with Light/Dark theme
├── templates/
│   └── index.html              # Main chat application HTML template
├── tests/
│   ├── test_chatbot.py         # Unit tests for RAG, rate limiting, and chat API
│   ├── test_theme.py           # Verification tests for Light/Dark theme feature
│   ├── test_live_interactions.py # Live streaming & integration tests
│   └── verify_live.py          # Quick health and element assertion script
├── app.py                      # Flask backend application
├── conversation_store.py       # Session transcripts & history persistence layer
├── metrics_db.py               # Deterministic query engine for fees & cutoffs
├── rag_engine.py               # RAG indexing, search scoring, and crawler
├── rate_limiter.py             # Sliding-window in-memory rate limiter
├── refresh_knowledge.py        # CLI script to re-index knowledge from vit.edu.in
├── requirements.txt            # Python dependencies
├── vercel.json                 # Vercel deployment configuration & route rewrites
├── .env.example                # Template for environment variables
└── .gitignore                  # Git exclusions (.env, .venv, *.db, pycache)
```

---

## 🚀 Local Development Setup

### 1. Clone the Repository
```bash
git clone https://github.com/talhakh1447m/VIT-College-Enquiry-Chatbot.git
cd VIT-College-Enquiry-Chatbot
```

### 2. Create and Activate Virtual Environment
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` with your API keys:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
PORT=5000
```

### 5. Run the Application
```bash
python app.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser.

### 6. Run Test Suite
```bash
python -m unittest discover tests
```

---

## ☁️ Deployment on Vercel

1. **Push your code to GitHub**:
   ```bash
   git add .
   git commit -m "Deploy VIT College Enquiry Chatbot"
   git push -u origin main
   ```

2. **Deploy via Vercel Dashboard or CLI**:
   - Go to [Vercel](https://vercel.com) and click **Add New > Project**.
   - Import `VIT-College-Enquiry-Chatbot`.
   - Set **Framework Preset** to **Other**.
   - Add Environment Variables:
     - `GEMINI_API_KEY` = *your Google Gemini API key*
     - `GEMINI_MODEL` = `gemini-3.5-flash-lite`
   - Click **Deploy**.

---

## 🛡️ License & Attributions
- Grounded on official public records from [Vidyalankar Institute of Technology (VIT), Mumbai](https://vit.edu.in/).
- Built for educational guidance and college enquiry assistance.
