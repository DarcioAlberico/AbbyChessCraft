# Roadmap: AbbyChessCraft como aplicação completa

Plano de construção da spec `docs/SPEC.md` (v0.4). Cada passo cabe numa sessão e traz o
contexto para ser executado do zero, sem ler os outros passos.

## Ordem serial

**0 → 1a → 1b → 2a → 2b → A1 → A2 → A3 → E → D1 → B → D2 → C → I → F → G → H → J → K → L**

Marcos para o usuário:
- **A3**: o lado a lado sincronizado.
- **E**: o lote não trava mais.
- **D1**: corrigir sem Word.
- **D2**: Ctrl+H.
- **C**: a galeria e o Ctrl+T.

Paralelos, só com git e worktrees e com arquivos disjuntos:
- B ∥ C;
- K ∥ (B ou C);
- L ∥ qualquer passo depois de A1.

## O contrato de todo passo

- Ler `README.md` e as seções da spec citadas no passo.
- Código, nomes e mensagens em português, UTF-8 sem BOM, LF.
- Nunca editar o PyBoxEditor (`C:\Python-Chess2\PyBoxEditor_Tkinter`) nem gravar na base
  global `training_data` dele. Precisar de privado do core vira pedido de API em
  `docs/pedidos-ao-pyboxeditor.md`, não importação.
- Lógica sem Qt em `abbychess/`; a janela só liga sinais a comandos (CA-14.1 vale em todo
  passo depois do 2a).
- Atalho novo entra primeiro em `docs/atalhos.yaml` (CA-3.7).
- Verificação, sempre:
  - `.venv\Scripts\python.exe -m pytest -q` (< 60 s);
  - `-m processo` quando o passo toca processo ou gravação;
  - `ABBY_PORTAO=1 .venv\Scripts\python.exe -m pytest -q -m "livro_real or desempenho"` no
    fechamento;
  - `C:\Python-Chess2\PyBoxEditor_Tkinter\.venv\Scripts\python.exe -m ruff check --select E,F --line-length 110 abbychess tests`;
  - `.venv\Scripts\python.exe ferramentas\medir.py --livro xv --indices 0,7,20-26` (e os
    outros livros, com os comandos do README), com o JSON citado no README.
- README: fluxo, "O que foi medido" (pelo JSON) e "Limitações conhecidas".
- Fechamento com as três revisões de §16 (nota ≥ 8 em cada eixo), registradas em
  `docs/revisoes/passo-N.md`.
- Com git: um ramo por passo, com o commit do código, o das correções de cada rodada de
  revisão e o das medidas (para cada medida registrar o commit que mediu); a tag do passo no
  commit aprovado. Sem git: cópia da pasta antes do passo
  (`robocopy . ..\AbbyChessCraft_backup_passoN /E /XD .venv rea`).

## Dependências

| Passo | Spec | Tamanho | Modelo | Depende de |
|---|---|---|---|---|
| 0 Git, linha de base, gabaritos, atalhos | §15, §3.4, §18 | M | padrão | — |
| 1a Persistência (formato v1) | §4.3 (parte) | M | mais forte | 0 |
| 1b Modelo v2 | §4.1, §4.2, §4.3, §4.4 | G | mais forte | 1a |
| 2a Controlador e gravador | §14.1, §4.3 | M | mais forte | 1b |
| 2b Desfazer e propagação | §14.2 | M | mais forte | 2a |
| A1 Visor novo | §3.3, §13 (estados) | M | padrão | 2b |
| A2 Espaço de trabalho | §3.1, §3.2, §3.4 | G | mais forte | A1 |
| A3 Documento e sincronia | §6.1, §6.2 | G | mais forte | A2 |
| E Servidor de leitura | §11, §4.6 | G | mais forte | 2b, A2 |
| D1 Edição (1:1, espaço, falta, apagar) e notação | §6.3 (D1), §6.4 | G | mais forte | A3 |
| B Busca | §7.1, §7.3 | M | padrão | A3 |
| D2 Substituir | §7.2 | M | mais forte | B, D1 |
| C Revisão | §8 | M | padrão | A3 |
| I Treino | §9 | M | padrão | A3, C, E |
| F Layout | §5 | G | mais forte | 1b, A2, E |
| G Edição completa | §6.3 (G) | M | mais forte | D1, F |
| H Diagramas | §10 | M | padrão | A3, F |
| J Exportação | §12.1–12.3 | M | padrão | F, H |
| K Aparência e teclado | §13, §3.4 (perfis) | M | padrão | A2 |
| L Editor de imagem e páginas | §12.4 | M | padrão | A1 |

