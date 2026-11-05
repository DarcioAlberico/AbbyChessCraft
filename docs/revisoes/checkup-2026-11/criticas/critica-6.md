# Crítica 6 de 6: aceitação

Sobre `docs/pesquisa/checkup-2026-11.md` (REL), `docs/SPEC-pagina-perfeita.md` (SPEC) e `plans/roadmap-pagina-perfeita.md` (ROAD), em `C:\Python-Chess2\AbbyChessCraft-coordenadas`, ramo `checkup-geral`, `262d897`. "REL:N" é linha do arquivo como está hoje.

**O que rodei.** Li os três do começo ao fim e as cinco críticas. Scripts leves, só com contagens: `c6_matriz.py`, `c6_prov.py`, `c6_linhas.py`, `c6_b.py`, `c6_c.py`, nesta pasta. Nenhum pytest, OCR ou edição no repositório. Trechos de código conferidos à mão em cerca de 15 citações `arquivo:linha`.

## 0. Veredito

**APROVADO COM CORREÇÕES.** A estrutura se sustenta: M1 a M3 entregam sem depender de nada do usuário além de decisões com padrão, e as cinco críticas entraram quase por inteiro. Falta o que nenhuma viu: o item central do plano (fila Lances) não tem medida de que pega erro, a catraca P1 fica presa a uma decisão que por padrão nunca vem, os números que decidiram a ordem do plano estão só no scratchpad, e o relatório abre com uma conclusão que o próprio plano abandonou.

| | Achados |
|---|---|
| **Bloqueante** | B1 a B4, todos de texto, mais uma cópia de arquivos |
| **Importante** | I1 a I12 |
| **Menor** | M1 a M18 |

Aplicar B e I antes do commit de PP0, item 0. Não pede nova rodada de crítica: pede rodar de novo `c6_matriz.py`.

---

## 1. Atende ao pedido?

| Pergunta | Resposta |
|---|---|
| "Como está o programa", para quem não leu nada | **Sim.** REL §1, primeiro parágrafo, e §2 |
| "Como os motores se ligam" | **Sim,** REL §5, curto e correto |
| "O que falta para a página perfeita" | **Não.** O relatório lista o que está errado e manda à spec. Nenhum trecho diz o que falta. B4 |
| Conclusão clara no início | **Em parte, e errada num ponto.** REL §1 item 3 vende a discordância; REL §4 conclui que ela "não está provada em lance". A fila Lances, que é a resposta do plano, só aparece em REL:199, sem definição. B4 |
| Ordem de importância | **Não.** §1 diz que "o maior problema não é de engenharia", e §2 é saúde de código, antes dos motores. Não proponho mover: B4 põe a ordem no §1, e a renumeração quebraria citações (§3.2, §4) |
| Relatório → spec → roadmap | **Sim.** Ids, CA e Dec se seguem (§3 abaixo) |
| Achar o que fazer na segunda-feira | **Não no relatório.** No ROAD, a linha 20 dá a ordem e a linha 9 o tempo, mas nada diz "comece aqui". B4 |

## 2. Correções aplicadas

### Amostra de 44 correções, com prioridade às bloqueantes

| Origem | Item | Onde está | Estado |
|---|---|---|---|
| C1 B1 | Tesseract pior em CER nos 5 | SPEC:291 | Entrou |
| C1 B2 | Medida não cega | REL:129-131 | Entrou |
| C1 B3 | 22 a 31 de 819 | REL:132, SPEC:304, Dec-3 | Entrou |
| C1 B4 | Sobras à parte | REL:109-111, :123 | Entrou |
| C1 B5 | Faltas no silencioso | REL:161, SPEC:369 | Entrou |
| C1 B6 | Core não medido em lance | REL:137, SPEC:294 | Entrou |
| C1 B7 | 17 páginas | REL:38 | Entrou |
| C1 B12 | `saidas_lidas` | JSON: 2429, 16:28, 75 e 6, 64 e 2, 20 px | Entrou; `in1n1cdiatc` só no REL, sem importância |
| C2 B1 | Auditoria do gabarito | SPEC:181-187 | Entrou |
| C2 B2 | Silencioso operacional | SPEC:43-57 | Entrou |
| C2 B3 | `classificar_token` | SPEC:74-95 | **Parcial:** perdeu "Figurina sem casa é Figurina solta". M2 |
| C2 B4 | Três conjuntos | SPEC:189-201 | Entrou, com os ajustes de C4 e C5 |
| C2 B5 | Alvos e intervalo | SPEC:99-129 | Entrou; conferi a tabela e "até 6 tokens" com DEFF 2 |
| C2 B6 | CA por classe | CA-F1.1, ROAD:276 | Entrou |
| C2 B7 | Ordenar e cortar | SPEC:373-385 | Entrou |
| C2 I3 | R-4 no fim de M5 | SPEC:228-234 | Entrou |
| C3 B1 | D-3 `remendar` | SPEC:552 | Entrou |
| C3 B2 | L-1 em três partes | SPEC:242-250 | Entrou; `hipoteses/` sumiu |
| C3 B3 | L-2 por imagem | SPEC:254-285 | Entrou; `servidor_de_opiniao` sumiu |
| C3 B4 | Fora de `pendentes` | SPEC:377 | Entrou |
| C3 B4 × C4 B6 | Conta do F6 | SPEC:379 × :475 | **Contradiz.** I7 |
| C3 B5 | L-4 1:1 | SPEC:306-308 | Entrou |
| C3 B6 | L-9 sem estado novo | SPEC:355 | Entrou |
| C3 B7 | `letras_das_pecas` | SPEC:82, ROAD:148 | Entrou |
| C3 B8 | Sincronia | SPEC:503 | Entrou |
| C3 I4 | `gids_do_rejeitado` | SPEC:413 | Entrou; `Lance` e `Validacao` não mudam |
| C4 B1 | Marcos | ROAD:7-14 | Entrou |
| C4 B2 | Dec-5 em níveis | SPEC:630-638 | **Parcial:** perdeu a recomendação. M3 |
| C4 B5, B6 | F-4 | SPEC:420-492 | Entrou; o título ficou sem marca de evidência. B1 |
| C4 cortes | L-7, X-5, G2-d, injeção, marca fraca, L-6f, U-12 | grep | Entraram |
| C4 I5 | L-9 nunca em silêncio | SPEC:361 | Entrou |
| C5 B1 | Contrato, ramo | ROAD:71-78, :99 | Entrou |
| C5 B2 | Passo PPT | ROAD:176-192 | Entrou |
| C5 B3 e §6 | PP2d sem A-6 | ROAD:112-120 × :356 | **Parcial:** T4 ainda diz "A-3 e A-6 estão em PP2d". M1 |
| C5 B4 | Sem rebobinar | SPEC:503, ROAD:227 | Entrou |
| C5 B5 | Ordem de PPL | ROAD:147-156 | Entrou |
| C5 B6 | "com 2.ª opinião" | SPEC:424, :475 | Entrou |
| C5 B7 | Arquivo dos 8 erros | `docs/revisoes/` | Entrou. **O mesmo risco ficou nas tabelas por token.** B3 |
| C5 B8 | Registro por página | ROAD:155 | Entrou |
| C5 B9 | Teclas | SPEC:422, :448 | Entrou |
| C5 B10 | Ciclo de CA-E5 | ROAD:210, SPEC:573 | Entrou |
| C5 B11 | Dec-5 B e CA-F1.1 | SPEC:393, ROAD:91 | Entrou; **(b) ficou sem método.** I3 |
| C5 I8 | Dec-4 no fim | ROAD:48 × SPEC:644 | **Refez o círculo.** I9 |
| C5 M10 | Ordem de CA-R1.4 | SPEC:161-165 | **O script partiu o CA ao meio.** I8 |

