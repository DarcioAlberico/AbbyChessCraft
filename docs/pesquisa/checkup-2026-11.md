# Check-up geral do AbbyChessCraft e análise dos motores de OCR (2026-11-05)

Commit medido: `262d897` (ramo `lacunas-da-spec`). Core: `70e6a86`. O que fazer a partir daqui está na
[`docs/SPEC-pagina-perfeita.md`](../SPEC-pagina-perfeita.md) e no
[`plans/roadmap-pagina-perfeita.md`](../../plans/roadmap-pagina-perfeita.md).

Os relatórios completos, com `arquivo:linha`, estão em `docs/pesquisa/checkup-2026-11/`: `arquitetura.md`,
`design.md`, `testes.md`, `motores.md` e `estado-da-arte.md`. Os scripts dos experimentos estão em
`checkup-2026-11/experimentos/`. Os números estão em `docs/medidas/2026-11-05-motores.json`, sem texto de livro.

**Marcas.** **Medido**: rodei e o número está no JSON citado; as saídas de execução estão em `saidas_lidas`, sem o log
original. **Confirmado**: li no código. **Inferido**: conclusão a partir de fatos, sem reprodução. **Hipótese**: a testar.
Os `motores*.json` de entrada têm texto de livro e não estão no repositório: refazer a tabela pede rodar o OCR de novo.
**Exploratório:** conta refeita depois sobre as mesmas saídas, por token, com uma gramática provisória e antes de auditar o gabarito (`experimentos/por_token_*.py`, chave `por_token_exploratorio` do JSON). Serve para derrubar e dimensionar, não para aprovar.

## 1. Veredito

**A engenharia do programa está boa no que protege o dado e ruim no que coordena.** Gravação, migração e testes de
comportamento estão bons. A fila tem bom fluxo de gestos e sinal fraco (§4). O controlador e a janela perderam
complexidade por função (cc ≥ 10, de 251 para 5), mas o acesso a privados entre objetos dobrou.

**O maior problema não é de engenharia, é de leitura e de medida:**

1. **O programa lê cada glifo sozinho.** Fora a caixa pela altura e o reler pelo efeito, nada usa o contexto para
   decidir. O Tesseract, o leitor de linha e a fusão do core não são chamados pelo app (**Confirmado**). Os "1,59 %" da
   análise de outubro medem outra cadeia.
2. **Um OCR de linha, com modelo de fábrica, lê a prosa melhor que o programa.** Sem contar sobras, o PP-OCRv6 ganha em 4
   dos 5 livros. O programa vence onde os outros não têm a classe: figurinas e lances com figurina
   (**Medido**, §3).
3. **A discordância entre motores é um sinal novo: claro em prosa, não provado em lance.** Por caractere, no Seirawan, ela marca menos e pega mais que a fila. Por token, nos livros com figurinas, ela não marca nenhum token com figurina e pega de 31 % a 37 % dos lances errados (exploratório, §4). Custa de 22 a 58 minutos a mais em 300 páginas, por linha, sem integrar; lendo a página inteira, de 3,5 a 15, sem precisão medida (**Medido**, §4).
4. **Nenhum teste reprova por qualidade de OCR.** Se o modelo sumir, a suíte e o portão seguem verdes (**Inferido** da
   leitura dos testes, `checkup-2026-11/testes.md`, Q1). `tests/verdade` tem 213 linhas verificadas de um livro, sem
   figurinas (135 tokens de lance). O `corpus_v2` do core soma 4 páginas revisadas (260 tokens, 270 figurinas). Juntos, 395
   tokens: com zero erro, isso só sustenta menos de 0,8 %.

**Limite de tudo o que vem abaixo:** a amostra é pequena (5 livros, 17 páginas lidas por todos os motores), sem o treino
por livro, que é a razão de ser do programa, e sem revisão humana. Os números dizem onde investir. Não dizem o resultado
final.

**O que fazer, em ordem** ([roadmap](../../plans/roadmap-pagina-perfeita.md), "Marcos"):

