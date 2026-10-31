# Passo Q7 — cortar os objetos-deus (em andamento, ramo `qualidade-q7`)

Oitavo passo de `plans/roadmap-qualidade.md`, a partir do `08a0080` (o Q6 mesclado no
`passo-i-treino`), na worktree irmã `C:\Python-Chess2\AbbyChessCraft-qualidade`. O roadmap
pede um corte por sessão; cada corte pina o comportamento, muda a estrutura e prova que nada
mudou com a mesma suíte.

## Cortes feitos

| Corte | Commits | O que mudou |
|---|---|---|
| 1. `aplicar_lida` (CA-Q-A2, parte 2) | `1c70d7f` o teste que pina o F5 e o lote na mesma página; `1015cb4` a função | `abbychess/arrumacao.py`: `arrumar(pagina, idioma)` (os ids, as legendas, os lances validados), usada por `_mudou` e `depois_de_editar`; `aplicar_lida(pagina, lida, idioma, tamanho=, zona=)`, usada pelo F5 e pelo lote. O pipeline "depois de ler" estava em quatro lugares |
| 2. `EstadoDaJanela` (CA-Q-A2, parte 1) | `6366d2f` o teste sem janela (vermelho); `2ce37e4` o módulo | `abbychess/estado_da_janela.py`: `calcular(p, livro, vista)` dá, por ação, None ou o motivo de não valer, as operações de página com a dica, e os textos do desfazer; `acoes.atualizar` só aplica; o alias `editar = tem` saiu |
| 3. `ControladorDePagina` (CA-Q-A1) | `5087723` as alavancas; `cc35249`, `5382db1`, `82c6c4a`, `85b2d7f`, `2216611`, `d97cf71`, `69b2ae8` um colaborador cada; `3ba3588` o alinhamento; `c2a17e0` o teste do tamanho | sete colaboradores, cada um no seu módulo e chamado pelo atributo: `Navegador` (`p.navegador`, as visitas e a pré-carga), `ControladorDaSequencia` (`p.operacoes`, §12.4), `AplicadorDoHistorico` (`p.desfazedor`, o Ctrl+Z e o Ctrl+Y), `ControladorDaSessao` (`p.sessoes`, a sessão do Documento), `ControladorDosPadroes` (`p.padroes_do_livro`, o esquecer e os limiares), `PonteDeLeitura` (`p.leitura`, o leitor e o servidor), `FilaDaPagina` (`p.fila_da_pagina`, §8.1). O controlador: de 2 620 para 888 linhas, de 143 para 61 métodos |
| 4. `ProjetoDeLivro` (CA-Q-A1, Q-P9) | `16dad3a`, `f53a462`, `3e4e3e5`, `be3f8d3`, `ebb35e1`, `ce401f8`, `572f2fc` um módulo cada; `37e97bf` o teste da cópia (vermelho); `712cd9d` a cópia; `e657a72` a fonte única | módulos: `pagina_em_json.py` (as funções da página em JSON), `pasta_do_projeto.py` (os nomes da pasta), `Migracoes` (`projeto.migracoes`, v1 e v2 → v3), `AntesDoLote` (`projeto.antes_do_lote`), `ResumoDoLivro` (`projeto.resumo`, o `livro.json`), `FonteDoLivro` (`projeto.origem`; a propriedade `fonte` delega), `CacheDoProjeto` (`projeto.paginas_em_memoria`; `cache` já é o das imagens no controlador), `SequenciaDoLivro` (`projeto.ordem`; a propriedade `sequencia` delega). Q-P9: `carregar_pagina` entrega cópias dos `BoxEntry` (1,5 ms numa página de 2 000 glifos; a busca, a galeria e o resumo não passam por ele); o `Projeto` perdeu `sequencia` e `proximo_pid`, montados da `ordem` ao gravar. `projeto.py`: de 2 215 para 950 linhas (saiu de `TETOS`); o `ProjetoDeLivro`: de 108 para 43 métodos |
| 5. A exportação (CA-Q-A1, Q-E5, Q-E6) | `0143296`, `6f76eea`, `2487738` a alavanca e as correções dela; `27093cc`, `da7551f`, `3f8e9da`, `d45b59e` um módulo cada; `e8788e0` o teste do idioma (vermelho); `2bc917a` o `Pedido`; `8ff9681` a marcação comum; `64b6440` o `PECAS`; `f514880` o teste das letras de lance (vermelho); `ecd09bd` as letras; `2ebdb57` o teste das regras únicas | módulos: `metadados.py` (o `metadados.json`, a capa, os `epub.Metadados`), `montagem.py` (a `Estrutura`, as linhas e as palavras, os parágrafos, as figuras, a `pagina_extraida`), `margens.py` (as margens corridas e os números impressos), `pedido.py` (as `Opcoes`, o alvo, o idioma e o `Pedido`), `pdf_pesquisavel.py`, e `marcacao.py` (os trechos marcados e a ressalva do diagrama, comuns ao EPUB e ao DOCX). O `Pedido` resolve a exportação uma vez: o idioma pela camada do PDF sai uma vez por exportação e por prévia (eram duas). Q-E5: o `PECAS` só no `modelo`; as letras de lance do `contexto` e do `zonas` saem dele (um livro em alemão ou espanhol tinha o lance de cavalo e de bispo improvável, e a linha de lances virava título); `tests/test_regras_unicas.py` pina as quatro regras. `exportar.py`: de 2 130 para 674 linhas (saiu de `TETOS`); `epub.py`: de 1 154 para 1 144 |