### As frases caçadas

| Frase | Resultado |
|---|---|
| 98,4 % | Só REL:169 (tabela, com a nota da base) e SPEC:292, "por caractere". Limpo |
| "barata" | Sumiu. "Barato" em SPEC:345 (holdout, certo) e ROAD:245, "ganho barato medido", **falso**. M6 |
| "Tesseract padrão" | Sumiu; "Padrão provisório, por custo" |
| "página com evidência" | Sumiu. Só "com evidência carregada" em CA-L2.7, correto |
| `hipoteses/`, `servidor_de_opiniao`, G2-d, X-5, L-6f, U-12, Alt+S, "quinto", "18 páginas" | Sumiram |
| "marca fraca" | Só "Não há" em SPEC:430 |
| L-7 | Só "fora do plano" |
| PP numerações | Todo PP citado tem passo. A numeração engana: PP2d antes de PP1. M18 |
| Dec-5 agora × depois | Coerente: sob "Depois", no fim de M3 |
| 5 × 4 livros | Coerente: quatro; N ≥ 1.600 nos dois |
| F7 | Coerente |
| `medir_sincronia` | Coerente: PPL item 4, PP2b, CA-X1.3 |
| `Validacao`, `Lance` com gids | Coerente |
| Ordem dos itens em M1 | Coerente com "Ordem de execução" e com as seções |
| `fortes` | **Falha.** I7 |
| "fila de hoje" | Sentido certo, mas **ambíguo em SPEC:424**. M4 |

## 3. Coerência interna, por script: só o que falhou

113 CA definidos. Nenhum CA, id, Dec ou PP citado sem definição, salvo os subitens legítimos (`L-1a` a `L-1c`, `U-5` genérico em SPEC:616). Títulos em ordem. Somas de sessões conferem (31 a 38; 41 a 51, escritas "40 a 50").

| Falha | Onde |
|---|---|
| CA-R1.4 com o texto partido por outros três CA | SPEC:161-165 (I8) |
| CA-A6 sem passo, e T4 diz que está em PP2d | ROAD:356 (M1) |
| `pendentes ∪ fortes` × "só as fortes" | SPEC:379 × :475 (I7) |
| CA-A5 depois da pergunta que precisa do número dele; "agora" × "só então" | ROAD:48, SPEC:590, :644 (I9) |
| "Figurina solta" na tabela e sem regra em `classificar_token` | SPEC:69 × :80 (M2) |
| "Lance conferido" com duas definições | SPEC:459 × :680 (M5) |
| "ficam corrigidas no projeto" × "numa cópia do projeto" | SPEC:197 × :203 (I10) |
| F-4 sem marca de evidência, contra §0 | SPEC:418 (B1) |
| R-4 e L-8 são "Hipótese" sem "Derruba", contra §0 | SPEC:226, :343 (M9) |
| PP6 "Custo: médio" × Dec-3 "1 sessão" | ROAD:303 × SPEC:643 (M10) |
| Campos faltando: PP1b sem Contexto; PP2b e PP2c sem CA e Risco; PP6 a PP9 sem Pronto e Carga | Aceitável nos dois primeiros grupos; em M6, M11 |
| Sem CA citado no ROAD, cobertos só pelo id: CA-A1, A2, A4 (T4, "ao tocar"), CA-U1b, U2, U5b, U5c, U6, U7, U9 (T1) | Aceitável |

## 4. Qualidade do texto

**A spec virou remendo em três lugares, não no todo.** 60 das 683 linhas passam de 300 caracteres, e o resto está quebrado a 120: dá para ver as camadas a olho, e foi assim que CA-R1.4 partiu. Não reescrever por isso. Os três lugares: o fim da §5.1 (I11), o CA partido (I8), e `fortes` (I7).

**Jargão.** O relatório depende da crítica em REL:181 e :183, e a spec em :181. "Exploratório" não está definido em lugar nenhum, e a spec o usa 4 vezes. Correção em B3.

**"Você".** §10 e os textos de tela falam com o usuário, e isso está certo. O ROAD mistura "você" (:7, :14, :18, :33) e "o usuário". Primeira pessoa solta em SPEC:536 e REL:54. M12.