---

## Passo 0 — Git, linha de base, gabaritos e atalhos

**Contexto.**
- A pasta (`C:\Python-Chess2\AbbyChessCraft`) não é repositório git.
- Os testes não têm marcadores.
- O pytest-qt está instalado e não é usado; hypothesis, regex e psutil não estão instalados.
- Não há gabarito rotulado nem ferramenta de medição.

**Tarefas.**
1. Com o sim do usuário (§18.1):
   - `git init`, com `.gitignore` para `.venv/`, `__pycache__/`, `rea/`, `*.egg-info` e os
     projetos de teste;
   - primeiro commit.
2. `pyproject.toml`:
   - marcadores, `addopts` e `timeout` de §15.1;
   - `[dev]` com hypothesis, pytest-qt, pytest-timeout, regex e psutil, instalados no
     `.venv`;
   - o hook do `ABBY_PORTAO`.
3. `tests/conftest.py` central:
   - os testes do Darcy Lima passam a `livro_real`;
   - o teste de página sintética pula sem a Arial.
4. **Testes de caracterização** do comportamento de hoje:
   - ensinar, propagar, dividir, juntar, ajustar, marcar, desfazer;
   - o texto das três montagens atuais (`pagina.texto`, `diagramas.texto_da_pagina`,
     `exportar.paragrafos`), como golden.
5. **Atalhos**:
   - `docs/atalhos.yaml` com a tabela de §3.4, nos dois perfis;
   - cada entrada com `desde_passo` (e `sem_atalho` ou exceção declarada, quando for o caso);
   - o teste de dados do CA-3.7, que já tem de passar sobre a própria tabela.
6. **Gabaritos**:
   - `ferramentas/rotular.py`;
   - rotulagem assistida:
     - Xadrez Vitorioso, índices 20–26;
     - Yusupov, escolher o PDF e fixá-lo por `pdf_sha256`, mais uma página de duas colunas e
       uma de uma;
     - Darcy Lima, índices 25–26 (p. 26–27 do PDF, impressas 27–28);
     - três páginas negativas;
   - a estrutura pelo assistente; o texto pelo usuário (`texto-exportar` / `texto-importar`),
     porque o assistente não transcreve o texto dos livros (direito autoral);
   - conferência cega de 1 página por livro, pelo usuário;
   - revisão pelo usuário (§18.3).
   - Até o texto ser verificado, as medidas de texto ficam "pendentes"; as de estrutura e
     de diagrama ficam "provisórias" até a revisão e a conferência dos FEN (spec §15.2).
     **Prazo**: as etapas do usuário não bloqueiam os passos 1a a A2; o texto e os FEN das
     p. 21–27 do Xadrez Vitorioso têm de estar verificados antes do fechamento do A3, que é o
     primeiro passo julgado pelo CA-F.1.
7. **Medidas**:
   - `ferramentas/medir.py`, `tests/desempenho/` e `docs/medidas/maquina.json`;
   - o snapshot `tests/dados/fatia/xv-i020-026-inicial.zip`, `ferramentas/replay_fatia.py` e o
     catálogo `ferramentas/replay/comandos.yaml` (revisado pela revisão de produto);
   - a linha de base de §2, com o replay da fatia sobre a interface de hoje;
   - `docs/medidas/protocolo-fatia.md`.

**Saída.** O passo em git, com a tag `passo-0` no commit aprovado pelas revisões; os
gabaritos com a estrutura rotulada pelo assistente (a revisão, o texto e a conferência cega
são do usuário, no prazo da tarefa 6); `docs/medidas/<data>-linha-de-base.json`, as medidas
de qualidade dos três livros e a da fatia, medidas com a árvore limpa.

## Passo 1a — Persistência, ainda no formato v1

**Contexto.**
- `abbychess/projeto.py` grava `paginas/NNNN.json` e `projeto.json`.
- `Projeto(**bruto)` quebra com campo desconhecido.
- `inclinacoes.json` (em `pagina.FonteDePaginas`) não é atômico.
- A fonte fica com caminho absoluto.

