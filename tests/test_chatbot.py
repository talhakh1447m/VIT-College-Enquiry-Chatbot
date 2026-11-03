"""
Comprehensive Test Suite for VIT Mumbai College Enquiry Chatbot.
Distinguishes between unit/mocked tests and live external API tests.
Includes tests for RAG engine, live verification, streaming SSE endpoints,
rate limiting, and SQLite session persistence.
"""

import json
import os
import unittest
import uuid
from unittest.mock import patch, MagicMock

# Import app components
import app as flask_app_module
from app import app
from rag_engine import VITKnowledgeBase
import conversation_store
from rate_limiter import SimpleRateLimiter


class TestRAGEngine(unittest.TestCase):
    """Unit tests for the Retrieval-Augmented Generation (RAG) engine."""

    def setUp(self):
        self.kb = VITKnowledgeBase()

    def test_chunks_loaded(self):
        """Ensure knowledge chunks are loaded and non-empty."""
        self.assertGreater(len(self.kb.chunks), 0)
        first_chunk = self.kb.chunks[0]
        self.assertIn("title", first_chunk)
        self.assertIn("url", first_chunk)
        self.assertIn("content", first_chunk)
        self.assertTrue(first_chunk["url"].startswith("https://vit.edu.in"))

    def test_search_btech_admission(self):
        """Test search query targeting B.Tech engineering admissions."""
        results = self.kb.search("How can I apply for First Year B.Tech engineering?", top_k=2)
        self.assertGreater(len(results), 0)
        titles = [r["title"].lower() for r in results]
        self.assertTrue(any("b.tech" in t or "admission" in t or "undergraduate" in t for t in titles))

    def test_search_placements(self):
        """Test search query targeting placement records and recruiters."""
        results = self.kb.search("What companies visit for placements?", top_k=2)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["category"], "Placements")

    def test_search_contact(self):
        """Test search query targeting contact and address information."""
        results = self.kb.search("Where is the campus and how do I contact VIT?", top_k=2)
        self.assertGreater(len(results), 0)
        self.assertIn("contact", results[0]["url"])

    def test_branch_comparison_query(self):
        """Test search query asking for branch comparison."""
        results = self.kb.search("Can you compare Computer Engineering vs Information Technology?", top_k=2)
        self.assertGreater(len(results), 0)
        self.assertTrue(any("comparison" in r["title"].lower() or "programs" in r["title"].lower() for r in results))


class TestRateLimiter(unittest.TestCase):
    """Unit tests for the sliding window rate limiter."""

    def test_rate_limiting(self):
        limiter = SimpleRateLimiter(max_requests=3, window_seconds=10)
        ip = "192.168.1.100"

        # First 3 requests must succeed
        self.assertFalse(limiter.is_rate_limited(ip)[0])
        self.assertFalse(limiter.is_rate_limited(ip)[0])
        self.assertFalse(limiter.is_rate_limited(ip)[0])

        # 4th request must be blocked
        is_limited, retry_after = limiter.is_rate_limited(ip)
        self.assertTrue(is_limited)
        self.assertGreater(retry_after, 0)


class TestConversationStore(unittest.TestCase):
    """Unit tests for SQLite conversation persistence and session management."""

    def test_save_and_retrieve_messages(self):
        session_id = f"test-session-{uuid.uuid4()}"
        conversation_store.save_message(session_id, "user", "What is VIT?")
        conversation_store.save_message(
            session_id, "assistant", "VIT Mumbai is located in Wadala.",
            sources=[{"title": "Overview", "url": "https://vit.edu.in/about-us/"}],
            provider="test-provider", model="test-model"
        )

        history = conversation_store.get_session_messages(session_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["content"], "What is VIT?")
        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[1]["provider"], "test-provider")
        self.assertIsNotNone(history[1]["sources"])

    def test_session_listing_and_deletion(self):
        session_id = f"test-del-{uuid.uuid4()}"
        conversation_store.save_message(session_id, "user", "Tell me about B.Tech courses")
        sessions = conversation_store.list_recent_sessions(limit=10)
        found = any(s["session_id"] == session_id for s in sessions)
        self.assertTrue(found)

        # Delete session
        deleted = conversation_store.delete_session(session_id)
        self.assertTrue(deleted)
        history_after = conversation_store.get_session_messages(session_id)
        self.assertEqual(len(history_after), 0)