**Frases ambíguas:** SPEC:260, "Só leitura: lê, mostra, não grava", logo antes de "O que grava" (M7); REL:127, "corta o erro em todos os livros, salvo Yusupov", quando o consenso também ganha do programa no Yusupov (M8); SPEC:424, "a de hoje" (M4).

**Cortes de 10 a 20 %?** Sem perder nada, **não**. Contei 20.845 palavras nos três; o que sai sem custo são cerca de 800 (4 %). Chegar a 10 % pede tirar o detalhe de itens opcionais de M6 (L-4, L-1c, X-2, X-4), uns 1.300, e aí é preciso reescrevê-lo quando pedirem. Recomendo só os 4 %:

| # | Onde | O que cortar | Palavras |
|---|---|---|---|
| 1 | SPEC:304 | "Das 819 edições medidas, 756 reduziram o erro em conta líquida, e de 22 a 31 pioraram, a maioria na tabela do Nunn." Está no REL e em Dec-3 | 22 |
| 2 | SPEC:310 | "A evidência "756 de 819" mede edições de todo tipo; só as 1:1 valem aqui, e o número sai menor." | 20 |
| 3 | SPEC:314 | "Hoje, por caractere e em todo tipo de edição, [...] erro do gabarito." | 35 |
| 4 | SPEC:298 | O parágrafo "Hipótese a testar antes do PP-OCRv6 pesado" inteiro: só existe com Dec-2 b | 45 |
| 5 | SPEC:369 | Trocar pelo texto curto: "Precisão de 9,3 %, 18 % dos boxes marcados (relatório, §4). A régua de 0,90 compara escalas diferentes. O padrão do livro fica isento pela confiança." | 20 |
| 6 | SPEC:387-391 | Ver I11 | 50 |
| 7 | SPEC:498 | "Medido aqui, por presença na unidade: 35 tokens errados em 554, nos livros com figurinas; 24 lidos em forma válida e falsos. No Seirawan, 26 em 135." | 25 |
| 8 | SPEC:274 | Trocar por: "**Custo, a medir em CA-L3.1.** De 3,5 a 15 min em 300 páginas, pelo registro do core. Por linha, de 22 a 58 min (relatório). **A precisão do Tesseract de página não foi medida.**" | 25 |
| 9 | SPEC §12 | Linhas que só repetem o item: "O PP-OCRv6 trava a máquina", "Dependências novas conflitam", "A fila vazia parece conferido", "Opinião velha depois de editar", "A opinião chega no meio de uma página" | 110 |
| 10 | SPEC §13 | Marca forte, Erro silencioso, Residual: definidos na §1 e em F-4 | 30 |
| 11 | SPEC:567, ROAD:348 | C-8 e CA-C8: opcional, e a última rodada travou a máquina | 35 |
| 12 | SPEC:197 | "Três conjuntos de quatro livros não se confundem: com figurinas, de avaliação, e com verdade humana hoje." | 18 |
| 13 | SPEC:150-151, :169-170 | As aberturas que repetem o relatório | 30 |
| 14 | SPEC:347 | "A rede global nunca aprende pelo uso. Fora de escopo até o holdout existir. Pedido ao core, se valer." | 18 |
| 15 | ROAD:358-371 | Antipadrões: manter "Olhar a lista de erros", "Medir em gabarito não auditado", "Mover método" e "Citar 99,76 %". O resto está no contrato | 60 |
| 16 | ROAD:276 | Trocar por: "**Contexto.** É o maior ganho medido **em prosa** e não é evidência sobre a métrica primária (relatório, §4). Não muda nenhum caractere, mas pode criar erro silencioso: CA-F1.1 vigia por classe." | 60 |
| 17 | ROAD:96 | "`qualidade.py` reprova nele: `exportar_as_selecionadas` repete `exportar` (0,88), e `_cinza` se repete entre `coordenadas.py` e `diagramas.py`." Está no item 2 | 20 |
| 18 | ROAD:196, :224 | Os dois "Contexto" de PP2 e PP2b | 50 |
| 19 | ROAD:36 | A linha PP2c da tabela de paradas: com um livro só, o próprio passo diz que "PP5 segue". Não trava nada | 20 |
| 20 | REL:117-118 | ""Lance" tem três regras [...] para o mesmo livro." Sobe a `motores.md`, e a spec resolve | 25 |
| 21 | REL:264-265 | "C-1 não foi reproduzido" e "O ganho do treino por livro não foi medido": já estão em REL:66 e :145 | 15 |

---

## 5. Achados

### Bloqueantes

#### B1. Nada mede se a fila Lances pega erro, e o critério dela premia o descuido

**Onde.** SPEC:55, :450, :491; ROAD:33, :144.

**Problema.** A spec chama a fila de "item de maior efeito do plano" sem nenhum número. O que a decide:
- **Tempo:** "até 2 min por página". É teto, sem piso: Enter, Enter, Enter passa.
- **Confiança:** "você diz que passou a confiar nela". Confiar é justamente o risco que B4 de C4 descreveu.
- **A métrica primária não a vê, por definição:** "Lance conferido por linha [...] conta como conferido, à parte: não é sinal" (SPEC:55).
- **O residual só chega em M5, com 3 páginas,** e só com Dec-5 B ou C. **No padrão, Dec-5 A, o plano acaba sem saber se o seu item central funciona.**

**O agravante.** Enter marca `revisado` (`edicao.revisar`). Com D-5, o glifo não é mais relido; L-2 não dá opinião a ele; ele sai de F6 e da fila; o lance legal e errado passa a contar como "conferido" no relatório. **Um Enter apressado torna o erro permanente e invisível.** Conferido não quer dizer certo, e a tela diz `Lances conferidos: 40`.

**A medida é barata e nenhuma crítica a propôs.** PPL item 4 já lê as 7 páginas do Seirawan e as 4 do `corpus_v2`. Elas têm gabarito e **54 tokens de lance errados conhecidos**, sem plantar nada (26 em 135; 28 em 260). As linhas com lance são umas 110: contei 53 no Seirawan e 55 nas 4 páginas. A 4,5 s, **uns 10 minutos do usuário**.

