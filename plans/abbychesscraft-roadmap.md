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
  - `.venv\Scripts\python.exe -m pytest -q -n auto` (< 60 s; em paralelo desde 2026-10-23);
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
     p. 21–27 do Xadrez Vitorioso têm de estar verificados antes do fechamento do D1, que é o
     primeiro passo julgado pelo CA-F.1 (até a versão 0.7, o A3).
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
2. Propagação assíncrona que emenda a transação do Enter, com token de invalidação; o
   painel de treino volta a valer logo depois da parte síncrona do Enter (no 2a ele fica
   desligado até o fim da propagação).
3. Medir o Enter: alvo de 100 ms.

**Verificação.** CA-4.3 (parte do 2b), CA-14.2 e CA-14.3; a meta do Enter [desempenho].

**O desempenho do 2b.** O 2a já tirou da interface a gravação, a reconciliação e a cópia
funda do desfazer: o p95 da releitura ficou em 86–106 ms (o alvo de 150 está alcançado) e o
do Enter em 90–116 ms (`docs/revisoes/passo-2a.md`). A verificação do 2b inclui 3 rodadas
completas com o congelamento (`repeticao-2b`) e 3 sem (`repeticao-2b_sem_congelar`): o
Enter é medido até a cor mudar (a parte síncrona, como §2 pede) e fica ≤ 100 ms no p95 em
pelo menos 2 das 3 com o congelamento (o 2a, medindo até o fim da propagação, já deu 2 de
3); as medianas do Enter (até o fim da propagação, como no 2a) e da releitura não sobem
mais de 5 ms acima das do 2a; a memória do desfazer estimada fica
≤ 50 MB; e as rodadas dizem se o congelamento (`gc.freeze`) continua. O alvo de §2 "com o
lote rodando" é do passo E, o primeiro que deixa medir isso.

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
- Pendência do A1: em `docs/atalhos.yaml`, a exceção do `proximo_da_fila` cita o widget
  `combobox` para a caixa de zoom, que é um `QSpinBox`; acertar o widget ao montar o teste da
  janela do CA-3.7.

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

Pendência do A2: a cláusula da Linha do CA-3.2 (a x-height ≥ 12 px na Linha, em 1366×768 e
1280×720) entra com a Linha (Ctrl+F5).

**Verificação.** CA-6.1 e CA-6.5; o CA-F.2 (informativo). (O CA-F.1 com alvo de ≤ 85% saiu
na versão 0.8: o A3 é só leitura, e o replay mediria o mesmo que no A2.)

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

**Execução iniciada em 2026-10-20, ramo `passo-i-treino`.** O texto desfaz as
ligaduras tipográficas (`ﬁ`, `ﬂ`, `ﬀ`, `ﬃ`, `ﬄ`) nos modos impresso e SAN; o
Documento mantém o mesmo gid nas letras que vieram do único glifo. Uma amostra
ensinada como `ﬁ` foi lida como um box e exportada como `fi` nos dois modos
(CA-9.2). `livro.paginas_da_amostra` escolhe as páginas a 10%, 50% e 90% do
intervalo do corpo, sem repetir índice. As amostras guardam negrito/itálico e, quando o
efeito do glifo é conhecido, o k-NN exclui amostras de efeito diferente; o metadado também
segue no delta para o servidor (CA-9.3). Em 2026-10-21, a régua pública de `core.negrito`
passou a medir as palavras da página; o efeito fica no `Box`, acompanha F5 e lote, é gravado
na amostra ensinada e filtra a propagação k-NN. O CA-9.5 também passou: o Ctrl+N oferece a
camada aprovada por `core.pdf_nativo`; aceitá-la cria páginas confirmadas no modelo sem
pedido ao servidor, enquanto as recusadas ficam para OCR e são as únicas candidatas à
amostra guiada quando a camada é parcial. O fluxo guiado de Ctrl+N agora
reúne nome, idioma e intervalo contínuo do corpo em um único formulário; escolhe e reconhece
automaticamente as três páginas da amostra dentro desse intervalo, abre a fila por caractere e
mostra a evolução dos pendentes e dos padrões no cartão Saúde, na gaveta e no estado vazio
do Documento; o cartão também oferece o lote completo e o destaca ao atingir o limiar
(CA-9.4). A faixa Linha única substituiu o antigo recorte “Na linha” do Inspetor Glifo e
continua sincronizada com a fila e o Documento. A medição do itálico em imagens OCR aguarda
uma régua pública do core; CA-9.1 também continua pendente.

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

**Execução iniciada em 2026-10-21, ramo `passo-i-treino`.** A ordem de leitura em colunas
foi separada em `abbychess.layout.OrdemDeLeitura` para o Documento. Ele agora forma linhas
dentro de cada trecho e lê uma coluna inteira antes da seguinte, preservando faixas
transversais como títulos. A exportação ainda conserva a implementação anterior até a
equivalência dos casos de caracterização permitir unificar as duas.

As zonas automáticas agora também são divididas por função quando há evidência local:
`titulo` pelo corpo tipográfico de pelo menos 1,3×, `numero_de_pagina` pelo texto e pela
faixa da margem, e `legenda` pelo texto e pela proximidade de um diagrama. Zonas desenhadas
pelo usuário nunca são reclassificadas. Cabeçalho e rodapé continuam pendentes porque a
regra correta aprende repetições entre páginas do livro.

Cada zona de `legenda` automática guarda também o `diagrama_id` estável (`dN`) do tabuleiro
mais próximo com sobreposição horizontal. O vínculo nasce junto com os IDs, antes do
histórico e da gravação, sobrevive ao ciclo JSON e não substitui uma ligação manual.

A regra de margens da exportação agora expõe a função semântica por glifo. Ao criar as
áreas automáticas, a página usa todas as páginas reconhecidas do livro para aprender
títulos corridos repetidos e grava as zonas como `cabecalho`, `rodape` ou
`numero_de_pagina`. A API antiga da exportação continua sendo um adaptador dessa mesma
verdade, incluindo a remoção de poeira.

**Concluído em 2026-10-21.** O classificador local também cobre título curto, isolado e
centralizado, nota menor no pé e novo parágrafo por recuo. O modo Áreas mostra cor e nome da
função, aceita T/H/C/R/P/N/L/D/X e menu de contexto, ordena por cliques com cancelamento
por Esc, salva/aplica um modelo no intervalo inteiro, pares ou ímpares (recusando outra
resolução) e relê somente a zona atual com Ctrl+Shift+R. Funções, ordem e ligação da
legenda entram no Documento e sobrevivem ao F5, ao desfazer e ao JSON.

