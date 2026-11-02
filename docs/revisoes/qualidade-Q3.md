# Passo Q3 — exportação fiel (2026-10-30, ramo `qualidade-q3`)

Quarto passo de `plans/roadmap-qualidade.md`, a partir do `17bd359` (o Q2 mesclado), na
worktree irmã `C:\Python-Chess2\AbbyChessCraft-qualidade`. A decisão §13.4 da spec foi do
usuário: só as decisões agora; o Documento inteiro (Q-E6) no Q7.

## O que foi feito

| CA | Teste (reprovava assim) | Correção |
|---|---|---|
| Q-E1 | `ba96dbb`: a linha "o cavlo vai a f6 maisum ♘f62.c4 fim", com o virtual, a quebra e os lances colados, saía assim; o Documento a lê "o cavalo vai a f6 mais um ♘f6 2.c4 fim" | `ba28f64`: a `Estrutura` leva as palavras do Documento, e cada linha exportada sai com elas (`_pelo_documento`) |
| Q-E1, a regressão | `1399a8c`: a medida achou "ca o" junto ("cao") na fatia; o teste com um glifo não lido no meio da palavra reprovava | `6a9d483`: as palavras do texto do Documento, sem os não lidos (`linhas_dos_gids(com_os_nao_lidos=False)`) |
| Q-E2 | `7408d5b`: sem nenhuma verificada, o PDF saía com as três páginas | `03b6f03`: `_alvo` para as páginas do projeto, o PGN e o PDF |
| Q-E3, Q-E4 | `b93bb89`: o EPUB recusado já tinha trocado o bom; nenhum dos quatro escritores tentava de novo na troca presa | `586d81f`: `gravacao.gravar_por` (temporário único, conferir antes, nova tentativa, nada sobra) nos quatro; o EPUB conferido antes de trocar |
| — | a medida no `6a9d483` achou um par novo de duplicação, deste passo (o DOCX e o EPUB) | `ee5e059`: `_escrever_formatado` |

## Verificação

- Suíte rápida com `-n 4`: 1870 passaram, 3 pularam.
- `ferramentas/medir_exportacao.py --livro xv`, com o EPUBCheck, o Ace e o Calibre, no
  `6a9d483` (`docs/medidas/2026-10-30-exportacao-xv.json`; o `ee5e059` depois dele só junta os
  dois adaptadores, coberto pelos goldens e pela reprodutibilidade da suíte): o EPUB aprovado
  nos três, os cinco formatos com os mesmos bytes em duas exportações, e os mesmos bytes que a
  base `17bd359` medida logo depois, formato a formato. O p50 ficou 2–4 % acima do da base
  (EPUB 1522 × 1485 ms, DOCX 1601 × 1574, TXT 1135 × 1098, PDF 3065 × 2958, PGN 8,3 × 7,6),
  também no PGN e no PDF, cujo caminho o passo quase não toca, e o Q3 rodou primeiro: ruído e
  deriva da máquina, sem prova de regressão.
- `ferramentas/qualidade.py` no `ee5e059` (árvore limpa,
  `docs/medidas/qualidade/2026-10-30-qualidade-224043.json`): a rápida e a `processo` (35)
  passam; cobertura combinada 91,9 % (91,8 % no Q2); 285 funções com CRAP ≥ 10 (285); 16 pares
  do dryer (16).
- Portão `ABBY_PORTAO=1 pytest -m livro_real` no `ee5e059`, com os validadores, sozinho na
  máquina: 20 passaram, 1 reprovou (`docs/medidas/2026-10-30-medida-falhou-225038.json`), o
  mesmo do Q1 e do Q2: o índice da busca pela janela (CA-7.1), 2580 ms, dentro do que a base
  deu hoje (2548–2894 ms). O passo não toca a busca.
- O ruff do portão passa.

## Registro

| Ação | Por quê |
|---|---|
| Perguntar a §13.4 antes do CA-Q-E1 | o roadmap pede, e a resposta muda o tamanho do passo |
| As palavras do Documento pela `Estrutura`, e não `texto.montar` | é a decisão do usuário: o resto da exportação (as margens, as coordenadas, os parágrafos) fica para o Q7 |
| Comparar o TXT da fatia com o da base, palavra a palavra, num projeto lido uma vez | a medida mostrou 40 bytes a menos; só a comparação mostrava onde |
| O teste da regressão antes da correção | a suíte não pegava: o caso (o glifo não lido no meio da palavra) não estava em teste nenhum |
| O EPUB que não passa na conferência é recusado | é o que o DOCX já fazia; o `problemas_do_arquivo` ficaria sempre vazio e saiu |
| A falha injetada só no arquivo exportado | o PDF grava antes um arquivo do projeto pela mesma gravação |
| Medir a exportação na base logo depois do Q3 | para comparar o tempo na mesma hora da máquina; o JSON da base, na pasta principal, foi apagado |
| A duplicação que o passo criou saiu antes de fechar | a medida a achou (17 pares) |

## O que ficou

- O índice da busca pela janela (CA-7.1) passa da meta também na base.
- A exportação ainda refaz as linhas e os parágrafos pela geometria; só as palavras vêm do
  Documento. O resto é o Q-E6, no Q7.
