"""
StudioAuth — autenticacao e autorizacao para o CRIS Studio.

Simples: usuario/senha com JWT, sessao em cookie ou header.
Permissoes: admin (tudo), editor (agentes), viewer (somente leitura).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("CRIS_STUDIO_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
SESSION_EXPIRY_S = 86400 * 7  # 7 days

# Default admin credentials (change in production via env vars)
DEFAULT_ADMIN_USER = os.environ.get("CRIS_ADMIN_USER", "admin")
DEFAULT_ADMIN_PASS = os.environ.get("CRIS_ADMIN_PASS", "cris2024")


def _hash_password(password: str, salt: str = "") -> str:
    """Hash de senha com salt."""
    if not salt:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return f"{salt}:{h.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    """Verifica senha contra hash armazenado."""
    parts = stored.split(":")
    if len(parts) != 2:
        return False
    salt, hash_hex = parts
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return hmac.compare_digest(h.hex(), hash_hex)


def _encode_jwt(payload: dict) -> str:
    """Encode JWT simples (sem biblioteca externa)."""
    import base64
    header = base64.urlsafe_b64encode(json.dumps({"alg": JWT_ALGORITHM, "typ": "JWT"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signing_input = f"{header}.{body}"
    sig = hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    return f"{header}.{body}.{signature}"


def _decode_jwt(token: str) -> dict | None:
    """Decode JWT. Retorna payload ou None se invalido."""
    import base64
    parts = token.split(".")
    if len(parts) != 3:
        return None
    header, body, signature = parts
    signing_input = f"{header}.{body}"
    expected_sig = hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest()
    expected_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")
    if not hmac.compare_digest(signature, expected_b64):
        return None
    # Decode body
    padding = 4 - len(body) % 4
    body_padded = body + "=" * padding
    try:
        payload = json.loads(base64.urlsafe_b64decode(body_padded))
    except Exception:
        return None
    # Check expiry
    if payload.get("exp", 0) < time.time():
        return None
    return payload


@dataclass
class User:
    username: str
    password_hash: str
    role: str = "editor"  # admin | editor | viewer
    display_name: str = ""
    created_at: float = field(default_factory=time.time)
    active: bool = True


@dataclass
class Session:
    token: str
    username: str
    role: str
    created_at: float
    expires_at: float


class StudioAuth:
    """Gerencia autenticacao e autorizacao do Studio."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._sessions: dict[str, Session] = {}
        self._init_default_user()

    def _init_default_user(self) -> None:
        """Cria usuario admin padrao se nao existir."""
        if DEFAULT_ADMIN_USER not in self._users:
            self._users[DEFAULT_ADMIN_USER] = User(
                username=DEFAULT_ADMIN_USER,
                password_hash=_hash_password(DEFAULT_ADMIN_PASS),
                role="admin",
                display_name="Administrador",
            )
            logger.info("Default admin user created: %s", DEFAULT_ADMIN_USER)

    def login(self, username: str, password: str) -> dict:
        """Autentica usuario e retorna token JWT."""
        user = self._users.get(username)
        if user is None or not user.active:
            return {"success": False, "error": "Usuario ou senha invalidos"}

        if not _verify_password(password, user.password_hash):
            return {"success": False, "error": "Usuario ou senha invalidos"}

        now = time.time()
        payload = {
            "sub": user.username,
            "role": user.role,
            "name": user.display_name,
            "iat": now,
            "exp": now + SESSION_EXPIRY_S,
        }
        token = _encode_jwt(payload)

        session = Session(
            token=token,
            username=user.username,
            role=user.role,
            created_at=now,
            expires_at=now + SESSION_EXPIRY_S,
        )
        self._sessions[token] = session

        return {
            "success": True,
            "token": token,
            "user": {
                "username": user.username,
                "role": user.role,
                "display_name": user.display_name,
            },
        }

    def verify(self, token: str) -> dict | None:
        """Verifica token JWT e retorna dados do usuario."""
        payload = _decode_jwt(token)
        if payload is None:
            return None
        return {
            "username": payload.get("sub"),
            "role": payload.get("role"),
            "display_name": payload.get("name"),
        }

    def logout(self, token: str) -> bool:
        """Remove sessao."""
        if token in self._sessions:
            del self._sessions[token]
            return True
        return False

    def create_user(self, username: str, password: str, role: str = "editor",
                    display_name: str = "") -> dict:
        """Cria um novo usuario."""
        if username in self._users:
            return {"success": False, "error": "Usuario ja existe"}
        if role not in ("admin", "editor", "viewer"):
            return {"success": False, "error": "Role invalida: use admin, editor ou viewer"}

        self._users[username] = User(
            username=username,
            password_hash=_hash_password(password),
            role=role,
            display_name=display_name or username,
        )
        return {"success": True, "username": username, "role": role}

    def change_password(self, username: str, new_password: str) -> bool:
        """Altera senha de um usuario."""
        user = self._users.get(username)
        if user is None:
            return False
        user.password_hash = _hash_password(new_password)
        return True

    def list_users(self) -> list[dict]:
        """Lista usuarios (sem senhas)."""
        return [
            {
                "username": u.username,
                "role": u.role,
                "display_name": u.display_name,
                "active": u.active,
                "created_at": u.created_at,
            }
            for u in self._users.values()
        ]

    def delete_user(self, username: str) -> bool:
        """Remove um usuario."""
        if username == DEFAULT_ADMIN_USER:
            return False  # Cannot delete default admin
        if username in self._users:
            del self._users[username]
            return True
        return False

    def check_permission(self, role: str, action: str) -> bool:
        """Verifica se uma role tem permissao para uma acao."""
        permissions = {
            "admin": ["read", "write", "delete", "execute", "publish", "manage_users", "manage_settings"],
            "editor": ["read", "write", "execute", "publish"],
            "viewer": ["read"],
        }
        return action in permissions.get(role, [])

    def extract_token(self, auth_header: str | None) -> str | None:
        """Extrai token do header Authorization: Bearer xxx."""
        if auth_header is None:
            return None
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        return None


# Singleton
_auth: StudioAuth | None = None


def get_auth() -> StudioAuth:
    global _auth
    if _auth is None:
        _auth = StudioAuth()
    return _auth
