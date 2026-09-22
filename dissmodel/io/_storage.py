from __future__ import annotations

import os

# MinIO client is an optional dependency, for s3:// URI support.
# Install with: pip install dissmodel[s3]

_default_client = None


def get_default_client():
    """
    Return the default MinIO client configured from environment variables.
    Raises ImportError if minio is not installed.
    """
    global _default_client

    if _default_client is not None:
        return _default_client

    try:
        from minio import Minio
    except ImportError:
        raise ImportError(
            "s3:// URIs require the 'minio' package.\n"
            "Install with: pip install dissmodel[s3]"
        )

    _default_client = Minio(
        os.getenv("MINIO_ENDPOINT",   "minio:9000"),
        access_key = os.getenv("MINIO_ACCESS_KEY", ""),
        secret_key = os.getenv("MINIO_SECRET_KEY", ""),
        secure     = bool(os.getenv("MINIO_SECURE", "")),
    )
    return _default_client


def set_default_client(client) -> None:
    """Override the default client — useful for testing."""
    global _default_client
    _default_client = client
