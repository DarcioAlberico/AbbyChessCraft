# AbbyChessCraft — spec da página perfeita

Versão 0.1, 2026-11-05, sobre o commit `262d897`. Complementa a `docs/SPEC.md` (v0.4) e a
`docs/SPEC-qualidade.md`. A evidência está em `docs/pesquisa/checkup-2026-11.md`. O plano está em
`plans/roadmap-pagina-perfeita.md`.

## 0. Como ler

- **Ids:** `R` régua, `L` leitura, `F` fila, `X` xadrez, `D` dados, `C` confiabilidade, `E` entrega, `A` arquitetura,
  `U` interface. Cada item tem um **critério de aceitação** (`CA-…`), que vira teste antes do código.
- **Evidência:** **Medido**, **Confirmado** (lido no código), **Inferido**, **Hipótese**. Item com hipótese traz o que
  a derruba. Se o experimento a derrubar, o item sai da spec, com o registro. Os itens de texto e de copy (A-7, U-11) não
  têm CA próprio.
- **Exploratório:** conta de 05/11 sobre o conjunto de ajuste, com gramática provisória (relatório, "Marcas"). Dimensiona; não aprova CA.
- **Prioridade:** **P1** perde dado ou invalida a medida; **P2** muda o que o usuário recebe; **P3** custo de
  manutenção ou conforto.
- **Decisões do usuário** ficam na §10. Toda decisão tem um padrão: sem resposta, o plano segue por ele, e nada de irreversível acontece.

## 1. O que é uma página perfeita

**Definição.** Uma página é perfeita quando todo caractere, figurina, sinal, posição de diagrama, lado a jogar, função de
área e ordem de leitura iguala o impresso. Erro de impressão fica como está impresso.

**Consequência.** Nenhum motor prova isso sozinho. A página perfeita é um resultado da cadeia inteira: leitura, sinais e
revisão humana bem dirigida. O objetivo desta spec é:

> **Levar o erro que passa despercebido a um nível medido, gastando o mínimo de atenção do revisor.**

**O que o plano não promete.** Nenhum marco entrega a página perfeita. O fim curto entrega marcas e a fila Lances, sem número de qualidade e sem melhorar nenhuma leitura. O fim completo entrega uma tabela por livro e consertos medidos. Diagrama e sinais têm só M6, opcional; função de área e ordem de leitura têm medida, sem item que as melhore.

Por isso a régua não é o CER. São quatro números, por classe, por livro:

| # | Número | Definição |
|---|---|---|
| 1 | **Erro bruto** | Token errado, por tipo. Em prosa, também o CER por caractere |
| 2 | **Erro silencioso** | Token errado e não sinalizado ÷ tokens da verdade da classe. **É a métrica primária** |
| 3 | **Trabalho** | Marcas `m` (tokens com marca forte ÷ tokens lidos), precisão, gestos e tempo por página |
| 4 | **Residual** | Token errado depois que o revisor dá a página por pronta (§3.4) |

**Decidem:** silencioso em Lance a `m`, silencioso em Prosa a `m`, e `m`. O resto é descritivo e não aprova CA.

**E um número que decide para o usuário:** minutos por página revisada, pelo registro de eventos, em páginas do trabalho real. Não custa revisão a mais. Vale nos pontos de parada de M2 e M5 (roadmap).

### As definições

**Unidade: o token da verdade,** depois de normalizar. Espaços separam tokens. O caractere fica só no erro bruto de prosa.

**Token certo:** todos os caracteres alinhados são iguais, e ele corresponde a exatamente um token lido. **Token errado, por tipo:**

| Tipo | Definição |
|---|---|
| troca | Caractere diferente |
| falta | Caractere ausente, no token que sobrou |
| espaço | Dois tokens da verdade colados, ou um partido; 1 erro em cada token da verdade envolvido |
| sumiu | Nenhum caractere lido cai no token |
| inventado | Token lido sem nenhum caractere alinhado à verdade. Conta em Estrutura |

**Token sinalizado:** há **marca forte** (F-4) em pelo menos um token lido alinhado a ele. Em `sumiu`, vale a marca forte no token lido vizinho, na mesma linha. Linha perdida só está sinalizada com marca de linha ou de tinta sem box. **Lance conferido por linha na fila Lances (F-4) conta como conferido, à parte:** não é sinal.

**Erro silencioso nunca sai sem as marcas do mesmo sinal: `silencioso @ m`.** Marcar tudo zera o número. Comparar dois sinais só vale com o mesmo `m`.

**Alinhamento:** um só, com teste. Empate: troca, depois falta, depois sobra.

### Classes e gravidade

| Classe | Conta como erro | Gravidade |
|---|---|---|
| Lance | Peça, casa, captura, promoção, xeque | Máxima se a forma for válida |
| Diagrama | FEN inteiro exato, lado, orientação | Máxima |
| Sinal (NAG) | ± ∓ ⩲ ⩱ ! ? e os demais | Alta: a legalidade não o vê |
| Número de lance | Valor, `...` | Média |
| Figurina solta | Figurina sem casa | Média |
| Estrutura | Ordem, função da área, linha perdida ou inventada | Média |
| Prosa | Token e CER | Baixa, salvo nome próprio |
| Tipografia | Só na leitura literal (abaixo) | Baixa |

**Classificar.** A classe vem **só da verdade**, por uma função única, `classificar_token`, que parte o token em subtokens: `abre`, `numero`, `nucleo`, `xeque`, `sinal`, `fecha`.

- **numero:** `\d+\.{1,3}` ou `\d+…`. Número de lance.
- **nucleo:** peça opcional (figurina ou letra de `letras_das_pecas`, abaixo), desambiguação, captura, casa, promoção; ou roque. Lance. Sem casa, não é lance.
- **xeque:** `+ # † ‡`, parte do Lance.
- **sinal:** `! ? !! ?? !? ?! ± ∓ ⩲ ⩱ = ∞ +- -+`, colado ou sozinho. O `=` colado à casa com peça depois é promoção.
- Figurina sem casa: Figurina solta. O resto é Prosa.

**Alfabeto.** `Notacao` diz se é figurina, não quais letras, e as letras vêm hoje do idioma da prosa (`lances.py:172-181`): num livro em português com notação inglesa, `Rf1` vira rei e todo lance de torre fica ilegal. **Fazer:** `Projeto.letras_das_pecas: str = ""`, 5 letras na ordem rei, dama, torre, bispo, cavalo; vazio é `PECAS[idioma]`. `lances._tabela`, `sessao.figurinas` e `classificar_token` o leem, e o JSON do gabarito traz o mesmo campo. Não muda a versão: campo novo em versão antiga vai a `extras`.

O erro de um subtoken conta na classe dele. **Lance exato** exige `nucleo` e `xeque` certos. **Forma válida:** o token lido classifica como núcleo pela mesma função. **Legal**, com posição conhecida, é campo à parte. Caractere a mais dentro de um token herda a classe do subtoken. **Nenhum número sai "sem sobras".**

**Normalização: duas leituras, as duas no JSON.**

- **Literal:** NFC e espaços colapsados. É a da página perfeita.
- **Semântica:** a literal, mais: figurina de qualquer cor vira uma só e depois a letra da peça; `– — −` viram `-` entre letras e números; aspas curvas viram retas; `…` vira `...`; `0-0` vira `O-O`. `+-` e `±` seguem diferentes.

**A métrica primária usa a semântica.** Erro só na literal é Tipografia. Cor errada da figurina tem contador próprio.

**Hífen:** o gabarito guarda a linha como impressa. Mede-se sobre a linha; a hifenização desfeita se mede só em Estrutura, na exportação.

**Ordem separada de caractere:** linhas casadas pela caixa, comparadas linha a linha. Ordem é só o Kendall. Sem caixa de linha, usar comparação flexível (FCA), e o JSON diz qual foi. Página inteira alinhada em sequência não entra em tabela nenhuma: a tabela de 05/11 do relatório é só exploratória.

### O que se pode afirmar

**Intervalo padrão.** Por livro, Clopper-Pearson com `N_ef = N / DEFF`. Até o livro ter 20 páginas, **DEFF 2 para tokens, 4 para caracteres** (exploratório, 05/11: 1,0 a 1,1 e 3,5 a 4,6, com 6 ou 7 páginas). Com 20 ou mais, o DEFF medido por página, nunca abaixo de 1,5. Com zero evento, bootstrap é proibido.

| Tokens no livro, sem erro (DEFF 2) | Pode-se afirmar |
|---|---|
| 300 | menos de 2 % |
| 600 | menos de 1 % |
| 1.200 | menos de 0,5 % |
| 3.000 | menos de 0,2 % |

**O que a soma significa.** Tokens de livros diferentes só se somam para dizer "**nestes** livros" (DEFF entre livros, exploratório: 15). Toda tabela traz os livros um a um. **Para outro livro não se afirma nada:** com zero falha em K livros, até 1 − 0,05^(1/K) dos livros ainda podem falhar: 45 % com K = 5, 26 % com K = 10.

**Aprovar um alvo:** o limite superior unilateral de 95 % fica abaixo dele; não se exige zero erro. Com limite maior e estimativa menor, o resultado é "**não decidido**", e não "reprovado".

**Hoje** há 395 tokens de lance com verdade humana, de quatro livros, e sem auditoria (§3.2).

### Alvos

São hipóteses de trabalho, e só para orientar. A linha de base abaixo é exploratória, do conjunto de ajuste. A da prova sai de PP2, e os alvos são revistos ali, com registro.

| Alvo | Linha de base | Alvo, **na prova, se houver** |
|---|---|---|
| Silencioso em lance, por token, nestes livros | Seirawan: 5,8 % com a fila, a 59 % de marcas | limite superior ≤ **1 %**, com `m` ≤ 15 % e N ≥ 1.600. Admite até 6 tokens silenciosos |
| Erro bruto em prosa | medir em PP2 | definir em PP2 |
| Figurina errada | 9 de 498 (IC 0,8 % a 3,4 %), 8 numa página | não piorar mais que 0,5 ponto |
| Marcas | 59 % dos tokens no Seirawan | ≤ 15 % dos tokens |
| Precisão das marcas | medir por token | ≥ 50 %, **também em cada classe** |
| FEN inteiro exato | 7 de 7 (IC 59 % a 100 %), sem conferência cega | 30 por livro sem erro, o que afirma ≥ 90 % por livro; amostrar só diagramas |
| Lado a jogar | 2 de 5 (IC 5 % a 85 %) | sinal em todo lado não dito pelo livro |
| Residual, por página revisada | não medido | medir primeiro; alvo depois |

