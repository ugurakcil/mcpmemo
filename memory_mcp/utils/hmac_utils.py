from __future__ import annotations

import hmac
import hashlib
import json
from typing import Any


def sign_payload(secret: str, payload: dict[str, Any]) -> str:
    message = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_signature(secret: str, payload: dict[str, Any], signature: str) -> bool:
    expected = sign_payload(secret, payload)
    return hmac.compare_digest(expected, signature)