**Conferi a outra premissa, e ela se sustenta:** "10 a 15 linhas por página". Em 21 páginas com gabarito, a mediana é 12 linhas com lance, de 0 a 40, e 2 passam de 27 (2 min a 4,5 s por linha). Logo o CA precisa dizer mediana.

**Correção. ROAD:33, a linha inteira:**

> | Fim de M2 | Em 20 páginas reais, a mediana é de até 2 min por página, pelo registro de eventos; **e** CA-F4.10 corrige pelo menos 80 % dos lances errados conhecidos | A fila Lances fica só com os ilegais. Sem ela, nada em M3 a M5 ataca o lance errado e legal: PP7 passa a ser a proposta seguinte |

**SPEC, depois de CA-F4.9:**

> - **CA-F4.10 (PPL).** Numa cópia com as 7 páginas do Seirawan e as 4 do `corpus_v2`, lidas sem padrões e sem revisão, o usuário passa a fila Lances (umas 110 linhas, 10 min). `medir_sincronia` conta os tokens de lance errados antes e depois, contra o gabarito, por livro, com o IC. Sem erro plantado. O Seirawan já foi visto, e o `corpus_v2` não foi auditado: vale como indício, não aprova alvo.

**SPEC:491:** trocar "a fila Lances leva até 2 min por página, pelo registro de eventos" por "a mediana da fila Lances é de até 2 min por página, pelo registro de eventos (05/11: mediana de 12 linhas com lance, de 0 a 40)".

**SPEC:418:** `### 5.4 F-4. A sessão de revisão (P1, Hipótese: CA-F4.8 e CA-F4.10)`

**SPEC:450:** trocar "**É o item de maior efeito do plano: a única garantia" por "**Deve ser o item de maior efeito do plano, e não foi medido: a única garantia".

**ROAD:158:** acrescentar `CA-F4.10`. **ROAD:144:** trocar "CA-F4.8 pode derrubá-la" por "CA-F4.8 e CA-F4.10 podem derrubá-la". **ROAD:10:** trocar "45 min: 8 erros do gabarito, e 20 páginas reais" por "1 h: 8 erros do gabarito, 10 min de CA-F4.10 e 20 páginas reais".

**SPEC §12, nova linha:**

> | Conferir depressa trava o erro | Glifo `revisado` não é relido, não tem opinião e sai das filas; o relatório o conta como conferido | CA-F4.10 mede. O relatório diz "conferidos", nunca "certos" |

#### B2. A catraca P1 fica presa a uma decisão que, por padrão, nunca vem

**Onde.** ROAD:205, :208, :47; SPEC §3.3; REL §1 item 4.

**Problema.** "Nenhum teste reprova por qualidade de OCR" é um dos quatro problemas do veredito, e R-3 é P1. Mas a catraca é o item 6 de PP2, e "Sem ela [Dec-5 B ou C], PP2 não começa, e o plano acaba em M3". **No fim curto, que é o padrão, o modelo pode sumir e a suíte seguir verde para sempre,** e o roadmap diz "Nada fica pendente".

Pior: **M1 a M3 mudam leitura sem proteção.** D-5 muda o que se relê, `letras_das_pecas` muda `lances._tabela` e `sessao.figurinas`, L-9 deixa de ler páginas, e os 8 erros mudam o gabarito. A catraca não pede hora nenhuma do usuário: usa o gabarito que já há, e leva ~70 s por portão. `medir.py:388` já calcula `cer_corpo`.

**Correção. ROAD, PP1, antes do item 1:**

> 0. **R-3 mínimo,** sobre o gabarito que já há: teste `livro_real` das 7 páginas, com rede carregada, `cer_corpo`, casas erradas, diagramas e linhas perdidas. É regressão: não aprova nada, por isso não pede auditoria. D-5, `letras_das_pecas` e L-9 mudam leitura antes de M4.

**ROAD:134:** `**CA:** CA-R3.1, CA-R3.2, CA-R3.3 (sem a parte por classe), CA-R3.5, CA-C2, CA-C5, CA-D1, CA-D2, CA-D4, CA-D5.`
**ROAD:140:** "4 sessões". **ROAD:205:** `6. A catraca passa a ser por classe, com `tokens.py` (CA-R3.3 e CA-R3.4).` **ROAD:212:** trocar `CA-R3.*` por `CA-R3.3, CA-R3.4`. **ROAD:220:** "3 a 4 sessões". **ROAD:9:** 7 sessões. **ROAD:12:** 4 a 5. Os totais não mudam.

#### B3. Os números que decidiram a ordem do plano estão só no scratchpad

**Onde.** REL:181-195; SPEC:99, :108, :291, :375, :389; ROAD:276.

**Problema.** As tabelas por token (58,7 %, 5,8 %, 18 de 26, 31 %, 37 %), os DEFF e os 190× vieram de `c2_b.py` e `c2_c.py`, que leem `motores3.json` e `motores-xv-p.json` num caminho fixo do scratchpad desta sessão. **Eles não estão em `experimentos/`, e nenhum desses números está em `2026-11-05-motores.json`** (conferi por busca em `c6_prov.py`). A conclusão mais importante do relatório, "não está provada em lance", cita "crítica 2", que nenhum leitor terá. E PP2 item 2 manda `medir_motores` "a partir de `checkup-2026-11/experimentos/`" e "igualar": a referência por token não estará lá. É o mesmo defeito de C5 B7, e **vale a mesma urgência: o scratchpad não sobrevive à sessão.**

**Correção. Agora, antes de tudo:**

