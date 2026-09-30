"""Regras de inspeção da linha de montagem.

Uma peça só é aprovada quando as três condições são verdadeiras ao mesmo tempo.
Se qualquer medida falhar, a peça é reprovada e todos os motivos são registrados.
"""

PESO_MIN = 95.0
PESO_MAX = 105.0
COMPRIMENTO_MIN = 10.0
COMPRIMENTO_MAX = 20.0
CORES_PERMITIDAS = ("azul", "verde")
CAPACIDADE_CAIXA = 10


def avaliar_peca(peso: float, cor: str, comprimento: float) -> tuple[bool, list[dict]]:
    """Retorna (aprovada, motivos). Lista vazia significa peça aprovada."""
    motivos: list[dict] = []
    cor_normalizada = (cor or "").strip().lower()

    if peso < PESO_MIN or peso > PESO_MAX:
        motivos.append(
            {
                "criterio": "peso",
                "descricao": (
                    f"Peso de {peso:.2f} g fora da faixa "
                    f"de {PESO_MIN:.0f} g a {PESO_MAX:.0f} g."
                ),
            }
        )

    if cor_normalizada not in CORES_PERMITIDAS:
        permitidas = " ou ".join(CORES_PERMITIDAS)
        motivos.append(
            {
                "criterio": "cor",
                "descricao": f"Cor '{cor}' não permitida. Aceitas: {permitidas}.",
            }
        )

    if comprimento < COMPRIMENTO_MIN or comprimento > COMPRIMENTO_MAX:
        motivos.append(
            {
                "criterio": "comprimento",
                "descricao": (
                    f"Comprimento de {comprimento:.2f} cm fora da faixa "
                    f"de {COMPRIMENTO_MIN:.0f} cm a {COMPRIMENTO_MAX:.0f} cm."
                ),
            }
        )

    return len(motivos) == 0, motivos
