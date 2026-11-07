# Crítica 3 de 6: viabilidade do desenho contra o código

Revisão de `docs/SPEC-pagina-perfeita.md` v0.1 e `plans/roadmap-pagina-perfeita.md`, ramo `checkup-geral`, sobre `262d897`. Core em `C:\Python-Chess2\PyBoxEditor_Tkinter`.

**Como ler.** Caminhos sem pasta são de `abbychess/`; `core/` é o do PyBoxEditor; "spec:N" é linha de `SPEC-pagina-perfeita.md`. Tudo com `arquivo:linha` foi lido. **Conta** marca estimativa minha, sem medida. **Não rodei** pytest, OCR nem motor. Método estatístico e números ficaram de fora: são das duas revisões anteriores.

## 0. Veredito

Sete itens não funcionam como escritos: D-3, L-1, L-2 (alinhamento e chave), F-1 sobre `pendentes`, L-4, L-9 e a parte de sincronia e alfabeto de X-1. O centro do problema é um só: L-1 e L-2 inventam estado derivado chaveado por `gid` e por linha, um terceiro processo e dois arquivos por página, quando o código já tem quase tudo o que resolve o caso com menos partes:

- `core/services/ocr_service.py:402-431` lê a página inteira no Tesseract, com palavra e caixa, numa chamada pública.
- `camada.py:130-162` já é uma segunda opinião alinhada por caixa.
- `sessao.py:64-82` já é o alinhamento por caractere com custo de espaço.
- `core/box_model.py:64` já tem o campo `margem`, gravado e jogado fora.
- `ponte_de_leitura.py:521-523` já é o molde do pedido sob demanda.

A §4 traz o desenho consolidado. Ele tira o `servidor_de_opiniao`, a pasta `hipoteses/`, a chave por recorte de linha e a dependência entre opinião e `gid`.

| Id | Sev. | Item | Em uma linha |
|---|---|---|---|
| B1 | Bloqueante | D-3 | Sair dos boxes apaga diagramas e embaralha colunas e tabelas |
| B2 | Bloqueante | L-1 | 2.ª classe do k-NN custa uma busca a mais; glifo do livro não passa pela rede; `gid` volta a ser alocado depois de queda |
| B3 | Bloqueante | L-2 | Token por linha marca `1. e4`; chave por recorte não dá o que mostrar quando a linha muda |
| B4 | Bloqueante | F-1, L-2 | A fila só tem `pendentes`, e `pendentes` manda reler e propagar: entrar nela muda leitura |
| B5 | Bloqueante | L-4 | "Só `char`, fonte própria" é relido por F5, Ctrl+R e propagação; token não vira edição 1:1 |
| B6 | Bloqueante | L-9 | Estado novo quebra a leitura do formato; a exportação não tem caminho para área de imagem |
| B7 | Bloqueante | §1, R-1, X-1 | O "alfabeto declarado por livro" não existe; `Notacao` é outra coisa |
| B8 | Bloqueante | X-1 | "Pilha para `(`" não acompanha variante sem parêntese; X-1 não cabe em `arrumar` |
| I1 | Importante | L-2 | `servidor_de_opiniao`: sem reuso de `_Laco`, sem a trava de só leitura, sem necessidade com Tesseract |
| I2 | Importante | D-1 | "Passa a só leitura" no meio da sessão não tem mecanismo; varredura ao abrir fura o CA-8.3 |
| I3 | Importante | Princípio 5 | Hoje o revisado é relido por Ctrl+R e pela propagação |
| I4 | Importante | F-3 | `Lance` com gids exige refazer `_tokens`; `Validacao.legais` já é o índice |
| I5 | Importante | T4 | Ordem; `pagina.py`, `documento.py` e tetos; 13 testes com monkeypatch; A-6 quebra `replay_fatia` |
| I6 | Importante | C-2, C-3, C-4 | Filho sem log; prazo menor que a capa; `reinicios` não se zera |
| I7 | Importante | E-1, E-5, E-6 | Três `cv2`; core em wheel perde os pesos; paddle não deve dividir venv |
| I8 | Importante | L-3, PP5 | Integra antes de medir; o varrimento não tem o modo página; `_idioma_tesseract` falha em `es`, `de`, `fr` |
| I9 | Importante | CA-L2.5, Dec-2 | Orçamento sem lugar nem medidor em produção |
| I10 | Importante | F-1 | Modos sem definição; onde moram coeficientes e escore |
| I11 | Importante | PP2b | Cobertura em páginas isoladas subestima X-1 e pode derrubá-lo |
| M1 | Menor | D-2 | Chave, base do FEN, 1 linha livre em `janela.py` |
| M2 | Menor | D-4 | Página importada que cai nos boxes herda B1 |
| M3 | Menor | C-1, C-5 | `vigiar_o_pai` serve; log do filho fora de C-5 |
| M4 | Menor | L-5, `Limiares` | A migração já é de graça; `bool` em `Limiares` impede abrir |
| M5 | Menor | Disco | `gravar_json` usa `indent=1`: triplica o arquivo derivado |
| M6 | Menor | Medida, teste | Motor em segundo plano suja a medida; falta o executável falso |
| M7 | Menor | X-1 | `e2-e4` não é lance para `lances.py`: cobertura zero sem aviso |

---

## 1. Bloqueantes

### B1. D-3 como escrito estraga a página (spec:467, roadmap:95,100)

**O que quebra.** "Página com edição sai dos boxes" assume que a página nativa tem boxes exportáveis. Não tem:

- `nativo._boxes` só trata `Paragrafo` e `Tabela` (`nativo.py:98-115`). `importar` não grava tabuleiros nem diagramas (`nativo.py:77-80`). A exportação pelos boxes pede `carregar_tabuleiros` (`exportar.py:286`) e `_figuras_da_pagina` só conhece tabuleiros (`montagem.py:891-899`). **Corrigir uma letra apaga todos os diagramas da página**, que a camada dava com FEN exato (`exportar.py:21-27`).
- O x é fictício: toda linha recomeça em `cursor = 40.0` (`nativo.py:131`) e a largura é `len × escala` (`nativo.py:138`). O y do parágrafo é real (`nativo.py:101-105`). Duas colunas com o mesmo y caem na mesma linha em `OrdemDeLeitura` (`exportar.py:291`, `montagem.py:850`).
- A tabela vira `"  ".join(linha)`, em y inventado `30 + linha_global * 36` (`nativo.py:110-113`), no meio do y real dos parágrafos: perde as células e a ordem.
- Título, nível, parágrafo e hífen vêm da camada, e pelos boxes passam a sair do vão entre linhas (`montagem.py:694,709`) sobre um y dividido por igual (`nativo.py:104-105`).
- "Página com edição" nem se detecta: `descartar` não deixa rastro (`edicao.py:166-170`), e o box apagado só sumiu.

O CA-D3 passa (a palavra está no EPUB) com a página destruída. O roadmap diz "conferir o golden", mas o golden não tem esse caso.

**Correção (spec:467).**

> **D-3.** Página importada da camada (boxes com fonte `nativa`) **continua saindo da camada**, com as edições aplicadas por cima: `nativo.remendar(extraida, pagina)`. Junta-se o texto sem espaços da extração, na ordem de `_boxes`, e o dos boxes, na ordem da lista. `difflib.SequenceMatcher(autojunk=False)` dá os trechos; cada trecho volta à posição `(bloco, deslocamento)` e entra em `Paragrafo.texto` ou na célula, levando `inicios` e os trechos de estilo como `montagem._andar_os_trechos`. Não há detecção de "editada": textos iguais não mudam nada. Quebra, junção e parágrafo decididos e similaridade abaixo de 0,9 não se aplicam e vão ao relatório (`edicoes_nao_aplicadas`, por página). Página aceita pela camada, mas **lida por OCR** (boxes sem fonte `nativa`) e com glifo `manual`, `revisado` ou decisão sai dos boxes, que nela têm geometria real e tabuleiros; o relatório a tira de `da_camada`.
>
> **CA-D3.** Numa página nativa com diagrama, duas colunas e tabela, trocar uma palavra e apagar outra: o EPUB difere do EPUB sem edição **só** nessas palavras (diagramas, títulos, ordem e parágrafos iguais). Numa página de OCR em PDF aceito, a correção de um glifo chega à exportação.

### B2. L-1 não cumpre "sem dobrar o tempo" e o arquivo por `gid` não se sustenta (spec:233-247)

**Rede: dá.** `predict` (`core/neural_trainer.py:915-946`) faz a própria passada e não usa `_probabilidades`, então `predict_topk` depois dele é **segunda passada** (`:824,894-913`). Mas as duas contas são iguais, e `predict_topk` guarda o resultado. Basta injetar em `predictor=` (`leitor.py:175`) um invólucro com `loaded`, `predict` (chama `predict_topk(k=3)` e guarda; devolve o primeiro) e `predict_topk` (repassa). A cadeia chama a rede sempre primeiro (`ocr_service.py:961-962`), e o veto cai no cache (`:967-968`). Custo: um `tobytes` por glifo. Nada novo no core.

**Veto.** `CANDIDATAS = 12` (`core/proporcao.py:170`): o veto pode escolher a 4.ª ou a 12.ª classe (`ocr_service.py:967-970`), e o lido fica fora do top-3. Multiclasse: 139 das 314 classes têm mais de um caractere (`motores.md:229`), e "em cada caractere errado, o certo está no top-3" (CA-L1.4) não está definido para `'xf3'`.

