# Auditoria da cadeia de OCR de páginas de xadrez

Mapa independente, feito só por leitura do código, em 2026-11-05.

**Estado lido.** App: worktree `AbbyChessCraft-coordenadas`, ramo `lacunas-da-spec`, commit `262d897`, árvore limpa. Core: `PyBoxEditor_Tkinter`, commit `70e6a86`, com arquivos não rastreados só em `Box/` e `fonts/`. A `main` e `passo-i-treino` podem diferir disso.

**Apelidos de caminho.**
- `core/` = `C:\Python-Chess2\PyBoxEditor_Tkinter\core`
- `ui/` = `C:\Python-Chess2\PyBoxEditor_Tkinter\ui`
- `abby/` = `C:\Python-Chess2\AbbyChessCraft-coordenadas\abbychess`
- `docs/`, `tests/`, `ferramentas/` = as do `AbbyChessCraft-coordenadas`

**Legenda de evidência.** **[F]** fato conferido no `arquivo:linha` citado. **[I]** inferência minha a partir de fatos. **[H]** hipótese, a medir. **[Doc]** o número ou a frase é de um documento ou comentário, e não foi reproduzido aqui.

**O que não fiz.** Não rodei OCR, pytest nem modelo. Só li código, os JSON de metadados e os gabaritos. Nenhum número de ganho é meu; os "cortes" de decisão na seção 4 são propostas de critério, não previsões.

---

## 0. O que mais importa

1. **"A cadeia de OCR" são três cadeias disjuntas, e o app roda a mais pobre em contexto.**
   - O app (`abby`, F5 e lote) lê glifo a glifo: k-NN do livro → CNN → k-NN global. Não chama Tesseract, leitor de linha, `core.livro`, `geometria_da_linha`, `notacao.analisar` nem `coleta`. [F, seção 1]
   - O `core.livro.extrair` (exportação do PyBoxEditor) é CNN + Tesseract com fusão por palavra, e não tem k-NN nenhum. [F, `core/editorial_legacy.py:162-166`]
   - A janela do PyBoxEditor é CNN → k-NN → EasyOCR glifo, mais poda geométrica e EasyOCR de linha. [F, `ui/reconhecimento.py:1069-1073`]
   - O "1,59 % de CER" e o "91,2 % por linha" do `docs/ANALISE_PYBOXEDITOR.md:44-46` medem as outras duas, e não o que o app faz. [I]
2. **Nada no app usa contexto para decidir uma leitura de glifo.** Palavra, léxico, linha, legalidade e diagrama só mandam à fila ou sugerem. As únicas trocas automáticas de caractere são a caixa pela altura (`abby/montagem.py:388-406`) e o reler pelo efeito (`abby/efeitos.py:317-333`). [F]
3. **A decisão é gulosa e o top-k é jogado fora.** O `Leitura` do app guarda um caractere, uma fonte e uma confiança. A margem do k-NN é descartada em `abby/leitor.py:178`, e o palpite da rede abaixo do limiar vira `""` com confiança 0. [F]
4. **O k-NN do livro vence a rede sem comparação e sai da fila.** Conf 0,25 do livro ganha de 0,99 da rede (`abby/leitor.py:166-168`), e `precisa_revisao` o isenta (`abby/leitor.py:41,249-250`). Só o `contexto` o traz de volta. [F]
5. **O árbitro da segmentação compara escalas diferentes.** No app, ele é a cascata inteira, sem altura, e devolve 0,0 quando ninguém leu (`abby/leitor.py:201-204`, `core/services/box_service.py:444-454`). O core documenta que esse papel é da rede crua (`core/services/learning_service.py:175-179`). A medida citada em `abby/pagina.py:6-7` não vale para essa configuração. [F + I]
6. **A legalidade só julga o diagrama, depois de tudo pronto.** `lances.validar` não toca em caractere nem em FEN. `notacao.analisar` não recebe FEN, só começa em `1.` e o app não o chama. [F]
7. **O gabarito só sustenta um livro.** Há 213 linhas com `texto_verificado: true`, todas do Xadrez Vitorioso. Darcy e Yusupov têm 0. [F, leitura de `tests/verdade/*/*.json`] Sem isso, nenhuma medida de CER de prosa ou lance generaliza. Vale consertar antes das mudanças da seção 4.

---

## 1. Inventário de motores

Estado: **LIGADO** roda em toda página do app; **SÓ PYBOX** roda no PyBoxEditor e o app não o alcança; **INERTE** o código existe e nenhum caminho de produção o aciona.

### 1.1 Pré-processamento e segmentação (o primeiro "motor", e o mais decisivo)

| Elo | Entrada → saída | Onde | Estado |
|---|---|---|---|
| Render do PDF | página → cinza a 300 dpi | `DPI_PADRAO=300` em `core/services/pdf_service.py:54`; `abby/pagina.py:395-404` | LIGADO |
| Endireitar | cinza → ângulo por variância da projeção, em meia resolução, ±3°, passo 0,05° | `abby/pagina.py:54-85`; giro `INTER_CUBIC`, `:88-95`; aplicado acima de 0,1°, `:184-185` | LIGADO se o projeto nasceu assim |
| Apagar fios | cinza → cinza sem componente longo e fino | `abby/pagina.py:660-687`, chamado em `:639` | LIGADO |
| Binarização | cinza → máscara. `auto` = Otsu se plausível, senão adaptativo | `core/preprocess.py:97-127`; `core/services/box_service.py:88-116` | LIGADO |
| Negativo, trama, vertical | reescrevem `th` e boxes antes de medir | `core/services/box_service.py:244-252` | LIGADO |
| Componentes conexos | `findContours(RETR_EXTERNAL)`, `boundingRect` inteiro | `core/services/box_service.py:208-215` | LIGADO |
| Merge vertical | funde pingos e pontuação, só por geometria | `core/services/box_service.py:1919`; `:254` | LIGADO |
| Descarte de não texto | tira blocos grandes | `core/services/box_service.py:53` | LIGADO |
| Dividir linhas coladas | corta box alto por vale de perfil | `core/services/box_service.py:56,816` | LIGADO |
| Dividir glifos colados | perfil propõe, árbitro endossa com margem 0,00 | `core/services/box_service.py:57-62,417,420-454,660-786` | LIGADO, árbitro = `leitor.arbitro` (`abby/pagina.py:649-650`) |
| Devolver pingos | órfão pequeno volta ao box de baixo | `abby/pagina.py:695-730` | LIGADO |
| Tirar boxes do tabuleiro | contido no tabuleiro + 1,4 escalas sai antes de ler | `abby/pagina.py:589,614-616` | LIGADO sem áreas |
| Filtrar por áreas | só fica box com centro em área de tipo TEXTO | `abby/zonas.py:771-782,814-827` | LIGADO com áreas |

### 1.2 Reconhecedores de glifo

**CNN de glifos (`SimpleCNN`).** LIGADO.
- Entrada: recorte cinza esticado a 32×32 sem preservar proporção, `cv2.resize` com interpolação padrão, dividido por 255. [F, `core/neural_trainer.py:925-926`; arquitetura `core/neural_model.py:5-38`]
- Saída: `(char, prob)`. Softmax com temperatura 1,825, em `model_meta.json`. [F, `core/neural_trainer.py:937`] 314 classes, treinado em 2026-08-25. [F, `model_meta.json`]
- Chamada: `core/services/ocr_service.py:962`, por `abby/leitor.py:174-177`. Passa se `conf > 0,80` (`abby/dados_do_projeto.py:42`, `core/services/ocr_service.py:971`).
- Se o veto de proporção recusa e não há substituta, **a leitura vetada segue** com a confiança dela. [F, `core/services/ocr_service.py:963-972`]
- Palpite para glifo sem leitura: `abby/leitor.py:180-199`, só para a tela (§9.2); não entra no box. [F]

