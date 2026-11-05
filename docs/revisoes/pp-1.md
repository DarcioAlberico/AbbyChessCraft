# Passo PP1 e T1, bloco 1 (M1): não perco nada, e a janela volta como deixei

| Item | Ação | Prova | O que ficou |
|---|---|---|---|
| R-3 | `ferramentas/catraca.py`, `docs/medidas/catraca-xv.json` | Regras sobre números fabricados; 7 páginas e 2 rodadas no portão | Sem a parte por classe (M4). Referência: CER 2,76 %, 331 erros, 7/7 diagramas, 0 casa errada, 1 linha perdida |
| C-2 | `abbychess/log_em_arquivo.py`: `app.log`, `leitura.log`, `faulthandler`, versões | Erro solto e `_sigsegv` em processos de verdade | O processo de render não tem log próprio: a SPEC pede dois |
| C-5 | `sem_erro_logado` em `conftest.py`, marca `erro_esperado` | `test_erro_logado` | Veja abaixo |
| D-1 | `Projeto.campos_do_box`, `PaginaDeOutraVersao` | CA-D1, com contador de leituras em `paginas/` | — |
| D-2 | O editor guarda o tabuleiro alterado por `(pid, caixa)` | CA-D2 | O guardado vive enquanto o projeto está aberto: não vai ao disco |
| D-4 | `Relatorio.camada_falhou`, trecho a trecho | CA-D4 | — |
| D-5 | `com_os_revisados` sai; `reler_boxes` recebe `nao_ler` | CA-D5, nos três caminhos | **O teste falhou antes da correção: o defeito é real. Dec-7 sem resposta: padrão a, nunca muda** |
| U-4 | `restaurar_a_geometria`, `reabrir_o_ultimo`, `app/recentes.py`, Projeto ▸ Recentes | CA-U4 | Só na entrada do programa, para a janela dos testes nascer sempre igual |
| U-5a | `_tem_por_conferir`, `_em_volta`; o resumo não conta o que falhou | CA-U5a | Num `livro.json` antigo, o F8 anda pela página até o resumo ser refeito |
| U-8 | Figurina e paleta na Galeria; Ctrl+Shift+G abre a Galeria | CA-U8 | A figurina repetida não alterna a cor, como no Documento |
| U-11 | "glifo" no lugar de "box" nas telas; F5 diz o que faz; "linha amarela"; "(F5)" pela tecla do perfil | Suíte | "Dividir o box" e os textos do Inspetor trocados. O número da fila já estava só no Inspetor e na barra |
| U-1 (foco) | `setFocusProxy`; o Glifo não toma o foco do Documento | CA-U1a | CA-U1b (borda, nome do painel) é T1, bloco 3 |

## C-5: os vermelhos do primeiro dia

20 no total, 18 na rápida e 2 na camada `processo`, no limite de 20. **19 provocam o erro de propósito** e levam `erro_esperado`. **1 achou defeito no próprio teste:** `test_diagramas_lidos_entram_na_pagina_que_pediu` gravava um diagrama com `casas=[None]`, e o gravador falhava em silêncio numa thread.

## O que mudou de comportamento

- Um glifo revisado não muda mais sozinho, nem por Ctrl+R, nem por F5 do "tudo", nem pela propagação.
- Reconhecer de novo (F5) não mudou; só o texto da pergunta, que estava errado.

## O que não foi verificado

A confirmação à mão que a SPEC pede antes de U-1 não foi feita: o agente não tem foco de verdade. O teste roda no `offscreen`.

## A medida de fim de marco

- `qualidade.py`: a rápida passou; a camada `processo` acusou 2 testes que provocam a queda do filho, e eles ganharam a marca. Medida de novo só no fim de M2 e de M3.
- Portão: 16 de 17 arquivos. **`test_ca_7_1` reprovou** (2.487 ms contra 2.400), como no PP0. A catraca passou, com duas rodadas iguais (CA-R3.5).
