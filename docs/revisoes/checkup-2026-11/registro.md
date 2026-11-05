# Registro do check-up de 2026-11-05 e das seis revisões

Base: `262d897`, ramo `checkup-geral`, sem commit. Documentos: `docs/pesquisa/checkup-2026-11.md`,
`docs/SPEC-pagina-perfeita.md`, `plans/roadmap-pagina-perfeita.md`.

## O que foi feito, e por quê

| Ação | Motivo |
|---|---|
| Cinco auditorias independentes, só de leitura: arquitetura, design, testes, motores, estado da arte | Ter uma leitura não ancorada na minha; os relatórios estão em `docs/pesquisa/checkup-2026-11/` |
| `medir.py`, `qualidade.py` e as capturas no `262d897` | Números de hoje, sem confiar nos de 28/10 |
| Perícia do erro, por box e por motor, nas 213 linhas verificadas | Saber quem erra e se a fila vê |
| Tesseract, EasyOCR e PP-OCRv6 nas mesmas linhas e nos livros com figurinas | Medir a complementaridade, em vez de supor |
| `core.livro` nas mesmas páginas (E0) | Saber se a fusão do core, que o app não usa, ganha |
| Seis revisões, cada crítico novo, uma de cada vez, cada uma corrigida antes da seguinte | O pedido do usuário |

## As seis revisões

Os textos completos estão em `criticas/`. Todos os achados foram aplicados, salvo os da última linha.

| # | Foco | Veredito | B / I / M | O que mudou de verdade |
|---|---|---|---|---|
| 1 | Fidelidade aos dados | Reprovado | 12 / 27 / 12 | As contas batiam; o texto dizia mais que os dados. A medida não foi cega; os 18 % e os 98 % têm bases diferentes; o "core pior em lance" não foi medido; "sem treino" não era igual para todos |
| 2 | Método e estatística | Reprovado | 7 / 8 / 5 | A régua passou a ser por token, com `silencioso @ m`. Três conjuntos. 8 erros achados no próprio gabarito. **Os 98 % são quase todos de prosa: em lance, a discordância pega de 31 % a 37 %** |
| 3 | Viabilidade contra o código | Reprovado | 8 / 11 / 7 | Saíram o terceiro processo e a pasta `hipoteses/`. A evidência fica fora de `pendentes`. D-3 corrigido: como escrito, apagaria os diagramas. Tesseract de página como candidato |
| 4 | Produto e fluxo | Reprovado | 6 / 10 / 3 | Marcos M1 a M6, três sem gabarito. **Fila Lances, o item central.** F-4 fixa o fluxo. Dec-5 em três níveis, com as horas. Cortes: L-7, X-5, G2-d, injeção, marca fraca |
| 5 | Execução do roadmap | Reprovado | 11 / 13 / 15 | Passo PPT, passo PP1b, ramo e comandos no contrato, ciclos desfeitos, tetos resolvidos antes de M1, teclas conferidas no verificador real, fim do plano e como reverter |
| 6 | Aceitação | **Aprovado com correções** | 4 / 12 / 18 | CA-F4.10 mede se a fila Lances pega erro. Catraca mínima em PP1, porque no caminho padrão ela nunca viria. Números por token no repositório. O relatório abre com o que fazer e diz que o plano não entrega a página perfeita |

**Da revisão 6, não aplicados, por escolha:** os cortes 13 e 18, de aberturas e contextos que ajudam quem chega cego a um passo. A matriz (`experimentos/matriz_dos_documentos.py`) foi repetida no fim: os únicos avisos são falsos, porque a expressão dela não reconhece CA com sufixo `(PPL)`, nem os subitens `L-1a` a `L-1c`.

## O que fica de fora, e o que não foi verificado

- **Nada foi commitado nem enviado.** O repositório é público (Dec-1), e o roadmap põe o commit no passo PP0, com o sim do usuário.
- **Os 8 erros do gabarito não foram corrigidos:** estão em `erros-do-gabarito.md`.
- **Nenhum teste nem código do programa mudou.** O `262d897` segue reprovando em `qualidade.py` por duplicação.
- **As capturas e os `motores*.json` não estão aqui:** têm conteúdo de livro.
- **`por_token_*.py`** recebem a pasta com aquelas saídas como argumento. Foram rodados depois de copiados, sem erro. Refazê-los em outra máquina pede rodar o OCR de novo.
