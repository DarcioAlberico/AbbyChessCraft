# Passo K — Aparência e teclado (§13, §3.4)

O passo foi feito em `passo-i-treino` (`42f8638`, `2c938d5`, e nas pendências o render da
pré-carga num processo, `be40bab` e `8388a7a`). O fechamento pela §16 foi feito em
2026-10-28, no ramo `fechamento-c` (worktree `C:\Python-Chess2\AbbyChessCraft-fechamento`),
sobre o código de hoje e no escopo do passo K, revisado num worktree parado
(`C:\Python-Chess2\AbbyChessCraft-revisao`).

## O que o passo fez

- **Os tokens da aparência** (`app/estilo.py`): o tema claro e o escuro pelo do sistema, sem
  reiniciar (CA-13.3), nenhuma cor literal fora de `estilo.py`; o papel, o Documento e o
  tabuleiro não invertem; o contraste medido (CA-13.2).
- **Os ícones** (Lucide) pintados na cor do tema, os estados vazios com a tecla do perfil.
- **O teclado**: o perfil FineReader, Ferramentas › Teclado… com as trocas pelas regras do
  YAML, lembradas, e todo texto que cita tecla seguindo o perfil e as trocas.
- **O desempenho**: a `QImage` nasce na thread que renderiza; a pré-carga segue o sentido do
  passo; o render da pré-carga num processo à parte (o fitz não segura o GIL da interface).

## Revisões do fechamento

| Rodada | Revisor | Notas | Veredito |
|---|---|---|---|
| Código 1 | código e testes | Correção 6 · Simplicidade 7 · Testes 7 | volta |
| Produto 1 | produto, design e medição | Completude 7 · Fidelidade 4 · Clareza 8 · Produtividade 8 · Design 8 | volta |
| Código 2 | código e testes | 8 · 8 · 8 | aceita |
| Produto 2 | produto, design e medição | 8 · 7 · 8 · 8 · 8 | volta (fidelidade: o JSON no portão) |

**Código 1**: o tema escuro punha a paleta escura sobre o estilo nativo do Windows
(`windowsvista`), e botão, combo e spinbox saíam claros com o texto claro ilegível; o aviso de
conflito e as linhas da busca guardavam a cor do tema de antes no HTML; no FineReader, o
Ctrl+Tab não se reatribuía (a exceção do QTabWidget virava "exceção sem uso").
**Produto 1**: as medidas do K (a troca no cache, quem folheia, a parada da pré-carga) só
estavam no roadmap e nas mensagens de commit, fora do método da §15.3; o `capturas.py` não
tinha a página sem leitura nem a plataforma do Windows, e gravava no registro do usuário; a
Galeria vazia não citava tecla; o diálogo Teclado descartava as trocas ao mudar de perfil.
**Código 2** (aceita): a Galeria vazia e a dica de Esquecer não seguiam a troca de tecla com a
janela aberta; corrigido.
**Produto 2**: só a fidelidade: os números antigos no README, no roadmap e nas pendências
trocados pelos do JSON do portão, e a alta da troca no cache registrada.

Os commits: `8680ed7`, `5ed6d2d`, `b7f9096`, `534147b`, `872df37` e o deste registro.

## Decisões

| Decisão | Por quê |
|---|---|
| O tema põe o estilo Fusion | ele pinta tudo pela paleta; o nativo do Windows pinta parte pelo tema do sistema |
| A cor do HTML guardado pela classe, lida na hora de pintar | o HTML guardado não segue o tema |
| A exceção da tecla que saiu da ação sai junto | todo atalho é reatribuível (§3.4) |
| O Enter e o Shift+Enter da grade da Galeria ficam escritos | são da própria grade, não ações do YAML |
| Quem folheia medido no banco (`test_folhear_paginas_nunca_vistas`) | a parada da interface é o maior vão de um relógio de 1 ms na thread principal |

## Verificação

- Suíte rápida no commit deste registro: ver o portão; ruff limpo.
- CA-13.2 e CA-13.3 em `tests/test_estilo.py` (com o contraste do botão no tema escuro);
  CA-13.1 em `tests/test_acessibilidade.py`; o teclado em `tests/test_teclado.py`.
- As medidas oficiais: o JSON do banco de desempenho do portão.
- As capturas da CA-13.2 (claro e escuro × 1366 e 1920 × com e sem leitura, a janela
  visível) pelo `ferramentas/capturas.py --visivel`; a nota humana da CA-13.2 é do usuário.

## Limitações conhecidas

- **A troca de página no cache ficou mais lenta**: p95 de 18,7 ms em `0888053` (23/10) para
  ~49 ms, dentro da meta de 150 ms. A bisseção (a mesma medida, nesta máquina, em cada
  commit) achou o salto em `2e3d9a1` (o cabeçalho e o rodapé corridos no fim da fila de
  revisão): a fila calcula `gids_fora_do_texto` a cada troca, e a chave do cache das margens
  percorre todos os glifos da página (~30 → ~48 ms); antes dele, a subida foi aos poucos
  (~20 → ~30 ms). Fica para uma pendência: guardar o que a fila tira pela geração da página.

- A tecla se digita como texto no diálogo Teclado, e o conflito só aparece no OK.
- O papel de referência (255) vem do gabarito, não medido da imagem.
- `COR_DA_ZONA["diagrama"]` tem 2,87:1 contra o papel (só reserva no visor).
- As suspeitas do `render.py` (o `Timer` ocioso, o PDF segurado pelo filho até 120 s), não
  reproduzidas.
