# Roadmap: a qualidade do AbbyChessCraft

Plano de execução da `docs/SPEC-qualidade.md` (v0.1, análise de 2026-10-30 sobre o
`4accb7f`). Cada passo cabe numa sessão e traz o contexto para ser feito do zero. Vale o
contrato de todo passo de `plans/abbychesscraft-roadmap.md` (português, UTF-8 sem BOM, LF;
nunca editar o PyBoxEditor; lógica sem Qt em `abbychess/`; `-n` no máximo 4; uma carga
pesada por vez; os passos numa worktree irmã, não na pasta principal).

## Ordem serial

**Q0 → Q1 → Q2 → Q3 → Q4 → Q5 → Q6 → Q7 → Q8 → Q9**

Por que essa ordem:
- **Q0** primeiro porque ajuda todos os outros: o portão volta a passar, as ferramentas e a
  cobertura combinada passam a medir cada passo.
- **Q1–Q3** são os que perdem dado ou escondem o erro que perdeu (severidade Alta).
- **Q4** (a suíte) antes das refatorações, porque elas dependem de testes que pinam o
  comportamento e não quebram por tempo.
- **Q5** (código morto e duplicação) antes de **Q7** (cortes): tirar antes de pôr.
- **Q8–Q9** (CRAP e mutação) por último, porque os cortes do Q7 mudam a maior parte das
  funções que eles listariam.

Paralelos, só em worktrees e com arquivos disjuntos:
- Q3 (exportação) ∥ Q2 (concorrência);
- Q4 ∥ Q3;
- Q9 por módulo ∥ qualquer passo que não toque aquele módulo (mas nunca duas cargas pesadas
  juntas: a mutação é carga pesada).

## O contrato de cada passo daqui

1. **O teste que falha primeiro.** Para cada `CA-Q` do passo, o teste entra num commit
   próprio e reprova no commit de partida **pelo motivo esperado** (registrar a saída). Um
   item "suspeita" cujo teste não falha sai da spec, com a nota.
2. **A menor correção** que faz o teste passar, num commit que diz por quê, o que mudou e
   como foi provado.
3. **Medir no fim:** `crapper.py` e `dryer.py` sobre a cobertura combinada; os números em
   `docs/medidas/qualidade/` com o commit medido.
4. **Verificação de sempre** (a do roadmap principal) e o `ruff --select E,F` limpo.
5. **Registro** em `docs/revisoes/qualidade-QN.md`: cada ação e o motivo, e o que ficou.

## Dependências

| Passo | Spec | Tamanho | Depende de |
|---|---|---|---|
| Q0 Alavancas e portão | §1, §8, §9 (parte) | P | — |
| Q1 Persistência sem perda | Q-P1, Q-P2, Q-P3, Q-P4 | M | Q0 |
| Q2 Nenhum erro some | Q-C1, Q-C4, Q-P7, Q-C2 | M | Q0 |
| Q3 Exportação fiel | Q-E1, Q-E2, Q-E3, Q-E4 | M | Q0 |
| Q4 Suíte confiável | Q-T1, Q-T2, Q-T4, Q-T5 | M | Q0 |
| Q5 Tirar antes de pôr | §11, §7 (Q-D1), Q-A3 | P | Q4 |
| Q6 Fronteira e tipos | Q-P5, Q-P6, Q-P8, Q-P9, Q-C3, Q-C5 | M | Q1 |
| Q7 Cortar os objetos-deus | Q-A1, Q-A2, Q-E5, Q-E6 | G | Q5, Q6 |
| Q8 CRAP < 10 | §8 (CA-Q-X1), Q-T3, Q-T6 | G | Q7 |
| Q9 Mutação | §9 (CA-Q-M1), Q-E7 | G (por módulo) | Q8 |

---

## Passo Q0 — Alavancas e portão

**Contexto.** O portão `ruff --select E,F` reprova desde `a973d3b` (3 F401 em
`abbychess/camada.py:23,28`). As ferramentas da análise (`ferramentas/crapper.py`,
`ferramentas/dryer.py`) foram escritas na análise e estão sem teste. A cobertura que alimenta
o CRAP é só a da suíte rápida, e por isso o servidor, o render e o lote aparecem com CRAP
alto sem que se saiba se a camada `processo` os cobre.

