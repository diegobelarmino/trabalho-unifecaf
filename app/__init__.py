import os

from flask import Flask, g, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix

from app.auth import auth_bp, garantir_admin, usuario_do_acesso
from app.db import init_db
from app.seguranca import aplicar_cabecalhos, garantir_segredos
from app.servicos import (
    ErroOperacao,
    adicionar_na_caixa,
    cadastrar_peca,
    inserir_demonstracao,
    listar_caixas,
    listar_pecas,
    relatorio,
    remover_peca,
    resumo,
)


def criar_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "..", "static"),
    )
    app.config["MAX_CONTENT_LENGTH"] = 256 * 1024
    app.config["JSON_AS_ASCII"] = False
    if os.getenv("TRUST_PROXY", "").lower() == "true":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    app.register_blueprint(auth_bp)

    @app.errorhandler(ErroOperacao)
    def erro_operacao(erro: ErroOperacao):
        return jsonify({"erro": erro.mensagem, "error": erro.mensagem, "code": erro.code}), erro.codigo

    @app.errorhandler(413)
    def corpo_grande(_erro):
        return jsonify({"erro": "Requisição muito grande.", "code": "PAYLOAD_TOO_LARGE"}), 413

    @app.before_request
    def proteger():
        if request.method == "OPTIONS":
            return None
        if "\x00" in request.path or ".." in request.path:
            raise ErroOperacao("Requisição recusada.", 400, "BAD_REQUEST")
        if not request.path.startswith("/api/") or request.path in {
            "/api/auth/login",
            "/api/auth/refresh",
            "/api/health",
        }:
            return None
        g.usuario = usuario_do_acesso()
        return None

    @app.after_request
    def cabecalhos(resposta):
        return aplicar_cabecalhos(resposta)

    @app.get("/")
    def inicio():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/resumo")
    def api_resumo():
        return jsonify(resumo())

    @app.get("/api/pecas")
    def api_pecas():
        status = request.args.get("status") or None
        busca = request.args.get("busca") or None
        return jsonify(listar_pecas(status, busca))

    @app.post("/api/pecas")
    def api_cadastrar():
        dados = request.get_json(silent=True) or {}
        resultado = cadastrar_peca(
            dados.get("id", ""),
            dados.get("peso"),
            dados.get("cor", ""),
            dados.get("comprimento"),
        )
        return jsonify(resultado), 201

    @app.delete("/api/pecas/<identificador>")
    def api_remover(identificador):
        return jsonify(remover_peca(identificador))

    @app.post("/api/caixas/<int:caixa_id>/pecas")
    def api_adicionar_na_caixa(caixa_id):
        dados = request.get_json(silent=True) or {}
        resultado = adicionar_na_caixa(
            caixa_id,
            dados.get("id", ""),
            dados.get("peso"),
            dados.get("cor", ""),
            dados.get("comprimento"),
        )
        return jsonify(resultado), 201

    @app.delete("/api/caixas/<int:caixa_id>/pecas/<identificador>")
    def api_tirar_da_caixa(caixa_id, identificador):
        return jsonify(remover_peca(identificador, caixa_id))

    @app.get("/api/caixas")
    def api_caixas():
        somente = request.args.get("status") == "fechada"
        return jsonify(listar_caixas(somente))

    @app.get("/api/relatorio")
    def api_relatorio():
        return jsonify(relatorio())

    @app.post("/api/demonstracao")
    def api_demonstracao():
        return jsonify(inserir_demonstracao())

    return app


def preparar():
    garantir_segredos()
    init_db()
    aplicacao = criar_app()
    garantir_admin()
    return aplicacao
