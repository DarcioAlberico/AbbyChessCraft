# Crítica 5 de 6: o roadmap se executa?

Sobre `plans/roadmap-pagina-perfeita.md` e `docs/SPEC-pagina-perfeita.md`, ramo `checkup-geral`, `262d897`. Sem editar o repositório, sem pytest, sem OCR. Rodei só grep e scripts leves; simulei as teclas com uma cópia do `atalhos.yaml` contra o `abbychess.atalhos.verificar` real.

## 0. Veredito

**Não se executa como está.** PP0 e PP1 quase andam. PPL pede coisas que só nascem em M4 e M5, e o M3 não tem passo. A reorganização em marcos mudou a ordem da tabela sem mudar as dependências: o texto "nenhum marco depende do seguinte" é falso em 5 pontos.

| | Achados |
|---|---|
| **Bloqueante** | B1 a B11 |
| **Importante** | I1 a I13 |
| **Menor** | M1 a M15 |

Todas as correções cabem no texto, sem item novo de produto. O que corto está na §6.

---

## 1. Simulação fria: a primeira tarefa de cada um

| Passo | Primeira tarefa que escrevi | Onde parei |
|---|---|---|
| **PP0** | "Juntar `exportar` e `exportar_as_selecionadas`" | Em qual ramo? `lacunas-da-spec` e `checkup-geral` estão no mesmo commit, e o roadmap, a spec e a evidência **nem estão em git**. O par está em `janela.py:416` × `paginas_na_janela.py:104`, e isso só se lê num `.txt` não rastreado. `_cinza` tem **4** definições (`controlador.py:204`, `coordenadas.py:177`, `diagramas.py:596`, `padroes.py:152`); o texto fala em 2 e não diz o destino. Comando de `qualidade.py` e do portão: no README, não no plano. Mesclar onde, e pode dar push? |
| **PP1** | "C-2: `app.log` e `leitura.log`, com `faulthandler`" | Esta anda: CA claro, `principal.py:43` citado. Trava depois: C-5 não tem limite, Dec-7 não aparece no passo, e D-3 e C-1 estão na lista e fora do marco |
| **PPL** | "`classificar_token` e `letras_das_pecas`" | Em que módulo? Onde fica a tabela de 60? Como o usuário preenche `letras_das_pecas`? O item 2 já pede `alinhar` (PP2), uma leitura do programa que não está no repositório e a sincronia que o item 5 só escreve se o item 2 passar |
| **M3** | Não há tarefa | **Não há passo.** Só a linha da tabela, uma frase em T1 e uma em PP3 |
| **PP5** | "L-3 só com a ferramenta" | `medir_motores` não tem varrimento pedido em PP2. Sem `Pronto quando`. "Precisa de E-6 (T3)", e T3 põe E-6 por último. "A-2, se ainda não feito": 230 acessos, sem recorte. CA-F1.2 é "na prova", que não existe no Dec-5 recomendado |

### Campos por passo (por script)

| Passo | Contexto | Fazer | CA | Risco | Pronto | Custo | Carga | Parada |
|---|---|---|---|---|---|---|---|---|
| PP0 | sim | sim | **não** | **não** | sim | sim | sim | n/a |
| PPL | sim | sim | sim | sim | **não** | sim | sim | sim |
| PP1 | sim | sim | sim | sim | sim | sim | sim | n/a |
| PP2 | sim | sim | sim | **não** | **não** | sim | sim | sim |
| PP2b | sim | sim | n/a | **não** | **não** | sim | sim | só na tabela |
| PP2c | sim | sim | n/a | **não** | **não** | sim | sim | só na tabela |
| PP2d | sim | sim | **não** (CA-A3, CA-A6) | **não** | sim | sim | **não** | n/a |
| PP3 | sim | sim | sim | sim | **não** | sim | sim | n/a |
| PP4 | sim | sim | sim | **não** | **não** | sim | **não** | só na tabela |
| PP5 | sim | sim | sim | sim | **não** | sim | sim | sim |
| PP6, PP8, PP9 | não | sim | sim | não | não | PP9 não | não | n/a |
| PP7 | sim | sim | sim | sim | não | sim | não | sim |
| T1 | não | sim | **não** | não | não | não | não | n/a |
| T2, T3, T4 | um parágrafo cada; sem marco, sem CA, sem custo, sem carga |||||||
| **M3** | **sem passo** |||||||

### Matriz de CA e de itens (por script, 111 CA na spec)

- **Fantasmas:** nenhum. Todo CA citado no roadmap existe.
- **Órfãos reais, sem passo nem trilha:** CA-L9.1 a CA-L9.4, CA-F2.1 a CA-F2.3 (M3). Sem CA citado, só o item numa trilha: CA-U1 a CA-U14 (T1); CA-C3, C4, C6, C7, C8 (T2); CA-E1, E2, E4, E6 (T3); CA-A1 a CA-A6 (T4).
- **Duplicados:** CA-R1.6 em PPL e em PP2 (`CA-R1.*`). CA-E5 em PP2 e em T3 (E-5). E-6 em PP5 e em T3. A-2 em PP5 e T4. A-3 e A-6 em PP2d e T4.
- **No passo errado:** CA-X1.3 em PPL pede um JSON que só nasce em PP2. CA-F4.6 em PP5 descreve o realce de M3. CA-F4.7 em PPL testa duas linhas de Dúvidas, que nascem em PP5. CA-X1.4 e CA-X1.5 em PP7 (opcional) protegem o que PPL liga (B4).
- **Item sem dono:** D-3 e C-1 (dizem "logo depois de M2"; nenhum passo). Dec-4: nenhum passo a pergunta, e ela pede "o número de A-5", que só existe "ao tocar". Dec-7: só na tabela de marcos. E-3 fica com Dec-1 e L-7 está fora do plano: aceitáveis.
- **Comportamento da spec sem CA:** a pergunta do Ctrl+T (spec:468), as contagens do relatório na exportação (spec:474), `importar-do-projeto` e a grade da dupla leitura (spec:203).

---

## 2. O grafo real

O que cada passo pede de verdade (→ "precisa de"). Em negrito, o que contraria a ordem escrita.

```
PP0  → docs em git, regra de ramo
T1.1 (U-1, U-4) → **A-3** (EspacoDeTrabalho 53/53)
PP1.D-5 → Dec-7
PPL.classificar → letras_das_pecas
PPL.PP2b → **alinhar, normalizar (PP2)**, **leitura do programa (fora do repo)**,
           **sincronia de X-1** ← X-1 → PP2b                         CICLO
PPL.F-3  → **EvidenciaDaPagina e "fortes" (PP5)**, **A-3, documento.py (PP2d)**
PPL.X-1  → **rebobinar e variantes (PP7, opcional)**, **CA-X1.3: JSON de medir_motores (PP2)**
PPL.F-4  → D-5 com Dec-7 a; **contagem de lances no resumo (ninguém)**;
           **cc de ControladorDaFila.andar (9)**; registro por página (ninguém)
M3.U-3   → contagem de lances no resumo (ninguém)
M3.F-2   → A-3, documento.py; "fortes"
PP2      → PPL.classificar; **CA-E5 → lock (E-1) → CA-R3.1 (PP2)**   CICLO
PP5      → PP2, PP2c, PP4, E-6; **E-1, E-2, E-4, E-5 pela ordem de T3**
Dec-4    → A-5 (sem passo)
```

