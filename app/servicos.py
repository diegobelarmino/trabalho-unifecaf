"""Cadastro, inspeção, caixas e relatório.

A repetição aparece ao percorrer peças e caixas.
A decisão aparece nas condições de aprovação e no fechamento da caixa.
"""

import json
from decimal import Decimal

from app.db import conexao
from app.qualidade import CAPACIDADE_CAIXA, avaliar_peca

ROTULOS = {
    "peso": "Peso fora da faixa (95 g a 105 g)",
    "cor": "Cor diferente de azul ou verde",
    "comprimento": "Comprimento fora da faixa (10 cm a 20 cm)",
}


class ErroOperacao(Exception):
    def __init__(self, mensagem: str, codigo: int = 400, code: str = "ERRO"):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo = codigo
        self.code = code


def _numero(valor):
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


def _limpar(registro: dict | None) -> dict | None:
    if registro is None:
        return None
    limpo = {}
    for chave, valor in registro.items():
        if chave == "motivos" and isinstance(valor, str):
            limpo[chave] = json.loads(valor) if valor else []
        elif hasattr(valor, "isoformat"):
            limpo[chave] = valor.strftime("%d/%m/%Y %H:%M")
        else:
            limpo[chave] = _numero(valor)
    return limpo


def _caixa_aberta(cur):
    cur.execute(
        """
        SELECT id, numero, status, capacidade, criada_em, fechada_em
        FROM caixas
        WHERE status = 'aberta'
        ORDER BY numero DESC
        LIMIT 1
        FOR UPDATE
        """
    )
    return cur.fetchone()


def _ocupacao(cur, caixa_id: int) -> int:
    cur.execute("SELECT COUNT(*) AS total FROM pecas WHERE caixa_id = %s", (caixa_id,))
    return int(cur.fetchone()["total"])


def _abrir_caixa(cur) -> dict:
    cur.execute("SELECT COALESCE(MAX(numero), 0) + 1 AS proximo FROM caixas FOR UPDATE")
    numero = int(cur.fetchone()["proximo"])
    cur.execute(
        """
        INSERT INTO caixas (numero, status, capacidade)
        VALUES (%s, 'aberta', %s)
        """,
        (numero, CAPACIDADE_CAIXA),
    )
    cur.execute("SELECT * FROM caixas WHERE id = %s", (cur.lastrowid,))
    return cur.fetchone()


def _dados_peca(identificador: str, peso, cor: str, comprimento):
    identificador = (identificador or "").strip().upper()
    if not identificador or len(identificador) > 40:
        raise ErroOperacao("Informe um identificador de até 40 caracteres.")
    if any(c.isspace() for c in identificador):
        raise ErroOperacao("O identificador não pode conter espaços.")

    try:
        peso = round(float(peso), 2)
        comprimento = round(float(comprimento), 2)
    except (TypeError, ValueError):
        raise ErroOperacao("Peso e comprimento precisam ser números.")

    if peso <= 0 or comprimento <= 0:
        raise ErroOperacao("Peso e comprimento precisam ser maiores que zero.")

    cor = (cor or "").strip().lower()
    if not cor:
        raise ErroOperacao("Informe a cor da peça.")

    aprovada, motivos = avaliar_peca(peso, cor, comprimento)
    return identificador, peso, cor, comprimento, aprovada, motivos