Verificação de cada um: a rápida inteira com -n 4 (de 1917 a 1927 passaram, 3 pularam,
74–85 s); ruff E,F limpo; os testes de desempenho com chamada trocada rodados à parte; no
corte 4, a camada `processo` no fim de cada rodada (36 passaram; na última, o
`test_ca_9_4` derruba o worker com -n 4, e a mesma queda vem da base `ebb35e1`; sozinho,
passa). No corte 5, também o golden da exportação a cada commit: a fatia (p. 21–27 do
Xadrez Vitorioso) lida uma vez num projeto do scratchpad, exportada nos cinco formatos em três
jogos de opções (o padrão, só verificadas, e tudo ligado: margens, quebras, marcas, realce,
links, diagramas como recorte), com os relatórios e as prévias: 37 arquivos, os mesmos bytes
da base `e0bd444` do começo ao fim. A medida da exportação (`medir_exportacao.py`, em
`docs/medidas/2026-10-31-exportacao-xv.json`), comparada com a da base `e0bd444` medida em
seguida numa worktree temporária: os mesmos bytes e o mesmo resumo nos cinco formatos, o EPUB
aprovado no EPUBCheck, no Ace e no Calibre, e o p50 dentro do ruído (EPUB 1 469 → 1 450 ms,
DOCX 1 565 → 1 534, TXT 1 101 → 1 090, PGN 7,5 → 7,4, PDF 2 962 → 2 982).

## O que falta

3. O resto do `ControladorDePagina`: 61 métodos para o teto de 40 (as edições: corrigir,
   dividir, juntar, marcar, ajustar; a seleção; o que a janela lê).
4. O resto do `ProjetoDeLivro`: 43 métodos para 40 (os seis ajudantes do desfazer da
   divisão: `pagina_do_pid`, `_carimbo_do_pid`, `_intocada`, `proximo_n_de`, `pagina_igual`,
   `gid_de_agora`).
5. Da exportação: a exportação consumindo `texto.montar` inteira (o fim do Q-E6) muda o texto
   exportado e não é corte de estrutura; o idioma do livro tem dois detectores (o do core, pt
   e en, na exportação; o de `idioma.py`, cinco idiomas, no projeto novo), e escolher um muda
   o `dc:language` (decisão do usuário); os privados que um módulo novo pede ao outro
   (`_linhas`, `_Linha`, `_quebras_da_camada`, `_juntar_entre_paginas`,
   `_funcoes_das_margens`, `_funcoes_dos_candidatos`) ficam para o Q8.