**k-NN global (`CharacterLearner`).** LIGADO.
- Entrada: mesmo esticão 32×32, cinza cru, L2 contra a matriz da base. [F, `core/learner.py:507-508`] `K_VIZINHOS=1`. [F, `:225`]
- Saída: `(char, 1 − d/2000, margem de Lowe)`. [F, `core/learner.py:692-696`]
- Chamada: `core/services/ocr_service.py:976`. Passa se `conf > 0,30`, ou seja, `d < 1400` (`abby/dados_do_projeto.py:43`). A margem é devolvida pelo core e **descartada pelo app**. [F, `abby/leitor.py:178`]

**k-NN por livro (`PadroesDoLivro`).** LIGADO, primeiro da cadeia.
- Entrada: recorte, altura relativa, efeito. [F, `abby/padroes.py:291-326`]
- Descritor: cinza cru 32×32 sem normalizar contraste, `_vetor`. [F, `:138-140`]
- Travas, nesta ordem: `d < 1500`, proporção 1,6×, altura 20 %, efeito compatível. [F, `:304-320`]
- Saída: `Resposta(char, 1 − d/2000, d, caminho)`, a amostra vencedora. [F, `:323-326`]
- `d` e os candidatos de outras classes são descartados no `Leitura`. [F, `abby/leitor.py:155-157`]

**EasyOCR glifo.** Desligado no app por um leitor falso, `_SemEasyOCR`. [F, `abby/leitor.py:54-58,106`] Fim da cadeia: `Leitura("", "none", 0.0)`. [F, `core/services/ocr_service.py:1001-1006`] SÓ PYBOX.

**Tesseract glifo (`--psm 10`).** `core/services/ocr_service.py:262-300`, sem `lang`, cai no padrão do executável. Consumido só pelo adapter do ensemble (`core/ocr_engines.py:95-96`). INERTE no app.

### 1.3 Leitores de linha e página

**Tesseract de página e faixa.** SÓ PYBOX. Nenhuma ocorrência de `tesseract` em `abby/`. [F, busca sem caixa]
- Modos: página `--psm 3` (`core/services/ocr_service.py:413`), faixa `--psm 7` (`:400`), sempre com `-c preserve_interword_spaces=1` (`:333`). Sem `--oem`, sem lista de palavras, sem `user-patterns`. [F]
- Idioma: um por vez. `en→eng`, `pt→por`, o resto passa literal. [F, `:303-310`] Nunca `eng+por`. [F, `core/editorial_legacy.py:166,183`]
- DPI: a imagem que `livro.extrair` renderiza, 300 por padrão. [F, `core/livro.py:4221,3859`]
- Saída: `[(texto, conf, caixa, detalhes)]`, palavras com `conf/100` e média da linha. [F, `core/services/ocr_service.py:345-387`]
- Segunda passada em páginas com mais de 20 mil componentes, sobre um recorte fixo de x (80 px a 47 % da largura). [F, `:442-460`] Só serve à coluna esquerda típica do livro que motivou a regra. [I]
- Chamada: `core/editorial_legacy.py:165-166,182-183` → `core/livro.py:3918-3923,3714-3721`. Prazo e disjuntor: `core/livro.py:4265`.

**EasyOCR de linha.** SÓ PYBOX. `core/services/ocr_service.py:656-679`; distribuição pelo alinhamento `core/leitura_de_linha.py:343,387-524`; chamada `ui/reconhecimento.py:1069-1073` e `core/searchable_pdf.py:177`. Confiança: a da faixa inteira, combinada com a do glifo por concordância. [F, `core/leitura_de_linha.py:375-384`]

**CRNN/CTC próprio.** INERTE.
- `LinhaPredictor` em `core/linha_trainer.py:811`; portão `modelo_utilizavel`, CER máximo 0,15 (`:37,215`).
- Último registro do treino: `cer: 0.9634`, época 21. [F, `text_line_model.json`] Divisão 333 treino e 1.136 validação. [F, `text_line_training_report.json`]
- O portão o recusa. [I, pelo `cer_de_validacao` em `core/linha_trainer.py`; não executei]
- Só `ocr_training_state.json` diz `line_model: true`, o que engana. [F]

**PaddleOCR.** Opcional, `core/services/ocr_service.py:684-830`. INERTE no app.

**Ensemble de linha.** `core/ocr_engines.py:209-290`. `usar_ensemble=False` por padrão (`core/editorial_legacy.py:66`). INERTE no app.

### 1.4 Camada nativa do PDF

- **Régua** `pdf_nativo.avaliar_pagina`: página a página, recusa texto invisível, ClearScan, sem Unicode, figurina em imagem e mais. [F, `core/pdf_nativo.py:670-781`]
- **Oferta na criação** do projeto, amostra de 12 páginas. [F, `abby/nativo.py:46-54`, `abby/app/dialogos.py:213`]
- **Importar**: palavra vira `BoxEntry(palavra, x1, y1, x2, y2, 1.0, "nativa")`, `revisado=True`. [F, `abby/nativo.py:140-141`]
  - A caixa é fictícia em x: `cursor = 40.0` e largura proporcional às letras. [F, `:131-139`]
  - `Figura` não entra: `_boxes` só trata `Paragrafo` e `Tabela`, e `importar` não grava tabuleiros nem diagramas. [F, `:77-80,98-115`]
- **Exportar**: `camada="auto"` é o padrão, e os dois chamadores não o mudam. [F, `abby/exportar.py:213,652,709`] Página aceita **sai da camada e os boxes são ignorados**. [F, `:236-237`] Edições feitas nela não chegam à exportação, salvo o lado conferido do diagrama. [I, `:409-420`]
- **Segunda opinião ClearScan**: `abby/camada.py:120-194`, só na verificação de texto, chamada em `abby/controladores.py:98-108`. Só sugere. [F]
- **`mapa_glifos`**: só `ui/reconhecimento.py:35-36`. INERTE no app.

### 1.5 Diagramas

- **Detector**: `diagrama.localizar`, contorno grande e quase quadrado antes do descarte, mais `_aninhados` e `_de_moldura_partida`. [F, `core/diagrama.py:452-503,512-561`] Chamada `abby/pagina.py:646`. LIGADO.
- **`deteccao_de_tabuleiro`**: no app só entra por `_de_moldura_partida`, e só a caixa é usada. [F, `core/diagrama.py:553-560`] O `warpPerspective` dele (`core/deteccao_de_tabuleiro.py:177-178`) não alcança `diagrama.ler`, que corta em grade uniforme. [F, `core/diagrama.py:1068-1074`]
- **Leitor**: resíduo da casa contra a mediana da mesma cor → rede de ocupação (`p ≥ 0,5`) → rede de peças só nas ocupadas → árbitro. [F, `core/diagrama.py:1086-1114,1500-1537`] Chamada `abby/diagramas.py:345-347`. LIGADO.
- **Confiança**: `Casa.confianca` (peça, com T) e `confianca_ocupacao`. Porteiro: menor das duas abaixo de 0,98 reprova. [F, `core/diagrama.py:1589-1628`] App: `DiagramaLido.motivo`. [F, `abby/diagramas.py:363-367`]
- **Árbitro**: troca a casa mais barata para: sem peão nas pontas, um rei de cada cor. Não usa legalidade de xeque nem o texto. [F, `core/diagrama.py:1381-1459`]
- **Top-k por casa**: `pontuacoes_de_casas`. [F, `core/diagrama.py:1199-1229`] Único consumidor: `core/biblioteca/ocr_phase4.py:441`, biblioteca fora de produção. INERTE.
- **Rótulos a–h, 1–8**: `ler_rotulos`, lidos por `leitor.arbitro`. [F, `core/diagrama.py:852-907`, `abby/servidor_de_leitura.py:120-121`]
- **Lado a jogar**: legenda, verbo do Mirkovic, número do primeiro lance. [F, `abby/diagramas.py:86-90,370-384`, `abby/lances.py:548-556`]