O alvo de 1 % é o que a medida consegue decidir: 0,5 % exigiria cerca de 5.000 tokens. Volta a 0,5 % se o limite de 1 % passar com folga.

## 2. Princípios

1. **Evidência em vez de decisão.** Motor produz hipótese. Quem decide é uma regra medida, ou o revisor.
2. **Nada é reescrito em silêncio.** Toda troca automática deixa rastro visível e se desfaz. A legalidade **nunca** troca
   um lance sozinha: o livro pode ter erro de impressão.
3. **O revisor é o recurso caro.** Sinal que não melhora a precisão não entra.
4. **Medir fora do que se ajustou.** Regra ajustada no ajuste só vale depois da validação, e a prova só reporta (§3.2).
5. **Decidido não volta.** Manual, revisado e conferido nunca são trocados por motor. **Hoje isso é falso** para o revisado: Ctrl+R e a propagação o relêem (D-5).
6. **O miolo da revisão não muda sem medida.** Dois gestos por correção é o coração do programa (CA-F.1).
7. **Uma carga por vez.** A máquina já travou por memória: no máximo um motor pesado por vez, com orçamento de RAM
   declarado.
8. **O treino por livro continua sendo o diferencial.** Tudo aqui se soma a ele, sem substituí-lo.

## 3. A régua (R)

Sem ela, nada de leitura se pode falsear. **Vem antes de toda mudança de leitura.**

### 3.1 R-1. Medida por classe e erro silencioso (P1, Confirmado)

Em texto, `ferramentas/medir.py` só dá o CER do corpo. A perícia em `checkup-2026-11/experimentos/` provou a ideia, mas é script
solto.

**Fazer.** Uma ferramenta `ferramentas/medir_motores.py`, com teste: lê o gabarito, classifica cada token, e devolve os
quatro números da §1 por classe, por livro e por motor. O alinhamento é um só, com teste. O JSON não leva texto de
livro.

- **CA-R1.1.** Dado um gabarito e uma leitura fabricados, com erros conhecidos de cada classe, a ferramenta conta cada um
  na classe certa.
- **CA-R1.2.** Num gabarito fabricado, com um erro de cada tipo: sem marca forte no token, conta como silencioso; com marca forte, não; com só o realce de hoje, conta como silencioso.
- **CA-R1.3.** Lance errado com forma válida sai à parte, como gravidade máxima.
- **CA-R1.4.** Toda medida grava o commit do programa, o commit e o estado sujo do core, o SHA-256 do modelo, as versões dos motores e o N de cada classe.
- **CA-R1.5.** Marcar todos os tokens dá silencioso 0 e `m` = 100 %, e o relatório mostra os dois.
- **CA-R1.6.** Uma tabela de 60 tokens rotulados à mão, com figurina, letra, número, variante entre parênteses, `±` colado, roque, promoção e tabela, é classificada sem erro. Roda com `RDTBC` e com `KQRBN`: `Rf1` é rei numa e torre noutra.
- **CA-R1.7.** `medir.py` e `medir_motores` usam as mesmas `normalizar` e `classificar_token`. Os scripts de `experimentos/` não são importados por nada.

### 3.2 R-2. Conjuntos de ajuste e de avaliação (P1, Medido)

`tests/verdade` tem 213 linhas verificadas, um livro, nenhuma figurina. Os gabaritos de Darcy e Yusupov têm 0 linha
verificada. O `corpus_v2` do core tem 4 páginas revisadas de 3 livros.

**Dois níveis de gabarito:**

| Nível | Origem | Custo | Limite |
|---|---|---|---|
| **G1** humano | `tests/verdade/xv`; `benchmarks/corpus_v2` do core; o que o usuário verificar | Alto | Pouco |
| **G2** camada digital | Dvoretsky e outros com camada tipográfica aceita pela régua, renderizados | Baixo | Imagem limpa |

**G2 não aprova alvo, não entra em intervalo e não ajusta a fila.** Serve para testar a ferramenta e contar figurinas raras.

**Auditoria do gabarito (obrigatória no G1).** O rascunho vem do programa, logo o erro plausível fica nos dois lados e conta como acerto. A conferência cega exigida pela §15.2 nunca rodou nos 14 gabaritos. Numa conferência contra a imagem, em 05/11: **8 erros em 2.077 tokens verificados do Seirawan (0,39 %, IC 0,17 % a 0,76 %), do tamanho do alvo de prosa,** sempre a favor do programa. Antes do primeiro uso:

1. **Dupla leitura:** a ferramenta lista os tokens em que o gabarito difere de uma leitura independente, mostra o recorte e as formas em ordem sorteada, sem dizer de onde vêm, e o usuário decide.
2. **Fiapo de legalidade:** todo token de lance com posição conhecida é validado. O ilegal volta ao usuário: ou é erro de impressão, registrado, ou é erro do gabarito.
3. **Amostra cega:** 1 página sorteada por livro (2 no nível C de Dec-5), transcrita do zero, pelo menos 7 dias depois da verificação. Resultado por token e classe. Avisos lembra quando liberar.

A medida grava `erro_do_gabarito_estimado` por classe. **Se ele não for menor que 1/5 do alvo da classe, o número sai como "limitado pelo gabarito" e não aprova nenhum CA.**

**Três conjuntos, por página sorteada com semente registrada:**

| Conjunto | O que entra | Para quê |
|---|---|---|
| **Ajuste** | Seirawan; Dvoretsky; as 4 páginas do `corpus_v2` | Livre: olhar erro a erro |
| **Validação** | 4 páginas por livro de avaliação | Decide L-3 a L-6 e F-1. A ferramenta só mostra totais por classe |
| **Prova, opcional** | 2 páginas inteiras por livro e só as linhas de lance de outras páginas, até 400 lances por livro | Não decide nada. **No máximo 3 usos.** Se um número dela levar a mudar uma regra, essas páginas vão para a validação e se sorteiam outras |

**Livros de avaliação, quatro,** com PDF e slug fixos, na ferramenta do sorteio: `aagaard` = *Grandmaster Preparation – Calculation*; `nunn` = *Secrets of Rook Endings*; `yusupov` = *Chess Evolution 1*; `darcy` = *A Estratégia no Xadrez* (português, notação em letras, outra editora, nenhum motor o leu em 05/11, e já tem estrutura rotulada). O usuário pode trocar por um que queira converter, antes do sorteio. **Só o Darcy testa outro livro de fato;** nos outros, a conclusão vale "para páginas novas destes livros".

**Sorteio:** só páginas de corpo, estratificadas pela contagem de lances, na proporção do livro. Excluir as vizinhas (5 páginas) das já vistas e as de `benchmarks/candidatos_v2`. **Tabela é estrato próprio e nunca se soma à prosa.** O `corpus_v2` escolheu páginas pela dificuldade: não representa o livro.

**Tamanho:** ver Dec-5. Só o nível C tem prova. Nas páginas extras dela, verificam-se só as linhas de lance: uma linha entra se o programa ou a opinião têm nela forma de lance, ou se ela está entre duas linhas assim, e `m` sai só das páginas inteiras.

**Verificar dentro do programa.** As páginas sorteadas abrem numa cópia do projeto, com Realce desligado e Seguir ligado, para a marca não dirigir o olho. O usuário corrige no Documento, linha a linha. Ao fim, `rotular.py importar-do-projeto --livro X` grava o texto no gabarito e marca as linhas. O tempo sai do registro de eventos. O `.txt` continua existindo, sem ser o caminho indicado. **A dupla leitura é uma grade, como a Galeria:** recorte, as duas formas em ordem sorteada, uma tecla decide, 20 por tela. Token com figurina fica fora, porque o outro motor não tem a classe.

- **CA-R2.1.** Toda leitura de validação ou de prova acrescenta uma entrada a `docs/medidas/uso-da-avaliacao.json`: commit, conjunto, pergunta, hipótese, decisão. Na prova, a quarta entrada do mesmo sorteio reprova, e a saída nunca traz lista de erros.
- **CA-R2.2.** Dado o Dvoretsky, o gerador G2 produz linhas com figurinas mapeadas e relata o que descartou, por fonte. A conferência à mão cobre 30 linhas sorteadas e até 5 ocorrências de cada símbolo.
- **CA-R2.3.** Nenhum texto de livro entra em repositório público (depende de Dec-1).
- **CA-R2.4.** Dado um gabarito fabricado com erro plantado num token em que os motores discordam, a dupla leitura o lista. Dado um lance ilegal plantado, o fiapo o lista.
- **CA-R2.5.** `medir_motores` recusa gabarito sem o registro da auditoria, salvo com `--provisorio`, que aparece no JSON.
- **CA-R2.6.** Num projeto fabricado, corrigir duas linhas no Documento e rodar `rotular.py importar-do-projeto --livro X` grava o texto, marca `texto_verificado` só nelas e sobe `verdade_versao`. A grade decide 20 pares por tela, por tecla, sem dizer a origem de cada forma.

### 3.3 R-3. A catraca no portão (P1, Inferido da leitura dos testes)

Nenhuma camada reprova por qualidade de OCR. Sem o `custom_model.pth`, tudo deve seguir verde.

**Fazer.** Um teste `livro_real` sobre as 7 páginas de texto do Seirawan: **uns 70 s**, sem a capa, que sozinha leva uns 6
minutos, pela conta (L-9). Ele reprova se piorar: CER por classe, casas erradas, diagramas, linhas perdidas. Mais uma asserção de
que a rede carregou.

- **CA-R3.1.** Com o modelo ausente, o portão reprova.
- **CA-R3.2.** Com o `cer_corpo` medido acima da catraca, o portão reprova, e o teste prova isso sobre um resultado fabricado.
- **CA-R3.3.** A catraca é chave de `(sha do gabarito, sha do modelo, commit do core, versão da normalização)`. Mudou a chave: a ferramenta remede a referência antiga sobre a nova e só compara essas duas. Por classe, tolerância de 2 tokens, e de 0 em linhas perdidas e casas erradas. Passar da tolerância exige registro no commit, com o ganho na validação que o justifica.
- **CA-R3.4.** Mudança no commit do core desde a medida de referência aparece como aviso no portão.
- **CA-R3.5.** Duas rodadas no mesmo commit dão JSON igual, salvo o tempo. Se não derem, a catraca não vale até achar a causa.

