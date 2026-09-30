"""Login, renovação e encerramento de sessão."""

import os
import re
from datetime import datetime

import pymysql
from flask import Blueprint, g, jsonify, request

from app.db import conexao
from app.seguranca import (
    ACCESS_SEGUNDOS,
    conferir_senha,
    cookie_seguro,
    emitir_tokens,
    email_valido,
    hash_senha,
    ip_cliente,
    ler_token,
    limitar_login,
    opcoes_cookie,
    sessao_suspeita,
    validar_senha_forte,
)
from app.servicos import ErroOperacao

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def registrar_evento(tipo: str, email: str | None, detalhe: str = "") -> None:
    with conexao() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO eventos_seguranca (tipo, email, ip, detalhe)
                VALUES (%s, %s, %s, %s)
                """,
                (tipo, (email or "")[:120], ip_cliente(), detalhe[:255]),
            )


def garantir_admin() -> None:
    with conexao() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM usuarios LIMIT 1")
            if cur.fetchone():
                return
            email = (os.getenv("ADMIN_EMAIL") or "admin@vertice.local").strip().lower()
            senha = os.getenv("ADMIN_PASSWORD") or ""
            gerada = False
            if not senha:
                import secrets
                senha = secrets.token_urlsafe(12)
                gerada = True
                from app.seguranca import _gravar_env
                _gravar_env("ADMIN_PASSWORD", senha)
            nome = os.getenv("ADMIN_NOME") or "Administrador"
            try:
                cur.execute(
                    """
                    INSERT INTO usuarios (nome, email, senha_hash, ativo)
                    VALUES (%s, %s, %s, 1)
                    """,
                    (nome[:80], email, hash_senha(senha)),
                )
            except pymysql.err.IntegrityError:
                return
    if gerada:
        print(f"Administrador criado: {email}")
        print("A senha inicial foi gravada em ADMIN_PASSWORD no arquivo .env. Troque no primeiro acesso.")


def _usuario_por_email(cur, email: str):
    cur.execute(
        """
        SELECT id, nome, email, senha_hash, ativo, refresh_token, falhas_login, bloqueado_ate
        FROM usuarios WHERE email = %s
        """,
        (email,),
    )
    return cur.fetchone()


def _publico(usuario: dict) -> dict:
    return {"id": usuario["id"], "nome": usuario["nome"], "email": usuario["email"]}


def _definir_refresh(resposta, token: str):
    resposta.set_cookie("refreshToken", token, **opcoes_cookie())
    return resposta


def _limpar_refresh(resposta):
    resposta.delete_cookie(
        "refreshToken",
        path="/api/auth",
        httponly=True,
        secure=cookie_seguro(),
        samesite="Strict",
    )
    return resposta


@auth_bp.post("/login")
def login():
    dados = request.get_json(silent=True) or {}
    email = str(dados.get("email") or "").strip().lower()
    senha = str(dados.get("senha") or "")
    if not email or not senha:
        raise ErroOperacao("E-mail e senha são obrigatórios.", code="MISSING_CREDENTIALS")
    if not email_valido(email) or not EMAIL_RE.match(email):
        raise ErroOperacao("Formato de e-mail inválido.", code="INVALID_EMAIL_FORMAT")
    limitar_login(email)

    acesso = refresh = None
    publico = None
    falha = None
    with conexao() as conn:
        with conn.cursor() as cur:
            usuario = _usuario_por_email(cur, email)
            senha_ok = conferir_senha(senha, usuario["senha_hash"] if usuario else None)
            bloqueado = usuario and usuario["bloqueado_ate"] and usuario["bloqueado_ate"] > datetime.now()
            if bloqueado:
                falha = ErroOperacao("Muitas tentativas. Tente novamente mais tarde.", 429, "ACCOUNT_LOCKED")
            elif not usuario or not senha_ok:
                if usuario:
                    falhas = int(usuario["falhas_login"]) + 1
                    if falhas >= 5:
                        cur.execute(
                            """
                            UPDATE usuarios
                            SET falhas_login = %s, bloqueado_ate = DATE_ADD(NOW(), INTERVAL 15 MINUTE)
                            WHERE id = %s
                            """,
                            (falhas, usuario["id"]),
                        )
                    else:
                        cur.execute(
                            "UPDATE usuarios SET falhas_login = %s, bloqueado_ate = NULL WHERE id = %s",
                            (falhas, usuario["id"]),
                        )
                falha = ErroOperacao("Credenciais inválidas.", 401, "INVALID_CREDENTIALS")
            elif not usuario["ativo"]:
                falha = ErroOperacao(
                    "Usuário desativado. Entre em contato com o administrador.",
                    403,
                    "USER_DISABLED",
                )
            else:
                acesso, refresh = emitir_tokens(usuario["id"])
                cur.execute(
                    """
                    UPDATE usuarios
                    SET refresh_token = %s, ultimo_login = NOW(), falhas_login = 0, bloqueado_ate = NULL
                    WHERE id = %s
                    """,
                    (refresh, usuario["id"]),
                )
                publico = _publico(usuario)
    if falha:
        codigo = "login_bloqueado" if falha.code == "ACCOUNT_LOCKED" else "login_invalido"
        if falha.code == "USER_DISABLED":
            codigo = "login_inativo"
        registrar_evento(codigo, email, falha.code)
        raise falha
    registrar_evento("login_ok", email, "sessão iniciada")
    resposta = jsonify({
        "message": "Login realizado com sucesso",
        "erro": None,
        "accessToken": acesso,
        "expiresIn": ACCESS_SEGUNDOS,
        "user": publico,
    })
    return _definir_refresh(resposta, refresh)


@auth_bp.post("/refresh")
def refresh():
    token = request.cookies.get("refreshToken")
    if not token:
        raise ErroOperacao("Refresh token não encontrado.", 401, "REFRESH_TOKEN_MISSING")
    dados = ler_token(token, os.environ["JWT_REFRESH_SECRET"], "refresh")
    if sessao_suspeita(dados):
        with conexao() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE usuarios SET refresh_token = NULL WHERE id = %s", (dados["userId"],))
        registrar_evento("sessao_suspeita", None, f"usuario {dados['userId']}")
        resposta = jsonify({"erro": "Sessão suspeita detectada. Faça login novamente.", "code": "SUSPICIOUS_SESSION"})
        resposta.status_code = 403
        return _limpar_refresh(resposta)

    with conexao() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, nome, email, ativo, refresh_token
                FROM usuarios WHERE id = %s AND refresh_token = %s
                """,
                (dados["userId"], token),
            )
            usuario = cur.fetchone()
            if not usuario or not usuario["ativo"]:
                raise ErroOperacao("Refresh token inválido ou usuário desativado.", 403, "REFRESH_TOKEN_INVALID")
            acesso, novo = emitir_tokens(usuario["id"])
            cur.execute("UPDATE usuarios SET refresh_token = %s WHERE id = %s", (novo, usuario["id"]))
    resposta = jsonify({"accessToken": acesso, "expiresIn": ACCESS_SEGUNDOS, "user": _publico(usuario)})
    return _definir_refresh(resposta, novo)


