# Auditoria de testes e confiabilidade: AbbyChessCraft

Worktree `C:\Python-Chess2\AbbyChessCraft-coordenadas`, commit `262d897`, 2026-11-05.

**Como foi feito.** Leitura estática dos arquivos, `git`, `gh repo view` e dois scripts AST sobre `tests/` e
`abbychess/`. Nada foi editado, e não rodei pytest nem medida. Os resultados de execução citados vêm dos JSON já
gravados em `docs/medidas/`. Nenhum achado foi reproduzido em execução: "Fato" é o que está no código ou nos JSON,
e "Inferência" e "Opinião" vêm marcadas.

## Resumo

A suíte é boa no que testa: comportamento, sem mocks, com falhas e matanças reais. O ponto fraco é o que está
fora dela. O OCR, razão de ser do produto, não tem nenhum portão automático, e 7 das 10 metas de desempenho da
§2 não têm corte. O diagnóstico depende de um log que só existe no stderr.

**Nenhum Crítico.** Não achei perda de dados nem saída errada em curso. A qualidade de hoje está estável: o CER
do corpo deu 2,76% no `262d897`, contra 2,80% em 10-28 (Q1).

| Id | Grau | Achado | Correção mínima |
|---|---|---|---|
| Q1 | Alto | Nenhuma camada reprova por qualidade de OCR; a medida é manual e sempre devolve 0 | teste com catraca sobre `medir.medir` |
| A1 | Alto | 7 das 10 metas da §2 sem corte; CA-11.7 estourado com o portão verde | `_portao` nos testes de linha de base e servidor |
| A2 | Alto | O "log do programa" não existe em arquivo; erro solto não chega ao usuário | arquivo rotativo, `faulthandler`, aviso no excepthook |
| A3 | Alto | Servidor de leitura (~1 GB) fica órfão se a interface morrer | `vigiar_o_pai()` em `_principal`, com teste |
| A4 | Alto | Falha na camada do PDF: o livro inteiro sai do OCR, sem aviso | não descartar trechos; avisar no relatório |
| A5 | Alto | Não instala fora do PC do autor; sem CI; portão é honra | declarar dependências, tirar o YAML de `docs/`, lock, CI ou gancho |
| A6 | Alto | Gabaritos com texto de livros em repositório **público**, contra a SPEC | decisão sua |
| M1 | Médio | Filho travado (vivo) não é morto: 600 s por página | matar e reabrir no timeout |
| M2 | Médio | Página que derruba o filho prende o lote para sempre | contar quedas por página |
| M3 | Médio | JSON v1 estragado impede abrir o projeto, sem mensagem | isolar como a v2; pegar o erro em `abrir_pasta` |
| M4 | Médio | Mutação cobre 13% do código e não tem "função vazia" | novo operador; rodar nos módulos de dados |
| M5 | Médio | A suíte não reprova erro logado | fixture autouse contra ERROR/CRITICAL |
| M6 | Médio | Sem ponta a ponta com servidor até a exportação | um teste `processo` |
| B1–B3 | Baixo | Segurança sem achado sério, `except` estreitos, documentação defasada | ver no fim |

## 1. Valor real dos testes

### O que está bom (Fato)

Varredura AST de `tests/`: 1.869 funções `test_` em 137 arquivos (~2.430 com a parametrização).

- **0 `MagicMock`/`Mock`, 0 `assert_called`/`call_count`.** Há 234 `monkeypatch.setattr`, os mais comuns na
  fronteira: `gv` (29, injeção de falha de disco), `QMessageBox` (26), `pg` (15).
- Só 4 testes sem nenhum `assert`, direto ou por ajudante, todos em `tests/desempenho/test_linha_de_base.py`
  (ver A1).
- Testes de CA que conferi e são honestos:
  - `test_gravador_processo.py:70-89`: mata de verdade em 50 pontos e valida todo JSON.
  - `test_portao.py:30-70`: testa o próprio portão num pytest filho.
  - `test_coluna_de_tabuleiros.py:230-258`: CA-5.2 em página real, com Kendall 0.
  - `test_lances.py:303`: CA-10.1, sobre os FEN do gabarito, como a SPEC pede (`SPEC.md:697`).
- `medir.py` é honesto ao rotular: o resumo traz `estado: provisória` e o motivo (`medir.py:356-390`).