### 3.4 R-4. O residual (P2, Hipótese)

A métrica primária supõe que o revisor corrige o marcado e só. O único estudo citado achou que metade dos erros segue sem correção. **Esse nexo é a hipótese central do plano,** e por isso vem cedo: no fim de M5.

**Referência: releitura cega de 3 páginas sorteadas, uma vez, no fim de M5.** Pelo menos 7 dias depois de dar o trecho por pronto, o usuário transcreve do zero, sem ver a leitura nem as marcas. A diferença é arbitrada contra a imagem. **O erro achado é corrigido no projeto,** logo não há trabalho perdido. A mesma amostra dá a fração dos erros marcados que foram corrigidos e a dos não marcados. Custa uns 25 min por página. Repetir num livro é escolha dele. Ao abrir o projeto, a partir do 7.º dia, Avisos diz: "Releitura de 3 páginas liberada. Ferramentas ▸ Releitura cega."

**Derruba:** erro marcado corrigido em até 80 % (roadmap, fim de PP5).

**Sem injeção de erros:** plantar erro no livro de quem teme o erro silencioso não vale o que mede.

- **CA-R4.1.** A ferramenta sorteia as páginas e compara a releitura cega com o projeto sem mostrar a leitura. Com erros plantados num projeto fabricado, conta os certos por classe.

## 4. A leitura (L)

### 4.1 L-1. Hipóteses, em três partes (P1, Confirmado)

O `Leitura` guarda um caractere, uma fonte e uma confiança. A margem do k-NN é descartada (`leitor.py:178`), embora `box.margem` já seja campo gravado. O palpite abaixo do limiar vira `""`.

**a) Medir sem mudar o programa.** `ferramentas/medir_hipoteses.py` lê as páginas do ajuste com o leitor de sempre e pergunta `rede.predict_topk(recorte, k=3)` a cada box. Sai `cobertura@3`, em T0 e T1, com o top-3 **mais** a classe lida (o veto de proporção pode escolher até a 12.ª). Classe de vários caracteres conta se o certo for substring, e a medida diz quantos casos há. **Derruba a parte c,** sem tocar no programa: limite inferior abaixo de 40 %.

**b) A margem deixa de ser jogada fora (sempre).** `leitor.Leitura` ganha `margem`; `_ler_global` passa `leitura.margem`; `por_leitura` grava `box.margem`. Para a rede, um invólucro em `predictor=` chama `predict_topk(k=2)` no lugar de `predict`, numa passada só, e a margem é `1 − p2/p1`. Para o livro, a margem e a 2.ª classe saem do `distancias` de `PadroesDoLivro.ler`. **O formato não muda.** O glifo lido pelo livro não passa pela rede.

**c) Top-3 sob demanda, só se a parte a passar.** Operação `hipoteses_recortes` no servidor, no molde de `sugerir_recortes`: recebe os recortes dos tokens de lance, devolve os candidatos, e fica na memória da página. **Sem arquivo por `gid`:** o `gid` pode voltar a ser alocado depois de uma queda (`projeto.py:576-578`), `ajustar` mantém o `gid` com caixa nova, e o arquivo dobraria o projeto (uns 135 MB em 300 páginas, por conta). A 2.ª classe do k-NN global fica fora: exigiria outra busca.

- **CA-L1.1.** Ligar b não muda caractere, fonte nem confiança (golden das 7 páginas).
- **CA-L1.2.** O tempo por página sobe menos de 5 %, **em T0 e em T1**: mediana de 5 rodadas alternadas A/B, na máquina cadastrada, sem outra carga.
- **CA-L1.3.** `cobertura@3` é a fração dos tokens errados do ajuste em que, em cada caractere errado, o certo está entre os candidatos, **contando faltas e `sumiu` como não cobertos**. Sai somada, com o intervalo padrão, e por classe só com pelo menos 50 erros.

### 4.2 L-2. A segunda opinião (P1, Medido por linha; de página, a medir em CA-L3.1)

Sem uma leitura independente, o programa não sabe quando errou com confiança alta. **O código já tem quase tudo:** `tesseract_pagina_detalhada_conf` lê a página com palavra e caixa; `camada.py` já é uma segunda opinião alinhada por caixa; `sessao.alinhar` já alinha por caractere com custo de espaço.

**O que o motor devolve.** `opiniao.ler_pagina(cinza, idioma) -> [PalavraDaCamada]`: caixa em pixels da página, texto e confiança.

**Onde roda.** Uma thread `opiniao` no processo da interface; o OCR é um `subprocess`, e a página vem do processo de render que já existe. **Sem processo Python novo.** `OMP_THREAD_LIMIT=1`. Uma página por vez. Nunca enquanto o lote ou um F5 estiverem em curso: espera, e retoma sozinha. Sem usar a fila de tarefas da janela, que travaria a edição. Motor que passa do prazo é morto, e a página fica sem opinião.

**Quando.** Entra na fila em `pagina_reconhecida`, `pagina_do_lote` e ao abrir uma página lida sem opinião, esta na frente. Só páginas com algum glifo que não seja `manual`, `revisado` ou `nativa`. Em projeto só de leitura: lê, mostra, não grava.

**O que grava.** `opinioes/p<pid>.json`, JSON compacto, pela própria thread, que é do processo dono da pasta. Arquivo descartável, fora de `paginas/`, uns 6 MB em 300 páginas, por conta. **A chave é da imagem, não da linha:** `sha1` da receita da entrada (`fonte`, `pagina`, `quadro`, `giro`, ângulo, `borrachas`), mais motor, versão, idioma e configuração. Editar glifo, dividir, juntar, F5 e desfazer não invalidam. Borracha, corte, giro e ângulo invalidam.

**Como compara.** `opiniao.comparar(pagina, palavras) -> EvidenciaDaPagina`, função pura, sem disco. Cada glifo cai na palavra da opinião que contém o centro dele. Os glifos de uma palavra do programa e as palavras da opinião que eles tocam formam um grupo. No grupo, compara-se o texto **sem espaços** (`sessao.alinhar`, depois de NFKC na opinião e `tx.normalizador` no programa): igual é concorda, e diferença só de espaço é "espaço". Fora disso, o alinhamento dá `gid` a `gid` qual caractere difere. **Sem opinião:** glifo `manual`, `revisado`, `nativa`; virtual; palavra com figurina, ou com dígito, salvo o medido em CA-L3.1.

**Como chega à tela.** `executar.na_interface(...)`, com o teste da `geracao`. A marca de agora não muda sob o revisor: a fila nova vale na próxima decisão.

**Quando o texto muda:** o glifo editado é comparado de novo com a mesma palavra. **Refazer só quando a `_chave` da página muda,** num dict em memória.

**O que não faz.** Não toca em `BoxEntry`. Não entra no JSON da página. Não ensina padrão. **Não entra em `contexto.pendentes`** (F-1).

**PP-OCRv6.** Só se Dec-2 o aprovar. `subprocess` do `python.exe` de um venv próprio, com recortes por linha pelo `stdin` e texto pelo `stdout`, e a mesma `EvidenciaDaPagina`.

**Custo, a medir em CA-L3.1.** De 3,5 a 15 min em 300 páginas, pelo registro do core. Por linha, de 22 a 58 min (relatório). **A precisão do Tesseract de página não foi medida.**

**Localizar o motor:** `ABBY_TESSERACT`, depois `PATH`, depois os dois caminhos de `Program Files`. Versão e idiomas vêm de `--version` e `--list-langs`, com prazo, uma vez por sessão. `_idioma_tesseract` só mapeia `en` e `pt`: passar `spa`, `deu`, `fra`.

- **CA-L2.1.** Sem nenhum motor, o programa funciona como hoje; a etiqueta de F-4 mostra `sem 2.ª opinião`, e Avisos explica uma vez.
- **CA-L2.2.** Matar `tesseract.exe` no meio não muda a leitura, e a fila segue.
- **CA-L2.3.** Um `gid` manual ou revisado, inclusive pela fila Lances, não recebe marca.
- **CA-L2.4.** Na mesma imagem, a segunda rodada não chama o motor, mesmo depois de F5, dividir e desfazer. Com uma borracha, chama.
- **CA-L2.5.** `PICO_DO_MOTOR = {motor: MB}`, no código, escrito pela medida. Orçamento em `ABBY_ORCAMENTO_RAM_MB`, ou 2.500. Antes de subir: `psutil.virtual_memory().available` ≥ pico + 1.024 MB; senão, não sobe, e Avisos diz o motivo. Um vigia mata o motor que passar do orçamento. `psutil` passa a dependência. O Tesseract, leve, não passa por isso.
- **CA-L2.6.** Tabela de alinhamento: `1.e4` × `1. e4` não marca lance; `ﬁm` × `fim` concorda; box `xf3` × `xf3` concorda; `□` × `a` sugere `a`; `rn` × `m` marca os dois glifos, sem sugestão em lote; página nativa não chama o motor.
- **CA-L2.7.** Enter em p95 ≤ 100 ms com evidência carregada, sem abrir arquivo (teste com contador de `open`).
- **CA-L2.8.** Trocar de projeto com a opinião em curso não grava nem mostra nada dela no novo. Os testes usam um executável falso, por `ABBY_TESSERACT`.

### 4.3 L-3. Qual motor (P2, Medido; Dec-2)

| Motor | A favor | Contra | Papel proposto |
|---|---|---|---|
| **Tesseract** | Instalado, leve, 0,15 s por linha, treino por livro documentado, alternativas por caractere | Pior que o PP-OCRv6 em CER nos 5 livros, e em prosa em 4 de 5. Em lance, por token, precisão de 38 % no Seirawan e 46 % nos livros com figurinas, contra 100 % e 88 % (exploratório) | **Padrão provisório, por custo.** Não marca lance até passar por CA-L3.1 |
| **PP-OCRv6** | Melhor sinal medido: 98,4 % e 88,3 % no Seirawan, por caractere | 2 GB de RSS, dependência pesada que traz outro OpenCV, sem figurinas, sem alternativas documentadas, 0,39 s por linha | **Opcional**, em venv próprio, ligado por livro |
| **EasyOCR** | Já está no core | Pior que o PP-OCRv6 em CER nos 5 livros; último lançamento em 2024 | Fora |
| **Cadeia do core** | Existe; 0,97 % no Seirawan, sem sobras, na régua do E0 (não comparar com as outras linhas) | Privados, sem treino por livro; não medida em lance | Fora; mantém-se como referência de medida |

