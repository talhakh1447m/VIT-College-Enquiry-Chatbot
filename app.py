"""
VIT Mumbai College Enquiry Chatbot — Real AI Assistant
Features:
- Official Anthropic Claude API (with Gemini resilient fallback)
- Real-time token-by-token streaming via Server-Sent Events (SSE)
- RAG grounded on https://vit.edu.in/ with live verification for recent notices
- SQLite session persistence, rate limiting, and comprehensive system prompt
"""

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request, stream_with_context

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("vit_chatbot")

# Local modules
from rag_engine import kb_engine
from metrics_db import metrics_engine
import conversation_store
from rate_limiter import SimpleRateLimiter

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static")
)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # Max 64 KB JSON payload

# Initialize Rate Limiter: 30 requests per minute per IP
rate_limiter = SimpleRateLimiter(max_requests=30, window_seconds=60)

# Configuration from Environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022").strip()

# Ordered candidate list of Gemini models to guarantee high availability
# If a model hits quota (429) or is deprecated (404), the engine cascades immediately
DEFAULT_GEMINI_MODELS = [
    GEMINI_MODEL,
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
]
GEMINI_CANDIDATE_MODELS = []
for m in DEFAULT_GEMINI_MODELS:
    if m and m not in GEMINI_CANDIDATE_MODELS:
        GEMINI_CANDIDATE_MODELS.append(m)

# Initialize Gemini Client (Primary AI Engine)
gemini_client = None
if GEMINI_API_KEY and not GEMINI_API_KEY.startswith("YOUR_"):
    try:
        from google import genai
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("Google Gemini client initialized as primary provider with candidate models: %s", GEMINI_CANDIDATE_MODELS)
    except Exception as e:
        logger.error("Failed to initialize Google Gemini client: %s", e)

# Initialize Anthropic Client (Optional fallback)
anthropic_client = None
if ANTHROPIC_API_KEY and not ANTHROPIC_API_KEY.startswith("YOUR_"):
    try:
        import anthropic
        anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=30.0)
        logger.info("Anthropic Claude client initialized with model %s", ANTHROPIC_MODEL)
    except Exception as e:
        logger.error("Failed to initialize Anthropic client: %s", e)

# Initialize database
conversation_store.init_db()

SYSTEM_PROMPT = """
You are the Official VIT College Enquiry Assistant for Vidyalankar Institute of Technology (VIT), Mumbai (DTE Code: 3139).
Your mission is to provide accurate, comprehensive, and well-structured guidance for prospective students, parents, and visitors.

MANDATORY NUMERICAL ACCURACY FOR FEES & CUTOFFS (ZERO GUESSWORK):
1. Whenever the user asks for fees (branch fees, 4-year fees, category fees for OBC/SC/ST/EWS/TFWS, or management quota):
   - You MUST extract and report the exact numerical amounts in ₹ provided in the AUTHORITATIVE NUMERICAL DATA context block.
   - Breakdown: State the Tuition Fee, Development Fee, and Total Annual Payable Fee.
   - State the Total 4-Year Programme Fee (e.g. Open/General: ₹8,12,000; OBC/EBC: ₹4,58,960; SC/ST/TFWS: ₹1,05,916).
   - For category concessions, explain the subsidy scheme (e.g. MahaDBT EBC 50% tuition waiver; SC/ST 100% tuition waiver).
   - For Institute Level / Management Quota, state the approved branch-wise rates (Computer Engineering: ₹4,00,000/yr; IT: ₹3,50,000/yr; ECS: ₹2,50,000/yr; EXTC/Biomedical: ₹2,03,000/yr).
   - Format fee breakdowns in clean, easy-to-read Markdown comparison tables.
   - Cite the official source: [VIT Admissions Portal](https://vit.edu.in/admissions/) and Fee Regulating Authority (FRA) Maharashtra.

2. Whenever the user asks for admission cutoffs (MHT-CET percentile, JEE Main rank, category cutoffs, CAP rounds, or year-wise cutoffs):
   - You MUST report the exact published closing percentiles or merit ranks provided in the AUTHORITATIVE NUMERICAL DATA context block.
   - State the exact branch, State CET Cell Choice Code (e.g. Computer: 313924510, IT: 313924610), academic year (e.g. 2024-25, 2025-26), and CAP Round (Round 1, 2, or 3).
   - Present cutoffs in structured Markdown tables with columns: | Category | Category Code | Closing Cutoff (%ile) | State Merit Rank |.
   - Never confuse percentile with marks or rank.
   - If the user asks for a cutoff without mentioning the branch, present the branches or politely ask which branch they want to know about.
   - Cite the official source: [Maharashtra State CET Cell Portal](https://fe2026.mahacet.org/).

GENERAL PRINCIPLES & ANSWER QUALITY:
1. Ground all VIT-specific answers strictly on the verified knowledge base and official URLs.
2. Never invent, guess, or estimate fees or cutoffs. If a specific year's cutoff or quota is not published in the database, clearly state that the exact figure is unverified and direct the user to the official CET Cell portal.
3. For broad questions (course details, syllabus, placements), provide comprehensive, structured answers with headings, bullet points, and next steps.
4. Seamlessly understand follow-up questions (e.g. "Explain more", "What is the fee for OBC?", "What about Round 2?") without asking the user to repeat previous context.
""".strip()


