# Crítica 1 de 6: fidelidade

Documentos: `docs/pesquisa/checkup-2026-11.md` (RELATÓRIO), `docs/SPEC-pagina-perfeita.md` (SPEC), `plans/roadmap-pagina-perfeita.md` (ROADMAP), em `C:\Python-Chess2\AbbyChessCraft-coordenadas`, ramo `checkup-geral`.

**Veredito: reprovado.** 12 bloqueantes, 27 importantes, 12 menores. A aritmética das tabelas confere com o JSON. O que falha é o que o texto diz que os números são.

Prefixos usados nas provas: `motores.json` = `docs/medidas/2026-11-05-motores.json`; `xv.json` = `docs/medidas/2026-11-05-qualidade-xv.json`; scripts em `docs/pesquisa/checkup-2026-11/experimentos/`.

---

## Bloqueantes

### B1. "Pior que o PP-OCRv6 em 3 de 5 livros"

- **Onde:** SPEC §4.3, tabela, linha Tesseract, coluna Contra.
- **Errado:** nenhuma métrica dá 3 de 5.
- **Prova** (`motores.json`, Tesseract contra `paddle`): CER pior em 5 de 5; `cer_lance` pior em 5 de 5; revocação da discordância pior em 5 de 5; `cer_prosa` pior em 4 de 5 (Nunn: 10,00 % contra 14,94 %); precisão pior em 4 de 5 (Nunn: 60,2 % contra 50,9 %); tokens de lance piores em 4 de 5 (Nunn empata em 42).
- **Correção:** "Pior que o PP-OCRv6 em CER nos 5 livros, e em prosa em 4 de 5".

### B2. "A regra foi fixada antes de olhar os livros com figurinas"

- **Onde:** RELATÓRIO §3, "O que isso diz", 2.º item.
- **Errado:** os scripts mostram a regra mudando justamente por causa desses livros.
- **Prova:** `motores_resumo.py`, `fusao_consenso` (Seirawan): sem proteção de figurina. `motores2_resumo.py`, `consenso` (livros com figurinas): protege só o caractere, com o comentário "figurina do programa nunca é trocada: os outros não têm a classe". `final_resumo.py`, `consenso`: protege o token inteiro, e a discordância também passa a excluir esses tokens ("os outros motores não têm a classe e sempre discordam"). `final_resumo.py` faz `exec` de `motores2_resumo.py` e lê `motores3.json`, gerado a partir de `motores2.json`: é posterior. O terceiro motor também trocou: `consenso_pte` existe no JSON e não aparece no texto; com ele, os tokens de lance errados sobem para 38 de 554, contra 35 do programa.
- **Correção:** "A regra base veio do Seirawan. A proteção de figurina foi acrescentada e ampliada depois de ver os livros com figurinas, e a tabela mostra só a variante com o PP-OCRv6; com o EasyOCR no lugar dele, são 38 tokens errados. Esta medida não é cega. Só a avaliação da §3.2 da SPEC, em páginas novas, pode confirmá-la."

### B3. "Das 819 edições, no máximo 22 mexeram em caractere certo"

- **Onde:** RELATÓRIO §3; SPEC §4.4 ("no máximo 22") e §10, Dec-3 ("22 de 819").
- **Errado:** 22 não é teto.
- **Prova:** `consenso_efeito.py`, `for op, a, b in mud: if a is not None and a in certo`. Inserções do consenso têm `a = None` e nunca contam. Soma de `mudou` = 819, de `criou` = 22, de `tirou` = 756. Logo 63 edições não reduziram o erro em conta líquida. Por livro: Nunn 56 mudadas e 20 tiradas; Seirawan 298 e 277; Yusupov 182 e 176. Supondo que cada edição mude a distância em +1, 0 ou −1, as que pioraram podem chegar a 31 (10 + 18 + 3).
- **Correção:** "Das 819 edições, 756 reduziram o erro em conta líquida. O contador acha 22 sobre caractere certo, 14 delas na tabela do Nunn, mas não vê inserção errada; pela conta líquida, até 31 pioraram. No Nunn, só 20 das 56 edições ajudaram." Em Dec-3: "22 a 31 de 819".

### B4. A "prosa" não conta sobras, e o texto não diz