**Em livro com figurinas, nenhum destes marca token com figurina:** para eles, o sinal vem de X-1.

- **CA-L3.1.** **Só com a ferramenta, antes de integrar.** No ajuste, fixar a configuração de cada motor num varrimento pequeno e registrado: `tessdata` `fast` e `best`, ampliação ×1 e ×2, `psm` 3, 4 e 6 **de página**, alinhados por caixa, com `OMP_THREAD_LIMIT=1` e sem a segunda passada; `psm` 7 e 13 **por linha**, como referência. O modo de página é o padrão se a revocação em Prosa ficar a menos de 5 pontos do melhor por linha. Depois, na validação, por classe e por token, em `m` igual: revocação, precisão, tempo e RAM. **O padrão é o motor mais leve cuja precisão em Lance fique ≥ 60 % e cuja revocação em Prosa fique a menos de 5 pontos da melhor.** Se nenhum leve passar em Lance, ele vale só em tokens sem forma de lance.

### 4.4 L-4. Consenso como sugestão (P2, Medido; Dec-3)

**Regra medida, com Tesseract e PP-OCRv6:** onde os dois concordam entre si e discordam do programa, a leitura deles é a sugestão. Token com figurina não muda. **A regra de CA-L4.2 é mais restrita** (protege também o lance de forma válida) e não foi medida.

**Fazer.** A sugestão aparece na fila e no Documento. **Só entra no lote a sugestão 1:1:** o mesmo número de glifos e de caracteres, sem box de vários caracteres, sem espaço a mais ou a menos, nenhum glifo com figurina, nem lance de forma válida. O resto é sugestão por palavra: uma tecla abre a sessão do Documento com o texto proposto, e a confirmação é a de sempre. A aplicação automática fica para depois da medida (Dec-3).

**Aplicar.** `edicao.trocar_varios(pagina, {gid: char})`: uma lista nova de `Box`, com `BoxEntry` copiado, `source = FONTE_OPINIAO`, confiança mantida, `amostra = None`, `revisado = True`. `FONTE_OPINIAO` entra em `FONTES_CONFIRMADAS`, sai de `volta_pelo_contexto` e ganha grupo próprio em `busca.grupo_da_fonte` e nome em `NOMES_DAS_FONTES`. Um `_mudou`: um passo do desfazer. **O caminho de hoje (`ss.aplicar`) não serve:** põe `FONTE_MANUAL` e pode recusar no meio.

**O lote só existe com dois motores concordando, logo só com Dec-2 b.** Com um motor só, a discordância vira dúvida, e a sugestão é por palavra (F-4). Ctrl+Shift+S abre a prévia em Resultados: antes, depois, caixa de marcar, `Aplicar 12` (Enter). Andar na lista move a Imagem e a Linha até a palavra. Só na página. Esc fecha sem aplicar. Ctrl+Z: "Desfazer: 12 sugestões". V mostra a origem `2.ª opinião`, e a exportação conta quantos glifos saíram assim.

- **CA-L4.1.** O glifo aceito sobrevive a F5, Ctrl+R, lote com "refazer" e dez Enters na página, com o mesmo `char` e `FONTE_OPINIAO`; nenhuma amostra nova; a exportação traz o aceito, sem caixa pela altura. **Não treina,** a menos que o revisor dê Enter nele.
- **CA-L4.2.** Nenhum token com figurina nem lance de forma válida muda pelo lote.
- **CA-L4.3.** Unidade: o **token alterado pelo lote**, só 1:1. Certo → errado: era certo e ficou errado, contra o gabarito **auditado**, arbitrado contra a imagem. Na validação, com tabela como estrato separado, em pelo menos 600 tokens alterados: limite superior ≤ 1 %. Se a tabela passar de 5 %, o lote não vale em tabela.
- **CA-L4.4.** Um Ctrl+Z volta `char`, `source`, `confidence` e `revisado` de todos.
- **CA-L4.5.** A busca por fonte acha o aceito em "opinião", e não em "rede".

### 4.5 L-5. O k-NN global (P2, Medido)

Lê 11,5 % dos caracteres e faz 52 % dos erros no Seirawan. A confiança não é probabilidade (erro de calibração 0,391).

**Experimento, um livro de ajuste, depois avaliação:** (a) subir o limiar de 0,30; (b) só aceitar se concordar com o top-3 da rede; (c) deixar sem leitura, com palpite. **Derruba:** se o erro total subir ou os vazios crescerem mais do que os erros somem.

- **CA-L5.1.** A variante escolhida passa pela regra de "melhorou" do roadmap, na validação, sem piorar as figurinas.
- **CA-L5.2.** Mudar o padrão não muda livro existente: `asdict(dados)` já grava todos os limiares. Variante booleana não entra em `Limiares`, cujo teste de tipo faria o projeto não abrir: fica em constante.

### 4.6 L-6. Consertos pequenos, cada um com medida (P2, Confirmado)

| Id | Conserto | Onde | Derruba |
|---|---|---|---|
| L-6a | Árbitro de corte: rede crua, com altura, numa escala só | `leitor.py:201-204`, `box_service.py:444-454` | Gestos de dividir e juntar e CER não mudam |
| L-6b | Passar `idioma` à cadeia, ligando a máscara de alfabeto | `leitor.py:174-177` | CER piora ou figurina some |
| L-6c | Passar a `escala` depois das áreas | `zonas.py:827`, `servidor_de_leitura.py:162` | Nada muda em casas nem em rótulos |
| L-6d | Avisar de box fora de área, sem apagar | `zonas.py:780` | — |
| L-6e | Rever `conflito = 0,10` (dispara só com `d ≤ 200`) | `dados_do_projeto.py:48` | Sem conflito novo real na amostra |

- **CA-L6.** Cada conserto entra sozinho, com o antes e o depois no mesmo JSON, pela regra de "melhorou" do roadmap. Se não melhora, não entra.

### 4.7 L-7. Segmentação (fora do plano)

`m` vira `1n` no Aagaard, e o corte é irreversível antes de ler. Refazê-lo é grande e não tem evidência de que se pague: a prosa é de gravidade baixa, e a sugestão por palavra cobre o caso. Reabre se PP5 mostrar que gestos de dividir e juntar pesam no tempo por página.

### 4.8 L-8. Treino (P2, a medir)

- **Holdout honesto da CNN.** O "99,76 %" não separa por livro (`core/avaliacao.py:52`), e 64 classes não têm validação, entre elas `!!` e `??`. **Reavaliar o modelo atual com separação por livro** é barato e dá o número real.
- **Ajuste por livro do motor de linha:** fora do plano. Treino pesado na máquina que trava, para prosa de gravidade baixa. O manual do Tesseract usa ± como exemplo: reabre se os sinais pesarem na medida.

- **CA-L8.1.** O relatório do holdout por livro lista recall por classe e as classes sem amostra.

### 4.9 L-9. Página que não é texto (P2, Medido)

A capa do Seirawan inventa 1.442 linhas e 5.429 pendentes, e custa uns 6 minutos, pela conta. `core.livro` marca `pagina_de_imagem` só quando a segmentação não acha box nem tabuleiro: não há classificador para reaproveitar, e o app não usa o campo.

**Fazer.** Classificar antes de segmentar, em `servidor_de_leitura.ler_pagina`, só em página **sem áreas**, por uma função de `abbychess/tipo_de_pagina.py`, a partir da densidade de componentes. Página de imagem: `PaginaLida` sem boxes, com `imagem=True`, e `aplicar_lida` põe uma `Zona` da página inteira, função `figura`, e o estado `reconhecida`. **Nenhum estado novo, nenhum formato novo:** um valor novo em `Estado` isolaria a página como corrompida em versão anterior. O lote a pula como lida, com zero pendentes. "Forçar a ler" é o que já existe: mudar a função da área para texto e dar F5. `segmentar_com_zonas` volta sem segmentar quando nenhuma área é de texto ou diagrama. A exportação escreve a área `figura` de página inteira como recorte, e o relatório a lista em `recortados`. **Derruba:** se o classificador errar em página de texto (CA-L9.2).

- **CA-L9.1.** A capa do Seirawan fica assim, em menos de 5 s, com zero pendentes, também no segundo F5.
- **CA-L9.2.** Nenhuma página com gabarito de texto de Seirawan, Darcy e Yusupov cai nele.
- **CA-L9.3.** Exportar a página de imagem a põe inteira, como figura, e o relatório a lista. O golden confere.

**Nunca em silêncio.** O fim do lote diz: `230 páginas lidas; 11 tratadas como imagem (ver)`, e o link abre a lista em Resultados. A gaveta tem o filtro "Tratadas como imagem". O Documento da página mostra: `Página tratada como imagem. Ctrl+Shift+T lê como texto.` Essa tecla muda a função da área e relê, num passo só do desfazer.

- **CA-L9.4.** A lista e o filtro trazem a capa do Seirawan; a tecla a lê como texto, e Ctrl+Z volta.

## 5. A fila (F)

### 5.1 F-1. Marcas por escore, dentro de um orçamento (P1, Medido por caractere; por token, exploratório)

Precisão de 9,3 %, 18 % dos boxes marcados (relatório, §4). A régua de 0,90 compara escalas diferentes. O padrão do livro fica isento pela confiança.

**Fazer: ordenar e cortar são coisas separadas.**

**Ordenar.** Regressão logística com **no máximo 8 parâmetros**, sobre: discordância (por motor), fonte, `logit(confiança)` por fonte, margem, token com figurina. Um modelo só, com a classe por termos fixos; **nada por classe com menos de 50 tokens errados no ajuste**. Ajuste em validação cruzada **deixando um livro de fora**. Sem isotônica: o corte é por posto, e calibração monótona não muda a ordem.

**Cortar: por orçamento.** A discordância vira marca forte nos `m` % maiores de cada página, com `m` fixo no ajuste. □ e lance ilegal sempre são marcados e não contam no orçamento. **O escore decide quem é marcado, não a ordem de visita:** ela é a de leitura. Probabilidade absoluta não aparece na tela nem decide corte entre livros: P(erro | concorda com o PP-OCRv6), por caractere, variou **190 vezes** entre livros (0,0003 no Seirawan, 0,058 no Nunn).