**k-NN global: não dá.** A cadeia chama `predict_e_margem` (`ocr_service.py:976`), que faz uma busca e devolve a margem, sem a classe (`core/learner.py:692-697`). A 2.ª classe só sai de `candidatas` (`core/learner.py:553-564`): outro produto de matriz de 86 mil × 1.024 (`:508`, `:676`), mais `argsort` e `unique`. Conta: dobra o custo do elo mais caro em cada glifo que chega a ele, e CA-L1.3 (< 5 %) cai. Fazer em uma busca só exige `_quadrados_ate` e `_ids`, privados fora da lista de `tests/test_privados_do_core.py:20-30`. A resposta honesta é **não colher**: nesse glifo a rede já rodou, e o top-3 dela serve de candidato. A margem vem de graça em `leitura.margem`.

**k-NN do livro: a rede nunca roda.** `ler` volta em `leitor.py:166-168`. Em T1, com o treino, é a maior parte da página. "Top-3 da rede" em todo glifo exige uma passada a mais onde hoje não há nenhuma, e CA-L1.3 fura justo no caso que importa. O CA o mede em T0, com padrões vazios (spec:246). A 2.ª classe do livro é conta nossa sobre o `distancias` já calculado (`padroes.py:302-303`).

**`reader`.** Não entra: é `_SemEasyOCR` (`leitor.py:54-58,106`), e `com_modelos_globais` nunca o liga (`leitor.py:128-129`).

**O arquivo por `gid`.**

- O servidor não tem gid: "os boxes sem gid" (`servidor_de_leitura.py:20-22`). O gid nasce em `reconciliar`, na interface (`arrumacao.py:44`), que é função pura "sem disco" (`arrumacao.py:1-4`). A spec não diz quem escreve nem quando.
- **Queda:** o próprio código diz que "um gid só na memória voltaria a ser alocado depois de uma queda" (`projeto.py:576-578`). O gravador tem coalescência de meio segundo (`gravador.py:27`). Hipótese gravada antes da página cai, depois da queda, sobre **outro glifo**, sem sintoma.
- **Releitura parcial:** Ctrl+R relê só os pendentes (`ponte_de_leitura.py:170`), e "Reconhecer a área" só a zona (`arrumacao.py:61-70`). "Refeito na releitura" apagaria o resto.
- **Dividir, juntar, ajustar:** gids novos (`edicao.py:34-41,44-56`), lidos por `ler_recortes`, outro caminho (`ponte_de_leitura.py:433`). `ajustar` mantém o gid com caixa nova (`edicao.py:186`): hipótese velha sob gid vivo.
- **Desfazer:** o `Box` volta (`historico.py:279-285`); o arquivo fica. Inofensivo só se a hipótese for função do recorte, o que a spec não diz.
- **Área, giro, borracha:** `reenquadrar` move a caixa e mantém o gid (`projeto.py:504`). Borracha muda a tinta com a mesma caixa (`pagina.py:183`).
- **Dividir a página:** o gid muda por `gids_movidos` (`projeto.py:689-698`).
- **`spawn` e pickle: aguentam.** A página já vai pela fila, e a resposta com uma lista paralela (como `amostras`, `servidor_de_leitura.py:124`) é pequena. Só que `reler_boxes` devolve tripla (`:135`, desempacotada em `ponte_de_leitura.py:182`), e o registro por objeto não atravessa a fila (`:139-140`). Colher por efeito colateral no leitor pegaria também o `arbitro` (`leitor.py:201-204`), chamado na segmentação e nos rótulos (`pagina.py:649-650`, `servidor_de_leitura.py:121`).

**A alternativa simples.** Para que serve o arquivo? F-1 usa `margem`, `fonte`, `confiança`: os dois últimos já estão no box, e o primeiro tem campo gravado (`core/box_model.py:64,97`), que `leitor.py:178` e `pagina.py:858` jogam fora. Só X-1 quer top-3, e só nos tokens de lance. Isso é o caso de `sugerir_recortes` (`servidor_de_leitura.py:153-156,393`, `ponte_de_leitura.py:521-523`), que já pede palpite sob demanda. E `cobertura@3`, o critério que derruba L-1, nem precisa do programa mudado. Hoje o roadmap constrói o arquivo e só então mede (roadmap:170).

**Correção (spec:233-247, roadmap:166-176).**

> ### 4.1 L-1. Hipóteses, em três partes
>
> **a) Medir sem mudar o programa.** `ferramentas/medir_hipoteses.py` lê as páginas do ajuste com o leitor de sempre e pergunta `rede.predict_topk(recorte, k=3)` a cada box. Sai `cobertura@3`, em T0 e T1. Top-3 **mais** a classe lida; classe de vários caracteres conta se o certo for substring, e a medida diz quantos casos há. **Derruba** a parte c, sem tocar no programa.
>
> **b) A margem deixa de ser jogada fora (sempre).** `leitor.Leitura` ganha `margem`; `_ler_global` passa `leitura.margem`; `por_leitura` grava `box.margem`. Para a rede, um invólucro em `predictor=` chama `predict_topk(k=2)` no lugar de `predict`, numa passada só, e a margem é `1 − p2/p1`. Para o livro, a margem e a 2.ª classe saem do `distancias` de `PadroesDoLivro.ler`. O glifo lido pelo livro não passa pela rede. O formato não muda: `margem` já é campo de `as_state`.
>
> **c) Top-3 sob demanda (só se a parte a passar).** Operação `hipoteses_recortes` no servidor, no molde de `sugerir_recortes`: recebe os recortes dos tokens de lance, devolve `[(char, p)] * 3`, fica na memória da página, sem arquivo. A 2.ª classe do k-NN global fica fora: exigiria outra busca; o candidato vem da rede.
>
> - **CA-L1.1.** Ligar b não muda caractere, fonte nem confiança (golden das 7 páginas).
> - **CA-L1.2.** O tempo por página sobe menos de 5 %, **em T0 e em T1**, mediana de 5 rodadas alternadas.
> - **CA-L1.3.** O arquivo do `cobertura@3` traz T0 e T1 e o N de casos multiclasse.

### B3. L-2: alinhamento por token e chave por recorte (spec:261-267)

**Alinhamento "por linha, com o token como unidade".** Caso a caso:

| Caso | O que acontece | Prova |
|---|---|---|
| Espaço | `1.e4` num lado e `1. e4` no outro são tokens diferentes: dois falsos por par. Regra `espaço` do §1 não vale aqui | `core/notacao.py:22-34`; `texto.py:144-155` parte palavras por regra de lance |
| Ligadura | Um box, 2 ou 3 letras; o motor pode devolver `fi` ou `ﬁ` | `texto.py:52-54,629-635`; `app/documento.py:353-360` |
| Box com vários caracteres | 139 de 314 classes; e a edição conserva caixa multicaractere | `motores.md:229`; `edicao.py:111-115` |
| Linha em box único | `moldura` faz a tabela virar faixa; a discordância vale para todos os tokens | `lances.py:476`; `texto.py:389` |
| Box vazio | Entra como `□` na vista, e a opinião é exatamente a letra que falta. Fora de `montar` sem os não lidos | `texto.py:95-111` |
| Virtual | Sem caixa, mas está na linha | `texto.py:498-535` |
| Camada nativa | Cada palavra é um box, x fictício; 300 páginas lidas à toa | `nativo.py:125-141` |
| Texto vertical | Lido por `recorte_de_pe`; o recorte da linha não gira | `pagina.py:807-809`, `editar_boxes.py:74` |
| Deskew | **Sem problema**: a imagem já vem endireitada | `pagina.py:184-186` |

**De onde saem as caixas.** `linhas_dos_gids` dá gids, não caixas (`texto.py:122-127`). `montar` tem o topo, mas não a caixa (`texto.py:429-444`). A medida da spec cortou pelas linhas **da exportação** (`mo._linhas`, em `experimentos/motores.py`, e `paddle_xv.py` com folga de 8 e 6 px), que têm 95 % das palavras em comum com o Documento (`arquitetura.md:159`). Depois das correções ou antes: a geometria não depende do caractere, salvo poucos casos (`texto.py:367-380`), logo a linha sobrevive a uma troca de letra; muda com dividir, juntar, F5, área e `paragrafo`.

**Chave por SHA do recorte.**

- **F5 que mexe um pixel** na caixa da linha (por isso existe `IOU_DA_RELEITURA`, `modelo.py:441`): troca o SHA da linha inteira, mesmo com a mesma imagem. CA-L2.4 passa só na página intocada.
- **Dividir ou aparar o último glifo:** o mesmo.
- **Área e giro:** a mesma tinta, com caixa nova. Sem índice por SHA no arquivo por `pid`, não se acha; com giro de 90°, os bytes mudam, e é certo reler.
- **Borracha (CA-12.17):** muda a tinta só onde apagou. Aí a chave acerta, mas a borracha que muda a caixa do glifo move a linha.
- **O que mostrar quando a linha muda:** a spec não diz. A contenção (spec:564) diz "`gid` editado perde a marca", mas a marca é de token e a chave é de linha.
- **Custo medido errado:** 30 × 0,15 s = 4,5 s por página. O core já mediu: "a página inteira (`--psm 3`) leva de 0,7 a 3 s" e até 19 s na trama; a faixa, 0,16 a 0,24 s (`ocr_service.py:95-99`). E diz: "iniciar o Tesseract uma vez para cada glifo ou linha torna um livro impraticavelmente lento" (`:408-411`). Os 22 minutos da spec (spec:271) viram de 3,5 a 15 com a chamada que já existe.

**Correção (spec:249-280).** Texto na §4.1.

### B4. F-1 e L-2 sobre `pendentes` mudam a leitura (spec:361-386)

**O que quebra.** A spec não diz onde a marca entra. A única entrada da fila é `contexto._pendentes` (`contexto.py:499-506`), e ela tem outros donos:

