"""Authentication endpoints — WebAuthn passkey registration and login."""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from trader_api.auth import (
    has_any_credential,
    invalidate_credential_cache,
    issue_token,
)
from trader_api.database import get_db
from trader_api.models import WebAuthnCredential

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Config from env
RP_NAME = os.environ.get("WEBAUTHN_RP_NAME", "signalhouse")


def _resolve_rp_id() -> str:
    """Resolve WebAuthn RP ID from shared DOMAIN env."""
    return os.environ.get("DOMAIN") or "localhost"


def _resolve_expected_origins(rp_id: str) -> list[str]:
    """Build allowed WebAuthn origins from env and safe defaults."""
    configured = os.environ.get("WEBAUTHN_EXPECTED_ORIGINS", "")
    origins = {
        origin.strip()
        for origin in configured.split(",")
        if origin.strip()
    }

    origins.add(f"https://{rp_id}")

    # Localhost origins for local development and local self-hosting.
    origins.update(
        {
            "http://localhost:3000",
            "http://localhost:8000",
        }
    )

    return sorted(origins)

# Single-user challenge store — one active challenge per flow type
# (registration or authentication). Simple and correct for single-instance apps.
_registration_state: dict[str, Any] | None = None
_authentication_state: dict[str, Any] | None = None

# Fixed user for single-user system
_USER_ID = b"trader-owner"
_USER_NAME = "owner"
_USER_DISPLAY_NAME = "signalhouse owner"


@router.get("/status")
async def auth_status(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Check if any passkey is registered (always accessible, no auth)."""
    registered = await has_any_credential(db)

    # Count credentials
    result = await db.execute(select(WebAuthnCredential))
    credentials = result.scalars().all()

    return {
        "registered": registered,
        "credentials": [
            {
                "id": c.id,
                "name": c.name,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in credentials
        ],
    }


@router.post("/register/options")
async def register_options(db: AsyncSession = Depends(get_db)) -> dict:
    """Generate WebAuthn registration options (challenge)."""
    rp_id = _resolve_rp_id()

    # Get existing credential IDs to exclude
    result = await db.execute(select(WebAuthnCredential.credential_id))
    existing_ids = result.scalars().all()

    exclude_credentials = [
        PublicKeyCredentialDescriptor(id=cid) for cid in existing_ids
    ]

    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=RP_NAME,
        user_id=_USER_ID,
        user_name=_USER_NAME,
        user_display_name=_USER_DISPLAY_NAME,
        exclude_credentials=exclude_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.ECDSA_SHA_256,
            COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
        ],
    )

    global _registration_state
    _registration_state = {
        "challenge": options.challenge,
        "rp_id": rp_id,
        "expected_origins": _resolve_expected_origins(rp_id),
    }

    return json.loads(options_to_json(options))


@router.post("/register/verify")
async def register_verify(
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Verify WebAuthn registration response and store credential."""
    global _registration_state
    if _registration_state is None:
        raise HTTPException(status_code=400, detail="No pending registration challenge")

    state = _registration_state
    _registration_state = None  # consume it

    try:
        verification = verify_registration_response(
            credential=body,
            expected_challenge=state["challenge"],
            expected_rp_id=state["rp_id"],
            expected_origin=state["expected_origins"],
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Registration failed: {e}")

    # Store credential
    transports = json.dumps(body.get("response", {}).get("transports", []))
    name = body.get("name", "Passkey")

    credential = WebAuthnCredential(
        credential_id=verification.credential_id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        transports=transports,
        name=name,
    )
    db.add(credential)
    await db.commit()

    invalidate_credential_cache()

    # Issue a token immediately so the user doesn't get locked out
    token = issue_token()

    return {"status": "ok", "token": token}


@router.post("/login/options")
async def login_options(db: AsyncSession = Depends(get_db)) -> dict:
    """Generate WebAuthn authentication options."""
    rp_id = _resolve_rp_id()

    registered = await has_any_credential(db)
    if not registered:
        raise HTTPException(status_code=400, detail="No passkey registered")

    result = await db.execute(
        select(WebAuthnCredential.credential_id, WebAuthnCredential.transports)
    )
    creds = result.all()

    allow_credentials = []
    for cred_id, transports_json in creds:
        transports = []
        if transports_json:
            try:
                for t in json.loads(transports_json):
                    try:
                        transports.append(AuthenticatorTransport(t))
                    except ValueError:
                        pass
            except (json.JSONDecodeError, TypeError):
                pass
        desc = PublicKeyCredentialDescriptor(id=cred_id, transports=transports)
        allow_credentials.append(desc)

    options = generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    global _authentication_state
    _authentication_state = {
        "challenge": options.challenge,
        "rp_id": rp_id,
        "expected_origins": _resolve_expected_origins(rp_id),
    }

    return json.loads(options_to_json(options))


@router.post("/login/verify")
async def login_verify(
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Verify WebAuthn authentication response and issue JWT."""
    global _authentication_state
    if _authentication_state is None:
        raise HTTPException(status_code=400, detail="No pending authentication challenge")

    state = _authentication_state
    _authentication_state = None  # consume it

    # Look up credential
    raw_id = body.get("rawId", "")
    from webauthn.helpers import base64url_to_bytes

    try:
        credential_id_bytes = base64url_to_bytes(raw_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid credential ID")

    result = await db.execute(
        select(WebAuthnCredential).where(
            WebAuthnCredential.credential_id == credential_id_bytes
        )
    )
    stored = result.scalar_one_or_none()
    if not stored:
        raise HTTPException(status_code=400, detail="Unknown credential")

    try:
        verification = verify_authentication_response(
            credential=body,
            expected_challenge=state["challenge"],
            expected_rp_id=state["rp_id"],
            expected_origin=state["expected_origins"],
            credential_public_key=stored.public_key,
            credential_current_sign_count=stored.sign_count,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication failed: {e}")

    # Update sign count
    stored.sign_count = verification.new_sign_count
    await db.commit()

    token = issue_token()
    return {"status": "ok", "token": token}


@router.delete("/credentials/{credential_id}")
async def delete_credential(
    credential_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a registered passkey."""
    result = await db.execute(
        delete(WebAuthnCredential).where(WebAuthnCredential.id == credential_id)
    )
    if result.rowcount == 0:  # type: ignore[union-attr]
        raise HTTPException(status_code=404, detail="Credential not found")
    await db.commit()
    invalidate_credential_cache()
    return {"status": "deleted", "id": credential_id}