**Onde mora.** `contexto.pendentes` não muda de sentido: é o que a leitura e a propagação podem reler, e o que `livro.json` conta. Se a discordância entrasse nele, um glifo de rede a 0,99 seria reescrito pelo padrão no próximo Enter. A evidência é outro objeto, `EvidenciaDaPagina`, sem Qt, que `FilaDaPagina` guarda por `pid`: `{gid: (motivo, sugestão)}` e `{gid: escore}`. É carregada **uma vez**, ao abrir a página, ou entregue quando a opinião chega. **`fila()` nunca abre arquivo.** O escore é `abbychess/escore.py`, com coeficientes em constante, escritos por `ferramentas/ajustar_fila.py`, só com `numpy`. Na interface, só soma e `exp`: sem torch (`docs/SPEC.md:726`). 

**No livro.** `do_modelo` acrescenta `"fortes"`, da evidência em memória. `proxima_com_pendentes` e o contador do escopo livro seguem F-4: só as fortes na página com 2.ª opinião; sem ela, os pendentes. O relatório de exportação traz as duas contagens.

**Discordância é a variável principal fora dos tokens com figurina;** neles, nenhum outro motor opina, e o sinal é a confiança e a legalidade (X-1). O padrão do livro deixa de ser isento: amostra com distância alta ou discordância entra.

**Recalibrar por livro:** não agora. Sem dado de T1 nem páginas auditadas, não há com o quê. Quando houver 10 erros auditados, só o intercepto. Em página só revisada, o rótulo depende da marca, e o modelo aprenderia que o não marcado está certo.

**Treino por livro:** medir em T0 (padrões vazios) e T1 (padrões ensinados nas páginas anteriores do mesmo livro). A fonte `livro` só entra no modelo com dado de T1: hoje não há nenhum.

**Qual fila abre:** ver F-4. Isso respeita o CA-F.1.

**A evidência não é sobre a métrica primária** (relatório, §4): em prosa o ganho é claro; em lance, pode piorar. Por isso o CA é por classe. **Derruba:** CA-F1.1 (a). Qual fila abre: F-4.

- **CA-F1.1.** Curva `(m, silencioso @ m)` por token e por classe, com a fila de hoje cortada no mesmo `m`, mais o ponto real da fila de hoje, no `m` dela. Na validação, em `m` = 10 %: **(a)** em Prosa, a nova deixa pelo menos 20 % menos silenciosos, pelo contrato do roadmap, item 6; **(b)** só no nível C de Dec-5, em Lance e em Sinal: limite superior da diferença ≤ +0,5 ponto; **(c)** nenhum livro piora em Lance mais de 1 ponto. **No nível B, (b) não tem poder: a fila nova vale só fora dos tokens de lance.** O ponto de parada de M5 mostra também a troca real: silenciosos na fila nova contra a de hoje no `m` dela.
- **CA-F1.2.** Marcas ≤ 15 % dos tokens, na validação; na prova, se houver.
- **CA-F1.3.** Sem opinião instalada, a fila é a de hoje.
- **CA-F1.4.** Na fatia, os gestos não sobem (CA-F.1).
- **CA-F1.5.** A discordância num glifo `neural` não o relê no Enter nem no Ctrl+R: `char`, `source` e `confidence` iguais depois de dez Enters.

### 5.2 F-2. O realce volta a dizer algo (P2, Medido na tela)

A captura mostra quase todo `o` e `s` em laranja, enquanto `s0rte` e `materia1` não se destacam. Os fundos têm 1,25:1 contra o papel e 1,02:1 contra o da busca. **A captura de 05/11 é de livro com 0 amostras, o pior caso.**

**Fazer.** Marca forte, como em F-4, com sublinhado e cor que passa de 3:1. **Pode entrar em M3, antes da 2.ª opinião:** destaca □ e palavra desmentida por cima do realce de hoje, sem esconder nada.

- **CA-F2.1.** O fundo forte passa de 3:1 contra o papel e contra o da busca (teste sobre os tokens).
- **CA-F2.2.** Estado não depende só da cor: há traço diferente.
- **CA-F2.3.** Antes e depois, as capturas de CA-13.2 numa página de livro **já treinado**, com padrões ensinados.

### 5.3 F-3. Lances na tela (P1, Confirmado)

Lance bem formado e errado com confiança alta não vai à fila, nem ao realce, nem à verificação (`contexto.py:17`, `verificacao.py:9`, `documento.py:413-429`). Ao falhar, a validação acusa o diagrama.

**Fazer.** `Validacao.legais` já é o índice do primeiro rejeitado. `lances.gids_do_rejeitado(documento, diagrama, tabela) -> Tuple[int, ...]`, com `tabela = lances.tabela_do_projeto(projeto)`, anda nas `Palavra` do bloco com o mesmo `_tokens` e devolve os gids do lance, sem os do número. **`Lance` e `Validacao` não mudam.** O Documento pinta por `estados`, com um estado novo de desenho. A fila soma esses gids aos fortes, e o modo "Lances" entra em `ControladorDaFila.MODOS`. Ver X-1.

- **CA-F3.1.** Um lance ilegal numa linha com FEN tem o token pintado e entra na fila.
- **CA-F3.2.** O texto diz qual lado da dúvida pode estar errado: o lance ou o diagrama.

### 5.4 F-4. A sessão de revisão (P1, Hipótese: CA-F4.8 e CA-F4.10)

**As filas.** Ids em `ControladorDaFila.MODOS`: `duvidas` e `lances`, à frente dos cinco de hoje. **`lances` entra em PPL e `duvidas` em PP5:** até lá, F7 cicla Lances, Confiança, Ordem de leitura, Por caractere, Palavras desconhecidas, Diagramas por conferir. `lances` não entra em `DE_GLIFOS`: abre o editor Palavra. `ControladorDaFila.andar` está em cc 9: modo novo entra por tabela, sem `if`.

**Teclas.** **F4** vai direto a Lances; é global, com a exceção `{tecla: F4, widget: combobox, tipo: substitui, motivo: "F4 é da fila Lances; o filtro da gaveta abre com espaço ou clique"}`, e o motivo de `proximo_da_fila` e `anterior_da_fila` passa a dizer "com espaço ou clique". Enter e Ctrl+Enter da fila Lances **não são ações novas:** são `corrigir_palavra` e `corrigir_e_ensinar_palavra`, com o sentido da fila. O escopo continua na tecla de hoje. As teclas das telas vêm do YAML, pelo perfil ativo, como `vazios.py` já faz: os textos abaixo são do perfil padrão.

**Qual fila abre.** Página da amostra guiada: Confiança. Outra página com 2.ª opinião: Dúvidas. Sem ela: Confiança. **A evidência de F-3 e X-1 não conta aqui:** só acrescenta marca e lance à contagem de Lances. Escolher uma fila com F7 ou F4 fixa a escolha até fechar o projeto.

**Dúvidas.** Todas as marcas fortes da página, **em ordem de leitura**. No escopo livro, as páginas vão em ordem.

**Marca forte.** Glifo sem leitura (□); palavra que desmente a leitura; discordância com a 2.ª opinião, dentro do orçamento `m`; lance ilegal ou duvidoso (F-3, X-1).

**O realce mostra a fila ativa.** Em Dúvidas: só as fortes. Em Confiança: o realce de hoje, com as fortes destacadas por cima. Não há "marca fraca": quem quer ver o resto aperta F7. Vale para o Documento, a Imagem e a Linha.

**A 2.ª opinião na tela.** Etiqueta fixa na barra de status, à direita da fila:

| Estado | Texto |
|---|---|
| Sem motor | `sem 2.ª opinião` (a dica diz como instalar) |
| Lendo o livro | `2.ª opinião: 120/300` |
| Lendo esta página | `2.ª opinião: lendo esta página…` |
| Esperando o lote | `2.ª opinião: espera o lote` |
| Chegou | `2.ª opinião: 23 dúvidas` |
| Passou do prazo | `2.ª opinião falhou nesta página` |
| Sem memória | `2.ª opinião parada: pouca memória` |

Ao chegar, o Inspetor mostra uma vez, até a próxima página: "Chegou a 2.ª opinião: 23 dúvidas, antes 94. Você continua neste glifo." Item, cursor e rolagem não mudam.

**O Glifo em Dúvidas.** Uma linha nova, acima do campo, diz por que o item está ali: `O Tesseract leu: l` · `A palavra desmente` · `Ninguém leu`. **O campo traz a leitura do programa, nunca a sugestão,** salvo o palpite do □, como hoje. **Enter ensina o que está no campo, em toda fila de glifos, como hoje.** Shift+Enter só corrige. Aceitar a sugestão é digitá-la: 2 gestos. A leitura de outro motor sobre token de lance só aparece depois de CA-L3.1.

**Sugestão por palavra.** Ctrl+Shift+O abre a sessão do Documento com o texto proposto. Enter confirma, Esc restaura, e nos dois o foco volta ao Inspetor. O Enter do Documento vai à próxima da fila ativa.

**Lances (F4).** Anda, em ordem de leitura, pelas **linhas com forma de lance na leitura, e pelas que estão entre duas assim**. **Deve ser o item de maior efeito do plano, e não foi medido: a única garantia que não depende de motor é o olho, e hoje ele procura lance no meio da prosa.** A Linha mostra imagem sobre texto, com os tokens de lance sublinhados e os ilegais em forte. O Inspetor abre o editor Palavra com o texto da linha.

- **Enter, sem editar:** confere. Número, lance, xeque e sinal da linha ficam `revisado`, sem ensinar, e vai à próxima. Um Ctrl+Z por linha.
- **Editar e Enter:** corrige pela sessão (§6.3 da SPEC principal), e confere.
- **Ctrl+Enter:** como acima, e ensina os glifos que mudaram, como no editor Palavra de hoje. Sem glifo mudado, não ensina.
- **Alt+↓:** pula, sem conferir.

A prosa da linha não muda de estado.