Este passo **não muda o formato** das páginas. A versão 2 nasce inteira no 1b.

**Tarefas.**
1. Escrita atômica, com `fsync`, nova tentativa em `PermissionError` e limpeza de `*.tmp`,
   em todo arquivo da lista de §4.3.
2. `extras` em `projeto.json` e modo só leitura para versão maior.
3. Caminho relativo da fonte e relocalização por SHA-256.
4. `livro.json` com o histograma de confianças.

**Verificação.** CA-4.2 (parte do 1a) e CA-4.7; a parte de `livro.json` do CA-4.4. A
caracterização segue passando.

## Passo 1b — Modelo v2 (§4.1–§4.4)

**Tarefas.**
1. `abbychess/modelo.py`:
   - `Box(gid, entry, amostra, estilo, revisado)` por composição;
   - `pid` estável por página, com o contador em `projeto.json`;
   - `gid = (pid << 20) | n`.
2. As funções de edição de `pagina.py` devolvem `Diferenca` com `sucessores`. O aplicador
   reescreve as decisões.
3. Leitor e propagação preenchem `Box.amostra`; `leitor.nome_de_origem` usa o gid.
4. `texto.py` e `montar(pagina) -> Documento`, com as decisões de §4.2, sobre as três
   montagens de hoje. Cada diferença em relação ao golden do passo 0 é justificada no
   registro do passo.
5. As zonas de hoje viram `Zona` com função. O `DiagramaLido` ganha `id`.
6. A máquina de estados de §4.4.
7. **Formato v2** (`paginas/p<pid>.json`), migração gravada, `backup-v1/` e `livro.json`
   com índice → pid.
8. A janela ainda usa índices, por um adaptador que o 2a remove.

**Verificação.** CA-4.1, CA-4.5; o CA-4.3 (parte do 1b); a caracterização (ou as diferenças
justificadas). O `livro.json` do 1a é recriado na migração (cache derivado).

## Passo 2a — Controlador e gravador (§14.1, §4.3)

**Contexto.**
- `abbychess/app/janela.py` (~1.300 linhas) guarda o estado em atributos soltos e os
  comandos em closures.
- `app/trabalho.py` roda uma tarefa e ignora o resto sem aviso.

**Tarefas.**
1. Extrair `ControladorDePagina`, família de comandos por família (estrangulador), com fila,
   seleção e pulados por gid. O adaptador de índices sai.
2. Gravador assíncrono com instantâneo imutável e escritor único.
3. Ocupado visível: a fila de tarefas na barra de status, nunca no-op.

**Verificação.** CA-4.2 (parte do 2a), CA-4.3 (parte do 2a), CA-4.4 (sem a cláusula do
servidor) e CA-14.1 (se não fechar só com o `ControladorDePagina`, extrair também os da
verificação e dos diagramas); a caracterização. Daqui em diante, `Box` e `BoxEntry` não são
mutados no lugar.

**A volta do custo do 1a e do 1b.** O 1a pôs `fsync` síncrono em cada gravação (uns 10 ms
na mediana do Enter), e o 1b a reconciliação da lista da janela com o modelo (mais 10 a 15 ms
na do Enter e na da releitura; `docs/revisoes/passo-1a.md` e `passo-1b.md`). O 2a tira as
gravações da thread da interface e a janela passa a editar o modelo, sem reconciliar; a
verificação dele inclui 6 rodadas completas de desempenho, 3 sem o congelamento
(`ABBY_SEM_CONGELAR=1`, `ABBY_ROTULO_DA_MEDIDA=repeticao-2a_sem_congelar`) e 3 com ele
(`repeticao-2a`, como o programa roda). Pelas **sem congelamento**, comparadas pela mediana
(p50) com as do passo 0 (que também não congelava), a mediana do Enter e a da releitura
voltam à faixa do passo 0 (em 2026-10-16: Enter 104–105 ms, releitura 106–108 ms), com 5 ms
de tolerância, em pelo menos 2 das 3 rodadas. Pelas **com congelamento**, o p95 da
releitura não fica pior que o do 1b (154–159 ms) e o do Enter não volta à faixa alta de
~200 ms; o alvo de 150 ms para o p95 da releitura é do passo 2b, que tira a cópia da página
inteira do desfazer.

