# Trabalho Unifecaf — Gestão de peças, qualidade e armazenamento

Protótipo web em Python (Flask). Não há menu de terminal: as funções da prova ficam no menu lateral da página, depois do login.

O nome visível do produto é **Trabalho Unifecaf**.

## Funcionamento

O operador entra com a conta de avaliação e usa o menu da esquerda. As cinco opções do desafio são estas, nesta ordem:

1. **Cadastrar nova peça** — abre o formulário com identificador, peso (g), cor e comprimento (cm). A inspeção roda no servidor ao clicar em **Inspecionar e salvar**.
2. **Listar peças aprovadas/reprovadas** — tabela com as abas Todas, Aprovadas e Reprovadas. A busca filtra por identificador ou cor. O detalhe da linha mostra todos os motivos, quando a peça foi reprovada.
3. **Remover peça cadastrada** — escolhe uma peça da lista e apaga só ela. A caixa não é excluída; a ocupação é atualizada.
4. **Listar caixas fechadas** — a aba **Fechadas** já vem selecionada. Cada caixa fechada mostra a ocupação e, em **Gerenciar**, as peças que estão nela.
5. **Gerar relatório final** — totais de aprovadas e reprovadas, quantidade de cada motivo, lista das peças reprovadas e quantidade de caixas utilizadas.

Antes dessas cinco opções o menu tem **Painel** (totais e últimas inspeções). Depois delas fica **Como funciona**, com a leitura das regras no código. Os dois são extras da interface.

Uma peça só é **aprovada** se as três condições valem ao mesmo tempo:

- peso entre 95 g e 105 g (inclusive);
- cor azul ou verde;
- comprimento entre 10 cm e 20 cm (inclusive).

Se algum critério falha, a peça é gravada como reprovada, sem caixa, e **todos** os motivos ficam registrados — o programa não para no primeiro erro. Peça aprovada entra na caixa aberta. Na 10ª peça essa caixa fecha e a próxima aprovada abre outra. Caixas utilizadas no relatório são as fechadas mais uma, se a caixa aberta já tiver pelo menos uma peça.

## Como rodar

Requisitos: Python 3.11 ou superior e MySQL ou MariaDB. No Windows, o XAMPP atende: o MySQL precisa estar em execução. Este roteiro não apaga o banco.

1. Abra o terminal na pasta do projeto:

```powershell
cd C:\Users\diego\trabalho5
```

2. Crie e ative o ambiente virtual, se ainda não existir:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Instale as dependências:

```powershell
pip install -r requirements.txt
```

4. Se o arquivo `.env` ainda não existir, copie o exemplo. Se já existir, mantenha o arquivo atual:

```powershell
copy .env.example .env
```

5. Suba a aplicação:

```powershell
python run.py
```

6. Abra [http://127.0.0.1:5000](http://127.0.0.1:5000).

7. Entre com a conta de avaliação:

- e-mail: `trabalho@unifecaf.com`
- senha: `trabalho123`

Na primeira subida, se o banco `gestao_pecas` ou as tabelas ainda não existirem, o programa cria só o que falta. Peças, caixas e usuários já gravados permanecem. Sem login, a API de operação responde 401.

O `.env` aceita `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` e `FLASK_PORT`. Com o XAMPP padrão, usuário `root` e senha vazia funcionam.

## Exemplos de entrada e saída

Os textos abaixo são os que o sistema mostra. O número da caixa depende do que já está gravado: se não houver caixa aberta, a primeira aprovada abre a caixa 1.

### Peça aprovada

No menu **Cadastrar nova peça**:

| Campo | Entrada |
| --- | --- |
| Identificador | QL-001 |
| Peso (g) | 100 |
| Cor | Azul |
| Comprimento (cm) | 15 |

Aviso na tela, com a caixa 1 vazia:

`Peça QL-001 aprovada e armazenada na caixa 1 (1/10).`

Na lista, o resultado aparece como **Aprovada**, na caixa 1. O detalhe diz: "Dentro de todos os critérios. Peça armazenada."

No lote de exemplos, `QL-010` (peso `96.5`, cor Verde, comprimento `13`) é a 10ª aprovada. Com o cadastro vazio, ela fecha a caixa 1 e o aviso é:

`Peça QL-010 aprovada. A caixa 1 atingiu 10 peças e foi fechada.`

Se essa mesma peça entrar numa caixa que ainda não está na 10ª vaga, o aviso é `Peça QL-010 aprovada e armazenada na caixa N (ocupação/10).`

### Peça reprovada por um motivo

| Campo | Entrada |
| --- | --- |
| Identificador | QL-013 |
| Peso (g) | 80 |
| Cor | Azul |
| Comprimento (cm) | 15 |

Aviso:

`Peça QL-013 reprovada. Veja os motivos da inspeção.`

A tela abre o detalhe da peça, com a etiqueta **Reprovada** e sem caixa. O único motivo exibido é:

`Peso de 80.00 g fora da faixa de 95 g a 105 g.`

Cor fora da faixa, com peso e comprimento válidos (`QL-014`, peso `100`, cor Vermelha, comprimento `15`):

`Cor 'vermelha' não permitida. Aceitas: azul ou verde.`

### Peça reprovada pelos três motivos

| Campo | Entrada |
| --- | --- |
| Identificador | QL-015 |
| Peso (g) | 110 |
| Cor | Amarela |
| Comprimento (cm) | 25 |

Aviso:

`Peça QL-015 reprovada. Veja os motivos da inspeção.`

O detalhe lista os três textos, nesta ordem:

- `Peso de 110.00 g fora da faixa de 95 g a 105 g.`
- `Cor 'amarela' não permitida. Aceitas: azul ou verde.`
- `Comprimento de 25.00 cm fora da faixa de 10 cm a 20 cm.`

### Relatório depois do lote de exemplos

O botão **Exemplos**, no topo, abre **Carregar exemplos**. **Incluir lote** grava 16 peças (QL-001 a QL-016) somente quando o identificador ainda não existe. Nada que já está no banco é apagado.

Se essas 16 peças entram com o cadastro vazio, **Gerar relatório final** mostra:

- Aprovadas: **12**
- Reprovadas: **4**
- Caixas fechadas: **1** (a caixa 1, com QL-001 a QL-010)
- Caixas usadas: **2** (a fechada e a caixa 2, aberta com QL-011 e QL-012)

Em **Motivos da reprovação**, cada critério que falhou soma um. A mesma peça entra em mais de um motivo:

- Peso fora da faixa (95 g a 105 g): **2**
- Cor diferente de azul ou verde: **2**
- Comprimento fora da faixa (10 cm a 20 cm): **2**

Em **Peças reprovadas** a lista vem da mais recente para a mais antiga: QL-016 (`comprimento`), QL-015 (`peso, cor, comprimento`), QL-014 (`cor`) e QL-013 (`peso`). QL-016 é peso 100, cor azul e comprimento 8.

Se algum identificador já existir, o lote ignora essa peça e os totais acompanham o que já estava gravado.

## Onde está a lógica

- `app/qualidade.py` — decisões da inspeção
- `app/servicos.py` — cadastro, caixas, remoção e relatório
- `templates/index.html` — menu lateral e telas
- `PARTE_TEORICA.md` — discussão do desafio
- `deploy/nginx/` — publicação HTTP e HTTPS, fora do roteiro local da prova