| Quem chama | O que faz com ela | Efeito se a discordância entrar |
|---|---|---|
| `propagar` | Relê pelo livro os pendentes a cada Enter, e **troca o caractere** (`ponte_de_leitura.py:354-362`, `pagina.py:964-976`) | Glifo de rede a 0,99 passa a ser reescrito pelo padrão. Contraria o Princípio 2 |
| `_preparar_reler` | Ctrl+R (`ponte_de_leitura.py:170-172`) | Relê sem motivo; o lido volta igual |
| `pg.ler_boxes` no filho | `contexto.pendentes` sem nada do arquivo (`pagina.py:824-825`) | O filho não lê arquivo: dois conjuntos diferentes |
| `resumo_das_confiancas` | `livro.json` e o histograma (`resumo_do_livro.py:226-242`) | A conta `pendentes_pelo_histograma` (`:245-250`) deixa de valer |
| `exportar`, `montagem` | `duvidosos` e relatório (`montagem.py:165`, `exportar.py:345`) | O realce do DOCX e o relatório mudam |
| Lote | `pg.resumir` (`lote.py:398-399`) | Conta de outro conjunto |

E o avesso: F-1 corta por `m` % da página. Página com marca forte e `pendentes` 0 não é visitada no escopo livro (`livro.py:205-218`, `controladores.py:370`), e `Relatorio.pendentes` diz outra coisa.

**A fila pode ler arquivo?** Não em `fila()`. "A fila da janela pergunta várias vezes por ação" (`contexto.py:376-377`), a meta é Enter ≤ 100 ms (`docs/SPEC.md:59`), e `fila()` é incremental de propósito (`fila_da_pagina.py:72-94`). Um `open` + `json.loads` no Windows, com antivírus, por chamada, derruba. `do_modelo` roda na interface a cada `agendar` (`cache_do_projeto.py:72-73`): também não lê disco. **Custo do jeito certo** (conta): carregar uma vez ao abrir; por gid, uma consulta em dict; ordenar 2.000 itens; refazer a comparação só quando `_chave` muda. Menos de 5 ms.

**Correção (spec:367, antes de "Dois modos").**

> **Onde mora.** `contexto.pendentes` não muda de sentido: é o que a leitura e a propagação podem reler, e o que `livro.json` conta. A evidência é outro objeto, `EvidenciaDaPagina` (sem Qt), que `FilaDaPagina` guarda por `pid`: `{gid: (motivo, sugestão)}` e `{gid: escore}`. É carregada **uma vez**, na thread que abre a página, ou entregue quando a opinião chega. Só a `FilaDaPagina` a lê: `fortes()`, a marca; `fila()`, a ordem. `pendentes`, `precisa_revisao`, `propagar_padroes`, `ler_boxes`, `resumo_das_confiancas`, `duvidosos` não a veem. O escore é função pura de `(evidência, box)`. `fila()` nunca abre arquivo.
>
> **O livro.** `do_modelo` acrescenta `"fortes"`, da evidência em memória (ausente na página fora da memória: vale o último valor). `proxima_com_pendentes` e o contador do escopo livro usam `pendentes ∪ fortes` no modo novo; sem `fortes` no resumo, `pendentes`. O relatório de exportação traz as duas contagens.
>
> **CA-F1.5.** Com opinião carregada numa página de 2.000 glifos, o Enter fica em p95 ≤ 100 ms, e nenhum arquivo de `opinioes/` é aberto nele (teste com contador de `open`).
> **CA-F1.6.** A discordância num glifo `neural` não o relê no Enter nem no Ctrl+R: `char`, `source`, `confidence` iguais depois de dez Enters na página.

### B5. L-4: "muda só `char`" e `fonte "opiniao"` (spec:297-308)

**Token não vira `char`.** Dos casos que a opinião propõe, só 1 glifo → 1 caractere é troca de `char`.

- O caminho que trata k → 1 e 1 → k é `ss.planejar` e `ss.aplicar` (`sessao.py:298,768-802`). Ele chama `ed.juntar_varios` e `ed.dividir_em`, que usam `pg.confirmar` (`edicao.py:87,106,112`), e `pg.confirmar` põe `FONTE_MANUAL`, confiança 1,0 (`pagina.py:980-984`), e `revisado=True` (`edicao.py:64,107,113`; `sessao.py:802`). Contradiz CA-L4.1.
- Dividir pede tinta e pode recusar (`sessao.py:810-821`). Um lote não pode parar no meio de uma recusa: "Nada da sessão fica pela metade" (`sessao_do_documento.py:114-122`).
- Inserir vira `GlifoVirtual` (`sessao.py:602`), sem caixa, com a marca de tinta sem box (`sessao_do_documento.py:158-162`).

**`fonte "opiniao"`: o que acontece com o código de hoje.**

| Lugar | Comportamento | Consequência |
|---|---|---|
| `FONTES_CONFIRMADAS` (`leitor.py:41`), `precisa_revisao` (`:249-253`) | Fora: volta à fila pela confiança antiga | O aceito reaparece |
| `_alvos_da_leitura` (`pagina.py:834-835`) e `ponte_de_leitura.py:168` | Só `manual` escapa | **F5 e "reler tudo" trocam em silêncio o que o usuário aceitou** |
| `a_manter_na_releitura` (`editar_boxes.py:208-209`) | Só `manual` ou `revisado` | Idem no lote |
| `propagar` (`ponte_de_leitura.py:354-355`) | `com_os_revisados=True` | Próximo Enter pode trocar (I3) |
| `volta_pelo_contexto` (`contexto.py:481-486`) | Fonte nova volta | Palavra que o contexto desmente volta à fila |
| `_trocaveis` (`montagem.py:384-385`) | Caixa pela altura troca na exportação | Texto exportado ≠ aceito, salvo `revisado` |
| `busca.grupo_da_fonte` (`busca.py:712-720`) | Cai em `REDE` | O filtro da busca mente. A correção é cirúrgica |
| `grade.estado` (`grade.py:48`) | Pinta como `REDE` | Sem estado próprio |
| `NOMES_DAS_FONTES` (`app/painel_treino.py:103-107,365`) | Mostra "opiniao" cru | Copy |
| Golden | `source` só aparece em `as_state`; o texto não muda | Sem quebra, salvo o golden do JSON, se houver |

**Conflito com "Decidido não volta" (spec:134).** Aceitar em lote, com prévia, é decisão. Como escrito, ela se desfaz sozinha. Com `revisado`, ela sai da fila, e CA-L4.1 ("não treina, a menos que o revisor a confirme") continua valendo: `revisado` não grava amostra.

**O desfazer funciona.** Tudo numa transação: uma troca de `pagina.boxes`, um `_mudou` (`controlador.py:812-823`, `historico.py:279-285`). A pré-condição por gid (`historico.py:267-276`) recusa o desfazer se um aguardando ou propagação tocar nele depois; `lido_depois` (`:256-264`) só cobre o aguardando.

**Correção (spec:301-308).**

> **Fazer.** A sugestão aparece na fila e no Documento. **Só entra no lote a sugestão 1:1:** o mesmo número de glifos e de caracteres, sem box de vários caracteres, sem espaço a mais ou a menos, nenhum glifo com figurina, nem lance de forma válida. O resto é sugestão por palavra: uma tecla abre a sessão do Documento com o texto proposto, e a confirmação é a de sempre (`sessao_confirmada`, com dividir, juntar e virtual, e fonte `manual`).
>
> **Aplicar.** `edicao.trocar_varios(pagina, {gid: char})`: uma lista nova de `Box`, com `BoxEntry` copiado, `source = FONTE_OPINIAO`, confiança mantida, `amostra = None`, `revisado = True`. `FONTE_OPINIAO` entra em `FONTES_CONFIRMADAS`, sai de `volta_pelo_contexto` e ganha grupo próprio em `busca.grupo_da_fonte` e nome em `NOMES_DAS_FONTES`. Um `_mudou`: um passo do desfazer. O glifo aceito não é relido por F5, Ctrl+R, lote nem propagação, e não vira amostra; o Enter sobre ele ensina, como sobre qualquer glifo.
>
> - **CA-L4.1.** O glifo aceito sobrevive a F5, Ctrl+R, lote com "refazer" e dez Enters na página (o mesmo `char` e `FONTE_OPINIAO`); nenhuma amostra nova; a exportação traz o aceito, sem caixa pela altura.
> - **CA-L4.4.** Um Ctrl+Z volta `char`, `source`, `confidence` e `revisado` de todos.
> - **CA-L4.5.** A busca por fonte acha o aceito em "opinião", e não em "rede".

A evidência "756 de 819 reduziram" mede a regra sobre edições de todo tipo. O CA-L4.3 tem de contar só as 1:1. O número sai menor.

### B6. L-9: estado novo e exportação sem caminho (spec:349-357)

**O que quebra.**

- `Estado` é fechado (`modelo.py:300-308`), a transição é tabela (`:322-341`), e `pagina_de_json` faz `Estado(...)` com `ValueError` (`pagina_em_json.py:68`). Valor novo: projeto aberto em versão anterior **isola a página como corrompida** (`projeto.py:404-408`), o defeito de D-1. Pede subir a versão, e o `lote` (`lote.py:216`), `LIDAS` (`modelo.py:318`) e `painel_paginas` passam a conhecê-lo.
- CA-L9.3 ("sai como imagem") não tem caminho. "Imagem" é tipo de área (`zonas.py:59-63`), e a exportação não a escreve: `_figuras_da_pagina` só conhece tabuleiros (`montagem.py:891-899`), e nem renderiza a página sem tabuleiro (`exportar.py:287`).
- A imagem da capa ainda custa segmentar: com área, `segmentar_com_zonas` roda `segmentar_tudo` com o árbitro antes de filtrar (`zonas.py:814-827`). CA-L9.1 (< 5 s) cairia no segundo F5.
- `pagina.py` está em 1.000 linhas: o classificador não cabe lá.

