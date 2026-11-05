# Passos PP1b e PPT (M3): a tela mostra o que importa

| Item | Ação | Prova | O que ficou |
|---|---|---|---|
| D-3 | `nativo.remendar`: as edições por cima da camada, palavra a palavra, por `difflib`; a página lida por OCR com glifo decidido sai dos boxes | CA-D3, sobre a página fabricada com figura e tabela e sobre a exportação de um PDF digital | Quebra, junção, parágrafo e letra inserida não se aplicam e vão ao relatório. Abaixo de 90 % igual, nada se aplica. Compara por palavra, e não "sem espaços" como a SPEC: cada glifo importado é uma palavra. Não testado num livro digital real |
| C-1 | `vigiar_o_pai` no começo de `_principal`, antes de carregar os modelos | CA-C1, com um processo de verdade morto à força | — |
| U-13 | `setNonBreakableLines` na linha impressa; o corpo desce até 9 pt | CA-U13 sobre linhas fabricadas | A captura do Seirawan p. 26 a 1366×768 não foi olhada |
| U-14 | "Largura" mede a mancha, sem o 1 % de glifos da margem; o zoom inicial é o da largura | CA-U14 sobre página fabricada | Em página sem leitura, vale a folha. Numa página real, a captura não foi olhada |
| F-2 | Os fortes (□, palavra desmentida, ilegal) com fundo de 3,9:1 sobre o papel e traço, por cima do realce de hoje | CA-F2.1, CA-F2.2, CA-F4.6 | **CA-F2.3, as capturas num livro treinado, não foi feito** |
| U-3 | `verificadas 123/300 · lances por conferir 410 · diagramas 14`, na barra; a fila vazia diz a tecla do lote | CA-U3 | — |
| U-10 | Filtro ao digitar; um resultado só já escolhe; 1 a 0 nos mais usados; a grade sai abaixo de 900 px | CA-U10: F2, `+`, `=` | **Os mais usados são da sessão, não do livro:** não há onde contar sem gravar nada novo no projeto |
| L-9 | `abbychess/tipo_de_pagina.py`, `PaginaLida.imagem`, a área `figura`, a exportação, o resumo, o fim do lote, a gaveta, o Documento, Ctrl+Shift+T | CA-L9.1 a CA-L9.4 | Abaixo |

## L-9, a medida

As grandezas, na capa e nas 13 páginas com gabarito de texto de três livros, a 300 dpi:

| Página | Tinta | Tinta em letras | Letras |
|---|---|---|---|
| Capa do Seirawan | 41,9 % | 1,4 % | 144 |
| As 13 de texto | 6,0 a 17,0 % | 52,7 a 98,6 % | 985 a 2.922 |

O corte: tinta ≥ 15 %, menos de 15 % dela em letras, e menos de 400 letras. **Varredura à parte, 1 página em 4 de 10 PDFs a 200 dpi:** só a página 0 de cada PDF e a 472 de um de 475 páginas caíram nele. Olhei três das miniaturas (a 472, que é uma imagem pequena sem texto, e duas capas). As outras são a primeira página de cada PDF, e não as abri. É amostra; o fim do lote lista e o Ctrl+Shift+T desfaz, porque o erro aqui esconde página.

## O que não foi verificado

- As capturas de CA-F2.3 e CA-U13, que pedem a tela real.
- Foco e teclado à mão: o agente só tem o `offscreen`.
- O teclado da paleta num menu de verdade: o teste manda as teclas ao `QMenu` direto.