FEES_DATA_FILE = BASE_DIR / "data" / "vit_fees.json"
CUTOFFS_DATA_FILE = BASE_DIR / "data" / "vit_cutoffs.json"
_FEES_DATA_CACHE = None
_CUTOFFS_DATA_CACHE = None


def load_authoritative_data():
    global _FEES_DATA_CACHE, _CUTOFFS_DATA_CACHE
    if _FEES_DATA_CACHE is None and FEES_DATA_FILE.exists():
        try:
            with open(FEES_DATA_FILE, "r", encoding="utf-8") as f:
                _FEES_DATA_CACHE = json.load(f)
        except Exception as err:
            logger.warning("Could not read vit_fees.json: %s", err)

    if _CUTOFFS_DATA_CACHE is None and CUTOFFS_DATA_FILE.exists():
        try:
            with open(CUTOFFS_DATA_FILE, "r", encoding="utf-8") as f:
                _CUTOFFS_DATA_CACHE = json.load(f)
        except Exception as err:
            logger.warning("Could not read vit_cutoffs.json: %s", err)


def get_authoritative_numerical_context(query: str = "") -> str:
    """Provide verified numerical data blocks from vit_fees.json and vit_cutoffs.json."""
    load_authoritative_data()
    q = query.lower() if query else ""
    blocks = []

    fee_tokens = ["fee", "fees", "cost", "scholarship", "tuition", "waiver", "ebc", "tfws", "obc", "sc", "st", "ews", "management", "quota", "acap", "installment"]
    if any(tok in q for tok in fee_tokens) or not q:
        if _FEES_DATA_CACHE:
            blocks.append(
                "--- AUTHORITATIVE NUMERICAL DATA - APPROVED FEES & SCHOLARSHIPS (FRA APPROVED / VIT MUMBAI 3139) ---\n"
                f"{json.dumps(_FEES_DATA_CACHE, indent=2, ensure_ascii=False)}\n"
                "--- END AUTHORITATIVE FEES DATA ---"
            )

    cutoff_tokens = ["cutoff", "cutoffs", "cut-off", "percentile", "score", "merit", "rank", "cet", "mht-cet", "jee", "round", "closing"]
    if any(tok in q for tok in cutoff_tokens) or not q:
        if _CUTOFFS_DATA_CACHE:
            blocks.append(
                "--- AUTHORITATIVE NUMERICAL DATA - PUBLISHED CAP CUTOFFS (MAHARASHTRA STATE CET CELL / VIT 3139) ---\n"
                f"{json.dumps(_CUTOFFS_DATA_CACHE, indent=2, ensure_ascii=False)}\n"
                "--- END AUTHORITATIVE CUTOFFS DATA ---"
            )

    return "\n\n".join(blocks)


def format_rag_context(chunks: List[Dict[str, Any]], message: str = "") -> str:
    """Format retrieved knowledge chunks into structured context text."""
    context_lines = ["--- BEGIN OFFICIAL VIT MUMBAI KNOWLEDGE BASE ---"]
    for i, c in enumerate(chunks, 1):
        is_live = " [LIVE VERIFIED FROM VIT.EDU.IN]" if c.get("is_live_verified") else ""
        context_lines.append(f"\n[Source Chunk {i}{is_live}]: {c.get('title')} ({c.get('category')})")
        context_lines.append(f"Official URL: {c.get('url')}")
        context_lines.append(f"Content: {c.get('content')}")
    context_lines.append("\n--- END OFFICIAL VIT MUMBAI KNOWLEDGE BASE ---")

    auth_numerical = get_authoritative_numerical_context(message)
    if auth_numerical:
        context_lines.append("\n" + auth_numerical)

    return "\n".join(context_lines)