1. **Primeiro:** responder Dec-1 e Dec-6 ([SPEC §10](../SPEC-pagina-perfeita.md), 15 min) e começar o passo PP0.
2. **M1 a M3, sem conferir nenhuma página:** nada mais se perde; a fila Lances mostra cada linha com lance, imagem sobre texto, e o lance ilegal fica marcado; a tela destaca o que importa. Nenhum caractere da leitura melhora. A fila Lances é hipótese, e o plano a mede (CA-F4.10).
3. **M4 e M5, só se o usuário der ~10 h (Dec-5):** a régua, os consertos de leitura e a 2.ª opinião, cada um entrando por medida.

**O plano não entrega a página perfeita.** Entrega erro silencioso medido, nos livros medidos, e menos atenção gasta. Para outro livro não se afirma nada.

## 2. Saúde do código

| Medida | Valor | Fonte |
|---|---|---|
| Suíte rápida | 2.429 passaram, 3 pularam; 99 s com cobertura, 64 s sem | `saidas_lidas` |
| Camada `processo` | 40 passaram, 250 s | `saidas_lidas` |
| Portão em série, no `8f8eccf` | 34 de 34, 16:28; CA-7.1 aprovado por 20 ms (2.380 contra corte de 2.400) | `2026-11-05-medida.json`, `saidas_lidas` |
| Cobertura combinada | 95,0 % de 24.920 linhas | `qualidade/2026-11-05-qualidade.json` |
| CRAP ≥ 10 | 9 de 2.977 funções, todas na lista aceita | `qualidade/crap-262d897.txt` |
| Duplicação ≥ 0,8 | 3 pares, **2 fora da lista: a medida reprova** | `qualidade/duplicacao-262d897.txt` |
| Módulos, linhas | 122 módulos, 41.713 linhas | `checkup-2026-11/arquitetura.md` |

Um dos dois pares fora da lista é do trabalho de 04/11: `exportar_as_selecionadas` repete `exportar` (rank 0,88).
O outro é `_cinza`, em `coordenadas.py` e `diagramas.py`. O ramo `lacunas-da-spec` não deve ser mesclado antes de
corrigir os dois (passo PP0).

### Achados que conferi no código

| Id | Achado | Efeito |
|---|---|---|
| D-1 | Página de versão futura ou `BoxEntry` com campo a mais vira `.corrompido.json` e sai do `livro.json`, com o projeto aberto para gravar (reproduzido pelo auditor em pasta temporária) | Abrir com um core mais velho tira páginas do livro |
| D-2 | Trocar de página fecha o editor de diagrama e apaga as casas editadas (`editor_diagrama.py:278-281`), sem aviso | Trabalho perdido em silêncio |
| D-3 | Página da camada nativa exporta ignorando os boxes (`exportar.py:236-237`) | Correção feita nela não chega ao EPUB |
| D-4 | Falha na camada descarta inclusive os trechos já lidos, com só um `warning` no log (`exportar.py:391-398`) | O livro sai dos boxes, com aparência normal |
| C-1 | O servidor de leitura não chama `vigiar_o_pai` (`servidor_de_leitura.py:413-419`) | Inferido: ~1 GB órfão se a interface morrer |
| C-2 | Não há log em arquivo nem `faulthandler` (`principal.py:43`) | Um relato de falha não tem rastro |
| E-1 | `chess` e `torch` não declarados, `regex` só em `[dev]`, venv com `--system-site-packages`, YAML fora do pacote, sem lock, sem CI | Inferido, não tentei: num ambiente limpo, instala e não roda |
| E-3 | O repositório é **público** e versiona gabaritos com texto de livro e um snapshot de páginas, contra `SPEC.md:1097` | Decisão do usuário |
| A-1 | Ciclo de 16 módulos, escondido por 185 imports tardios (`arquitetura.md`, A4) | Erro de import só em execução |
| A-2 | 230 acessos a privados entre objetos, o dobro de outubro; 169 vão ao controlador ou ao projeto | O `_` não informa nada, e nada se testa sozinho |
| A-3 | `JanelaPrincipal`: 237 métodos em 10 classes, com `janela.py` parado em 498 linhas | O teto de 500 linhas empurra método, não reduz |
| U-1 | Sem indicação de foco; Alt+3 não entra no Documento; não há `setFocusProxy` em `app/` | Tecla vai ao painel errado; Enter pode ensinar padrão |