- **Onde:** RELATÓRIO §1 item 2, §3 (tabela por classe, "os outros erram de 2 a 3 vezes menos"); SPEC §1 (alvo 2,34 %).
- **Errado:** o relatório define CER como distância de edição, e a linha Prosa é outra conta. Lance também não conta sobras.
- **Prova:** `final_resumo.py`, `medir`: `cer_prosa = (e - el - sob) / (n - tl)`, `cer_lance = el / tl`. Nos 4 livros, o JSON tem 331 sobras do programa, 566 do Tesseract, 59 do PP-OCRv6 e 217 do consenso. Com `tl` ≈ 3.415 deduzido do próprio JSON e todas as sobras na prosa (teto), programa 10,1 %, Tesseract 9,7 %, consenso 4,8 %, PP-OCRv6 2,8 %. A faixa real do Tesseract é 3,16 % a 9,65 %: "2 a 3 vezes menos" só se sustenta no piso. No Yusupov, com o teto, o Tesseract (26,4 %) fica pior que o programa (17,7 %).
- **Correção:** renomear a linha para "Prosa: trocas e faltas fora dos tokens de lance, sem sobras". Acrescentar a linha "Sobras, sem classe: 331 / 59 / 566 / 217". Trocar a frase por: "Sem contar sobras, os outros erram de 2 a 3 vezes menos em prosa. As sobras não têm classe: se todas fossem de prosa, o PP-OCRv6 manteria a vantagem (2,8 % contra 10,1 %), e o Tesseract não (9,7 %)." No §1 item 2, acrescentar "sem contar sobras".

### B5. "Erros silenciosos: 32 de 199 (16,1 %); 2 em lance"

- **Onde:** RELATÓRIO §4, tabela; SPEC §5.1 ("16,1 % dos erros silenciosos").
- **Errado:** a SPEC define erro silencioso como errado e sem nenhum sinal na tela, e diz que é a métrica primária. A conta deixa as faltas de fora.
- **Prova:** `motores.json`, `pericia_seirawan`: "faltas (char não lido; a fila não tem como ver): 74 em lance 14"; "em lance: 11 silenciosos 2". Com as faltas: (32 + 74) / (199 + 74) = 38,8 %; em lance, (2 + 14) / (11 + 14) = 64 %. Ressalva: `perita_ocr.py` filtra `if b.char`, então parte das faltas pode cair sobre um box vazio visível, e isso não foi cruzado.
- **Correção:** "32 de 199 boxes lidos com erro (16,1 %); 2 em lance. Fora da conta: 74 faltas, 14 em lance, que a fila não vê. Com elas, até 106 de 273 (38,8 %) e até 16 de 25 em lance (64 %); não se cruzou quantas caem sobre box vazio visível." Na SPEC §5.1, a mesma ressalva.

### B6. "A cadeia do core é pior em lances"

- **Onde:** RELATÓRIO §3 ("mas é pior em lances"); SPEC §4.3, linha Cadeia do core ("pior em lance").
- **Errado:** não foi medido.
- **Prova:** `e0_resumo.py` calcula só troca, falta e sobra do texto corrido por página. `core_livro_e0_seirawan.resumo` no JSON tem 4 linhas, sem classe. A busca por "pior em lance" só acha estas duas frases. `motores.md:333` pedia separar prosa e lance; isso não foi feito.
- **Correção:** "Não foi medida em lances: o E0 só compara texto corrido." Tirar "pior em lance" da coluna Contra.

### B7. "18 páginas lidas"

- **Onde:** RELATÓRIO §1, "Limite de tudo".
- **Errado:** a soma dá 17 nos motores, ou 19 contando a medida do programa.
- **Prova:** Seirawan 7 (`xv.json`, `linhas_verificadas` de i020 a i026 somam 213), Aagaard 1, Nunn 1, Yusupov 2 (`corpus_v2.json`), Dvoretsky 6 (`PAG_DVORETSKY`) = 17. `xv.json` lê também i000 e i007 só no programa = 19.
- **Correção:** "5 livros, 17 páginas lidas por todos os motores".

### B8. "Margens com precisão de 0,64" como sintoma solto

- **Onde:** RELATÓRIO §4, "Três sintomas soltos".
- **Errado:** é o mesmo sintoma da capa.
- **Prova:** `xv.json`: i000 tem `margens: {vp: 0, fp: 4}`. As outras páginas têm `fp: 0`, com vp 7. 7 / 11 = 0,6364. Sem a capa, a precisão é 1,0. O `diagramas_falsos: 1` também é de i000.
- **Correção:** apagar o item, e no da capa acrescentar: "Ela também é a origem de toda a queda de precisão das margens (0,64; sem ela, 1,0) e do único diagrama falso". Título: "Dois sintomas".

### B9. "Todos sem treino" e "Nenhum motor foi treinado"

