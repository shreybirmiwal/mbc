import sys
import os

# Add parent directory to path so we can import server
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import app

# Export the Flask app for Vercel
# Vercel's Python runtime automatically handles WSGI applications
# The app variable is what Vercel will use