@auth_bp.post("/logout")
def logout():
    usuario = g.usuario
    with conexao() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE usuarios SET refresh_token = NULL WHERE id = %s", (usuario["id"],))
    registrar_evento("logout", usuario["email"], "sessão encerrada")
    resposta = jsonify({"message": "Logout realizado com sucesso"})
    return _limpar_refresh(resposta)


@auth_bp.get("/me")
def me():
    return jsonify({"user": _publico(g.usuario)})


@auth_bp.post("/senha")
def alterar_senha():
    dados = request.get_json(silent=True) or {}
    atual = str(dados.get("senha_atual") or "")
    nova = str(dados.get("senha_nova") or "")
    validar_senha_forte(nova)
    usuario = g.usuario
    if not conferir_senha(atual, usuario["senha_hash"]):
        raise ErroOperacao("Senha atual incorreta.", 401, "INVALID_CREDENTIALS")
    with conexao() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE usuarios SET senha_hash = %s, refresh_token = NULL WHERE id = %s",
                (hash_senha(nova), usuario["id"]),
            )
    registrar_evento("senha_alterada", usuario["email"], "senha atualizada")
    resposta = jsonify({"message": "Senha alterada. Entre novamente."})
    return _limpar_refresh(resposta)


def usuario_do_acesso():
    cabecalho = request.headers.get("Authorization", "")
    token = cabecalho[7:] if cabecalho.startswith("Bearer ") else ""
    if not token:
        raise ErroOperacao("Token de acesso requerido.", 401, "TOKEN_MISSING")
    dados = ler_token(token, os.environ["JWT_ACCESS_SECRET"], "access")
    with conexao() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, nome, email, senha_hash, ativo
                FROM usuarios WHERE id = %s
                """,
                (dados["userId"],),
            )
            usuario = cur.fetchone()
    if not usuario or not usuario["ativo"]:
        raise ErroOperacao("Usuário desativado.", 403, "USER_DISABLED")
    return usuario
