# Passo J — Exportação (§12.1–12.3)

O passo foi feito em `passo-i-treino` (`4134917`, `24fc4fe`, `ccc14cc`, `4f02c1f`, `2072ba3`,
`c080486`, `cbcde19`, `1fbc57d`, e o fechamento antigo em `42f8638`). O fechamento pela §16 foi
feito em 2026-10-28, no ramo `fechamento-c` (worktree
`C:\Python-Chess2\AbbyChessCraft-fechamento`), sobre o código de hoje e no escopo do passo J,
revisado num worktree parado (`C:\Python-Chess2\AbbyChessCraft-revisao`).

## O que o passo fez

- **A exportação pela estrutura do Documento**: as funções das áreas, o negrito e o itálico, o
  parágrafo e o hífen decididos; TXT, PGN por diagrama (CA-12.2), EPUB e DOCX por escritores
  próprios, e o PDF pesquisável.
- **O diálogo** com as opções (§12.1), o intervalo de páginas e os metadados do livro; a
  **prévia** em HTML pelo mesmo caminho (CA-12.4, CA-12.5).
- **O relatório** (§12.2): o que saiu e o que ficou de fora, uma linha por página em Avisos,
  que o duplo clique abre.
- **O EPUB aprovado** pelo EPUBCheck 5.4.0, pelo Ace by DAISY 1.4.6 e aberto no Calibre; os
  **mesmos bytes** com o mesmo `SOURCE_DATE_EPOCH` nos cinco formatos (CA-12.6).

## Revisões do fechamento

| Rodada | Revisor | Notas | Veredito |
|---|---|---|---|
| Código 1 | código e testes | Correção 7 · Simplicidade 8 · Testes 7 | volta |
| Produto 1 | produto, design e medição | Completude 7 · Fidelidade 6 · Clareza 7 · Produtividade 7 · Design 7 | volta |
| Código 2 | código e testes | 7 · 8 · 8 | volta (correção) |
| Produto 2 | produto, design e medição | 8 · 7 · 8 · 8 · 8 | volta (fidelidade: o JSON no portão) |
| Código 3 | código e testes | 8 · 8 · 8 | aceita |

**Código 1**: a opção desabilitada no diálogo continuava valendo (o desenho do FEN desligado
no EPUB, lembrado, trocava os diagramas do TXT por recortes sem o usuário ver); o
`so_verificadas` sem o caso positivo; o desempate da função da linha pelo hash de `str`
(mudava por processo); a capa velha apagada antes do JSON; o PGN vazio trocava o anterior.
**Produto 1**: o relatório inteiro num aviso só, sem destino por item; faltava o intervalo
da §12.1; nenhuma medida da exportação em JSON; no livro de referência o sumário não tinha
capítulo (a página lida sem área não tinha título); o PDF não era reproduzível; a prévia com
cores fixas.
**Código 2**: o intervalo ia até a última página do PDF, não do livro (com as inseridas).
**Produto 2**: só o JSON das medidas (`ferramentas/medir_exportacao.py`), que sai no portão
do fechamento, e o README passando a citá-lo; e o relatório lotaria os Avisos num livro
inteiro (uma linha por item), agora uma linha por página. A rodada disse que o passo fecha,
sem nova revisão de produto, quando o portão gravar o JSON e o README o citar: feito neste
registro (`docs/medidas/2026-10-29-exportacao-xv.json`).

Os commits: `46ef90d`, `a823ae5`, `976cafa`, `acd4de9`, `4558a53` e o deste registro.

## Decisões

| Decisão | Por quê |
|---|---|
| A opção que o formato não oferece (o controle cinza) vale o padrão | a lembrada de outro formato mudava este, escondida |
| A página lida sem área ganha as áreas automáticas no lote e no F5 | como o FineReader ao reconhecer: o título chega ao Documento e ao sumário sem abrir o modo Áreas |
| A linha de lances é reconhecida também pelas casas e pela peça, no texto sem espaços | o OCR leu "21." como "2lI." e a linha de lances virava capítulo |
| O relatório: uma linha por página, com o número impresso na frente quando difere | um aviso por item daria ~1.100 num livro inteiro; "página N" é o que o duplo clique abre |
| O intervalo não é lembrado | a próxima exportação começa no livro todo |
| O PDF com `SOURCE_DATE_EPOCH`: as datas dela e o `/ID` do original | o PyMuPDF sorteia a segunda metade do `/ID` a cada gravação |

## Verificação

- Suíte rápida no commit deste registro: 1769 aprovados e 3 pulados; ruff limpo. O portão
  do fechamento no `cd6681a`, com a árvore limpa: os 30 testes `livro_real` e `desempenho`
  aprovados (`ABBY_PORTAO=1`), a fatia em 0,687 da linha de base (739 de 1076 gestos) e as
  legendas aprovadas.
- CA-12.3 (`tests/golden/opcoes.yaml`, com o `intervalo` e o `so_verificadas` cobertos),
  CA-12.6 (EPUB, DOCX e PDF) em `tests/test_exportar_documento.py` e
  `tests/test_golden_exportacao.py`; o lote com as áreas automáticas em `tests/test_lote.py`.
- As medidas oficiais: `docs/medidas/2026-10-29-exportacao-xv.json`, do portão (o commit `cd6681a`, a árvore limpa): o
  EPUBCheck, o Ace e o Calibre sem problema; os cinco formatos com os mesmos bytes; o p95 de
  30 repetições, 3,2 s o PDF, 1,6 s o DOCX, 1,5 s o EPUB, 1,1 s o TXT e 9 ms o PGN; o EPUB com
  2 capítulos, 3 diagramas desenhados do FEN e 4 como recorte.

## Limitações conhecidas

- O EPUB é conferido (`epub.conferir`) depois de trocar o arquivo; o DOCX, antes.
- O número impresso só vem das páginas lidas pelos boxes: num PDF nascido digital todo da
  camada nativa, a `page-list` usa a posição no PDF.
- As páginas da camada nativa não contam os cabeçalhos tirados no relatório: desde 2026-11-05
  ele avisa, e a lista depende de um pedido ao core (`docs/pedidos-ao-pyboxeditor.md`, item 5).
- "Páginas não verificadas" é uma linha só, sem página para o duplo clique.
- O PDF guarda os metadados do original (o formulário é do EPUB e do DOCX).
- ~~O primeiro capítulo (as páginas antes do primeiro título) não tem item no `nav`; só o marco
  "Início do texto" leva a ele.~~ Corrigido em 2026-11-05.
- O Thorium e o leitor do celular continuam sem teste (com o usuário).