- **Onde:** RELATÓRIO §1 item 2, §3 (abertura e 2.ª ressalva).
- **Errado:** o programa usa uma CNN e uma base já treinadas em livros de xadrez. Os outros usam modelo de fábrica. Não é a mesma condição.
- **Prova:** `relatorio_treino.txt` do core: "treino 500961"; `model_meta.json`: 314 classes; `core/avaliacao.py:52` sem grupo por livro; a pasta `Box` do core tem outros livros do Aagaard. Não se verificou se os 5 livros testados estão no treino. A própria SPEC §4.8 reconhece que o holdout não separa por livro.
- **Correção:** "Sem treino neste livro: o programa com a CNN e a base globais, treinadas em livros de xadrez (500.961 amostras), sem saber se estes livros estão entre elas; os outros com modelo de fábrica. A vantagem do programa em figurina pode conter treino sobre o mesmo material." No §1 item 2: "Um OCR de linha, com modelo de fábrica".

### B10. "E nenhum sinal na tela"

- **Onde:** ROADMAP, passo PP7, Contexto ("35 tokens errados em 554 [...] e nenhum sinal na tela").
- **Errado:** falso como está escrito.
- **Prova:** perícia: 9 dos 11 erros de lance com box estão na fila (Seirawan). A fila dos livros com figurinas não foi medida. A própria SPEC §5.3 limita o caso a lance "bem formado e errado com confiança alta".
- **Correção:** "Hoje: 35 tokens errados em 554, nos livros com figurinas, sem saber quantos vão à fila. Lance bem formado com confiança alta não tem sinal nenhum (F-3)."

### B11. "Realçar pouco funciona melhor"

- **Onde:** RELATÓRIO §6.
- **Errado:** omite o resultado principal do mesmo estudo, e compara unidades diferentes.
- **Prova:** `estado-da-arte.md:255`: redução de WER de 0,47, 0,48 e 0,45 nas três condições, "sem diferença significativa (p = 0,767)"; `:24`: "o realce por confiança não alterou a redução de erro". O número 2,64 é a chance de corrigir o erro realçado (`:166`). `:166` diz "deixou de ser significativa", e não "sem efeito". O estudo mede percentual de palavras; os 18 % da fila são de boxes.
- **Correção:** "Realçar não reduziu o erro final no único estudo achado (fala, não OCR, 36 pessoas; p = 0,767). A chance de corrigir o erro realçado foi 2,64 com 4 % das palavras marcadas, e deixou de ser significativa com 13 a 21 %. A fila de hoje marca 18 % dos boxes; não se mediu em palavras."

### B12. A marca "Medido" não cumpre a própria definição

- **Onde:** RELATÓRIO, "Marcas": "rodei e o número está no JSON citado"; §2, §4.
- **Errado:** vários números não estão em arquivo nenhum do repositório.
- **Prova:** busca nos JSON e em `docs/`: "2.429 passaram, 3 pularam", "99 s", "64 s", "40 passaram", "250 s" (`qualidade/2026-11-05-qualidade.json` só tem `camadas: {rapida: 0, processo: 0}`); "16:28" e "34 de 34" não estão no `2026-11-05-medida.json`, que traz `exitstatus: 0` (34 de 34 está na mensagem do commit `262d897`); "64 linhas [...] 2 erradas", "2,04 %", "6 das 75", "altura mediana de 20 px" e `in1n1cdiatc` não estão no `motores.json`, embora os scripts que os imprimem existam (`motores_resumo.py`, `diag_um.py`). Os `motores*.json` de entrada não estão no repositório, então os resumos não se refazem sem novo OCR.
- **Correção:** gravar esses números no JSON antes de publicar, ou marcá-los: "**Medido, sem registro**: rodei, li a saída, e o número não ficou em arquivo."

---

## Importantes

### I1. Discordância e fila têm bases diferentes, além da unidade

- **Onde:** RELATÓRIO §4, nota da tabela; ROADMAP PP5; SPEC §4.3.
- **Errado:** o texto só admite "por box × por caractere". A revocação não conta faltas (`op in ("troca", "sobra")`), e a base da fila é 199, contra 246 da discordância com o PP-OCRv6, de 331 erros.
- **Prova:** `motores.json`: `erros: 246, pegos: 242`; `ops: troca 223, falta 80, sobra 28`.
- **Correção:** "Nenhuma das linhas conta as faltas (80 dos 331 erros do Seirawan). Sobre os 331, a fila pega uns 167 (50 %), o PP-OCRv6 242 (73 %) e o Tesseract 234 (71 %). A ordem se mantém, com distância menor." No ROADMAP: "pega 73 % de todos os erros, ou 98,4 % das trocas e sobras, contra cerca de 50 % da fila".

