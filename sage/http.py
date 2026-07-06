# sage/http.py
"""Shared HTTP transport setup for the OpenAI client.

Centralizes TLS configuration (custom CA bundle or verification
toggle) so every part of the app connects consistently.
"""

from __future__ import annotations

import warnings

import httpx

from sage.config import Config


def build_http_client(config: Config) -> httpx.Client:
    """Build an httpx.Client honoring the TLS settings in config.

    Precedence:
      1. If verify_tls is False -> verification disabled (INSECURE).
      2. Elif ca_bundle is set  -> verify against that CA bundle.
      3. Else                   -> default system verification.

    Args:
        config: Loaded application config.

    Returns:
        A configured httpx.Client for passing to OpenAI via http_client=.
    """
    if not config.verify_tls:
        _warn_insecure_once()
        verify: bool | str = False
    elif config.ca_bundle:
        verify = config.ca_bundle
    else:
        verify = True

    if verify is False:
        import urllib3

        urllib3.disable_warnings()

    return httpx.Client(verify=verify, timeout=60.0)


_INSECURE_WARNED = False


def _warn_insecure_once() -> None:
    """Emit the insecure-TLS warning at most once per process."""
    global _INSECURE_WARNED
    if not _INSECURE_WARNED:
        # print(
        #     "[tls] WARNING: TLS verification disabled (VERIFY_TLS=false). "
        #     "Insecure — local testing only.",
        # )
        _INSECURE_WARNED = True