### 1.6 Conhecimento que opina

| Motor | Entrada → saída | Onde | Estado |
|---|---|---|---|
| Veto de proporção | `(char, w, h, altura ref.)` → cabe? | `core/proporcao.py`; `core/services/ocr_service.py:949-958` | LIGADO, sem altura no árbitro |
| Máscara de alfabeto | `(char, idioma)` → permitido? | `core/alfabeto.py:45-57` | **INERTE no app**: `_ler_global` não passa `idioma` (`abby/leitor.py:174-177`), e sem idioma ela sempre diz sim |
| Léxico | palavra de prosa → sinaliza | `abby/verificacao.py:119-147`, `core/lexico.py:1016`; só na verificação, `abby/controladores.py:64-92` | LIGADO, não decide |
| `juntar_hifenizadas`, `partir_colada`, `reparar`, `_corrigir_juncoes` | o léxico decide | `core/lexico.py:278,334,871`; `core/livro.py:1971` | SÓ PYBOX; zero ocorrências em `abby/` |
| Palavra e linha (`contexto`) | caracteres, caixas → improvável + sugestão | `abby/contexto.py:127-138,235-253,391-431` | LIGADO, só fila e sugestão |
| Caixa pela altura | caixas da linha → troca de caixa | `abby/montagem.py:352-376`; leitura `:388-406` via `abby/arrumacao.py:41`; exportação `:270` | LIGADO, **troca sozinho** |
| Geometria de Baird | top-k + linha → poda em grupos de mesmo desenho | `core/geometria_da_linha.py:446-513`; `core/livro.py:2408-2413` | SÓ PYBOX |
| Legalidade do lance | FEN + linha → estado do diagrama | `abby/lances.py:362-434`; `abby/arrumacao.py:24` | LIGADO, não muda leitura |
| `notacao.analisar` | boxes → correções por legalidade | `core/notacao.py:524-650`; chamadores `ui/reconhecimento.py:1681` e `core/pgn.py:228` | SÓ PYBOX (botão e PGN) |
| Negrito | espessura em cinza + régua por caractere → `Optional[bool]` por palavra | `abby/efeitos.py:26-65,128-146`; `core/negrito.py` | LIGADO |
| Itálico | cisalhamento da projeção → `Optional[bool]` por palavra | `abby/efeitos.py:208-256,308-314` | LIGADO |
| Colunas e ordem | boxes → colunas, faixas, ordem | `core/services/box_service.py:1402-1697`; `abby/layout.py:86-105` | LIGADO |
| Áreas automáticas e funções | boxes, tabuleiros, texto → zonas | `abby/zonas.py:351-458,490` | LIGADO |
| Margens corridas | livro inteiro → cabeçalho e rodapé | `abby/margens.py`; `abby/exportar.py:272-275` | LIGADO na exportação |
| Tabela | grade da página → células | `core/livro.py:2676` | SÓ PYBOX. No app, `tabela` é tipo imagem (`abby/zonas.py:61`) |

---

## 2. O grafo

### 2.1 App: F5 e lote, a ordem exata

`abby/servidor_de_leitura.py:114-126`; o lote usa a mesma função (`abby/lote.py:256,285`).

```
página endireitada (cinza 300 dpi)
  │
  ├─ apagar_fios → binária → boxes_antes_do_descarte ─→ diagrama.localizar ─→ TABULEIROS
  │                                                                              │
  └─ generate_boxes_opencv(arbitro = leitor.arbitro)                             │
        negativo, trama, vertical(arbitro), merge,                               │
        descarte, linhas coladas, colados(arbitro), ordem                        │
        → devolver_pingos                                                        │
        → sem áreas: tira boxes contidos no tabuleiro + 1,4 escalas              │
          com áreas: só centro em área TEXTO; escala = 0,0                       │
                     │                                                           │
                     ▼                                                           │
  ler_boxes: para cada box, sozinho e na ordem                                   │
    1. k-NN LIVRO   d<1500 + proporção + altura          ─ acha → FIM (livro)    │
    2. CNN          conf>0,80 (veto de proporção)        ─ acha → FIM (neural)   │
    3. k-NN GLOBAL  conf>0,30 (veto de proporção)        ─ acha → FIM (learner)  │
    4. EasyOCR falso → ("", "none", 0.0)                                         │
                     │                                                           │
                     ├─ boxes lidos ────────→ ler_diagramas(arbitro p/ rótulos) ◄┘
                     │                          rótulos → orientação; legenda → lado
                     ▼
  medir_efeitos (palavras, char → régua) → negrito, itálico por palavra
                     │
  reler_pelo_efeito: só quem foi lido por amostra de efeito incompatível volta a `ler`
                     │  ─── FIM DO SERVIDOR ────────────────────────────────────
                     ▼
  na interface, aplicar_lida (abby/arrumacao.py:27-58):
    corrigir_a_caixa_na_leitura → reconciliar (decisões seguem gids, IoU) → diagramas.mesclar
    → zonas.depois_de_ler → vincular_legendas → lances.validar_pagina → estado
                     │
                     ▼
  fila: precisa_revisao(conf<0,90, fora livro/manual/nativa) OU contexto.improvaveis
    ordem: margem no fim, round(conf,2), posição (abby/pagina.py:889-900)
                     │
                     ▼
  Enter → ensinar: amostra no livro; propagar só pelos pendentes da página, só pelo livro
```

Exportação, depois: Documento (`abby/texto.py`) → `_caixa_pela_altura` com a regra inteira (`abby/montagem.py:270`) → parágrafos, hífen → `Figura` desenhada ou recorte conforme `DiagramaLido.confiavel`.

### 2.2 Quem vence em conflito

| Conflito | Regra | Limiar | Onde |
|---|---|---|---|
| Livro × rede × k-NN global | ordem fixa; não se comparam | livro `d<1500`; rede `>0,80`; global `>0,30` | `abby/leitor.py:166-169`, `core/services/ocr_service.py:971,986` |
| Veto × classificador | filtra; a próxima candidata do mesmo elo sobe; sem candidata, a vetada fica | `CANDIDATAS` | `core/services/ocr_service.py:963-970` |
| Peça × ocupação | ocupação decide primeiro | `p ≥ 0,5` | `core/diagrama.py:1505-1507` |
| Árbitro do tabuleiro | a casa de menor `log p` muda; a casa fica travada | contagem de reis, peão nas pontas | `core/diagrama.py:1427-1458` |
| Altura × caixa lida | a altura vence; manual, nativa e revisado não mudam; na leitura, fora de palavra com dígito ou figurina | corte a 50 % entre x e maiúscula | `abby/montagem.py:367-376,404-406,435-436` |
| Corte de colados | menor parte > inteiro | margem 0,00 | `core/services/box_service.py:417,454` |
| Conferido × releitura | conferido vence | sobreposição ≥ 0,5 | `abby/diagramas.py:484-494` |
| Manual × releitura | manual nunca é relido | — | `abby/pagina.py:834` |
| Lance × diagrama | estado `lance_ilegal`, nada muda | primeiro lance que falha | `abby/lances.py:414-434` |
| Camada × boxes | camada aceita ignora os boxes | régua da página | `abby/exportar.py:236-237` |