**Fazer.**
1. Tirar os 3 imports de `camada.py`.
2. Um teste para cada ferramenta sobre um pacote de brinquedo em `tmp_path`: o crapper com uma
   função de cc conhecido (contada à mão) e uma cobertura fabricada; o dryer com dois pares
   (um igual, um diferente) e uma aninhada que não pode casar com a mãe.
3. Cobertura combinada: `coverage` com `parallel = true` e `concurrency = multiprocessing`
   (o `processo` usa spawn), `coverage combine`, e um comando no README que gera
   `docs/medidas/qualidade/cobertura-<commit>.json` rodando a rápida e depois a `processo`,
   em série.
4. Reemitir os dois relatórios sobre a cobertura combinada e atualizar a §1 da spec.

**Pronto quando:** o portão passa; as ferramentas têm teste; a §1 da spec traz o CRAP com a
cobertura combinada e diz quantos dos 45 casos de cobertura baixa eram só a camada `processo`.

**Feito** em 2026-10-30, ramo `qualidade-q0` (`docs/revisoes/qualidade-Q0.md`): 16 dos 45
eram só a `processo`; a linha de base combinada é 91,7 % e 286 funções com CRAP ≥ 10.

## Passo Q1 — Persistência sem perda

**Contexto.** `abbychess/projeto.py` lê a v1 pela posição e não pelo pid (Q-P1), deixa o v1
de zonas regravar a página vazia (Q-P2), pode despejar do cache a página aberta (Q-P3) e
grava o mesmo `p<pid>.json` por dois caminhos (Q-P4).

**Fazer**, um CA de cada vez (teste, correção, verificação):
1. **CA-Q-P1.** Decidir antes a §13.1 da spec com o usuário (migrar tudo na abertura ou só
   trocar para pid). Teste em `tests/test_migracao_v3.py`.
2. **CA-Q-P2**, com a falha do `apagar` injetada.
3. **CA-Q-P3**: se o teste não falhar, o item sai da spec; se falhar, `projeto.fixar(pid)`.
4. **CA-Q-P4**: barreira entre o gravador e `salvar_modelo`; 500 repetições em `-m processo`
   ou `noturno`, não na rápida.

**Pronto quando:** os quatro CA passam; `-m processo` e o portão `livro_real` passam; o
comentário de `projeto.py:234` está certo.

**Feito** em 2026-10-30, ramo `qualidade-q1` (`docs/revisoes/qualidade-Q1.md`): os quatro CA
e o comentário. O portão `livro_real` passa em 20 de 21; o que reprova (o índice da busca
pela janela, CA-7.1, 2,5 s para a meta de 2 s × 1,2) reprova igual na base `bc4c6c5`.

## Passo Q2 — Nenhum erro some

**Contexto.** `app/trabalho.py:_fim` deixa a exceção do `pronto` sair sem log (Q-C1); há
`except Exception` cegos em oito lugares (tabela de Q-C4); a página ilegível é tratada de três
jeitos (Q-P7); o lote e o F5 podem gravar a mesma página (Q-C2, suspeita).

**Fazer.**
1. **CA-Q-C1**, com um `pronto` que levanta; `excepthook` em `app/principal.py`.
2. O teste de arquitetura de **CA-Q-C4** (AST: `except Exception` sem `log.exception` nem
   `raise`), com a lista de exceções justificadas; depois um teste por linha da tabela.
3. **CA-Q-P7** com `ler_pagina -> Pagina | PaginaIlegivel`.
4. **CA-Q-C2**: o teste com um F5 lento injetado e o lote na mesma página.

**Pronto quando:** os CA passam e o teste de arquitetura está na suíte rápida.