**Ciclos:** dois, PP2b ↔ X-1 e CA-E5 ↔ CA-E1. **Marco que depende de marco seguinte:** M2 → M4 (`alinhar`, JSON), M2 → M5 (`EvidenciaDaPagina`), M2 → M6 (variantes), M1 e M2 → PP2d (listado em M5), PP2 → T3.

**Conferidos e sem problema:** X-3 só pede Ctrl+W e Ctrl+B (passam no verificador). F-2 sem F-4 completo funciona, desde que `fortes` exista (B5). PP2 depende de `classificar_token` de PPL e isso vale, se os dois módulos forem um só. D-5 antes de PPL está certo pela tabela e errado pela ordem do documento (PPL vem antes de PP1 no arquivo).

**Caminho crítico:** PP0 → PP2d → PP1 → PPL → *20 páginas do usuário* → M3 → *Dec-5* → PP2 → *~10 h e 7 dias* → PP2b → PP2c → PP4 → PP5 → *uso e 7 dias da R-4* → fim de M5. O teto não é sessão de agente: são duas esperas de 7 dias e as ~12 h dela.

---

## 3. Custo

**"Sessão" não está definida, e o histórico mostra que o tamanho varia 100 vezes.**

| Passo | Commits | Relógio entre os commits | Linhas em `abbychess`, `tests`, `ferramentas` |
|---|---|---|---|
| Q0 | 5 | 16 min | 265+ |
| Q1, 4 CA | 9 | 46 min | 341+ |
| Q2, 4 CA | 12 | 2 h | 453+ |
| Q3, 4 CA | 10 | 1 h 07 | 317+ |
| Q4, 4 CA | 10 | 1 h 13 | 1.219+ |
| Q5 | 17 | 1 h 23 | 362+ |
| Q6, 6 CA | 22 | 44 min | 821+ |
| Q7, cortes | 43 | **12 h 26** | 7.535+ |
| Q8, CRAP | 163 | **13 h 38** | 14.048+ |
| Q9, mutação | 39 | **~44 h, com 2 resets** | 2.383+ |
| `lacunas-da-spec`, 5 itens de interface | 13 | 31 min | 573+ |
| PR #12, CA-5.2 e mais | 7 | | 1.427+ |
| PRs #13 a #18 e #20 | 2 a 3 cada | | ~110 cada |

**Regra que sai disso:** cerca de **4 CA por sessão**, 1 a 2 h, 300 a 800 linhas, em código novo. O que mexe em muitos arquivos por motivo de estrutura (Q7, Q8) custa 10 vezes mais.

| Marco | Plano | CA + trabalho sem CA | Minha conta |
|---|---|---|---|
| M1 | 5 | 10 CA; C-5 aberto; A-3 agora aqui | **6** |
| M2 | 6 a 7 | 12 CA, mais resumo, registro, F4, relatório, Ctrl+T | **7 a 9** |
| M3 | 3 a 4 | 11 CA | **3 a 4** |
| M4 | 3 | **18 CA** em PP2, mais grade, importar, G2, PP2b | **5 a 6** |
| M5 | 8 a 10 | PP5 sozinho tem **19 CA**, não "3 a 4" | **10 a 13** |
| **M1 a M5** | **25 a 29** | | **31 a 38** |
| PP1b (D-3, C-1) | sem número | D-3 é "o mais difícil" | 2 |
| T1 blocos 3 e 4, T2, T3 | sem número | | 8 a 11 |
| **Ordem de grandeza** | | | **40 a 50 sessões, uns 60 a 100 h de agente; mais 12 a 14 h dela e dois intervalos de 7 dias. Em calendário: de 4 a 8 semanas** |
| M6 | "conforme o pedido" | PP6 1, PP7 4 a 6, PP8 3, PP9 1 | 9 a 11, fora da conta |

**A máquina.** As medidas não são demais; a RAM é o limite. Cabem ~10 portões no plano (16,5 min cada, 2 h 45 no total), um por marco e um por passo que muda leitura. O problema é outro: **o último portão passou com 5,49 GB livres, mas um anterior, em série, foi parado pelo vigia em 0,74 GB**, e o vigia que o protege (`portao_por_arquivo.py`) está no scratchpad desta sessão, fora do repositório. Ver I5.

---

## 4. Bloqueantes

### B1. O plano não está em git, e nenhum passo diz em que ramo trabalhar

**Onde.** Roadmap, cabeçalho, "O contrato de cada passo", PP0.

**Problema.** Quem abre uma worktree nova não tem spec, roadmap nem evidência. O contrato diz "Worktree própria", sem nome, sem base, sem como mesclar. O contrato de origem (português, LF, nunca editar o PyBoxEditor, lógica sem Qt) não foi copiado para "esta lista", e o `-n auto` do README contradiz o `-n 4`.

**Prova.** `git status`: `?? docs/SPEC-pagina-perfeita.md`, `?? plans/roadmap-pagina-perfeita.md`, `?? docs/pesquisa/checkup-2026-11/`, `?? docs/medidas/2026-11-05-*`. `git log main -1` = `867e60d`, enquanto `origin/main` = `passo-i-treino` = `7fcc454`: partir do `main` local perde 41 commits. README:35 `-n auto`. A autorização de push e merge do usuário valeu para um pedido só.

**Correção, no contrato, antes do item 1:**

> **0. Onde.** Integração: `passo-i-treino`, igual a `origin/main`. **O `main` local está atrasado: não partir dele.** Uma worktree só, reaproveitada: `git worktree add ..\AbbyChessCraft-pp -b pp-<id> passo-i-treino`. O venv é o da pasta principal, e tudo roda da raiz da worktree, com `PYTHONPATH` nela:
> ```
> $env:PYTHONPATH = (Get-Location).Path; $py = "C:\Python-Chess2\AbbyChessCraft\.venv\Scripts\python.exe"
> & $py -m pytest -q -n 4                         # a rápida, nunca -n auto
> & $py ferramentas\qualidade.py                  # rápida, processo, CRAP e duplicação: ~6 min
> & $py ferramentas\portao.py                     # livro_real e desempenho, arquivo por arquivo, com o vigia: ~17 min
> ```
> Vale o contrato de `plans/abbychesscraft-roadmap.md`: português, UTF-8 sem BOM, LF, nunca editar o PyBoxEditor, lógica sem Qt em `abbychess/`. Merge em `passo-i-treino` com `--no-ff`, depois de ler a suíte. **Push e PR para `main` só com o sim do usuário, pedido ao fim de cada marco.**

**Correção, em PP0, no lugar de "Fazer":**

> 0. **Versionar o plano:** spec, roadmap, `docs/pesquisa/checkup-2026-11*`, as medidas de 05/11 e os dois `.txt` de qualidade, num commit local em `lacunas-da-spec`. Antes, conferir que nenhum desses arquivos traz trecho de livro além de palavras soltas; **sem push até Dec-1.**
> 0b. Versionar o vigia como `ferramentas/portao.py` (hoje `portao_por_arquivo.py`, no scratchpad da sessão de 05/11) e os 8 erros do gabarito (B7). Trocar `-n auto` por `-n 4` no README.
> 1. `janela.py:416 exportar` e `paginas_na_janela.py:104 exportar_as_selecionadas` numa função. `_cinza` de `coordenadas.py` e `diagramas.py` em `abbychess/geometria.py`; `controlador.py:204` é método de outra coisa, e o de `padroes.py:152` só entra se for igual.
> 2. `qualidade.py`, sozinho; depois o portão, sozinho.
> 3. Dec-1 e Dec-6 ao usuário.
> 4. Merge em `passo-i-treino`. **Com Dec-6 b, os passos seguintes partem de `lacunas-da-spec` do mesmo jeito:** as citações `arquivo:linha` e os tetos são desse commit. Dec-6 b só adia o push.
>
> **CA:** a medida não acusa par fora da lista. **Risco:** nenhum de dado; o par 0,88 é do fluxo de exportação, e o golden o vigia.