**O que muda no modelo: quase nada, e nenhum formato.** Conferir é `edicao.revisar(pagina, gids)`, que já é um passo do desfazer e não troca a fonte. **Lance conferido** é o token de lance com todos os glifos `manual`, `revisado` ou `nativa`. **Aceito como impresso** não se grava: é o lance conferido que a validação rejeita, calculado de novo ao abrir. `do_modelo` acrescenta `lances_por_conferir` ao resumo da página; página sem a chave conta como desconhecida, e `recalcular` a preenche. **Efeitos de `revisado`:** saem de pendentes, do F6 e da coluna Rev. Não mudam `verificada`, a exportação nem o treino. **Exige D-5 com Dec-7 a:** com Dec-7 b, PPL para e volta ao usuário. **A fila Lances e o F-3 usam `classificar_token`,** com `lances._tokens` conferido sobre a mesma tabela de 60 (CA-R1.6): as duas regras não podem discordar.

**Lance ilegal.** Na linha, o motivo: `Bf3 não se joga aqui. Erro de leitura, de impressão ou do diagrama?` Enter sem editar quer dizer "está assim no livro": o lance fica como está, sem marca, e conta no relatório como `aceito como impresso`. Só o **primeiro** ilegal de cada sequência é marcado; os seguintes ficam `sem posição`, até uma âncora. Corrigir recalcula a linha em 500 ms.

**Estados vazios.** Nunca dizem "nada a revisar" enquanto houver lance por conferir: **sem marca não quer dizer conferido.**

| Situação | Texto |
|---|---|
| Dúvidas vazia, com lances por conferir | `Sem dúvidas nesta página. 40 lances não conferidos: F4 confere · Ctrl+T marca verificada` |
| Dúvidas vazia, lances conferidos | `Sem dúvidas, e os lances estão conferidos. Ctrl+T marca verificada` |
| Lances vazia, página sem lance | `Nenhuma forma de lance lida nesta página` |
| Lances vazia, conferidos | `Lances conferidos: 40, sendo 2 como impressos` |
| Fim do livro | `Sem dúvidas no livro. 410 lances por conferir (F4 + Shift+F7) · 14 diagramas (F8)` |

**Ctrl+T.** Conta só a fila ativa e os lances: `Aceitar 3 dúvidas como estão? 12 lances não conferidos. Enter aceita · Esc não marca`. O resto da fila antiga não entra na pergunta, e nada muda de estado.

**F6, gaveta e contador do livro.** Página com 2.ª opinião conta só as fortes; sem ela, os pendentes. Página com 2.ª opinião e sem fortes não para o F6. A coluna Rev. da gaveta e a etiqueta de U-3 usam a mesma conta.

**Página já verificada.** A 2.ª opinião não roda nela, e o F6 e os contadores a ignoram. **Decidido não volta.** Ferramentas ▸ "2.ª opinião nas páginas verificadas" roda em segundo plano e lista em Resultados as discordâncias, por página. **Um livro com 200 páginas revisadas pela fila antiga continua igual nessas 200.**

**Relatório de lances.** Ferramentas ▸ "Relatório de lances" lista em Resultados, por página: ilegais, sem posição, não conferidos, aceitos como impressos. Enter vai ao lance. A exportação traz as mesmas quatro contagens.

**Palavras na tela.** A interface diz **dúvida**, **2.ª opinião**, **lance conferido** e **glifo**. Não diz marca forte, escore, discordância, evidência, box nem pendente.

- **CA-F4.1.** Enter numa linha da fila Lances deixa `revisado` só os tokens de lance, número e sinal; nenhuma amostra nova; um Ctrl+Z volta tudo; vai à próxima linha.
- **CA-F4.2.** Lance ilegal aceito sem editar: sem marca depois de reabrir, e o relatório o conta.
- **CA-F4.3.** Cada linha da tabela de estados da 2.ª opinião aparece com o executável falso de CA-L2.8.
- **CA-F4.4.** A chegada da opinião não muda item, cursor nem rolagem.
- **CA-F4.5.** Numa página verificada com glifos não revisados, a opinião não roda, o F6 não para, e o estado não muda.
- **CA-F4.6.** Sem motor, o Documento em Confiança tem o realce de hoje, com □ e palavra desmentida destacados.
- **CA-F4.7a (PPL).** As linhas de Lances e, em Confiança, a tela vazia acrescida de `40 lances não conferidos: F4 confere`, nos dois perfis. Com lance por conferir, nenhuma tela diz "nada a revisar".
- **CA-F4.7b (PP5).** As linhas de Dúvidas e o fim do livro.
- **CA-F4.8.** Em 20 páginas reais, a mediana da fila Lances é de até 2 min por página, pelo registro de eventos (05/11: mediana de 12 linhas com lance, de 0 a 40). **Derruba:** acima disso, ela fica só com os ilegais. A estimativa de 1 min por página é hipótese.
- **CA-F4.9.** Ctrl+T numa página com 3 glifos da fila ativa e 12 lances não conferidos pergunta com esses dois números, e Esc não marca.
- **CA-F4.10 (PPL).** Numa cópia com as 7 páginas do Seirawan e as 4 do `corpus_v2`, lidas sem padrões e sem revisão, o usuário passa a fila Lances (umas 110 linhas, 10 min). `medir_sincronia` conta os tokens de lance errados antes e depois, contra o gabarito, por livro, com o IC. Sem erro plantado. O Seirawan já foi visto, e o `corpus_v2` não foi auditado: vale como indício, não aprova alvo.
- **CA-F4.11 (PPL).** `medir_sincronia` lista, por livro, os tokens de lance da verdade em linha fora da fila, e quantos deles estão errados. Se passar de 5 % dos errados, a fila inclui também a linha vizinha. Exploratório: 4 de 149 linhas ficam fora, com 5 de 42 tokens errados (12 %, IC 4 % a 26 %).

## 6. Xadrez (X)

### 6.1 X-1. Legalidade como evidência (P1, Hipótese forte)

Baird e Thompson relatam erro cerca de 30 vezes menor.

**Desenho.**

1. **Sementes:** FEN do diagrama, quando a linha o segue. Sem diagrama, `1.` abre a posição inicial **como hipótese**: vale se os dois primeiros lances são legais nela. No fim da página, o estado segue para a seguinte, numa passada de livro, se ela estiver lida. O JSON diz quantos tokens têm posição por semente.
2. **Sincronia:** número e `...` como âncoras. Número que já passou **rebobina** para a posição de antes daquele lance, buscando de trás para a frente; `(` e `)` empilham; `;` não encerra. Com mais de uma posição possível, o lance seguinte desempata, e sem desempate não há marca (o desenho de `core/notacao.py:661-691`). Metade do texto destes livros são alternativas sem parêntese. **Sem rebobinar (M2):** a posição só anda enquanto o número for o esperado. Número que volta, `(`, `;`, ou lance de lado errado: a posição se perde, e tudo fica `sem posição`, sem marca, até o próximo diagrama. **Nunca se marca lance sem posição.** PP7 troca essa perda pela rebobinada.
3. **Candidatos:** os lances legais da posição, pontuados por gid × letra do candidato, em `abbychess/decodificador_de_lances.py`, sem Qt. Sem hipóteses, `core.notacao.custo_da_troca`, com a confiança do box. Com hipóteses, a mesma conta, com o custo `1 − p`, se a letra está nos candidatos, e 1 se não. **Sem hipóteses a margem é pobre:** serve para ilegal e forma inválida.
4. **Saída:** melhor hipótese legal, segunda melhor, margem. **Margem pequena abre dúvida, mesmo com leitura legal.** Leitura ilegal vira marca forte. **Nada é trocado sozinho.**
5. **Onde roda:** nunca em `arrumar`, que roda a cada edição. Numa tarefa leve, ao abrir a página e depois de 500 ms sem editar; o resultado entra em `EvidenciaDaPagina`. No lote, ao fim.

**Derruba:** se a cobertura (tokens com posição conhecida) ficar abaixo de 30 %, ou se a margem não separar certo de errado.

- **CA-X1.1.** Em pelo menos 300 tokens de lance com posição conhecida, no ajuste: a top-1 acerta mais que a leitura, por pelo menos 5 tokens, com certo → errado ≤ 1 token. Depois, o mesmo na validação, antes de virar sugestão.
- **CA-X1.2.** O lance impresso errado (fabricado) fica como está, com marca.
- **CA-X1.3.** A cobertura sai no JSON de `medir_sincronia`, por livro; em PP2, também no de `medir_motores`.
- **CA-X1.4.** Variante aninhada e página que começa no meio da partida não geram marca falsa.
- **CA-X1.5.** `12...Ra6; 12...Ra7; 12...Nb6 13.Qc2` não gera marca falsa, e o lance 13 fica com posição.
- **CA-X1.6.** O Enter em página com X-1 fica em p95 ≤ 100 ms.
- **CA-X1.7.** O JSON da cobertura traz também os tokens com forma de lance longo (`e2-e4`), hoje não aceitos por `lances.py`.

### 6.2 X-2. Diagrama com o texto (P2, Hipótese)

Hoje só a primeira linha depois do diagrama é testada. Faltam: as duas orientações contra os lances; top-k por casa (`core/diagrama.py:1199`, ninguém usa); diagrama N + lances = diagrama N+1; xeque do lado que não joga.

**Derruba:** se os erros reais de FEN do gabarito não tiverem a posição certa entre as candidatas.

- **CA-X2.1.** Entre diagramas lidos errados, a sugestão recupera o FEN do gabarito sem piorar os certos. Medir em erros reais, além de perturbações.
- **CA-X2.2.** "Confiável pelos lances" diz quantas casas a validação cobriu.

### 6.3 X-3. Lado a jogar (P1, Medido)

Certo em 2 de 5. **Fazer:** sem o livro dizer, **não afirmar**. O estado é "lado não dito", com marca e uma tecla para definir (hoje exige Tab até os rádios). Testar o lado contra os lances, como evidência. Copiar FEN e a exportação usam o lado do primeiro lance impresso, se houver; sem isso, `w`, e o relatório lista os diagramas em que o lado foi presumido.

- **CA-X3.1.** Nenhum diagrama sem lado dito sai como "confiável".
- **CA-X3.2.** Ctrl+W e Ctrl+B definem o lado no editor, conferido contra o YAML.

### 6.4 X-4. Sinais (P2, Hipótese)

A legalidade não os protege. A CNN tem as classes (`±`, `⩲`, `!!`…), parte delas sem validação; `⨁ ⇆ ⟫` estão em `lances.py:85`, mas não são classes dela, e a classe `'č\t'` é lixo. Não se confirmou amostra nos modelos de fábrica dos outros motores, que erram de 3 a 4 vezes mais em símbolo (45 e 55 contra 15, em 247).