### Limite do que afirmo

Não dá para dizer quantos testes passariam com função vazia sem rodar nada, e o mutador da casa também não
responde isso (M4).

### Q1 (Alto, o primeiro da fila): nenhuma camada reprova por qualidade de OCR

**Fato**

- A SPEC marca CA-5.1, CA-9.1 e CA-F.1 como `[livro_real]` (`SPEC.md:416, 662, 1124`). Os testes com esses nomes
  são sintéticos: `test_zonas.py:294`, `test_medir_legendas.py:1` ("sem PDF"), `test_replay_fatia.py:1` ("PDF
  sintético").
- `ferramentas/medir.py:525-534` e `ferramentas/replay_fatia.py:725` gravam o JSON e devolvem 0 sempre. O CER não
  aparece em nenhuma asserção real: as duas únicas ocorrências em testes são sobre dados fabricados
  (`test_medir.py:96`, `test_resumo_medidas.py:72`).
- O que os testes `livro_real` afirmam:

| Teste | Afirma | Pega piora de leitura? |
|---|---|---|
| `test_servidor_livro_real.py:43-46` | filho == processo; `len(boxes) > 500` | não: os dois lados pioram juntos |
| `test_suite.py:190-192` | `base` e `ocr` não são None; **`rede` não é conferida** | não |
| `test_coluna_de_tabuleiros.py:248-258` | ordem das linhas, 85% casadas por caixa | não olha o caractere |
| `test_documento.py:427-458`, `test_espaco.py:547-569` | x-height na tela | não |
| `test_treino_por_livro.py:165-174`, `test_diagramas.py:298-321` | segmentação e FEN do Darcy p. 26 | só diagramas |
| `tests/desempenho/*` | tempo e memória | não |

- `docs/medidas/2026-11-05-medida.json`: 28 medidas, nenhuma de qualidade.
- Até hoje, a última qualidade versionada era `2026-10-28-qualidade-xv*.json` (CER 2,8%), nos commits `8194283` e
  `cd6681a`: **243 e 214 commits em `abbychess/`** sem medida (`git rev-list --count`). Parte é refatoração, mas
  `pagina`, `montagem`, `zonas`, `texto`, `efeitos` e `leitor` mudaram.
- Durante esta auditoria, a medida em curso gravou `docs/medidas/2026-11-05-qualidade-xv.json` (ainda fora do
  git), no `262d897`, sobre a árvore limpa: CER 0,0276, 7/7 diagramas, 0 casas erradas, legendas 17/17, cabeçalho
  P = R = 1,0, lado 2/5. **Nada piorou, mas só se soube porque alguém rodou à mão e leu.** Ela leva
  `lote_s: 452,5` (9 páginas), acima do orçamento de 5 min da camada (`SPEC.md:1056`), o que pode explicar a
  ausência no portão.
- A medida não registra o que mais muda a leitura: o commit do core e o SHA do modelo não estão em
  `tests/desempenho/conftest.py:87-107`, `ferramentas/comum.py:25-37` nem em `medir.py:458-466`.

**Cenário concreto que nenhuma camada pega.** O `custom_model.pth` some, ou deixa de abrir:
`NeuralPredictor.load` devolve falso (`core/neural_trainer.py:741-742`), e `leitor.py:127` dá `rede=None`. A
leitura cai para o k-NN.

1. A rápida passa: ela não usa os modelos (`conftest.py:112-124`).
2. A `processo` passa: fora o teste do passo 4, ela usa leitor falso.
3. `test_suite.py:192` passa: não olha a rede.
4. O teste de equivalência compara filho sem rede com processo sem rede e acha iguais.
5. As medidas de tempo melhoram.
6. O único sinal é um `QMessageBox.warning` (`dialogos.py:344-346`), que `test_carregar_modelos.py:38-39` troca
   por nada.

Variantes com o mesmo desfecho:

- Trocar `custom_model.pth`: está fora do git no PyBoxEditor, então não gera commit em lugar nenhum.
- Mudar `Limiares.rede`.
- OpenCV 5: o core avisa que ele "altera limiares de segmentação medidos" (`requirements.txt`, `<5`), mas o
  `pyproject.toml:15` daqui não tem teto, e o README instala o core com `--no-deps`.

**Respondendo à pergunta:** os limiares não são frouxos. Eles não existem.

**Menor correção** (~40 linhas):

- `tests/test_qualidade_livro_real.py`, marcado `livro_real` com timeout próprio de 15 min (ou com um marcador à
  parte, no portão), chama `medir.medir("xv", pdf, 20..26)` e aplica uma catraca sobre o que já é medido:
  - `cer_corpo` ≤ 0,030;
  - `casas_erradas_por_diagrama` == 0;
  - `diagramas_achados` 7/7;
  - `ligacao_da_legenda` 17/17;
  - cabeçalho com P = R = 1,0 (CA-5.1);
  - `linhas_perdidas` ≤ 1.
- O mesmo para `gestos` do replay, se o tempo couber.
- `assert leitor.rede is not None` em `test_suite.py:192`.
- O commit do core e o SHA-256 do `.pth` no `_ambiente` e no `medir`.

Os valores de partida já existem: são os do JSON de hoje. Falta decidir o orçamento de tempo da camada.

### A1 (Alto): 7 das 10 metas da §2 não têm corte

**Fato.** `SPEC.md:53` diz que "o corte que reprova é alvo × 1,2". `tests/desempenho/conftest.py:6-7` diz que "os
passos que perseguem uma meta acrescentam o portão". Não foi feito para estas:

- `test_linha_de_base.py`: troca de página (`:78`, `:98`), Enter (`:183`, `:244`), releitura (`:287`), memória do
  desfazer (`:320`), clique (`:388`). Os únicos `assert` do arquivo são de espera (`:56`, `:75`).
- `test_servidor.py`: atraso e memória no lote (`:94`), releitura com o lote (`:182`), lote com e sem servidor
  (`:214`). Só `assert` de espera (`:41`, `:66`, `:268`).
- O corte existe só em `test_busca.py`, `test_revisao.py`, `test_visor.py`, `test_sessao.py`, `test_substituir.py`
  e `test_carregar_modelos.py`.

**A prova está nos JSON.** CA-11.7 pede p95 ≤ 150 ms (`SPEC.md:752`), corte 180:

| Medida | `releitura_com_o_lote` p95 | exitstatus |
|---|---|---|
| `2026-11-03-medida.json` | **241,09** | 0 |
| `2026-10-28-passo-fechamento.json` | **218,77** | 0 |
| `2026-11-04-medida.json` | 179,57 | 0 |
| `2026-11-05-medida.json` | 143,87 | 0 |

`qualidade-Q9.md:106` registra "22 de 22 passaram" sobre o `2026-11-03`.

**O único tempo que reprovou é ruído.** O CA-7.1 tem corte de 2.400 ms e deu 2824, 2580, 2559, 2416, 2541, 3003,
2692, 2412, depois 2271, 2364, 2380. São oito `medida-falhou` seguidas (10-30 a 11-01), aceitas com explicação
(`qualidade-Q9.md:107-109`).

**Opinião:** é a pior combinação. O vermelho habitual ensina a ignorar, e as metas que o usuário sente não podem
ficar vermelhas.

**Cenário.** Uma mudança leva o Enter de 53 para 119 ms, o lote de 8,6 para 30 s por página (sem alvo nenhum) e a
memória com o lote de 2,1 para 6 GB, numa máquina de 16 GB que já travou por memória. O portão fica verde; o
número muda no JSON e ninguém é avisado.

**Menor correção.** Levar o `_portao` de `test_busca.py:67` ao `conftest` e chamá-lo nas sete metas. Decisões
suas: o que fazer com a releitura com o lote, que oscila em torno do corte, e com o CA-7.1 (mediana de mais
rodadas, ou rever o alvo). Mantê-los sempre vermelhos é o pior caminho.

## 2. Lacunas

### A3 (Alto): o servidor de leitura fica órfão quando a interface morre

**Fato**

- `render.vigiar_o_pai` existe (`render.py:46-58`) e é usado pelo render (`render.py:124`) e pelo pool do índice
  (`busca.py:265,273`), mas não pelo servidor: `_principal` (`servidor_de_leitura.py:413-419`) não o chama.
- O teste de órfão do servidor só cobre o fechamento limpo (`test_servidor.py:109`,
  `test_servidor_janela.py:115`). O de morte à força é só do pool (`test_render.py:164`).
- `docs/revisoes/pendencias.md:112-117` já registrou esse defeito no pool: doze processos parados.

**Inferência (não reproduzido).** No Windows, `daemon=True` só vale na saída ordenada. O filho guarda as duas
pontas da fila, então não recebe EOF e fica para sempre em `_receber` (`:265-273`). Se a interface cair (falha
nativa do Qt, encerrar pelo Gerenciador), sobra ~1 GB (`servidor_no_fim_mb: 1031`). Numa máquina de 16 GB com
histórico de travamentos, cada queda piora a seguinte.

**Menor correção.** `render.vigiar_o_pai()` no começo de `_principal`: o filho só lê, então `os._exit` não põe
dados em risco. Mais um teste copiado de `test_render.py:164`.

### M1 (Médio): filho travado, mas vivo, não é tratado

**Fato**

- `_caiu` só dispara com o processo morto (`servidor_de_leitura.py:574-575`).
- No lote, o timeout cancela e levanta (`lote.py:293-295`); o `cancelar` vai a um filho que não lê. A página vira
  falha e a próxima espera mais 600 s (`:322-328`).
- `render.py:14` mata o filho travado; o servidor não.
- `grep` por `TEMPO_DO_PEDIDO` em `tests/` não acha nada.
- `_proxima_do_filho` só pega `queue.Empty`, `EOFError` e `OSError` (`:571-578`). **Inferência:** um erro ao
  desserializar mata o ouvinte, que é o único vigia. Um resultado que não serializa cai na thread interna da fila
  e não vira resposta, e quem pediu espera os mesmos 600 s.

**Cenário.** Filho preso em paginação ou deadlock: um lote de 230 páginas leva até 38 horas falhando, página a
página. No F5, a fila de tarefas fica presa por 10 minutos (`ponte_de_leitura.py:108`).

**Correção.** No `TimeoutError`, `processo.kill()` e `_caiu("não respondeu")`, e `except Exception` em
`_proxima_do_filho` chamando `_caiu`.

### M2 (Médio): página que derruba o filho prende o lote

**Fato.** Na queda dupla a página não sai de `restante` (`lote.py:310-317`), e `reinicios` nunca zera
(`servidor_de_leitura.py:623-629`), então duas quedas em horas de lote bastam para desistir. Retomar relê a mesma
página, que derruba de novo, e o usuário não tem como pular.

**Correção.** Na desistência, marcar a página em curso em `falhas` depois de duas quedas nela, e zerar `reinicios`
a cada resposta com sucesso.

### M3 (Médio): JSON v1 estragado impede abrir o projeto, sem mensagem

**Fato**

- `_ler_v1` faz `json.loads` sem guarda (`migracoes.py:69`), chamado em `migrar_a_v1:101`.
- `_abrir_para_gravar` só pega `OSError` (`projeto.py:291-295`); `abrir_pasta` só pega `ProjetoInvalido`
  (`dialogos.py:271-275`). O erro vai ao `excepthook`, que só loga (A2).
- O caminho só de leitura trata isso (`migracoes.py:116-119`).
- `preparar_migracao` já gravou `versao=2` (`:138-139`), então toda abertura seguinte repete a falha.
- `test_migracao_v1.py` não tem caso de JSON estragado.

**Cenário.** Projeto antigo com uma página cortada: clicar em Abrir não faz nada, sempre.

**Opinião:** grau Médio porque v1 é formato antigo; se não restar projeto v1, é Baixo. A parte que vale para
qualquer versão é o `abrir_pasta` só pegar `ProjetoInvalido`.

**Correção.** Isolar como `_isolar_a_ilegivel`, e `except Exception` com aviso em `abrir_pasta`.

### M6 (Médio): falta um ponta a ponta

**Fato.** `test_servidor_janela.py` cobre bem o lote pelo filho (CA-11.x), mas nenhum teste segue até exportar. A
exportação pela janela está em `test_janela_livro.py:179-249`, sem o filho. `ferramentas/medir_exportacao.py` faz
o fluxo real, mas é ferramenta e não reprova; a última medida é de 10-31.

**Correção.** Um teste `processo` com leitor falso: PDF sintético, lote pelo filho, matar o filho, retomar, fechar,
reabrir, exportar EPUB, `conferir`.

### Persistência: o que está bom (Fato)

- Gravação atômica com `fsync` e novas tentativas (`gravacao.py:171-191`).
- Escritor único por bilhete (`projeto.py:538-546`).
- Trava entre processos (`gravacao.py:102-122`).
- Versão mais nova abre só para leitura (`projeto.py:236-237`).
- Página ilegível vai à parte, sem perda (`projeto.py:410-431`).
- Backup antes de migrar (`migracoes.py:126-134, 150-156`).
- Disco cheio: a página fica suja, com aviso e nova tentativa (`gravador.py:9-11, 171-197`), e fechar pergunta
  antes de perder (`janela.py:346-353`).
- Exportação confere antes de trocar o arquivo (`gravacao.py:194-222`, `test_gravacao_da_exportacao.py:67`).

Menor: `gravar_por` não faz `fsync` no arquivo exportado (perda só em queda de energia).

### Concorrência: o que está bom (Fato)

Reabertura com reenvio dos pendentes e dos cancelamentos (`servidor_de_leitura.py:630-633`), trava em todo método
do leitor (`:312-325`), `lendo_no_f5` contra a corrida do lote com o F5 (`lote.py:348`), e matança real nos testes
(`test_servidor.py:96-102`).

## 3. Falhas silenciosas

### A4 (Alto): falha na camada do PDF manda o livro para o OCR, sem aviso

**Fato**

- `exportar.py:391-398`: um `except Exception` por trecho devolve `{}`, descartando **também os trechos já lidos**.
- `paginas_da_camada` não recebe o `Relatorio`, então o relatório só deixa de listar as páginas da camada
  (`:341-342`).
- O único sinal é `log.warning`, que vai ao stderr (A2).
- `SPEC-qualidade.md:253-254` diz que "a extração é uma chamada só": isso não vale com mais de um trecho (página
  cortada, girada ou inserida; laço por `sq.trechos_do_pdf`, `:386-391`).
- Nenhum teste faz o `pdf_nativo.extrair` falhar (`grep` por `extrair` em `tests/test_exportar_preciso.py` não
  acha nada).

**Cenário.** Odds & Ends, 375 páginas, um corte numa delas. Um `extrair` falha no último trecho: o EPUB sai inteiro
dos boxes do OCR, com aparência normal, sem a precisão pela qual a exportação da camada existe.

**Menor correção.** `continue` no lugar de `return {}`, um campo `camada_falhou` no `Relatorio`, uma linha nos
Avisos e um teste.

### M5 (Médio): a suíte não reprova erro logado

**Fato**

- `conftest.py:99-109` torna `warning`, `information` e `critical` inócuos em toda a suíte.
- `controlador.py:94-95` (ouvinte), `trabalho.py:172-175` (`pronto`) e `trabalho.py:92-93` levam a exceção ao log.
- Nada reprova um teste por um registro ERROR: não há fixture global, e `caplog` aparece só em 20 linhas de 6
  arquivos.

**Cenário.** Um ouvinte de `pagina_reconhecida` levanta `AttributeError` em todo F5. O painel dele não atualiza e o
registro vai ao log; só falha quem confere aquele painel.

**Menor correção** (~15 linhas). Fixture autouse com um handler que reprova o teste em ERROR/CRITICAL, salvo
`@pytest.mark.erro_esperado`; o mesmo para `QMessageBox.critical`. **Opinião:** tem a maior relação valor/custo
deste relatório. Espere alguns vermelhos no primeiro dia, e cada um é informação.

### A lista de exceções aceitas

`test_arquitetura.py:113-122`, `LEVAM_O_ERRO`: 7 entradas, todas conferidas e justas. O teste é bom, mas tem dois
limites:

- Só vê `Exception`/`BaseException` (`:125-129`).
- "Registrou" conta como tratado (`:132-139`), mesmo quando o registro não chega a ninguém (A2, A4).

Varredura minha: de 214 `except`, 81 não logam, não levantam e não usam o erro. Os que li são quase todos
legítimos.

## 4. Segurança proporcional

**Nenhum achado sério em código (Fato).**

| Item | Situação |
|---|---|
| `pickle`/`torch.load` | nenhum em `abbychess/`; no core, `weights_only=True` em todos (`neural_trainer.py:795`, `diagrama.py:1246,1297`, `linha_trainer.py:664,826`) |
| Zip | sem `extractall`; só abre o que o programa acabou de escrever (`epub.py:873-879`, `escritor_docx.py:518`) |
| XML | `ElementTree` só sobre arquivo próprio |
| YAML | `safe_load` (`atalhos.py:144`) |
| Subprocess | listas, sem `shell=True` (`validacao_do_epub.py:273,331,423`) |
| Caminhos | padrão fora da pasta é recusado (`padroes.py:255-261`); `projeto.json` tem tipos conferidos (`projeto.py:771-773`); ciclo em `gids_movidos` limitado (`:693`) |
| Links | a prévia só abre `https` (`dialogo_exportacao.py:351-354`) |

Risco residual aceitável: um PDF hostil chega ao parser do PyMuPDF.

### A6 (Alto, não é código): texto de livros em repositório público

**Fato**

- `gh repo view` dá `DarcioAlberico/AbbyChessCraft`, **`PUBLIC`**.
- `origin/main` tem os 14 arquivos de `tests/verdade/` e `tests/dados/fatia/xv-i020-026-inicial.zip`.
- `tests/verdade/xv/i025.json` traz 22 linhas transcritas (1.198 caracteres); são 213 linhas verificadas nas p.
  21–27 (`pendencias.md:326`).
- `SPEC.md:1097` diz: "Os gabaritos ficam fora de qualquer publicação". O `.gitignore` tira as `.rotulagem/` por
  direito autoral.

**Correção.** Decisão sua: tornar o repositório privado é o mais simples; a alternativa é mover os gabaritos e
reescrever o histórico. Isto é um desencontro com a sua própria regra, não um parecer jurídico.

## 5. Empacotamento e reprodutibilidade

### A5 (Alto): não instala fora do PC do autor

**Fato: o que quebra**

| O quê | Evidência | Efeito numa máquina limpa |
|---|---|---|
| `chess` não declarado | `lances.py:48`, importado por `controlador.py:61`; `pyproject.toml:15-16` | não abre |
| `regex` só em `[dev]` | `busca.py:34`, `substituir.py:24`; `pyproject.toml:22-23` | não abre sem `[dev]` |
| `torch` não declarado | `core/neural_trainer.py:7`, extra `[ml]` do core; README usa `--no-deps` | **Inferência:** o `import` derruba `com_modelos_globais`, o filho cai duas vezes, e a janela oferece abrir sem servidor (`lote_na_janela.py:50-55`) |
| Ambiente herdado | `README.md:21-24`: `--system-site-packages`, `--no-deps` | depende do Python global do autor |
| Sem lock | `git ls-files`: nenhum `requirements`/`lock` | `PySide6>=6.6`, numpy e OpenCV soltos (testado em 6.11.1, 2.2.6) |
| YAML fora do pacote | `atalhos.py:31`, `teclado.py:54`; `pyproject.toml:12-14` promete resolver no "passo A2" | `pip install .` sem `-e` falha ao abrir a janela |
| Pesos e base | `custom_model.pth` e `training_data` fora do git do core (`git check-ignore`) | leitura sem modelo; backup não verificado |
| PDFs | `comum.py:17-18`, caminho fixo; `PDF` fora do git | portão não roda |
| `pytest-cov` | ausente do `pyproject` e do README; `qualidade.py:50` usa `--cov` | medida não roda |
| Base vazia | `dialogos.py:344-349` só avisa da rede | "0 referências" na barra, F5 não lê |

Sem tesseract: `abbychess/` não o usa, e o EasyOCR fica desligado (`leitor.py:54-58, 106`).

**CI: não existe** (sem `.github/`). Sua nota de memória registra o custo: o PR #16 entrou na `main` com 4 testes
reprovando e a descrição dizendo "suíte aprovada" (`nao-encadear-merge-com-teste.md:13`). O portão é por honra.

**Menor correção**

1. Acrescentar `chess`, `regex`, `torch` e `opencv-python<5` às dependências.
2. Mover `atalhos.yaml` para `abbychess/` (package-data).
3. `pip freeze > requirements.lock` e um venv sem `--system-site-packages`.
4. CI só da rápida no `windows-latest`, se o core for acessível de lá (sem os modelos a rápida já roda, e no
   Windows a Arial existe, cf. `SPEC-qualidade.md:569`), ou, sem isso, um `pre-push` local mais a proteção da
   `main`.
5. Conferir o backup de `custom_model.pth` e `training_data`.

**Opinião:** para ferramenta pessoal os itens 1 a 3 custam pouco e valem mais como documentação do ambiente. A
perda do modelo é o único dano aqui que não se desfaz.

## 6. Observabilidade

### A2 (Alto): o log não existe como arquivo

**Fato**

- `principal.py:43`: `logging.basicConfig` sem arquivo. `grep` por `FileHandler`, `RotatingFile` e `faulthandler`
  em `abbychess/` não acha nada. O filho faz o mesmo (`servidor_de_leitura.py:415`).
- `principal.py:14-15` diz que o erro solto vai ao log porque "o programa aberto pelo atalho não tem o stderr". Mas
  esse log **é** o stderr. **Inferência:** sem console (`pythonw`), `sys.stderr` é `None` e o `StreamHandler` falha
  calado.
- `lote_na_janela.py:53-54` manda o usuário a "o log do programa". `servidor_de_leitura.py:372` diz "o log do filho
  guarda o rastro", mas ali não há registro nenhum.
- `excepthook` só loga (`principal.py:16-17`): erro num slot não mostra nada ao usuário.
- A queda do filho perde o motivo: "o processo terminou", sem `exitcode` (`:574-575`).
- Falha nativa não deixa rastro.

**Cenário.** Você manda um relato: "abri o projeto e nada aconteceu". Só há `avisos.log`, sem a falha, porque ela
nunca virou aviso, e sem a versão do programa, do core ou do modelo.

**Bom (Fato).** `avisos.py` é persistente, por projeto e visível ao usuário. `ABBY_REGISTRO_DE_EVENTOS` grava
gestos, sob demanda.

**Menor correção** (~25 linhas)

- `RotatingFileHandler` em `%LOCALAPPDATA%\AbbyChessCraft\abbychess.log`, também no filho.
- `faulthandler.enable(arquivo)`.
- Linha de abertura com a versão, o commit do core, o Python e o SHA do modelo.
- `excepthook` também registra em Avisos.
- `exitcode` na mensagem de queda.
- Um teste com processo filho que confira o arquivo.

## 7. Mutação e os demais pontos menores

### M4 (Médio): a mutação cobre pouco, e não testa "função vazia"

**Fato**

- Oito módulos (`qualidade-Q9.md:38-47`), 5.554 de 41.713 linhas (13%).
- Fora: `gravacao`, `projeto`, `migracoes`, `lote`, `exportar`, `epub`, `montagem`, `pagina`, `arrumacao`,
  `servidor_de_leitura`.
- Operadores (`mutador.py:128-155`): nenhum troca o corpo por `return None` nem apaga comando.

**Inferência.** Sete dos oito módulos tinham 56,8–87,2% antes do trabalho à mão (`qualidade-Q9.md:38-47`), com a
cobertura global já em 94,7% (fim do Q8). Os 94,9% de hoje dizem pouco sobre os módulos não mutados.

**Correção.** Operador "corpo vazio" (~20 linhas; um mutante por função, ~2.900 no projeto inteiro), rodado
primeiro em `gravacao`, `migracoes`, `arrumacao`, `lote`, com `--trabalhadores 2`, um por vez.

### B1 a B3 (Baixo)

- **B1.** `busca.py:203-204`: página que não lê fica fora do índice, sem aviso; a busca devolve menos e não diz.
  `AttributeError` não está na tupla, diferente de `ERROS_DE_PAGINA_ILEGIVEL`.
- **B2.** `migracoes.py:59-60`: `marcadas.json` v1 estragado vira conjunto vazio, em silêncio.
- **B3.** `README.md:27` ainda fala em "abaixo de 60 s" (SPEC: 90 s), e a linha de instalação omite `pytest-xdist`.

## Ordem que eu seguiria

Só A6 e o orçamento de tempo do Q1 pedem decisão antes de codar. O resto cabe em commits pequenos, TDD, um por
vez.

1. **A6**: decidir (minutos).
2. **A3**: uma linha e um teste.
3. **A2**: log em arquivo; ajuda a diagnosticar todo o resto.
4. **M5**: reprovar em erro logado; vai revelar coisas.
5. **Q1**: catraca de qualidade, com os valores do JSON de hoje.
6. **A4**, **A1**, **M1**/**M2**, **A5**, **M3**, **M4**, **M6**.