def cadastrar_peca(identificador: str, peso: float, cor: str, comprimento: float) -> dict:
    identificador, peso, cor, comprimento, aprovada, motivos = _dados_peca(
        identificador, peso, cor, comprimento
    )
    status = "aprovada" if aprovada else "reprovada"

    with conexao() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM pecas WHERE id = %s", (identificador,))
            if cur.fetchone():
                raise ErroOperacao(f"Já existe uma peça com o identificador {identificador}.")

            caixa = None
            fechou = False
            if aprovada:
                caixa = _caixa_aberta(cur) or _abrir_caixa(cur)

            cur.execute(
                """
                INSERT INTO pecas (id, peso, cor, comprimento, status, motivos, caixa_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    identificador,
                    peso,
                    cor,
                    comprimento,
                    status,
                    json.dumps(motivos, ensure_ascii=False) if motivos else None,
                    caixa["id"] if caixa else None,
                ),
            )

            ocupacao = None
            if caixa:
                ocupacao = _ocupacao(cur, caixa["id"])
                if ocupacao >= int(caixa["capacidade"]):
                    cur.execute(
                        """
                        UPDATE caixas
                        SET status = 'fechada', fechada_em = NOW()
                        WHERE id = %s
                        """,
                        (caixa["id"],),
                    )
                    fechou = True

    if aprovada and fechou:
        mensagem = (
            f"Peça {identificador} aprovada. A caixa {caixa['numero']} atingiu "
            f"{CAPACIDADE_CAIXA} peças e foi fechada."
        )
    elif aprovada:
        mensagem = (
            f"Peça {identificador} aprovada e armazenada na caixa {caixa['numero']} "
            f"({ocupacao}/{CAPACIDADE_CAIXA})."
        )
    else:
        mensagem = f"Peça {identificador} reprovada. Veja os motivos da inspeção."

    return {
        "mensagem": mensagem,
        "peca": obter_peca(identificador),
        "caixa_fechada": fechou,
    }


def obter_peca(identificador: str) -> dict:
    with conexao() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.*, c.numero AS caixa_numero, c.status AS caixa_status
                FROM pecas p
                LEFT JOIN caixas c ON c.id = p.caixa_id
                WHERE p.id = %s
                """,
                (identificador,),
            )
            peca = _limpar(cur.fetchone())
    if not peca:
        raise ErroOperacao("Peça não encontrada.", 404)
    return peca


def listar_pecas(status: str | None = None, busca: str | None = None) -> list[dict]:
    sql = """
        SELECT p.*, c.numero AS caixa_numero, c.status AS caixa_status
        FROM pecas p
        LEFT JOIN caixas c ON c.id = p.caixa_id
        WHERE 1 = 1
    """
    params: list = []
    if status in ("aprovada", "reprovada"):
        sql += " AND p.status = %s"
        params.append(status)
    if busca:
        sql += " AND (p.id LIKE %s OR p.cor LIKE %s)"
        termo = f"%{busca.strip()}%"
        params.extend([termo, termo])
    sql += " ORDER BY p.criada_em DESC, p.id DESC"

    with conexao() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [_limpar(linha) for linha in cur.fetchall()]


def adicionar_na_caixa(caixa_id: int, identificador: str, peso, cor: str, comprimento) -> dict:
    """Inclui uma peça aprovada numa caixa escolhida, se ainda houver vaga."""
    identificador, peso, cor, comprimento, aprovada, motivos = _dados_peca(
        identificador, peso, cor, comprimento
    )
    if not aprovada:
        texto = " ".join(item["descricao"] for item in motivos)
        raise ErroOperacao(f"Peça reprovada e não entrou na caixa. {texto}")

    with conexao() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM caixas WHERE id = %s FOR UPDATE", (caixa_id,))
            caixa = cur.fetchone()
            if not caixa:
                raise ErroOperacao("Caixa não encontrada.", 404)
            cur.execute("SELECT id FROM pecas WHERE id = %s", (identificador,))
            if cur.fetchone():
                raise ErroOperacao(f"Já existe uma peça com o identificador {identificador}.")

            ocupacao = _ocupacao(cur, caixa["id"])
            capacidade = int(caixa["capacidade"])
            if ocupacao >= capacidade:
                raise ErroOperacao(
                    f"A caixa {caixa['numero']} está cheia ({capacidade}/{capacidade}). "
                    "Tire uma peça para liberar espaço."
                )

            cur.execute(
                """
                INSERT INTO pecas (id, peso, cor, comprimento, status, motivos, caixa_id)
                VALUES (%s, %s, %s, %s, 'aprovada', NULL, %s)
                """,
                (identificador, peso, cor, comprimento, caixa["id"]),
            )
            ocupacao += 1
            fechou = ocupacao >= capacidade
            if fechou:
                cur.execute(
                    """
                    UPDATE caixas
                    SET status = 'fechada', fechada_em = NOW()
                    WHERE id = %s
                    """,
                    (caixa["id"],),
                )

    if fechou:
        mensagem = (
            f"Peça {identificador} incluída na caixa {caixa['numero']}. "
            f"A caixa atingiu {capacidade} peças e foi fechada."
        )
    else:
        mensagem = (
            f"Peça {identificador} incluída na caixa {caixa['numero']} "
            f"({ocupacao}/{capacidade})."
        )
    return {"mensagem": mensagem, "peca": obter_peca(identificador), "caixa_fechada": fechou}