O CA-Q-A1 pega também `controladores.py` (2 055), `pagina.py` (1 446) e `epub.py` (1 144), e
as classes `VistaDoDocumento` (58 métodos), `EspacoDeTrabalho` (53) e `VisorDePagina` (55),
que o roadmap não lista. Todos estão em `TETOS` de `tests/test_tamanho_dos_modulos.py`, com o
tamanho de hoje: o teto só desce.

## Registro

| Ação | Por quê |
|---|---|
| O teste do corte 1 pina os dois caminhos antes de juntá-los | o CA pede a comparação; ela passou no código de antes, e passou igual depois |
| A primeira versão dos dados do teste não cabia na página sintética (900 × 260) | o diagrama sumia (o `mesclar` só guarda o que a leitura traz); refeitos para caber |
| O F5 passa `evento=None` ao `_mudou` | o estado já vem de `aplicar_lida`; reconhecer duas vezes mudaria o estado em dobro |
| As leituras do `calcular` ficam atrás do `pronto` | o `and` do `atualizar` antigo cortava a leitura da visita sem página; a primeira rodada reprovou 332 testes por isso |
| Corte 3: primeiro as alavancas (`mover_metodos.py`, `trocar_chamadas.py`), com teste | cem métodos e centenas de chamadas não se conferem de relance; um grupo à mão (o Navegador), depois a ferramenta igual a ele |
| As chamadas trocadas só nos receptores que são o controlador, com a contagem conferida | `desfazer`, `reconhecer`, `fila`, `girar_paginas` também são da janela, do Documento, do editor de diagrama, dos executores: esses ficaram |
| Os grupos do desfazer em diante, um subagente por rodada, um de cada vez, revisados aqui | a mesma worktree e os mesmos arquivos: nunca dois escritores juntos; o diff e os números conferidos antes de seguir |
| `AVISO_LONGO_MS` foi para `avisos.py` e `Antes` para `historico.py` | o módulo novo não importa o controlador, que o importa |
| Um `avisos.py` sobrescrito por engano no meio do corte, restaurado do git antes de qualquer commit | o arquivo já existia (o log de avisos); o roteiro dos subagentes manda conferir antes de sobrescrever |
| A fila de glifos não foi juntada ao `ControladorDaFila` (a spec propunha) | ele é da janela (o modo da revisão, o escopo página/livro) e a fila da página precisa valer sem janela (o lote, os testes); juntar faria uma dependência circular na construção: virou `FilaDaPagina` |
| Privados que outros chamam viraram públicos no colaborador (`aplicar_sequencia`, `procurar_no_livro`, `propagar`, `emendar`, `servidor_para_pedir`, `depois_de_ensinar`, `guardar_lugar`, `lendo`) | nenhum colaborador lê privado de outro; os serviços gerais do controlador (`_avisar`, `_falhou`, `_gravar`, `_mudou`, `_agora`, `tarefa`) ainda são chamados por `self._p._…`: ficam para o Q8 |
| A contagem de métodos dos dois primeiros commits do corte (140 → 129 → 114) difere da do `ast` (143 → 132 → 117) | o primeiro mapa contou nomes únicos (o getter e o setter de uma propriedade, uma vez só); dali em diante, a conta do `ast`, a mesma do teste do tamanho |
| `app/janela.py` está com 499 linhas, no teto de 500 do teste de arquitetura | só anotado: nada do corte 3 o tocou além dos receptores |
| Corte 4 em três rodadas de subagente (JSON, migrações, antes do lote; resumo e fonte; cópia, cache e sequência), com a camada `processo` no fim de cada uma | o projeto é aberto, migrado e travado entre processos: a rápida não pega tudo isso |
| As propriedades `fonte` e `sequencia` ficam no projeto, delegando | mais de cem chamadas cada, e o mesmo nome é a fonte das páginas renderizadas e a sequência pura (`sequencia.py`): trocar uma a uma era risco sem ganho |
| A cópia do `Box` só no `carregar_pagina` | `carregar_modelo` e `pagina_para_editar` precisam do objeto vivo (a janela, o lote, a substituição o editam, e o gravador o grava, Q-P3); quem muda a caixa de um glifo no lugar e grava por listas ganha um gid novo para ele (nenhum chamador de hoje faz isso) |
| A fonte única da sequência e do pid sem teste vermelho | procurado um cenário de divergência com resultado errado visível (o pid repetido depois de inserir e reabrir, a ordem velha gravada), e nenhum apareceu: mudança estrutural com a suíte como pino; quem ler `dados.sequencia` agora quebra, e não lê uma cópia velha |
| `pid_da_pagina` e `_pid_em` viraram um só, `ordem.pid_em` | davam a mesma resposta (84 chamadas) |
| Os colaboradores do projeto ainda alcançam privados dele por `self._p` (`_trava_do_livro`, `_gravar`, `_gravar_instantaneo`, `_bilhetes`…) | como no corte 3: fica para o Q8 |
| Os `docs/medidas/2026-10-31-medida-parcial*.json` não versionados | gerados pelas rodadas de `tests/desempenho/`; ficam fora dos commits |
| Corte 5: o golden da exportação antes de mexer, a fatia lida uma vez | a lição do Q3: a suíte não pegou a regressão do glifo não lido; o golden compara os bytes de cada formato com a base, sem reler |
| Uma alavanca nova, `mover_definicoes.py`, e duas correções dela no caminho | a primeira aplicação (desfeita antes do commit) pôs uma linha em branco no import e separou as constantes vizinhas; a segunda deixou sem import a outra função do `replay_fatia` que importa o `exportar`; cada defeito virou um caso do teste do brinquedo |
| O `exportar` continua importando as `Opcoes` e o `NadaParaExportar` do `pedido` | é a porta de entrada: os 61 `ex.Opcoes` ficam; os nomes internos (a montagem, as margens, o PDF, os metadados) os chamadores pedem ao módulo deles |
| O log dos metadados, da montagem e do PDF passa a ter o nome do módulo | nenhum teste filtra pelo nome `abbychess.exportar` |
| O `controladores.py` ganhou um import por corte e perdeu uma linha cada vez (um `p, projeto` numa linha, um `setdefault`) | a catraca do tamanho reprovou os dois: o teto só desce |
| O `pedido.py` e o `pdf_pesquisavel.py` num commit | o PDF precisa do `NadaParaExportar` e do `Progresso`, que moravam na porta de entrada |
| O idioma do `Pedido` é um `cached_property` | o PGN e o PDF pesquisável não o leem e não devem abrir o PDF para isso; a camada só o pede depois de saber que há trecho a ler, como antes |
| A ressalva do diagrama na prévia: o teste vermelho foi desfeito | a prévia já a mostra, no texto alternativo à vista; a repetição era só de estrutura (o EPUB e o DOCX montando a mesma frase), e o golden a pinou |
| A `Estrutura` continua chaveada pelo `id()` do `BoxEntry` | a exportação lê `carregar_modelo` (os objetos vivos; a cópia do corte 4 é só do `carregar_pagina`) e a montagem não copia caixas: nenhum caminho de hoje perde o estilo, e um teste honesto não acha o defeito |
| As letras de lance do `contexto` e do `zonas` por um subagente, revisado aqui | TDD em dois commits (5 falhas: o espanhol, o alemão e o francês); o golden em português ficou igual |
| O lado do PGN com o diagrama conferido (`lances.py:504`, "suspeita" na spec) não foi investigado | fora da estrutura da exportação; fica a suspeita, para o Q8 ou um passo próprio |