**Fazer.** Vocabulário de sinais por livro, ensinado na amostra. Métrica própria. Toda ocorrência de sinal em que a opinião não concorda vai à fila.

**Derruba:** se a marca nos sinais só trouxer falso alarme, porque os outros motores os erram quase sempre.

- **CA-X4.1.** A medida traz erro bruto e silencioso de cada sinal, com N.

## 7. Dados, confiabilidade e entrega

### 7.1 Dados (P1, Confirmado)

| Id | Problema | Fazer | CA |
|---|---|---|---|
| D-1 | "Não entendo" vira "corrompido" e tira a página do livro | **Ao abrir, O(1):** `Projeto.campos_do_box` é o maior `len(fields(BoxEntry))` que gravou; maior que o de agora: só leitura, com o motivo. `VERSAO_DA_PAGINA` não sobe sem `VERSAO` (teste). **Ao ler, de reserva:** `PaginaDeOutraVersao(OSError)`, que `_gravada` não isola. Contrato de `as_state` fixado por teste | **CA-D1:** com `BoxEntry` de 12 campos num core de 11, nada é movido, o projeto abre só para leitura, e `abrir()` não lê nenhum arquivo de `paginas/` |
| D-2 | Edição do diagrama some ao mudar de página | `_guardados[(pid, caixa)] = (fen_base, tabuleiro)` ao fechar. `abrir` devolve o guardado se `diagrama.fen == fen_base`; senão, descarta e avisa. Indicar "alterado". Fechar pergunta, por `_edicoes_resolvidas` em `DiagramasNaJanela` | **CA-D2:** editar, PgDn, voltar: a casa está lá; fechar com alteração pergunta |
| D-3 | Página nativa exporta ignorando as edições. **Sair dos boxes não serve:** apaga os diagramas e embaralha colunas e tabelas, porque o x é fictício (`nativo.py:77-80,131`) | Página importada **continua saindo da camada**, com as edições por cima: `nativo.remendar(extraida, pagina)`, por `difflib` sobre o texto sem espaços. Quebra, junção e parágrafo decididos e similaridade abaixo de 0,9 não se aplicam e vão ao relatório. Página aceita pela camada, mas lida por OCR e com glifo decidido, sai dos boxes | **CA-D3:** numa página nativa com diagrama, duas colunas e tabela, trocar uma palavra e apagar outra: o EPUB difere do sem edição **só** nelas |
| D-4 | Falha na camada descarta tudo, com só um `warning` no log | `continue`, e `camada_falhou` no relatório. A página importada que cai nos boxes não tem diagramas e tem x fictício: o relatório diz isso | **CA-D4:** falha num trecho mantém os outros, e Avisos diz qual |
| D-5 | Revisado é relido: `_preparar_reler` e `propagar` usam `com_os_revisados=True` (`ponte_de_leitura.py:170,355`). Glifo revisado pode trocar de caractere no próximo Enter. Vem da leitura do código: o teste vermelho vem primeiro | `reler_boxes` recebe a lista de quem não ler, e `com_os_revisados` sai. Se o teste não falhar, o item sai da spec | **CA-D5:** glifo `neural` revisado, confiança 0,5, padrão que o lê diferente: Enter, Ctrl+R e propagação não o trocam |

### 7.2 Confiabilidade (P1 e P2, Confirmado; C-1 Inferido)