As réguas de complexidade e de privados do core funcionaram. As de 500 linhas e de 40 métodos medem a coisa errada:
o código diz "funções: a classe não cresce" em três lugares. O que está bom e não deve mudar está listado no fim de
`arquitetura.md` e de `design.md`.

### A interface na tela

Capturas reais da janela, a 1920 e a 1366 px (`ferramentas/capturas.py`, Seirawan p. 26). Elas mostram página de livro e
não estão no repositório: refaça com a ferramenta.

- **O miolo funciona bem:** Imagem, Documento e Glifo lado a lado, Linha embaixo, a dúvida com palpite honesto.
- **O realce saturou.** A página mostra 207 de 1.047 boxes a revisar: quase todo `o` e `s` fica laranja, e `s0rte`,
  `conc1uir` e `materia1`, que são os erros de verdade, não se destacam do resto.
- **A 1366 px, o Documento quebra a linha impressa dentro da largura** ("mais do / erro"), o que atrapalha a leitura:
  é o custo visível da decisão em aberto sobre parágrafos refluídos (§6.1 da SPEC principal).
- **A 1366 px, a Imagem abre em 22 %** e os símbolos ficam abaixo da dobra.

## 3. Os motores nas mesmas linhas

Sem treino neste livro, com os recortes das linhas do programa. **A condição não é igual:** o programa usa a CNN e a base
globais, treinadas em livros de xadrez (500.961 amostras), com os padrões do livro vazios, sem saber se estes livros estão
entre elas; os outros usam modelo de fábrica. **CER** é a distância de edição sobre os caracteres da verdade.

| Livro, material | Programa | PP-OCRv6 | Tesseract | EasyOCR | Consenso P+T+PP |
|---|---|---|---|---|---|
| Seirawan, escaneado, 213 linhas verificadas | 2,76 % | **0,74 %** | 1,24 % | 2,17 % | **0,45 %** |
| Aagaard, escaneado, 1 página revisada | 13,86 % | 5,70 % | 8,27 % | 10,55 % | **2,17 %** |
| Yusupov, escaneado, 2 páginas revisadas | 13,49 % | **7,67 %** | 25,74 % | 17,37 % | 8,16 % |
| Nunn, escaneado, 1 página (tabela) revisada | 16,22 % | 21,46 % | 22,30 % | 28,54 % | **14,56 %** |
| Dvoretsky, digital renderizado a 300 dpi, 6 páginas | 2,09 % | 4,38 % | 5,88 % | 7,10 % | **0,76 %** |

Nos quatro livros com figurinas juntos, por classe:

| | Programa | PP-OCRv6 | Tesseract | Consenso P+T+PP |
|---|---|---|---|---|
| Prosa: trocas e faltas fora dos tokens de lance, sem sobras | 6,34 % | **2,11 %** | 3,16 % | 2,33 % |
| Tokens com lance, por caractere, sem sobras | **3,57 %** | 18,34 % | 22,44 % | **3,14 %** |
| Sobras, sem classe | 331 | 59 | 566 | 217 |
| Figurinas erradas, sem contar cor | **9 de 498** | 498 de 498 | 498 de 498 | 9 de 498 |
| Tokens de lance errados, por presença | 35 de 554 | 428 de 554 | 461 de 554 | **26 de 554** |

Figurinas: 9 de 270 nos escaneados, 8 delas na tabela do Nunn; 0 de 228 no digital. Tokens de lance: 28 de 260 nos
escaneados com figurinas; 7 de 294 no digital. A contagem é por presença na unidade, sem posição: é um piso nos
escaneados, onde a unidade é a página.

**O que isso diz.**

- **Os motores são complementares.** Em figurina, o programa erra pouco, e os outros não têm a classe. Na prosa, sem contar
  sobras, os outros erram de 2 a 3 vezes menos. As sobras não têm classe: se todas fossem de prosa, o PP-OCRv6 manteria
  a vantagem (2,8 % contra 10,1 %), e o Tesseract não (9,7 %).