### I2. A discordância é cega para o token com figurina, por construção

- **Onde:** RELATÓRIO §4; SPEC §5.1 ("Discordância é a variável principal"); ROADMAP PP5.
- **Errado:** a ressalva é um parêntese ("token com figurina fora"), sem a consequência: em livro com figurinas, a classe de gravidade máxima não recebe marca dela.
- **Prova:** `final_resumo.py`, `discordancia`: `dif = {... and not prot[a]}`. Não há recorte por lance.
- **Correção:** acrescentar em ambos: "Em livro com figurinas, a discordância não marca nenhum token com figurina. A revocação dela em lance não foi medida."

### I3. "Os erros quase não coincidem", "muito melhor", "barata"

- **Onde:** RELATÓRIO §1 item 3.
- **Errado:** vale no Seirawan e não se generaliza. A comparação com a confiança só existe nele. "Barata" contradiz §7 e a SPEC.
- **Prova:** Nunn: revocação 58,2 % e 52,7 %. Dvoretsky: 75 % e 68,2 %. 4 livros: 81,1 % e 74,4 %. Custo: 22 a 58 minutos sobre 48 (+46 % a +121 %), sem integrar; ROADMAP PP5: "Custo: grande".
- **Correção:** "No Seirawan, os erros quase não coincidem, e a discordância marca menos e pega mais que a fila. Nos livros com figurinas, varia: com o PP-OCRv6, 96,5 % no Aagaard, 83,2 % no Yusupov, 75 % no Dvoretsky e 58,2 % no Nunn. A fila não foi medida neles. O custo é de 22 a 60 minutos a mais em 300 páginas, sem integrar."

### I4. "O programa é quase perfeito em figurina" e "a razão das 489"

- **Onde:** RELATÓRIO §3; SPEC §11 ("Ela é a razão das 489 figurinas certas em 498").
- **Errado:** 46 % das figurinas vêm do Dvoretsky limpo. A fonte de cada figurina não foi medida, então "a razão" é inferência. `limpar` funde a cor (`PRETA`): figurina de cor errada não conta. Figurina inventada também não conta (`classes` só olha a verdade).
- **Prova:** `figurina`: Aagaard 1 de 64, Nunn 8 de 73, Yusupov 0 de 133, Dvoretsky 0 de 228. Escaneados: 9 de 270 (3,3 %); Nunn, 11 %.
- **Correção:** "Figurinas erradas: 9 de 498, sem contar cor; 9 de 270 nos escaneados, 8 delas na tabela do Nunn; 0 de 228 no digital." Na SPEC: "Inferido: a rede deve ser a razão; a fonte de cada figurina não foi medida."

### I5. O agregado de lances esconde o único livro verificado

- **Onde:** RELATÓRIO §1 item 2, §3; ROADMAP PP7; SPEC §6.1.
- **Errado:** "o programa vence [...] lances" vale só na notação com figurina. No Seirawan, o programa perde. E o Dvoretsky pesa 53 % dos 554 tokens.
- **Prova:** Seirawan: programa 26 de 135 (19,3 %), PP-OCRv6 8 de 135, consenso 11 de 135; `cer_lance` 4,99 % contra 1,66 %. Escaneados com figurinas: 28 de 260 (10,8 %). Digital: 7 de 294 (2,4 %).
- **Correção:** acrescentar no §3: "Em notação com letras (Seirawan), o programa perde em lance: 26 tokens errados em 135, contra 8 do PP-OCRv6, que também ganha do consenso (11). Nos escaneados com figurinas, 28 em 260; no digital, 7 em 294."

### I6. "Tokens de lance errados" é um piso, e há três definições de lance

- **Onde:** RELATÓRIO §3, §4; SPEC §6.1.
- **Errado:** a conta é por presença em saco, e na página inteira nos escaneados. Um token errado conta como certo se o mesmo texto existir em outro ponto da página. O texto não diz.
- **Prova:** `final_resumo.py`: `lidos = p.split(); if tk not in lidos`. As unidades escaneadas são páginas (`motores2.py`). Três réguas: `TOKEN_LANCE` (`marca`, para o CER de lance), `SAN` (tokens) e `LANCE` (`perita_ocr.py`, para "2 em lance"). `motores.json` dá `cer_lance` 4,99 % e, na perícia, 4,38 % para o mesmo livro.
- **Correção:** nota sob a tabela: "Tokens contados por presença na unidade, sem posição: é um piso nos escaneados, onde a unidade é a página. 'Lance' tem três regras nestes scripts: `marca` no CER, `SAN` nos tokens, `LANCE` na perícia."