**Correção (spec:353-357).**

> **Fazer.** Classificar antes de segmentar, em `servidor_de_leitura.ler_pagina`, só em página **sem áreas**, por uma função de `abbychess/tipo_de_pagina.py`. Página de imagem: `PaginaLida` sem boxes, com `imagem=True`, e `aplicar_lida` põe uma `Zona` da página inteira, função `figura`, e o estado `reconhecida`. **Nenhum estado novo, nenhum formato novo.** O lote a pula como lida, e ela tem zero pendentes. "Forçar a ler" é o que já existe: mudar a função da área para texto e dar F5. `segmentar_com_zonas` volta sem segmentar quando nenhuma área é de texto ou diagrama. A exportação escreve toda área de função `figura` como recorte (`Figura`, com o motivo), na ordem das áreas, e o relatório a lista em `recortados`.
>
> - **CA-L9.3.** Exportar a página de imagem a põe inteira, como figura, e o relatório a lista. Uma área "Imagem" desenhada à mão numa página de texto também sai.

Isso entrega de graça o que falta hoje: área "Imagem" desenhada à mão não sai na exportação. É mudança de saída: conferir o golden. Se a exportação da área à mão não for desejada agora, limitar à página inteira.

### B7. O alfabeto de notação não existe (spec:75, spec:194, X-1)

**O que quebra.** O §1 pede "letra do alfabeto de notação **declarado por livro**". `Notacao` tem `LIVRO`, `FIGURINAS`, `LETRAS` (`dados_do_projeto.py:16-22`): **diz se é figurina, e não quais letras.** As letras vêm do **idioma da prosa** (`dados_do_projeto.py:61-62`, `modelo.py:119`, `lances.py:172-181`).

- Livro em português com notação inglesa: `Rf1` é torre no livro, e `lances._tabela` faz `R → K` (rei). Todo lance de torre vira ilegal. O erro acusa o diagrama (spec:399).
- O quinto livro de avaliação é justamente "em português ou espanhol, com notação em letras" (spec:194).
- `core.notacao.analisar` é pior: `INICIAIS = set("KQRBNabcdefgh0O")` (`core/notacao.py:326`) rejeita `Cf3` e `Tae1`, e lê `R` como torre sempre.
- `contexto._LANCE` usa a união de todos os alfabetos (`contexto.py:57-60`), logo aceita o que `lances.py` recusa.

**Correção (spec:75 e §7.3; R-1 usa o mesmo campo).**

> **Alfabeto.** `Projeto.letras_das_pecas: str = ""`, 5 letras na ordem rei, dama, torre, bispo, cavalo; vazio é `PECAS[idioma]`. `lances._tabela`, `sessao.figurinas` e `classificar_token` o leem. Para o gabarito, o JSON do livro traz o mesmo campo. Não muda a versão: campo novo em versão antiga vai a `extras`.
>
> **CA-R1.6, acrescentar:** a tabela roda duas vezes, com `RDTBC` e `KQRBN`; `Rf1` é rei numa e torre noutra.

### B8. X-1: sincronia só por parêntese, e não cabe em `arrumar` (spec:414-418)

**Sincronia.** "Pilha de posições para `(`" não acompanha o que o próprio core registrou: "12.Re1 Qa5 12...Ra6; 12...Ra7; 12...Nb6 13.Qc2" não tem parêntese, e metade do texto destes livros são alternativas assim (`core/notacao.py:537-543`). Quem acompanha é o **número**: número que já passou rebobina, de trás para a frente, e, se mais de uma posição explica, o lance seguinte desempata (`core/notacao.py:661-691`). Sem isso, CA-X1.4 reprova, com marca falsa. `lances.py` nem tenta: para no primeiro `;`, `(` ou número inesperado (`lances.py:279-286`).

**Semente "`1.` da partida".** Em livro de exercícios, `1.` depois de um diagrama é da posição dele (a validação de hoje já assume isso: `lances.py:362-381`). `core.notacao` zera o tabuleiro em todo `1.` (`:566-568`). A partida que continua na página seguinte não tem semente: `validar_pagina` é por página (`lances.py:508-525`).

**Onde roda.** `arrumar` chama `validar_pagina` em **toda edição** (`arrumacao.py:24`, `controlador.py:822`), na interface. Conta: 100 tokens × 35 legais × `board.san` (dezenas de µs) + 35 programações dinâmicas de 36 células em Python: de 0,3 a 0,6 s por página. Enter ≤ 100 ms não permite. O cache por `_chave_do_texto` (`lances.py:470-485`) não ajuda: a chave inclui `char`, e o Enter muda `char`.

**Compatibilidade.**

- `lances.py` opera em **texto** (`_tokens`, `:209-230`; `.split()`, `_NUMERO_SEPARADO.sub`), não em gids. Ver I4.
- `core/notacao.py`: reaproveitar o **desenho** e `custo_da_troca`, que é público (`:460-490`). Não `_melhor_lance_legal` (privado), nem `analisar` (sem FEN, sem alfabeto).
- Lance com casa: a ponte é `Palavra.gids` (`texto.py:58-60`) e `tx.normalizador` (`:624-636`). Um box pode dar 2 ou 3 letras; `♘f4` lido `♘4` em um box (`contexto.py:36-38`). A programação dinâmica é por gid × letra do candidato, não por caractere × caractere.
- Na comparação: figurina e letra ao SAN inglês por `lances._tabela`; ignorar `x`, `+`, `#` em falta (`lances.py:27-30`), e `:` ou `×` por `x` (`:240`).

**Quão difícil.** Sem hipóteses: **média**, 1 a 2 sessões para a linha principal, com o custo do core e a confiança por glifo. Só que "margem" é pobre: com confiança 0,99, toda letra custa o mesmo, e a margem é contagem de letras diferentes. Serve para ilegal e forma inválida. **Com** hipóteses: **média a alta**, por causa de classe multiletra e top-3 que não cobre o box colado; é o que dá margem de verdade. A variante soma mais 1 a 2 sessões, com ou sem elas.

**Correção (spec:414-418).**

> 1. **Sementes:** FEN do diagrama, quando a linha o segue. Sem diagrama, `1.` abre a posição inicial **como hipótese**: vale se os dois primeiros lances são legais nela. Fim de página: o estado segue para a página seguinte, numa passada de livro, se ela estiver lida. O JSON diz quantos tokens têm posição por cada semente.
> 2. **Sincronia:** número e `...` como âncoras. Número que já passou **rebobina** para a posição de antes daquele lance, buscando de trás para a frente; `(` e `)` empilham; `;` não encerra. Mais de uma posição possível: o lance seguinte desempata, e sem desempate não há marca (o desenho de `core/notacao.py:661-691`).
> 3. **Candidatos:** por gid × letra do candidato, em `abbychess/decodificador_de_lances.py`, sem Qt. Sem hipóteses, `core.notacao.custo_da_troca`, com a confiança do box. Com hipóteses, a mesma conta, com o custo `1 − p`, se a letra está no top-3, e 1 se não.
> 4. **Onde roda:** nunca em `arrumar`. Numa tarefa leve, ao abrir a página e depois de 500 ms sem editar; o resultado entra em `EvidenciaDaPagina`. A chave do cache é a do texto; muda, descarta. No lote, ao fim, com a opinião.
>
> **CA-X1.5.** `12...Ra6; 12...Ra7; 12...Nb6 13.Qc2` não gera marca falsa e o lance 13 fica com posição.
> **CA-X1.6.** O Enter em página com X-1 fica em p95 ≤ 100 ms.

---

## 2. Importantes

### I1. `servidor_de_opiniao` como terceiro processo (spec:261-263)

**Cabe, com custo.** `ServidorDeLeitura` não se reutiliza: `_Laco` chama `self.leitor.ler`, `ler_pelo_livro`, `sugerir`, `padroes` (`servidor_de_leitura.py:246,295-302,316-319`) e `_operar` é fixo (`:381-410`). Seriam 300 a 500 linhas de filas, queda, reabertura e testes `processo`.

**Trava de gravação.** `protegida` é um `Counter` **do processo** (`gravacao.py:50,58-62`), e `projeto.lock` é só a dona (`:82-122`). Filho que grave não vê "só leitura". E escritor único é regra (§4.3, `servidor_de_leitura.py:20-22`). Logo o filho devolve, e a interface grava: a spec precisa dizer.

**`vigiar_o_pai`.** Só `render.py:46` e `busca.py:273` o usam: C-1 ainda não está feito, e a spec o dá como certo.

**Tesseract não precisa de processo Python.** `tesseract.exe` já é outro processo: não segura o GIL, não fica órfão por mais de segundos, "sai da memória quando acaba", e o prazo e a morte estão prontos (`ocr_service.py:103,337-341`). Uma thread na interface basta. Fila de tarefas, **não**: `_agora` trava a edição (`controlador.py:528-532`). A página vem do processo de render que já existe (`pagina.py:176-186,201-205`).

**PP-OCRv6 sim precisa,** mas só existe se L-3 o aprovar. Aí: `subprocess` de um `python.exe` de venv próprio, com JSON por linha em `stdin` e `stdout` (I7).

**Correção:** §4.1.

### I2. D-1: "passa a só leitura" (spec:465, roadmap:92)

**O que quebra.**

- `somente_leitura` nasce em `abrir` (`projeto.py:236-273`). A página é lida depois, por threads (`lote.py:249`, `busca.py:200-204`). Passar a só leitura no meio da sessão, com o gravador cheio e `gv.proteger` a meio caminho, não tem mecanismo, e o CA diz "abre só para leitura".
- Ler tudo ao abrir: 230 JSONs fura `CA-8.3` (300 ms, `docs/SPEC.md:615`).
- A escolha da classe importa. `ValueError` (o natural) cai em `ERROS_DE_PAGINA_ILEGIVEL` (`projeto.py:118`), em `resumo_do_livro.py:118` e `sequencia_do_livro.py:257`: some em silêncio.

