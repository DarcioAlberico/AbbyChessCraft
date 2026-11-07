# Passo PPL (M2): ver o lance

| Item | Ação | Prova | O que ficou |
|---|---|---|---|
| 0, viabilidade | A linha abre no editor Palavra; corrigir vai pela sessão do Documento, não por `vf.corrigir`, que não respeita a prosa da linha | Testes da fila | Uma diferença do roteiro: **a sessão pega só as palavras que mudaram**, porque ela marca `revisado` em tudo o que cobre |
| 1 | `abbychess/tokens.py`: `classificar_token` usa as funções de `lances`; `Projeto.letras_das_pecas`, nas Opções | CA-R1.6: 60 linhas, nos dois alfabetos, e `lances._tokens` na mesma tabela | A letra inglesa vale também em português, como já valia em `lances` |
| 2 | **Não feito: é do usuário.** Os 8 erros do gabarito | — | `docs/revisoes/checkup-2026-11/erros-do-gabarito.md`. Muda a chave da catraca: `ferramentas/catraca.py --remedir` |
| 3 | `abbychess/decodificador_de_lances.py`, sem rebobinar | CA-X1.2, CA-X1.4, CA-X1.5 (metade) | A semente da página anterior só na ferramenta |
| 4 | `ferramentas/medir_sincronia.py` | Abaixo | No `corpus_v2`, a referência não traz diagramas: o teto ali é um piso |
| 5 | F-3: `lances.gids_do_rejeitado`, `abbychess/evidencia.py`, o estado `FORTE` no Documento | CA-F3.1, CA-F3.2 | — |
| 6 | X-3: "lado não dito", Ctrl+W e Ctrl+B, lado presumido no relatório | CA-X3.1, CA-X3.2 | `DiagramaLido.confiavel` não mudou: o diagrama sem lado continua saindo desenhado na exportação, com `w` |
| 7 | X-1, sem hipóteses | CA-X1.2, CA-X1.3, CA-X1.4, CA-X1.6 no portão, CA-X1.7 | Ver abaixo: **ele não marcou nenhum erro nesta amostra** |
| 8 | `{"evento": "pagina"}`, `tempo_da_fatia --por-pagina`, ligado por padrão no programa, com a opção de desligar | Testes | Só instantes e tipos |
| 9 | F-4: a fila, F4, relatório, Ctrl+T, `lances_por_conferir` | CA-F4.1, CA-F4.2, CA-F4.7a, CA-F4.9 | Ver abaixo |

## A diferença do desenho: a evidência não usa tarefa nem 500 ms

A SPEC pede tarefa leve, 500 ms depois da última edição. Aqui ela é calculada em `pintar_texto`, que já roda fora do Enter, 150 ms depois da última edição, e guardada por uma chave da página. É mais simples e não abre corrida com a fila de tarefas. CA-X1.6 vigia o Enter.

## A medida do item 4 (05/11, `docs/medidas/2026-11-05-sincronia.json`)

**Exploratório:** o Seirawan já foi visto, e o `corpus_v2` não foi auditado. O alinhamento é da página inteira, em sequência.

| Livro | Tokens de lance | Teto, sem rebobinar | Cobertura na leitura | Errados | De forma válida | Marcados | Certos marcados | Errados fora da fila |
|---|---|---|---|---|---|---|---|---|
| Seirawan | 136 | 32,4 % | 16,8 % | 28 | 7 | 0 | 0 | 1 |
| Aagaard | 77 | piso 0 % | 0 % | 31 | 10 | 0 | 0 | 2 |
| Nunn | 55 | piso 0 % | 2,1 % | 24 | 15 | 0 | 1 | 2 |
| Yusupov | 154 | piso 0 % | 0 % | 24 | 16 | 0 | 0 | 1 |

- **Ponto de parada, pela regra:** teto de 32,4 % ≥ 30 %, alarme de 0,3 % < 5 %. X-1 entra.
- **Mas isto é fraco, e o registro precisa dizer:** o teto só passa no único livro com diagramas no gabarito, e por pouco. **Dos 107 tokens errados, X-1 marcou 0.** O alarme baixo é de quem quase nunca tem posição. Sem rebobinar, a marca de ilegal vale pouco nestes livros; o ganho, se houver, é da fila Lances e do olho. PP7 é quem pode mudar isso.
- **CA-F4.11:** 6 dos 107 errados (5,6 %) ficavam em linha fora da fila, acima dos 5 %. A regra manda incluir a vizinha, e `COM_AS_VIZINHAS` a inclui: ficam 4 de 107 (3,7 %). Custa linhas de prosa a mais; o ponto de parada de M2 revê. O JSON gravado é o de depois da vizinha; a tabela acima, de antes dela, na coluna de fora da fila.

## O que falta, e é do usuário

- **CA-F4.8:** 20 páginas reais; `ferramentas/tempo_da_fatia.py <registro> --por-pagina --fila lances`. Mediana de até 2 min por página.
- **CA-F4.10:** passar a fila nas 7 páginas do Seirawan e nas 4 do `corpus_v2`, e `ferramentas/medir_sincronia.py --projeto X --livro seirawan` (10 min).
- **Os 8 erros do gabarito.**

Sem resposta, vale o roteiro: PP1b e PPT seguem, e a fila Lances fica no F4, sem abrir sozinha.

## O que não foi verificado

- Teclado e foco à mão: o agente só tem o `offscreen`.
- A viabilidade a 1366 px da linha de 70 caracteres foi resolvida por conta (`corpo_do_texto`), não olhada numa tela.
- Os glifos `revisado` por linha conferida saem da fila de hoje. Ninguém mediu o efeito no treino (SPEC §12).

## A medida de fim de marco

- `qualidade.py`, depois da correção do par do dryer e dos caminhos sem teste: rápida e `processo` saída 0, cobertura 95,1 %, nada fora da lista.
- Portão: 16 de 17 arquivos. **`test_ca_7_1` reprovou de novo** (2.461 ms contra 2.400), como em M1 e no PP0; a meta oscila (C-6, fora dos marcos). O índice da busca não mudou neste passo.
- CA-F.1 e a catraca passaram: a fila nova não subiu os gestos da fatia, nem mudou a leitura.