### I7. "A fila de revisão [está] acima da média" e "só mudaram de arquivo"

- **Onde:** RELATÓRIO §1, 1.º parágrafo.
- **Errado:** a primeira não tem comparação e contradiz §4 (9 em cada 10 paradas sem erro) e "O realce saturou". A segunda ignora o ganho medido.
- **Prova:** `arquitetura.md:32-33`: funções com cc ≥ 10, de 251 para 5; maior cc, de 62 para 15, "ganho real". "Acoplamento dobrou" é só o contador de privados (115 → 230).
- **Correção:** "Gravação, migração e testes de comportamento estão bons; a fila tem bom fluxo de gestos e sinal fraco (§4). O controlador e a janela perderam complexidade por função (cc ≥ 10, de 251 para 5), mas o acesso a privados entre objetos dobrou."

### I8. "Nada usa o contexto para decidir"

- **Onde:** RELATÓRIO §1 item 1.
- **Errado:** há decisão por contexto.
- **Prova:** `motores.md:26`: "As únicas trocas automáticas de caractere são a caixa pela altura (`abby/montagem.py:388-406`) e o reler pelo efeito". `:135`: "troca sozinho".
- **Correção:** "Fora a caixa pela altura e o reler pelo efeito, nada usa o contexto para decidir."

### I9. Marcas de evidência que divergem entre os documentos

- **Onde:** SPEC §3.3 "(P1, Confirmado)" e "tudo segue verde", contra RELATÓRIO §1 item 4 "(**Inferido**)". SPEC §7.2 "(P1 e P2, Confirmado)" inclui C-1, contra RELATÓRIO D/C "Inferido" e §7 "C-1 não foi reproduzido".
- **Prova:** `testes.md:91-102` é raciocínio, sem execução. `servidor_de_leitura.py:413-419` e `_receber` confirmam a ausência do vigia, não o órfão.
- **Correção:** SPEC §3.3: "(P1, Inferido da leitura dos testes)". SPEC §7.2: marcar "C-1: Inferido".

### I10. "O gabarito verificado cobre um livro só" e "135 tokens"

- **Onde:** RELATÓRIO §1 item 4; SPEC §1 e §3.2.
- **Errado:** vale para `tests/verdade`. O próprio §3 usa referência revisada por humano em outros 3 livros, e a SPEC §3.2 a põe no nível G1.
- **Prova:** `corpus_v2.json`: `ground_truth_policy: human-reviewed-text`, `annotation_status: reviewed`, 4 páginas, 260 tokens de lance e 270 figurinas. Somadas: 395 tokens.
- **Correção:** "`tests/verdade` tem 213 linhas de um livro, sem figurinas (135 tokens de lance). O `corpus_v2` do core soma 4 páginas revisadas (260 tokens, 270 figurinas). Juntos, 395 tokens: com zero erro, isso só sustenta menos de 0,8 %."

### I11. Os alvos da §1 misturam linha de base e conjunto

- **Onde:** SPEC §1, Alvos.
- **Errado:** "Valem para o conjunto de avaliação", mas as linhas de base 2,34 %, 18 %, 9,3 %, 7 de 7 e 2 de 5 são do Seirawan, que é conjunto de ajuste. "Livro bom" não está definido. "Baseadas no que o consenso já mediu" só vale em dois livros.
- **Prova:** prosa do consenso: Seirawan 0,21 %, Dvoretsky 0,52 %, Aagaard 1,09 %, Yusupov 3,72 %, Nunn 9,75 %. Marca do PP-OCRv6: Aagaard 11,3 %, Nunn 13,7 %, Yusupov 10,3 %, contra o alvo de ≤ 5 %. Pela regra de 3/N da própria seção, ≤ 0,5 % com N = 600 e ≥ 98 % com N = 150 só fecham com zero erro: com um erro em 600, o limite de 95 % sobe para cerca de 0,8 %.
- **Correção:** coluna "Linha de base (Seirawan, ajuste)"; acrescentar "A linha de base da avaliação sai da primeira medida de PP2". Definir "livro bom" ou trocar por "Seirawan". Nos dois alvos: "com N ≥ 600 e zero erro".

### I12. CA-L4.3 reprova a regra que a SPEC recomenda

- **Onde:** SPEC §4.4, CA-L4.3 ("abaixo de 0,5 % das edições") contra Dec-3 ("pouco").
- **Prova:** medido: 22 de 819 = 2,7 %; Seirawan 1,7 %; Nunn 25 %.
- **Correção:** registrar junto do CA: "Hoje a regra mede 2,7 %, e até 3,8 % pela conta líquida, nos livros já vistos: ela não passa neste corte sem mudar." E em Dec-3, dizer isso.