1. Copiar `c2_b.py` e `c2_c.py` para `docs/pesquisa/checkup-2026-11/experimentos/por_token_a.py` e `por_token_b.py`, trocando o caminho fixo por um argumento. Conferi nos `print`, sem ler cada linha: a saída na tela é de contagens, e o código não traz texto de livro. A seção 8 de `c2_b.py` grava `c2_candidatos.txt`, com palavras: tirar essa escrita, ou apontá-la para fora do repositório. Eles também leem `perita-xv.json`. `c2_pares.txt` e `c2_f.py` ficam de fora: um tem pares, o outro imprime janelas de texto.
2. Em `2026-11-05-motores.json`, nova chave `por_token_exploratorio`, com as tabelas de REL:183-195, os DEFF (1,0 a 1,1; 3,5 a 4,6; 15) e P(erro | concorda) por livro.

**REL:12, acrescentar à "Marcas":**

> **Exploratório:** conta refeita depois sobre as mesmas saídas, por token, com uma gramática provisória e antes de auditar o gabarito (`experimentos/por_token_*.py`, chave `por_token_exploratorio` do JSON). Serve para derrubar e dimensionar, não para aprovar.

**REL:181:** `**Por token, que é o que o revisor vê, o quadro muda (exploratório):**`
**REL:183:** trocar "(N = 137, pela regra de token da crítica 2; 135 pela `SAN`)" por "(N = 137 pela gramática provisória; 135 pela `SAN`)".

**SPEC §0, nova linha:**

> - **Exploratório:** conta de 05/11 sobre o conjunto de ajuste, com gramática provisória (relatório, "Marcas"). Dimensiona; não aprova CA.

**SPEC:181:** trocar "Numa olhada contra a imagem, na crítica metodológica de 05/11:" por "Numa conferência contra a imagem, em 05/11:".

#### B4. O relatório abre com a conclusão que o plano abandonou, e não diz o que falta nem o que fazer

**Onde.** REL §1 item 3, REL §5, REL §7.

**Problema.** Quem lê só o veredito sai achando que a discordância é a resposta ("marca menos e pega mais que a fila"). O §4 conclui o contrário em lance, e o ROAD:26 diz que ela "não é onde o trabalho se ganha nem se perde". A palavra "Lances", resposta do plano, não está no §1. Nada diz que **sem o usuário conferir páginas o OCR não muda um caractere**, nem que o plano não entrega a página perfeita. O pedido dizia "o que falta": REL §5 tem 2 defeitos, sem lista.

**Correção. REL:29-32, o item 3 inteiro:**

> 3. **A discordância entre motores é um sinal novo: claro em prosa, não provado em lance.** Por caractere, no Seirawan, ela marca menos e pega mais que a fila. Por token, nos livros com figurinas, ela não marca nenhum token com figurina e pega de 31 % a 37 % dos lances errados (exploratório, §4). Custa de 22 a 58 minutos a mais em 300 páginas, por linha, sem integrar; lendo a página inteira, de 3,5 a 15, sem precisão medida (**Medido**, §4).

**REL, depois do parágrafo "Limite de tudo" (:40), novo:**

> **O que fazer, em ordem** ([roadmap](../../plans/roadmap-pagina-perfeita.md), "Marcos"):
>
> 1. **Primeiro:** responder Dec-1 e Dec-6 ([SPEC §10](../SPEC-pagina-perfeita.md), 15 min) e começar o passo PP0.
> 2. **M1 a M3, sem conferir nenhuma página:** nada mais se perde; a fila Lances mostra cada linha com lance, imagem sobre texto, e o lance ilegal fica marcado; a tela destaca o que importa. Nenhum caractere da leitura melhora. A fila Lances é hipótese, e o plano a mede (CA-F4.10).
> 3. **M4 e M5, só se o usuário der ~10 h (Dec-5):** a régua, os consertos de leitura e a 2.ª opinião, cada um entrando por medida.
>
> **O plano não entrega a página perfeita.** Entrega erro silencioso medido, nos livros medidos, e menos atenção gasta. Para outro livro não se afirma nada.

**REL, ao fim do §5, novo:**

> **O que falta, na ordem do plano:**
>
> 1. **O olho no lugar certo:** uma fila pelas linhas com lance, imagem sobre texto (F-4). Sem motor novo. Não medida.
> 2. **A legalidade como sinal,** além da primeira linha depois do diagrama (F-3, X-1). Só marca, nunca troca.
> 3. **Uma régua que reprove:** erro silencioso por classe, gabarito auditado, catraca (R-1 a R-3).
> 4. **Guardar a evidência** que hoje se joga fora: a margem, e o top-3 sob demanda (L-1).
> 5. **Uma segunda leitura independente,** alinhada por caixa, que vira marca e nunca troca caractere (L-2, F-1).

**REL §7, acrescentar:**

> - A fila Lances, centro do plano, não existe e não foi medida.
> - A fila de hoje nos 4 livros com figurinas não foi medida.
> - O Tesseract lendo a página inteira, que é o desenho da spec: os números são por linha.

### Importantes

#### I1. A fila Lances não visita a linha em que o lance foi lido errado demais

**Onde.** SPEC:450, :469; ROAD:144.

**Problema.** A classe vem "só da verdade" na medida, mas no programa só há a leitura. Linha cuja leitura não tem forma de lance não entra na fila, não conta em `lances_por_conferir`, e a página pode dizer `Esta página não tem lances`. "Cobertura de todos os lances legíveis" não foi conferida, e o teto de cobertura de PP2b é sobre o texto do gabarito, que não vê isso.

**Medi (exploratório, gramática da crítica 2, por linha, Seirawan e Dvoretsky):** 4 de 149 linhas com lance ficam fora, com 5 de 450 tokens. **Mas esses 5 são todos errados: 5 de 42 tokens errados (12 %), IC 4 % a 26 %.** Ou seja, a fila perde pouco lance e perde justo o erro. A regra "entre duas linhas assim", que R-2 já usa no gabarito, recupera 2 das 4, ao custo de 22 % e 16 % mais linhas. Pela vizinha, recupera as 4, ao custo de mais que o dobro no Seirawan (112 contra 51).

**Correção. SPEC:450:** trocar "Anda pelas **linhas com token de lance**, em ordem de leitura." por "Anda, em ordem de leitura, pelas **linhas com forma de lance na leitura, e pelas que estão entre duas assim**."