**Correção (spec:465).**

> **D-1.** Duas peças. **Ao abrir, O(1):** `Projeto.campos_do_box: int` é o maior `len(fields(BoxEntry))` que gravou no projeto. Maior que o de agora: abre só para leitura, com o motivo; menor: atualiza e grava. A versão da página fica amarrada à do projeto por teste: `VERSAO_DA_PAGINA` não sobe sem `VERSAO`. **Ao ler, de reserva:** `class PaginaDeOutraVersao(OSError)`, levantada por `pagina_de_json` e `Box.de_json`. É `OSError` de propósito: `_gravada` diz "o `OSError` sobe: quem lê decide" (`projeto.py:393`), a busca e o resumo pulam, o lote a registra como falha, e `_modelo_ou_novo` não cria página por cima. `_ainda_ilegivel` não a captura.
>
> **CA-D1.** Com `BoxEntry` de 12 campos num core de 11: nada é movido, `somente_leitura` é verdadeiro ao abrir, e `abrir()` não lê nenhum arquivo de `paginas/`.

### I3. O Princípio 5 é falso hoje (spec:134)

**Prova.** `_preparar_reler` e `propagar` calculam os pendentes com `com_os_revisados=True` (`ponte_de_leitura.py:170,354-355`), e o filho recalcula sem revisado (`pagina.py:824-825`). `_alvos_da_leitura` só protege `manual` (`pagina.py:834-835`). `aplicar_leituras` entra, porque o objeto é o mesmo (`edicao.py:224-231`), e `revisado` fica (`:237-242`). Logo: **glifo "visto e aceito" no Documento, com fonte `neural` e confiança < 0,90, troca de caractere no próximo Enter, se um padrão do livro o ler diferente,** continuando `revisado`. O docstring admite a releitura pela confiança (`contexto.py:520-521`); o Princípio 5 a proíbe, e nenhum teste de `tests/` usa `com_os_revisados`. Não rodei; é leitura do caminho.

**Correção (PP1, depois de D-4).**

> **D-5.** Revisado não é relido. `_preparar_reler` e `propagar` usam os pendentes sem o `com_os_revisados`, `reler_boxes` recebe a lista de quem não ler, e `com_os_revisados` sai. **CA-D5:** glifo `neural` revisado, confiança 0,5, padrão que o lê diferente: Enter, Ctrl+R e propagação não o trocam.

Se o comportamento atual for o desejado, o Princípio 5 tem de ser reescrito. É decisão.

### I4. F-3: `Lance` com gids; `Validacao` já tem o índice (spec:401)

**Prova.**

- `Validacao(ILEGAL, total, len(sans), ...)` (`lances.py:429`): `legais` **é** o índice do primeiro rejeitado. Campo novo é redundância. Nos dois retornos de antes (`:375,379`), `legais = 0` e a dúvida é da posição, não do lance: CA-F3.2 os separa pelo aviso.
- `Lance` não é gravado. Só `Validacao.lances`, em SAN (`:149-152`). Pôr gids nele muda igualdade e `frozen` (`:109`) sem ganho.
- `primeira_linha(texto, idioma)` recebe **string** (`:251`), e `_tokens` faz `.split()`, depois de `_NUMERO_SEPARADO.sub` juntar duas palavras (`:213`). Uma palavra dá número e lance (`:222-226`). A ponte para gids só existe em `Documento` (`texto.py:58-65`), que `textos_depois` achata (`lances.py:441-459`).
- **Pintar é fácil.** `estados` é por gid (`app/documento.py:354`, `app/desenho.py:409-412`). Sem parâmetro novo em `_escrever_as_linhas`, que já tem 10.

**Correção (spec:401).**

> **Fazer.** `lances.gids_do_rejeitado(documento, diagrama, idioma) -> Tuple[int, ...]`: anda nas `Palavra` do bloco com o mesmo `_tokens`, por palavra (com o `_NUMERO_SEPARADO` aplicado entre palavras vizinhas), acha a palavra do lance `linha[validacao.legais]` e devolve os gids sem os do número. Cacheado com os textos de `_textos_da_pagina`. **`Lance` e `Validacao` não mudam.** O Documento pinta por `estados`, com `gd.LANCE_RECUSADO`. A fila soma esses gids aos fortes. O modo "Lances" entra em `ControladorDaFila.MODOS`.

### I5. T4 conflita com a leitura (roadmap:25, roadmap:261, spec:500-506)

**Pressão real, com o teste.**

| Arquivo | Hoje | Limite | Quem quer crescer |
|---|---|---|---|
| `pagina.py` | **1.000** (`splitlines`) | `tamanho > 1000` reprova (`tests/test_tamanho_dos_modulos.py:13,41-42`) | `por_leitura` em L-1 |
| `app/documento.py` | 992 | idem | F-2, F-3 |
| `VistaDoDocumento` | teto 58 | **só desce** (`:16-22,43`) | Dica da sugestão (F-2): `viewportEvent` é método |
| `ControladorDePagina` | teto 61 | idem | Colaborador novo: delegação proibida |
| `app/janela.py` | 498 `\n` | `< 500` (`tests/test_arquitetura.py:61-63`) | **Uma** linha |
| `sessao.py` | 992 | idem | Nada, se L-4 for B5 |
| `controlador.py` | 950 | idem | Pouco |
| `montagem.py` | 942 | idem | Área de figura (B6) |

`cc < 10`: `FilaDaPagina._pendentes` e `_preencher` não têm folga; helper novo, sim. O teto da lista de exceções é 9 (`tests/test_complexidade.py:23`).

**Conflito de arquivos.** T4 corre em paralelo a PP3 e PP4, e tudo toca o mesmo:

| Arquivo | Leitura | T4 |
|---|---|---|
| `leitor.py` | L-6a, L-6b, L-1 | A-1 (`leitor→projeto`) |
| `zonas.py` | L-6c, L-6d, B6 | A-1 (`zonas→pagina`) |
| `pagina.py` | L-1 | A-1, A-6 |
| `servidor_de_leitura.py` | L-6c, L-9, L-1 | — |
| `ponte_de_leitura.py` | L-1, L-2, L-4 | A-2: **135 acessos a `self._p`** (`arquitetura.md:87`) |
| `fila_da_pagina.py` | F-1, F-3 | A-2 |
| `projeto.py` | D-1 | A-1, A-6 |

Rename de 170 trocas (`arquitetura.md:368`) em paralelo a L-2: conflito garantido. O projeto usa worktree irmã.

**Os cortes são seguros?** Em disco, sim: nada de pickle persistido (o que cruza a fila é da mesma versão). Três riscos reais:

1. **13 arquivos de teste fazem `monkeypatch` em `pg.*`** (ex.: `monkeypatch.setattr(pg, "medir_inclinacao", ...)`, `tests/test_borracha.py:58`; `pg.propagar_padroes`, `tests/test_desfazer.py:375`). Partir `pagina.py` com reexportação faz o `setattr` cair no nome reexportado, e não no que a função chama: **o teste passa a rodar sem o dublê, sem reprovar** ou reprova por outro motivo. Trocar o alvo no mesmo commit.
2. **A-6 quebra uma ferramenta central.** `ferramentas/replay_fatia.py:346,368` e `ferramentas/medir_legendas.py:137` chamam `pg.ensinar` sem `gid`, ou seja, por `gid_do_box` (`pagina.py:920-921`). `arquitetura.md:220,225` propõe mover o método e exigir o `gid` olhando só a produção. Nenhuma das três chamadas passa o `gid`, e `replay_fatia` é PP2c e o CA-F.1.
3. **`A-1` simula os cortes sem as arestas de módulos novos** (`arquitetura.md:138`).

**Correção (roadmap:25, roadmap:261).**

> **T4 não é paralela. Parte vem antes de PP3, e o resto é janela entre passos.**
>
> **PP2d. Abrir espaço (mecânico, um commit por item, golden como pino):**
> 1. `pagina.py`: `FonteDePaginas`, `CacheDePaginas` e geometria vão a `fonte_de_paginas.py`. Reexportar. Os `monkeypatch` em `pg.*` dos itens movidos passam ao módulo novo no mesmo commit.
> 2. `app/documento.py`: `_escrever_as_linhas` e `_formato_novo` vão a `app/formatos_do_documento.py`.
> 3. **A-3:** a régua nova entra aqui, porque F-2 precisa de método em `VistaDoDocumento`.
> 4. `replay_fatia` e `medir_legendas` passam a dar o `gid`, e só então **A-6**.
>
> **A-1 (os cortes), A-2, A-4:** cada um numa janela sem passo de leitura em voo, na worktree única, e **A-2 antes de PP5**, porque ele reescreve `ponte_de_leitura.py` e `fila_da_pagina.py`. A-5 e A-7 ao tocar.

### I6. C-2, C-3, C-4 (spec:475-477)

**C-2.** O filho tem só `logging.basicConfig(level=WARNING)` em `stderr` (`servidor_de_leitura.py:415`). Falha nativa no torch não deixa rastro. `RotatingFileHandler` entre processos falha no Windows ao girar. Correção: `app.log` e `leitura.log`, e `faulthandler` em cada um, com o arquivo aberto em vida.

**C-3.** "Filho que não responde no prazo": `TEMPO_DO_PEDIDO = 600` (`servidor_de_leitura.py:57`), e a capa custa 6 min até L-9. Prazo curto mata leitura legítima; longo não serve. Enquanto atende interativo, a thread principal não recebe nada (`:220-222`). Medir o que importa: batimento.

