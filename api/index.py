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

# Expose the Flask WSGI app instance for Vercel
from app import app