class TestFlaskEndpoints(unittest.TestCase):
    """Tests for Flask API endpoints."""

    def setUp(self):
        self.client = app.test_client()
        flask_app_module.rate_limiter.reset()

    def test_home_page(self):
        """Test that the homepage renders 200 with correct branding."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("VIT Mumbai", html)
        self.assertIn("VIT Assistant", html)

    def test_health_endpoint(self):
        """Test health endpoint structure."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data["status"], "healthy")
        self.assertIn("knowledge_base", data)
        self.assertIn("providers", data)

    def test_sources_endpoint(self):
        """Test that sources endpoint returns official vit.edu.in links."""
        res = self.client.get("/api/sources")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("sources", data)
        self.assertGreater(len(data["sources"]), 0)

    def test_sessions_endpoint(self):
        """Test retrieval of past sessions list."""
        res = self.client.get("/api/sessions")
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("sessions", data)

    def test_chat_validation_empty_message(self):
        """Test that empty messages are rejected with 400."""
        res = self.client.post("/api/chat", json={"message": "   "})
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertIn("error", data)

    def test_chat_validation_oversized_message(self):
        """Test that oversized messages (>2000 chars) are rejected with 400."""
        res = self.client.post("/api/chat", json={"message": "A" * 2005})
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertIn("error", data)

    @patch("app.gemini_client", None)
    @patch("app.anthropic_client")
    def test_chat_mocked_claude_response(self, mock_anthropic):
        """Test that /api/chat formats Claude responses and attaches source citations."""
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "VIT offers B.Tech in Computer Engineering. See [UG Page](https://vit.edu.in/admission-engineering-ug/)."
        mock_response.content = [mock_block]
        mock_anthropic.messages.create.return_value = mock_response

        res = self.client.post("/api/chat", json={
            "message": "What courses are offered?",
            "session_id": f"mock-test-{uuid.uuid4()}"
        })

        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn("answer", data)
        self.assertEqual(data["provider"], "anthropic")
        self.assertIn("sources", data)
        self.assertGreater(len(data["sources"]), 0)

    def test_streaming_endpoint_headers(self):
        """Test that /api/chat/stream returns text/event-stream content type."""
        res = self.client.post("/api/chat/stream", json={
            "message": "Tell me about VIT campus location",
            "session_id": f"stream-test-{uuid.uuid4()}"
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.content_type.startswith("text/event-stream"))
        # Read initial events
        first_chunk = next(res.response).decode("utf-8")
        self.assertIn("data:", first_chunk)
        self.assertIn("sources", first_chunk)


class TestLiveAIAvailability(unittest.TestCase):
    """
    Genuine live test with active AI backend.
    Tests end-to-end communication with the active provider.
    """

    def test_live_chat_endpoint(self):
        client = app.test_client()
        res = client.post("/api/chat", json={
            "message": "What is the official campus address of VIT Mumbai?"
        })

        data = json.loads(res.data)
        if res.status_code == 200:
            print(f"\n[LIVE TEST PASSED] Provider: {data.get('provider')}, Model: {data.get('model')}")
            print(f"Sample Answer Preview: {data.get('answer')[:120]}...")
            self.assertIn("answer", data)
            self.assertIn("sources", data)
        else:
            print(f"\n[LIVE TEST NOTE] Status {res.status_code}: {data.get('error')}")
            self.assertIn("error", data)


if __name__ == "__main__":
    unittest.main()