### 2.3 `core.livro` (só para comparar)

`_texto_da_linha`: `classificar` por box (rede + veto + alfabeto, `core/editorial_legacy.py:162`), `geometria_da_linha.podar`, piso `conf < 0,5` **apaga o caractere** (`core/livro.py:2433-2434`, `:120`). Depois `_ler_linha`:
- Domínio pela âncora (`:3676`). Notação fica com a cadeia, salvo lacunas (`:3689`). Prosa vai ao motor (`:3683`).
- Casar com registro da página; aceito se semelhança ≥ 0,5 e tem letra (`:1083-1085`). Senão, faixa `psm 7` (`:3714-3721`).
- `_fundir_por_palavra`: token com forma de lance fica com a âncora. Token de prosa é trocado pelas palavras do motor com conf ≥ 0,5 que sobrepõem em x ≥ 0,5 (`:1596,1619-1623,1661-1671`). **A confiança da âncora nem entra na conta.** Quem decide é o tipo do token, e uma figurina no token decide sozinha (`core/notacao.py:393`).

### 2.4 Pontos onde a informação se perde

| # | Perda | Onde | Consequência |
|---|---|---|---|
| L1 | Margem do k-NN | `abby/leitor.py:178` | O core a produz para a revisão (`core/services/ocr_service.py:21-25`), e o app a joga fora. [F] |
| L2 | Top-k da rede | só `predict`; `predict_topk` no veto e no palpite (`abby/leitor.py:191-195`) | Sem candidatas para qualquer etapa posterior. [F] |
| L3 | Palpite abaixo do limiar | `core/services/ocr_service.py:1006` | Vira `""`, conf 0. A investigação do CA-F.1 registra 88 de 122 pendentes sem leitura. [Doc, `docs/revisoes/ca-f1-investigacao.md:35`] |
| L4 | Distância e classes vizinhas do livro | `abby/leitor.py:155-157` | Só a conf 1−d/2000 sobrevive, e o `precisa_revisao` a ignora. [F] |
| L5 | Proporção e tamanho antes do classificador | `core/neural_trainer.py:925`, `core/learner.py:507`, `abby/padroes.py:140` | Documentado em `core/proporcao.py:6-34`. Corrigido por veto depois, não por entrada. [F] |
| L6 | Interpolação | `cv2.resize` padrão bilinear na redução de glifo; `INTER_AREA` na casa do diagrama (`core/diagrama.py:1073`) | Serrilhado em glifo grande. [H: efeito não medido] |
| L7 | Contraste | cinza cru em todos os descritores | `d` absoluto depende do papel e da tinta. `contraste_borrado` foi medido e não generalizou. [Doc, `ca-f1-investigacao.md:134-150`] |
| L8 | Coordenadas | `boundingRect` inteiro; altura pela caixa, não pela tinta | 1 px em 6 px de pontuação são 16 %. O core documenta o erro da caixa com pingo (`core/geometria_da_linha.py:23-28`), e `abby/contexto.py:217-219`, `abby/montagem.py:418,430` usam a caixa. [F] |
| L9 | Segmentação antes do reconhecimento | `core/services/box_service.py:45-63` | Um box partido nunca é refundido pela leitura; só o corte tem árbitro. 139 das 314 classes da CNN têm mais de um caractere (`'a2'`, `'xf3'`, `'♕x'`, `'.♗'`), remendo de sub-segmentação no vocabulário do modelo. [F para a lista, `model_meta.json`; I para o motivo] |
| L10 | Escala com áreas | `abby/zonas.py:827` (`PaginaSegmentada` sem escala) → `abby/diagramas.py:343` → fallback grosseiro `core/diagrama.py:877-880`. Também `abby/servidor_de_leitura.py:162` | Depois da primeira leitura a página ganha áreas automáticas; o F5 seguinte lê rótulos com a estimativa pior. [F + I] |
| L11 | Texto fora das áreas | `abby/zonas.py:780-781` | Box com centro fora de área some, sem aviso. [F] |
| L12 | Top-k por casa | `core/diagrama.py:1528-1537` | Só o símbolo decidido fica em `Casa`. [F] |
| L13 | Evidência do fio | `abby/pagina.py:639` | O fio some antes do layout; a SPEC §5.1(7) quer "depois de fio". [F] |
| L14 | Procedência depois da troca de caixa | `abby/montagem.py:404-406` | `char` muda; fonte, confiança e amostra ficam. [F] |
| L15 | Efeito na releitura de recortes | `abby/servidor_de_leitura.py:150` | `ler_recortes` não passa efeito. [F] |
| L16 | Vão entre palavras | `core/notacao.py:93,219-223,252` | Limiar 0,5 × largura mediana **da página**. O core já trocou por vão típico da linha em `core/livro.py:2402` (F107). `abby/layout.py` remenda com `partir_nos_vaos`. [F] |

### 2.5 Escalas não calibradas comparadas entre si

- **A régua de 0,90** vale igual para softmax com T e `1 − d/2000`. [F, `abby/leitor.py:253`] Com repetições a distância 900–1400 (`abby/dados_do_projeto.py:35`), todo k-NN global fica entre 0,30 e 0,55, logo **sempre** vai à fila. [I] A régua vira um teste de fonte disfarçado.
- **Ordem da fila** por `round(conf, 2)` entre fontes. [F, `abby/pagina.py:900`] O core mediu que desencontrar réguas piora a fila (`core/learner.py:196-199`), mas essa medida era em outra cadeia. [Doc]
- **O comentário** `abby/padroes.py:74-76` diz que o divisor comum serve para "as duas confianças falarem a mesma escala na fila". O livro nem entra na fila pela confiança. [F]
- **Árbitro de corte**: `menor > p_inteiro` com valores de três escalas, mais o 0,0 do "ninguém leu". [F, `abby/leitor.py:201-204`, `core/services/box_service.py:444-454`]
  - Glifo inteiro sem leitura tem `p_inteiro = 0`: **qualquer** corte cujas partes todas leiam algo é endossado. [I]
  - Ligadura ensinada no livro a `d ≈ 1000` vale 0,5; as partes pela CNN a 0,9 a desfazem. [H]
- **`vertical.decidir_angulo`** escolhe o ângulo pela média dessas mesmas confianças. [F, `core/vertical.py:270-292`]
- **Calibração por domínio** existe (`core/ocr_phase7.py`), e o único uso é o treino de linhas (`core/ocr_training.py:235`). [F]

### 2.6 Onde a decisão de um motor impede outro