**Contexto.**
- `core/livro.py` do PyBoxEditor já tem colunas, parágrafos com recuo,
  `retirar_cabecalhos` e tabelas.
- O AbbyChessCraft tem `zonas.automaticas` e `exportar.margens_corridas`.
- Ler os docstrings do core e registrar o que precisa de API pública.

**Tarefas.**
1. ~~Completar o pipeline de §5.1, gravando zonas e funções.~~
2. ~~Persistir a ligação da legenda já identificada ao diagrama correspondente.~~
3. ~~O cabeçalho aprendido por livro.~~
4. ~~A interface do modo Áreas: funções por letra, Ordenar, modelo de áreas e
   Ctrl+Shift+R.~~
5. ~~A transferência de §4.6 passa a carregar as funções de zona do layout novo.~~

**Verificação.** CA-5.1, CA-5.2, CA-5.3 (parte do Documento), CA-5.4 e CA-5.5.

## Passo G — Edição completa (§6.3, linhas G)

**Tarefas.**
1. ~~Os trechos que faltam:~~
   - ~~k → 1, que junta os boxes;~~
   - ~~1 → k, que divide pela tinta, ou faz uma caixa de k caracteres.~~
2. ~~Ctrl+Shift+Enter (parágrafo) e o hífen de quebra.~~
3. ~~Ctrl+B/I/U e os estilos no Documento.~~
4. ~~A prévia de substituição passa a habilitar esses casos.~~

**Concluído em 2026-10-21.** As operações estruturais conservam sucessores e desfazer;
a divisão usa os vãos da tinta e cai para uma caixa multicaractere quando não há corte
confiável. Parágrafos e estilos ficam no modelo persistido, aparecem no Documento e os
mesmos casos são aplicáveis pela prévia de substituição.

**Verificação.** CA-6.4 completo e CA-6.6.

## Passo H — Diagramas (§10)