**Feito** em 2026-10-30, ramo `qualidade-q2` (`docs/revisoes/qualidade-Q2.md`): os quatro CA
e o teste de arquitetura. O CA-Q-P7 mudou (a página ilegível fica guardada e é não
reconhecida, em vez de um estado novo), e o dano do Q-C2 era outro (a leitura do lote
perdida, e não o Ctrl+Z). O portão `livro_real` segue com a falha de tempo do CA-7.1, que
vem da base.

## Passo Q3 — Exportação fiel

**Contexto.** A exportação refaz o texto dos boxes em vez de ler o Documento (Q-E1, a §12.1
diz o contrário); o PDF pesquisável ignora `so_verificadas` (Q-E2); o EPUB troca o anterior
antes de conferir (Q-E3); quatro gravações atômicas próprias fora de `gravacao` (Q-E4).

**Fazer.**
1. **CA-Q-E1**: o golden de uma página com virtual, quebra e lances colados; ver falhar; a
   menor correção (as decisões aplicadas na exportação). Decidir antes a §13.4 com o usuário.
2. **CA-Q-E2** com `_alvo(projeto, indices, opcoes)` comum aos três caminhos.
3. **CA-Q-E3**: o `conferir` no temporário, dentro de `_gravar_zip`.
4. **CA-Q-E4**: `gravacao.gravar_por` e os quatro escritores passando por ele.

**Pronto quando:** os CA passam; `ferramentas/medir_exportacao.py` não piora; o EPUBCheck e o
Ace passam no livro de referência (ABBY_EPUBCHECK, ABBY_ACE).

**Feito** em 2026-10-30, ramo `qualidade-q3` (`docs/revisoes/qualidade-Q3.md`): os quatro CA;
a medida da exportação dá os mesmos bytes que a base nos cinco formatos, o EPUB aprovado no
EPUBCheck, no Ace e no Calibre, e o tempo 2–4 % acima da base medida em seguida (também nos
formatos que o passo não tocou: ruído, sem prova de regressão).

## Passo Q4 — Suíte confiável

**Contexto.** Um teste da janela estoura com `-n 4` porque carrega os modelos globais
(Q-T1); há asserção de relógio e `sleep` como sincronização (Q-T2); a pirâmide da §15.1 não é
imposta (Q-T4); o conftest central não existe de fato (Q-T5).

**Fazer.**
1. **CA-Q-T1**: a fixture autouse que bloqueia `com_modelos_globais`; o teste esperando a
   condição dele; 20 rodadas com `-n 4` (rodar sozinho, sem outra carga).
2. **CA-Q-T2**: o teste de arquitetura contra `time.sleep`/`perf_counter` em asserção; os
   `Event`s nos falsos; um `esperar(cond)` só (ou `qtbot.waitUntil`).
3. **CA-Q-T4**: o marcador `noturno` nas máquinas; o hook dos 60 s; o resumo de pulos.
4. **CA-Q-T5**: o conftest central e as fixtures de sessão (PDF, PNG, projeto reconhecido).

**Pronto quando:** a rápida passa em < 60 s com `-n 4`, sem `from tests.test_`, e 20 vezes
seguidas sem falha.

## Passo Q5 — Tirar antes de pôr

**Contexto.** A §11 da spec lista o código morto; a §7 os 16 pares do dryer; a Q-A3 as
decisões em dois lugares do controlador.

**Fazer.**
1. Apagar cada item morto confirmado por `git grep`, um commit por item (CA-Q-Z1).
2. Os pares do dryer marcados com destino, um por commit, cada um com o teste que pina o
   comportamento antes; os "rever" vão para a lista de exceções com motivo ou se fundem.
   Decidir antes a §13.2 (as faixas de páginas).
3. Q-A3: um flag de lote, um modo da fila, a duração das mensagens numa constante.

**Pronto quando:** `dryer.py abbychess 0.8` só lista as exceções aceitas; o teste de
arquitetura de CA-Q-D1 está na rápida.

## Passo Q6 — Fronteira e tipos

**Contexto.** O `projeto.json` é validado pela metade (Q-P6); a sequência grava ao ser lida
(Q-P8); estados e notação são strings soltas, e há duas fontes da verdade para a sequência e o
próximo pid (Q-P9); dois processos podem abrir o mesmo projeto (Q-P5); o servidor usa a rede
fora da trava (Q-C3); as corridas menores de Q-C5.