- **Livro leu**: a rede nunca é consultada, e `precisa_revisao` diz não. [F, `abby/leitor.py:167-168,249-250`]
- **Rede passou de 0,80**: o k-NN não opina. Acima de 0,90 não há fila, salvo o contexto. A investigação registra 48 de 217 glifos ensinados nesse caso (`1→l`, `C→c`, `S→s`, `-→.`). [Doc, `ca-f1-investigacao.md:41-43`]
- **Forma de lance**: `julgar_palavra` para em `_e_lance` (`abby/contexto.py:133-134`). "Ca6" ilegal passa como provável. A regex nem olha o tabuleiro. [F]
- **Tirado antes de ler**: box contido na margem do tabuleiro. O app não tem a recuperação de faixa de `core/livro.py:677-697`. [F]
- **Propagação**: `propagar_padroes` só consulta o livro. Um pendente que a rede leria bem após mudança não muda. [F, `abby/pagina.py:946-977`]
- **Conferido e manual** não voltam. É o correto, e também imobiliza o erro de quem conferiu. [F]
- **Fusão do core**: figurina falsa no token (o `♕` de um ponto) prende o token na âncora. O core só alivia sobre trama (`core/livro.py:1646`). Lance com figurina lida como letra vira prosa e o motor o reescreve. [F + I]
- **Validação cega à causa**: `lance_ilegal` não separa FEN errado de lance mal lido. O primeiro erro encerra a linha. [F, `abby/lances.py:428-430`]

### 2.7 Onde o xadrez poderia restringir e não restringe

1. **Vocabulário dependente da posição no token.** Num lance, a segunda letra é `[a-h1-8x]`. A rede sempre compete com 314 classes. Só depois regex como `_FILEIRA_1_DO_OCR` (`abby/lances.py:86`) entendem `l→1`, e só para a validação: o texto fica errado. [F]
2. **Número esperado do lance.** `_Linha.esperado` (`abby/lances.py:266,300`) sabe que depois de `14...` vem `15.`. Só serve para cortar a linha. [F]
3. **Lances legais como candidatos.** `core/notacao.py:503-517` já pontua os legais contra a leitura com a confiança por caractere. Só `ui/reconhecimento.py:1681` e `core/pgn.py:228` a alcançam. [F]
4. **FEN do diagrama como semente.** `analisar` não aceita FEN e só zera o tabuleiro em `1.` sem reticências. [F, `core/notacao.py:524,566-568`] Página que abre no meio da partida não é validada, e o tabuleiro não atravessa de uma página para outra. [F]
5. **Variantes.** `lances.primeira_linha` encerra em `(`, `;` ou número inesperado. [F, `abby/lances.py:279-286`] O texto de variantes, grande parte da notação destes livros (`core/notacao.py:537`) [Doc], não recebe prova nenhuma no app.
6. **Diagrama seguinte.** Posição do diagrama N + lances da linha = diagrama N+1. Busquei e não achei essa comparação. [F, ausência em `abby/lances.py`, `abby/diagramas.py`]
7. **Alternativas do FEN.** Quando um lance falha, as casas com peça de baixa confiança poderiam ser testadas. O top-k existe (`core/diagrama.py:1199`) e ninguém o usa. [F]
8. **Orientação pelos lances.** Sem rótulos, é "branca" (`abby/diagramas.py:346`). Testar as duas contra os lances não é feito. [F]
9. **Legalidade do FEN no árbitro.** `_arbitrar` não testa xeque do lado que não joga. [F, `core/diagrama.py:1381-1459`]

**Limite importante.** O livro pode imprimir lance errado. OCR que "corrige" pela legalidade falsifica o livro. Portanto a restrição deve gerar hipótese e sinal, e não reescrever em silêncio (`CONTEXT.md`, invariante 5). [I]

### 2.8 O laço de retroalimentação

**O que aprende e quando.**
- Enter: `pg.ensinar` grava o recorte em `padroes/<classe>/` com altura, origem, efeito. Vale na hora. Vira manual, conf 1,0. [F, `abby/pagina.py:918-925`, `abby/padroes.py:361-384`]
- Propaga só na página aberta, só pendentes, só pelo livro. [F, `abby/ponte_de_leitura.py:342-381`]
- Servidor recebe deltas antes do pedido seguinte. [F, `abby/ponte_de_leitura.py:553-564`]
- Páginas já lidas ficam velhas até reler; `ensinados_depois` só conta. [F, `abby/padroes.py:557`]
- Nada do app toca a base global ou a rede. A conferência de diagrama guarda amostras no projeto e ninguém as lê (`abby/diagramas.py:19-34,551-564`). [F] **O reconhecimento global nunca melhora pelo uso.**

**Contaminação.**
- 1-NN deixa uma amostra ruim decidir sozinha, e o livro é isento da fila. [F]
- O aviso de conflito usa `Limiares.conflito = 0,10`, ou seja, `d ≤ 200`. [F, `abby/dados_do_projeto.py:48`, `abby/padroes.py:338-345`] Se as repetições ficam em 900–1400 em scans, o aviso só dispara em quase-duplicata. [I]
- Amostra de box mal segmentado vira padrão. Não há checagem de que o box é um glifo inteiro. [F, `abby/pagina.py:922`]
- Mundo aberto: com poucas classes ensinadas, a classe nunca vista cai no vizinho mais perto abaixo de 1.500, sem classe "outro". As tabelas de `abby/padroes.py:21-25` foram medidas com amostras por letra. [F + H]
- Evidência parcial: Yusupov, K=3, 223 certos e 11 errados, em glifos fáceis. Esses erros não vão à fila pela confiança. [Doc, `ca-f1-investigacao.md:144`]
- Saída de emergência boa: `esquecer` devolve à fila os glifos daquela amostra, e a página verificada volta à revisão. [F, `abby/padroes_do_livro.py:132-149`]

**No core.**
- `learn_from_boxes` grava todo box com caractere, sem porta. [F, `core/services/learning_service.py:64-93`; `ui/treino.py:251`] A `coleta` tem quarentena, mas é outro caminho.
- O próprio core fala de páginas "menos contaminadas pela própria base". [Doc, `core/learner.py:207`]
- **Divisão da CNN**: `dividir_estratificado(labels, num_classes, ...)` não tem grupo por livro. [F, `core/avaliacao.py:52`] O "99,76 %" é sobre amostras do mesmo material, contra a invariante 13 do `CONTEXT.md`. [I]
- 64 classes sem validação, entre elas `!!`, `!?`, `?!`, `??`, `⨀`, `⯺`–`⯽`, `Δ`, `○`. "Nenhum número abaixo diz nada sobre elas". [F, `relatorio_treino.txt`]
- Classe-lixo `'č\t'` no `idx_to_char`. [F, `model_meta.json`]

---

## 3. Modos de falha estruturais

"Página perfeita" = todo caractere, símbolo, posição e estrutura iguais ao impresso. Em cada linha: onde nasce e o que faltaria. Zerar de fato exige, em algum ponto, verificação humana barata e bem dirigida; nenhum dos motores daqui prova correção sozinho.

