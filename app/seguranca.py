"""Autenticação JWT no mesmo desenho do Actus: access curto, refresh em cookie, bcrypt."""

import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from flask import request

from app.servicos import ErroOperacao

EMISSOR = "vertice-platform"
AUDIENCIA = "vertice-users"
ALGORITMO = "HS256"
ACCESS_SEGUNDOS = 15 * 60
REFRESH_DIAS = 7
JANELA_LOGIN = 15 * 60
MAX_LOGIN = 30
MAX_FALHAS = 5
_DUMMY = bcrypt.hashpw(b"vertice-timing-shield", bcrypt.gensalt(rounds=12))
_tentativas: dict[str, list[float]] = {}


def producao() -> bool:
    return os.getenv("FLASK_ENV", "development") == "production"


def cookie_seguro() -> bool:
    valor = os.getenv("COOKIE_SECURE", "")
    if valor:
        return valor.lower() == "true"
    return producao()


def _gravar_env(chave: str, valor: str) -> None:
    caminho = os.path.join(os.path.dirname(__file__), "..", ".env")
    caminho = os.path.abspath(caminho)
    linhas = []
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as arquivo:
            linhas = arquivo.read().splitlines()
    prefixo = f"{chave}="
    novas = [linha for linha in linhas if not linha.startswith(prefixo)]
    novas.append(prefixo + valor)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write("\n".join(novas) + "\n")
    os.environ[chave] = valor


def garantir_segredos() -> None:
    for chave in ("JWT_ACCESS_SECRET", "JWT_REFRESH_SECRET"):
        if not os.getenv(chave):
            _gravar_env(chave, secrets.token_urlsafe(48))
    if os.getenv("JWT_ACCESS_SECRET") == os.getenv("JWT_REFRESH_SECRET"):
        _gravar_env("JWT_REFRESH_SECRET", secrets.token_urlsafe(48))


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt(rounds=12)).decode()


def conferir_senha(senha: str, senha_hash: str | None) -> bool:
    material = (senha_hash or "").encode()
    if not material.startswith(b"$2"):
        material = _DUMMY
    return bcrypt.checkpw(senha.encode(), material)


def validar_senha_forte(senha: str) -> None:
    if len(senha) < 8 or not any(c.isupper() for c in senha) or not any(c.islower() for c in senha) or not any(c.isdigit() for c in senha):
        raise ErroOperacao(
            "A senha deve ter pelo menos 8 caracteres, com maiúscula, minúscula e número.",
            code="SENHA_FRACA",
        )


def email_valido(email: str) -> bool:
    if not email or len(email) > 120 or "@" not in email:
        return False
    local, _, dominio = email.partition("@")
    return bool(local and "." in dominio and " " not in email)


def ip_cliente() -> str:
    if os.getenv("TRUST_PROXY", "").lower() == "true":
        encaminhado = request.headers.get("X-Forwarded-For", "")
        if encaminhado:
            return encaminhado.split(",")[0].strip()[:64]
    return (request.remote_addr or "")[:64]


def _hash_curto(valor: str) -> str:
    return hashlib.sha256((valor or "").encode()).hexdigest()[:16]


def limitar_login(email: str) -> None:
    agora = time.time()
    chave = email.lower()
    recentes = [t for t in _tentativas.get(chave, []) if agora - t < JANELA_LOGIN]
    if len(recentes) >= MAX_LOGIN:
        raise ErroOperacao(
            "Muitas tentativas de login. Tente novamente em alguns minutos.",
            429,
            "RATE_LIMIT_EXCEEDED",
        )
    recentes.append(agora)
    _tentativas[chave] = recentes


def emitir_tokens(usuario_id: int) -> tuple[str, str]:
    agora = datetime.now(timezone.utc)
    acesso = jwt.encode(
        {
            "userId": usuario_id,
            "type": "access",
            "iss": EMISSOR,
            "aud": AUDIENCIA,
            "iat": int(agora.timestamp()),
            "exp": int((agora + timedelta(seconds=ACCESS_SEGUNDOS)).timestamp()),
        },
        os.environ["JWT_ACCESS_SECRET"],
        algorithm=ALGORITMO,
    )
    jti = secrets.token_hex(16)
    refresh = jwt.encode(
        {
            "userId": usuario_id,
            "type": "refresh",
            "jti": jti,
            "iss": EMISSOR,
            "aud": AUDIENCIA,
            "iat": int(agora.timestamp()),
            "exp": int((agora + timedelta(days=REFRESH_DIAS)).timestamp()),
            "userAgent": _hash_curto(request.headers.get("User-Agent", "")),
            "ipHash": _hash_curto(ip_cliente()),
        },
        os.environ["JWT_REFRESH_SECRET"],
        algorithm=ALGORITMO,
    )
    return acesso, refresh


def ler_token(token: str, segredo: str, tipo: str) -> dict:
    try:
        dados = jwt.decode(
            token,
            segredo,
            algorithms=[ALGORITMO],
            issuer=EMISSOR,
            audience=AUDIENCIA,
        )
    except jwt.ExpiredSignatureError:
        raise ErroOperacao("Token expirado", 401, "TOKEN_EXPIRED")
    except jwt.InvalidTokenError:
        raise ErroOperacao("Token inválido", 401, "TOKEN_INVALID")
    if dados.get("type") != tipo:
        raise ErroOperacao("Token inválido", 403, "INVALID_TOKEN_TYPE")
    return dados


def sessao_suspeita(dados: dict) -> bool:
    agente = _hash_curto(request.headers.get("User-Agent", ""))
    ip = _hash_curto(ip_cliente())
    return dados.get("userAgent") != agente or dados.get("ipHash") != ip


def aplicar_cabecalhos(resposta):
    resposta.headers["Server"] = "Trabalho Unifecaf"
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resposta.headers["X-Frame-Options"] = "DENY"
    resposta.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    resposta.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    if producao():
        resposta.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resposta


def opcoes_cookie() -> dict:
    return {
        "httponly": True,
        "secure": cookie_seguro(),
        "samesite": "Strict",
        "max_age": REFRESH_DIAS * 24 * 60 * 60,
        "path": "/api/auth",
    }