**SPEC:469:** `` | Lances vazia, página sem lance | `Nenhuma forma de lance lida nesta página` | ``

**ROAD:144:** trocar "com cobertura de todos os lances legíveis" por "com cobertura dos lances cuja linha a leitura reconhece".

**SPEC, depois de CA-F4.10:**

> - **CA-F4.11 (PPL).** `medir_sincronia` lista, por livro, os tokens de lance da verdade em linha fora da fila, e quantos deles estão errados. Se passar de 5 % dos errados, a fila inclui também a linha vizinha.

#### I2. Conferir e corrigir na fila Lances não ensina

**Onde.** SPEC:452-454, :459, Princípio 8; ROAD:160.

**Problema.** Enter sem editar: `revisado`, "sem ensinar". Editar e Enter: "corrige pela sessão", sem ensinar; só Ctrl+Enter ensina. Isso foi aceito para não repetir os 8 sentidos de Enter. O efeito não foi visto: os glifos de lance, os que mais importam, **saem da fila de hoje sem virar amostra**, e o que foi corrigido à mão não vai aos padrões. O erro se repete nas páginas seguintes, e o Princípio 8 diz que o treino é o diferencial. CA-F.1 não vê: "o replay não usa Lances" (C5 I2). O ROAD:160 chama isso de "o desejado".

**Correção. SPEC §12, nova linha:**

> | A fila Lances não ensina | Os glifos de lance saem da fila sem virar amostra, e o erro se repete; CA-F.1 não vê, porque o replay não usa Lances | No ponto de parada de M2, contar amostras novas do livro por página, fora da amostra guiada. Caindo pela metade, Editar e Enter passa a ensinar os glifos que mudaram |

**ROAD:160:** trocar "é o desejado, e CA-F.1 confere" por "é o desejado na fila, e ninguém mede o efeito no treino: SPEC §12".

#### I3. CA-F1.1 compara com uma fila que o usuário não usa, e (b) não tem método no nível B

**Onde.** SPEC:393; ROAD:38, :91.

**Problema 1.** O CA corta a fila de hoje no mesmo `m` = 10 %. Para comparar sinais está certo. **Para decidir a troca, não:** o usuário sai da fila de hoje no `m` dela, 59 %, não de uma fila cortada. Nos números de REL:183-187, com o PP-OCRv6, o silencioso em lance sobe de 5,8 % para 8,8 %, e a prosa perde 12 tokens. O CA pode aprovar isso, e o ponto de M5 só pergunta minutos.

**Problema 2.** (b) pede "limite superior da diferença ≤ +0,5 ponto". O contrato diz que com menos de 20 páginas vale o teste de sinal, que não dá limite. Com B há ~950 tokens de lance (4 × (71 + 74 + 44 + 50)). Pela minha conta, com pares e DEFF 2, o limite só fica em 0,5 ponto com até 4 tokens discordantes. **No nível B, (b) é indecidível na prática.** O texto já diz o que fazer "com (a) sem (b)": a fila nova vale fora dos tokens de lance. É o resultado esperado, e o plano deve dizê-lo.

**Correção. SPEC:393, inteiro:**

> - **CA-F1.1.** Curva `(m, silencioso @ m)` por token e por classe, com a fila de hoje cortada no mesmo `m`, mais o ponto real da fila de hoje, no `m` dela. Na validação, em `m` = 10 %: **(a)** em Prosa, a nova deixa pelo menos 20 % menos silenciosos, pelo contrato do roadmap, item 6; **(b)** só no nível C de Dec-5, em Lance e em Sinal: limite superior da diferença ≤ +0,5 ponto; **(c)** nenhum livro piora em Lance mais de 1 ponto. **No nível B, (b) não tem poder: a fila nova vale só fora dos tokens de lance.** O ponto de parada de M5 mostra também a troca real: silenciosos na fila nova contra a de hoje no `m` dela.

**ROAD:38:** trocar "CA-F1.1 (a) e (b)" por "CA-F1.1 (a), e (b) se houver prova".

#### I4. O ponto de parada não tem padrão: se o usuário demorar um ano, o plano para em M2

**Onde.** SPEC:16; ROAD:47, :162.

**Problema.** SPEC:16 promete "sem resposta, o plano segue". Isso vale para as Dec. Mas "Pronto quando: [...] o usuário respondeu ao ponto de parada de M2", e o fim curto exige "respondido". As 20 páginas só o usuário faz. Sem elas, PP1b e PPT não têm base, e o fim curto nunca chega.

**Correção. ROAD:29, acrescentar:**

> **Sem resposta:** o passo mescla pelos CA que o agente prova, e o plano segue. Sem a resposta de M2, PP1b e PPT seguem, e a fila Lances fica no F4, sem abrir sozinha, como já é. Sem a de M5, a fila nova fica como opção.

**ROAD:162:** `**Pronto quando:** os CA passam, salvo CA-F4.8 e CA-F4.10, que são do ponto de parada, e CA-F.1 não sobe no portão.`

**ROAD:47:** trocar "com o ponto de parada de M2 respondido" por "com o ponto de parada de M2 respondido, ou registrado como sem resposta".

#### I5. O ponto de parada de PP2 mede um Tesseract que não é o que vai rodar

**Onde.** ROAD:34, :206, :279; SPEC:300.

**Problema.** "Fim de PP2" decide L-2 pela discordância com o Tesseract, na validação. A configuração só se fixa em PP5, item 1 (`--varrer`). A única que os scripts conhecem é `--psm 7`, por linha, e o desenho de L-2 é de página. Decide-se com uma, gasta-se uma leitura da validação, e entrega-se outra.

**Correção. ROAD:206:** `7. Fixar a configuração do Tesseract no ajuste (`medir_motores --motor tesseract --varrer`, a primeira metade de CA-L3.1). Depois, primeira medida completa com ela, **por token e por classe, na validação;** na prova só no nível C de Dec-5.`

**ROAD:279:** `1. **L-3:** a segunda metade de CA-L3.1, na validação, com a configuração de PP2. Dec-2 ao usuário.`