- **Em notação com letras, o programa perde também em lance.** No Seirawan, 26 tokens errados em 135, contra 8 do PP-OCRv6,
  que aí ganha até do consenso (11).
- **O consenso simples fica abaixo do programa nos 5 livros, e abaixo de todos os motores em 4;** no Yusupov, o PP-OCRv6 sozinho ganha por pouco. A
  regra: onde os dois outros concordam entre si e discordam do programa, vale o deles; token com figurina não muda.
- **Esta medida não é cega.** A regra base veio do Seirawan. A proteção de figurina foi acrescentada e ampliada depois de
  ver os livros com figurinas, e a tabela mostra só a variante com o PP-OCRv6; com o EasyOCR no lugar dele, são 38 tokens
  errados, contra 35 do programa. Só a avaliação da §3.2 da SPEC, em páginas novas, pode confirmá-la.
- **O consenso quase sempre ajuda, mas não sempre.** Das 819 edições, 756 reduziram o erro em conta líquida. O contador acha
  22 sobre caractere certo, 14 delas na tabela do Nunn, mas não vê inserção errada; pela conta líquida, até 31 pioraram. No
  Nunn, só 20 das 56 edições ajudaram.
- **A cadeia do core (CNN + Tesseract) dá 0,97 %, contra 2,43 % do programa e 1,09 % do Tesseract sozinho,** no Seirawan,
  contando trocas e faltas por página (E0). O core tem 342 sobras, contra 32, e não se separou quantas são das linhas não
  verificadas. Ela existe, e o app não a usa. Não tem treino por livro, e não foi medida em lances.

**Ressalvas.**

- Os escaneados com referência têm uma a duas páginas, **escolhidas por serem difíceis** (`corpus_v2`), e a comparação é
  por página. Refeita por token, a ordem explica até 16 de 69 no Nunn e quase nada nos outros: o grosso são sobras e erros
  reais. Os dois do Yusupov têm resultado invertido entre si (30 contra 109; 113 contra 46). Não se comparam com as linhas
  do Seirawan, e são pouca coisa para generalizar.
- O treino por livro não foi medido em motor nenhum. Ele pode mudar o quadro a favor do programa, e a vantagem do programa
  em figurina pode conter treino sobre o mesmo material.
- Os recortes vêm da segmentação do programa: linha que ele perdeu, ninguém lê.
- O Dvoretsky é imagem limpa: é o melhor caso.

## 4. A fila de revisão

Perícia nas 213 linhas verificadas do Seirawan, por box e por motor (**Medido**):

| Medida | Valor |
|---|---|
| Boxes | 10.005; com erro, 199 (1,99 %) |
| Na fila | 1.799 (18,0 %) |
| Precisão da fila | **9,3 %**: 9 em cada 10 paradas não têm erro |
| Revocação da fila | 83,9 % |
| Erros silenciosos | 32 de 199 boxes lidos com erro (16,1 %); 2 em lance |
| Fora dessa conta | 74 faltas, 14 em lance. Com elas, até 106 de 273 (38,8 %) e até 16 de 25 em lance (64 %). As linhas têm 78 boxes vazios, que vão à fila e devem cobrir boa parte, mas não se cruzou |
| Linhas perfeitas | 72 de 213 (33,8 %) |

Como sinal de revisão, a discordância entre motores, por caractere (trocas e sobras; token com figurina fora):

| Sinal | Marca | Pega | Precisão |
|---|---|---|---|
| Fila de hoje, Seirawan, por box | 18,0 % | 83,9 % | 9,3 % |
| Discordância com o PP-OCRv6, Seirawan | 2,3 % | **98,4 %** | **88,3 %** |
| Discordância com o Tesseract, Seirawan | 2,4 % | 96,7 % | 83,0 % |
| Discordância com o PP-OCRv6, 4 livros com figurinas | 6,4 % | 81,1 % | 85,8 % |
| Discordância com o Tesseract, 4 livros com figurinas | 6,9 % | 74,4 % | 72,7 % |