**Fazer**, um CA por vez: CA-Q-P6 (parametrizado ou hypothesis), CA-Q-P8, CA-Q-P9 (`StrEnum`),
CA-Q-P5 (decidir antes a §13.3), CA-Q-C3, e um teste para cada corrida de Q-C5.

**Pronto quando:** os CA passam; abrir um projeto estragado nunca grava nada.

## Passo Q7 — Cortar os objetos-deus

**Contexto.** `ControladorDePagina` (138 métodos), `ProjetoDeLivro` (~1 640 linhas),
`exportar.py` (~2 000 linhas) e a `JanelaPrincipal` com 9 mixins (Q-A1); o app decide regra
de negócio e o pipeline "depois de ler" está em quatro lugares (Q-A2); a exportação repete
regras do resto (Q-E5, Q-E6).

**Fazer**, um corte por sessão, na ordem que menos mexe no resto:
1. `aplicar_lida` pura, usada pelo F5 e pelo lote (CA-Q-A2, parte 2).
2. `EstadoDaJanela` sem Qt e `acoes.atualizar` só aplicando (CA-Q-A2, parte 1).
3. `ControladorDePagina`: `Navegador`, `ControladorDaSequencia`, `PonteDeLeitura`,
   `AplicadorDoHistorico`, `ControladorDaSessao`, a fila para o `ControladorDaFila`.
4. `ProjetoDeLivro`: `CacheDePaginas`, `ResumoDoLivro`, `Migracoes`, `Fonte`.
5. A exportação: `Pedido`, o adaptador do Documento, `exportar.py` partido (Q-E6), e as
   regras únicas de Q-E5.

Cada corte: pinar o comportamento (os testes de comportamento existentes, mais o que faltar),
mudar a estrutura, provar que nada mudou (a mesma suíte, o mesmo golden de exportação, a
mesma medida da fatia).

**Pronto quando:** CA-Q-A1 (nenhum arquivo > 1 000 linhas, nenhuma classe > 40 métodos) e
CA-14.1 da spec principal passam.

## Passo Q8 — CRAP abaixo de 10

**Contexto.** Depois do Q7, o que sobrar acima de 10 no crapper com a cobertura combinada.
Também os testes de implementação (Q-T3) e as propriedades que faltam (Q-T6).

**Fazer.** Para cada função: se a cobertura < 50 %, testar primeiro pelo comportamento; se o
cc ≥ 10, partir (e só partir um despacho se a tabela ficar mais clara). Q-T3: trocar os testes
que montam estado privado por API pública. Q-T6: as máquinas de estado que faltam.

**Pronto quando:** CA-Q-X1 passa e a lista de exceções tem motivo em cada linha.

## Passo Q9 — Mutação

**Contexto.** Nenhum teste de mutação até aqui. `cosmic-ray` roda no Windows; o `mutmut` 3
não. Também o acoplamento com privados do core (Q-E7).

**Fazer**, um módulo por sessão (`modelo`, `texto`, `lances`, `sequencia`, `historico`,
`sessao`, `zonas`, `busca`), sozinho na máquina, só os testes que importam o módulo, `-n` ≤ 4:
cobrir o não coberto, matar os sobreviventes, apagar o código morto que eles revelarem. Q-E7:
os testes de contrato contra o core e os pedidos em `docs/pedidos-ao-pyboxeditor.md`.

**Pronto quando:** CA-Q-M1 (≥ 85 % de mutantes mortos por módulo puro) e CA-Q-E7.

## Antipadrões

- Corrigir sem o teste que falhou antes (e sem registrar por que falhou).
- Um guarda que só esconde o erro (`if x is None: return`) no lugar da causa.
- Refatorar e mudar comportamento no mesmo commit.
- Rodar a mutação, a suíte e uma medida ao mesmo tempo.
- Juntar passos numa sessão para "aproveitar": cada passo fecha medido antes do próximo.
