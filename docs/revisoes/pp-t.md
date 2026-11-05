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
| As 13 de texto | 2,1 a 17,0 % | 52,7 a 98,6 % | 417 a 2.922 |

O corte: tinta ≥ 15 %, menos de 15 % dela em letras, e menos de 400 letras. **Varredura à parte, 1 página em 4 de 10 PDFs a 200 dpi:** só a página 0 de cada PDF e a 472 de um de 475 páginas caíram nele. Olhei três das miniaturas (a 472, que é uma imagem pequena sem texto, e duas capas). As outras são a primeira página de cada PDF, e não as abri. É amostra; o fim do lote lista e o Ctrl+Shift+T desfaz, porque o erro aqui esconde página.

## A tela real

O programa inteiro, no `offscreen`, com a rede e sem padrões ensinados, a 1366×768, Seirawan:

| Medida | Resultado |
|---|---|
| CA-U13, p. 26 | nenhuma linha impressa em duas; só os 3 blocos de diagrama têm mais de uma linha visual; corpo 9 de 10, sem rolagem |
| CA-U14, p. 26 | zoom de 0,268 contra 0,166 da folha: 61 % maior |
| CA-L9.1, capa | 0,1 s, área `figura`, 0 glifo |
| Fila Lances, por página (i020 a i026) | 5, 36, 14, 31, 13, 0 e 15 linhas com as vizinhas; 3, 22, 6, 17, 7, 0 e 9 sem elas |

**A vizinha dobra a fila:** mediana de 14 linhas, contra 7. Fica dentro da estimativa (de 10 a 15), mas o pior caso é quase a página inteira (36 de 40). Se CA-F4.8 passar de 2 min, é a primeira coisa a desligar: `decodificador_de_lances.COM_AS_VIZINHAS`.

**O que a tela achou e os testes não:** o campo abria a linha toda selecionada, e uma tecla sem querer apagaria a linha; agora começa sem seleção, em letra menor. A etiqueta do progresso ficava para trás até a próxima mudança; agora conta a página aberta. **O campo do Inspetor continua estreito para uma linha de 70 caracteres:** a comparação é na faixa Linha.

**Não é captura num livro treinado:** CA-F2.3 continua por fazer. Sem padrões, os fortes são muitos (29 na p. 26).

## O que não foi verificado

- CA-F2.3, a captura num livro já treinado.
- Foco e teclado à mão: o agente só tem o `offscreen`.
- O teclado da paleta num menu de verdade: o teste manda as teclas ao `QMenu` direto.

## A revisão independente

Uma leitura do diff inteiro, só de leitura, sem rodar nada, achou 10 pontos. Conferi cada um no código e corrigi com teste em `tests/test_revisao_da_entrega.py`:

| # | Defeito | Correção |
|---|---|---|
| 1 | Página de core mais novo levantava na navegação, com o estado meio trocado | `ir_para` carrega antes de mudar o estado, avisa e devolve falso; `recalcular` registra |
| 2 | Lance com letra inserida nunca ficava conferido | `conferidos` conta os virtuais |
| 3 | A evidência não via decisão nem área | Na chave |
| 4 | Trocar as letras não refazia a validação gravada | A página aberta na hora; relatório e exportação validam de novo. **As outras páginas só ao serem editadas, na marca da tela** |
| 5 | `do_modelo` montava o texto na thread da interface | `leve=True` em `agendar`; o gravador refaz. O portão vigia |
| 6 | Ilegal com `!` contava duas vezes | Por interseção de gids |
| 7 | `ir_para` falso seguia para `recontar` | Testado o retorno |
| 8 | `1.` depois de diagrama não lido abria a posição inicial | Não abre mais |
| 9 | Backspace e dígito na paleta | Tratados |
| 10 | Mudança do core desfazia a camada nova, em silêncio | Página importada sem edição não é remendada. **Com edição, o risco fica:** uma diferença do core vira edição. Guardar as palavras da importação pediria gravar mais no projeto |

## A medida de fim de marco

- `qualidade.py` no `27bded1`: rápida e `processo` saída 0, cobertura 95,2 %, nada fora da lista. O que veio depois é só a interface: suíte rápida, 2.889 passaram, e `ruff`.
- Portão no `ee61677`, com as correções da revisão: 17 de 18 arquivos. A catraca não mudou: CER 2,76 %, duas rodadas iguais; a capa e as páginas com gabarito passam em L-9.
- **`test_ca_7_1` reprovou em todas as rodadas do dia:** 2.498, 2.487, 2.461, 2.433 e 2.464 ms contra o limite de 2.400, nas duas primeiras antes de qualquer código de M1 entrar no índice. A meta é o C-6, fora dos marcos, e passou em 05/11 de manhã por 20 ms. **Não é regressão provada, nem foi investigado.**