**ROAD:212:** acrescentar `CA-L3.1, a primeira metade`.

#### I6. O título promete o que o plano não entrega, e a spec não diz isso

**Onde.** SPEC:1, §1; ROAD:47.

**Problema.** A §1 define perfeição por "todo caractere, figurina, sinal, posição de diagrama, lado a jogar, função de área e ordem de leitura". O plano: no padrão, nenhum número; diagrama e sinais só em M6 (X-2, X-4), opcional; função e ordem só têm medida (R-1), sem nenhum item que as melhore; "FEN inteiro exato, 30 por livro" não tem passo. A spec é honesta em cada linha e não diz isso em nenhuma. Não mudar o título: é o nome do alvo.

**Correção. SPEC, depois de :26:**

> **O que o plano não promete.** Nenhum marco entrega a página perfeita. O fim curto entrega marcas e a fila Lances, sem número de qualidade e sem melhorar nenhuma leitura. O fim completo entrega uma tabela por livro e consertos medidos. Diagrama e sinais têm só M6, opcional; função de área e ordem de leitura têm medida, sem item que as melhore.

#### I7. F-1 e F-4 mandam contar o F6 de dois jeitos

**Onde.** SPEC:379 × :475. Prova: C4 B6 trocou a regra em F-4, e F-1 ficou.

**Correção. SPEC:379:** trocar "`proxima_com_pendentes` e o contador do escopo livro usam `pendentes ∪ fortes` no modo novo." por "`proxima_com_pendentes` e o contador do escopo livro seguem F-4: só as fortes na página com 2.ª opinião; sem ela, os pendentes."

#### I8. CA-R1.4 está partido ao meio

**Onde.** SPEC:161-165. A correção de C5 M10 entrou entre as duas linhas físicas do item.

**Correção. SPEC:161:** `- **CA-R1.4.** Toda medida grava o commit do programa, o commit e o estado sujo do core, o SHA-256 do modelo, as versões dos motores e o N de cada classe.`
**SPEC:165:** apagar a linha "  dos motores e o N de cada classe."

#### I9. Dec-4 pede um número que só se calcula depois dela

**Onde.** ROAD:48, SPEC:590, SPEC:644.

**Prova.** ROAD: "Dec-4 é perguntada aqui, e só então CA-A5 é feito". Spec, Dec-4: "decidir com o número de A-5 na mão". Spec, A-5: "Catraca [...] agora".

**Correção. ROAD:48:** "CA-A5 é feito aqui, e Dec-4 é perguntada com o número." **SPEC:590:** trocar "Catraca do percentual de palavras iguais agora; o resto é Dec-4" por "Catraca do percentual de palavras iguais, no fim de M5; o resto é Dec-4".

#### I10. "As páginas conferidas ficam corrigidas no projeto" não é verdade pelo mecanismo descrito

**Onde.** SPEC:197 × :203. A verificação é "numa cópia do projeto", e `importar-do-projeto` grava no gabarito. O real não muda. É o argumento de custo de Dec-5 (C4 B2).

**Correção.** SPEC:197: cortar "As páginas conferidas ficam corrigidas no projeto." Trocar por alimentar o projeto real seria item novo.

#### I11. O fim da §5.1 é colagem, e o título mente

**Onde.** SPEC:367, :387-391. "Por isso o CA é por classe:" termina em dois-pontos e vem "**Derruba:**". "Fila por probabilidade de erro", quando o texto diz que probabilidade absoluta não aparece nem decide.

**Correção. SPEC:367:** `### 5.1 F-1. Marcas por escore, dentro de um orçamento (P1, Medido por caractere; por token, exploratório)`

**SPEC:387-391, os três parágrafos, por:**

> **A evidência não é sobre a métrica primária** (relatório, §4): em prosa o ganho é claro; em lance, pode piorar. Por isso o CA é por classe. **Derruba:** CA-F1.1 (a). Qual fila abre: F-4.

(Derruba por (a), e não mais por (b): I3.)

#### I12. A legibilidade da Linha, de que tudo depende, não foi testada

**Onde.** ROAD:147; `app/linha.py:103,115`; `design.md` M2: "a letra é fixa em 12 pt, com caixa ±8 px além do glifo: pode sobrepor". A escala da imagem é `min(altura, largura)`. A viabilidade de PPL, item 0, testa só o editor. Não vi a Linha na tela: as capturas não estão no repositório.

**Correção. ROAD:147, acrescentar:**

> Na mesma meia hora, a 1366 px: uma linha de 70 caracteres com figurinas se lê na Linha, sem letra sobre letra? Se não, o tamanho da letra entra no item 9.

### Menores