def remover_peca(identificador: str, caixa_id: int | None = None) -> dict:
    """Remove somente a peça escolhida pelo operador. Caixas vazias permanecem no histórico."""
    identificador = (identificador or "").strip().upper()
    with conexao() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.*, c.numero AS caixa_numero, c.status AS caixa_status, c.capacidade
                FROM pecas p
                LEFT JOIN caixas c ON c.id = p.caixa_id
                WHERE p.id = %s
                FOR UPDATE
                """,
                (identificador,),
            )
            peca = cur.fetchone()
            if not peca:
                raise ErroOperacao("Peça não encontrada.", 404)
            if caixa_id is not None and peca["caixa_id"] != int(caixa_id):
                raise ErroOperacao("Essa peça não está nesta caixa.")

            cur.execute("DELETE FROM pecas WHERE id = %s", (identificador,))
            if caixa_id is not None and peca["caixa_numero"]:
                aviso = f"Peça {identificador} retirada da caixa {peca['caixa_numero']}."
            else:
                aviso = f"Peça {identificador} removida do cadastro."

            if peca["caixa_id"]:
                ocupacao = _ocupacao(cur, peca["caixa_id"])
                capacidade = int(peca["capacidade"])
                if peca["caixa_status"] == "fechada" and ocupacao < capacidade:
                    aberta = _caixa_aberta(cur)
                    if aberta is None:
                        cur.execute(
                            """
                            UPDATE caixas
                            SET status = 'aberta', fechada_em = NULL
                            WHERE id = %s
                            """,
                            (peca["caixa_id"],),
                        )
                        aviso += (
                            f" A caixa {peca['caixa_numero']} foi reaberta "
                            f"({ocupacao}/{capacidade}), pois ficou abaixo da capacidade "
                            "e não havia outra caixa aberta."
                        )
                    else:
                        aviso += (
                            f" A caixa {peca['caixa_numero']} permanece fechada "
                            f"com {ocupacao}/{capacidade} peças, porque a caixa "
                            f"{aberta['numero']} já está em enchimento."
                        )
                elif peca["caixa_status"] == "aberta":
                    aviso += (
                        f" A caixa {peca['caixa_numero']} segue aberta "
                        f"({ocupacao}/{capacidade})."
                    )

    return {"mensagem": aviso}


def listar_caixas(somente_fechadas: bool = False) -> list[dict]:
    sql = "SELECT * FROM caixas"
    if somente_fechadas:
        sql += " WHERE status = 'fechada'"
    sql += " ORDER BY numero ASC"

    with conexao() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            caixas = [_limpar(linha) for linha in cur.fetchall()]
            for caixa in caixas:
                cur.execute(
                    """
                    SELECT id, peso, cor, comprimento, status, criada_em
                    FROM pecas
                    WHERE caixa_id = %s
                    ORDER BY criada_em ASC, id ASC
                    """,
                    (caixa["id"],),
                )
                caixa["pecas"] = [_limpar(p) for p in cur.fetchall()]
                caixa["ocupacao"] = len(caixa["pecas"])
    return caixas


def resumo() -> dict:
    with conexao() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  SUM(status = 'aprovada') AS aprovadas,
                  SUM(status = 'reprovada') AS reprovadas,
                  COUNT(*) AS total
                FROM pecas
                """
            )
            totais = cur.fetchone()
            cur.execute("SELECT COUNT(*) AS fechadas FROM caixas WHERE status = 'fechada'")
            fechadas = int(cur.fetchone()["fechadas"])
            cur.execute(
                """
                SELECT c.numero, c.capacidade, COUNT(p.id) AS ocupacao
                FROM caixas c
                LEFT JOIN pecas p ON p.caixa_id = c.id
                WHERE c.status = 'aberta'
                GROUP BY c.id
                ORDER BY c.numero DESC
                LIMIT 1
                """
            )
            aberta = cur.fetchone()

    aprovadas = int(totais["aprovadas"] or 0)
    reprovadas = int(totais["reprovadas"] or 0)
    total = int(totais["total"] or 0)
    caixa_aberta = None
    if aberta:
        caixa_aberta = {
            "numero": int(aberta["numero"]),
            "ocupacao": int(aberta["ocupacao"]),
            "capacidade": int(aberta["capacidade"]),
        }
    utilizadas = fechadas + (1 if caixa_aberta and caixa_aberta["ocupacao"] > 0 else 0)
    return {
        "total_pecas": total,
        "aprovadas": aprovadas,
        "reprovadas": reprovadas,
        "caixas_fechadas": fechadas,
        "caixas_utilizadas": utilizadas,
        "caixa_aberta": caixa_aberta,
        "taxa_aprovacao": round((aprovadas / total) * 100, 1) if total else 0,
    }


