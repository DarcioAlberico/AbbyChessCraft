# Auditoria do AbbyChessCraft (2026-10-15)

Retrato do programa antes da spec (`docs/SPEC.md`). Feito só lendo o código; os caminhos são
relativos a `abbychess/`, e `core/` é o PyBoxEditor. As linhas são as daquele dia e mudam.

## A interface hoje

- `app/janela.py` (1.280 linhas): o visor no centro; à direita, uma doca com as abas Treino,
  Padrões do livro e Verificação; embaixo, o **texto reconhecido num `QPlainTextEdit`
  somente leitura**, de umas três linhas de altura. Os menus são Projeto, Editar, Página e
  Ferramentas. Não há Exibir, Ajuda nem Janela, e o layout das docas não é guardado
  (`saveState` não é usado).
- `app/visor.py`: o zoom é só Ctrl+roda, fator 1,15, sem limite, e Ctrl+0 ajusta à janela.
  Não há 100%, zoom no box nem reajuste ao redimensionar. Cada `_atualizar_tudo` remove e
  recria uns 2.000 `QGraphicsRectItem`, e `_box_em` varre todos os boxes a cada clique.
- **Não existe**: localizar e substituir, miniaturas das páginas, lista de páginas com
  estado, sincronia entre o texto e a imagem, edição do texto, painel permanente de
  diagramas, cache de páginas.
- Atalhos que conflitam: Tab é "pular" no treino e "pular palavra" na verificação; Esc e Del
  têm três sentidos, conforme o foco; não há atalhos de zoom, nem da primeira ou da última
  página.

## Dados e persistência

- O projeto guarda `projeto.json`, `padroes/<char>/*.png` com `metadados.json`,
  `paginas/NNNN.json`, `paginas/marcadas.json`, `zonas/NNNN.json`, `diagramas/`,
  `lexico.txt` e `inclinacoes.json`.
- Em `projeto.json`, `VERSAO = 1` não tem migração, e um campo desconhecido o torna
  "ilegível" (`Projeto(**bruto)`). A fonte é guardada com caminho absoluto.
- `inclinacoes.json` é gravado sem a escrita atômica de `_gravar_json`.
- A página não guarda colunas, parágrafos, estilos, cabeçalho, rodapé nem a ordem das áreas.
  O texto é remontado dos boxes toda vez, por **três caminhos que normalizam diferente**:
  `pagina.texto`, `diagramas.texto_da_pagina` (que troca ♘ por N) e `exportar.palavras` /
  `paragrafos` (que mantém ♘).
- Os boxes são identificados pelo **índice**, e o conjunto `pulados` é remapeado à mão em
  seis lugares da janela.

## O que o core oferece e não está ligado

| Módulo | O que traria |
|---|---|
| `core/livro.py` | Colunas de primeira classe, tabelas por réguas, parágrafos com recuo, `retirar_cabecalhos`, junção no hífen, `titulo_e_autor` |
| `core/pagina.py` | O modelo `Tabela` (só `Figura`, `PaginaExtraida` e `Paragrafo` são usados) |
| `core/pdf_nativo.py` | Texto e FEN exatos de PDFs nascidos digitais, sem OCR |
| `core/familias_de_pagina.py` | Classificar a página (prosa, tabela, duas colunas, painel) |
| `core/negrito.py` | Negrito pela espessura do traço (linha principal, legendas) |
| `core/pgn.py`, `core/nags.py` | Exportar PGN; a tabela dos NAGs |
| `core/editorial_*` | Documento intermediário, fila de revisão com diário, gate de qualidade |

`exportar.py` importa dois privados do core (`_corpo_que_preenche`, `_origem_do_texto`).

## Arquitetura e desempenho

- A janela concentra o estado (uns 20 atributos soltos), a orquestração das tarefas e a
  lógica de domínio em closures.
- `app/trabalho.py` roda **uma tarefa por vez** (`setMaxThreadCount(1)`); o lote trava o
  programa inteiro, e uma ação pedida com ele ocupado é ignorada sem aviso. Os boxes são
  mudados na thread de trabalho enquanto o visor guarda a mesma lista.
- Por ação: a fila é recalculada várias vezes, o visor recriado, o texto remontado e o JSON
  da página inteiro regravado na thread da interface.
- Trocar de página renderiza e endireita a página de novo, sem cache, e lê o mesmo JSON três
  vezes.
- O desfazer copia a página inteira duas ou três vezes por ação, até 100 passos por página e
  sem limite de páginas: numa sessão longa, centenas de MB.
- `PadroesDoLivro.esquecer` e `restaurar` releem todos os PNGs do disco.
- O F6 com a fila vazia lê o JSON de todas as páginas na thread da interface.

## O uso num livro de 300 páginas

1. O lote de ~50 min trava tudo, e não aprende com o que se ensina durante ele.
2. Não há visão do livro: quais páginas faltam, têm pendentes ou diagramas por conferir.
3. O texto não se edita: espaço que falta, palavra partida e hífen só se corrigem no Word.
4. Não há busca; um erro repetido ("1" por "l") se acha página a página.
5. Clicar no texto não leva ao glifo, nem o glifo ao texto.
6. A fila por confiança faz o olho saltar pela página; não há fila por caractere ("todos os
   'l' duvidosos") para confirmar de uma vez.
7. A conferência de diagramas é um diálogo, sem a galeria dos diagramas do livro.
8. A sessão não se lembra do zoom, do layout nem da página aberta por último.
9. A exportação não tem pré-visualização, PGN nem relatório do que saiu como margem.