| # | Onde | Problema | Correção exata |
|---|---|---|---|
| M1 | ROAD:356 | A-6 saiu de PP2d (C5 §6) | "A-3 está em PP2d. A-6 ao tocar." |
| M2 | SPEC:80 | Figurina sem casa cai em Prosa, contra a tabela da :69 | "- Figurina sem casa: Figurina solta. O resto é Prosa." |
| M3 | SPEC:630 | Toda Dec tem "Recomendo", menos Dec-5 | Acrescentar: "Recomendo B, se a resposta de M2 for sim." |
| M4 | SPEC:424 | "Página da amostra guiada: a de hoje. [...] Sem ela: Confiança." É o mesmo modo | "Página da amostra guiada: Confiança." |
| M5 | SPEC:680 | Definição diferente da :459 | "**Lance conferido:** token de lance com todos os glifos `manual`, `revisado` ou `nativa`." |
| M6 | ROAD:245 | "ganho barato medido": nenhum conserto de PP3 foi medido; a regra medida (`wordfreq`) não está no plano | "Há consertos pequenos, confirmados no código. Nenhum foi medido." |
| M7 | SPEC:260 | "Só leitura: lê, mostra, não grava." antes de "O que grava" | "Em projeto só de leitura: lê, mostra, não grava." |
| M8 | REL:127 | Consenso também ganha do programa no Yusupov | "**O consenso simples fica abaixo do programa nos 5 livros, e abaixo de todos os motores em 4;** no Yusupov, o PP-OCRv6 sozinho ganha por pouco." |
| M9 | SPEC:226, :343 | Hipótese sem Derruba | R-4, acrescentar: "**Derruba:** erro marcado corrigido em até 80 % (roadmap, fim de PP5)." L-8, título: "(P2, a medir)" |
| M10 | ROAD:303 | Dec-3 diz 1 sessão | "**Custo:** 1 sessão." |
| M11 | ROAD:295 | PP6 a PP9 sem Pronto e Carga | Abaixo do título de PP6: "De PP6 a PP9, os campos se escrevem quando o usuário pedir o passo." |
| M12 | REL:54, SPEC:536 | "do meu trabalho de ontem"; "Não confirmei" | "de 04/11"; "Não se confirmou" |
| M13 | SPEC:252 | L-2 "(P1, Medido)", e o desenho de página não foi medido | "(P1, Medido por linha; de página, a medir em CA-L3.1)" |
| M14 | SPEC:635 | B omite a dupla leitura, que entra nas ~10 h | "4 páginas sorteadas de cada um dos 4 livros; a grade da dupla leitura; depois, 1 página por livro de novo, do zero, 7 dias depois" |
| M15 | ROAD:60-63 | `fortes` em `livro.json` não está na tabela de reverter | Linha M2: acrescentar "`fortes`" junto de `lances_por_conferir` |
| M16 | ROAD:31-40 | A tabela de paradas não está em ordem de execução | Pôr "Em PPL, item 4" em primeiro; PP2c sai (corte 19) |
| M17 | SPEC:642 | Dec-2 a "de 3,5 a 15 min" está como certo; é o registro do core | "de 3,5 a 15 min em 300 páginas, a confirmar" |
| M18 | ROAD, todo | PP2d roda antes de PP1 | Trocar `PP2d` por `PPE` (espaço), por substituição em ROAD, e conferir com `c6_matriz.py`. Não renumerar o resto |

## 6. Advogado do diabo

| E se... | O plano ainda presta? |
|---|---|
| **A fila Lances não funcionar** | M1, F-3, X-3 e M3 ficam. **A métrica primária fica sem alavanca até M6,** e hoje isso não está escrito: "Rever antes de M3" não diz nada. Corrigido em B1. Sem CA-F4.10, nem se saberia que não funcionou |
| **O Tesseract de página não servir** | Sim. CA-L3.1 cai na leitura por linha ou em "só em tokens sem forma de lance", e o usuário tem a opção c. Só muda o custo de Dec-2 (M17), e o ponto de PP2 precisa medir o certo (I5). A 2.ª opinião é prosa, de gravidade baixa: perdê-la não ameaça o objetivo |
| **O usuário responder em um ano** | Com I4, sim: M1 a M3 chegam pelos padrões. Sem B2, chegariam sem catraca. **O OCR não melhora nada nesse caminho,** e isso precisa estar escrito (B4, I6). O k-NN, com 52 % dos erros medidos, fica para sempre atrás de Dec-5 B. É coerente com "medir fora do ajuste", e custa caro: se o usuário disser não, o maior erro medido fica |
| **O treino por livro mudar tudo** | Tudo é T0. PP2c só tem o Seirawan, e "PP5 segue" com qualquer resultado. Honesto, mas sem efeito: corte 19 |
| **O título** | Promete mais; a definição é boa como alvo. I6 |
| **O relatório é honesto sobre o que não mediu?** | Sim sobre motores, amostra, gabarito e interface. Faltavam a fila Lances e o modo de página. B4 |
| **Decisão errada que todos aceitaram** | Duas: Enter em Lances como conferência definitiva sem medida (B1), e Enter corrigido sem ensinar (I2). E uma de ordem: catraca depois da decisão de gabarito (B2) |
| **O que está sobrando** | PP2c como trava; §12 repetindo os itens; C-8; a hipótese `tiny`/`small`; os antipadrões repetidos (§4) |

**Verifiquei e está certo, contra o que eu esperava achar:** a estimativa de 10 a 15 linhas (mediana 12); a tabela de intervalos (300, 600, 1.200, 3.000 com DEFF 2); "até 6 tokens" com N = 1.600; 13 de 16 no teste de sinal (p = 0,021; 12 dá 0,077); "PP-OCRv6 ganha em 4 dos 5" em prosa; 13 commits à frente de `passo-i-treino`, sem atraso; `main` local em `867e60d`, atrasado, como o contrato avisa; `MODOS` e o padrão `confianca` não dependem da ordem da tupla (`controladores.py:295`, `espaco.py:87`), logo pôr `lances` à frente não muda a fila que abre.

## 7. Limites

- Os números de I1 e a mediana de B1 são exploratórios: minha aplicação da gramática da crítica 2, não `classificar_token`; `presença` na linha, sem alinhar. Em Aagaard, Nunn e Yusupov a unidade é a página, e I1 não se mede neles.
- A conta de poder em I3 é aproximação minha (pares, DEFF 2, 1,645σ), para dizer a ordem de grandeza.
- 10 minutos em CA-F4.10 supõem 4,5 s por linha, estimativa de C4. O Seirawan já foi visto pelo usuário: o número sai otimista.
- Não vi a janela. Não refiz as somas de C1 nem os 111+ CA um a um contra o código: amostrei.
- As contagens de palavras dos cortes são por linha, com script, e aproximadas onde a frase é parte da linha.

## 8. Veredito final

**APROVADO COM CORREÇÕES.**
O plano é executável e M1 a M3 valem por si; as cinco críticas entraram, salvo os sete pontos marcados na §2.
Falta provar o centro: a fila Lances sem medida de acerto, a catraca atrás de Dec-5, os números por token fora do repositório, e o relatório abrindo com a conclusão antiga.
São 4 bloqueantes de texto, mais copiar dois scripts agora, antes que a sessão acabe; aplicados, sem nova crítica, basta repetir a matriz.