### I13. O número medido não é da regra especificada

- **Onde:** SPEC §4.4, "Regra medida" contra CA-L4.2 ("Nenhum token com figurina nem lance de forma válida muda").
- **Errado:** a regra medida protege só token com figurina. Lance em letras mudou: no Seirawan, tokens errados de 26 para 11. Além disso, a medida usa exatamente dois votos (T e PP), e Dec-2 recomenda Tesseract como padrão, com PP-OCRv6 opcional.
- **Correção:** "Regra medida: com T e PP-OCRv6, token com figurina não muda. Os 819 e os 22 são dessa regra; a de CA-L4.2 é mais restrita e não foi medida. Com o Tesseract sozinho, não há consenso."

### I14. A SPEC alinha por token, e a medida é por caractere

- **Onde:** SPEC §4.2 ("com o token como unidade") e §4.3 ("98,4 % e 88,3 %").
- **Prova:** `final_resumo.py`, `discordancia`, usa `ops` por caractere.
- **Correção:** "Os 98,4 % e 88,3 % são por caractere. Por token, a fração marcada é maior; não foi medida."

### I15. E0: as 342 sobras sumiram, e a SPEC cita o número nu

- **Onde:** RELATÓRIO §3; SPEC §4.3 ("0,97 % no Seirawan"), na mesma leitura do CER 0,74 %.
- **Errado:** é outra conta: sem sobras, por página, com hifenização desfeita. O core tem 342 sobras contra 32 do programa, e o Tesseract sozinho dá 1,09 % na mesma régua.
- **Prova:** `core_livro_e0_seirawan.resumo`. A nota do JSON atribui as sobras às linhas não verificadas; isso não foi separado.
- **Correção:** RELATÓRIO: "0,97 % contra 2,43 % do programa e 1,09 % do Tesseract sozinho, contando trocas e faltas por página. O core tem 342 sobras, contra 32, e não se separou quantas são das linhas não verificadas." SPEC: "0,97 % sem sobras, régua do E0; não comparar com as outras linhas".

### I16. "O core tem `pagina_de_imagem`"

- **Onde:** SPEC §4.9.
- **Errado:** sugere um classificador pronto. É um campo que `core.livro` liga depois de segmentar, só quando não há nenhum box nem tabuleiro.
- **Prova:** `core/pagina.py:237`; `core/livro.py:3876-3882` (`if not boxes and not tabuleiros`). A capa dá 5.429 pendentes no app. Não rodei a segmentação do core nela.
- **Correção:** "`core.livro` marca `pagina_de_imagem` só quando a segmentação não acha box nem tabuleiro; não há classificador para reaproveitar, e o app não usa o campo."

### I17. "Os modelos de fábrica não os têm"

- **Onde:** SPEC §6.4.
- **Errado:** absoluto, ambíguo logo antes de falar da CNN, e a CNN tem as classes.
- **Prova:** `model_meta.json`: `±`, `∓`, `⩲`, `⩱`, `!!`, `??`, `!?`, `?!` são classes. A fonte diz "que eu tenha podido confirmar" (`estado-da-arte.md:215`). Símbolos errados nos 4 livros: programa 15 de 247; PP-OCRv6 45; Tesseract 55. Confere: `⨁ ⇆ ⟫` fora das classes.
- **Correção:** "A CNN tem as classes (`±`, `⩲`, `!!`...), e parte delas fica sem validação. Não confirmei amostra nos modelos de fábrica dos outros motores, que erram de 3 a 4 vezes mais em símbolo (45 e 55 contra 15, em 247)."

### I18. "Não instala fora deste PC"

- **Onde:** RELATÓRIO E-1; SPEC §7.3 (Confirmado).
- **Errado:** não foi tentado. O que o código mostra é outra coisa.
- **Prova:** `pyproject.toml` não declara `chess` nem `torch`, e `abbychess/lances.py` importa `chess`: um `pip install` deve concluir e falhar ao rodar. No core, `torch` é extra (`ml`). `pyvenv.cfg`: `include-system-site-packages = true`.
- **Correção:** "Instalado num ambiente limpo, não deve rodar: faltam `chess` e `torch`. Inferido: não tentei."

### I19. "Nada moderno a usa"

- **Onde:** RELATÓRIO §6.
- **Prova:** `estado-da-arte.md:21`: "[?] Não achei nenhum trabalho moderno".
- **Correção:** "Não achei trabalho moderno que a use dentro da decodificação em livro impresso."

### I20. "Treinar pesa mais que a arquitetura"