| Item | Sintoma | Elo onde nasce | O que precisaria existir |
|---|---|---|---|
| **Prosa: letra errada** | `c0l0ca`, `spuares` | Classificação isolada de glifo, sem modelo de língua. Léxico só sinaliza | Segunda hipótese de linha (Tesseract, M3), decodificador por palavra com léxico, sobre top-k (M1) |
| **Prosa: linha ausente** | Linha sumida | Segmentação: tabuleiro + margem, áreas (L11), fio, moldura | Conferir tinta sem box ao fim: toda tinta tem dono ou justificativa, com aviso. Hoje só os pingos voltam |
| **Espaços** | `distancebetween` | L16: limiar da página; corte sem hipótese | Vão por linha (F107 do core) e hipótese de espaço no decodificador. 15 correções na fatia [Doc] |
| **Caixa e homoglifos** | `s/S`, `1/l`, `0/o` | Esticão L5. Regras de altura em 4 lugares no app e no core (`padroes`, `contexto`, `montagem`, `geometria_da_linha`), sem medida conjunta | Altura como entrada, ou a poda de Baird por tinta. Uma régua só |
| **Figurinas** | `♘f4` lido `♘4`; figurina de ponto | Sub-segmentação L9; ausência de restrição por posição | Gramática de lance + legalidade + separação com hipótese. Só 6 classes de figurina (`♔♕♖♗♘♙`): fonte nova depende do livro |
| **Lances** | SAN ilegal | Sem restrição 2.7; `_e_lance` isenta (2.6) | M2: candidatos legais a partir do FEN, com árvore de variantes |
| **NAGs e símbolos** | `?` como `.` + gancho; `⨁`, `⇆`, `⟫` | Classes raras sem validação; `⨁ ⇆ ⟫` estão em `abby/lances.py:85` e **não** são classes da CNN [F]; merge vertical da pontuação | Vocabulário de NAG por livro, ensinado de início. Amostragem ativa desses símbolos. Medida por classe |
| **Diagrama: casa errada** | Peça trocada | Rede sobre grade uniforme. Ocupação decide antes da peça (L12). Setas: `abby/diagramas.py:25` [Doc] | M7 + confirmação visual (já existe) |
| **Diagrama: confiável falso** | "confiável pelos lances" com lance não relacionado | CA-10.1 registra 73/100 perturbadas [Doc, `docs/SPEC.md:703-704`]. `DiagramaLido.confiavel` já corrige em parte (`abby/diagramas.py:165-176`) | Medir só as casas tocadas pelos lances; dizer quantas casas a validação cobriu |
| **Diagrama: orientação** | Virado | Sem rótulos, supõe branca (`abby/diagramas.py:346`) | Testar as duas contra os lances |
| **Colunas e ordem** | Coluna colada; pilha de tabuleiros | Regras geométricas, antes de ler. `FILAS_DE_COLUNA` etc. | Conferência pela continuidade dos números de lance entre colunas. Modelo de áreas por livro (já existe) |
| **Notas** | Nota no meio do texto | `_nota`: y ≥ 0,7, corpo ≤ 0,82, isolada (`abby/zonas.py:454-458`), sem fio (L13), sem chamada de nota | Guardar os fios como evidência. Chamada ↔ nota |
| **Tabelas** | Texto perdido, sai como imagem | `TIPO_DA_FUNCAO["tabela"] = IMAGEM` (`abby/zonas.py:61`); `filtrar` tira o texto. A detecção do core não é chamada. SPEC: "fase posterior" | API pública de `_tabela_da_pagina` (pedido ao core), ou zona tabela com células |
| **Negrito e itálico** | Palavra curta sem efeito; efeito errado | Depois de ler, depende do `char` (`abby/efeitos.py:149-155`). Mínimos de 2 glifos e 3 letras (`:144,271`). Rede não condicionada ao estilo | Agrupar por fonte antes de ler; efeito propagado de trecho, e não por palavra sozinha. Medidas fortes já existem [Doc] |
| **Ligaduras** | `fi` partido; caixa ≠ letras | Arbitragem pode desfazer (2.5). Classes de ligadura e de colagem misturadas no mesmo vocabulário (L9) | Separar "ligadura tipográfica" de "colagem". Leitura por palavra alinhada |
| **Hífen** | `Xue-Fierro` vira `XueFierro`; hífen × travessão × ponto | Regra letra + minúscula, sem dicionário (`abby/montagem.py:565-568`). `lexico.juntar_hifenizadas` não é usado [F]. `—→-` 8× [Doc] | Decidir com léxico + vocabulário do livro; sinalizar o que sobra |
| **Camada nativa** | Edição não exportada; caixas falsas | `abby/exportar.py:236-237`; `abby/nativo.py:131` | Página editada sai dos boxes, ou as edições viram patches sobre a camada. Coordenadas reais do `rawdict` |
| **Cabeçalho comido** | Cabeçalho do diagrama some | `abby/pagina.py:614-616`; margem de 1,4 sem a faixa de `core/livro.py:677-697` | Recuperar faixa e legenda, como o core |

---

## 4. Mudanças de arquitetura com maior ganho esperado

**Antes das mudanças, dois itens que definem se qualquer número vale.**

**P0. A régua.** Verificar o texto de ao menos Yusupov e mais um livro: hoje são 213 linhas de 1 livro, português. Acrescentar ao `ferramentas/medir.py` CER por classe de token (prosa, lance, número, NAG, figurina), e o **erro silencioso**: glifo errado, fora da fila. Sem isso não há como falsear M1–M8.

**E0. O experimento mais barato deste relatório.** Rodar `core.livro.extrair` nas mesmas páginas de `tests/verdade/xv` e comparar com o F5, nas 213 linhas verificadas, separando prosa e lance. Custa uma ferramenta de poucas linhas, sem mudar nada. Responde se a falta de Tesseract é a maior lacuna, ou se o k-NN compensa. **Decide a ordem de M3.** Rodar sozinho, uma carga por vez.

A ordem abaixo é a da minha expectativa de ganho e de dependência. É julgamento, não medida.

### M1. Contrato de hipóteses por glifo (o que habilita o resto)

- **O que muda.** `Leitura` passa a guardar top-k da rede, melhor distância e segunda classe do k-NN do livro, a margem do global, e o palpite em vez de `""`. Persistido fora do `BoxEntry`. A escolha atual continua igual; só para de jogar fora.
- **Hipótese falseável.** Nos glifos errados ou vazios do gabarito, o certo está no top-3 da rede ou do k-NN numa fração útil. **Falseia** se a cobertura@3 dos erros ficar abaixo de um corte fixado antes de medir (proponho 50 %): o decodificador não teria de onde tirar.
- **Medir.** Só instrumentação: cobertura@k por classe de token, na fatia XV.
- **Custo.** Baixo a médio: `leitor`, `procedencia`, formato de página, fila do servidor. Top-5 de 314 classes em cada glifo pesa no JSON.
- **Risco.** Formato de projeto (migração); tamanho; a fila do `spawn`.
- **Onde.** App. `predict_topk` é público; o acesso a `_predictor` já está em `docs/pedidos-ao-pyboxeditor.md`, item 3.

### M2. Decodificação de lance com legalidade e posição

- **O que muda.** Para tokens de lance com posição conhecida (FEN do diagrama + árvore de variantes), pontuar os lances legais contra as hipóteses do M1. Sugere e sinaliza; **não reescreve em silêncio** (o livro pode ter erro de impressão). Aproveita a ideia de `core/notacao.py:460-517`, sem a limitação do `1.`.
- **Hipótese falseável.** Em tokens de lance verificados, a sugestão top-1 acerta mais que a leitura atual, com número de "certo → errado" igual a zero no conjunto fixado. **Falseia** se a cobertura (tokens com posição conhecida) for pequena demais, ou se aparecer certo → errado.
- **Medir.** Acerto exato por token de lance contra o gabarito; cobertura de posição; gestos no `replay_fatia.py`. Hoje há poucos lances rotulados por diagrama (`lances` em xv/i022, i024, yusupov/i012, darcy/i025): as `linhas_corpo` verificadas precisam ser classificadas em tokens.
- **Custo.** Médio a alto: o difícil é a árvore de variantes e a perda de sincronia.
- **Risco.** Falsa correção; erro de FEN contamina a decodificação (uma posição errada torna o lance certo "ilegal"), logo precisa de M7 ou de marca de incerteza.
- **Onde.** App (`python-chess`, `lances.py`). O `analisar` do core não aceita FEN; pedir se quiser unificar.