| Id | Problema | CA |
|---|---|---|
| C-1 | Servidor órfão | **CA-C1:** matar a interface à força encerra o filho em até 5 s |
| C-2 | Sem log em arquivo, nem na interface nem no filho | **CA-C2:** erro solto e falha nativa deixam rastro em `%LOCALAPPDATA%\AbbyChessCraft\`, `app.log` e `leitura.log`, um por processo, sem rotação entre processos, com versão do programa, do core e do modelo |
| C-3 | Filho travado, vivo, fica 600 s por página. Prazo curto mataria leitura legítima | **CA-C3:** o filho manda `("vivo", id)` a cada 50 glifos. Um leitor falso que dorme para sempre no glifo 10 é morto em até 70 s, e o pedido segue a regra da queda |
| C-4 | Página que derruba o filho prende o lote; `reinicios` nunca zera | **CA-C4:** o filho manda `("comecou", id)`. Duas quedas no mesmo pedido: ele vira falha, e o lote segue. `reinicios` zera a cada pedido concluído. Pedido que não estava em curso não acumula queda |
| C-5 | A suíte não reprova erro logado | **CA-C5:** teste que loga ERROR sem a marca `erro_esperado` reprova |
| C-6 | 7 das 10 metas de desempenho sem corte; o CA-7.1 oscila | **CA-C6:** toda meta tem corte, pela mediana de N rodadas; meta que oscila tem o método revisto, sem ficar sempre vermelha |
| C-7 | Sem ponta a ponta com o filho até exportar | **CA-C7:** teste `processo`: PDF, lote, matar, retomar, reabrir, exportar, conferir |

### 7.3 Entrega (P1 e P2, Confirmado)

| Id | Problema | CA |
|---|---|---|
| E-1 | Inferido, não tentei: num ambiente limpo, instala e não roda (faltam `chess` e `torch`). Há três `opencv` no mesmo `cv2`, e `chess` junto de `python-chess` | **CA-E1:** venv limpo, sem `--system-site-packages`, com o lock e **um** OpenCV (`opencv-python-headless`): a suíte rápida passa, a janela abre e, se CA-R3.1 já existir, ele passa, com os pesos dados por `ABBY_PESOS` ou pelo checkout. Sem pesos, a janela diz isso em Avisos |
| E-2 | Portão por honra; o PR #16 entrou reprovando | **CA-E2:** `pre-push` local roda a suíte rápida. CI não: core e pesos ficam fora, e há um só usuário |
| E-3 | Repositório público com texto de livros | Dec-1 |
| E-4 | Modelos e base fora do git, sem backup verificado | **CA-E4:** comando que confere SHA-256 dos pesos contra um manifesto, com o backup testado |
| E-5 | Core sem pino | **CA-E5:** o lock traz `pyboxeditor @ git+…@<sha>`. No checkout editável, `ferramentas/conferir_core.py` compara o commit com o do lock, e o portão avisa. O wheel não leva os pesos: E-4 cobre |
| E-6 | Dependências novas de opinião | **CA-E6:** um só extra, `[opiniao-tesseract]`, ausente sem quebrar nada. **Paddle não é extra:** se aprovado, vive em venv próprio, em `%LOCALAPPDATA%\AbbyChessCraft\motores\paddle\`, com lock e modelos próprios, e baixar depende de sim do usuário |

## 8. Arquitetura (A)

**Não reescrever a janela.** É a dívida mais visível e a que menos arrisca dado.

| Id | Problema | Fazer | CA |
|---|---|---|---|
| A-1 | Ciclo de 16 módulos, 185 imports tardios | 4 cortes o levam a 4 módulos, e mais 3 a zero; partir `pagina.py` em imagem, segmentação e leitura. **13 arquivos de teste fazem `monkeypatch` em `pg.*`:** ao mover, trocar o alvo no mesmo commit, senão o teste roda sem o dublê | **CA-A1:** teste de AST com camadas permitidas; maior ciclo e imports tardios só descem |
| A-2 | 230 acessos a privados entre objetos | Promover `avisar`, `falhou`, `mudou`, `gravar`; `PaginaAberta` | **CA-A2:** catraca do total, que só desce |
| A-3 | Tetos que empurram método | Trocar as 500 linhas e os 40 métodos pelo total da MRO e por acoplamento; manter cc e 1.000 linhas | **CA-A3:** nenhum teto novo reprova o estado de hoje, e cada um prova que pega a violação |
| A-4 | `pid` × posição e função de área como tipos crus | `Pid`, `Posicao`, `Funcao(StrEnum)`, `ResumoDaPagina`. Pyright fica para depois | **CA-A4:** `test_regras_unicas` cobre as funções de área |
| A-5 | Dois caminhos de texto (Documento e exportação) | Catraca do percentual de palavras iguais, no fim de M5; o resto é Dec-4 | **CA-A5:** `qualidade.py` mede, e o número só sobe |
| A-6 | API de gravação só para testes (`salvar_pagina`: 95 usos, 0 em produção) | `replay_fatia` e `medir_legendas` passam a dar o `gid`; depois, mover para `tests/ajudantes.py` | **CA-A6:** `ProjetoDeLivro` sai da lista de tetos, sem empurrar método; `replay_fatia` segue rodando |
| A-7 | Comentários que mentem (`projeto.py:539`, `:3`, `leitor.py:10-12`, `janela.py:22-23`, `pyproject.toml:13-15`, `rotular.py:26`) | Corrigir ao tocar | — |

## 9. Interface (U)

O miolo não muda. Quase tudo aqui é pequeno.

| Id | Problema | Fazer | CA |
|---|---|---|---|
| U-1 | Foco invisível; Alt+3 para no contêiner; clique na palavra e fim de tarefa tiram o foco do Documento | `setFocusProxy`, regra de foco na folha, nome do painel na barra | **CA-U1a (M1):** Alt+3 e digitar escreve no Documento; clique e fim de tarefa não movem o foco dele. **CA-U1b:** o painel com foco tem borda em `destaque`, o nome dele aparece na barra de status, e o Enter diz o que faz: `Enter ensina`, `Enter confirma`, `Enter confere` |
| U-2 | Três modos de arraste sem indicação fixa nem Esc | Rótulo fixo, cursor próprio, Esc sai | **CA-U2:** cada modo mostra o rótulo e sai com Esc |
| U-3 | Próximo passo e progresso invisíveis | Etiqueta fixa: `verificadas 123/300 · lances por conferir 410 · diagramas 14`. Tela de fim de fila dizendo a tecla do lote | **CA-U3:** a etiqueta acompanha o livro; a fila vazia oferece o lote |
| U-4 | Geometria gravada e nunca lida; sem recentes | `restoreGeometry`, último projeto, "Recentes" | **CA-U4:** reabrir volta tamanho, divisores e projeto |
| U-5a | F8 preso em diagrama não lido | F8 pula quem não tem leitura | **CA-U5a:** F8 chega ao fim |
| U-5b | Ctrl+T ignora diagramas | A pergunta conta os diagramas por conferir | **CA-U5b:** a pergunta os conta |
| U-5c | Grade sem impresso; estado só por cor | Recorte na grade; traço por estado | **CA-U5c:** grade com recorte; traço por estado |
| U-6 | Falha de gravação pesa igual a aviso | Faixa fixa enquanto há página suja; ⚠ em cor de erro; relatório abre Avisos | **CA-U6:** com disco falhando, a faixa fica até gravar |
| U-7 | Contraste: seleção 1,66:1 sozinha na Linha; borda 1,63:1; verde e laranja de mesma luminância no tabuleiro | Contorno duplo; canto por estado; borda mais forte | **CA-U7:** teste calcula as razões dos tokens |
| U-8 | Galeria não aplica figurina, contra o YAML e a SPEC | `j.galeria` nos `widgets`; tecla para a Galeria | **CA-U8:** Ctrl+Shift+N na Galeria troca a seleção |
| U-9 | Recorte do Glifo esticado a 140 px: `o`/`O` e vírgula perdem o tamanho | Escala comum por linha e traço da linha de base | **CA-U9:** dois glifos de alturas diferentes mantêm a razão |
| U-10 | F2: 58 itens sem busca; a paleta fica abaixo da dobra a 768 px, e a grade é só de mouse | Filtro ao digitar e os 10 mais usados do livro. A grade fica no Inspetor em qualquer altura (decisão do usuário, 06/11: tirá-la abaixo de 900 px a sumia na tela de 768) | **CA-U10:** ± em até 3 teclas |
| U-11 | Copy: F5 "descarta correções" é falso; "linha vermelha" é amarela; "boxes" na tela; o mesmo 207 em quatro lugares | `glifos`, nunca `boxes`. O número da fila só no cabeçalho do Inspetor e na barra de status | — |
| U-13 | A 1366 px, a linha impressa quebra na largura, justo o que a comparação linha a linha pede | Enquanto o Documento mostra uma linha impressa por parágrafo, o corpo diminui até a linha mais longa caber, no mínimo 9 pt. Abaixo disso, rolagem horizontal. **Nunca quebra.** É independente de refluir (Dec-4), que faz o oposto | **CA-U13:** Seirawan p. 26, 1366×768: nenhuma linha impressa vira duas |
| U-14 | Imagem em 22 % a 1366 px | "Largura" e o zoom inicial usam a largura da **mancha**, não a da folha | **CA-U14:** Seirawan p. 26, 1366×768: o zoom inicial fica pelo menos 15 % maior que o da folha |

**Antes de codar U-1, U-2 e U-5,** confirmar à mão: as capturas não mostram foco nem teclado.

## 10. Decisões do usuário

**Agora**

| # | Pergunta | Opções e custo | Sem resposta | Recomendo |
|---|---|---|---|---|
| **Dec-1** | Seu repositório no GitHub é público e contém páginas de livros, contra a sua regra (`SPEC.md:1097`). O que fazer? | **a)** Tornar privado: 2 min, você mesmo, em Settings. Não perde nada; cópias já feitas continuam existindo. **b)** Seguir público e apagar os livros do histórico: 1 sessão, reescreve o histórico. **c)** Não fazer nada | Segue público, e o plano não para | a |
| **Dec-6** | O ramo `lacunas-da-spec` tem 13 commits prontos: editor de área, número da área, gaveta. Junto? | **a)** Juntar depois de limpar a duplicação que a medida acusa: 1 sessão. **b)** Esperar | a | a |
| **Dec-7** | Hoje, um glifo que você aceitou pode mudar sozinho no próximo Enter. Isso continua? (Só se o teste confirmar; senão, a pergunta sai.) | **a)** Nunca muda. Custo: um glifo aceito errado não é consertado por um padrão ensinado depois; a Galeria conserta. **b)** Como hoje; a fila Lances não se faz | a | a |

**Depois, com número na mão**

**Dec-5, no fim de M3: quanto do seu tempo vai para conferir o programa?** Sem resposta, fica a A, e o plano termina em M3. **Recomendo B, se a resposta de M2 for sim.** Para saber se uma mudança de leitura melhora o programa, são precisas páginas com o texto certo, conferido por você contra a imagem. Horas estimadas, a confirmar nas 5 primeiras páginas:

| Opção | Você faz | Horas | O que recebe | O que fica de fora |
|---|---|---|---|---|
| **A. Nada agora** | Corrige os 8 erros do Seirawan (15 min) | 0 | M1, M2 e M3 inteiros: fila Lances, realce, capa | Nenhuma mudança na leitura; sem fila Dúvidas nem 2.ª opinião |
| **B. Só a validação** | 4 páginas sorteadas de cada um dos 4 livros; a grade da dupla leitura; depois, 1 página por livro de novo, do zero, 7 dias depois | ~10 h, em 7 blocos de 90 min | M4 e M5: cada mudança de leitura entra ou sai por medida | Nenhum número geral, como "menos de 1 % de erro". Algumas perguntas podem sair "não deu para decidir" |
| **C. Validação e prova** | B, mais 2 páginas inteiras por livro e só as linhas de lance de outras páginas, até 400 lances por livro | ~22 h | B, e uma afirmação com número, nestes livros | — |

Você pode passar de A a B e de B a C a qualquer momento: nada se perde. **Regra de parada:** se as 5 primeiras páginas levarem mais de 2 h, paro e proponho menos. **Diagramas:** nenhum à parte; o que você conferir no trabalho real entra na medida.

| # | Quando | Pergunta | Opções e custo | Sem resposta | Recomendo |
|---|---|---|---|---|---|
| **Dec-2** | Depois de M4 | Posso instalar um segundo leitor, para a 2.ª opinião? | **a)** Só o Tesseract: leve, de 3,5 a 15 min em 300 páginas, a confirmar; ajuda na prosa, pouco em lance. **b)** Também o PP-OCRv6: até 2,5 GB de memória, ~1 h por livro, para deixar rodando quando você não estiver usando a máquina, com download grande; melhor na prosa, e permite aceitar em lote. **c)** Nenhum: fila de hoje e fila Lances | a, se a medida aprovar; senão, c | a; b só se a máquina aguentar um teste de um livro |
| **Dec-3** | Só com Dec-2 b | Aceitar sugestões em lote? | **a)** Não: você digita cada uma, com 2 teclas. **b)** Com prévia: 1 sessão. Os aceitos ficam como revisados e não voltam à fila. Medido: de 819 trocas, de 22 a 31 pioraram, a maioria numa tabela. **c)** Automático, sem prévia | a | b |
| **Dec-4** | Depois de M5 | O Documento pode mostrar parágrafos em vez de linhas impressas? E pode ser o mesmo texto que vai ao EPUB? | **a)** Nada muda: você corrige linhas, e a exportação monta os parágrafos. Hoje os dois saem por caminhos diferentes, e A-5 vigia a diferença. **b)** Um botão "ver como parágrafos": médio, com a comparação por linha como padrão. **c)** Um texto só para os dois: grande; o que você vê é o que sai | a | decidir com o número de A-5 na mão |

## 11. O que não fazer agora

- **VLM como leitor principal.** Sem caixa nem confiança por caractere, com erro plausível.
- **LLM para corrigir lance.** Evidência fraca, e troca erro visível por silencioso.
- **Gramática dura na saída.** Troca erro visível por silencioso. Em [Reading or Guessing?, 2026], a máscara de escrita na saída de VLM piorou o CER em até 74,7 pontos no grego; não mede gramática de lance, e desaconselha importar a ideia sem medir.
- **`--user-patterns` para lance.** É dica, e não sabe a posição.
- **PP-StructureV3 nesta RAM.** 13 a 14 GB relatados.
- **Kraken em Windows,** sem antes confirmar o ambiente.
- **Reescrever a janela.**
- **Trocar a rede de glifos.** Inferido: ela deve ser a razão das 489 figurinas certas em 498 (a fonte de cada uma não foi medida; a cor não conta).

## 12. Riscos

| Risco | Efeito | Contenção |
|---|---|---|
| A amostra de hoje engana | Investir em motor que só brilha no Seirawan | A validação (R-2) decide L-3 e F-1 |
| O gabarito herda o erro do programa | A medida favorece o programa, e o ruído iguala o alvo | Auditoria (R-2) e `erro_do_gabarito_estimado` |
| Conferir depressa trava o erro | Glifo `revisado` não é relido, não tem opinião e sai das filas; o relatório o conta como conferido | CA-F4.10 mede. O relatório diz "conferidos", nunca "certos" |
| A fila Lances não ensina | Os glifos de lance saem da fila sem virar amostra, e o erro se repete; CA-F.1 não vê, porque o replay não usa Lances | No ponto de parada de M2, contar amostras novas do livro por página, fora da amostra guiada. Caindo pela metade, Editar e Enter passa a ensinar os glifos que mudaram |
| A vantagem em figurina vem de treino sobre os mesmos livros | Conclusão falsa sobre a rede | Listar as fontes da base de treino em PP2; holdout de L-8 antes de PP5 se houver vazamento |
| A fila nova esconde o que o treino precisa | Sobe o custo da fatia | Dois modos (F-1) e CA-F.1 |
| `--psm 3` pula linha | Glifo sem opinião não é marca: o silencioso em cabeçalho fica como hoje | CA-L3.1 mede o modo; por faixa, se perder |
| O treino por livro altera a calibração | Corte da fila desatualizado | A ordem é por escore e o corte por orçamento; a recalibração usa só páginas auditadas por inteiro |
| Verificar gabarito custa caro ao usuário | A medida não fecha | Dec-5 em níveis: o programa melhora com qualquer um; a estimativa é de ~10 h no B, e a regra de parada a corrige |

## 13. Glossário

- **Opinião:** a leitura de um motor independente sobre uma linha. Nunca altera o box sozinha.
- **Discordância:** o `gid` cuja leitura difere da opinião, depois do alinhamento.
- **Sugestão:** a leitura proposta quando os motores independentes concordam entre si.
- **Lance conferido:** token de lance com todos os glifos `manual`, `revisado` ou `nativa`.
- **Ajuste, validação e prova:** conjuntos separados por página, e só o Darcy é, de fato, outro livro. Ajuste decide parâmetro. Validação decide se a mudança entra. Prova só reporta.