- **Onde:** RELATÓRIO §6.
- **Prova:** `estado-da-arte.md:19`: "No único estudo que achei", com grego e árabe, Kraken treinado.
- **Correção:** "No único estudo achado com os dois lado a lado (grego e árabe), o treino no domínio pesou mais que a arquitetura."

### I21. "A temperatura não reordena a fila"

- **Onde:** RELATÓRIO §6.
- **Errado:** perdeu o qualificador, e a fila daqui mistura fontes.
- **Prova:** `estado-da-arte.md:158`: "não reordena a fila dentro de um mesmo modelo [...] Conclusão minha". A própria perícia mostra ECE de 0,391 e 0,008 em escalas diferentes.
- **Correção:** "A temperatura não reordena dentro de um mesmo modelo (conclusão minha). A fila daqui mistura rede e k-NN: calibrar cada fonte muda a ordem entre elas, não dentro."

### I22. Reading or Guessing fora do contexto

- **Onde:** SPEC §11, "Gramática dura na saída".
- **Prova:** `estado-da-arte.md:97`: a máscara de escrita é de VLM, "no grego", e "desaconselha importar sem medir". A SPEC omite as duas coisas.
- **Correção:** "Gramática dura na saída de VLM. Em [Reading or Guessing?, 2026], a máscara de escrita piorou o CER em até 74,7 pontos no grego. Não mede gramática de lance."

### I23. "Não pode criar erro"

- **Onde:** ROADMAP, "Por que essa ordem" e PP5.
- **Errado:** não muda caractere, mas a métrica primária é o erro silencioso. Passar de 18 % para ≤ 5 % das marcas tira da fila erros que hoje estão nela.
- **Correção:** "Não muda nenhum caractere. Pode criar erro silencioso, se a fila nova perder o que a de hoje pega: é o que CA-F1.1 vigia."

### I24. O conjunto de avaliação já foi visto, e a SPEC o usa para escolher

- **Onde:** SPEC §3.2, Princípio 4, §13 ("Avaliação nunca decide parâmetro"), contra CA-L3.1 ("A escolha sai do conjunto de avaliação"), §12 ("decide antes de L-3 e F-1") e CA-R2.1 (ajuste permitido com `--avaliacao`).
- **Errado:** Aagaard, Nunn e Yusupov já informaram a regra do consenso (B2) e a escolha de motor.
- **Correção:** §3.2: "As páginas de Aagaard, Nunn e Yusupov usadas em 05/11 saem da avaliação, ou ficam marcadas como vistas." CA-L3.1: "A escolha sai do ajuste e é confirmada, com N, na avaliação." CA-R2.1: "`medir_motores` recusa ajustar sobre a avaliação."

### I25. L-6f não é "léxico" do projeto

- **Onde:** RELATÓRIO §4; SPEC §4.6, L-6f ("pelo léxico", `contexto.py`).
- **Prova:** `motores_resumo.py`: `from wordfreq import zipf_frequency`, em `pt`, sobre as linhas do Seirawan. `abbychess/` não usa `wordfreq`, nem o `pyproject.toml` o declara. O léxico do projeto é `core.lexico`.
- **Correção:** "Regra com `wordfreq`, medida só no Seirawan: 2,76 % → 2,04 %, com 6 de 75 linhas piores. Não foi medida com `core.lexico`."

### I26. A SPEC descumpre a própria §0

- **Onde:** SPEC §0 ("Item com hipótese traz o que a derruba"; "Cada item tem um critério").
- **Prova:** X-2, X-4, X-5 e a hipótese `tiny`/`small` de L-3 são hipóteses sem "Derruba". A-7, U-11, U-12 e U-13 têm CA "—".
- **Correção:** escrever o que derruba em cada um, ou mudar a §0 para "quando couber", e listar as exceções.

### I27. "Três confusões [...] todas dentro de palavra"

- **Onde:** RELATÓRIO §4.
- **Errado:** nenhum script mede a posição na palavra. Em português, `o` é palavra inteira, e `0→o` pode ser o artigo.
- **Prova:** `perita_resumo.py` só faz `Counter((r["p"], r["t"]))`. A conta dos 46 % confere: 103 / 223.
- **Correção:** "Três confusões fazem 46 % das trocas: `1→l` (58), `0→o` (37), `9→g` (8). Não se mediu quantas ficam dentro de palavra."

---

## Menores

