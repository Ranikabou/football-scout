"""Vercel serverless entrypoint — exports the FastAPI app object."""
from football_scout.api.app import app  # noqa: F401 — Vercel picks up 'app'
