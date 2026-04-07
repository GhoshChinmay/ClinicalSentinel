"""
DataSentinel — API Key Authentication
Opt-in API key gate.  When the DS_API_KEY environment variable is set,
every protected endpoint requires a matching `X-API-Key` request header.
When the variable is *not* set (default for local dev), authentication is
completely bypassed so there is zero friction for personal use.
"""

import os
from fastapi import Header, HTTPException, status

# ---------------------------------------------------------------------------
# Read the key once at import time.  An empty / missing value means "auth off".
# ---------------------------------------------------------------------------
_API_KEY: str | None = os.getenv("DS_API_KEY") or None


def is_auth_enabled() -> bool:
    """Return True when API-key protection is active."""
    return _API_KEY is not None


async def require_api_key(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> None:
    """FastAPI dependency — validates the X-API-Key header.

    • If DS_API_KEY is not configured → always passes (dev mode).
    • If DS_API_KEY is configured and the header is missing/wrong → 401.
    """
    if not is_auth_enabled():
        return  # Auth disabled — allow everything

    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide it via the X-API-Key header.",
        )

    # Constant-time comparison to avoid timing attacks
    import hmac
    if not hmac.compare_digest(x_api_key, _API_KEY):  # type: ignore[arg-type]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )
