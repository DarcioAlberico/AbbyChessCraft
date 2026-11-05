# Crítica 2 de 6: método de medida

Revisão de `docs/SPEC-pagina-perfeita.md` v0.1, `plans/roadmap-pagina-perfeita.md` e `docs/pesquisa/checkup-2026-11.md`, ramo `checkup-geral`.

**O que rodei.** Nenhum OCR, nenhum pytest, nenhuma edição. Refiz contas sobre as saídas que já existem (`motores3.json`, `motores-xv-p.json`, `perita-xv.json`, `2026-11-05-motores.json`) e renderizei 18 recortes de linha para conferir o gabarito contra a imagem. Os scripts são `c2_a.py` a `c2_f.py`, nesta mesma pasta.

**Limite dos números novos.** São exploratórios: minha gramática de token, um alinhamento só, sobre o conjunto de ajuste, antes de corrigir o gabarito. Nas 4 páginas escaneadas a unidade é a página. Servem para derrubar afirmações e dimensionar a medida. Não entram em tabela como resultado.

## Veredito

A régua proposta tem a forma certa e ainda não mede. Quatro defeitos invalidam o que ela produziria:

1. **O gabarito tem erro provado na mesma ordem do alvo.** Achei 8 erros em 2.077 tokens "verificados", em 14 olhadas.
2. **"Erro silencioso" muda de valor conforme a unidade.** A fila marca 18 % dos boxes, que são 58,7 % dos tokens.
3. **Os alvos não se decidem com o N pedido.** Com "zero erro em 600", um sistema cinco vezes melhor que o alvo reprova em 45 % das vezes.
4. **O centro do roadmap não tem evidência na métrica primária.** A discordância por token pega de 31 % a 65 % dos lances errados, e não os 98,4 % citados, que são por caractere e sobretudo de prosa.

| Severidade | Achados |
|---|---|
| **Bloqueante** | B1 a B7 |
| **Importante** | I1 a I8 |
| **Menor** | M1 a M5 |

---

## Bloqueantes

### B1. O gabarito herda os erros do programa, e a conferência cega nunca rodou

**Onde.** SPEC §3.2 (R-2), `docs/protocolo-rotulagem.md` etapas 3 e 4, `docs/SPEC.md` §15.2.

**Problema.** O texto do gabarito começa como a leitura do programa, e o usuário o corrige. O erro plausível que o revisor não vê fica nos dois lados e conta como acerto. É exatamente o erro que a métrica primária quer contar. A conferência cega é obrigatória desde a §15.2, mas o campo `conferencia_cega` está vazio nos 14 gabaritos, tanto em texto quanto em diagrama.

**Por que importa: medi.** Auditei as linhas do Seirawan em que o programa concorda com o gabarito e algum motor discorda: 13 tokens de prosa, mais 1 da lista por caractere, 14 olhadas no total. **8 são erro do gabarito, contra a imagem** (apêndice A). Os outros 6: 2 de falta vizinha, 2 de recorte com tabuleiro, 1 tipográfico (`—` × `–`) e 1 não esclarecido.

- 8 em 2.077 tokens é **0,39 %, IC 95 % de 0,17 % a 0,76 %**, e é um piso: não cobre o que os três motores erram igual, nem os lances. **O ruído do gabarito é do tamanho do alvo de 0,5 %.**
- São até 8 das 213 linhas "verificadas" (3,8 %).
- O erro corre sempre a favor do programa. Refeita a conta, o CER do Seirawan passa de 2,76 % para cerca de 2,82 %, o do PP-OCRv6 de 0,74 % para cerca de 0,67 % e o do Tesseract de 1,24 % para cerca de 1,17 %.
- **As 5 "pioradas" do consenso no Seirawan são, pela definição, estes mesmos casos:** programa igual ao gabarito, e os dois motores concordando contra ele. Conferi os 5, e todos são erro do gabarito. O "1,7 % no Seirawan" de CA-L4.3 tende a 0 de 298 (limite superior de 1,2 %), e o argumento de Dec-3 perde parte do peso.
- O corte de 99,5 % admite 7 caracteres errados numa página de 1.500. É igual ao alvo de prosa e, por token, vale de 2 % a 3 %. E 1 página por livro não estima nada.

Os gabaritos do `corpus_v2` passaram por rascunho e fila de conferência no core (`benchmarks/candidatos_v2/rascunhos`). Não medi neles, mas o risco é o mesmo, e nos tokens com figurina nenhum motor serve de contraprova.

**Correção, SPEC §3.2, depois da tabela de níveis:**

> **Auditoria do gabarito (obrigatória para o G1).** Rascunho e verificação não bastam, porque o rascunho vem do programa. Todo gabarito G1 passa por três filtros antes do primeiro uso:
> 1. **Dupla leitura:** a ferramenta lista os tokens em que o gabarito difere de qualquer leitura independente (PP-OCRv6, Tesseract), mostra o recorte e as duas formas em ordem sorteada, sem dizer de onde vem cada uma, e o usuário decide.
> 2. **Fiapo de legalidade:** todo token de lance do gabarito com posição conhecida é validado. O ilegal volta ao usuário: ou é erro de impressão, registrado, ou é erro do gabarito.
> 3. **Amostra cega:** 2 páginas sorteadas por livro, transcritas do zero, pelo menos 7 dias depois da verificação. O resultado é por token, separado por classe. Toda diferença é arbitrada contra a imagem e conta como erro de quem errou.
>
> **O número sai com o piso de ruído.** A medida grava `erro_do_gabarito_estimado`, por classe. Se ele não for menor que 1/5 do alvo da classe, o número é publicado como "limitado pelo gabarito" e não aprova nenhum CA.

> **CA-R2.4.** Dado um gabarito fabricado com erro plantado num token em que os motores discordam, a dupla leitura o lista. Dado um lance ilegal plantado, o fiapo o lista.
> **CA-R2.5.** `medir_motores` recusa gabarito sem o registro da auditoria, salvo com `--provisorio`, que aparece no JSON.

**Correção, roadmap PP2, novo item 0:**

> 0. Corrigir os 8 erros do apêndice A da crítica 2 (`verdade_versao` sobe) e rodar a mesma auditoria no `corpus_v2`. Refazer a linha de base, porque a catraca e a fatia usam esse gabarito.

### B2. "Erro silencioso" não é operacional

**Onde.** SPEC §1 (tabela dos quatro números), CA-R1.2, F-2, glossário §13.

**Problema.** Quatro indefinições:

- **Unidade.** A tabela diz "por token ou caractere". O checkup reporta por box e por caractere, e CA-R1.2 diz "box".
- **Falta, espaço e sobra.** Falta não tem box, então não pode "estar na fila". Espaço também não tem. Sobra não tem classe. Nada diz o que marca um erro desses.
- **"Sinal".** CA-R1.2 igualou "na fila" a "com sinal", mas F-2 cria o nível fraco, "só ao pedir". Erro no nível fraco está na fila e invisível.
- **É trapaceável sozinho.** Marcar tudo zera o número. Nenhum alvo da §1 fixa o orçamento de marcas junto dele.

**Por que importa: medi, por token, no Seirawan.**

| Sinal | Tokens marcados | Lance errado pego (26) | Silencioso em lance (N = 137) | Prosa errada pega (232) |
|---|---|---|---|---|
| Fila de hoje | **58,7 %** | 18 | 5,8 % (IC 2,6 a 11,2) | 202 |
| Discordância com o Tesseract | 11,5 % | 17 | 6,6 % (IC 3,0 a 12,1) | 188 |
| Discordância com o PP-OCRv6 | 10,3 % | 14 | 8,8 % (IC 4,6 a 14,8) | 190 |
| Fila ou Tesseract | pelo menos 58,7 % | 23 | 2,2 % (IC 0,5 a 6,3) | 220 |

O "18 % contra 2,3 %" do checkup vira "59 % contra 11 %" em tokens, que é o que o revisor vê. Nos livros com figurinas, a discordância marca 18,5 % a 20,3 % dos tokens, faixa em que, no único estudo citado, o efeito do realce deixou de ser significativo. O alvo "≤ 5 % por caractere" pode valer de 15 % a 25 % dos tokens.

Por token, a falta deixa de ser problema: só 4 dos 258 tokens errados do Seirawan não têm nenhum token lido em cima.

**Correção, SPEC §1, substitui as linhas 2 e 3 da tabela dos números:**

> **Unidade: o token da verdade**, depois de normalizar (ver "Normalização"). Espaços separam tokens. Toda marca, todo erro e todo denominador de `Erro silencioso` e `Trabalho` são por token. O caractere fica só no `Erro bruto` de prosa.
>
> **Token certo:** todos os caracteres alinhados são iguais, e ele corresponde a exatamente um token lido, sem nada a mais dentro.
>
> **Token errado, por tipo:**
> - **troca:** caractere diferente;
> - **falta:** caractere ausente, no token que sobrou;
> - **espaço:** dois tokens da verdade colados, ou um partido; conta 1 erro em cada token da verdade envolvido;
> - **sumiu:** nenhum caractere lido cai no token;
> - **inventado:** token lido sem nenhum caractere alinhado à verdade. Entra em `Estrutura` e, se a linha for de lances, também é reportado à parte.
>
> **Token sinalizado:** um token da verdade está sinalizado quando há **marca forte** (F-2) em pelo menos um dos tokens lidos alinhados a ele. Sem nenhum token alinhado (`sumiu`), vale a marca forte no token lido imediatamente antes ou depois, na mesma linha. Linha inteira perdida só está sinalizada se houver marca de linha ou de tinta sem box. Marca fraca, disponível só ao pedir, **não conta**.
>
> **Erro silencioso** = tokens errados e não sinalizados ÷ tokens da verdade da classe. **Nunca se reporta sem as marcas do mesmo sinal:** `silencioso @ m`, com m = tokens com marca forte ÷ tokens lidos. Comparar dois sinais só vale com o mesmo m.

**CA-R1.2 passa a:**

> **CA-R1.2.** Num gabarito fabricado, com um erro de cada tipo (troca, falta, espaço, sumiu, inventado): cada um, sem marca forte no token, conta como silencioso; com marca forte, não; com marca fraca, conta como silencioso.
> **CA-R1.5.** Marcar todos os tokens dá silencioso 0 e m = 100 %, e o relatório mostra os dois.

### B3. Não há classe de token nem normalização definidas

**Onde.** SPEC §1 (classes), R-1, `checkup-2026-11/experimentos/` (`SAN`, `marca`, `LANCE`), `ferramentas/medir.py`.

**Problema e medida.**

- **Três regras dão denominadores muito diferentes.** No Nunn, os tokens de lance são 44 (`SAN`), 54 (uma gramática razoável), 60 (`LANCE`) ou 72 (`marca`). No Seirawan, 135, 137, 148 e 156.
- **`SAN` perde figurina.** Nos escaneados há 270 figurinas para 260 tokens, sinal direto. Dos 495 tokens com figurina nos 4 livros, 71 ficam fora de `SAN`, 28 deles no Nunn. Caem `±` colado, `(` antes e formas de tabela.
- **`marca` pega prosa.** 77 tokens em 5 livros não são lance por nenhuma gramática razoável.
- **"Lance" mistura o que a tabela da §1 separa.** `12.♘f3+!` é um token só, com número (média), lance (máxima) e sinal (alta). Sem partir, erro no `!` vira erro de lance, e a legalidade não o vê.
- **Sobra não tem classe:** 331 nos livros com figurinas, 220 delas nos 445 erros do Yusupov. Os alvos "sem sobras" premiam quem inventa.
- **Nenhuma normalização comum.** `medir.py` compara cru, e os experimentos dobram a cor da figurina e o espaço. Em `ferramentas/` não há `unicodedata` nem `translate`. A catraca (R-3) e os alvos ficariam em réguas diferentes.
- **A dobra tipográfica mexe no que o alvo decide.** No Dvoretsky, o programa vai de 2,09 % a 1,56 % só dobrando traços e aspas. Com alvo de 0,5 %, isso não é detalhe.
- **O gabarito manda em `O-O` × `0-0`, `+-` × `±`, `...` × `…`.** Yusupov tem 12 `+-`, Aagaard 2 `±`.

**Correção, SPEC §1, depois da tabela de classes:**

> **Classificar.** A classe vem **só da verdade**, por uma função única, `classificar_token`, com teste, que parte o token em subtokens nesta ordem:
> `abre` `numero` `nucleo` `xeque` `sinal` `fecha`.
> - **numero:** `\d+\.{1,3}` ou `\d+…`; classe Número de lance.
> - **nucleo:** peça opcional (figurina ou letra do alfabeto de notação **declarado por livro** no gabarito), desambiguação, captura, casa, promoção; ou roque. Classe Lance. Sem casa, não é lance.
> - **xeque:** `+ # † ‡` faz parte de Lance.
> - **sinal:** `! ? !! ?? !? ?! ± ∓ ⩲ ⩱ = ∞ +- -+`, colado ou sozinho; classe Sinal. O `=` colado à casa com peça depois é promoção.
> - O resto é Prosa. Figurina sem casa é **Figurina solta**, classe própria.
>
> O erro de um subtoken conta na classe dele. O token de lance "exato" exige `nucleo` e `xeque` certos. Um número sem núcleo é Número de lance.
>
> **Sobra:** o caractere inventado dentro de um token herda a classe do subtoken dele. Fora de qualquer token, é `inventado`. **Nenhum número se reporta "sem sobras".**
>
> **Normalização: duas leituras, as duas no JSON.**
> - **Literal:** NFC, e espaços colapsados. Só isso. É o que define a página perfeita da §1.
> - **Semântica:** a literal, mais: figurina de qualquer cor vira uma só; `– — −` viram `-` entre letras e números; `’ ‘` viram `'`, `“ ”` viram `"`; `…` vira `...`; `0-0` vira `O-O`; figurina vira a letra da peça; `+-`, `+−` e `±` continuam diferentes.
>
> **A métrica primária usa a semântica.** Erro só na literal é **Tipografia**, classe própria, baixa gravidade, reportada à parte. A cor errada da figurina tem contador próprio.
>
> **Hífen:** o gabarito guarda a linha como impressa, com o hífen de fim de linha. Medir sobre a linha, antes de desfazer. A hifenização desfeita se mede só em `Estrutura`, na exportação.
>
> **Ordem separada de caractere:** linhas casadas pela caixa e comparadas linha a linha. Ordem é só o Kendall. Sem caixa de linha no gabarito, usar FCA, e o JSON diz qual foi. Página inteira alinhada em sequência não entra em nenhuma tabela.
>
> **Linha perdida:** os tokens contam como `sumiu` na classe deles, e a linha conta uma vez em `Estrutura`.

> **CA-R1.6.** Uma tabela de 60 tokens com o rótulo à mão, cobrindo figurina, letra, número, variante entre parênteses, `±` colado, roque, promoção e tabela, é classificada sem erro.
> **CA-R1.7.** `medir.py` e `medir_motores` usam a mesma `normalizar` e a mesma `classificar_token`; os scripts de `experimentos/` não são importados por nada.

**Correção, CA-R1.3 e a tabela de classes:**

> **Forma válida:** o token lido, depois da normalização semântica, classifica como núcleo pela mesma função. "Lance errado com forma válida" é token da verdade de classe Lance, errado, cujo token lido tem núcleo válido. **Legal**, quando a posição for conhecida, é campo à parte.

### B4. O conjunto de avaliação já está contaminado, não é por livro e será queimado

**Onde.** SPEC §2 princípio 4, §3.2, CA-R2.1, §13 glossário; CA-L3.1, L4.3, L5.1, L7.1, F1.1; roadmap PP2 a PP9.

**Problema.**

- **Contradição direta.** O glossário diz "conjuntos separados por livro". A §3.2 põe Aagaard, Nunn e Yusupov nos dois lados, e admite que as páginas de ajuste deles já foram vistas. A própria regra de consenso foi "acrescentada e ampliada depois de ver os livros com figurinas" (checkup §3).
- **A dependência real é de livro, e talvez de editora.** Entre livros, o ICC do erro de lance é 0,111; dentro do livro, por página, é cerca de 0 nos dois livros em que dá para medir (ver B5). `Box/` no core tem caixas de três livros de Aagaard, entre eles outro volume da série *Grandmaster Preparation*. **Mesma série, provável mesma tipografia.** Não confirmei se entraram no treino da CNN; `relatorio_treino` e `model_meta` não citam livro.
- **Reuso.** Cinco CA decidem "na avaliação" (L3.1, L4.3, L5.1, L7.1, F1.1), mais o ponto de parada de PP2, e há variantes: 3 em L-5, até 6 consertos em L-6, 2 motores mais `tiny` e `small` em L-3. Sem efeito nenhum, 15 olhadas a 5 % dão 54 % de chance de ao menos um falso ganho. E o que se aceita pela avaliação vira ajuste sobre ela.
- **CA-R2.1 não é testável.** Uma ferramenta não sabe se a pessoa está ajustando.
- **As páginas não são amostra.** O `corpus_v2` escolheu páginas pelo que têm de difícil (`mixed_layout`, `table`, `two_columns`, `halftone_panel`). A §1 usa isso para dizer que o consenso está "longe" em Aagaard, Yusupov e Nunn. Nos dois do Yusupov, o programa erra 30 contra 109 do PP-OCRv6 numa página, e 113 contra 46 na outra. **Uma página difícil diz pouco do livro.** "Páginas novas" não diz como escolhê-las.
- **Sem representante de notação com letras na avaliação.** Ajuste: Seirawan (português, letras) e Dvoretsky (inglês, figurinas, limpo). Avaliação: três em inglês com figurinas. A afirmação "em notação com letras, o programa perde" tem 1 livro e nenhuma validação.
- **Os 10 "por livro" dão N muito desigual.** Lances por página: Seirawan 20, Nunn 54, Dvoretsky 52, Yusupov 71, Aagaard 76.

**Correção, SPEC §3.2, substitui "Divisão fixa, por livro" e a meta:**

> **Três conjuntos.**
> - **Ajuste (livre):** Seirawan; Dvoretsky, páginas pares e as ímpares já lidas (101, 201); as 4 páginas do `corpus_v2`. Pode olhar erro a erro.
> - **Validação (decide):** 4 páginas sorteadas por livro de avaliação. Decide L-3, L-4, L-5, L-6, L-7 e F-1. A ferramenta só mostra totais por classe; a lista de erros fica fechada.
> - **Prova (não decide nada):** 8 páginas sorteadas por livro de avaliação. No máximo **3 usos**: fim de PP2, fim de PP5, fim de PP7. Só reporta. Se um número da prova levar a mudar qualquer regra, essas páginas passam para a validação e sorteiam-se outras.
>
> **Livros de avaliação:** Aagaard, Nunn, Yusupov e um quinto escaneado **em português ou espanhol, com notação em letras**, que nenhum motor tenha lido e de **editora diferente** das outras. O Darcy serve, porque já tem estrutura rotulada. **Só o quinto livro testa outro livro de fato.** Nos outros três, a conclusão vale "para páginas novas destes livros".
>
> **Sorteio:** semente registrada; só páginas de corpo. Estratos pela contagem de lances da página: sem lance, poucos, muitos, nesta proporção do livro. Excluir as a menos de 5 páginas das já vistas e as de `benchmarks/candidatos_v2`, selecionadas por família e com rascunho do core. Tabela é estrato próprio e nunca se soma à prosa.
>
> **Tamanho:** 12 páginas × 5 livros. Na prova, sorteiam-se mais páginas até 400 tokens de lance por livro, com teto de 20 páginas: um livro como o Seirawan dá uns 20 por página. Mínimo aceitável com o usuário sobrecarregado: 8 páginas por livro, e aí a prova só reporta limite, sem aprovar alvo. Medir o tempo de verificar nas 5 primeiras páginas e rever este número.

> **CA-R2.1 (troca).** Toda leitura de validação ou de prova acrescenta uma entrada a `docs/medidas/uso-da-avaliacao.json`: commit, conjunto, pergunta, hipótese, decisão. Na prova, a quarta entrada do mesmo sorteio reprova, e a saída nunca traz lista de erros.

**Correção, glossário §13:**

> **Ajuste, validação e prova:** conjuntos separados por página, e só o quinto livro é separado por livro. Ajuste decide parâmetro. Validação decide se a mudança entra. Prova só reporta.

### B5. Os alvos não são verificáveis com o N pedido, e 3/N não vale como está escrito

**Onde.** SPEC §1 ("O que se pode afirmar", "Alvos"), CA-L4.3.

**Problema e conta.**

1. **3/N pede amostra independente e zero evento.** Medi nos dados de hoje, para erro de lance por token: ICC entre páginas no mesmo livro de −0,007 (Seirawan) e 0,002 (Dvoretsky), com 6 páginas cada, logo pouco preciso; **entre livros, 0,111, DEFF 15**. Por caractere dentro do livro, DEFF de 3,5 a 4,6. Figurinas: 8 das 9 erradas estão numa página só.
   - Dentro de um livro, 3/N é quase honesto para lance, e falso para caractere.
   - **Somar N de livros diferentes não é honesto.** Com DEFF 4, 600 tokens sem erro sustentam 2,0 %, e não 0,5 %. Com DEFF 15, 7,2 %.
   - O "395 tokens, menos de 0,8 %" da §1 soma dois conjuntos de livros diferentes.
2. **"Zero erro" é um critério ruim.** Com taxa real de 0,1 %, cinco vezes melhor que o alvo, P(zero em 600) = **0,55**: reprova em 45 % das vezes. Com 0,2 %: 0,30. O CA tem erro de tipo II alto e não define o que fazer com 1 erro.
3. **O alvo depende de uma revocação impossível sem a legalidade.** Silencioso = bruto × (1 − revocação). Para 0,5 %: com bruto de 19 % (Seirawan) a revocação tem de ser 97,4 %; com 31 % (Nunn), 98,4 %; com 5 % (Dvoretsky), 90 %. Hoje a revocação por token em lance vai de 31 % a 69 %.
4. **N ≥ 150 diagramas não cabe no plano.** Com 60 páginas, a cerca de 1 ou 2 diagramas por página, há de 60 a 120. E o erro de FEN aglomera por livro, pelo mesmo desenho de peça.
5. **"Por livro" e "N ≥ 600" somado discordam.** Com 150 por livro, o limite por livro é 2 %.
6. **Três alvos estão no Seirawan,** que é ajuste (prosa, marcas), e CA-F1.2 também.
7. **"Não piorar" sem margem** é indecidível ou trivial.

**Correção, SPEC §1, substitui "O que se pode afirmar":**

> **Intervalo padrão.** Por livro, Clopper-Pearson com `N_ef = N / DEFF`. Até haver 20 páginas no livro, **DEFF = 2 para tokens e DEFF = 4 para caracteres** (medido: 1,0 a 1,1 e 3,5 a 4,6, com 6 ou 7 páginas). Com 20 páginas ou mais, usar o DEFF medido por página, nunca abaixo de 1,5. Com 10 páginas ou mais e 5 eventos ou mais, pode-se usar o bootstrap por página; **com zero evento o bootstrap dá intervalo vazio e é proibido**.
>
> **O que a soma significa.** Tokens de livros diferentes só se somam para dizer "**nestes** livros". Toda tabela traz os livros um a um. **Para outro livro não se afirma nada:** com zero falha em K livros, até 1 − 0,05^(1/K) dos livros ainda podem falhar: 45 % com K = 5, 26 % com K = 10, 14 % com K = 20, 9,5 % com K = 30.

| Tokens no livro, sem erro (DEFF 2) | Pode-se afirmar |
|---|---|
| 300 | menos de 2 % |
| 600 | menos de 1 % |
| 1.200 | menos de 0,5 % |
| 3.000 | menos de 0,2 % |

> **Aprovar um alvo.** Aprovado quando o limite superior unilateral de 95 % fica abaixo do alvo; não se exige zero erro. Se o limite for maior e a estimativa pontual menor, o resultado é "**não decidido**", e não "reprovado".

**Correção, SPEC §1, tabela de alvos:**

| Alvo | Linha de base | Alvo |
|---|---|---|
| Erro silencioso em lance, por token, nestes livros, **na prova** | Seirawan, exploratório: 5,8 % com a fila, a 59 % de marcas | limite superior ≤ **1 %**, com m ≤ 15 %, com N ≥ 2.000. Permite até 8 tokens silenciosos: passa em 82 % das vezes se a taxa real for 0,3 %, e em menos de 5 % se for 1 % |
| Erro bruto em prosa, **na prova** | medir em PP2 | definir em PP2 |
| Figurina errada | 9 de 498 (IC 0,8 % a 3,4 %), 8 numa página | não piorar mais que 0,5 ponto, IC por página |
| Marcas | 59 % dos tokens, Seirawan | ≤ 15 % dos tokens, na prova |
| Precisão das marcas | medir por token | ≥ 50 % por token, **também em cada classe** |
| FEN inteiro exato | 7 de 7 (IC 59 % a 100 %), sem conferência cega | 30 por livro sem erro, afirma ≥ 90 % por livro; amostrar só diagramas |

> Revisto por ser o que a medida consegue decidir: 0,5 % exigiria cerca de 5.000 tokens para ter 80 % de chance de aprovar um sistema com 0,2 % real. Volta a 0,5 % se o limite de 1 % passar com folga.

### B6. O centro do plano foi escolhido por uma métrica que não é a primária

**Onde.** Roadmap "Por que essa ordem", PP5 Contexto; SPEC F-1, CA-F1.1, L-3; checkup §4.

**Problema.** A métrica primária é silencioso em lance. A justificativa de PP5 é "98,4 % das trocas e sobras", por caractere, em quase tudo prosa. O checkup admite que a revocação em lance não foi medida. **Medi, por token:**

| Livro | Tokens de lance | Errados | Com figurina (verdade) | Pega PP-OCRv6 | Pega Tesseract |
|---|---|---|---|---|---|
| Seirawan | 137 | 26 | 0 | 14 (54 %) | 17 (65 %) |
| Aagaard | 76 | 16 | 13 | 2 | 4 |
| Nunn | 54 | 17 | 17 | 8 | 8 |
| Yusupov | 142 | 3 | 1 | 2 | 2 |
| Dvoretsky | 313 | 16 | 12 | 4 | 5 |
| **4 com figurinas** | **585** | **52** | **43 (83 %)** | **16 (31 %)** | **19 (37 %)** |

- Em 77 % dos tokens de lance desses livros há figurina, e neles a discordância não opina por construção. **PP5 não alcança a maior parte da métrica primária.** Só 9 dos 52 errados não têm figurina na verdade: os pegos acima disso são tokens que o programa leu sem ela.
- CA-F1.1 ("acha mais erros") se aprova com prosa, e a fila nova pode perder todo lance. Em Seirawan há 232 tokens de prosa errados para 26 de lance. A comparação somada é o caso clássico de Simpson.
- **A fila hoje pega mais lance que a discordância, no Seirawan: 18 contra 14 ou 17.** Custa 5 vezes mais marcas, mas a troca "discordância como variável principal" pode subir o silencioso em lance. O risco é reconhecido no roadmap, mas o CA não o vigia na classe.
- **"A legalidade depende da opinião" é só meio verdade.** F-3 (token rejeitado na tela) e a cobertura de X-1 não dependem de PP4 nem de PP5.

**Correção, CA-F1.1, por este:**

> **Critério risco-cobertura.** Para cada sinal (fila de hoje, nova), a curva `(m, silencioso @ m)`, por token, uma por classe (Lance, Sinal, Número, Prosa), com a fila ordenada, em m = 2, 5, 10 e 15 %, e na marca de operação. A fila de hoje entra pela sua ordem atual, cortada no mesmo m.
>
> **CA-F1.1.** Na validação, depois na prova, em m = 10 %:
> (a) em Prosa, a fila nova deixa pelo menos 20 % menos silenciosos que a de hoje, com o IC do bootstrap pareado por página inteiro abaixo de 0;
> (b) em Lance e em Sinal, **não pode ser pior**: limite superior da diferença em silencioso ≤ +0,5 ponto;
> (c) nenhum livro piora em Lance mais de 1 ponto.
> Com (a) sem (b), a fila nova vale só fora dos tokens de lance.

**Correção, roadmap "Ordem":**

> **PP2b, antes de PP3: a primeira pergunta sobre lance.** Só leitura de JSON, sem OCR novo, sem integrar nada.
> 1. **Teto de cobertura:** sobre o **texto do gabarito**, com a sincronia de X-1 (sementes, âncoras, pilha de variantes), qual fração dos tokens de lance tem posição conhecida e lance legal?
> 2. **Sinal da legalidade:** na leitura do programa, qual fração dos tokens errados de lance dá ilegal ou fora de sincronia, e qual a dos certos?
> 3. A tabela `token de lance errado × (fila, discordância, legalidade, nenhum)`, por livro.
>
> **Decisão:** se o teto for abaixo de 30 %, X-1 cai agora (Derruba de X-1). Se a legalidade pegar mais de 50 % dos lances errados com falso alarme abaixo de 5 % dos certos, **F-3 e X-1 sem hipóteses passam para antes de PP5**, e PP5 fica como conserto de prosa.

**Correção, roadmap PP5, Contexto:** trocar "É o maior ganho medido no Seirawan: marca 2,3 % dos caracteres e pega 98,4 %..." por:

> É o maior ganho medido **em prosa**. Por token, no Seirawan, marca de 10 % a 12 % e pega cerca de 82 % da prosa e de 54 % a 65 % dos lances. Nos livros com figurinas, marca de 18 % a 20 %, e pega de 31 % a 37 % dos lances. **Não é evidência sobre a métrica primária.**

### B7. F-1 como escrita não se ajusta nem se transfere

**Onde.** SPEC §5.1 (F-1), §12 (risco do treino), `checkup-2026-11/estado-da-arte.md` linha 159.

**Problema.**

1. **Isotônica é univariada.** `P(erro | discordância, fonte, confiança, margem, classe, contexto)` por isotônica não está definida: ela exige um escore já ordenado. Faltou o modelo que produz o escore.
2. **Poucos positivos.** No ajuste, erros de caractere do programa: símbolo 7 + 11 + 4; figurina 0 + 9 (8 numa página); tokens de lance errados: menos de 100. Isotônica com poucos dados costuma sobreajustar, e o cuidado usual é ter da ordem de mil pontos e bastante positivo. Por classe, não há como. E os positivos não são independentes: `1→l`, `0→o` e `9→g` fazem 46 % das trocas do Seirawan.
3. **Não se transfere entre livros. Medi.**

| Livro | P(erro \| discorda do PP) | P(erro \| concorda) | Taxa-base |
|---|---|---|---|
| Seirawan | 0,883 | 0,0003 | 2,1 % |
| Aagaard | 0,969 | 0,0045 | 11,3 % |
| Nunn | 0,509 | 0,0578 | 11,9 % |
| Yusupov | 0,936 | 0,0218 | 11,6 % |
| Dvoretsky | 0,985 | 0,0038 | 1,5 % |

   P(erro | concorda) varia **190 vezes**. É um número por caractere, mas basta para dizer que um corte em P absoluto ajustado no Seirawan não significa nada no Nunn.
4. **A fonte `livro` não tem nenhum dado.** Toda medida é com padrões vazios (`ambiente.programa`), e F-1 promete tratar o padrão do livro. Sobre o que depois vai ser o caso comum, o conjunto de ajuste não tem uma amostra.
5. **Recalibrar "em páginas revisadas" tem viés de verificação.** Numa página revisada, o rótulo depende da marca: erro sem marca tende a continuar "certo". A recalibração aprende que o que não se marcou está certo, e isso se realimenta. A §12 não vê isso.
6. **Marcas e erros dependem da classe e do contexto.** A discordância é nula em token com figurina por construção; o sinal do Tesseract em lance tem precisão de 18,5 % no Dvoretsky, 38 % no Seirawan e 46 % nos 4 livros juntos, e na prosa de 93 % a 95 %. Uma P única esconde isso.

**Correção, SPEC §5.1, substitui "Fazer" até "isenta":**

> **Duas coisas separadas: ordenar e cortar.**
>
> **Ordenar.** Regressão logística com **no máximo 8 parâmetros**, sobre: discordância (motor), fonte, `logit(confiança)` por fonte, margem, token com figurina. Um modelo só, com a classe por termos fixos; **nada por classe enquanto a classe tiver menos de 50 tokens errados no ajuste**. Ajuste em validação cruzada **por livro** (deixa um livro de fora). Isotônica só depois, sobre o escore, e só se o ajuste tiver mais de 1.000 tokens, com pelo menos 200 erros, mantida se melhorar o log-loss deixando um livro de fora. Senão, Platt.
>
> **Cortar: por orçamento, não por probabilidade.** A marca forte vai aos m % maiores de cada página, com m fixo no ajuste. Probabilidade absoluta não aparece na tela nem decide corte entre livros.
>
> **Recalibrar por livro:** um parâmetro só, o intercepto, com a taxa de erro de **páginas auditadas por inteiro** (R-4), não de páginas apenas revisadas. Com menos de 10 erros auditados, não recalibrar.
>
> **Treino por livro.** Medir em dois estados, T0 (padrões vazios) e T1 (padrões ensinados nas páginas anteriores do mesmo livro, pelo `replay_fatia`). Ajuste e prova trazem os dois. A fonte `livro` só entra no modelo com dado de T1. Enquanto não houver, ela segue a regra de amostra de distância alta, sem calibrar.
>
> **Curva de confiabilidade** só por decil, deixando um livro de fora, e informativa. **Decide-se pela curva risco-cobertura,** CA-F1.1.

**Correção, §12, linha "O treino por livro altera a calibração":**

> A ordem é por escore e o corte por orçamento, logo o corte não envelhece. A recalibração do intercepto usa só páginas auditadas por inteiro, porque em página revisada o rótulo depende da marca.

---

## Importantes

### I1. Catraca: determinística, mas o gabarito muda

**Onde.** R-3, CA-R3.2 a CA-R3.4.

**Problema.** Com commit, modelo e gabarito fixos, a medida não tem ruído. Portanto a catraca é um teste de regressão, sem nenhuma estatística, e qualquer mudança é real **naquelas 7 páginas**. Três falhas:

- Corrigir o gabarito muda o CER sem mudar o programa. Os 8 erros de B1 movem o CER do programa em +0,07 ponto, o que dispara a catraca, ou, no sentido inverso, dá folga que ninguém ganhou.
- Tolerância zero em 12.008 caracteres: 1 caractere são 0,008 %. Um conserto que tira 100 erros em outros livros e cria 1 no Seirawan "volta" (roadmap PP3: "se a catraca reprovar, o conserto volta").
- O gabarito da catraca é ajuste, e vale como proteção, não como evidência de melhora.

**Correção, CA-R3.3, e novo CA:**

> **CA-R3.3.** A catraca é chave de `(sha do gabarito, sha do modelo, commit do core, versão da normalização)`. Mudou a chave: a ferramenta **remede a referência antiga sobre a nova chave** e só compara essas duas. A comparação entre chaves diferentes é recusada, como em `replay_fatia.py comparar`. Por classe, tolerância de 2 tokens ou caracteres e de 0 em linhas perdidas e casas erradas. Passar da tolerância exige registro no commit, com o ganho na validação que o justifica.
> **CA-R3.5.** Duas rodadas no mesmo commit dão JSON igual, salvo o tempo. Se não derem, a catraca não vale até achar a causa.

### I2. "Melhorou" não tem definição

**Onde.** CA-L5.1, CA-L6, CA-L7.1, CA-F1.2, CA-X1.1, CA-L1.4, L-3.

**Problema.** "Baixa o CER" passa com 1 caractere. "Zero certo → errado no conjunto de ajuste" (CA-X1.1) passa com N pequeno e não diz N. Reportar taxas de dois sistemas não aproveita o pareamento.

**Medi o que os dados de hoje sustentam, por página:**

- Programa contra PP-OCRv6, 4 páginas escaneadas: +4,35 pontos, IC de −6,08 a +12,49.
- Teste de sinal por página: o menor p possível é 0,125 com 4 páginas e 0,0625 com 5. **Nunca dará significância com menos de 6 páginas, ou 6 livros,** bicaudal.
- Tesseract menos PP-OCRv6, nos 17: 16 de 17 páginas, mas as 13 são de dois livros.
- Entre livros (t, 4 graus de liberdade): PP-OCRv6 ÷ programa = 0,70 (IC 0,25 a 2,01); PP-OCRv6 ÷ Tesseract = 0,61 (IC 0,36 a 1,06); consenso ÷ programa = 0,35 (IC 0,13 a 0,91).

**Correção, roadmap "O contrato de cada passo", item 6 passa a:**

> 6. **Experimento de leitura.** Ajustar só no ajuste. Antes de rodar a validação, escrever no registro a métrica, a classe e o efeito mínimo. **Uma mudança entra quando, nas páginas de validação, com as duas versões sobre o mesmo gabarito:**
> a) a redução líquida na métrica fixada é de pelo menos **10 %** e de pelo menos **5 eventos**;
> b) o IC 95 % do bootstrap pareado, reamostrando **páginas dentro de cada livro** (2.000 réplicas, semente fixa), fica inteiro do lado do ganho;
> c) o registro dá **erros tirados e erros criados**, separados, por classe; nenhuma classe de maior gravidade piora mais do que a margem declarada;
> d) nenhum livro piora mais de 1 ponto, e o resultado por livro é mostrado, sem teste entre livros.
>
> Sem (a) e (b), "não entra", mesmo com o sentido certo. Com menos de 20 páginas, em vez de (b), um teste exato de sinal por página, e, se ele não puder dar menos de 0,05, o registro diz "não decidível".

**CA-X1.1 passa a:**

> **CA-X1.1.** Em pelo menos 300 tokens de lance com posição conhecida, no ajuste: a top-1 acerta mais que a leitura, por pelo menos 5 tokens, com certo → errado ≤ 1 token (limite de 1,6 %). Depois, o mesmo na validação, antes de virar sugestão.

### I3. R-4 tem validade fraca e chega tarde

**Onde.** R-4, CA-R4.1, roadmap PP9, §1 ("Residual").

**Problema.**

- **Injeção supõe que o erro plantado se ache como o natural.** Sem imitar as confusões reais, a medida diz pouco. Injetar aumenta a prevalência e o aviso aumenta a vigilância, os dois inflam a fração achada; o efeito de prevalência é conhecido em busca visual.
- **Marca muda tudo.** Silencioso é o que importa, e injetar sem dizer se o erro tem marca mistura as duas situações.
- **O N é pequeno:** 16 de 20 achados dá IC de 56 % a 94 %, ou seja, resíduo entre 6 % e 44 % dos erros.
- **O teste que derruba não tem critério nem poder.** "Divergir da releitura às cegas" não tem número, e com poucos erros os dois intervalos sempre se cruzam.
- **O trabalho é perdido:** a revisão na cópia não volta ao projeto. O usuário paga duas vezes.
- **O nexo silencioso → residual é a hipótese central do plano e não foi testado.** A métrica primária supõe que o revisor corrige todo o marcado e nada do não marcado. O estudo citado achou que metade dos erros segue sem correção. Testar isso só em PP9 deixa PP5 sem resposta sobre valer a pena.

**Correção, SPEC §3.4, substitui o corpo:**

> **Referência: releitura cega de páginas sorteadas.** Depois que o usuário dá um trecho por pronto, 1 página em cada 20, no mínimo 3, sorteadas por semente, são transcritas do zero, pelo menos 7 dias depois, sem ver a leitura nem as marcas. A diferença é arbitrada contra a imagem. Conta por token e classe. **O erro achado é corrigido no projeto,** logo não há trabalho perdido.
>
> **Residual** = tokens errados que restaram ÷ tokens da amostra, por classe, com o intervalo padrão da §1, **por livro**. Este é o número que vale para um livro novo: não se generaliza, mede-se nele.
>
> **O nexo com o silencioso:** a mesma amostra dá a fração dos erros marcados que foram corrigidos e a dos não marcados. Sem isso, silencioso não prevê residual.
>
> **Injeção: opcional, e só como calibragem do revisor.** Na própria revisão real, com erros tirados da matriz de confusão do ajuste, incluindo lance de forma válida; no máximo 1 por página, para não subir a prevalência; metade com marca, metade sem; a ferramenta desfaz ao fim. Pelo menos 40 injetados para reportar (38 de 40 dá IC de 83 % a 99 %). **Derruba:** se ficar acima da fração da releitura cega por mais de 10 pontos em 40 ou mais, a injeção sai.

> **CA-R4.1.** A ferramenta sorteia as páginas e compara a releitura cega com o projeto sem mostrar a leitura. Com erros plantados num projeto fabricado, conta os certos por classe.
> **CA-R4.2.** A injeção, com semente, sai por inteiro ao desfazer: projeto byte a byte igual, salvo o que o revisor corrigiu de verdade.

**Correção, roadmap:**

> R-4 sai de PP9 e vai para o **fim de PP5**: 3 páginas, com o usuário, antes do ponto de parada. A pergunta de parada passa a incluir: **o erro marcado é corrigido em mais de 80 %?** Se não, a fila nova é a segunda prioridade, e a interface (F-2) vem primeiro.

### I4. Nada foi medido no estado de uso

**Onde.** Checkup §3 e §4; SPEC princípio 8; roadmap ponto de parada de PP2.

**Problema.** Todas as linhas são "padrões do livro vazios", e "treino por livro é o diferencial" (princípio 8). A seleção de motor e a ordem do plano supõem que o erro de hoje é o erro depois de treinar. Hipótese: esse treino reduz justo as confusões que a discordância pega, baixando a utilidade dela, e, ao isentar a fonte `livro` da fila, sobe o silencioso. O sentido e o tamanho são desconhecidos, e os dois são decisivos.

**Correção, roadmap PP2, novo item:**

> **PP2c. Medir T0 e T1 no Seirawan e no Yusupov.** T1: `replay_fatia` ensina as primeiras páginas verificadas e lê as seguintes; separação por página (CA-L8.2). Reporta os quatro números e a tabela `lance errado × sinal`. **Decisão:** se a discordância pegar menos de metade dos erros de T1 que pegava em T0, PP5 é revisto antes de começar.

### I5. Comparabilidade: as conclusões L-3 e "os motores são complementares"

**Onde.** Checkup §3, SPEC L-3, Dec-2.

- **Segmentação do próprio programa.** Serve para o desenho de L-2, porque o motor opina na linha achada. Mas não mede o motor nem revela a linha perdida. Linha sem nenhum motor: 1 em 213 no Seirawan, 1 em 223 no Dvoretsky, logo não é o principal viés **nestes dois**. Nas 4 páginas escaneadas, sem caixas, não dá para saber. Os recortes com tabuleiro (linha "Diagrama 8", p. 26) mostram outro viés: a caixa do programa inclui tinta do tabuleiro e o motor devolve lixo.
- **Ordem pesa pouco.** O checkup atribui o CER alto à "ordem errada". Por token, sequência contra saco: 139 × 138, 69 × 53, 30 × 30, 113 × 111. **A ordem explica no máximo 16 de 69 no Nunn, e quase nada nas outras.** O que sobra são sobras: 250 tokens a mais no programa, no Yusupov com trama. Portanto a ressalva está errada no peso.
- **Página e linha seguem sem comparação.** A §1 põe 0,21 % e 9,75 % em sequência, e L-3 diz "nos 5 livros".
- **Modelo global contra fábrica.** O teste não é justo nos dois sentidos: possível vazamento de irmãos na CNN (B4) e motores sem ajuste nenhum.
- **Tesseract sem configuração controlada.** `motores.md` admite não saber se o `tessdata` é `fast` ou `best`. Corpo com altura mediana de 20 px no Aagaard, sem ampliar. Idioma `eng` em todos, menos no Seirawan. O 25,74 % no Yusupov, contra 7,67 %, pede conferência antes de virar "pior".
- **O papel "Padrão" do Tesseract não é robusto na classe primária.**

| | Tesseract | PP-OCRv6 |
|---|---|---|
| Lance lido errado, Seirawan | 44 de 137 | 8 de 137 |
| Diferença, por página | | +26 pontos, IC 14 a 35; 5 de 5 páginas; p = 0,0625 |
| Marcas em lance, Seirawan | 45 tokens (30 %) | 14 (9,5 %) |
| Precisão em lance, Seirawan | **37,8 %** | 100 % |
| Precisão em lance, Dvoretsky | **18,5 %** | 100 % |
| Precisão em lance, 4 livros | **45,9 %** | 88,5 % |
| Pega lance, 4 livros | 19 de 52 | 16 de 52 |

**Conclusões.** "Tesseract padrão" hoje só se sustenta pela RAM. Isso é um argumento legítimo, mas é de custo, não de medida. "Complementares" está mantida para prosa. **A diferença em lance é o que falta decidir, e o critério de L-3 ignora a classe.**

**Correção, SPEC §4.3, CA-L3.1:**

> **CA-L3.1.** Antes da validação, no ajuste: fixar a configuração de cada motor com um varrimento pequeno e registrado (`tessdata` `fast` e `best`, ampliação ×1 e ×2, `psm` 7 e 13). Depois, na validação, por classe (Lance, Sinal, Prosa), por token, em m igual: revocação, precisão, tempo e RAM. **O padrão é o motor mais leve cuja precisão em Lance fique ≥ 60 % e cuja revocação em Prosa fique a menos de 5 pontos da melhor.** Se nenhum leve passar em Lance, ele vale só em tokens sem forma de lance, e o texto de L-3 diz isso.

**Correção, SPEC §4.3, célula do Tesseract, "Papel proposto":**

> **Padrão provisório, por custo.** Sua precisão em lance, por token, é de 38 % no Seirawan e de 46 % nos livros com figurinas: não marca lance até passar por CA-L3.1.

**Correção, §1, frase dos alvos:** trocar "(prosa: Seirawan 0,21 %, Dvoretsky 0,52 %), e longe nos outros (Aagaard 1,09 %, Yusupov 3,72 %, Nunn 9,75 %)" por:

> (prosa: Seirawan 0,21 %, Dvoretsky 0,52 %, por linha). As 4 páginas escaneadas foram escolhidas por serem difíceis e medem a página inteira: não dizem a distância até o alvo nesses livros.

**Correção, checkup §3, ressalva:**

> Refeita por token: a ordem explica até 16 de 69 no Nunn e quase nada nos outros. O grosso são sobras e erros reais. As páginas foram escolhidas por dificuldade (`corpus_v2`), e os dois do Yusupov têm resultado invertido entre si (30 contra 109; 113 contra 46).

**Experimento de vazamento, barato:**

> Listar as fontes da base de treino (a `Box/` tem caixas de Aagaard, incluindo a série *Grandmaster Preparation*). Fechar `não se sabe` em `treino_da_cnn`. Se os 5 livros ou irmãos da mesma editora estiverem nela, o holdout de L-8 sobe para antes de PP5 e a vantagem em figurina fica como "medida com vazamento".

### I6. CA-L4.3 mede com um contador que falha

**Onde.** CA-L4.3, Dec-3, checkup §3.

**Problema.**

- O próprio relatório diz que o contador "não vê inserção errada". "22 a 31" não é um intervalo: são dois contadores.
- Regra medida e regra do CA são diferentes.
- O certo → errado do Seirawan é, na verdade, erro do gabarito (B1). Sem ele, cerca de 17 de 819.
- 14 dos 22 estão numa tabela. Sem o Nunn: 8 de 763, 1,0 %, IC 0,5 a 2,1. É estrato, não média.
- A unidade do lote é a palavra, mas conta caractere.
- Para afirmar menos de 0,5 % com zero erro, são 598 edições, no mínimo, e 1.200 com DEFF 2.

**Correção:**

> **CA-L4.3.** Unidade: o **token alterado pelo lote**. Certo → errado: era certo e ficou errado, contra o gabarito **auditado**. Errado → errado conta à parte. Na validação, com tabela como estrato separado, em pelo menos 600 tokens alterados: limite superior ≤ 1 %. Se a tabela passar de 5 %, o lote não vale em tabela e continua em prosa. Todo caso certo → errado é arbitrado contra a imagem antes de contar.

### I7. G2 e G2-d

**Onde.** R-2, CA-R2.2, `motores2.py:21-35`.

**Problema.**

- `linhas_nativas` joga fora **a linha inteira** se um span usar `Merida` ou `ArialMT`, e não sei o que se perde.
- 30 linhas sorteadas têm poucos sinais: o Dvoretsky tem 112 símbolos em 5.885 caracteres, e é o erro "alta" da §1.
- O G2 dá uma única fonte e imagem limpa. Nele, a figurina tem 0 de 228 erros, e nenhuma calibração deveria vir daí para o escaneado.
- G2-d sem critério de semelhança é só um nome.
- Dvoretsky entra no ajuste por páginas pares, mas 101 e 201 já foram vistas (corrigido em B4), e as ímpares ficam sem uso.

**Correção, CA-R2.2 e tabela de níveis:**

> **CA-R2.2.** Dado o Dvoretsky, o gerador G2 produz linhas com figurinas mapeadas e relata quantas linhas e caracteres descartou, e por qual fonte. A conferência à mão cobre 30 linhas sorteadas **e todas as ocorrências de cada símbolo diferente, até 5 por símbolo**.

> **Limite do G2 e do G2-d (acrescentar à tabela).** Não aprovam alvo, não entram em intervalo da §1, não calibram o modelo da fila. Servem para testar a ferramenta e para contar figurinas raras. G2-d só vale se a matriz de confusão de um livro degradado se parecer com a de um escaneado real: medir em PP2. Se as 10 maiores confusões tiverem menos de 5 em comum, o G2-d sai.

### I8. Pontos de parada e critérios sem número

**Onde.** Roadmap "Pontos de parada", CA-L1.4, X-1, L-5, PP5.

**Problema.**

- "Confirma a complementaridade?" e "A margem separa?" não têm número, e a resposta será interpretada depois de ver o dado.
- `cobertura@3` (CA-L1.4): sem denominador, nem IC. Faltas não têm box, logo não têm top-3, e são 80 de 331 no Seirawan. Sem incluí-las, o número sobe. Por classe: figurina com 9 erros tem IC de ±30 pontos.
- Nenhum critério encerra o plano nem limita o gabarito.

**Correção, roadmap, tabela de pontos de parada:**

| Ponto | Pergunta, com número | Se não |
|---|---|---|
| Fim de PP2 | Auditoria do gabarito feita; **em Prosa**, a discordância por token pega ≥ 60 % com precisão ≥ 70 %, na validação | Rever L-2 e L-3; não começar PP5 |
| PP2b | Teto de cobertura ≥ 30 %; a legalidade pega ≥ 50 % dos lances errados, com alarme < 5 % nos certos | Cobertura baixa: X-1 cai. Legalidade forte: F-3 e X-1 antes de PP5 |
| Fim de PP4 | `cobertura@3` ≥ 50 %, **com faltas no denominador e limite inferior do IC ≥ 40 %**, somada; por classe só com mais de 50 erros | Sem decodificador |
| Fim de PP5 | CA-F1.1 (a) e (b); e erro marcado corrigido em mais de 80 % (I3) | Mantém a fila de hoje em lance; opinião só em prosa |
| Fim de PP7 | Em m = 5 % dos tokens de lance, a margem pega ≥ 50 % dos errados; cobertura ≥ 30 % | Fica a marca de ilegal |

> **Parar de crescer o gabarito:** quando a prova tiver ≥ 2.000 tokens de lance, ou o IC de CA-F1.1 já estiver todo de um lado.
> **Parar o plano de leitura:** se dois passos seguidos não tirarem pelo menos 20 % do silencioso em Lance na validação, volta ao usuário, antes do passo seguinte. Se o limite de silencioso em lance chegar a ≤ 1 %, com m ≤ 15 %, na prova, fim: o resto do plano de leitura vira opcional.
> **Parar de usar a prova:** 3 usos (B4).

**CA-L1.4 passa a:**

> **CA-L1.4.** `cobertura@3` é a fração dos tokens errados do ajuste em que, em cada caractere errado, o certo está no top-3, **incluindo** faltas e `sumiu` como não cobertos. Sai somada, com o intervalo padrão, e por classe só com pelo menos 50 erros. O passo só segue com limite inferior ≥ 40 %.

---

## Menores

### M1. Empates do alinhamento

**Onde:** `ops`, `perita_ocr.alinhar`. Dois alinhamentos de mesmo custo atribuem o erro a posições diferentes, e a classe pode mudar. Os scripts têm dois alinhadores. **Correção, R-1:** "Empate no alinhamento: preferir troca, depois falta, depois sobra, com teste de ordem. Um único `alinhar`."

### M2. Precisão por classe

**Onde:** §1 ("Precisão das marcas"). Já incorporado em B5: 88 % por caractere, em prosa, esconde 18,5 % em lance.

### M3. CA-L1.3 sem método

**Onde:** "O tempo sobe menos de 5 %". O CA-7.1 já oscila por 20 ms. **Correção:** "Mediana de 5 rodadas alternadas A/B, na máquina cadastrada, sobre as mesmas 7 páginas, sem outra carga."

### M4. Linha de base do lado

**Onde:** "Lado a jogar 2 de 5" (IC 5 % a 85 %), "FEN 7 de 7" (IC 59 % a 100 %). Sem o IC, leem-se como medida. **Correção:** acrescentar o IC na célula. L-3: "5 pontos abaixo" só com N ≥ 200 erros, senão "não decidível".

### M5. Quantos números

**Onde:** §1: 4 números × 6 classes × 5 livros × 4 motores. Sem primária, algo sempre melhora. **Correção, §1:** "Decidem: silencioso em Lance @ m, silencioso em Prosa @ m e marcas. O resto é descritivo e não aprova CA."

---

## A pergunta barata

**"Dos tokens de lance errados hoje, quantos a fila, a discordância e a legalidade pegam, e quantos têm posição conhecida?"**

As duas primeiras partes respondi aqui, em B2 e B6, com contagens das saídas que já existem. A que falta é a mais valiosa e não exige OCR: rodar a sincronia de X-1 sobre o **texto do gabarito** dá o teto de cobertura. Uns poucos parsers, em uma sessão, decidem se a ordem PP5 → PP7 se mantém (PP2b, em B6). Hoje a ordem se sustenta só por "ela usa as hipóteses e a opinião como entrada", e F-3 e a legalidade simples não usam.

**Robustez das conclusões:**

| Conclusão | Robusta? |
|---|---|
| PP0 e PP1 primeiro | Sim, não dependem de medida |
| Régua antes de motor | Sim, e B1 reforça |
| Discordância como sinal para **prosa** | Sim, provável: pega de 72 % a 82 % por token, nos dois grupos, mas com poucos livros e páginas difíceis |
| PP5 antes de PP7 | **Não**, sem PP2b |
| Tesseract padrão | **Só por RAM.** Em lance, medido contra |
| PP-OCRv6 "melhor em prosa em 4 de 5" | Nestes livros. Entre livros, IC 0,05 a 1,13 |
| Consenso reduz o erro | Nestes livros (IC 0,13 a 0,91), e mais depois de B1 |
| Vantagem do programa em figurina | **Não até fechar o vazamento** (I5) |

## Experimentos faltantes, baratos, que podem derrubar o plano

Em ordem. Todos sem carga pesada, salvo o 4.

| # | Experimento | Custo | Derruba |
|---|---|---|---|
| 1 | Auditoria do gabarito no `corpus_v2`, igual à do apêndice A | Minutos, sem OCR | Se achar mais erro em lance: os 35 de 554 e a tabela mudam |
| 2 | Teto de cobertura de X-1 sobre o texto do gabarito (PP2b) | Uma sessão, sem OCR | Abaixo de 30 %: X-1 cai. Alto: ordem do roadmap muda |
| 3 | Legalidade na leitura do programa, nos tokens já alinhados (PP2b) | Junto do 2 | Separa ou não certo de errado, antes de PP4 |
| 4 | Tesseract `best`, ampliação ×2, nas 17 páginas | Cerca de 15 min, sozinho | Muda a precisão em lance e talvez L-3 |
| 5 | Fontes da base de treino (I5) | Minutos | Fecha o vazamento da figurina |
| 6 | Sorteio das páginas e tempo de verificar 5 delas | 1 sessão do usuário | Se custar demais, os N da §1 viram os de reserva, e a prova só reporta |
| 7 | T0 × T1 no Seirawan (I4) | Uma medida | Se a discordância não ganhar nada depois de treinar, PP5 é repensado |
| 8 | 1 página cega, por token, com o usuário | 30 min | Mede o ruído real do gabarito |

---

## Apêndice A. Erros do gabarito achados (Seirawan)

Conferidos por mim contra o recorte do PDF. Não corrigi nada. A página é o índice do PDF.

| Página | Gabarito | Impresso |
|---|---|---|
| i020 | `por` (em "3? por quê?") | `Por` |
| i021 | `melhor` | `melhor,` |
| i021 | `potter` | `Potter` |
| i022 | `Dama` | `Dama,` |
| i022 | `portanto,` | `Portanto,` |
| i024 | `ai` | `aí` |
| i025 | `Tarrasch,Schroeder` | `Tarrasch-Schroeder` |
| i025 | `Aguns` | `Alguns` |

Olhados e não contados: `força` e `tranqüilo` (i023, vizinhos de uma falta real, ou o motor errou), `—` × `–` (i025, tipografia, decidir pela Normalização), `mente,` (i026, causa não esclarecida), 2 tokens da linha "Diagrama 8" (i026, recorte com tabuleiro).
