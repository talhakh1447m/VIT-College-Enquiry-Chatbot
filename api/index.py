"""
Vercel Serverless Function entry point for VIT Mumbai College Enquiry Chatbot.
Routes all web requests and API endpoints to the Flask WSGI application.
"""
import os
import sys
import urllib.parse

# Ensure project root is present in module search path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app import app


class VercelPathMiddleware:
    """Restores the original client request path when rewritten by Vercel."""

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        qs = environ.get("QUERY_STRING", "")
        params = urllib.parse.parse_qs(qs, keep_blank_values=True)
        if "__vercel_path" in params and params["__vercel_path"]:
            path = params["__vercel_path"][0]
            if not path.startswith("/"):
                path = "/" + path
            environ["PATH_INFO"] = path

            # Clean __vercel_path out of query string
            filtered_params = {k: v for k, v in params.items() if k != "__vercel_path"}
            environ["QUERY_STRING"] = urllib.parse.urlencode(filtered_params, doseq=True)
        elif environ.get("PATH_INFO") == "/api/index.py":
            # Fallback if accessed directly
            environ["PATH_INFO"] = "/"

        return self.wsgi_app(environ, start_response)


app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