def relatorio() -> dict:
    base = resumo()
    pecas = listar_pecas()
    reprovadas = [p for p in pecas if p["status"] == "reprovada"]
    contagem = {chave: 0 for chave in ROTULOS}
    for peca in reprovadas:
        criterios = {m["criterio"] for m in (peca.get("motivos") or [])}
        for criterio in criterios:
            if criterio in contagem:
                contagem[criterio] += 1

    motivos = [
        {"criterio": chave, "rotulo": rotulo, "quantidade": contagem[chave]}
        for chave, rotulo in ROTULOS.items()
        if contagem[chave] > 0
    ]
    caixas = listar_caixas()
    return {
        **base,
        "motivos": motivos,
        "reprovadas_detalhe": reprovadas,
        "caixas": caixas,
        "capacidade_caixa": CAPACIDADE_CAIXA,
    }


def inserir_demonstracao() -> dict:
    """Inclui um lote fixo apenas quando o identificador ainda não existe."""
    lote = [
        ("QL-001", 100, "azul", 15),
        ("QL-002", 95, "verde", 10),
        ("QL-003", 105, "azul", 20),
        ("QL-004", 98.5, "verde", 12.4),
        ("QL-005", 101, "azul", 18),
        ("QL-006", 99, "verde", 14),
        ("QL-007", 102.2, "azul", 11),
        ("QL-008", 97, "verde", 16.5),
        ("QL-009", 104, "azul", 19),
        ("QL-010", 96.5, "verde", 13),
        ("QL-011", 100, "azul", 15),
        ("QL-012", 103, "verde", 17),
        ("QL-013", 80, "azul", 15),
        ("QL-014", 100, "vermelha", 15),
        ("QL-015", 110, "amarela", 25),
        ("QL-016", 100, "azul", 8),
    ]
    inseridas = 0
    ignoradas = 0
    for item in lote:
        try:
            cadastrar_peca(*item)
            inseridas += 1
        except ErroOperacao as erro:
            if erro.codigo == 400 and "Já existe" in erro.mensagem:
                ignoradas += 1
            else:
                raise
    return {
        "mensagem": f"Lote de demonstração: {inseridas} peça(s) incluída(s), {ignoradas} já existente(s).",
        "inseridas": inseridas,
        "ignoradas": ignoradas,
    }