### B2. O marco M3 não tem passo

**Onde.** Roadmap:11. Matriz: CA-L9.*, CA-F2.* órfãos.

**Problema.** Sem contexto, ordem, CA, risco, pronto ou carga. É o único marco nessa situação.

**Correção:** acrescentar, depois de PPL (e mover PPL para depois de PP1, na ordem PP0, PP2d, PP1, T1 bloco 1, PPL, PP1b, PPT, PP2…):

> ## Passo PPT — A tela mostra o que importa (M3)
>
> **Contexto.** A 1366 px, a linha impressa quebra e a Imagem abre em 22 %. O realce satura. A capa do Seirawan inventa 1.442 linhas. Nada aqui usa 2.ª opinião.
>
> **Fazer, um commit vermelho e um verde por item, nesta ordem:**
> 1. **U-13 e U-14:** `app/documento.py`, `app/visor.py`.
> 2. **F-2,** com `fortes` = □ e palavra desmentida, mais os ilegais de PPL, por cima do realce de hoje.
> 3. **U-3:** usa `lances_por_conferir` do resumo (PPL). **U-10.**
> 4. **L-9,** por último: é o único item de M1 a M3 que muda o que se lê. `abbychess/tipo_de_pagina.py`, `servidor_de_leitura.ler_pagina`, `arrumacao.aplicar_lida`, a exportação e o filtro da gaveta.
>
> **CA:** CA-U13, CA-U14, CA-F2.*, CA-F4.6, CA-U3, CA-U10, CA-L9.*.
>
> **Risco:** L-9 pode esconder página de texto: o fim do lote lista, e Ctrl+Shift+T desfaz. `tests/verdade/xv/i000.json` é a capa e tem blocos: em CA-L9.2, "gabarito de texto" é página com pelo menos uma linha rotulada.
>
> **Pronto quando:** os CA passam; a capa lê em menos de 5 s; o golden muda só com motivo escrito.
>
> **Custo:** 3 a 4 sessões. **Carga:** suíte rápida; portão no fim, por L-9. CA-F2.3 e CA-U13 pedem capturas, uma vez.

### B3. Os tetos reprovam o primeiro método novo, e PP2d está no marco errado

**Onde.** Roadmap:11 ("PP2d só se um teto impedir"), roadmap:13 (PP2d em M5), PP2d.

**Problema.** Não é "se": **as cinco classes com teto estão exatamente no teto**, e a suíte rápida reprova com um método a mais. M1 e M2 vêm antes de PP2d. A folga em `documento.py` é de 6 linhas pela conta do teste, e não 8. Dois limites que o plano não cita: `sessao.py` e o cc.

**Prova.** `tests/test_tamanho_dos_modulos.py`, medido com o mesmo `ast`:

| Classe ou arquivo | Hoje | Teto | Quem precisa |
|---|---|---|---|
| `VistaDoDocumento` | 58 | 58 | F-3, F-2, U-13 |
| `EspacoDeTrabalho` | 53 | 53 | U-1, U-4 (M1) |
| `VisorDePagina` | 55 | 55 | U-14 |
| `ControladorDePagina` | 61 | 61 | F-4 |
| `ProjetoDeLivro` | 43 | 43 | D-1 |
| `app/documento.py` | **994** (`splitlines`; `wc` dá 992) | 1.000 | F-3, F-2, U-13 |
| `pagina.py` | 1.000 | 1.000 | L-1b (PP4) |
| `sessao.py` | 993 | 1.000 | `letras_das_pecas` |
| `janela.py` | 498 | < 500 | U-4 |
| `ControladorDaFila.andar` | **cc 9** | cc < 10; lista de aceitos cheia, 9/9 | um ramo para `lances` reprova |
| `VistaDoDocumento._formato_do_glifo` | **cc 9** | idem | "um estado novo de desenho" reprova |

**Correção.** Trocar a linha de M3 por `L-9, F-2 com os sinais de hoje, U-3, U-10, U-13, U-14`; tirar PP2d de M5; em M1, escrever `PP0, PP2d, PP1 (sem D-3 e C-1), T1 bloco 1` e 6 sessões. Reescrever PP2d, **antes de PP1**:

> ## Passo PP2d — Abrir espaço (M1)
>
> **Contexto.** As cinco classes da lista de tetos estão no limite, e `documento.py` tem 6 linhas de folga. Sem isto, o primeiro método de M1 reprova a rápida.
>
> **Fazer, mecânico, um commit por item, com o golden como pino:**
> 1. **A-3:** a régua nova em `tests/test_tamanho_dos_modulos.py` e `tests/test_arquitetura.py`, sem mover método.
> 2. `app/documento.py`: `_escrever_as_linhas` e `_formato_novo` vão a `app/formatos_do_documento.py`.
>
> **CA:** CA-A3. **Pronto quando:** golden e suíte iguais, e `VistaDoDocumento` aceita método novo. **Custo:** 1 sessão. **Carga:** portão uma vez, no fim. **Risco:** nenhum de dado.

E, em PP4, como item 0:

> 0. `pagina.py`: `FonteDePaginas`, `CacheDePaginas` e geometria vão a `fonte_de_paginas.py`, com reexportação. Os `monkeypatch` em `pg.*` dos itens movidos passam ao módulo novo no mesmo commit. L-1b precisa disso.

Em PPL e em PPT, uma frase: "`ControladorDaFila.andar` e `_formato_do_glifo` estão em cc 9: modo e estado novos entram por tabela, sem `if`." A-6 sai de PP2d: ver §6.

### B4. PP2b e X-1 formam um ciclo, e a legalidade de M2 não tem definição de "linha principal"

**Onde.** Roadmap:82-85, 145; PP7; spec:495-498, 506-507.

**Problema.** Três coisas juntas.
1. PP2b (item 2 de PPL) mede o teto "com a sincronia de X-1 (sementes, âncoras, **rebobinar, variantes**)". X-1 é o item 5, e só existe se PP2b passar. Rebobinar e variantes só existem em PP7.
2. "X-1 só na linha principal" não diz o que fazer quando o texto sai dela, e a spec diz que **"metade do texto destes livros são alternativas sem parêntese"**. Sem regra, cada alternativa vira lance ilegal marcado.
3. CA-X1.4 e CA-X1.5, os testes dessa marca falsa, estão em PP7, que é opcional.

**Prova.** Roadmap:145, 233; spec:496, 506-507.

**Correção, em spec:496, ao fim do item 2:**

> **Sem rebobinar (M2):** a posição só anda enquanto o número for o esperado. Número que volta, `(`, `;`, ou lance de lado errado: a posição se perde, e tudo fica `sem posição`, sem marca, até o próximo diagrama. **Nunca se marca lance sem posição.** PP7 troca essa perda pela rebobinada.

**Em PP2b, item 1:**

