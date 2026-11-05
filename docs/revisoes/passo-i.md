# Passo I — Treino (§9)

O passo foi feito em `passo-i-treino` (de `a728553` a `b416a95`), com a régua do itálico e o
CA-9.1 nas pendências de 2026-10-23 e 2026-10-28. O fechamento foi feito em 2026-10-28, no
ramo `fechamento-c` (worktree `C:\Python-Chess2\AbbyChessCraft-fechamento`), sobre o código de
hoje e no escopo do passo I, junto com o do passo C.

## O que o passo fez

- **O livro novo guiado** (§9.1): o Ctrl+N pede num formulário só o nome, o idioma e o
  intervalo do corpo; com os modelos prontos, três páginas a 10%, 50% e 90% do corpo são lidas
  como amostra pelo servidor, e a janela abre a primeira delas com a fila por caractere, o
  primeiro glifo no Glifo e o foco no campo.
- **O cartão Saúde do livro**, na gaveta e no estado vazio do Documento: os pendentes de cada
  página da amostra, antes e agora (cada página é um link), as amostras ensinadas, e
  "Reconhecer o livro" em destaque quando a amostra cai até o limiar escolhido no cartão.
- **O texto nativo** (`core.pdf_nativo`, CA-9.5): a oferta no Ctrl+N; aceitá-la cria as
  páginas sem pedir OCR ao servidor.
- **Os efeitos de impressão** (CA-9.3): negrito e itálico medidos por palavra, guardados no
  glifo e na amostra ensinada, e o k-NN só compara amostras do mesmo efeito quando o efeito
  do glifo é conhecido — na propagação do Enter e, desde o fechamento, também na leitura do
  lote e do F5.
- **As ligaduras** (CA-9.2): `ﬁ` ensinada lê como um box "fi", e sai "fi" no Documento e
  na exportação.
- **A faixa Linha** no Inspetor Glifo, no lugar do antigo "Na linha".

## Revisões do fechamento

| Rodada | Revisor | Notas | Veredito |
|---|---|---|---|
| Código 1 | código e testes | Correção 6 · Simplicidade 7 · Testes 7 | volta |
| Produto 1 | produto, design e medição | Completude 6 · Fidelidade 7 · Clareza 6 · Produtividade 6 · Design 7 | volta |
| Código 2 | código e testes | 6 · 8 · 7 | volta |
| Produto 2 | produto, design e medição | 8,5 · 8,5 · 8,5 · 9 · 7 | volta |
| Código 3 | código e testes | 8 · 8 · 8 | aceita |
| Produto 3 | produto, design e medição | 9 · 8,5 · 8,5 · 9 · 8,5 | aceita |

**Código 1**: o estilo não medido valia como "reto conhecido" no k-NN (o `Estilo` padrão era
`(False, False)`), e um glifo em negrito sem medida nunca casava com as amostras em negrito;
o filtro do efeito não participava da leitura do lote nem do F5, só do Enter (a medida do
CA-9.1 provava a propagação, não o lote); a oferta e a importação da camada nativa rodavam na
thread da interface; a ligadura saía `ﬁ` na exportação, um segundo caminho que monta o texto.
**Produto 1**: depois da amostra, a janela ficava na p. 1, fora dela, e o primeiro Enter não
fazia nada; as mensagens da amostra e da camada nativa eram apagadas na hora; o CA-9.4 não
era medido por gestos (o teste rodava no controlador, sem Ctrl+N nem servidor falso) e a
cláusula de desempenho não tinha teste; o cartão Saúde mostrava só a soma, sem as páginas,
sem o limiar escolhível; o destaque "pronto" não tinha estilo; textos e a faixa Linha.
**Código 2**: `reler_pelo_efeito` nunca relia em produção: a procedência gravada é relativa à
pasta dos padrões, e `efeito_de` só aceitava o caminho absoluto. O teste passava porque
registrava o absoluto.
**Produto 2**: o cartão Saúde alargava a gaveta de 150 para 268 px.
**Produto 3** (aceita): o rótulo do limiar dizia "o lote" quando o destaque é do
botão "Reconhecer o livro"; o texto foi trocado junto com este registro.

Os commits: `c8e8922` (o `Estilo` de três estados), `5067748` (o efeito no lote e no F5, a
camada nativa numa thread, a ligadura na exportação), `bfa078f` e `9ebe441` (a amostra guiada,
o cartão Saúde, o CA-9.4, os textos, a faixa Linha), `fc54326` (a procedência relativa, o
cartão em 150 px, os plurais).

## Decisões

| Decisão | Por quê |
|---|---|
| `Estilo` com três estados por eixo (`None` não medido, `False` reto, `True`) | o "não medido" tem de comparar com todas as amostras; o reto medido tem de excluir as de outro efeito. O JSON guarda os retos num quarto item: o de antes, `[0, 0, 0]`, continua "não medido" |
| O filtro do lote por releitura depois de medir | a medida do efeito precisa das palavras lidas; reler só os glifos lidos por amostra de efeito incompatível custa pouco |
| A camada nativa por `dialogos.em_segundo_plano` (thread e diálogo modal) | o projeto ainda não está ligado à janela, e não há outro escritor; o PDF inteiro a 300 dpi leva tempo |
| No CA-9.4, o diálogo de pasta conta com o de arquivo | os dois são a escolha do livro e de onde guardá-lo; os gestos contados são Ctrl+N, Enter no formulário e o Enter que ensina |
| O corte da cláusula de desempenho é 60 ms | a regra da §15.3 ("o corte é o alvo × 1,2"), igual aos outros testes de desempenho |

## Verificação

- Suíte rápida no `fc54326`: 1727 testes aprovados e 3 pulados; `-m processo
  tests/test_ca_9_4.py` aprovado; ruff limpo.
- CA-9.1 (`ferramentas/medir_legendas.py`, `2026-10-28-legendas-xv.json`, definitivo),
  CA-9.2 e CA-9.3 (`tests/test_ligaduras.py`, `tests/test_italico.py`), CA-9.4
  (`tests/test_ca_9_4.py`: 3 gestos; [desempenho] em `tests/desempenho/test_carregar_modelos.py`,
  com o JSON no portão do fechamento) e CA-9.5 (`tests/test_nativo.py`).

## Limitações conhecidas

- ~~A releitura (F5, lote com refazer) troca o negrito e o itálico que o usuário decidiu
  (Ctrl+B, Ctrl+I) pelos medidos; o sublinhado fica. O F5 se desfaz.~~ Corrigido em 2026-11-05
  (`Estilo.decidido`); vale para as decisões daí em diante.
- Amostras ensinadas antes do fechamento com o efeito `[0, 0]` continuam lidas como retas
  (o glifo podia não ter sido medido).
- A camada nativa não traz as figuras do PDF, e os boxes dela (geometria aproximada,
  revisados) ficam numa página relida pelo F5.
- Com o aviso ativo, a imagem da faixa Linha fica mais baixa por uns segundos.
- O projeto criado pela camada nativa abre na última página lida.