A comparação é aproximada: a primeira linha é por box, e as outras por caractere. Nenhuma conta as faltas, 80 dos 331
erros do Seirawan. **Sobre os 331, a fila pega uns 167 (50 %), o PP-OCRv6 242 (73 %) e o Tesseract 234 (71 %).** A ordem se
mantém, com distância menor. Das 64 linhas em que Tesseract e programa concordam por inteiro, 2 estão erradas.

**Em livro com figurinas, a discordância não marca nenhum token com figurina,** por construção: os outros motores não têm a
classe e sempre discordariam. A revocação dela em lance não foi medida. É preciso outro sinal para eles (X-1, na SPEC).

**Por token, que é o que o revisor vê, o quadro muda (exploratório):**

| Sinal, Seirawan | Tokens marcados | Lance errado pego (de 26) | Silencioso em lance (N = 137 pela gramática provisória; 135 pela `SAN`) | Prosa errada pega (de 232) |
|---|---|---|---|---|
| Fila de hoje | **58,7 %** | 18 | 5,8 % (IC 2,6 a 11,2) | 202 |
| Discordância com o Tesseract | 11,5 % | 17 | 6,6 % (IC 3,0 a 12,1) | 188 |
| Discordância com o PP-OCRv6 | 10,3 % | 14 | 8,8 % (IC 4,6 a 14,8) | 190 |

| Lances errados pegos, por token | Errados | Com figurina | PP-OCRv6 | Tesseract |
|---|---|---|---|---|
| Aagaard | 16 | 13 | 2 | 4 |
| Nunn | 17 | 17 | 8 | 8 |
| Yusupov | 3 | 1 | 2 | 2 |
| Dvoretsky | 16 | 12 | 4 | 5 |
| **4 livros** | **52** | **43** | **16 (31 %)** | **19 (37 %)** |

**Conclusão: a discordância é um ganho claro em prosa, e não está provada em lance, que é a métrica primária.** Nos livros
com figurinas, ela marca de 18 % a 20 % dos tokens, faixa em que o efeito do realce deixou de ser significativo no estudo
citado. Por isso o plano vigia por classe, e a fila Lances, que não depende de motor, vem antes (M2).

**O próprio gabarito tem ruído.** O rascunho vem do programa, e a conferência cega nunca rodou. Nas linhas em que o programa
concorda com o gabarito e outro motor discorda, 8 de 14 olhadas eram erro do gabarito: 0,39 % de 2.077 tokens (IC 0,17 % a
0,76 %), e é um piso. Corrigidos, o CER do programa sobe a cerca de 2,82 %, e o do PP-OCRv6 cai a cerca de 0,67 %. Os erros
estão listados em `docs/revisoes/checkup-2026-11/erros-do-gabarito.md`; não foram corrigidos.

**De onde vêm os erros no Seirawan:**

- **O k-NN global lê 11,5 % dos caracteres e faz 52 % dos erros** (9,04 % de erro contra 1,07 % da rede).
- **A confiança dele não é probabilidade.** Com confiança 0,42, ele acerta 92,5 %. O erro de calibração é 0,391, e o da
  rede é 0,008. A régua única de 0,90 vira um teste de fonte disfarçado.
- **Três confusões fazem 46 % das trocas:** `1→l` (58), `0→o` (37), `9→g` (8). Não se mediu quantas ficam dentro de palavra.
- **Uma regra de frequência sobre dígito em palavra** (`wordfreq`, não o `core.lexico`) baixa o CER de 2,76 % para 2,04 %,
  com 6 das 75 linhas mudadas pioradas. Medida só no Seirawan.
- **No Aagaard, a segmentação pesa:** `m` vira `1n` (`in1n1cdiatc`, "immediate"). O corpo é pequeno, com altura mediana
  de 20 px.

**Dois sintomas soltos da medida do Seirawan (`2026-11-05-qualidade-xv.json`):**

- **Lado a jogar certo em 2 de 5.** Sem rede de proteção visível.
- **A capa inventa 1.442 linhas e 5.429 pendentes.** Pela conta, leva uns 6 minutos sozinha: as 9 páginas levam 452 s, e as 7
  de texto levam 67 s. Uma página de imagem não devia entrar assim. Ela também é a origem de toda a queda de precisão das
  margens (0,64; sem ela, 1,0) e do único diagrama falso.