> **Teto de cobertura:** `ferramentas/medir_sincronia.py` sobre o **texto do gabarito**, em duas versões: **sem rebobinar**, que é a de M2 e decide o ponto de parada de PPL, e **com rebobinar**, que só existe na ferramenta e decide PP7. Cada uma por página e, em 20 páginas seguidas de um livro, por seguimento.

**Em PPL:** acrescentar CA-X1.4 e a primeira metade de CA-X1.5 ("não gera marca falsa"). **Em PP7:** "CA-X1.5, a segunda metade: o lance 13 fica com posição". O código da sincronia nasce antes do ponto de parada: ver B5, itens 3 e 4.

### B5. PPL usa o que nasce em M4 e M5

**Onde.** Roadmap:80-88.

**Problema.** Viola "nenhum marco depende do seguinte".

**Prova.**

| PPL pede | Nasce em | Conferido |
|---|---|---|
| `alinhar`, `normalizar` (o alarme da legalidade compara leitura e gabarito) | PP2, item 1 | grep: `classificar_token`, `EvidenciaDaPagina`, `fortes` não existem em `abbychess/` nem `ferramentas/` |
| `EvidenciaDaPagina`, `fortes` (spec:412, 499) | PP5, item 3 | idem |
| "O JSON" de CA-X1.3 | `medir_motores`, PP2 | |
| Gabarito sem os 8 erros (PP2b roda sobre ele) | PP2, item 0 | Dec-5 A diz que ela corrige, sem passo |
| Leitura do programa em JSON | os `motores*.json` têm texto de livro e estão fora do repositório | checkup:13. "**Carga: nenhuma**", em PP2b, é falso |
| `lances_por_conferir` por página, para "410 lances", F4 no escopo livro e U-3 | ninguém | `resumo_do_livro.do_modelo` só conta `pendentes` e `confirmados`; `proxima_com_pendentes` idem |
| Onde o usuário declara `letras_das_pecas` | ninguém | `app/opcoes.py:53` só tem `campo_notacao` |

E o risco que o próprio passo chama de maior, o editor Palavra numa linha, é avaliado por último.

**Correção: "Fazer" de PPL inteiro:**

> **Fazer, nesta ordem, um commit vermelho e um verde por item:**
> 0. **Viabilidade, meia hora, sem commit:** abrir uma linha em `PainelDeVerificacao` com `vf.Desconhecida(palavra=<linha>, indices=<índices dela>, motivo="lance")`, e corrigir por `ControladorDeVerificacao.corrigir`. Se não servir, avisar o usuário: é uma sessão a mais.
> 1. `abbychess/tokens.py`, sem Qt: `normalizar`, `alinhar` e `classificar_token`, com a tabela de 60 em `tests/dados/tokens_rotulados.yaml` (CA-R1.6). `Projeto.letras_das_pecas`, com o campo nas Opções, abaixo de Notação.
> 2. Os 8 erros do Seirawan (`docs/revisoes/checkup-2026-11/erros-do-gabarito.md`, 15 min dela), com `verdade_versao` subindo.
> 3. `abbychess/decodificador_de_lances.py`: sementes e sincronia sem rebobinar, sem interface.
> 4. **PP2b sobre o gabarito que já há:** `ferramentas/medir_sincronia.py`. Teto de cobertura e alarme, na linha principal. **Carga: uma leitura das 7 páginas do Seirawan e das 4 do `corpus_v2`.** Ponto de parada.
> 5. **F-3,** com `abbychess/evidencia.py`: `EvidenciaDaPagina` só com `{gid: (motivo, sugestão)}` e os `fortes`; PP5 acrescenta os escores.
> 6. **X-3.**
> 7. **X-1 sem hipóteses,** se o item 4 passou: tarefa leve de 500 ms, e a marca de ilegal.
> 8. **Registro por página** (B8).
> 9. **F-4:** a fila Lances (I2), o F4, o relatório de lances, a pergunta do Ctrl+T, `lances_por_conferir` no resumo.
>
> **CA:** CA-R1.6, CA-F3.*, CA-X3.*, CA-X1.2, CA-X1.4, CA-X1.5 (a primeira metade), CA-X1.6, CA-F4.1, CA-F4.2, CA-F4.7a, CA-F4.8, CA-F4.9.

**CA-X1.3:** "A cobertura sai no JSON de `medir_sincronia`, por livro; em PP2, também no de `medir_motores`."

**Em PP2:** item 0 sai, salvo "rodar a mesma auditoria no `corpus_v2`"; item 1 vira "`tokens.py` vem de PPL". **CA de PP2:** CA-R1.1 a CA-R1.5, CA-R1.7, CA-R2.*, CA-R3.*.

**CA novo, para o que a spec já pede (spec:468):**

> **CA-F4.9.** Ctrl+T numa página com 3 glifos da fila ativa e 12 lances não conferidos pergunta com esses dois números, e Esc não marca.

### B6. "Página com evidência" muda F6 e a fila em M2, sem querer

**Onde.** Spec:421, 470, 499; roadmap:16.

**Problema.** X-1 grava em `EvidenciaDaPagina`, e F-3 também. A partir de M2, toda página tem evidência. Pelo texto, ela abre em **Dúvidas, que só existe em PP5**, e o F6, a gaveta e os contadores passam a contar "só as fortes": a fila de hoje some da contagem. Tudo isso contraria "M1 a M3 só acrescentam sinal" e mexe no CA-F.1. E F7 "cicla" uma fila que não existe.

**Prova.** Spec:421 "Outra página com evidência: Dúvidas"; spec:470 "Página com evidência conta só as fortes"; spec:499 "o resultado entra em `EvidenciaDaPagina`". `MODOS` tem 5 ids, sem `lances` nem `duvidas` (`controladores.py:283`). `espaco.py:89` e `desenho.py:54` leem o modo.

**Correção, spec:419:**

> **As filas.** Ids em `ControladorDaFila.MODOS`: `duvidas` e `lances`, à frente dos cinco de hoje. **`lances` entra em PPL e `duvidas` em PP5:** até lá, F7 cicla Lances, Confiança, Ordem de leitura, Por caractere, Palavras desconhecidas, Diagramas por conferir. `lances` não entra em `DE_GLIFOS`: abre o editor Palavra.

**Spec:421 e 470: trocar as três ocorrências de "com evidência" por "com 2.ª opinião", e "sem evidência" por "sem ela", e acrescentar:** "A evidência de F-3 e X-1 não conta: só acrescenta marca e lance à contagem de Lances."

**Spec:458-466, CA-F4.7:**

> **CA-F4.7a (PPL).** As linhas de Lances e, em Confiança, a tela vazia acrescida de `40 lances não conferidos: F4 confere`. Com lance por conferir, nenhuma tela diz "nada a revisar".
> **CA-F4.7b (PP5).** As linhas de Dúvidas e o fim do livro.

**CA-F4.6** passa a PPT, sem a última oração sobre a fila; **CA-F1.3** segue em PP5.

### B7. O arquivo com os 8 erros não existe

**Onde.** Roadmap:123; checkup:204.

**Prova.** `docs/revisoes/checkup-2026-11/` não existe. A lista está no apêndice A de `critica-2.md`, no scratchpad desta sessão, que não sobrevive a ela.

**Correção.** Em PP0, item 0b: copiar a tabela do apêndice A para `docs/revisoes/checkup-2026-11/erros-do-gabarito.md`, só com página, linha e o token, e trocar as duas citações de `criticas.md` por esse nome. **Fazer agora, enquanto o scratchpad existe.**

