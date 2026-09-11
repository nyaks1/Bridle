"""Bridle Gateway entrypoint.

Aliases to server/server.py for compatibility with both:
- uvicorn main:app
- uvicorn server:app
"""

from server.server import app, PRICING, SERVICE_TYPES, verify_onchain_tx, log_to_hcs

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