## Passo 2b — Desfazer e propagação (§14.2)

**Tarefas.**
1. `HistoricoDoProjeto`:
   - `Transacao` com pré-condição por gid;
   - limite de 50 MB;
   - cobre o esquecer padrão e as zonas.
2. Propagação assíncrona que emenda a transação do Enter, com token de invalidação.
3. Medir o Enter: alvo de 100 ms.

**Verificação.** CA-4.3 (parte do 2b), CA-14.2 e CA-14.3; a meta do Enter [desempenho].

**O alvo da releitura.** O 2b tira a cópia da página inteira de cada passo do desfazer;
a verificação dele inclui 3 rodadas completas com o congelamento (`repeticao-2b`), e o p95
da releitura fica ≤ 150 ms (alvo de §2), em pelo menos 2 das 3.

## Passo A1 — Visor novo (§3.3)

**Tarefas.**
1. Um item que pinta os boxes, com índice em grade e repintura por retângulo.
2. Tokens de estado de §13: cores e traços dos boxes, inclusive "aguardando leitura".
3. Aceitos discretos e V.
4. Zoom:
   - 0/7/8/9 e Ctrl++/−, com limites;
   - caixa de zoom com `ClickFocus`;
   - o zoom do Documento fica para A3.
5. Espaço e botão do meio arrastam; PgUp e PgDn viram a página.
6. Navegação: Ctrl+G passa a ir para a página e a conferência de diagramas passa a F8 já
   aqui, pelo YAML; Alt+Home e Alt+End, Alt+← e Alt+→, Seguir.
7. Cache LRU e pré-carga.

**Verificação.** CA-3.4, CA-3.5, CA-3.6 e CA-3.8; a troca de página de §2.

## Passo A2 — Espaço de trabalho (§3.1, §3.2, §3.4)

**Tarefas.**
1. O splitter da Imagem com a vista direita, que até o A3 mostra o texto de hoje.
2. O Inspetor de um editor só:
   - Glifo, com o treino de hoje e a exceção 6 de §3.4;
   - Palavra, com a verificação de hoje;
   - seletor da fila em `QToolButton`.
3. Gaveta de Páginas pelo `livro.json`, aberta em projeto novo.
4. Resultados e Avisos, com log persistente.
5. Arranjos e foco do perfil padrão; Shift+F10 e Menu abrindo o menu de contexto.
6. Os demais atalhos com `desde_passo = A2`, registrados a partir do YAML (Alt+↓/↑, F7, Ctrl+M, Ctrl+T).
7. Menus Exibir e Ajuda.
8. `saveState` por projeto.

**Verificação.**
- CA-3.1, CA-3.2 (sem a cláusula do tabuleiro) e CA-3.3 (perfil padrão).
- CA-3.7: o teste de dados mais o da janela, só no perfil padrão, `desde_passo ≤ A2`.
- CA-4.2 (parte do A2) e CA-8.2 (a parte do Alt+↓).
- `ferramentas/capturas.py` nasce aqui; capturas para a revisão de design.

## Passo A3 — Documento e sincronia (§6.1, §6.2)

**Tarefas.**
1. Montar o `QTextDocument` do `Documento`:
   - mapa posição → gid em `QTextBlockUserData`;
   - diagramas inline e atômicos;
   - realce que liga e desliga;
   - Ctrl+Shift+H para os cabeçalhos;
   - zoom do corpo.
2. Até o D1, o Documento é somente leitura.
3. A faixa Linha.
4. Sincronia nos dois sentidos e com a fila; Seguir.
5. Atualização por eventos, sem perder o cursor.

**Verificação.** CA-6.1 e CA-6.5; o CA-F.1 com alvo de ≤ 85%; o CA-F.2 (informativo).

## Passo E — Servidor de leitura (§11, §4.6)

**Tarefas.**
1. `abbychess/servidor_de_leitura.py`:
   - sem PySide6 nem torch na interface;
   - `spawn`, prioridade e threads;
   - a guarda em `__main__.py`.
2. Toda leitura global passa pelo servidor:
   - F5, releituras e lote;
   - preempção entre glifos;
   - "aguardando leitura".
3. Deltas de padrões.
4. Escritor único com a regra de conflito.
5. §4.6: transferência das decisões; `.antes-do-lote/` e "Voltar ao estado antes do lote".
   Até o passo F, a função de zona transferida é a do modelo de hoje.