def prepare_claude_messages(
    message: str,
    safe_history: List[Dict[str, str]],
    rag_context: str
) -> List[Dict[str, str]]:
    """Format messages array for Anthropic Claude ensuring alternating turns."""
    user_content_with_context = (
        f"{rag_context}\n\n"
        f"STUDENT ENQUIRY:\n{message}\n\n"
        f"Provide a comprehensive, well-structured response citing relevant official VIT URLs."
    )

    messages_payload: List[Dict[str, str]] = []
    for item in safe_history:
        role = item.get("role")
        content = item.get("content", "").strip()
        if not content:
            continue
        mapped_role = "user" if role == "user" else "assistant"
        if messages_payload and messages_payload[-1]["role"] == mapped_role:
            messages_payload[-1]["content"] += f"\n\n{content}"
        else:
            messages_payload.append({"role": mapped_role, "content": content})

    if messages_payload and messages_payload[-1]["role"] == "user":
        messages_payload[-1]["content"] += f"\n\n{user_content_with_context}"
    else:
        messages_payload.append({"role": "user", "content": user_content_with_context})

    return messages_payload


def stream_claude_response(
    messages_payload: List[Dict[str, str]]
) -> Generator[str, None, None]:
    """Stream token chunks from Anthropic Claude Messages API."""
    with anthropic_client.messages.stream(
        model=ANTHROPIC_MODEL,
        max_tokens=3000,
        temperature=0.2,
        system=SYSTEM_PROMPT,
        messages=messages_payload,
    ) as stream:
        for text in stream.text_stream:
            yield text


def stream_gemini_response(
    message: str,
    safe_history: List[Dict[str, str]],
    rag_context: str
) -> Generator[Tuple[str, str], None, None]:
    """Stream token chunks from Gemini API with automatic model cascade fallback.
    Yields (chunk_text, model_name).
    """
    from google.genai import types

    user_prompt = (
        f"{rag_context}\n\n"
        f"STUDENT ENQUIRY:\n{message}\n\n"
        f"Provide a comprehensive, well-structured response citing relevant official VIT URLs."
    )

    contents = []
    for item in safe_history:
        role = "user" if item.get("role") == "user" else "model"
        content = item.get("content", "").strip()
        if content:
            contents.append({"role": role, "parts": [{"text": content[:2500]}]})

    contents.append({"role": "user", "parts": [{"text": user_prompt}]})

    last_error = None
    for model_name in GEMINI_CANDIDATE_MODELS:
        try:
            logger.info("Attempting Gemini streaming with model: %s", model_name)
            response_stream = gemini_client.models.generate_content_stream(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.2,
                    max_output_tokens=3000,
                ),
            )
            has_yielded = False
            for chunk in response_stream:
                if chunk.text:
                    has_yielded = True
                    yield chunk.text, model_name
            if has_yielded:
                logger.info("Gemini stream completed successfully using model: %s", model_name)
                return
        except Exception as e:
            last_error = e
            logger.warning("Gemini model %s error (%s). Trying next candidate...", model_name, str(e)[:150])
            continue

    if last_error:
        raise last_error


# ---------------------------------------------------------------------------
# Flask Routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    """Render the main college enquiry chat page."""
    return render_template(
        "index.html",
        college_name="Vidyalankar Institute of Technology (VIT), Mumbai",
        active_provider="Google Gemini" if gemini_client else ("Anthropic Claude" if anthropic_client else "None")
    )