| # | Onde | Problema e prova | Correção |
|---|---|---|---|
| M1 | RELATÓRIO §4; SPEC §3.3, §4.9 "(Medido)"; ROADMAP PP3 | "6 minutos" é subtração entre rodadas: 452,5 − 67 = 385 s, para 2 páginas (capa e i007). O relatório diz "pela conta"; os outros não | SPEC e ROADMAP: "uns 6 minutos, pela conta" |
| M2 | RELATÓRIO §2 | "Commit medido: `262d897`", e o portão é do `8f8eccf` (`ambiente.commit`). "CA-7.1 aprovado" é mediana de 2.380 ms contra corte de 2.400 (`_portao`, alvo × 1,2) | "No `8f8eccf`. CA-7.1 aprovado por 20 ms" |
| M3 | RELATÓRIO §2 contra ROADMAP PP0 | "Antes de corrigir o primeiro" não faz a medida passar: são 2 pares fora da lista | "Antes de corrigir os dois" |
| M4 | ROADMAP, Contrato | "Mais três regras", seguido de 7 itens | "Numa lista só:" |
| M5 | ROADMAP, Ordem | E-6 em PP5 e T3; U-12 em T1 e X-3 em PP7; "R-1..3, E-5, catraca" repete R-3 | Um lugar para cada |
| M6 | SPEC §3.2, Dec-5 | 20 páginas por livro não dá 600 tokens: Yusupov tem 71 por página, Aagaard 74, Nunn 44; 3 livros dão mais de 3.000 | "Pelo menos 600 tokens" |
| M7 | SPEC §1 | "Abaixo de 2 %": 3/135 = 2,2 % | "Abaixo de 2,2 %" |
| M8 | SPEC CA-L9.2; §2 item 7 | "Três livros" não está definido. `carga-pesada-trava-o-pc` é nota de memória, sem arquivo no repositório | "Xv, Darcy e Yusupov"; descrever a regra |
| M9 | SPEC §3.1 | "`medir.py` só dá CER do corpo": `xv.json` traz funções, margens, diagramas, FEN e lado | "Em texto, só dá o CER do corpo" |
| M10 | SPEC §4.2 | "2 GB" é RSS (`psutil`), e não pico. "60" são 58,2. "Não se empilha" é falso em tempo: T + PP somam ~80 min | "2 GB de RSS, sem pico medido"; "Não rodam juntos; o tempo soma" |
| M11 | SPEC §4.3, EasyOCR | "Pior nos dois eixos": eixos indefinidos; ganha do Tesseract no Yusupov, e empata nos 4 livros em discordância (74,0 % e 72,0 % contra 74,4 % e 72,7 %) | "Pior que o PP-OCRv6 em CER nos 5 livros" |
| M12 | SPEC §7.1, D-4; RELATÓRIO D-4 | "Sem aviso" contra "só registra `warning`"; "sai do OCR" só vale quando os boxes vieram do OCR (`nativo.importar` também grava boxes) | "Só um `warning` no log"; "Sai dos boxes" |

---

## O que conferi e o que não conferi

**Conferi cerca de 130 alegações.** Todos os números das tabelas do §2 com arquivo, §3 e §4 do relatório, os alvos, os custos e as somas pedidas (819, 22, 489 de 498, 11,5 %, 52 %, 46 %, 22 e 60 minutos, 6 minutos, 135, 5 livros), refeitos com Python sobre os JSON. Métricas lidas nos scripts: `consenso`, `discordancia`, `medir`, `marca`, `perita`, `e0_resumo`, `consenso_efeito`. No código, com `arquivo:linha`: D-1 a D-4, C-1, C-2, E-1, E-3 (com `gh`: repositório `PUBLIC`), F-3, L-1, L-6a a L-6e, L-9, U-1, U-8, U-11 (F5), X-2, X-4, L-8, A-3, A-6, os três "a classe não cresce", contrastes de F-2 e U-7, módulos, linhas e janela. Citações de `estado-da-arte.md` usadas nos três documentos.

**Não conferi:**
- A-2 (230 e 169) e o ciclo de 16 módulos, sem recontar. Imports tardios: contei 183, contra 185 do texto, por outro critério. Por contagens próprias, A-6 deu 94 chamadas, contra 95, e as linhas deram 41.717, contra 41.713; não relato como erro.
- A interface na tela: 1.047 boxes, 22 %, quebra a 1366 px. Não há captura no repositório; só 207 confere (`xv.json`, i025).
- As reproduções em pasta temporária de D-1 e a suíte: nada foi rodado.
- 2.429, 40 passaram, 250 s, 16:28: sem fonte (B12).
- U-2 a U-7, U-9, U-10, C-3, C-4, C-6 a C-8, E-2, E-4 a E-6, A-4, A-5, A-7: só contra os relatórios, sem o código.
- As fontes externas no original.