> **C-3.** O filho manda `("vivo", id)` a cada 50 glifos (`_ler_com_vez`). Sem batimento por 60 s num pedido em curso, é morto e reaberto. **CA-C3:** um leitor falso que dorme para sempre no glifo 10 é morto em até 70 s, e o pedido segue a regra da queda.

**C-4.** `_caiu` conta `reinicios` no objeto inteiro, sem zerar (`:623-629`): a segunda queda da **sessão** desiste, e o lote para (`lote.py:310-317`). E a interface não sabe qual pedido estava em curso: reenvia todos (`servidor_de_leitura.py:630-633`).

> **C-4.** O filho manda `("comecou", id)` em `_atender`. Cada `Pedido` conta `quedas`, só o que estava em curso. Duas quedas no mesmo pedido: ele conclui com `ErroDoServidor("a página derrubou o servidor")`, e o lote o registra como falha e segue. `reinicios` zera a cada pedido concluído; só três quedas sem nada concluído no meio fazem desistir. **CA-C4,** acrescentar: um pedido na fila, que não estava em curso, não acumula queda.

### I7. Dependências e empacotamento (spec:487-492)

**Fato deste ambiente.** `.venv` com `include-system-site-packages = true`, Python 3.13.2: `torch 2.14.0`, `paddlepaddle 3.3.1`, `paddleocr 3.7.0`, `paddlex 3.7.2`, `pytesseract 0.3.13`, `chess 1.11.2` **e** `python-chess 1.999`, `opencv-python`, `opencv-python-headless` **e** `opencv-contrib-python`, todos no mesmo `cv2`. Tesseract em `C:\Program Files\Tesseract-OCR`, 740 MB com todos os idiomas, `por` de 2 MB e `eng` de 4 MB (`fast`, pelo tamanho). PP-OCRv6 em `~/.paddlex/official_models`.

**O que isso significa.** Convivem aqui, em processos separados, sem prova num venv limpo. Ninguém importou `torch` e `paddle` no mesmo processo: `experimentos/paddle_xv.py` importa `abbychess.pagina` e `paddleocr`, e `abbychess.pagina` não traz torch. Num venv limpo com lock, os três `opencv` se sobrescrevem: `abbychess` pede `opencv-python` (`pyproject.toml:15`), `core[ocr]` pede `-headless` (`core pyproject:28`), e `paddlex` traz `-contrib`. `pytesseract` é só do core.

**Core fora do PyPI.** `pyboxeditor @ git+https://github.com/DarcioAlberico/PyBoxEditor_Tkinter@<sha>` funciona para o lock; o repositório precisa estar acessível (Dec-1 pede privar **este**, e o outro?). `pip install -e` e "commit fixado no lock" são contraditórios: quem desenvolve usa o editável. E **os pesos não vão no wheel:** `projeto_dir()` é o pai do pacote (`config/paths.py:13-15`), `base_global()` lê `training_data` dali (`leitor.py:61-65`). Instalado não editável, abre sem rede e sem base. CA-E1 "a janela abre" passa com o OCR morto.

**Como acha o motor.** `_configurar_tesseract` é privado e só conhece dois caminhos (`ocr_service.py:173-187`). Há a sonda pública, com prazo (`tesseract_disponivel`, `:215-256`). O projeto já usa `ABBY_EPUBCHECK`, `ABBY_ACE`, `ABBY_CALIBRE`.

**Correção (spec:487-492).**