### B8. As medidas por página, que decidem M2 e M5, não se podem tirar

**Onde.** Spec:39, CA-F4.8; roadmap:31, 37.

**Problema.** O registro de eventos não diz em que página o gesto foi, está desligado por padrão e não diz a fila. `tempo_da_fatia.py` divide por erros de um bloco, e não por página. Ninguém avisa que as "10 páginas antes" de M5 têm de ser colhidas **antes** de PP5 entrar.

**Prova.** `app/registro_de_eventos.py`: grava `{"t", "evento", "widget"}`, só com `ABBY_REGISTRO_DE_EVENTOS`. `tempo_da_fatia.py:8-9`.

**Correção.** Em PPL, item 8:

> **Registro por página.** `RegistroDeEventos` acrescenta uma linha `{"evento": "pagina", "pid": n, "fila": modo}` a cada troca de página ou de fila; sem texto de livro. `ferramentas/tempo_da_fatia.py --por-pagina` soma o tempo por `pid`, com a mesma regra de ociosos, e dá a mediana. **A partir de PPL, o programa liga o registro por padrão em `%LOCALAPPDATA%\AbbyChessCraft\`,** com a opção de desligar nas Opções: só instantes e tipos.

Na tabela de paradas, "Fim de M5":

> Em 10 páginas revisadas **antes de PP5 entrar** (o usuário as faz no fim de M4; 20 min) e 10 depois…

Sem a primeira amostra, o ponto de parada fica "não medido", e a fila nova vai como opção.

### B9. Alt+S é proibido, F4 reprova, e nenhum passo novo existe para o YAML

**Onde.** Spec:445, 419; roadmap "Toda tecla nova".

**Prova: rodei o verificador real numa cópia.**

| Tecla, escopo | Resultado |
|---|---|
| `Alt+S` | **reprova:** "Alt+letra é dos menus" |
| `F4`, global | **reprova:** "nativo de combobox (o atalho apaga a ligação nativa) sem exceção declarada" |
| `Enter`, em `palavra`, como ação nova | **reprova:** "nativo de lineedit… sem exceção" |
| `desde_passo: PP9` | **reprova:** "não é passo do roadmap" |
| `Ctrl+Shift+S`, `Ctrl+Shift+T`, global | ok |
| `Ctrl+W`, `Ctrl+B`, em `diagrama` | ok (`Ctrl+B` global colidiria com `negrito`) |
| `Ctrl+Shift+O`, global | ok, livre |

E o motivo gravado de `proximo_da_fila` (atalhos.yaml:161) diz: "o filtro da gaveta de Páginas abre a lista com **F4** ou clique". F4 global tira essa saída; fica o clique e o espaço.

**Correção, spec:445:** "**Ctrl+Shift+O** abre a sessão do Documento com o texto proposto."

**Spec:419, acrescentar:**

> F4 é global, com a exceção `{tecla: F4, widget: combobox, tipo: substitui, motivo: "F4 é da fila Lances; o filtro da gaveta abre com espaço ou clique"}`, e o motivo de `proximo_da_fila` e `anterior_da_fila` passa a dizer "com espaço ou clique". Enter e Ctrl+Enter da fila Lances **não são ações novas:** são `corrigir_palavra` e `corrigir_e_ensinar_palavra`, com o sentido da fila.

**No contrato:**

> Tecla nova: acrescentar o id do passo em `passos:` de `docs/atalhos.yaml` (a ordem importa), depois a ação, depois `ferramentas/atalhos.py`, porque `test_atalhos_md_esta_em_dia` reprova sem isso. Trocar a ordem de `MODOS` reprova `tests/test_revisao.py:65`, e isso é esperado.

### B10. CA-E5 e CA-E1 se pedem um ao outro, e E-6 vem por último em T3

**Onde.** Roadmap:134, 210, 273; spec:566, 570-571.

**Problema.** PP2 lista CA-E5, que pede "o lock", que é de E-1. CA-E1 pede "CA-R3.1 passa", que é de PP2. PP5 "precisa de E-6", e T3 diz "E-1… depois E-2, E-4, E-5 e E-6": lido ao pé da letra, toda a T3 antes de PP5.

**Correção.** Em PP2, trocar `CA-E5` por:

> `ferramentas/conferir_core.py` compara o commit do core com o gravado na referência da medida, e o portão avisa (CA-R3.4).

**Spec, CA-E1:** "…a suíte rápida passa, a janela abre e, se CA-R3.1 já existir, ele passa". **CA-E5 fica em T3.**

**Em PP5, item 3:** "`opiniao.py`, `EvidenciaDaPagina`, a thread e `opinioes/`, com o motor vencedor, e o extra `[opiniao-tesseract]` e `psutil` no `pyproject.toml` (E-6, CA-E6)." Tirar "Precisa de E-6 (T3)". **Em T3:** "E-1, depois E-2, E-4, E-5, independentes do resto do plano. E-6 está em PP5."

### B11. Com o Dec-5 recomendado, M5 não fecha

**Onde.** Spec:392-393, 627; contrato, item 6.

**Problema.** A recomendação é B, sem prova. Mas CA-F1.1 diz "na validação, **depois na prova**", CA-F1.2 é "**na prova**", e o ponto de parada de PP5 depende de CA-F1.1. Pelo texto, CA-F1.2 nunca é avaliado. E B dá **16 páginas** de validação: o contrato manda "bootstrap" na regra de "melhorou" e "teste de sinal com menos de 20 páginas", logo sob B **sempre** cai no segundo caminho, enquanto CA-F1.1 exige "o IC do bootstrap". Quem chega não sabe qual vale.

**Prova.** 4 livros × 4 páginas = 16 (spec:194, 627).

**Correção. CA-F1.1:** "Na validação; na prova, **só se Dec-5 for C**". **CA-F1.2:** "Marcas ≤ 15 % dos tokens, na validação; na prova, se houver." **Em (a):** trocar "com o IC do bootstrap pareado por página inteiro abaixo de 0" por "pelo critério do contrato, item 6". **No contrato, item 6, ao fim:**

> Com Dec-5 B são 16 páginas: vale o teste de sinal por página. Com um mesmo sinal em menos de 13 das 16, sai "não decidível". O bootstrap só vale com 20 ou mais.

(Com 16 páginas, 12 no mesmo sentido dão p = 0,077 bilateral, e 13 dão 0,021.) **Alvos da §1, coluna:** "Alvo, na prova, **se houver**".

---

## 5. Importantes

### I1. Faltam "Pronto quando"

**Onde.** Tabela da §1. **Correção, uma linha por passo:**

| Passo | Texto |
|---|---|
| PPL | **Pronto quando:** os CA passam, CA-F.1 não sobe no portão, e o usuário respondeu ao ponto de parada de M2. **Carga:** suíte rápida; **portão no fim**, porque CA-X1.6 e CA-F.1 são dele. |
| PP2 | **Pronto quando:** auditoria registrada, catraca no portão, primeira tabela na validação, alvos revistos com o usuário. **Risco:** o gabarito custar mais que ~10 h: a regra de parada do Dec-5 corta. |
| PP2b | **Pronto quando:** a tabela está no registro, com os dois tetos e o alarme. |
| PP2c | **Pronto quando:** os quatro números e a tabela, em T0 e T1, estão no registro, e o ponto de parada foi aplicado. |
| PP3 | **Pronto quando:** cada conserto tem "entra" ou "não entra" no registro, pelo contrato, item 6. |
| PP4 | **Pronto quando:** `cobertura@3` tem IC no registro, e CA-L1.1 e CA-L1.2 passam. **Risco:** cc e tempo do invólucro. **Carga:** uma medida; CA-L1.2 são 5 rodadas A/B, sozinhas. |
| PP5 | **Pronto quando:** os CA passam, R-4 feita, e o usuário respondeu aos pontos de parada de PP5 e de M5. |
| T1, bloco 1 | **Pronto quando:** CA-U4, CA-U5a, CA-U8 passam, e a metade de CA-U1 sobre Alt+3 e foco. **Custo:** 1 sessão. **Carga:** suíte rápida. |

Spec, **CA-U1**: partir em CA-U1a (Alt+3 e digitar; clique e fim de tarefa não movem o foco; M1) e CA-U1b (borda, barra de status, "Enter ensina"; T1 bloco 3). Hoje o CA não pode passar em M1.

### I2. A fila Lances mexe no modelo, e a spec não diz como

**Onde.** Spec:447-456, CA-F4.1, CA-F4.2; roadmap:90.

**Problema, cinco lacunas.**
1. "Aceito como impresso" **precisa sobreviver a reabrir** (CA-F4.2), mas não há campo nem regra. Quem chega vai criar campo em `Box`, e isso muda o formato.
2. `conferido`, de L-2 e CA-L2.3, não é estado nenhum no código.
3. O efeito em massa de `revisado` não está listado. Li os usos:
   - **pendentes, F6, coluna Rev., `confirmados`:** caem, por `contexto.py:522`, `fila_da_pagina.py:87`, `resumo_do_livro.py:233`. É o desejado.
   - **`verificada`:** não muda; só o Ctrl+T a põe (`modelo.py:308`).
   - **Exportação:** não muda; "não revisado" é de diagrama (`marcacao.py:61`).
   - **CA-F.1:** o replay não usa Lances, logo não sobe, salvo se a fila padrão mudar (B6).
   - **Lote e F5:** "a relida mantém `manual` e `revisado`" (`livro.py:10`).
   - **D-5:** com Dec-7 b, ou se o teste vermelho não falhar por outro motivo, o `revisado` volta a ser relido, e o Enter da fila Lances vira promessa falsa.
4. **Ctrl+Enter diverge do código.** Spec: "ensina o glifo sob o cursor". `corrigir(texto, ensinar)` em `controladores.py`: "ensina **os que mudaram**", e o YAML diz "os glifos dela". Em uma linha, isso são dezenas.
5. `gids_do_rejeitado(documento, diagrama, idioma)` e `_tabela(idioma)`: depois de `letras_das_pecas`, `idioma` não basta (`lances.py:172`).

**Correção, spec, depois de spec:456:**

> **O que muda no modelo: quase nada, e nenhum formato.** Conferir é `edicao.revisar(pagina, gids)` (`edicao.py:351`), que já é um passo do desfazer e não troca a fonte. **Lance conferido** é o token de lance com todos os glifos `manual`, `revisado` ou `nativa`. **Aceito como impresso** não se grava: é o lance conferido que a validação rejeita, calculado de novo ao abrir. `do_modelo` acrescenta `lances_por_conferir` ao resumo da página; página sem a chave conta como desconhecida, e `recalcular` a preenche. **Efeitos de `revisado`:** saem de pendentes, do F6 e da coluna Rev. Não mudam `verificada`, a exportação nem o treino. **Exige D-5 com Dec-7 a:** com Dec-7 b, PPL para e volta ao usuário.

**Spec:451:** "**Ctrl+Enter:** como acima, e ensina os glifos que mudaram, como no editor Palavra de hoje. Sem glifo mudado, não ensina."

**Spec:263 e CA-L2.3:** trocar "conferido" por "`revisado` pela fila Lances".

**F-3, spec:412:** `gids_do_rejeitado(documento, diagrama, tabela)`, com `tabela = lances.tabela_do_projeto(projeto)`.

**Palavra de lance:** "A fila Lances e o F-3 usam `classificar_token`, com `lances._tokens` conferido sobre a mesma tabela de 60 (CA-R1.6): as duas regras não podem discordar."

### I3. D-3, C-1 e as trilhas não têm lugar

**Onde.** Roadmap:9, 16, 100-110, 258-277.

**Problema.** PP1 lista D-3 e C-1 "nesta ordem" e nos CA; M1 os exclui; "entram logo depois de M2" não tem passo. CA-D3 e CA-C1 ficam no pronto de PP1, que por isso não fecha em M1. T1 blocos 3 e 4, T2 e T3 não pertencem a marco algum.

**Correção.** Em PP1, cortar os itens 7 e 8, e o CA fica `CA-C2, CA-C5, CA-D1, CA-D2, CA-D4, CA-D5`. No item 6, acrescentar: "**Dec-7 ao usuário, se o teste falhar.**" No item 2, acrescentar: "**Limite:** o que passar de 20 vermelhos ganha `erro_esperado`, com linha no registro, e vira pendência; C-5 não trava o passo." Tirar D-3 do Risco. Novo passo, depois de PPL:

> ## Passo PP1b — Página nativa e servidor órfão
>
> **Quando:** logo depois de M2; **antes de PPL, se o próximo livro for PDF digital.**
>
> **Fazer:** D-3, `nativo.remendar`; C-1, `vigiar_o_pai` no começo de `_principal`, antes de carregar os modelos.
>
> **CA:** CA-D3, CA-C1. **Risco:** D-3 é o item mais difícil: `difflib` e relatório do que não se aplica. **Pronto quando:** os CA passam, e o golden muda só com motivo. **Custo:** 2 sessões. **Carga:** portão no fim.

**Em T1, T2 e T3, na abertura de cada uma:** "Fora dos marcos: depois de M3, um item por vez, quando o usuário pedir. Um PR por item; custo de 1 sessão por bloco; suíte rápida, e portão só onde o item mexe em leitura ou exportação."

### I4. L-9 contraria a regra que o marco invoca

**Onde.** Roadmap:12, 16, 23; CA-L9.2.

**Problema.** "M1 a M3 não pedem gabarito: só acrescentam sinal, e não trocam nenhum caractere", e "daqui em diante, nada de leitura entra sem medida". Mas L-9 tira leitura de páginas, em M3, e CA-L9.2 lê gabaritos. Também Dec-5 A cobra 15 min de correção, e PP2b lê gabarito em M2.

**Correção, roadmap:16:**

> **M1 a M3 não pedem gabarito novo.** PP2b e CA-L9.2 leem os que já há. Só acrescentam sinal, e não trocam caractere. **A exceção é L-9:** a página classificada como imagem deixa de ser lida; por isso ela vai por último em PPT, com CA-L9.2 e a lista no fim do lote.

**Roadmap:12:** "Daqui em diante, **nada mais de leitura** entra sem medida."

### I5. Medir no fim, e o portão: nada diz o quê

**Onde.** Contrato, item 3; cada "Carga".

**Problema.** "Medir no fim" não diz o que medir em passo de interface. PPL diz "suíte rápida" e pede "conferir a fatia", que é `livro_real`. O vigia de RAM não está no repositório, e a máquina costuma ter ~3 GB livres.

**Correção, contrato, item 3:**

> **3. Medir no fim, sozinho, com a worktree intocada, RAM livre ≥ 3 GB:**
>
> | Tipo do passo | Medida |
> |---|---|
> | Interface, sem mudar leitura nem exportação | suíte rápida, `ruff`, e `test_atalhos` |
> | Dado ou exportação | isso, `-m processo`, portão no fim do passo |
> | Leitura | isso, portão, e a medida da regra de "melhorou" |
> | Fim de marco | `qualidade.py`, depois o portão, em comandos separados |
>
> Nada de portão por commit: **no máximo um por passo.** O portão reprovar por desempenho sem a máquina livre é rerrodado uma vez, sozinho, antes de investigar. CA-7.1 passou por 20 ms em 05/11 e oscila.

### I6. PP2: decisão de entrada no meio, e os livros ambíguos

**Onde.** Roadmap:127, 132; spec:197.

**Problema.** "Decisão de entrada: Dec-5 B ou C" e, no item 4, "Dec-5 ao usuário". Quem chega não sabe se faz os itens 0 a 4 sem o sim. Há **dois** PDFs de Aagaard e dois de Yusupov. `tests/verdade` não tem pasta de Aagaard nem de Nunn, e `--pdf` é obrigatório no rascunho. "Rodar a auditoria no `corpus_v2`" esbarra em "nunca editar o PyBoxEditor". `importar-do-projeto` e a grade da dupla leitura não têm CA.

**Prova.** `PASTA_DOS_PDFS` lista `Aagaard - Grandmaster Preparation - Calculation`, `Jacob Aagaard - Attacking Manual I`, `Artur Yusupov - Chess Evolution 1`, `Yusupov_Artur_Complete`. O `corpus_v2` e `tests/verdade/yusupov/i006.json` usam *Calculation* e *Evolution 1* (`aagaard_calculation_p030`, `yusupov_evolution_1_p034`). grep: `importar-do-projeto` não existe.

**Correção, PP2:**

> **Decisão de entrada: Dec-5 B ou C, antes do item 1.** Sem ela, PP2 não começa, e o plano para em M3 (ver "Quando o plano acaba").

**Spec:197, depois de "quatro":**

> Com PDF e slug fixos, na ferramenta do sorteio: `aagaard` = *Grandmaster Preparation – Calculation*; `nunn` = *Secrets of Rook Endings*; `yusupov` = *Chess Evolution 1*; `darcy` = *A Estratégia no Xadrez*, os mesmos do `corpus_v2` e de `tests/verdade`. O usuário pode trocar por um que queira converter, antes do sorteio.

**Item "auditoria no `corpus_v2`":**

> O gabarito do core não se edita: as páginas auditadas ficam em `tests/verdade/corpus_v2/`, com `origem` apontando para o core, e o que achar vai a `docs/pedidos-ao-pyboxeditor.md`.

**Novo CA:**

> **CA-R2.6.** Num projeto fabricado, corrigir duas linhas no Documento e rodar `rotular.py importar-do-projeto --livro X` grava o texto, marca `texto_verificado` só nelas e sobe `verdade_versao`. A grade decide 20 pares por tela, por tecla, sem dizer a origem de cada forma.

### I7. PP2c pede o que não existe

**Onde.** Roadmap:155.

**Problema.** "No Seirawan e no Yusupov, `replay_fatia` ensina as primeiras páginas verificadas e lê as seguintes." O Yusupov tem i006, i012 e i033, e 0 linha verificada; a validação exclui vizinhas. T1 pede páginas seguidas. Usar páginas de validação para ensinar também contamina.

**Correção:**

> **Fazer.** No Seirawan, i020 a i026, ensinando as 3 primeiras e lendo as 4 seguintes. Em outro livro, só se o usuário já tiver 5 páginas seguidas verificadas fora da validação. Com um livro só, o registro diz "só Seirawan", e o ponto de parada vale como indício: PP5 segue, com CA-F1.1 decidindo.

### I8. Governança: o plano não tem fim, nem registro de andamento

**Onde.** Todo o roadmap.

**Problema.** Sem definição de pronto. Sem resposta, Dec-5 fica em A, e o plano parece "parado em M4" para sempre. Dec-4 sem dono. Sem a linha "**Feito**", que o roadmap de qualidade usa. "Cada um volta ao usuário": 8 pontos de parada, 4 deles com o "se não" já decidido.

**Correção. Acrescentar, depois dos Pontos de parada:**

> ## Quando o plano acaba
>
> - **Fim curto, o padrão (Dec-5 A):** M1, M2, M3 e PP1b mesclados, com o ponto de parada de M2 respondido. O roadmap diz "parado em M3: sem gabarito". Nada fica pendente.
> - **Fim completo (Dec-5 B ou C):** M4 e M5 mesclados, com o ponto de parada de M5 respondido: a fila nova como padrão ou como opção, e a tabela por livro no registro. Dec-4 é perguntada aqui, e só então CA-A5 é feito.
> - **Não é condição de fim:** os alvos da §1, sem prova; M6; T1 blocos 3 e 4; T2; T3. São pedidos, um por vez.
>
> **Andamento.** Ao fechar um passo, abaixo do título: `**Feito** em AAAA-MM-DD, ramo pp-<id> (docs/revisoes/pp-<id>.md): <o número ou a decisão>.` A tabela de marcos ganha a coluna "Estado". Só isso.
>
> **Quem decide.** O que tem número e "se não" escrito, o agente aplica e registra. O usuário responde em quatro pontos: fim de M2, fim de PP2, fim de PP5, fim de M5. Mais as Dec, cada uma com padrão.

**Na tabela de paradas:** trocar "Cada um volta ao usuário" por "Só os quatro acima voltam ao usuário; os outros se aplicam sozinhos." **Fim de PP5:** trocar "Se o corrigido for baixo, F-2 vem primeiro" por "Se o corrigido for baixo, volta ao usuário: F-2 já está em M3, e a fila nova fica como opção." **Fim de PP2:** dizer o motor: "**o Tesseract** (e o PP-OCRv6, se houver venv)".

**Dec-7, roadmap:9:** "Dec-7, se o teste de D-5 falhar". **Dec-5, spec:618:** está sob "Agora", com "A agora; B depois de M3": mover para "Depois, com número na mão", com Quando = "Fim de M3".

### I9. Custo: a tabela não diz o que é sessão

**Onde.** Roadmap:7-14, 18.

**Correção, roadmap:18:**

> **Sessão:** 1 a 2 h de agente, cerca de 4 CA, 300 a 800 linhas, medido em Q1 a Q6. Um marco com mais de 50 % além da estimativa volta ao usuário antes de seguir. Mover estrutura custa 10 vezes mais (Q7, Q8): por isso T4 não é trilha.

**Coluna Sessões:** M1 **6**, M2 **7 a 9**, M3 **3 a 4**, M4 **5 a 6**, M5 **10 a 13**. **PP2:** "Custo: 4 a 5 sessões, mais o tempo dela, com **pelo menos 7 dias de calendário** por causa da amostra cega". **PP5:** "Custo: grande, 5 a 6 sessões". **PP1b:** 2. Depois da tabela: "**M1 a M5: 31 a 38 sessões. Com PP1b e as trilhas, 40 a 50. O calendário é decidido pelos 12 a 14 h dela e por duas esperas de 7 dias.**"

### I10. PP5: A-2 sem recorte, e `medir_motores` sem varrimento

**Onde.** Roadmap:204-205.

**Correção.**

> 1. **L-3, sem tocar no programa:** `medir_motores --motor tesseract --varrer` faz a grade de CA-L3.1; é a única coisa que PP5 acrescenta à ferramenta. Dec-2 ao usuário.
> 2. **A-2 só nos acessos de `ponte_de_leitura.py` e `fila_da_pagina.py` a privados do controlador.** Sem catraca do total.

**CA-A2** fica em T4, "ao tocar".

### I11. O perfil FineReader quebra os textos novos

**Onde.** Spec:360, 462-468.

**Problema.** Os textos fixam teclas do perfil padrão. No FineReader, **Shift+F7 é arranjo empilhado** e o escopo é Ctrl+Shift+F8; **F8 é arranjo só vista** e o diagrama é Ctrl+F8; F7 é arranjo, e o ciclo é Ctrl+Shift+F7. O fim do livro diria "F4 + Shift+F7" e "14 diagramas (F8)", ambos errados.

**Prova.** `atalhos.yaml:169-176, 184-188`.

**Correção, spec, antes da tabela de estados vazios:**

> As teclas das telas vêm do YAML, pelo perfil ativo, como `vazios.py:54` já faz com `_tecla`. Os textos abaixo são do perfil padrão.

**CA-F4.7a:** "… nos dois perfis." **F4** é igual nos dois.

### I12. Como reverter: nenhum marco diz

**Correção, depois de "Quando o plano acaba":**

> ## Como reverter
>
> Cada marco é um merge `--no-ff`: `git revert -m 1 <merge>`.
>
> | Marco | O que fica nos projetos depois de reverter | Efeito |
> |---|---|---|
> | M1 | `campos_do_box` em `projeto.json`; logs | Vai a `extras`. Nada a fazer |
> | M2 | `letras_das_pecas`; `lances_por_conferir` em `livro.json`; `revisado` em massa; `"fila": "lances"` no espaço | `extras`; a chave a mais, confirmar com teste em PPL; `revisado` continua válido, e sai da fila de hoje; o espaço cai no padrão com aviso (`espaco.py:776`) |
> | M3 | Zona `figura` nas páginas de imagem | Continuam sem leitura; mudar a função e F5 |
> | M4 | Nada no projeto; `tests/verdade` sobe de versão | Não reverter o gabarito: ele é a verdade |
> | M5 | `opinioes/`, descartável | Apagar a pasta |
>
> **Regressão num marco:** o que reprova CA-F.1 ou o golden não entra. Depois de mesclado, reverte-se primeiro e investiga-se depois.

### I13. Dec-1 "não trava nada", e PP2 põe texto de livro no repositório público

**Onde.** Roadmap:72; spec:617, CA-R2.3; PP2.

**Problema.** O padrão de Dec-1 é "segue público". Mas PP2 grava páginas inteiras verificadas em `tests/verdade`, e CA-R2.3 proíbe texto de livro em repositório público. `.gitignore` não cobre `tests/verdade`, e `rotular.py:26` diz "que é privado". Com o padrão, PP2 ou viola o CA, ou não sabe onde gravar. Também: Dec-1 b reescreve o histórico, e há 14 worktrees e citações de hash por toda parte.

**Correção, PP2, item 4:**

> **Com o repositório público, os gabaritos novos ficam em `%LOCALAPPDATA%\AbbyChessCraft\verdade\`, pela variável `ABBY_VERDADE`, fora do git, com backup dela.** Dec-1 a volta a pô-los em `tests/verdade`.

**Roadmap:72:** "Dec-1 não trava M1 a M3; M4 usa `ABBY_VERDADE` enquanto ela não vier."

---

## 6. O que cortar ou juntar

| Corte | Por quê |
|---|---|
| A-6 fora de PP2d, para T4 | Nenhum passo até M5 precisa dele; `ProjetoDeLivro` só importa em D-1, que não acrescenta método à classe |
| PP2d: `pagina.py` vai para PP4 | Só L-1b toca lá |
| 8 pontos de parada → 4 voltam ao usuário | I8 |
| "Parar de usar a prova: 3 usos" sai da lista | CA-R2.1 já reprova a quarta |
| E-5 em PP2, A-2 catraca em PP5 | B10, I10 |
| Dec-6 b deixa de mudar a base | B1 |
| PP2c no Yusupov | I7 |

---

## 7. Menores

| # | Onde | Problema | Correção exata |
|---|---|---|---|
| M1 | Spec:146 | "**Vem primeiro.**" contra M4 | "Sem ela, nada de leitura se pode falsear. **Vem antes de toda mudança de leitura.**" |
| M2 | Spec:172 | "Três níveis de gabarito", com 2 linhas | "**Dois níveis de gabarito:**" |
| M3 | Spec:677 | "só o quinto livro é separado por livro" | "e só o Darcy é, de fato, outro livro." |
| M4 | Spec, CA-R1.2 | "com marca fraca" contra "Não há 'marca fraca'" (spec:427) | "sem marca forte no token, conta como silencioso; com marca forte, não; com só o realce de hoje, conta como silencioso." |
| M5 | Spec:194 | "Decide L-3 a L-7", com L-7 fora do plano | "Decide L-3 a L-6 e F-1" |
| M6 | Roadmap:161 | `app/documento.py` em 992 | "994, pela conta do teste" |
| M7 | Roadmap, títulos | Só PPL, PP6, PP7 e PP9 dizem o marco; PP8 não | Título de todo passo com `(Mn)`: PP0, PP2d, PP1 (M1); PPL (M2); PPT (M3); PP2, PP2b (M4); PP2c a PP5 (M5); PP6 a PP9 (M6) |
| M8 | Checkup:199 | "a ordem dos passos depende de uma pergunta anterior (PP2b)" | "e a fila Lances, que não depende de motor, vem antes (M2)." |
| M9 | Spec:227, 229 | "no fim de PP5" e "no fim de M5" | Os dois: "no fim de M5" |
| M10 | Spec, §3.1 | CA-R1.4 depois de CA-R1.7 | Pôr na ordem |
| M11 | Spec | Três "quatro livros" diferentes: com figurinas (A, Y, N, D); de avaliação (A, N, Y, Darcy); com verdade (S, A, Y, N) | Na §3.2, depois do Sorteio: "Três conjuntos de quatro livros não se confundem: com figurinas, de avaliação, com verdade humana hoje." |
| M12 | Checkup:31 × spec:273 | "22 a 60 minutos" × "22 e 58" | Spec fica; checkup: "de 22 a 58" |
| M13 | Checkup:183 × spec:491 | N = 137 × 135 para o Seirawan | Na tabela do checkup: "(N = 137, pela regra de token da crítica 2; 135 pela `SAN`)" |
| M14 | `rotular.py:26` | "o repositório, que é privado": falso | Acrescentar a A-7 |
| M15 | Antipadrões | "Mover método para passar em teto", contra PP2d | "Mover método só para passar em teto, sem a régua nova (A-3)." |

**Conferidos, sem achado:** N ≥ 1.600 igual em spec e roadmap, e bate com 400 × 4; "3 usos" igual; "12 páginas" não aparece; `arquivo:linha` que amostrei (`lances.py:172`, `ponte_de_leitura.py:170,355`, `dados_do_projeto.py:48`, `exportar.py:236`, `SPEC.md:726,1097`, §15.2) estão certos; `Realce` e `edicao.revisar` existem; "13 commits" de `lacunas-da-spec` confere; PP2b e PP7 só aparecem onde devem. A spec não cita PP7 nem PP2b.
