"""
Vercel Serverless Function entry point for VIT Mumbai College Enquiry Chatbot.
Routes all web requests and API endpoints to the Flask WSGI application.
"""
import os
import sys

# Ensure project root is present in module search path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import app


class VercelPathMiddleware:
    """Restores the original request path from Vercel headers if rewritten."""

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        # Vercel provides the client's requested URL path in HTTP_X_MATCHED_PATH, HTTP_X_FORWARDED_URI, or RAW_URI
        orig = (
            environ.get("HTTP_X_MATCHED_PATH")
            or environ.get("HTTP_X_FORWARDED_URI")
            or environ.get("RAW_URI")
            or environ.get("REQUEST_URI")
        )
        if orig and orig != "/api/index.py" and not orig.startswith("/api/index.py"):
            path = orig.split("?", 1)[0]
            environ["PATH_INFO"] = path
        return self.wsgi_app(environ, start_response)


app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
