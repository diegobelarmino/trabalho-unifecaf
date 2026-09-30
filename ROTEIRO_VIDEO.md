# Roteiro do vídeo pitch (até 4 minutos)

Grave a tela do navegador em http://127.0.0.1:5000 e o terminal com o programa rodando. Publique como não listado no YouTube, Loom, Google Drive ou LinkedIn e cole o link na entrega.

## 0:00 – 0:40 · Problema

Na inspeção manual, peso, cor e comprimento dependem de quem confere. Isso atrasa a linha, deixa passar peça fora da faixa e aumenta o custo de retrabalho. O Trabalho Unifecaf automatiza essa decisão e organiza as aprovadas em caixas de 10.

## 0:40 – 1:40 · Lógica

Mostre o painel com as três regras: peso de 95 g a 105 g, cor azul ou verde, comprimento de 10 cm a 20 cm. Explique que a peça só é aprovada se as três passarem, que a reprovada guarda todos os motivos e que a aprovada entra na caixa aberta. Na décima, a caixa fecha.

Aponte no código, se quiser, `avaliar_peca` em `app/qualidade.py` e o fechamento da caixa em `app/servicos.py`.

## 1:40 – 2:10 · Boas práticas

Funções separadas para regra de qualidade, banco e interface. Validação no servidor. Banco MySQL/MariaDB, sem apagar o histórico ao abrir o programa. Menu com as cinco opções do desafio e modais para cadastrar, remover e ver detalhes.

## 2:10 – 3:40 · Demonstração

1. Clique em **Carregar exemplos** ou cadastre `QL-020`, peso `100`, cor azul, comprimento `15`. Mostre a mensagem de aprovada e a caixa enchendo.
2. Cadastre uma reprovada: peso `80`, cor vermelha, comprimento `8`. Abra o modal e leia os três motivos.
3. Abra **Listar peças** e alterne aprovadas e reprovadas.
4. Abra **Caixas fechadas** e o modal com as peças da caixa 1 (o lote de exemplo fecha uma caixa).
5. Remova uma peça pelo menu 3 e leia o aviso sobre a caixa.
6. Abra **Relatório final**: totais, motivos e caixas utilizadas.

## 3:40 – 4:00 · Fecho

O mesmo critério pode receber dados de sensor, câmera e integração com a linha. O protótipo já registra a decisão, a caixa e o motivo.