**Execução iniciada em 2026-10-22, ramo `passo-i-treino`.** `abbychess.lances` lê a primeira
linha de lances do texto que segue cada diagrama (até o próximo diagrama ou título, sem
legenda nem margens), com as letras do idioma do livro (`Cf3` em português) e as figurinas;
a linha começa no primeiro lance numerado, aceita a prosa no meio e para na variante (o
parêntese, o ponto e vírgula, o número que volta). A validação joga a linha no FEN lido com
`python-chess`: o lance ilegal ou ambíguo, o `x` que não captura, o `+`/`#` que não dá
xeque/mate e o lado do número contra o da legenda dão o aviso ("3.Cf3 do texto não é legal
aqui"); todos legais dão **confiável pelos lances**. A validação é derivada como o lado pela
legenda: refeita em `_mudou`, no lote, na substituição pelo livro e na leitura dos
diagramas, gravada no diagrama e usada por `confiavel`: o lance ilegal tira a confiança do
porteiro, mas a linha legal não anula a dúvida dele (um lance só passa em muitas posições
erradas). Quando nem a legenda nem quem conferiu disseram o lado, o número do primeiro
lance (`10...`) o diz, com a procedência própria (`lances`), e o FEN, o texto e o PGN
concordam. O texto de um diagrama ainda por ler não cai no anterior. A conferência revalida
a cada casa corrigida. Pendente da revisão: desmarcar todos os roques na conferência ainda
deixa o inferido valer na validação (o modelo não guarda `roque_informado`). **Feito em
2026-10-23** (`cf151d1`, ver "Pendências").

O roque inferido (rei e torre nas casas iniciais) é usado só para validar e aparece na
conferência com o botão "Usar"; o FEN e a exportação continuam sem ele até alguém marcar
(CA-10.3). O PGN por diagrama (Copiar PGN na conferência) parte do FEN com `SetUp`, leva os
lances validados com os NAGs e declara só o roque conferido ou jogado pelo próprio texto.

CA-10.1 em `ferramentas/medir.py` (`validacao_pelos_lances`, também no JSON da medição),
sobre os gabaritos do Xadrez Vitorioso: os 2 diagramas com lances saem confiáveis; das 100
perturbações (semente 1234), 23 tocam uma casa usada pela linha e as 23 são detectadas
(1,0 ≥ 0,6), nenhuma afetada sai confiável. As 73 não afetadas que saem confiáveis estão
fora do alcance de qualquer validação pelos lances; a precisão 1,0 "nas perturbadas" do
CA-10.1 só é atingível lida sobre as afetadas — **decisão pendente do usuário** sobre a
redação do critério.

A conferência deixou de ser um diálogo modal: é o editor Diagrama do Inspetor
(`app/editor_diagrama.py`). A Imagem enquadra o diagrama impresso (`VisorDePagina.enquadrar`)
e continua com zoom e rolagem livres (CA-10.2, testado). Ctrl+Enter confere e vai ao próximo
por conferir (o F8, também no fim da página); PgUp/PgDn andam pelos diagramas do livro,
atravessando páginas sem dar a volta; os três estão no `docs/atalhos.yaml` com o escopo
`diagrama` (`desde_passo: H`), e o Ctrl+Z com o foco no editor desfaz as casas, não a página.
A aba Diagramas da vista direita (`app/painel_diagramas.py`) lê os diagramas do livro fora da
interface e os mostra em grade (recorte das páginas na memória, posição desenhada e estado),
com os filtros por conferir, lidos sem confiança, confiáveis pelos lances e conferidos; Enter
abre no editor. O recorte das páginas nunca abertas fica de fora: converter o livro inteiro
para a aba seria trabalho longo. Da revisão de código: a conferência grava pela caixa do
diagrama (nunca no diagrama errado depois de um F5, desfazer ou edição de áreas) e só marca
"conferido" se gravou; o editor acompanha as mudanças da página ou fecha; reabrir na mesma
página mantém as casas em edição; sem casa a desfazer, o Ctrl+Z no editor desfaz a página
(a conferência); a aba lê o livro sem passar pelo cache de páginas.

**Concluído em 2026-10-22**, salvo a decisão pendente sobre a redação do CA-10.1.

**Tarefas.**
1. ~~O editor Diagrama no Inspetor, com a Imagem dando zoom no diagrama, PgUp e PgDn pelo
   livro, e F8.~~
2. ~~A aba Diagramas.~~
3. ~~A validação pelos lances, com o gerador de perturbações.~~
4. ~~O roque inferido.~~
5. ~~O PGN por diagrama.~~

**Verificação.** CA-10.1, CA-10.2 e CA-10.3; CA-3.2 (cláusula do tabuleiro).

## Passo J — Exportação (§12.1–12.3)

### Auditoria do EPUB real — Aagaard, 2026-10-21

Artefato auditado: `a-matter-of-endgame-technique-jacob-aagaard.epub`, 19.367.892 bytes,
SHA-256 `1AD8C9CAC636EC70A5AACB5BAF7F167B97E60D53F32F0707F7CFC746FBB5CB9B`. O pacote básico
está correto: `mimetype` é a primeira entrada e não está comprimida; os 898 XHTML são XML
válido; não há imagem referenciada ausente; o OPF declara EPUB 3 e idioma `en`. A fonte de
símbolos de xadrez está incorporada e 2.589 dos 2.636 diagramas têm FEN no texto alternativo.

O artefato revelou estas lacunas, que entram no escopo dos passos F, G, H e J:

- **OCR e texto (P0, todos os formatos):** aparecem nomes destruídos (`S k Mi hal Kr`),
  trocas recorrentes de `I/l` e `0/O` (`lt is`, `ln the`, `6o.`), palavras erradas
  (`rwists`), espaços dentro da palavra (`unnec. essary`), pontuação convertida em apóstrofo
  e cabeçalho/rodapé no corpo (`pawn moves 95`). Foram contados ao menos 143 `lt is` e 103
  `ln ...`; isto pede relatório pré-exportação por léxico, confusões recorrentes, palavra
  partida e trecho de baixa confiança, com ação para voltar à página e corrigir em lote.
- **Parágrafos entre páginas (P0, EPUB/DOCX/TXT):** cada página física virou um documento;
  há 439 limites cujo último parágrafo não termina em pontuação e 18 continuações fortes
  começando em minúscula. O intermediário deve juntar parágrafos que atravessam a página,
  desfazer hífen de quebra e conservar a página original como âncora, não como quebra
  editorial obrigatória.
- **Estrutura (P0/P1):** os 8.825 parágrafos saíram com zero `h1`–`h6`, zero `strong`/`em`,
  zero tabelas e zero links. Funções de zona precisam produzir títulos, subtítulos, notas,
  legendas, tabelas e estilos inline no Documento; EPUB e DOCX devem consumir essa mesma
  estrutura, sem remontá-la diretamente dos boxes.
- **Sumário e navegação (P1):** o `nav.xhtml` tem 898 itens planos chamados “Página N”, em
  português num livro inglês. Gerar TOC hierárquico pelos títulos reais; mover as páginas
  físicas para um `epub:type="page-list"`; acrescentar landmarks (capa, sumário, corpo,
  índice) e preservar âncoras de página. “Solution onpage N”, índice e referências a
  diagramas/capítulos devem virar links internos conferidos.
- **Granularidade (P1):** 898 arquivos no spine tornam navegação e manutenção ruins. Gerar
  XHTML por capítulo/seção, com divisão por limite de tamanho, em vez de um por página;
  manter `epub:type="pagebreak"` para a correspondência com o impresso.
- **Diagramas (P0/P1):** 47 imagens têm apenas `alt="Diagrama"` e não têm FEN; 53 figuras
  não têm legenda. Antes de exportar, listar diagramas não lidos/não conferidos; quando não
  houver FEN, produzir alternativa útil (estado, lado a jogar, legenda e aviso) sem afirmar
  no OPF que texto alternativo suficiente existe. Ligar legenda, solução e PGN ao diagrama.
- **Metadados e capa (P1):** o OPF não tem `dc:creator`, `dc:publisher`, `dc:date`,
  `dc:subject` nem `cover-image`, embora o autor esteja no título. Adicionar formulário e
  extração assistida desses campos, identificador configurável, capa real, direitos e
  idioma das mensagens geradas. Não codificar “Sumário”, “Página” e o resumo de
  acessibilidade em português quando `dc:language` for outro.
- **Acessibilidade (P1):** recalcular `accessModeSufficient` e
  `accessibilityFeature=alternativeText` a partir do que foi realmente exportado; não usar
  `hazard=none` sem verificação. Imagens informativas ganham alternativa específica;
  decorativas, `alt=""`; títulos, tabelas, notas, landmarks e ordem de leitura usam HTML
  semântico. Rodar Ace by DAISY além do EPUBCheck.
- **Tamanho (P2):** há 2.636 PNG; 157 são cópias byte a byte, desperdiçando cerca de
  958.719 bytes. Deduplicar pelo hash, reutilizar o mesmo recurso, aplicar otimização
  lossless e dimensões responsivas; conservar resolução suficiente para peças e texto.
- **Apresentação (P2):** trocar larguras inline em `pt` por classes/CSS responsivo; estilos
  distintos para título, corpo, nota, legenda, variante e notação; `break-inside: avoid`
  onde fizer sentido; tema que respeite modo escuro e tamanho de fonte do leitor.

Critérios de aceite acrescentados à exportação:

1. EPUBCheck sem erro; Ace sem violação séria; abrir e navegar em Calibre, Thorium e ao
   menos um leitor móvel. O teste verifica manifest/spine/referências e `mimetype`.
2. TOC contém os capítulos esperados, `page-list` contém as páginas e nenhum item genérico
   “Página N” ocupa o TOC principal quando há títulos.
3. Zero imagem informativa com alternativa genérica; todo diagrama com FEN expõe FEN, lado
   e estado, e os não lidos aparecem no relatório.
4. Uma fixture que cruza página, tem título, itálico/negrito, nota, tabela, referência a
   solução e diagrama produz estrutura equivalente em EPUB e DOCX e texto limpo em TXT.
5. PDF pesquisável recebe metadados, bookmarks pelos mesmos títulos, camada na ordem do
   Documento e FEN pesquisável; a opção de preservar paginação não reintroduz cabeçalhos.
6. PGN inclui apenas diagramas/linhas validados, com vínculo à página e relatório dos que
   ficaram de fora; TXT tem opção de marcas de página, nunca cabeçalho corrido por acidente.
7. O relatório de exportação conta páginas, capítulos, palavras sinalizadas, diagramas
   lidos/não lidos, imagens reutilizadas, links quebrados e itens omitidos, com destino para
   cada correção na interface.
8. Saída reprodutível com `SOURCE_DATE_EPOCH`: mesmos dados geram bytes idênticos, inclusive
   ordem do ZIP, UUID, datas, nomes e deduplicação de recursos.

**Execução iniciada em 2026-10-22, ramo `passo-i-treino`.** A exportação dos boxes passou
a ler a estrutura do Documento (`exportar.Estrutura`): a função da área de cada glifo
(título vira `<h1>`/Heading 1 e entra no sumário; as áreas de cabeçalho, rodapé e número de
página saem; a regra das margens corridas continua olhando o livro inteiro, mas não tira o que
o usuário marcou como texto; `ignorar` sai sempre), o negrito e o itálico do glifo (trechos do texto do parágrafo), o parágrafo pedido
e o hífen de quebra decidido. A montagem das linhas continua a da exportação (caixa pela
altura, trechos de coluna, coordenadas), que tem casos medidos; unificá-la com a
`OrdemDeLeitura` do Documento continua esperando a equivalência da caracterização (passo
F). A junção entre páginas é a de `core.pdf_nativo`. Novos formatos: **TXT** (um parágrafo
por bloco, o diagrama numa linha com FEN e lado, marcas `[p. N]` opcionais) e **PGN** (uma
partida por diagrama conferido ou confiável pelos lances, com `Page` e `Diagram`, os NAGs e
os de fora no relatório; CA-12.2 testado). `Opcoes` traz manter margens, só verificadas,
diagramas como recorte e marcas de página (ainda sem diálogo). O `Relatorio` (páginas,
títulos, margens tiradas, diagramas recortados com o motivo, não verificadas, pendentes,
fora do PGN) vai a Resultados / Avisos depois de cada exportação. Da revisão de código: o
estilo não passa do hífen tirado nem cobre letra não marcada entre dois trechos; o PGN recusa
posição ilegal mesmo conferida, e um diagrama estranho não derruba o arquivo; só verificadas
vale também no PGN e lê o estado pelo resumo do livro, sem carregar os modelos. CA-12.6 testado (EPUB e
DOCX iguais byte a byte com o mesmo `SOURCE_DATE_EPOCH`).

**Tarefas.**
1. ~~A exportação passa a ler o Documento estruturado e faz a junção entre páginas.~~
   (Falta "manter quebras de linha e hífens", que depende de os escritores do core
   aceitarem a quebra dentro do parágrafo.)
2. Metadados, capa, idioma das mensagens e opções por formato (o diálogo das `Opcoes`).
3. TOC semântico, `page-list`, landmarks, bookmarks e links internos.
4. ~~TXT e PGN, com validação e relatório do que ficou de fora.~~
5. ~~Pré-visualização em HTML do conteúdo e do relatório antes de gravar.~~ (Rodada 4: o
   botão Pré-visualizar do diálogo da exportação; `exportar.previa` pelo mesmo caminho e
   opções, `abbychess/previa.py` com a marcação do EPUB e as imagens dentro do HTML, as 30
   primeiras páginas e o relatório inteiro; CA-12.4 e CA-12.5 testados. Da revisão de código: a
   prévia que chega depois de fechar o diálogo é ignorada, fechar o diálogo fecha a prévia e
   libera a memória, Exportar espera a prévia em curso, e a prévia do TXT é o próprio TXT.)
6. Validação automática (EPUBCheck, Ace, referências internas e smoke tests de leitores).
7. Deduplicação/otimização de recursos e divisão dos XHTML por capítulo e tamanho.
8. ~~`SOURCE_DATE_EPOCH` e pacote byte a byte reprodutível.~~
9. Sair dos privados do core.

**Rodada 2 (2026-10-22): o escritor de EPUB próprio** (`abbychess/epub.py`, decisão do
usuário: sem mexer no core). Lê as mesmas `PaginaExtraida` e escreve um XHTML por capítulo
(o `<h1>`, partido também acima de 120 mil caracteres), com a página impressa como âncora
`epub:type="pagebreak"`; o `nav` tem o sumário pelos títulos em dois níveis (sem título,
pelas faixas de páginas), a `page-list` e os `landmarks` (capa, sumário, começo do texto); as
mensagens saem no idioma do livro (pt, en, es, de, fr); os metadados vêm de
`<projeto>/metadados.json` (autores, editora, data, assuntos, direitos, identificador, capa);
a acessibilidade é calculada do que foi escrito (`alternativeText` e `accessModeSufficient`
textual só com todo diagrama em FEN; `accessibilityHazard` `unknown`); o texto alternativo
traz o FEN e o lado com a procedência; imagens iguais viram um recurso só. `epub.conferir`
lê o arquivo escrito (pacote, manifesto, espinha, XML, cada link e âncora) e o que acusar
vai ao relatório; `epub.epubcheck` roda o EPUBCheck quando `ABBY_EPUBCHECK` aponta o jar
(não instalado aqui: baixá-lo pede o sim do usuário). Na fatia do Xadrez Vitorioso (pp.
21–27, projeto da fatia) o EPUB, o TXT e o PGN saem e `conferir` não acusa nada; o
relatório mostrou que a regra antiga das margens tira duas legendas de diagrama da p. 26
como rodapé ("Diagrama 6. Jogam as brancas"), pendência para quando as legendas tiverem
área. Da revisão de código: a fonte dos símbolos estava num `url()` errado (as figurinas
não apareceriam) e o `conferir` não lia o CSS; os caracteres de controle do OCR saem antes
de escrever o XML; livro vazio é recusado em vez de virar pacote inválido; a âncora da página
cai no capítulo do primeiro bloco dela; o `conferir` passou a ler as árvores (ids e itens
repetidos, links decodificados e só para itens do manifesto, `toc` e `page-list` vazios,
metadados obrigatórios); o OPF ganhou `dc:source` e recusa data fora de AAAA-MM-DD; o zip
sai igual no Windows e no Linux.

Estado das tarefas depois da rodada 2:
- 2: feita (rodada 3). Depois do arquivo, o diálogo da exportação (`app/dialogo_exportacao.py`)
  pergunta as `Opcoes` (cada uma habilitada só no formato que a usa, lembradas em`nQSettings) e, no EPUB e no DOCX, os metadados; o formulário vai ao `metadados.json` (atômico,
  a capa copiada para a pasta do projeto) e volta preenchido; em projeto só de leitura vale só
  naquela exportação. O DOCX passou a levar o título e os autores dos metadados. Da revisão
  de código: as chaves escritas à mão no `metadados.json` ficam ao gravar; metadados ruins no
  arquivo não travam a exportação de PDF, TXT e PGN; a capa é validada (PNG, JPEG, GIF, WebP,
  até 20 MB), não é recopiada sobre si mesma, a de outra extensão não fica órfã e, se a
  gravação falhar, vale a de antes.
- 3: feita (rodada 5). O número impresso de cada página sai das margens que a exportação já
  reconhece (`exportar.numeros_impressos`: o deslocamento número − posição mais votado, com ao
  menos duas páginas de acordo, vale para o livro todo; na fatia do Xadrez Vitorioso dá 21–27,
  como o gabarito). Ele vira o rótulo da `page-list` do EPUB e o rótulo das páginas do PDF, e
  as referências do texto ("página 23", "on page 23", "Seite 23", por idioma) viram link para
  a âncora daquela página quando ela está no livro exportado (as outras ficam texto). O PDF
  pesquisável ganha os marcadores pelos títulos do Documento; o sumário e os rótulos que o PDF
  original já tinha ficam. Exportar sobre o próprio arquivo de origem é recusado. Links para
  "Diagrama N" e para capítulos ficam para depois. Da revisão de código: o deslocamento vale por
  trechos de páginas seguidas (o encarte que o livro não numera muda o número dali em diante);
  as páginas sem número (de rosto) ganham romanos no PDF e `[N]` no EPUB, sem colidir com um
  impresso, e a primeira regra de rótulo está sempre na página 0 (senão o PDF fica inválido);
  os rótulos do original são lidos antes do `select`, que os apagava; o caminho do PDF não
  paga mais a comparação n² das margens e carrega cada modelo uma vez; citação de outra obra
  ("Fine, p. 3", "(Informator 45, p. 12)") não vira link; os marcadores não derrubam a
  exportação.
- 6: conferência interna feita; **EPUBCheck 5.4.0** (oficial, w3c/epubcheck, em`nC:\tools\epubcheck-5.4.0`) aprova sem erro nem advertência o EPUB da fatia do Xadrez
  Vitorioso e três sintéticos (capa JPEG e PNG, fonte de símbolos, inglês, alemão,
  subtítulos, recortes, página vazia, capítulo partido). O único erro que ele achou (o
  marco do sumário apontava o `nav` fora da espinha, RSC-011) foi corrigido e o `conferir`
  passou a acusá-lo; `tests/test_epub.py` roda o EPUBCheck quando `ABBY_EPUBCHECK` aponta o
  jar. **Ace by DAISY 1.4.6** (oficial, `@daisy/ace`, instalado em `C:\tools\ace-1.4.6` com o
  sim do usuário) achou duas violações sérias no OPF (sem `xml:lang` no `<package>`; páginas
  sem a fonte da paginação declarada) e nenhuma nos capítulos nem no `nav`; corrigidas (o
  `dc:source` refinado como `source-of pagination`: o `a11y:pageBreakSource` também satisfaz o
  Ace, mas o EPUBCheck 5.4 o recusa, OPF-027). Agora os dois validadores aprovam a fatia e os
  três sintéticos sem violação, erro ou advertência, e `tests/test_epub.py` roda o Ace quando
  `ABBY_ACE` aponta o executável. Faltam os testes em leitores (Calibre, Thorium, móvel).
- 7: deduplicação e divisão por capítulo feitas; falta a otimização sem perda das imagens.
- 9: feita (rodada 6). O DOCX também tem escritor próprio (`abbychess/escritor_docx.py`, pelo
  python-docx): títulos nos estilos Heading 1/2, negrito e itálico, a fonte dos símbolos, os
  diagramas com o texto alternativo do EPUB no `descr`, um marcador `pgN` no começo de cada
  página e hiperlink interno para ele nas referências `página N`, as propriedades pelos
  metadados, o idioma no estilo base, e o zip regravado com a data de `SOURCE_DATE_EPOCH`
  (os mesmos bytes, CA-12.6); `escritor_docx.conferir` relê o arquivo (pacote, XML, imagens,
  marcadores, hiperlinks). Os três privados do core que a exportação usava (`_coluna_de`,
  `_corpo_que_preenche`, `_origem_do_texto`) viraram funções daqui. A aplicação não usa mais
  escritor nem privado do core. Na fatia do Xadrez Vitorioso o DOCX sai e a conferência não
  acusa nada. Da revisão de código, o que o escritor do core fazia e tinha ficado de fora
  voltou, pelas funções públicas dele: a fonte dos símbolos embutida e ofuscada (ECMA-376
  §15.2.13) e nos quatro atributos de fonte, o desenho da página (Georgia 11, justificado,
  recuo, margens de 2,2 cm), cada página impressa começando numa página nova, a largura do
  diagrama pelo tamanho da casa e a legenda visível do diagrama não revisado (PD-21, também
  no EPUB como `<figcaption>`); saíram a miniatura e a data de impressão do modelo do
  python-docx; o DOCX é conferido antes de substituir o anterior. As aspas curvas do core
  (PD-07) não foram trazidas: o texto sai como lido.

**Verificação.** CA-12.1 a CA-12.6; CA-5.3 (parte da exportação).

Em 2026-10-23 (ver "Pendências") saíram todas as da lista abaixo, menos os testes em leitores:
os links, as quebras, as imagens, o golden e o `opcoes.yaml`, as aspas, e também o realce da
baixa confiança no DOCX, que a §12.1 pedia e a lista esquecia.

**Fechado em 2026-10-22, a pedido do usuário, com estas pendências:** os testes em leitores
de verdade (Calibre, Thorium, móvel), que pedem quem os abra; os links para "Diagrama N" e
para capítulos; "manter quebras de linha e hífens" como opção; a otimização sem perda das
imagens; o golden normalizado do CA-12.1 e o `opcoes.yaml` do CA-12.3 (as opções estão
testadas uma a uma, não pela diferença declarada); as aspas curvas do core (PD-07), que os
escritores próprios não aplicam. Os gabaritos do EPUB (EPUBCheck 5.4.0 e Ace 1.4.6) passam
sem violação, erro ou advertência.

## Passo K — Aparência e teclado (§13, §3.4)

**Execução iniciada em 2026-10-22, ramo `passo-i-treino`.** Rodada 1: `app/estilo.py` tem
todos os tokens (`app/cores.py` saiu) e nenhuma cor literal sobra em `app/` (varredura por
AST, CA-13.3). Há os do papel, que nunca invertem (a página, a Linha, o Documento, os
tabuleiros), e os da interface, que seguem o tema do sistema (`Tema` claro e escuro: paleta
Qt e folha de estilo; os rótulos de dica, aviso, erro e acerto têm um papel pintado pelo
tema; o `colorSchemeChanged` troca tudo sem reiniciar). Os estados foram escurecidos na
mesma matiz até ≥ 3:1 contra o papel do gabarito (255) e contra o cinza 230 (CA-13.2, com
o traço de cada estado distinto: o `rede` ganhou um tracejado próprio). Das pendências do
A1: a seleção tem contorno duplo; os diagramas usam os tokens; abaixo de 40% de zoom os
boxes pendentes são só contorno; o glifo atual no Documento tem um azul mais forte. O
`ferramentas/capturas.py` ganhou `--tema`. Da revisão de código: o que guardava cor da interface (a gaveta de
Páginas, os avisos em Resultados) é pintado de novo quando o tema muda (`estilo.avisos`),
as cores de estado sobre a interface escura são clareadas até 4,5:1 (`estilo.na_interface`),
os avisos de conflito e o erro da busca usam a cor do tema, e a varredura de cor literal pega
também `#rgb` e cores por nome.

Rodada 2 (o resto do passo). Os ícones são do Lucide 0.460.0 (ISC; a decisão 5 de §18,
escolhida pelo usuário): só os 25 SVG usados, com a licença, em `app/icones/`, pintados pela
cor do texto do tema e refeitos quando ele muda. Os estados vazios (`app/vazios.py`) dizem o
que fazer com a tecla do perfil em uso, e toda dica ou aviso que cita tecla a tira do perfil
(`teclado.com_teclas`; as dicas das ações seguem a troca). CA-13.1 (`tests/test_acessibilidade.py`)
cobre a janela e os diálogos, com os botões internos do Qt nomeados. O perfil FineReader
entrou com as ações que só ele tem (Ctrl+F7, Alt+4, Ctrl+Tab, Ctrl+1…5), e
**Ferramentas › Teclado…** escolhe o perfil e troca as teclas pelas regras do YAML, sem
reiniciar, lembrado no `QSettings` (os testes usam um INI temporário). Desempenho: a
`QImage` da página nasce na thread que a renderiza (a troca no cache, 23 → 13 ms); a trava
da fonte cobre só o render do fitz, e a medida da inclinação (~370 ms) não segura mais o
clique noutra página; a pré-carga segue o sentido do passo e, quem folheia (trocas a menos
de 1 s), a tem já: parado 0,25 s em cada página nunca vista, ~390 → ~250 ms por troca
(medido no Xadrez Vitorioso, offscreen).

**Pendente.** O render do fitz segura o GIL (~80 ms por página nunca vista, a interface
para nesse tempo durante a pré-carga); tirá-lo da interface pede um processo, como o
servidor de leitura. **Feito em 2026-10-23 para a pré-carga** (`abbychess/render.py`, ver
"Pendências"); a página pedida na hora ainda renderiza aqui. A medida da inclinação (~370 ms) poderia buscar do grosso ao fino, mas
mudaria os ângulos gravados dos projetos novos: fica para quando houver gabarito que a meça.

**Tarefas.**
1. ~~Tokens completos e o tema claro e escuro.~~
2. ~~Os ícones (§18.5).~~
3. ~~Os estados vazios.~~
4. ~~`accessibleName`.~~
5. ~~O perfil FineReader e a reatribuição de atalhos em Opções.~~
6. ~~Pendências do A1 (revisão de produto):~~
   - os tokens de estado do A1 (Okabe-Ito) não dão o contraste de 3:1 do CA-13.2 contra o
     papel (o laranja do pendente, 1,8:1 contra o cinza 230; o roxo, 2,45; o verde-azulado,
     2,74): escolher variantes mais escuras, mantendo os traços distintos;
   - a seleção ainda é um traço amarelo único (§3.3 pede contorno duplo), e os diagramas
     usam a paleta antiga (`cores.py`): passar aos tokens;
   - a conversão do pixmap da página seguinte roda na thread da interface, 400 ms depois de
     trocar (p50 18 ms, máximo 93): fazer a `QImage` na thread da pré-carga.
   - em zoom baixo (22%), o fundo laranja dos boxes pendentes cobre a letra (revisão de
     produto do A2): só o contorno abaixo de ~40%;
   - o fundo azul-claro do glifo atual no Documento é discreto sobre um □ (revisão de produto
     do A3): um tom mais forte;
   - folhear depressa páginas nunca vistas: a pré-carga adiada chega tarde (parado 0,25 s
     por página, ~403 ms por troca); cancelar ou adiar a pré-carga quando outra página já foi
     pedida.

**Verificação.** CA-13.1, CA-13.2 e CA-13.3; CA-3.3 e CA-3.7 nos dois perfis.

## Passo L — Editor de imagem e páginas (§12.4)

**Início em 2026-10-22, ramo `passo-i-treino`.** As decisões do usuário: os glifos
acompanham girar, cortar e dividir (endireitar à mão relê); a página inserida é copiada para
o projeto; apagar guarda a página; cada operação entra no Ctrl+Z. O modelo e os CA-12.7 a
12.16 estão em §12.4; a revisão de arquitetura do mesmo dia trocou o corte e a metade por um
`quadro` inteiro, pôs a `geometria` dos boxes em cada JSON de página (a transformação
preguiçosa, segura contra queda), fixou a ordem das gravações e a cadeia v1 → v2 → v3, e
acrescentou os casos negativos.

As rodadas:
1. A sequência e todo dado chaveado por `pid`, sem operação nova e sem mudar o formato até o
   último subpasso: (1a) o tipo `Sequencia` (posição ↔ `pid`) montado dos dados da v2, com
   um adaptador índice → `pid` na borda da API; (1b) `_modelos`, `_a_gravar`, `livro.json`,
   o índice da busca e `MudancaDaPagina` por `pid`, sem ler o `indice` do JSON de página;
   (1c) renderizar pela entrada, `inclinacoes` e o lote por `pid`; (1d) `janela.json`, as
   listas do `projeto.json`, a origem das amostras e as exportações pela sequência; (1e)
   `VERSAO = 3`, `backup-v2/`, a cadeia v1 → v3, CA-12.7 e de novo CA-4.1 e CA-4.5. Um teste
   por AST reprova método público do `ProjetoDeLivro` que ainda tome `indice`.
   **Feito**: (1a) `abbychess/sequencia.py` (`d53ad1d`). (1b) o `ProjetoDeLivro` monta a
   sequência ao abrir (o número de páginas do PDF, os `pid` do `livro.json`, os arquivos que
   ele não cita, a v1 com `pid` = índice, e todo `p<pid>.json` em disco abaixo do próximo
   `pid`); o cache, as gravações pendentes e o `livro.json` (versão 4) são por `pid`, com a
   página do PDF (`pagina_da_fonte`) no resumo e no `indice` do JSON de página, e não a
   posição; a página editada pela primeira vez usa o `pid` da sequência; perguntar fora do
   livro não cria páginas; o desfazer e o lote acham a página pelo `pid`. O índice da busca
   fica por posição: ele vive só na memória e é refeito a cada sessão, e na rodada 2 é
   rechaveado pelo `pid` que cada página indexada já guarda quando a sequência mudar.
   (1c) a `FonteDePaginas` renderiza pela entrada (a fonte, inclusive `inseridas/`, a página,
   o `quadro`, o `giro` e o ângulo à mão, que vence o medido); o cache de páginas é chaveado
   pela entrada (a página que muda de lugar fica nele; a que muda de geometria sai); o lote
   resolve as páginas em `pid` ao começar, segue a posição de agora e pula a que saiu do
   livro. A chave de `inclinacoes.json` continua o índice do PDF na página do livro sem
   geometria: até a v3 o `pid` das páginas nunca editadas muda de uma sessão para outra, e a
   medida iria parar noutra página; passa a `pid` na rodada 1e.
   (1d) a origem da amostra vem do `gid` dela (`ProjetoDeLivro.origem_da_amostra`: a
   posição de agora, ou "saiu do livro"; a amostra antiga sem `gid` vai à primeira entrada
   da página do PDF do nome); as exportações seguem a sequência: a camada de texto nativa e
   a importação dela só na página do livro intacta, pela página do PDF da entrada e com o
   número da posição; o PDF pesquisável seleciona as páginas do PDF na ordem do livro (e
   recusa, até a rodada 4, a inserida, cortada ou girada); a altura vem da página do PDF da
   entrada. O `janela.json` e as listas de páginas do `projeto.json` (o corpo, a amostra
   guiada, a camada nativa, o lote a retomar) **foram para a 1e**: chaveá-los por `pid`
   antes de todo `pid` ser gravado faria a página nunca editada abrir outra ao reabrir.
   (1e) `VERSAO = 3`: a sequência vai para o `projeto.json` (o projeto novo já nasce com
   ela); a cadeia v1 → v2 → v3, com `backup-v1/` e `backup-v2/` (o `projeto.json`, as
   inclinações, `janela.json` e `lote.json` de antes); a sequência montada dos dados da v2 e
   as listas de páginas passadas a `pid` vão juntas na gravação do `projeto.json`, antes de
   qualquer outro arquivo; depois, `inclinacoes.json` (chave `p<pid>:<quadro>:<giro>`),
   `janela.json` (o `pid` da página aberta) e `lote.json` (`pids`) passam a `pid`, e quem os
   lê aceita a forma da v2 (uma queda no meio não faz medir de novo). Sem gravar na pasta, o
   projeto da v2 abre só para leitura, com a sequência na memória. Na v3, o `p<pid>.json` que
   não está na sequência vai às apagadas, e a página da sequência que o `livro.json` não
   cita volta a ele. Da revisão: a fonte é procurada antes de migrar, e sem ela a v3 espera
   (a sequência curta, de um PDF sumido, nunca é gravada; a gravada curta ganha no fim as
   páginas do PDF que faltam); o que a migração passa a `pid` depois do `projeto.json` é
   completado a cada abertura da v3 (`_completar_v3`), e uma falha ali só avisa; valor
   estragado nas listas sai; o perdedor de dois arquivos da mesma página não vira apagada;
   `salvar` toma a trava do livro; a sequência gravada sem `entradas` é recusada. O
   `backup-v2/` é o da primeira migração: copiado de volta e migrado de novo, ele não é
   regravado. **O JSON de página v3** (sem o índice, com a geometria dos boxes, §4.3)
   **foi para a rodada 3**, com girar, cortar e dividir: é só lá que a geometria muda. O teste
   por AST dos métodos públicos que tomam `indice` não entrou: eles tomam a posição do livro,
   que segue sendo o que a interface usa.
2. Reordenar, apagar e inserir, com a seleção (CA-12.8 a 12.10, 12.15).
   **(2a) feito**: as operações puras na `Sequencia` (mover, apagar, restaurar, inserir); o
   `ProjetoDeLivro.gravar_sequencia` (o `projeto.json` antes da memória) e o
   `inserir_arquivo` (a cópia em `inseridas/` pelo SHA-256, o PDF cifrado recusado); no
   controlador, os comandos, uma transação do desfazer com a sequência antes e depois
   (recusada se a ordem mudou por fora, com o lote ou com uma tarefa em curso), as visitas e
   a página aberta seguindo o `pid`, e `sequencia_mudou`: a busca é montada de novo, o lote
   a retomar volta do `lote.json`, e a janela limpa os pixmaps, a gaveta, a aba Diagramas,
   o seletor e os resultados. A página apagada guarda a vizinha de antes (`depois_de`):
   restaurar todas juntas, ou da apagada mais nova para a mais velha, devolve a ordem exata;
   restaurar uma apagada mais velha antes de uma mais nova, que eram vizinhas, pode trocar as
   duas de lugar. Desfazer um inserir põe as inseridas nas apagadas. **(2b) feito**: o menu
   Página (Mover, Apagar, Inserir, Páginas apagadas…, sem tecla), o menu de contexto da
   gaveta (mover e apagar as selecionadas), os diálogos (`app/dialogo_paginas.py`: a seleção
   conferida enquanto se digita) e o mixin `app/paginas_na_janela.py`; as ações desligam com
   o motivo na dica; a janela segue a ordem nova (o seletor, o total, a gaveta, a busca, os
   resultados).
3. Girar, cortar e dividir, com a `geometria` preguiçosa (CA-12.11 a 12.13, CA-4.6).
   **(3a) feito**: a ordem da imagem passou a fonte → endireitar → quadro → giro (§12.4: a
   conta exata); `abbychess/geometria.py` (as caixas entre geometrias), o `tamanho` da fonte
   na entrada (sem renderizar), o JSON de página v3 (`geometria`, `tamanho`, `fora`) e
   `modelo.reenquadrar` ao carregar e ao trocar a sequência; no controlador,
   `girar_paginas`, `cortar_paginas` (as margens do que se vê) e `tirar_o_corte`, que gravam
   só a sequência (o Ctrl+Z é a de antes); a página com boxes guarda o ângulo em que foi
   lida; o glifo cortado fica guardado e volta, e também as áreas, os tabuleiros e os
   diagramas (`areas_fora`); o `angulo` do glifo acompanha o giro. Ficam para a rodada 4:
   endireitar à mão limpa os `fora` (eles estão na página endireitada pelo ângulo de antes);
   o resumo do livro e o índice da busca contam os glifos guardados até a página ser
   gravada; `tamanho_da_fonte` reabre o PDF a cada página (girar muitas de uma vez).
   **(3b) feito**: `modelo.dividir` (os glifos pelo centro, os da direita com gids do `pid`
   novo; as áreas cortadas; as decisões e os virtuais com os glifos deles),
   `ProjetoDeLivro.trocar_paginas` (as páginas inteiras com a sequência e os
   `gids_movidos`, na ordem de gravação da SPEC) e `pagina_igual`; a `Transacao` ganha
   `inteiras` e `movidos`, e o Ctrl+Z junta as metades e apaga o arquivo da direita;
   `origem_da_amostra` segue os `gids_movidos`; no menu Página, **Girar páginas…**, **Cortar
   páginas…**, **Tirar o corte…** e **Dividir páginas…**, com a seleção. As operações de
   página esperam a leitura do servidor pendente chegar. Ficam como estão: as duas metades
   herdam o estado da página (a verificada continua verificada), e o diagrama que passa da
   divisão vai aparado com a leitura de antes.
4. Endireitar à mão e as imagens transformadas nas exportações (CA-12.14, 12.16).
   **Feito**: `modelo.endireitar` (ficam os glifos de leitura digitada ou aceitos na
   revisão, com o centro girado; as áreas do usuário giram; o resto sai, e a página vai a
   `glifos_marcados`) e `ControladorDePagina.endireitar_paginas` (o ângulo na entrada, a
   página trocada inteira com a sequência, como dividir; até 20°; None volta ao medido);
   **Página › Endireitar páginas…**; o PDF pesquisável monta, quando há página inserida,
   cortada ou girada, um PDF novo com o original (`insert_pdf`) e a imagem da entrada nas
   outras. As pendências da 3a: girar e cortar regravam as páginas pelo gravador depois da
   sequência (o `livro.json` e a busca seguem a imagem); endireitar gira o `fora` junto; o
   tamanho da página da fonte sai do documento aberto uma vez.

**Fechamento** (2026-10-23, `docs/revisoes/passo-l.md`): as revisões de código e de produto
voltaram na rodada 1 (o ângulo no Ctrl+Z do giro, dividir medindo na thread da interface, o
`backup-v2/` depois de inserir; dividir o livro preso 108 s, o padrão do endireitar, girar sem
gesto único, a seleção sem paridade com intervalo, os textos); as correções e a ferramenta
`ferramentas/capturas_paginas.py` entraram antes da rodada 2. A rodada 3 aceitou as duas, e
nenhuma nota ficou abaixo de 8.

O primeiro portão reprovou no CA-7.1 pela janela: o índice da busca levou 2,4 s, por uma
regressão do passo F, que detectava as colunas duas vezes por página. Corrigido no core e aqui,
o segundo portão (`071b8e5`) aprovou, com 2,0 s. O lote, o Enter e o clique no Documento
pioraram desde o D2, o último portão medido antes deste. Medidos agora, deram o mesmo no K e
no L, então essas pioras não vêm do L. O registro tem os números. Tag `passo-l`.

**Tarefas.**
1. Dividir páginas espelhadas, girar, cortar e endireitar à mão, em páginas pares, ímpares
   ou num intervalo.
2. Apagar, reordenar e inserir páginas, com `pid` estável, `inclinacoes.json` chaveado por
   `pid` e o `livro.json` coerente.

**Verificação.** CA-4.6; um CA por operação, escrito no início do passo e revisado.

## Pendências (2026-10-23, ramo `pendencias`)

Depois do L, o que os passos deixaram e dava para fazer sem o usuário, sem editar o core e sem
gabarito novo (`docs/revisoes/pendencias.md`, com as medidas):

- O lote voltou a 8,5 s por página (17,2 no L): desde o I (`2bbf0e7`), o negrito convertia a
  página inteira para cinza a cada glifo.
- O clique no Documento voltou a 3,7 ms (10,6 no L) e o Enter caiu para 38,8 (45,8): o aviso
  de ensino do C e o Enter recortam da matriz do cache.
- O roque desmarcado na conferência (H).
- Da exportação (J, §12.1): os links para "Diagrama N" e "capítulo N", manter as quebras e os
  hífens, realçar a baixa confiança no DOCX, as aspas curvas, o PNG sem perda, o golden do
  CA-12.1 e o `opcoes.yaml` do CA-12.3.
- A suíte rápida de 314 para ~102 s (as janelas apagadas no fim de cada módulo; os ícones
  rasterizados uma vez por tema), e dois bugs que isso e o portão mostraram (a troca de perfil
  com uma janela apagada; o aviso de uma thread depois que a janela fechou).
- O Enter que confirma a leitura não monta mais o texto da página para a validação pelos
  lances: ~25 ms na mediana (38,8 antes).

- A exportação lê a página pela `OrdemDeLeitura` do Documento (F, J): as duas liam igual em
  157 de 160 páginas de 8 livros, e nas 3 outras a da exportação inventava colunas.
- A pré-carga renderiza o PDF num processo à parte (K): a interface não para mais ~85 ms a
  cada página nunca vista (a maior parada, 13–14 ms).
- A suíte rápida roda em paralelo (`-n auto`, pytest-xdist): ~32–39 s.

- O itálico no OCR (I), com uma régua do AbbyChessCraft (o core não tem): no Odds & Ends, 0
  falsos em 17.941 palavras retas e ~96% das itálicas (`ferramentas/medir_italico.py`).
- Corrigir um caractere não refaz a ordem de leitura nem as linhas (H): validar a página, 13,6
  → 2,8 ms.
- Manter as quebras na camada nativa devolve o hífen que o core tirou (J).
- O EPUB conferido no Calibre (J, `epub.calibre`).
- Os processos do índice da busca morrem com o programa morto à força.

- CA-10.1 com a redação nova (com o sim do usuário): a precisão 1,0 nos FEN do gabarito e a
  detecção ≥ 60% das perturbadas afetadas, as não afetadas fora da conta.

Continuam: CA-9.1 e CA-F.1 (o texto verificado); o EPUB no Thorium e no celular. A página pedida na hora renderiza
na thread da interface por decisão (o registro diz por quê).

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
- **0.6 (2026-10-16)** (fechamento do passo 2a, `docs/revisoes/passo-2a.md`): o critério de
  desempenho do 2b foi refeito (o p95 da releitura já está no alvo; o do Enter ≤ 100 ms em 2
  de 3 rodadas; a memória do desfazer ≤ 50 MB); o 2b religa o painel de treino logo depois
  da parte síncrona do Enter.
- **0.7 (2026-10-16)** (fechamento do passo 2b, `docs/revisoes/passo-2b.md`): o
  congelamento da coleta de lixo saiu (`ABBY_CONGELAR=1` religa); os passos seguintes medem
  3 rodadas (sem o A/B do congelamento) e o Enter até a cor mudar, com o painel de texto à
  parte (`texto_da_pagina`); o Reler pendentes entrou no desfazer.
- **0.8 (2026-10-16)** (revisão de produto do A3, `docs/revisoes/passo-a3.md`, com o sim do
  usuário): o prazo da verificação do texto e dos FEN da fatia passou do fechamento do A3
  ao do D1, e o alvo de ≤ 85% do CA-F.1 depois do A3 saiu (o A3 é só leitura; o replay não
  ganha comando mais barato com ele); o D1 é o primeiro passo julgado pelo CA-F.1.
