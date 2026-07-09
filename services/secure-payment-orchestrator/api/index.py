"""Vercel serverless entrypoint — exposes the FastAPI app from main.py."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import app  # noqa: E402,F401