@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """Real-time SSE streaming chat endpoint."""
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "127.0.0.1"
    is_limited, retry_after = rate_limiter.is_rate_limited(client_ip)
    if is_limited:
        return jsonify({
            "error": f"Rate limit exceeded. Please wait {retry_after} seconds before sending another message.",
            "retry_after": retry_after
        }), 429

    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    history = payload.get("history", [])
    session_id = str(payload.get("session_id", "")).strip() or str(uuid.uuid4())

    if not message:
        return jsonify({"error": "Please enter a question about VIT Mumbai."}), 400
    if len(message) > 2000:
        return jsonify({"error": "Question exceeds the 2,000 character limit."}), 400

    # Clean history
    safe_history: List[Dict[str, str]] = []
    if isinstance(history, list):
        for item in history[-12:]:
            if isinstance(item, dict):
                role = str(item.get("role", "")).lower()
                content = str(item.get("content", "")).strip()
                if role in ("user", "assistant", "model", "bot") and content:
                    norm_role = "user" if role == "user" else "assistant"
                    safe_history.append({"role": norm_role, "content": content[:2500]})

    # RAG Retrieval
    retrieved_chunks = kb_engine.search(message, top_k=4)
    rag_context = format_rag_context(retrieved_chunks, message)

    # Format structured sources
    sources = []
    seen_urls = set()
    for chunk in retrieved_chunks:
        url = chunk.get("url")
        if url and url not in seen_urls:
            seen_urls.add(url)
            sources.append({
                "title": chunk.get("title", "Official VIT Source"),
                "url": url,
                "category": chunk.get("category", "General"),
                "is_live": chunk.get("is_live_verified", False)
            })

    # Generator for SSE
    def generate_events():
        # 1. Send sources metadata first
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'session_id': session_id})}\n\n"

        full_answer = []
        active_provider = ""
        active_model = ""

        try:
            if gemini_client:
                active_provider = "gemini"
                for chunk_text, model_used in stream_gemini_response(message, safe_history, rag_context):
                    active_model = model_used
                    full_answer.append(chunk_text)
                    yield f"data: {json.dumps({'type': 'chunk', 'text': chunk_text})}\n\n"
            elif anthropic_client:
                active_provider = "anthropic"
                active_model = ANTHROPIC_MODEL
                messages_payload = prepare_claude_messages(message, safe_history, rag_context)
                for chunk_text in stream_claude_response(messages_payload):
                    full_answer.append(chunk_text)
                    yield f"data: {json.dumps({'type': 'chunk', 'text': chunk_text})}\n\n"
            else:
                err_msg = "No AI API key is configured. Please set GEMINI_API_KEY in your .env file."
                yield f"data: {json.dumps({'type': 'error', 'error': err_msg})}\n\n"
                return

            complete_text = "".join(full_answer).strip()
            # 2. Persist message to SQLite
            try:
                conversation_store.save_message(session_id, "user", message)
                conversation_store.save_message(
                    session_id, "assistant", complete_text,
                    sources=sources, provider=active_provider, model=active_model
                )
            except Exception as e:
                logger.warning("Failed to persist conversation: %s", e)

            # 3. Send done event
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'provider': active_provider, 'model': active_model})}\n\n"

        except Exception as exc:
            logger.error("Streaming error: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'error': str(exc)[:300]})}\n\n"

    return Response(stream_with_context(generate_events()), content_type="text/event-stream")


@app.route("/api/chat", methods=["POST"])
def chat():
    """Standard non-streaming enquiry chat endpoint."""
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "127.0.0.1"
    is_limited, retry_after = rate_limiter.is_rate_limited(client_ip)
    if is_limited:
        return jsonify({
            "error": f"Rate limit exceeded. Please wait {retry_after} seconds.",
            "retry_after": retry_after
        }), 429

    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    history = payload.get("history", [])
    session_id = str(payload.get("session_id", "")).strip() or str(uuid.uuid4())

    if not message:
        return jsonify({"error": "Please enter a question about VIT Mumbai."}), 400
    if len(message) > 2000:
        return jsonify({"error": "Question exceeds the 2,000 character limit."}), 400

    safe_history: List[Dict[str, str]] = []
    if isinstance(history, list):
        for item in history[-10:]:
            if isinstance(item, dict):
                role = str(item.get("role", "")).lower()
                content = str(item.get("content", "")).strip()
                if role in ("user", "assistant", "model", "bot") and content:
                    norm_role = "user" if role == "user" else "assistant"
                    safe_history.append({"role": norm_role, "content": content[:2000]})

    retrieved_chunks = kb_engine.search(message, top_k=4)
    rag_context = format_rag_context(retrieved_chunks, message)

    sources = []
    seen_urls = set()
    for chunk in retrieved_chunks:
        url = chunk.get("url")
        if url and url not in seen_urls:
            seen_urls.add(url)
            sources.append({
                "title": chunk.get("title", "Official VIT Source"),
                "url": url,
                "category": chunk.get("category", "General"),
                "is_live": chunk.get("is_live_verified", False)
            })

    answer = ""
    provider_name = ""
    model_name = ""

    if gemini_client:
        from google.genai import types
        user_prompt = f"{rag_context}\n\nSTUDENT ENQUIRY:\n{message}\n\nProvide a comprehensive response."
        last_error = None
        for cand_model in GEMINI_CANDIDATE_MODELS:
            try:
                resp = gemini_client.models.generate_content(
                    model=cand_model,
                    contents=[{"role": "user", "parts": [{"text": user_prompt}]}],
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.2,
                        max_output_tokens=3000
                    )
                )
                answer = (resp.text or "").strip()
                provider_name = "gemini"
                model_name = cand_model
                break
            except Exception as e:
                last_error = e
                logger.warning("Gemini non-streaming error with model %s: %s", cand_model, str(e)[:150])
                continue

        if not answer and last_error:
            if anthropic_client:
                try:
                    messages_payload = prepare_claude_messages(message, safe_history, rag_context)
                    res = anthropic_client.messages.create(
                        model=ANTHROPIC_MODEL,
                        max_tokens=3000,
                        temperature=0.2,
                        system=SYSTEM_PROMPT,
                        messages=messages_payload,
                    )
                    text_blocks = [b.text for b in res.content if hasattr(b, "text")]
                    answer = "".join(text_blocks).strip()
                    provider_name = "anthropic-fallback"
                    model_name = ANTHROPIC_MODEL
                except Exception as e:
                    return jsonify({"error": f"AI service error: {str(e)[:200]}"}), 502
            else:
                return jsonify({"error": f"Gemini error: {str(last_error)[:200]}"}), 502
    elif anthropic_client:
        try:
            messages_payload = prepare_claude_messages(message, safe_history, rag_context)
            res = anthropic_client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=3000,
                temperature=0.2,
                system=SYSTEM_PROMPT,
                messages=messages_payload,
            )
            text_blocks = [b.text for b in res.content if hasattr(b, "text")]
            answer = "".join(text_blocks).strip()
            provider_name = "anthropic"
            model_name = ANTHROPIC_MODEL
        except Exception as exc:
            return jsonify({"error": f"Anthropic error: {str(exc)[:200]}"}), 502
    else:
        return jsonify({"error": "No AI API key is configured. Please set GEMINI_API_KEY in .env."}), 503

    try:
        conversation_store.save_message(session_id, "user", message)
        conversation_store.save_message(session_id, "assistant", answer, sources=sources, provider=provider_name, model=model_name)
    except Exception as e:
        logger.warning("Failed to persist conversation: %s", e)

    return jsonify({
        "answer": answer,
        "provider": provider_name,
        "model": model_name,
        "sources": sources,
        "session_id": session_id
    })