> **E-1.** O lock escolhe **um** OpenCV (`opencv-python-headless`; a janela é PySide6). `chess` e `torch` declarados; `python-chess` sai. **CA-E1**, acrescentar: e `CA-R3.1` passa no venv limpo, com a pasta dos pesos dada por `ABBY_PESOS` ou pelo checkout. A janela aberta sem pesos diz isso em Avisos.
>
> **E-5.** O `lock` traz `pyboxeditor @ git+…@<sha>`. No checkout editável, `ferramentas/conferir_core.py` compara o commit do checkout com o do lock, e o portão avisa (CA-R3.4). Os pesos têm manifesto com SHA-256 (E-4).
>
> **E-6.** Um só extra: `[opiniao-tesseract] = ["pytesseract"]`. **Paddle não é extra:** se Dec-2 o aprovar, vive em venv próprio, `%LOCALAPPDATA%\AbbyChessCraft\motores\paddle\`, com lock próprio, modelos em `PADDLE_PDX_CACHE_HOME` dentro dele, e o baixar depende de sim do usuário. O programa só conhece o `python.exe` dele e fala por `stdin`/`stdout`.
>
> **Localizar o motor:** `ABBY_TESSERACT`, depois `PATH`, depois os dois caminhos de `Program Files`. A versão e os idiomas vêm de `tesseract --version` e `--list-langs`, com prazo, uma vez por sessão.

### I8. L-3 e PP5: integrar antes de medir (spec:295, roadmap:183-185)

**O que quebra.**

- O roadmap faz `OpiniaoDeLinha` e o servidor (item 1), e só depois mede (item 3). Os scripts `experimentos/motores*.py` já comparam motores sem o programa. CA-L3.1 cabe em `medir_motores`, e a decisão vem antes da obra.
- O varrimento (`psm` 7 e 13) **exclui a chamada de página**, que é mais barata (B3).
- `_idioma_tesseract` só mapeia `en` e `pt` (`ocr_service.py:303-310`); `es`, `de`, `fr` (`modelo.py:119`) viram pacote inexistente e `MotorIndisponivel`. Passar `spa`, `deu`, `fra` funciona (`:310`).
- `_linhas_do_tesseract` fixa `--psm`, sem `--tessdata-dir` nem `--oem` (`:330-333`), e é privado. `fast` e `best` pedem `TESSDATA_PREFIX` por processo.
- A segunda passada da trama (`:418-430`) recorta um x fixo "que só serve à coluna esquerda" (`motores.md:89`): `_segunda_passada=False` na medida.
- Sem `OMP_THREAD_LIMIT=1`, o Tesseract usa vários núcleos e compete com o torch do filho (`servidor_de_leitura.py:207`): faz parte da configuração medida.

**Correção (spec:295, roadmap:183).**

> **CA-L3.1,** no varrimento, acrescentar: `psm` 3, 4 e 6 **de página**, alinhados por caixa, com `OMP_THREAD_LIMIT=1`, e sem a segunda passada; `psm` 7 e 13 **por linha** como referência. O padrão é o modo de página, se a revocação em Prosa por token ficar a menos de 5 pontos do melhor modo por linha.
>
> **PP5, ordem:** 1. L-3, só com a ferramenta, sem tocar no programa. Dec-2. 2. A opinião do vencedor no programa. 3. F-1. 4. F-2. 5. R-4.

### I9. Orçamento de RAM sem lugar (spec:136, spec:280, Dec-2)

**O que quebra.** CA-L2.5 diz "pico registrado na medida; acima do orçamento, o motor não sobe". Medida é documento; "subir" é produção. `psutil` é só `[dev]` (`pyproject.toml:23`) e opcional no filho (`servidor_de_leitura.py:200-205`). O orçamento é da máquina, não do livro, e não cabe em `Limiares`. O Princípio 7 existe porque a máquina já travou por memória (spec:136), e o filho de leitura já ocupa uns 700 MB (`servidor_de_leitura.py:3`).

**Correção (spec:280).**

> **CA-L2.5.** O registro é uma tabela no código, `PICO_DO_MOTOR = {motor: MB}`, escrita pela medida, com a data. O orçamento vem de `ABBY_ORCAMENTO_RAM_MB`, ou de 2.500. Antes de subir: `psutil.virtual_memory().available` ≥ pico + 1.024 MB; senão, não sobe, e Avisos diz o motivo. `psutil` passa a dependência. Um vigia de 2 s mata o processo do motor se o RSS passar do orçamento. **Tesseract** (< 200 MB, conta) não passa por isso. Nunca roda junto do lote (§4.1).

### I10. F-1: modos e lugar (spec:367,375,377)

- **"Amostra de treino" sem definição.** Candidatas: `paginas_da_amostra_guiada`, `candidatos_da_amostra_guiada` (`pasta_do_projeto.py:30-31`). Livro sem amostra guiada: qual modo? Sem definir, a fila depende de quem implementa, e CA-F.1 mede outra coisa.
- **Coeficientes.** Em arquivo de dados pedem `package-data` (`pyproject.toml:31-33`, só ícones) e E-1 já tem esse defeito (`arquitetura.md:269`). Em constante de módulo: sem Qt, sem torch, sem disco.
- **Ajuste.** `numpy` basta: 8 parâmetros, IRLS, em `ferramentas/`. Sem `sklearn`. Na interface só soma e `exp`. `docs/SPEC.md:726` fica intacto.
- **Ordem de hoje.** `_na_ordem` tem três modos, e `gids_fora_do_texto` e pulados vêm depois (`fila_da_pagina.py:66-70,189-197`): o escore é um quarto modo, sem tirar os outros.

**Correção (spec:377).**

> **Dois modos, por página.** Página em `paginas_da_amostra_guiada`, com `amostra_guiada_pendente`: a fila de hoje. As outras, com evidência carregada: a nova. Sem evidência: a de hoje. O modo sai em `ControladorDaFila`, e o F7 continua trocando. O escore é `abbychess/escore.py`, sem Qt: coeficientes em constante, escritos por `ferramentas/ajustar_fila.py`, com o SHA do ajuste em comentário. `ordem_da_fila` ganha `"escore"`.

### I11. PP2b mede cobertura em páginas soltas (roadmap:130-139, spec:196)

**O que quebra.** O sorteio **exclui as vizinhas** (spec:196). A partida que vem da página anterior aparece sem semente em toda página sorteada. O ponto de parada "cobertura ≥ 30 %" pode derrubar X-1 por causa do desenho da amostra, e X-1 cai ("Cobertura baixa: X-1 cai", roadmap:43).

**Correção (roadmap:135).**

> O teto sai em duas versões: **por página** (limite inferior, com o gabarito) e **por seguimento**, em 20 páginas seguidas de um livro, com o texto do programa e só para saber quantos tokens ganham posição ao atravessar a página. "Cai" só se os dois ficarem abaixo de 30 %.

---

## 3. Menores

**M1. D-2** (spec:466). Funciona, com ajustes. `EditorDeDiagrama.tabuleiros` é por **índice** (`app/editor_diagrama.py:226`), `fechar` o zera (`:278-281`), e os mixins o chamam na troca de página (`app/diagramas_na_janela.py:55-58`). Sem conflito de mixin: `_abrir_conferencia` tem `self.pagina` (`:34-40`).

> Guardar em `_guardados[(pid, caixa)] = (fen_base, tabuleiro)` ao fechar, só os com `pode_desfazer`. `abrir` recebe `pid` e devolve o guardado, se `diagrama.fen == fen_base`; senão, descarta e avisa (o F5 mudou a posição). Sair: `janela.py` tem **uma** linha livre, então estender a condição que existe, `if not self._gravou_ou_perder(projeto) or not self._edicoes_resolvidas():` (`app/janela.py:329`), e pôr `_edicoes_resolvidas` em `DiagramasNaJanela`.

**M2. D-4** (spec:468). Serve como escrito: `continue` em `exportar.py:393-398`. A página importada que cai nos boxes herda B1 (sem diagrama, x fictício). O relatório diz: "saiu das caixas aproximadas, sem os diagramas da camada", para que `camada_falhou` não pareça detalhe.

**M3. C-1, C-5** (spec:474,478). `render.vigiar_o_pai` serve: chamar no começo de `_principal` (`servidor_de_leitura.py:413-419`), antes de carregar os modelos, que levam segundos. Cuidar para o `import` de `render` não trazer Qt: `test` "modulos" confere (`:408-409`). C-5 só vê o processo do teste; o `ERROR` do filho fica de fora, e a queda vai pelo `("caiu", …)`.

**M4. L-5 e `Limiares`** (spec:317). `asdict(self.dados)` grava todos os limiares em todo `salvar` (`projeto.py:346`). Mudar o padrão de `base` não muda livro existente: **CA-L5.2 já vale, sem migração**. Só o campo novo pede cuidado: `TIPOS_DOS_LIMIARES = (int, float)` para todos (`dados_do_projeto.py:95`), e `bool` não vale por número (`:110`). A variante (b) com `Limiares.knn_exige_top3: bool` **faz o projeto não abrir** ("está ilegível", `projeto.py:776-777`). Variante em constante, ou tipo próprio na tabela. `m` e coeficientes não vão a `Limiares`: não são do livro.

**M5. Disco** (spec:239,264). `gv.gravar_json` usa `indent=1` (`gravacao.py:231`), que dá uma linha por campo: em arquivo derivado, triplica o tamanho (§5, item 9). Arquivo derivado: `gv.gravar_bytes(json.dumps(..., separators=(",", ":")))`.

**M6. Medida e teste.** R-3 pede JSON igual em duas rodadas (CA-R3.5): opinião em segundo plano, gravando, suja a pasta. `medir` e `replay_fatia` ligam o programa sem o trabalhador. Para os testes, o molde de `ABBY_FABRICA_DE_LEITOR` (`servidor_de_leitura.py:24-25`): `ABBY_TESSERACT` aponta para um `.cmd` ou `python` falso, que devolve TSV fixo; sem isso, CA-L2.* depende de ter Tesseract na máquina.

**M7. X-1.** `_LANCE` não aceita `e2-e4` nem `Cg1-f3` (`lances.py:87`): vira prosa, sem marca, sem cobertura. CA-X1.3 mostra 0 % e parece "livro sem lance". O JSON da cobertura traz também os tokens com **forma** de lance longo, não contados.

---

## 4. O desenho mais simples que funciona

### 4.1 L-2, texto de substituição (spec:249-280)

> ### 4.2 L-2. A segunda opinião
>
> Sem uma leitura independente, o programa não sabe quando errou com confiança alta.
>
> **O que o motor devolve.** `opiniao.ler_pagina(cinza, idioma) -> [PalavraDaCamada]`: a mesma estrutura de `camada.py` (caixa em pixels da página, texto), mais a confiança. Com o Tesseract: `OCRService.tesseract_pagina_detalhada_conf`, que é pública, ou `pytesseract.image_to_data` se a medida escolher outro `psm`.
>
> **Onde roda.** Uma thread `opiniao` do processo da interface; o OCR é um `subprocess`, e a página vem de `pagina_da_entrada(entrada, render)`. **Sem processo Python novo.** `OMP_THREAD_LIMIT=1`. Uma página por vez. Nunca enquanto o lote ou um F5 estiverem em curso: espera, e retoma sozinha (Princípio 7). Sem usar a fila de tarefas da janela (`_agora` travaria a edição). Motor que passa do prazo: morto; página fica sem opinião; próxima.
>
> **Quando.** Entra na fila: `pagina_reconhecida` (F5), `pagina_do_lote` (o lote) e abrir uma página lida sem opinião, esta na frente. Só páginas com algum glifo que não seja `manual`, `revisado` ou `nativa`. Só leitura: lê, mostra, não grava.
>
> **O que grava.** `opinioes/p<pid>.json`, JSON compacto, pela própria thread (o processo dono da pasta): `chave` e as palavras. **A chave é da imagem, não da linha:** `sha1` da receita da entrada (`fonte`, `pagina`, `quadro`, `giro`, ângulo aplicado, `borrachas`), mais motor, versão, idioma e configuração. Editar glifo, dividir, juntar, F5 e o desfazer não invalidam. Borracha, corte, giro, ângulo invalidam. Reler a mesma imagem não chama o motor. Arquivo descartável.
>
> **Como compara.** `opiniao.comparar(pagina, palavras) -> EvidenciaDaPagina`, função pura, sem disco. Cada glifo cai na palavra da opinião que contém o centro dele (`camada._indices_na_caixa`, que passa a público, para não somar à catraca de A-2). Os glifos de uma palavra do programa e as palavras da opinião que eles tocam formam um grupo. No grupo, compara-se o texto **sem espaços** (`sessao.alinhar`, depois de NFKC na opinião e `tx.normalizador` no programa): igual é concorda, e diferença só de espaço é "espaço". Fora disso, o alinhamento dá gid a gid qual caractere difere: o box de vários caracteres e a ligadura contam pelas letras, o box vazio aceita qualquer letra e a recebe como sugestão. Sem par: nada. **Sem opinião:** glifo `manual`, `revisado`, `nativa`, conferido; virtual; `angulo != 0`; palavra com figurina ou dígito, salvo o medido em CA-L3.1. **Refazer só quando `_chave` da página muda**, e só aí; é um dict em memória.
>
> **Como chega à tela.** `executar.na_interface(...)`, com o teste da `geracao`, como `ponte_de_leitura`. Se a página é a aberta: `glifos_mudaram`, e a sessão aberta faz esperar, como hoje. Nenhuma releitura.
>
> **Quando a linha muda:** não há linha. O glifo editado é comparado de novo com a mesma palavra. Se ficar igual, a marca some; se o usuário aceitou, `revisado`, some. Glifo novo de dividir compara como os outros. Palavra da opinião sem nenhum glifo, fora de tabuleiro, é sinal de "tinta sem box": entra só depois de medida.
>
> **O que não faz.** Não toca em `BoxEntry`. Não entra no JSON da página. Não ensina padrão. Não entra em `contexto.pendentes` (B4).
>
> **PP-OCRv6.** Só se Dec-2 o aprovar. `subprocess` do `python.exe` do venv dele, com recortes por linha pelo `stdin` e texto pelo `stdout`, e a mesma `EvidenciaDaPagina`, com `sessao.alinhar` dentro da linha.
>
> **Custo, a medir no CA-L3.1.** Pelo core: página de 0,7 a 3 s, com casos de 19 s. 300 páginas: de 3,5 a 15 min, sobre 48. Por linha, os 22 min de antes.
>
> - **CA-L2.1.** Sem nenhum motor, o programa funciona como hoje e diz uma vez, em Avisos, que está sem opinião.
> - **CA-L2.2.** Matar `tesseract.exe` no meio não muda a leitura; a fila segue.
> - **CA-L2.3.** Um `gid` manual, revisado ou conferido não recebe marca.
> - **CA-L2.4.** Na mesma imagem, a segunda rodada não chama o motor, mesmo depois de F5, dividir e desfazer. Com uma borracha, chama.
> - **CA-L2.5.** Ver I9.
> - **CA-L2.6.** Tabela de alinhamento: `1.e4` × `1. e4` não marca lance; `ﬁm` × `fim` concorda; box `xf3` × `xf3` concorda; `□` × `a` sugere `a`; `rn` × `m` marca os dois glifos, sem sugestão em lote; página nativa não chama o motor.
> - **CA-L2.7.** Enter em p95 ≤ 100 ms com evidência carregada, e sem abrir arquivo.
> - **CA-L2.8.** Trocar de projeto com a opinião em curso não grava nem mostra nada dela no novo projeto.

### 4.2 Roadmap (roadmap:166-196)

> **PP2d** Abrir espaço (I5).
> **PP4** L-1a e L-1b. Medir `cobertura@3` com a ferramenta. Sem arquivo novo. **Custo:** pequeno.
> **PP5** Medir L-3, sem integrar. Dec-2. `opiniao.py`, `EvidenciaDaPagina`, `escore.py`, F-2. R-4. **Custo:** 2 a 3 sessões, contra as 3 a 5 de hoje.
> **PP6** L-4 1:1.
> **PP7** F-3. X-3. X-1 sem hipóteses. L-1c e X-1 com hipóteses, se `cobertura@3` passou.

### 4.3 O que sai

| Sai | Por quê | Fica no lugar |
|---|---|---|
| `servidor_de_opiniao` | Tesseract é processo por si | Thread + `subprocess` |
| `hipoteses/p<pid>.json` | F-1 não precisa; X-1 pede pouco | `box.margem` e `hipoteses_recortes` sob demanda |
| `OpiniaoDeLinha(Protocol)` com dois motores | Um é provável; dois só com Dec-2 | Uma função |
| Chave por SHA do recorte | Depende da caixa da linha | Chave da receita da imagem |
| Alinhamento próprio | Já há dois | `camada._indices_na_caixa`, `sessao.alinhar` |
| `[opiniao-paddle]` | Conflito no venv | Venv próprio |
| `Validacao` com índice, `Lance` com gid | Redundantes | `legais`, `gids_do_rejeitado` |
| Estado "página de imagem" | Formato e tabela | Área `figura` |

---

## 5. Item a item

**1. L-1.** Top-3 da rede: sim, sem core novo, sem segunda passada, com invólucro em `predictor=`. Margem do k-NN: já vem. 2.ª classe do k-NN global: não, sem outra busca ou privado. Livro: a rede não roda, logo top-3 só com custo. `reader`: não entra. Veto: registrar top-3 **mais** o lido. Arquivo por `gid`: não sobrevive sem guarda de caixa e chave de imagem, e nem é preciso. `spawn` e pickle: aguentam. Ver B2.

**2. L-2.** Terceiro processo: cabe, sem reuso, e sobra (I1). Quem dispara: `pagina_reconhecida`, `pagina_do_lote`, abrir a página. Depois do lote e do F5. Chega por `na_interface`, sem reler. Linhas: não usar. Alinhamento: B3 e §4.1. SHA do recorte: B3. Mostrar quando muda: comparar de novo. `contexto`, `pendentes`, `resumo`: não entram (B4). Fila recalculada em `FilaDaPagina`, sem arquivo, menos de 5 ms (conta).

**3. L-4.** Token vira edição só no caso 1:1, por `edicao.trocar_varios`. O resto, pela sessão, com a fonte `manual` e o usuário. Desfazer único: sim. `fonte "opiniao"` sozinha é relida e mal rotulada nos lugares da tabela de B5. Com `revisado`, `FONTES_CONFIRMADAS`, `volta_pelo_contexto` e os dois rótulos, deixa de conflitar com o Princípio 5.

**4. F-1, F-3.** Mora em `FilaDaPagina` e `escore.py`, sem Qt nem torch. Dados: evidência em memória mais box. `Lance` não precisa de gid (I4). O Documento pinta token por `estados`, e a montagem permite. Catracas: `pagina.py`, `documento.py` e tetos pedem PP2d; `janela.py` não precisa crescer; cc < 10 exige helper.

**5. X-1.** Compatível no desenho, não no código: `lances.py` é por texto; `core/notacao.py` não tem FEN nem alfabeto. Reaproveita `custo_da_troca` e a sincronia. SAN a boxes: gid × letra; média sem hipóteses, média a alta com. Letras por idioma: `modelo.PECAS` existe, mas ligado ao idioma; `Notacao` não é alfabeto (B7).

**6. L-9, D-1 a D-4, C-1 a C-5.**

| Item | Como escrito | Ver |
|---|---|---|
| L-9 | Não: estado novo e CA-L9.3 sem caminho | B6 |
| D-1 | Em parte: abrir precisa de O(1), e a classe é `OSError` | I2 |
| D-2 | Sim, com chave e base do FEN; uma linha em `janela.py` | M1 |
| D-3 | **Não**: destrói a página | B1 |
| D-4 | Sim, com aviso | M2 |
| C-1 | Sim | M3 |
| C-2 | Falta o filho | I6 |
| C-3 | Não como "prazo": batimento | I6 |
| C-4 | Não sem refazer `_caiu` | I6 |
| C-5 | Sim, só no processo do teste | M3 |

**7. A-1 a A-6.** Cortes seguros em disco; arriscados nos 13 testes com `monkeypatch`. A-6 quebra `replay_fatia`. Conflito garantido com a leitura se T4 correr em paralelo. Ordem: PP2d antes de PP3; A-2 antes de PP5 (I5).

**8. Dependências.** Convivem aqui, por `system-site-packages`, sem prova num venv limpo, com três `opencv`. Extra só para `pytesseract`; paddle em venv próprio. Motor: `ABBY_TESSERACT`, `PATH`, `Program Files`. RAM: variável e tabela (I9). Modelos: `PADDLE_PDX_CACHE_HOME` no venv dele; hoje em `~/.paddlex`. Core: `git+…@sha` no lock; pesos à parte, porque o wheel não os leva (I7).

**9. Formato e disco.** Conta, 1.500 glifos por página (o core cita 1.404, `core/notacao.py:26`; a SPEC, 2.000), 30 linhas, 300 páginas:

| O quê | Bytes por item | Por página | Livro |
|---|---|---|---|
| `paginas/p<pid>.json` hoje (`indent=1`) | ~280 B por glifo | ~420 KB | **~126 MB** |
| `hipoteses/`, compacto | ~100 B por glifo | ~150 KB | ~45 MB |
| `hipoteses/`, com `gravar_json` | ~300 B por glifo | ~450 KB | **~135 MB: dobra o projeto** |
| `opinioes/`, por linha, com SHA | ~220 B por linha | ~7 KB | ~2 MB por motor |
| `opinioes/`, por palavra, com caixa | ~70 B por palavra, 300 palavras | ~21 KB | ~6 MB |
| `.antes-do-lote/` (refazer tudo) | igual à página | ~420 KB | ~126 MB |

Mudanças no projeto, pelo desenho da §4: `opinioes/` (nova, descartável, fora de `paginas/`, logo fora do `glob` de `recalcular`, `resumo_do_livro.py:112`); `Projeto.letras_das_pecas` e `campos_do_box` (projeto antigo entende: `extras`, `_dados_do_projeto`, `projeto.py:781-789`); `livro.json` com `fortes` (sem versão nova; `.get`). **Sem limiar novo. Sem versão nova.** `antes_do_lote` guarda só a página (`antes_do_lote.py:28-33`): com a chave de imagem, a opinião continua valendo depois de voltar; com `hipoteses/` por gid, ficaria desencontrada. Portabilidade: a chave não tem caminho; copiar o projeto leva a opinião, e outra versão do motor só faz reler. `limpar_temporarios` já cobre `.json.tmp` em qualquer pasta (`gravacao.py:260-261`).

**10. Riscos não listados, e o superdimensionado.**

Riscos, além dos achados:

- **Temporários do `pytesseract`:** PNG de página a 300 dpi em `%TEMP%` a cada chamada, sob antivírus. Medir o custo real; se pesar, `tesseract stdin stdout tsv`.
- **`--psm 3` pula linha** ("às vezes pula um cabeçalho em negrito inteiro", `ocr_service.py:394-395`): glifo sem opinião não é marca. O silencioso em cabeçalho fica como hoje.
- **A opinião que muda o realce sob o revisor,** quando chega no meio de uma página: a fila reordena. Regra: o atual não muda; a fila nova vale na próxima decisão.
- **`camada.py` tem coordenadas sem endireitar** (`camada.py:92-94`): ao virar motor gratuito de ClearScan, compensar o ângulo, porque `_na_caixa` tem só um terço da altura de folga (`:105-108`). Motor grátis nesses livros, e medir antes.

Superdimensionado para um usuário só, além da §4.3:

- **Recalibração por livro com intercepto** (spec:373): sem dado de T1 nem páginas auditadas no primeiro ano. Fica para quando houver 10 erros auditados, e não como requisito de PP5.
- **Isotônica depois da logística** (spec:367): Platt basta, e a ordem não muda com calibração monotônica; só o corte por `m` importa, e ele é por posto.
- **CI** (spec:488): core e pesos fora; `pre-push` local cobre o único usuário.
- **Operador novo de mutação** (spec:481): 13 % de cobertura e dois travamentos de máquina na última rodada. Depois de PP5, se sobrar interesse.
- **A-4 com pyright em quatro módulos** (spec:503): `Funcao(StrEnum)` e `Pid` pagam; o portão com pyright, um dia. Ele pede node (o `pip install pyright` baixa), e as anotações falsas de `modelo.py:364,418` viram trabalho antes de ganho.

---

## 6. Limites

- Nada rodou. Tempos de 0,7 a 3 s e 0,16 a 0,24 s são os que `ocr_service.py:95-99` registra; o resto marcado "conta" é estimativa minha, para dimensionar.
- A precisão de Tesseract de página, alinhado por caixa, **não foi medida**: os números da spec são de `--psm 7` por linha (`experimentos/motores.py:73-74`). I8 existe para isso: se ele perder, o motor lê por faixa e o resto da §4.1 não muda, porque `image_to_data` também dá caixa de palavra na faixa.
- Não abri `sequencia_do_livro.py` inteiro, `migracoes.py`, `core/livro.py`, `core/diagrama.py`, nem o corpo de `app/espaco.py`. As afirmações sobre eles vêm de trechos lidos ou de `arquitetura.md` e `motores.md`, e estão citadas assim.
- I3 é leitura do caminho, sem execução. Vale escrever o CA-D5 como teste vermelho antes de mudar.