6. Cancelar pelo ✕, retomar, pular as verificadas e progresso na gaveta.
7. Fábrica de leitor falso.

**Verificação.**
- CA-11.1 a CA-11.8.
- CA-4.4 completo.
- CA-4.8.
- O trecho do lote do CA-8.5 (as verificadas são puladas).

## Passo D1 — Edição e notação (§6.3, linhas D1; §6.4)

**Contexto.** É a parte mais delicada do produto. O Documento fica editável com a sessão de
§6.3. Neste passo entram só os trechos marcados D1; os marcados G recusam a confirmação com
aviso.

**Tarefas.**
1. A sessão de várias palavras, com realinhamento em `contentsChange` e o desfazer do widget
   desligado.
2. Enter, Shift+Enter, Ctrl+Enter e Esc (restaurar). Enter numa palavra sem mudança a
   aceita.
3. `revisado`; o aviso estrutural na Linha.
4. Figurinas ao digitar, Ctrl+Shift+peça (repetir alterna a cor) e F2.
5. A máquina de estados do CA-4.3 ganha `editar_palavra`.

**Verificação.**
- CA-6.2, CA-6.3, CA-6.7, CA-6.8 e CA-6.9.
- CA-6.4 nas linhas D1.
- CA-4.3 completo.
- CA-F.1 com alvo de ≤ 70%; CA-F.2 (informativo).

## Passo B — Busca (§7.1, §7.3)

**Tarefas.**
1. Índice em segundo plano.
2. A barra de busca e as opções.
3. `regex` com `concurrent=True` e timeout, abortando no primeiro timeout.
4. As classes `\L`, `\P`, `\C` e `\V`.
5. Figurina = letra.
6. Resultados.
7. Busca por glifo, que mostra a lista até o passo C.

**Verificação.** CA-7.1, CA-7.3, CA-7.4 e CA-7.6; repetir o CA-11.1 com a busca no roteiro.

## Passo D2 — Substituir (§7.2)

**Tarefas.**
1. Ctrl+H, com `\1` e `\g<nome>`.
2. Prévia com caixas de marcar, mostrando os casos sem tradução desabilitados.
3. Escolha entre Prosa, Notação e Ambos.
4. Uma transação do desfazer.

**Verificação.** CA-7.2 e CA-7.5.

## Passo C — Revisão (§8)

**Tarefas.**
1. Modos e escopo da fila: F7 e Shift+F7.
2. Galeria por caractere.
3. Aba Padrões com a origem e o esquecer que se desfaz.
4. Procedência: o esquecer devolve à fila e as verificadas voltam a `em_revisao`.
5. Aviso de conflito ao ensinar.
6. Ctrl+T com confirmação inline.

**Verificação.** CA-8.1 a CA-8.6.

## Passo I — Treino (§9)

**Tarefas.**
1. O livro novo guiado:
   - amostra de 3 páginas pelo servidor;
   - fila por caractere;
   - cartão Saúde do livro na gaveta e no estado vazio.
2. Texto nativo pelo `core.pdf_nativo`.
3. Efeitos de impressão (`core.negrito`).
4. Ligaduras.
5. A Linha no Inspetor Glifo.

**Verificação.** CA-9.1 a CA-9.5.

## Passo F — Layout (§5)

**Contexto.**
- `core/livro.py` do PyBoxEditor já tem colunas, parágrafos com recuo,
  `retirar_cabecalhos` e tabelas.
- O AbbyChessCraft tem `zonas.automaticas` e `exportar.margens_corridas`.
- Ler os docstrings do core e registrar o que precisa de API pública.

**Tarefas.**
1. O pipeline de §5.1, gravando zonas e funções; as zonas automáticas são divididas por
   função.
2. A legenda ligada ao diagrama.
3. O cabeçalho aprendido por livro.
4. A interface do modo Áreas: funções por letra, Ordenar, modelo de áreas e Ctrl+Shift+R.
5. A transferência de §4.6 passa a carregar as funções de zona do layout novo.

**Verificação.** CA-5.1, CA-5.2, CA-5.3 (parte do Documento), CA-5.4 e CA-5.5.

## Passo G — Edição completa (§6.3, linhas G)