## 5. Como os motores se ligam hoje

```
página → segmentação em boxes (irreversível; o árbitro é a própria cascata)
       → cada box sozinho: k-NN do livro → CNN → k-NN global → "não li"
            (primeiro que passa o limiar vence; top-k, margem e distância são descartados)
       → contexto: palavra e linha só mandam à fila ou sugerem
       → legalidade: só a primeira linha depois de um diagrama, e só muda o estado do diagrama
       → fila: conf < 0,90 ou a palavra desmente; padrão do livro não volta pela confiança
       → exportação: outro caminho de texto (montagem), não o Documento
```

Os dois defeitos de arquitetura, detalhados em `checkup-2026-11/motores.md`:

- **A decisão é gulosa e joga a evidência fora.** Nada depois do leitor tem de onde tirar uma alternativa.
- **Só há um ponto de vista.** Sem uma segunda leitura independente, o programa não tem como saber que errou com
  confiança alta.

**O que falta, na ordem do plano:**

1. **O olho no lugar certo:** uma fila pelas linhas com lance, imagem sobre texto (F-4). Sem motor novo. Não medida.
2. **A legalidade como sinal,** além da primeira linha depois do diagrama (F-3, X-1). Só marca, nunca troca.
3. **Uma régua que reprove:** erro silencioso por classe, gabarito auditado, catraca (R-1 a R-3).
4. **Guardar a evidência** que hoje se joga fora: a margem, e o top-3 sob demanda (L-1).
5. **Uma segunda leitura independente,** alinhada por caixa, que vira marca e nunca troca caractere (L-2, F-1).

## 6. O estado da arte, no que muda a decisão

Detalhe e fontes em `checkup-2026-11/estado-da-arte.md`. A maioria das páginas foi lida por extrator automático: conferir
na fonte antes de decidir por um número.

- **VLM não serve como leitor principal aqui:** sem confiança nem caixa por caractere, o erro típico é plausível, e o
  hardware não cabe. Em xadrez, plausível é o pior erro.
- **A legalidade é a alavanca clássica:** Baird e Thompson (1990) relatam erro cerca de 30 vezes menor, número visto em
  resumo. Não achei trabalho moderno que a use dentro da decodificação em livro impresso. **Legal não quer dizer certo:**
  ordena hipóteses e abre dúvida, nunca reescreve em silêncio.
- **A temperatura não reordena dentro de um mesmo modelo** (conclusão do levantamento). A fila daqui mistura rede e k-NN:
  calibrar cada fonte muda a ordem entre elas, não dentro. O que reordena é informação nova: discordância, margem legal.
- **Realçar não reduziu o erro final no único estudo achado** (fala, não OCR, 36 pessoas; p = 0,767). A chance de corrigir o
  erro realçado foi 2,64 com 4 % das palavras marcadas, e deixou de ser significativa com 13 a 21 %. A fila de hoje marca
  18 % dos boxes; não se mediu em palavras.
- **No único estudo achado com os dois lado a lado** (grego e árabe), o treino no domínio pesou mais que a arquitetura. Vale
  medir o ajuste por livro nos motores de linha antes de trocar qualquer um.

## 7. O que não foi verificado

- Nenhum achado de interface foi testado à mão. Vi capturas, sem interagir com a janela.
- Foco invisível e Alt+3 estão confirmados no código, mas não observados na janela.
- A legalidade como sinal não foi medida.
- A fila Lances, centro do plano, não existe e não foi medida.
- A fila de hoje nos 4 livros com figurinas não foi medida.
- O Tesseract lendo a página inteira, que é o desenho da spec: os números são por linha.
- O tempo das opiniões é por linha, num lote pequeno, sem o custo de integrar.
- Tesseract sem configuração controlada: não se sabe se o `tessdata` é `fast` ou `best`, sem ampliar corpo pequeno.
- Se os livros testados, ou irmãos da mesma série, estão na base de treino da CNN. A pasta `Box/` do core tem caixas de três
  livros de Aagaard, e isso pode explicar parte da vantagem em figurina.
- Busca, substituição e operações de página não tiveram auditoria de interface.