### M3. Segunda hipótese de linha para a prosa

- **O que muda.** Tesseract de página no servidor (uma chamada por página, com o idioma do projeto), alinhado por caixa aos boxes, como **terceira opinião** ao estilo de `abby/camada.py`. Primeiro só opina e entra na fila. Com a medida na mão, pode decidir em prosa.
- **Hipótese falseável.** Nas palavras de prosa em que o Tesseract discorda do app, ele acerta mais que o app, e a concordância entre os dois prevê acerto melhor que a confiança atual. **Falseia** se o E0 mostrar CER de prosa do F5 com livro treinado ≤ `core.livro`, ou se a fração certa nas discordâncias não passar da metade.
- **Medir.** E0; depois CER de prosa por livro; gestos; tempo por página. Sem acesso a Tesseract, a primeira medida é por ferramenta.
- **Custo.** Médio. [Doc] 0,7–3 s por página, até 19 s (`core/services/ocr_service.py:96-98`). Dependência externa, instalar `por.traineddata`.
- **Risco.** Prazo no lote; figurina vira lixo no Tesseract (excluir tokens com forma de lance, como `abby/camada.py:38` faz); reescrita de grafia antiga por idioma errado; `eng` em livro bilíngue.
- **Onde.** App, para a opinião. `_fundir_por_palavra`, `_casar_linha_ocr` são privados; se fundir no modo do core, **pedido ao core** de API pública.

### M4. Roteamento calibrado por probabilidade de erro, sem isenção do livro

- **O que muda.** Uma função `P(erro | fonte, conf, margem, d, classe, contexto)` por isotônica, ajustada no gabarito. A fila ordena por ela. O livro deixa de ser isento: amostra com `d` alto, ou segunda classe perto, entra. Rede abaixo de 0,80 mantém o palpite e vai à fila com ele.
- **Hipótese falseável.** Com o mesmo orçamento de N glifos revisados, a nova ordem acha mais erros que `round(conf, 2)`, e o erro silencioso cai. **Falseia** se a curva "erros achados × revisados" não superar a atual em holdout de outro livro.
- **Medir.** ECE por fonte; curva de revisão; erro silencioso; gestos da fatia (CA-F.1 limita o custo: a fila maior pode piorar a razão).
- **Custo.** Baixo a médio, depois do M1 e do P0.
- **Risco.** Sobreajuste a 1 livro, por isso depende do P0; a fila cresce; `precisa_revisao` é usado em muitos lugares (`abby/pagina.py`, `abby/contexto.py`, `abby/fila_da_pagina.py`).
- **Onde.** App.

### M5. Descritor aprendido no k-NN do livro

- **O que muda.** Trocar cinza cru 32×32 pela penúltima camada de 256 dimensões da `SimpleCNN` (`core/neural_model.py:35`), com ou sem contraste. A investigação pede algo assim (`ca-f1-investigacao.md:155-156`), e o `contraste_borrado`, testado, não generalizou.
- **Hipótese falseável.** Com o mesmo número de erros, o descritor lê mais da página seguinte em **Darcy e Yusupov**, e não só no Xadrez Vitorioso. Yusupov é o teste duro: menos de 10 % com o atual. **Falseia** com o mesmo critério que reprovou o outro.
- **Medir.** `ferramentas/medir_descritor.py`, que já existe, com ajuste num livro e validação em dois. Mais o caso do mundo aberto: ensinar só K classes e medir falso positivo das não ensinadas.
- **Custo.** Médio.
- **Risco.** **Conflito de arquitetura**: a interface não importa torch (`docs/SPEC.md:726`), e a propagação roda nela. O descritor teria de ser calculado no servidor, ou a propagação mudaria de lugar. A amostra gravada deve seguir como PNG, e o descritor em cache. Fragilidade a troca de pesos (o cache precisa do `modelo_sha256`).
- **Onde.** App; `model` é atributo do `NeuralPredictor`. Um `embedding()` público seria um pedido limpo ao core.

### M6. Árbitro coerente, e divisão ou junção por hipótese

- **Passo 1, conserto.** `arbitro` volta à rede crua com o veto, numa escala só, como o core documenta. Passa a altura de referência.
- **Passo 2, arquitetura.** Candidatos de divisão e junção na palavra, pontuados pelas hipóteses e pelo léxico ou gramática. `BoxService.prova_de_reparo` (`core/services/box_service.py:579`) e `lexico.reparar` (`core/lexico.py:871`) já fazem parte disso, e o app não os usa.
- **Hipótese falseável.** Passo 1: menos cortes falsos e menos colagens sem cortar, CER igual ou melhor. **Falseia** se não mudar o número de gestos `dividir`, `juntar` nem o CER. Passo 2: as 48 divisões da fatia, menos as 29 já certas no texto [Doc, `ca-f1-investigacao.md:75-80`], caem sem gerar outras.
- **Medir.** `replay_fatia.py` (gestos por comando); CER; contagem de boxes por linha contra as verificadas. Ligadura ensinada continua inteira: teste próprio.
- **Custo.** Passo 1: muito baixo; é o melhor custo-benefício da lista. Passo 2: alto.
- **Risco.** O árbitro hoje enxerga o que o livro ensinou: sem ele, uma colagem ensinada pode voltar a ser cortada. Por isso o passo 1 precisa da regra "o que o livro lê inteiro com `d` baixo não se corta". Custo em CPU no passo 2 (já houve 22.852 candidatos em 7 boxes [Doc, `core/neural_trainer.py:884-886`]).
- **Onde.** App, nos dois passos.

### M7. Decodificação conjunta da posição com o texto

- **O que muda.** Usar `pontuacoes_de_casas` por casa, mais ocupação como probabilidade, em busca limitada (beam) sobre as casas fracas. Critérios: legalidade (inclusive xeque do lado que não joga), lances do texto, diagrama anterior + lances. Sai como **sugestão** e como explicação do `lance_ilegal`: "a posição com o bispo em f6 explica os 6 lances".
- **Hipótese falseável.** Entre os diagramas lidos errados, a sugestão top-1 recupera o FEN do gabarito sem piorar os certos. **Falseia** com a recuperação baixa nos erros reais, e não nas perturbações sintéticas.
- **Medir.** Casas erradas por FEN no gabarito; recuperação em `perturbacoes.py` estendido a trocas de peças parecidas; CA-10.1; corpus de 346 tabuleiros do core [Doc].
- **Custo.** Médio.
- **Risco.** Lances curtos deixam a posição subdeterminada: nunca confirmar sozinho (o `DiagramaLido.confiavel` já aprendeu isso). A rede roda duas vezes por tabuleiro, a menos que `ler` exponha as pontuações.
- **Onde.** App; `pontuacoes_de_casas` é público. Um `ler(..., com_pontuacoes=True)` seria pedido ao core.

### M8. Nova entrada da CNN e treino honesto

- **O que muda.** Entrada com proporção preservada (pad) e canais de altura relativa e proporção. Divisão por livro. Mais amostra de NAG. Vocabulário sem as classes de colagem acidentais e sem `'č\t'`.
- **Hipótese falseável.** Em livro de fora do treino, cai a confusão de família (`o/O/0`, `l/1/I`, `-/./—`) sem piorar o resto. **Falseia** se o holdout por livro empatar com o modelo atual avaliado da mesma forma.
- **Medir.** Primeiro, e barato: reavaliar **o modelo atual** com holdout por livro, para ter o número real. Depois matriz de confusão por família e recall por NAG.
- **Custo.** Alto. Treino pesado numa máquina que trava com carga: precisa de orçamento próprio.
- **Risco.** Regride tudo que foi afinado sobre o modelo atual (temperatura, limiares, `proporcao.ENVELOPE`, `geometria_das_classes.json`).
- **Onde.** **Exige o core.**