**Tarefas.**
1. Os trechos que faltam:
   - k → 1, que junta os boxes;
   - 1 → k, que divide pela tinta, ou faz uma caixa de k caracteres.
2. Ctrl+Shift+Enter (parágrafo) e o hífen de quebra.
3. Ctrl+B/I/U e os estilos no Documento.
4. A prévia de substituição passa a habilitar esses casos.

**Verificação.** CA-6.4 completo e CA-6.6.

## Passo H — Diagramas (§10)

**Tarefas.**
1. O editor Diagrama no Inspetor, com a Imagem dando zoom no diagrama, PgUp e PgDn pelo
   livro, e F8.
2. A aba Diagramas.
3. A validação pelos lances, com o gerador de perturbações.
4. O roque inferido.
5. O PGN por diagrama.

**Verificação.** CA-10.1, CA-10.2 e CA-10.3; CA-3.2 (cláusula do tabuleiro).

## Passo J — Exportação (§12.1–12.3)

**Tarefas.**
1. A exportação passa a ler o Documento.
2. As opções.
3. TXT e PGN.
4. A pré-visualização em HTML.
5. O relatório.
6. `SOURCE_DATE_EPOCH`.
7. Sair dos privados do core.

**Verificação.** CA-12.1 a CA-12.6; CA-5.3 (parte da exportação).

## Passo K — Aparência e teclado (§13, §3.4)

**Tarefas.**
1. Tokens completos e o tema claro e escuro.
2. Os ícones (§18.5).
3. Os estados vazios.
4. `accessibleName`.
5. O perfil FineReader e a reatribuição de atalhos em Opções.

**Verificação.** CA-13.1, CA-13.2 e CA-13.3; CA-3.3 e CA-3.7 nos dois perfis.

## Passo L — Editor de imagem e páginas (§12.4)

**Tarefas.**
1. Dividir páginas espelhadas, girar, cortar e endireitar à mão, em páginas pares, ímpares
   ou num intervalo.
2. Apagar, reordenar e inserir páginas, com `pid` estável, `inclinacoes.json` chaveado por
   `pid` e o `livro.json` coerente.

**Verificação.** CA-4.6; um CA por operação, escrito no início do passo e revisado.

---

## Antipadrões

- Texto solto no Documento, ou um segundo caminho que monta o texto.
- Índice de box ou de página fora do modelo (use `gid` e `pid`).
- Trabalho longo na thread da interface, ou ação ignorada sem aviso.
- Dois escritores no mesmo arquivo. Torch no processo da interface.
- Atalho fora do `docs/atalhos.yaml`, letra solta em widget editável ou Ctrl+Alt.
- Importar privado do core, editar o core ou gravar na base global.
- Tempo medido fora da camada `desempenho`, ou número no README sem o JSON da medição.
- Declarar pronto sem a medição no livro de referência.

## Mudanças

- **0.2 (2026-10-15)**: fatia vertical, passo 1 dividido, desfazer unificado, passos I e L,
  dependências corrigidas (rodada 1, `docs/revisoes/rodada-1.md`).
- **0.3 (2026-10-15)** (rodada 2, `docs/revisoes/rodada-2.md`):
  - Ordem serial explícita.
  - 1b e 1c viraram um passo só, e o formato v2 nasce inteiro.
  - O 2 se dividiu em 2a e 2b.
  - O E vem logo depois do A3 e traz a §4.6.
  - O D se dividiu em D1 (edição, só depende do A3) e D2 (substituir).
  - Dependências do I e do F corrigidas.
  - Os tokens de estado entraram no A1.
  - O perfil FineReader foi para o K.
- **0.4 (2026-10-15)** (rodada 3, `docs/revisoes/rodada-3.md`): verificações por parte, cada
  uma no passo em que pode passar (CA-4.2, 4.3, 3.2, 3.8, 5.3); `desde_passo` nos atalhos;
  catálogo de comandos do replay; capturas no A2.
- **0.5 (2026-10-16)** (fechamento do passo 0, `docs/revisoes/passo-0.md`): a saída do
  passo 0 deixa de esperar os gabaritos revisados pelo usuário, que têm prazo até o
  fechamento do A3; a linha de base fica presa à tag `passo-0`; o catálogo do replay ganhou
  `ensinar_da_fila` e `reler_pendentes`.