@app.route("/api/health")
def health():
    """Health check endpoint providing model, knowledge base, and provider status."""
    return jsonify({
        "status": "healthy",
        "service": "VIT Mumbai Enquiry Chatbot",
        "providers": {
            "gemini": {
                "configured": bool(gemini_client),
                "model": GEMINI_CANDIDATE_MODELS[0] if GEMINI_CANDIDATE_MODELS else "none",
                "available_models": GEMINI_CANDIDATE_MODELS
            },
            "anthropic": {
                "configured": bool(anthropic_client),
                "model": ANTHROPIC_MODEL
            }
        },
        "active_provider": "gemini" if gemini_client else ("anthropic" if anthropic_client else "none"),
        "knowledge_base": {
            "chunks_count": len(kb_engine.chunks),
            "source": kb_engine.metadata.get("source"),
            "last_updated": kb_engine.metadata.get("last_updated")
        }
    })


@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    """Retrieve list of recent chat sessions."""
    sessions = conversation_store.list_recent_sessions(limit=25)
    return jsonify({"sessions": sessions})


@app.route("/api/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    """Retrieve message history for a given session."""
    messages = conversation_store.get_session_messages(session_id)
    return jsonify({"session_id": session_id, "messages": messages})


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    """Delete a session."""
    success = conversation_store.delete_session(session_id)
    return jsonify({"success": success})


@app.route("/api/sources")
def get_sources():
    """Return all official VIT Mumbai indexed pages for reference."""
    from rag_engine import OFFICIAL_PAGES
    return jsonify({"sources": OFFICIAL_PAGES})


@app.route("/api/fees", methods=["GET"])
def get_fees():
    """Return official FRA-approved fee structure and scholarship details."""
    load_authoritative_data()
    return jsonify(_FEES_DATA_CACHE or {})


@app.route("/api/knowledge/refresh", methods=["POST"])
def refresh_knowledge():
    """Trigger on-demand live re-indexing of official vit.edu.in pages."""
    try:
        result = kb_engine.refresh()
        return jsonify(result)
    except Exception as e:
        logger.error("Knowledge base refresh failed: %s", e)
        return jsonify({"status": "failed", "error": str(e)}), 500


@app.errorhandler(413)
def request_entity_too_large(_error):
    return jsonify({"error": "Request payload too large. Please shorten your message."}), 413


@app.errorhandler(404)
def not_found(_error):
    return jsonify({
        "error": "Resource not found",
        "path": request.path,
        "full_path": request.full_path,
        "headers": dict(request.headers),
        "environ": {k: str(v) for k, v in request.environ.items() if k.startswith(("HTTP_", "PATH_", "REQUEST_", "RAW_"))}
    }), 404


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