### Resumo

| Mudança | Ataca | Custo | Onde | Depende de |
|---|---|---|---|---|
| P0 + E0 | a medida | Baixo | App | — |
| M6 passo 1 | árbitro | Muito baixo | App | P0 parcial |
| M1 | L1–L4 | Baixo a médio | App | — |
| M3 | prosa | Médio | App; core para fundir | E0 |
| M4 | fila, livro | Baixo a médio | App | M1, P0 |
| M2 | lances | Médio a alto | App | M1 |
| M5 | propagação | Médio | App; core opcional | — |
| M7 | diagramas | Médio | App; core opcional | — |
| M6 passo 2 | segmentação | Alto | App | M1 |
| M8 | modelo | Alto | Core | P0 |

**Consertos pequenos fora da lista, que qualquer um dos acima encontraria** [F]:
- passar `idioma` em `abby/leitor.py:174-177`, e medir, porque liga uma máscara hoje inerte;
- passar a `escala` em `abby/zonas.py:827` e `abby/servidor_de_leitura.py:162`;
- avisar sobre box fora de área em `abby/zonas.py:780`;
- rever o `conflito=0,10`;
- exportação de página nativa editada;
- `lances._AVALIACAO` x classes da CNN.

---

## 5. Onde documento e código divergem

| # | Documento diz | Código faz | Tipo |
|---|---|---|---|
| D1 | `docs/ANALISE_PYBOXEDITOR.md:10-13,44`: o motor existe; `core.livro` é "o leitor de produção" | O app nunca importa `core.livro` (busca em `abby/`) | Documento desatualizado para o app |
| D2 | `docs/SPEC.md:397,405`: colunas e tabelas "pelo `core.livro`" | Colunas por `BoxService` (`abby/layout.py:93`); tabela vira imagem (`abby/zonas.py:61`) | SPEC x código |
| D3 | `abby/leitor.py:10-12`: "vetos de proporção e de alfabeto" | Sem `idioma`, alfabeto não veta (`abby/leitor.py:174-177`, `core/alfabeto.py:54-55`) | Comentário falso |
| D4 | `core/services/ocr_service.py:874-878`: 0,70 desde a F22, tabela em `NEURAL_THRESHOLD` de `ui/main_window` | `ui/reconhecimento.py:235` tem 0,80, "pico" medido; o app segue 0,80 (`abby/dados_do_projeto.py:31,42`) | Comentário velho no core |
| D5 | `docs/ANALISE_PYBOXEDITOR.md:47`: `notacao` usa a legalidade "para escolher entre leituras" | Só no botão da janela e no PGN; nem `core.livro` nem o app | Escopo exagerado |
| D6 | `docs/ANALISE_PYBOXEDITOR.md:31,33`: `coleta` e `ocr_phase7` "Direto" | Sem import em `abby/` | Plano que não se realizou |
| D7 | `docs/ANALISE_PYBOXEDITOR.md:29`: 99,76 % como medida | Divisão sem grupo por livro (`core/avaliacao.py:52`); 64 classes sem validação (`relatorio_treino.txt`) | Número sem o contexto |
| D8 | `CONTEXT.md`, invariante 13 | Vale para linhas (`core/ocr_phase7.py`), não para glifos | Invariante parcial |
| D9 | `CONTEXT.md`, "Fusão", "Decisão": sem eliminar alternativas | Top-k e margem descartados no app; `core.livro` guarda só o registro da linha (`core/livro.py:3775-3780`) | Vocabulário não realizado |
| D10 | `CONTEXT.md`, "Posição candidata" | Só na biblioteca fora de produção (`core/biblioteca/ocr_phase4.py:441`) | Inerte |
| D11 | `CONTEXT.md`, invariante 7 | `_arbitrar` converte peça observada em rei quando falta rei (`core/diagrama.py:1446-1455`), com `mexida=True` | Tensão, mitigada pelo porteiro |
| D12 | `core/services/learning_service.py:175-179`: árbitro = rede crua | `core/livro.py:657` passa `classificar` com vetos; o app passa a cascata (`abby/leitor.py:201-204`) | Contrato não seguido |
| D13 | `abby/pagina.py:6-7`: medida do árbitro | O número foi com outro árbitro (`core/services/box_service.py:698-733`) | Medida transferida sem refazer [I] |
| D14 | `README.md:925`: padrão do livro "não volta à fila" | Volta se a palavra o desmente (`abby/contexto.py:481-486,499-506`) | README incompleto |
| D15 | `core/learner.py:548`: "Nada em produção chama isto" (`candidatas`) | `core/services/ocr_service.py:978-979` chama | Comentário velho |
| D16 | `docs/SPEC.md:404`: nota "depois de fio ou vão" | Fio apagado antes (`abby/pagina.py:639`), `_nota` não o usa (`abby/zonas.py:454-458`) | SPEC x código |
| D17 | `docs/ANALISE_PYBOXEDITOR.md:55`: "corrige a perspectiva" | No caminho do app, `diagrama.ler` corta grade uniforme sobre a caixa | Não vale aqui |
| D18 | `abby/padroes.py:74-76`: divisor comum "na fila de revisão" | O livro é isento da fila pela confiança (`abby/leitor.py:41,249`) | Razão obsoleta |

---

## 6. Limites desta auditoria

- **Não executei** nada que leia página. Efeitos de limiar e de escala ficam como [I] ou [H] até medir.
- **Li inteiros:** `abby/leitor.py`, `ponte_de_leitura.py`, `servidor_de_leitura.py`, `pagina.py`, `padroes.py`, `contexto.py`, `lances.py`, `efeitos.py`, `arrumacao.py`, `nativo.py`, `camada.py`; `core/services/ocr_service.py`, `learning_service.py`, `core/notacao.py`, `core/ocr_engines.py`, `core/ocr_routing.py`, `CONTEXT.md`.
- **Li em parte (cabeçalho, símbolos e trechos citados):** `core/livro.py` (4,3 mil linhas), `core/services/box_service.py`, `core/pdf_nativo.py`, `core/diagrama.py`, `core/lexico.py`, `core/negrito.py`, `core/geometria_da_linha.py`, `core/leitura_de_linha.py`, `core/learner.py`, `core/neural_trainer.py`, `core/linha_trainer.py`, `core/coleta.py`, `abby/montagem.py`, `abby/layout.py`, `abby/zonas.py`, `abby/verificacao.py`, `abby/sessao.py`, `abby/texto.py`, `abby/exportar.py`.
- **Só cabeçalho:** `core/negativo.py`, `core/trama.py`, `core/vertical.py`, `core/deteccao_de_tabuleiro.py`, `core/lado_a_jogar.py`, `core/mapa_glifos.py`, `core/ocr_phase7.py`, `core/ocr_phase8.py`, `core/ocr_runtime.py`, `core/avaliacao.py`, `core/pagina.py`. `ROADMAP.md` só por busca; o detalhe das fases está em `ROADMAP_F94-F125.md`, que não abri.
- **Não conferi:** `tessdata` instalado (`fast` ou `best`), tamanho real da base global, e o que `medir.py` calcula linha a linha.
- **Ausências** ("não usa", "não há") são de buscas em `abby/` e nos chamadores de `core/` e `ui/`. Chamada dinâmica por nome escaparia, e não vi indício disso.
