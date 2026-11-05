# Crítica 4 de 6: produto

Sobre `docs/SPEC-pagina-perfeita.md`, `plans/roadmap-pagina-perfeita.md` e `docs/pesquisa/checkup-2026-11.md`, ramo `checkup-geral`. Li também SPEC.md §1-3, §6, §8, §9, §15.2, `design.md`, `ATALHOS.md`, `protocolo-rotulagem.md`, `folha_de_conferencia.py`, as capturas de 1366 e 1920 px e as densidades dos 14 gabaritos. Não abri o programa. As horas e os tempos por gesto são **estimativa minha**: nada no repositório mede tempo de verificação.

## Veredito

**O plano mede bem um problema e adia a solução dele.** O pior erro dela é o lance errado sem sinal. O próprio plano admite que a discordância "em lance, pode piorar" e que não opina em 77 % dos tokens de lance nos livros com figurinas. Mesmo assim, a primeira marca em lance chega por volta da sessão 20, depois de cerca de 40 horas de revisão de gabarito.

**A nova revisão não está especificada como fluxo.** A sessão abaixo tem 17 pontos que quem programar teria de inventar. Dois podem criar erro silencioso novo: a fila vazia que parece "conferido" e a página de texto classificada como imagem sem ninguém ver.

**Dec-5 pede 3 semanas úteis de trabalho e descreve isso como "12 páginas".** Também não diz o que acontece se ela não fizer.

**O que proponho:** três marcos usáveis antes de ela verificar uma página, a fila Lances como peça central, uma seção F-4 que fixa o fluxo, Dec-5 em três níveis, e o corte de PP6 como padrão, L-7, X-5, da injeção e do conceito de marca fraca.

---

## 1. O que ela ganha e quando

### B1. Bloqueante: o ganho em lance vem por último

**Onde:** roadmap, "Ordem" e "Por que essa ordem"; PP7, item 1.

**O problema para ela.** Contando como o roadmap conta (pequeno = 1 sessão, médio = 3, PP1 e PP5 = 3 a 4):

| Até | Sessões somadas | O que ela sente na revisão | Tempo dela |
|---|---|---|---|
| PP0 e PP1 | 4 a 5 | Quase nada: o que muda é o que deixa de se perder | Dec-1, Dec-6 |
| T1, primeiro bloco | +1 | Janela volta como estava, foco, Galeria | 0 |
| PP2 | +3 | Nada. Uma tabela | **~40 h** |
| PP2b, PP2c, PP2d | +3 a 5 | Nada | 0 |
| PP3 | +3 | A capa não atrapalha mais | 0 |
| PP4 | +1 | Nada | 0 |
| PP5 | +3 a 4, mais A-2 e E-6 | **A primeira mudança na fila e no realce** | R-4 |
| PP7, item 1 | +1 | **A primeira marca em lance** | 0 |

São cerca de 20 sessões. F-3 custa pouco, não muda caractere e "vale com a legalidade de hoje", como o próprio roadmap escreve. X-3 também é pequeno. L-9 é uma função. O realce em dois níveis pode usar sinais que já existem. "Medida antes de motor" é um bom princípio, mas nada disso é motor: marca a mais não troca letra.

A cláusula "PP2b decide" não resolve: PP2b só vem depois de PP2, e a promoção depende de um limiar. O ganho concreto dela não deveria depender dele.

**Correção.** Inserir no roadmap, antes de "Ordem", e reordenar conforme a tabela:

> ## Marcos, do ponto de vista de quem revisa
>
> | Marco | O que você passa a ter | Itens | Sessões | Seu tempo |
> |---|---|---|---|---|
> | **M1. Não perco nada, e a janela volta como deixei** | Edição de diagrama sobrevive à troca de página; glifo aceito não muda sozinho; trecho da camada que falha não some; janela, divisores e último projeto voltam; Galeria aplica figurina; F8 não prende; Alt+3 escreve no Documento | PP0; C-2, C-5, D-1, D-2, D-4, D-5; U-4, U-8, F8 de U-5, U-11, foco de U-1 | 5 | Dec-1, Dec-6, Dec-7: 15 min |
> | **M2. Vejo o lance errado** | Fila Lances (F-4): cada linha com lance, imagem sobre texto, Enter confere. Lance ilegal marcado no Documento, com o motivo. Lado do diagrama nunca afirmado sem o livro dizer, com tecla. Relatório de lances do livro | `classificar_token` e `letras_das_pecas`; PP2b sobre o que já há de gabarito; F-3; X-3; X-1 só na linha principal, sem hipóteses; F-4 | 6 a 7 | 30 min: usar em 20 páginas reais e dizer se serve |
> | **M3. A tela mostra o que importa** | Capa fora da fila, com lista; □ e palavra desmentida se destacam do resto; linha impressa não quebra a 1366 px; Imagem maior; `verificadas 123/300 · lances por conferir 410 · diagramas 14` | L-9; F-2 com os sinais de hoje; U-3, U-14, U-15. PP2d só se um teto impedir | 3 a 4 | 0 |
> | **M4. Sei quanto vale** | Tabela por livro, em palavras. Daqui em diante, nada de leitura entra sem medida | O resto de PP2; Dec-5, nível B | 3 | ~10 h |
> | **M5. A fila encolhe** | Fila Dúvidas, com 2.ª opinião, na prosa. Consertos pequenos de leitura | PP2c, PP2d, resto de PP3, PP4, PP5 | 8 a 10 | R-4: 1,5 h |
> | **M6. Opcional, um por vez, se você pedir** | Segundo leitor pesado e aceitar em lote; legalidade com hipóteses; diagramas pelo texto; treino do Tesseract | Dec-2, Dec-3; PP7 item 4; PP8; PP9 item 1 | conforme o pedido | Dec-2, Dec-3 |
>
> **Regra.** Depois de cada marco, o programa está numa versão que você usa num livro real. Nenhum marco depende do seguinte. M1 a M3 não pedem gabarito: só acrescentam sinal, e não trocam nenhum caractere.
>
> **D-3 e C-1 saem de M1** e entram logo depois de M2. Se o próximo livro for um PDF digital, D-3 volta a M1.

No Ponto de parada, acrescentar:

> | Fim de M2 | Em 20 páginas reais, pelo registro de eventos, a fila Lances leva até 2 min por página, e você diz que passou a confiar nela mais do que em ler no Documento | A fila Lances fica só com os ilegais. Rever antes de M3 |
> | Fim de M5 | Em 10 páginas antes e 10 depois, pelo registro de eventos, os minutos por página caem pelo menos 20 % | Mesmo com CA-F1.1 aprovado, volta a você: a fila nova fica como opção, não como padrão |

### I1. Importante: tempo dela não decide nada

**Onde:** SPEC §1, "Decidem"; CA-F.2 ("informativo").

**O problema para ela.** O objetivo escrito é gastar "o mínimo de atenção do revisor", e o recurso caro é o tempo dela. Só que `m` conta marcas, CA-F.1 conta gestos simulados, e nenhum aprova nem reprova por minutos reais. Uma fila pode marcar 10 % e custar mais, se cada marca pedir mais trabalho. O registro já existe (`ABBY_REGISTRO_DE_EVENTOS`, `tempo_da_fatia.py`) e a medida sai do trabalho que ela já faz.

**Correção.** Em §1, depois de "Decidem":

> **E um número que decide para o usuário:** minutos por página revisada, pelo registro de eventos, em páginas do trabalho real. Não custa revisão a mais. Vale nos pontos de parada de M2 e M5 (roadmap).

---

## 2. O custo que o plano cobra dela

### B2. Bloqueante: Dec-5 esconde o tamanho, os livros e a consequência

**Onde:** SPEC §10 Dec-5, §3.2 "Tamanho" e "Prova", §1 tabela de alvos; roadmap, Fim de PP2.

**Densidade real (contei nos JSON de `tests/verdade`, lances por regex simples; "Yusupov 71, Aagaard 74, Nunn 44" vêm da crítica 1):**

| Livro | Linhas por página | Tokens | Caracteres | Lances por página |
|---|---|---|---|---|
| Seirawan, 7 páginas | 22 a 38 | 204 a 381 | 1.016 a 1.818 | 0 a 30, média ~20 |
| Darcy, 2 páginas | 45 a 52 | 338 a 446 | 1.708 a 2.115 | 10 e 101 |
| Yusupov, 3 páginas | 37 a 75 | 124 a 623 | 660 a 2.990 | 0 a 112 |

**Estimativa do que Dec-5 pede de fato:**

| Trabalho | Base | Horas, central (faixa) |
|---|---|---|
| Verificar 60 páginas | 12 do tipo Seirawan a 10-18 min (ler 30 linhas contra a imagem, ~30 correções, 1 ou 2 diagramas); 48 de livros com figurinas a 20-40 min (40-50 linhas, CER de dois dígitos nas difíceis, figurina que o bloco de notas não digita) | **25 (18 a 36)** |
| Dupla leitura | ~70 páginas, com Seirawan e `corpus_v2`, a 2-5 min | 4 (2,5 a 6) |
| Amostra cega | 10 páginas transcritas do zero, com arbitragem, a 18-30 min | 4 (3 a 5) |
| R-4 | 3 páginas | 1,25 (1 a 1,5) |
| Diagramas do alvo de FEN | 30 por livro: ~90 fora das páginas sorteadas, a 1-1,5 min. **Não consta em Dec-5** | 2 (1,5 a 2,5) |
| Decisões, tabelas de parada, conferências à mão | 6 decisões, 6 pontos de parada | 2,5 (2 a 3) |
| Comandos por livro | `rascunho`, `texto-exportar`, `texto-importar`, `revisar` | 1 |
| **Total** | | **~40 h (29 a 55)** |

Em blocos de 90 min, dois por dia, são cerca de 14 dias de trabalho. **É o que custa revisar um livro inteiro de 300 páginas, se uma página custar de 5 a 10 min** (estimativa), e nenhuma dessas horas entrega um EPUB, a menos que os livros sejam os que ela quer converter.

**O texto atual engana em quatro pontos:**

1. **"12 páginas" é o piso.** A prova admite "até 400 tokens de lance por livro, com teto de 20 páginas": até 24 páginas por livro, 120 no total. Um livro com a densidade do Seirawan (~20 lances por página), que é o que se pede do quinto (notação em letras), vai ao teto sozinho.
2. **"5 livros" não fecha.** A lista tem quatro: Aagaard, Nunn, Yusupov e "um quinto". Com quatro, são 48 páginas e 1.600 tokens de lance, abaixo dos 2.000 do alvo. Ela não sabe quais livros preparar.
3. **As outras quatro tarefas não aparecem.** Dec-5 fala de verificar e de corrigir os 8 erros. Dupla leitura, amostra cega, 7 dias de espera e 30 diagramas por livro estão em §3.2 e §1.
4. **O que acontece se ela disser não está em outro arquivo.** O roadmap diz "o passo fecha com o G2", e o ponto de parada diz "não começar PP5". Traduzido: sem gabarito, nada de leitura entra nunca. Dec-5 não diz isso. E o "mínimo de 8 páginas" não diz quais conjuntos encolhem.

**A prova custa mais da metade e não decide nada.** A SPEC diz: "Prova: não decide nada"; quem decide é a validação, 4 páginas por livro. Então ela pode ter todas as decisões de plano com um terço do trabalho e deixar a prova para quando quiser afirmar um número.

**Correção.** Substituir a linha Dec-5 pelo texto abaixo. Em §3.2, trocar "Tamanho" por "ver Dec-5", e dizer a lista dos cinco livros, ou passar a quatro e rever os 2.000 tokens. Decisão de quem cuida da régua; ela não pode ficar sem nome.

> **Dec-5. Quanto do seu tempo vai para conferir o programa?**
>
> Para saber se uma mudança de leitura melhora o programa, preciso de páginas com o texto certo, conferido por você contra a imagem. Eu não transcrevo os livros, por direito autoral. Estimativa, a confirmar nas 5 primeiras páginas:
>
> | Opção | Você faz | Horas | O que você recebe | O que fica de fora |
> |---|---|---|---|---|
> | **A. Nada agora** | Corrige os 8 erros do Seirawan (15 min) | 0 | M1, M2 e M3 inteiros: a fila Lances, o realce, a capa | Nenhuma mudança na leitura. Sem fila Dúvidas, sem 2.ª opinião |
> | **B. Só a validação (recomendo)** | 4 páginas sorteadas de cada livro; depois, 1 página por livro de novo, do zero, 7 dias depois | ~10 h, em 7 blocos de 90 min | M4 e M5: cada mudança de leitura entra ou sai por medida | Nenhum número geral, como "menos de 1 % de erro". Algumas perguntas podem sair "não deu para decidir" |
> | **C. Validação e prova** | B, mais 2 páginas inteiras por livro e só as linhas de lance de outras páginas, até 400 lances por livro | ~22 h | B, e uma afirmação com número, nestes livros | — |
>
> **Se você não responder, fica a A.** Você pode passar de A a B e de B a C a qualquer momento: nada se perde.
>
> **Quais livros?** Prefira os que você quer converter de verdade: as páginas conferidas ficam corrigidas no projeto. Hoje: Aagaard, Nunn, Yusupov, Darcy e [nomear o quinto].
>
> **Regra de parada:** se as 5 primeiras páginas levarem mais de 2 h, paro e proponho menos.
>
> **Diagramas:** não peço nenhum à parte. O que você conferir no trabalho real entra na medida.

### B3. Bloqueante: não há ferramenta para ela verificar

**Onde:** roadmap PP2, item 4; `docs/protocolo-rotulagem.md`, etapa 3.

**O problema para ela.** O fluxo de hoje é um `.txt` num editor, no formato `lNN<TAB>texto`, olhando para PNGs de faixas em outra janela e digitando figurina sem tecla. Mais os comandos de `rotular.py`. O plano cria ferramenta de auditoria e sorteio, e nenhuma de verificação. A medição de tempo que Dec-5 pede teria de ser de cronômetro. O programa já tem imagem sobre texto (Linha), edição sem perda (sessão do Documento) e tecla de figurina.

**Correção.** Roadmap, PP2, item 4, acrescentar:

> **Verificar dentro do programa.** As páginas sorteadas abrem numa cópia do projeto, com Realce desligado e Seguir ligado, para a marca não dirigir o olho. Você corrige no Documento, linha a linha, como numa revisão. Ao fim, `rotular.py importar-do-projeto --livro X` grava o texto no gabarito e marca as linhas. O tempo sai do registro de eventos, sem cronômetro. O fluxo por `.txt` continua existindo, sem ser o caminho indicado.
>
> **Dupla leitura em grade, como a Galeria:** recorte, as duas formas em ordem sorteada, uma tecla decide, 20 por tela. Token com figurina fica fora, porque o outro motor não tem a classe e discordaria sempre.

Para reduzir o resto sem mudar o que se mede:

| Corte | Economia estimada | Por que não invalida |
|---|---|---|
| Só a validação no nível B | ~20 h | A prova não decide |
| Dentro do programa, em vez de `.txt` | ~25 % da verificação | Mesmo rascunho, mesma auditoria |
| Linhas de lance nas páginas extras da prova | ~50 % da prova | Prosa não falta. **O `m` passa a sair só das páginas inteiras.** Uma linha entra se o programa ou a opinião têm nela forma de lance, ou se ela está entre duas linhas assim. Pode perder lance tão ilegível que nenhum dos dois reconhece: o dono da régua confirma antes de adotar |
| 1 página por livro na amostra cega, no nível B | ~2 h | É a regra da §15.2 da SPEC principal. O nível C volta a 2 |
| Sem diagramas à parte | ~2 h | O alvo de FEN passa a acumular pelo trabalho real |

### I2. Importante: a releitura não tem quem lembre, e R-4 cresce escondido

**Onde:** §3.2 item 3; §3.4; roadmap PP5, item 6.

**O problema para ela.** "Pelo menos 7 dias depois" depende da memória dela. "1 página em cada 20" dá 15 páginas num livro de 300, ~6 horas por livro, enquanto o roadmap fala em 3. E a injeção propõe plantar erro na revisão real de quem tem como pior erro o erro silencioso.

**Correção.** Em §3.4:

> **R-4 roda uma vez, com 3 páginas, no fim de M5.** Repetir num livro é escolha sua, e custa ~25 min por página. Ao abrir o projeto, a partir do 7.º dia, Avisos diz: "Releitura de 3 páginas liberada desde 12/11. Ferramentas ▸ Releitura cega."

Apagar o parágrafo **Injeção** e CA-R4.2.

---

## 3. A experiência da nova revisão

### A sessão, como a spec a descreve

Livro de 300 páginas, com figurinas, lote feito, só o Tesseract instalado, plano executado até PP7. ▲ marca o que a spec não define. As soluções estão em F-4, com o mesmo número.

1. Ela abre o projeto e aperta **F6**. Vai à p. 147. ▲1 *F6 usa "pendentes ∪ fortes": para em toda página com pendente antigo, mesmo sem nenhuma marca forte.*
2. A opinião desta página ainda não chegou. A fila é "a de hoje": `Confiança · página 1/94`. ▲2 *O realce: pela F-2, "o resto da fila" é fraco e "só ao pedir". Sem opinião, tudo é fraco. Logo, 94 itens na fila e **Documento sem nenhum realce**, justo com o motor ausente ou atrasado.* ▲3 *Nada na tela diz que a opinião está a caminho, nem quantas páginas faltam.*
3. Ela corrige dois glifos. A opinião chega. O contador pula de `3/94` para `?/23`, com outro nome de fila. ▲4 *Sem mensagem. Sem nome para o modo novo.* O realce repinta sob os olhos dela.
4. Alt+↓ a leva da linha 31 à linha 2, depois à 18: `ordem_da_fila = "escore"`. ▲5 *Ela vai ver as 23 de qualquer jeito: o salto só custa olho.*
5. Item: `o`, e o Tesseract leu `0`. ▲6 *Onde aparece o que ele leu? A F-2 diz "sobre o token". A L-4, "na fila e no Documento". O Inspetor, onde está o foco, não é citado.* ▲7 *O campo vem com a leitura ou com a sugestão? E Enter ensina, aceita ou os dois? CA-L4.1 diz "não treina, a menos que o revisor dê Enter nele".*
6. Palavra `in1n1cdiatc`, com sugestão. "Uma tecla abre a sessão do Documento." ▲8 *Qual tecla? Depois de Enter, o foco volta? A "próxima duvidosa" é de qual fila?*
7. Lote. ▲9 *Só o Tesseract instalado: pela L-4, não existe sugestão em lote. Ela não sabe, porque Dec-3 não diz. Com dois motores: sem tecla, sem prévia, sem escopo, sem nome no desfazer.*
8. Quer conferir os lances. F7 cicla. ▲10 *O modo Lances é o sexto ou sétimo: F7 até cinco vezes.* A fila traz 2 tokens. ▲11 *`gids_do_rejeitado` devolve 4 gids: são 4 itens? Enter ensina 4 amostras? Abre Glifo, Palavra ou Documento?*
9. O primeiro é erro de impressão. Certo: "fica como está, com marca" (CA-X1.2). ▲12 *Marca para sempre? Como ela diz "é assim no livro"? Volta a cada abertura?* ▲13 *Depois de um lance que não dá para jogar, todos os seguintes da linha ficam ilegais?* ▲14 *CA-F3.2: "o texto diz qual lado da dúvida pode estar errado". Qual texto, e onde?*
10. A fila acaba. Tela: "Nada a revisar nesta página." ▲15 ***A página tem 40 lances, e 77 % deles não receberam nenhuma opinião. Vazio não é conferido, e a tela diz que é.***
11. Ctrl+T. "Aceitar 94 pendentes como estão?" ▲16 *94 é a fila velha, que ela nunca viu nesta página. O que significa aceitar?*
12. F6 passa pela capa da Parte III sem parar: `figura`, zero pendentes. Depois, ela abre a p. 12, verificada há um mês: 6 marcas fortes, e o contador do livro subiu. ▲17 *Página de texto classificada como imagem: ninguém vê. Página verificada: volta a ser trabalho?*

### B4. Bloqueante: "sem marca" vai ser lido como "conferido"

**Onde:** F-1, F-2, CA-X1.3 ("a cobertura sai no JSON"); ▲15.

**O problema para ela.** Hoje ela desconfia do programa, porque tudo é laranja. Com a fila nova, a página parece limpa e o programa diz que acabou. Em livro com figurinas, a opinião não vê a maior parte dos lances, e a legalidade não vê lance legal e errado. Tudo o que o plano calcula sobre isso vai para um JSON que ela não lê. O resultado pode ser menos atenção onde o erro é mais caro.

### B5. Bloqueante: o que ela precisa é ler todos os lances depressa, e não há como

**Onde:** F-3, modo "Lances", que só mostra os rejeitados; design.md C1: "Conferir cada lance a olho, por 300 páginas".

**O problema para ela.** A única garantia que não depende de motor é o olho, e hoje esse olho trabalha em corpo 10-11, no Documento, procurando lance no meio da prosa. A faixa Linha já mostra imagem ampliada sobre texto, alinhados por glifo. `classificar_token` vai existir. Falta uma fila que ande pelas **linhas com lance**, com uma tecla para conferir. Estimo 10 a 15 linhas por página, a 4-5 s: cerca de 1 min por página, de 3 a 6 horas em 300 páginas, com cobertura de todos os lances legíveis. É o item de maior efeito do plano, e não está nele.

**Correção de B4, B5 e dos ▲: a seção abaixo, nova, na SPEC.**

### B6. Bloqueante: a spec não fixa o fluxo

**Onde:** §5, F-1 a F-3, L-4; ▲1 a ▲17.

**Correção.** Acrescentar à SPEC:

> ### 5.4 F-4. A sessão de revisão (P1)
>
> **As filas.** F7 cicla, nesta ordem: **Dúvidas, Lances**, Confiança, Ordem de leitura, Por caractere, Palavras desconhecidas, Diagramas por conferir. **F4** vai direto a Lances. O escopo continua em Shift+F7.
>
> **Qual fila abre (▲4).** Página da amostra guiada: a de hoje. Outra página com evidência: Dúvidas. Sem evidência: Confiança. Escolher uma fila com F7 ou F4 fixa a escolha até fechar o projeto. Escolher Dúvidas volta à regra automática.
>
> **Dúvidas.** Todas as marcas fortes da página, **em ordem de leitura** (▲5). O escore decide quem é marcado, não a ordem de visita. No escopo livro, as páginas vão em ordem.
>
> **Marca forte (substitui a lista da F-2).** Glifo sem leitura (□); palavra que desmente a leitura; discordância com a 2.ª opinião, dentro do orçamento `m`; lance ilegal ou duvidoso (F-3, X-1). □ e lance ilegal não contam no orçamento: sempre são marcados.
>
> **O realce mostra a fila ativa (▲2).** Em Dúvidas: só as fortes. Em Confiança: o realce de hoje, com as fortes destacadas por cima. **Sai a "marca fraca".** Quem quer ver o resto aperta F7. Vale para o Documento, a Imagem e a Linha. Na Imagem, o que está fora da fila ativa fica no traço discreto dos aceitos.
>
> **A 2.ª opinião na tela (▲3, ▲4).** Etiqueta fixa na barra de status, à direita da fila. Nunca só em Avisos:
>
> | Estado | Texto |
> |---|---|
> | Sem motor | `sem 2.ª opinião` (a dica diz como instalar) |
> | Lendo o livro | `2.ª opinião: 120/300` |
> | Lendo esta página | `2.ª opinião: lendo esta página…` |
> | Esperando o lote | `2.ª opinião: espera o lote` |
> | Chegou | `2.ª opinião: 23 dúvidas` |
> | Passou do prazo | `2.ª opinião falhou nesta página` |
> | Sem memória | `2.ª opinião parada: pouca memória` |
>
> Ao chegar, o Inspetor mostra uma vez, até a próxima página: "Chegou a 2.ª opinião: 23 dúvidas, antes 94. Você continua neste glifo." Item, cursor e rolagem não mudam.
>
> **O Glifo em Dúvidas (▲6, ▲7).** Uma linha nova, acima do campo, diz por que o item está ali: `O Tesseract leu: l` · `A palavra desmente` · `Ninguém leu`. **O campo traz a leitura do programa, nunca a sugestão,** salvo o palpite do □, como hoje. **Enter ensina o que está no campo, em toda fila de glifos, como hoje.** Shift+Enter só corrige. Aceitar a sugestão é digitá-la: 2 gestos, como qualquer correção. A leitura de outro motor sobre token de lance só aparece depois de CA-L3.1. A sugestão não aparece sobre o token nem na Imagem; no Documento, só na dica ao passar o mouse.
>
> **Sugestão por palavra (▲8).** Alt+S abre a sessão do Documento com o texto proposto. Enter confirma, Esc restaura, e nos dois o foco volta ao Inspetor. O Enter do Documento vai à próxima da fila ativa.
>
> **Lances (F4) (▲10, ▲11).** Anda pelas **linhas com token de lance**, em ordem de leitura. A Linha mostra imagem sobre texto, com os tokens de lance sublinhados e os ilegais em forte. O Inspetor abre o editor Palavra com o texto da linha.
> - **Enter, sem editar:** confere. Número, lance, xeque e sinal da linha ficam `revisado`, sem ensinar, e vai à próxima. Um Ctrl+Z por linha.
> - **Editar e Enter:** corrige pela sessão (§6.3 da SPEC principal), e confere.
> - **Ctrl+Enter:** como acima, e ensina o glifo sob o cursor.
> - **Alt+↓:** pula, sem conferir.
>
> A prosa da linha não muda de estado.
>
> **Lance ilegal (▲12, ▲13, ▲14).** Na linha, o motivo: `Bf3 não se joga aqui. Erro de leitura, de impressão ou do diagrama?` Enter sem editar quer dizer "está assim no livro": o lance fica como está, sem marca, e conta no relatório como `aceito como impresso`. Só o **primeiro** ilegal de cada sequência é marcado; os seguintes ficam `sem posição`, até uma âncora. Corrigir recalcula a linha em 500 ms.
>
> **Estados vazios (▲15).** Nunca dizem "nada a revisar" enquanto houver lance por conferir:
>
> | Situação | Texto |
> |---|---|
> | Dúvidas vazia, com lances por conferir | `Sem dúvidas nesta página. 40 lances não conferidos: F4 confere · Ctrl+T marca verificada` |
> | Dúvidas vazia, lances conferidos | `Sem dúvidas, e os lances estão conferidos. Ctrl+T marca verificada` |
> | Lances vazia, página sem lance | `Esta página não tem lances` |
> | Lances vazia, conferidos | `Lances conferidos: 40, sendo 2 como impressos` |
> | Fim do livro | `Sem dúvidas no livro. 410 lances por conferir (F4 + Shift+F7) · 14 diagramas (F8)` |
>
> **Ctrl+T (▲16).** Conta só a fila ativa e os lances: `Aceitar 3 dúvidas como estão? 12 lances não conferidos. Enter aceita · Esc não marca`. O resto da fila antiga não entra na pergunta, e nada muda de estado.
>
> **F6, gaveta e contador do livro (▲1).** Página com evidência conta só as fortes; sem evidência, os pendentes. Página com evidência e sem fortes não para o F6. A coluna Rev. da gaveta e a etiqueta de U-3 usam a mesma conta.
>
> **Página já verificada (▲17).** A 2.ª opinião não roda nela, e o F6 e os contadores a ignoram. **Decidido não volta.** Quem quiser: Ferramentas ▸ "2.ª opinião nas páginas verificadas" roda em segundo plano e lista em Resultados as discordâncias, por página, com a contagem em lance. Nada muda de estado até você editar. **Um livro com 200 páginas revisadas pela fila antiga continua igual nessas 200.** A fila nova vale nas outras.
>
> **Relatório de lances.** Ferramentas ▸ "Relatório de lances" lista em Resultados, por página: ilegais, sem posição, não conferidos, aceitos como impressos. Enter vai ao lance. A exportação traz as mesmas quatro contagens.
>
> **Palavras na tela.** A interface diz **dúvida**, **2.ª opinião**, **lance conferido** e **glifo**. Não diz marca forte, escore, discordância, evidência, box nem pendente.
>
> - **CA-F4.1.** Enter numa linha da fila Lances deixa `revisado` só os tokens de lance, número e sinal; nenhuma amostra nova; um Ctrl+Z volta tudo; vai à próxima linha.
> - **CA-F4.2.** Lance ilegal aceito sem editar: sem marca depois de reabrir, e o relatório o conta.
> - **CA-F4.3.** Cada linha da tabela de estados da 2.ª opinião aparece com o executável falso de CA-L2.8.
> - **CA-F4.4.** A chegada da opinião não muda item, cursor nem rolagem.
> - **CA-F4.5.** Numa página verificada com glifos não revisados, a opinião não roda, o F6 não para, e o estado não muda.
> - **CA-F4.6.** Sem motor, o Documento em Confiança tem o realce de hoje, com □ e palavra desmentida destacados, e a fila é a de hoje (CA-F1.3).
> - **CA-F4.7.** Cada linha da tabela de estados vazios tem teste do texto. Com lance por conferir, nenhuma tela diz "nada a revisar".
> - **CA-F4.8.** Em 20 páginas reais, a fila Lances leva até 2 min por página, pelo registro de eventos. **Derruba:** acima disso, ela fica só com os ilegais.

**Por que Enter continua ensinando.** Trocar o sentido por modo repete o problema dos 8 sentidos de Enter (design.md, C2) e mexe no miolo que o Princípio 6 protege. A fila Lances confirma sem ensinar porque abre outro editor, e U-1 faz a tela dizer o que o Enter faz. Se a página 200 acumular amostra inútil, o registro de eventos mostra, e aí se decide com número.

Em F-1, trocar "O modo sai em `ControladorDaFila`, e o F7 continua trocando" por "Ver F-4". Em CA-L2.1, trocar "diz uma vez, em Avisos" por "a etiqueta de F-4 mostra `sem 2.ª opinião`, e Avisos explica uma vez".

### I3. Importante: F-2 tira do forte os dois melhores sinais de hoje

**Onde:** §5.2.

**O problema para ela.** A lista é "discordância, sugestão, lance sem par". Na captura, os erros reais da página são □ e `s0rte`, `conc1uir`, `materia1`, e o sinal disso já existe. Nenhum dos dois entra como forte. "Lance sem par" não está definido em lugar nenhum. E os testes de F-2 só medem contraste, não se a tela deixou de estar saturada.

**Correção.** Em §5.2, "Fazer":

> Forte, como em F-4. Pode entrar em M3, **antes** da 2.ª opinião: destaca □ e palavra desmentida por cima do realce de hoje, sem esconder nada.

Acrescentar:

> - **CA-F2.3.** Antes e depois, as capturas de CA-13.2 numa página de livro **já treinado**, com padrões ensinados. A de 05/11 é de livro com **0 amostras**, o pior caso: os 207 de 1.047 não representam a página 200 de um livro real. Calibrar o realce só na captura de 05/11 é calibrar outro programa.

### I4. Importante: aceitar em lote é o item mais citado e, por padrão, não existe

**Onde:** L-4, roadmap PP6, Dec-3, §13.

**O problema para ela.** O lote exige consenso de dois motores. O motor padrão é um só. Portanto, sem o PP-OCRv6 (2 GB, ~1 h por livro, numa máquina que já travou), PP6 só entrega a sugestão por palavra. Dec-3 pergunta "sugestão ou troca automática", como se o lote já estivesse disponível. Fora isso, `revisado = True` num glifo que ninguém olhou individualmente some do realce para sempre.

**Correção.** Roadmap, em PP6, acrescentar:

> **Só com Dec-2 aprovando o segundo leitor.** Sem ele, este passo não existe. A sugestão por palavra da F-4 entra em PP5.

E na L-4, em "Fazer":

> **O lote.** Ctrl+Shift+S abre a prévia em Resultados, como a de §7.2 da SPEC principal: antes, depois, caixa de marcar, `Aplicar 12` (Enter). Andar na lista move a Imagem e a Linha até a palavra. Só na página. Esc fecha sem aplicar. Ctrl+Z: "Desfazer: 12 sugestões". **Rastro:** V mostra a origem `2.ª opinião`, e a exportação conta quantos glifos saíram assim.

### I5. Importante: a página de imagem pode engolir uma página de texto

**Onde:** L-9, ▲17.

**O problema para ela.** O classificador erra numa página de texto: zero pendentes, F6 não para, o lote pula, a exportação põe uma figura. Uma página inteira vira erro silencioso, e CA-L9.2 só testa as páginas com gabarito. "Forçar a ler" exige Ctrl+Shift+A, escolher a área, T, sair, F5.

**Correção.** Em L-9, acrescentar:

> **Nunca em silêncio.** O fim do lote diz: `230 páginas lidas; 11 tratadas como imagem (ver)`, e o link abre a lista em Resultados. A gaveta tem o filtro "Tratadas como imagem". O Documento da página mostra: `Página tratada como imagem. Ctrl+Shift+T lê como texto.` Essa tecla muda a função da área e relê, num passo só do desfazer.
>
> - **CA-L9.4.** A lista e o filtro trazem a capa do Seirawan; a tecla a lê como texto, e Ctrl+Z volta.

### Menor

**Me1.** X-3, "não afirmar", não diz o que sai no FEN, que não admite lado desconhecido. **Texto:** "Copiar FEN e a exportação usam o lado do primeiro lance impresso, se houver; sem isso, `w`. O relatório lista os diagramas em que o lado foi presumido."

---

## 4. A interface (§9)

**Os itens estão certos. Faltam os que as capturas mostram, e dois não têm verificação.**

### I6. Importante: a quebra da linha impressa não depende de Dec-4

**Onde:** §9 U-13; Dec-4; checkup §2.

**O problema para ela.** A 1366 px, "mais do / erro" quebra uma comparação linha a linha contra a imagem, que é o trabalho central e o que a fila Lances e a verificação de gabarito pedem. O plano empurra isso para "depois de PP5", junto com parágrafos refluídos. São coisas opostas: refluir **piora** a comparação por linha. Na captura, a linha passa da largura por poucos caracteres.

**Correção.** Substituir U-13 por:

> | U-13 | A 1366 px, a linha impressa quebra na largura | Enquanto o Documento mostra uma linha impressa por parágrafo, o corpo diminui até a linha mais longa da página caber, no mínimo 9 pt. Abaixo disso, rolagem horizontal. **Nunca quebra.** Fica em M3 | **CA-U13:** Seirawan p. 26, 1366×768, arranjo padrão: nenhuma linha impressa vira duas |

Refluir vira Dec-4 (§5 abaixo).

### I7. Importante: a Imagem em 22 % não tem item nenhum

**Onde:** checkup §2 cita; §9 não tem.

**O problema para ela.** Na captura de 1366, as letras são quase ilegíveis, e o traço laranja cobre o que sobra. A folha tem margens brancas largas ocupando largura. CA-3.2 aprova com x-height ≥ 6 px, que é pouco para reconhecer uma letra. A Linha salva a leitura, mas só de uma linha.

**Correção.** Nova linha em §9:

> | U-14 | Imagem em 22 % a 1366 px | "Largura" e o zoom inicial usam a largura da **mancha** (da caixa de texto mais à esquerda à mais à direita, mais 2 %), não a da folha. O que está fora da fila ativa não leva traço (F-4). Fica em M3 | **CA-U14:** Seirawan p. 26, 1366×768: o zoom inicial fica pelo menos 15 % maior que o da folha |

### I8. Importante: as prioridades e os CA de §9 não seguem o trabalho

| Item | Problema | Correção |
|---|---|---|
| U-1 | O CA testa Alt+3 e o clique, e não testa **ver** o foco, que é o título do problema | **CA-U1:** acrescentar "o painel com foco tem borda em `destaque`, o nome dele aparece na barra de status, e o Enter diz o que faz: `Enter ensina` / `Enter confirma` / `Enter confere`" |
| U-3 | A etiqueta ignora o que mais importa | `verificadas 123/300 · lances por conferir 410 · diagramas 14` |
| U-5 | Quatro correções e três CA: Ctrl+T ignorando diagramas fica sem teste. F8 está em M1, o resto "depois" | Partir: U-5a F8, em M1. U-5b Ctrl+T conta diagramas, com CA. U-5c, a grade com recorte e o traço por estado, depois |
| U-10 | Está em "depois". A captura de 1366 mostra a paleta abaixo da dobra, e a grade é só de mouse. Sinal (± ⩲) é classe de gravidade alta | Sobe para M3. A paleta sai do Inspetor abaixo de 900 px de altura, e F2 com filtro passa a ser o caminho |
| U-11 | Lista três. A captura mostra "boxes" em dois lugares, e o mesmo 207 em quatro: rodapé, Inspetor, cabeçalho da fila e status | Acrescentar: "`glifos`, nunca `boxes`. O 207 aparece só no cabeçalho do Inspetor e na barra de status" |
| U-12 | Duplica X-3 | Sai de §9 |

### Menores

**Me2.** Na captura de 1366, o diagrama inline e o FEN ocupam cerca de 40 % da altura do Documento. **Texto (depois de M3):** "Tabuleiro inline em 120 px; o FEN numa linha só, com rolagem. Clique ou F8 abre grande."

**Me3.** A dica "Bordas: Shift+seta…" está no corpo do Inspetor e, de novo, no rodapé, empurrando o resto para baixo a 768 px. **Texto:** "A dica fica só no rodapé."

---

## 5. As decisões (§10)

### I9. Importante: as decisões estão escritas para quem leu a spec

**Onde:** §10; §0, "Nada que dependa delas é feito antes da resposta".

**O problema para ela.** "venv próprio", "CA-L3.1", "Tesseract de página", "PP-OCRv6", "acima do corte de CA-L4.3". Nenhuma diz o custo de cada opção, nem o que acontece se ela não responder, nem quando pode responder com informação. Nenhuma tem "não fazer". Dec-4 junta três perguntas. Dec-1 trava PP0 ("Pronto quando: Dec-1 respondida"), e isso trava o plano inteiro por uma decisão sem relação com o resto. Três perguntas só têm resposta com número que ainda não existe.

**Correção.** Substituir §0, "Decisões", por:

> **Decisões do usuário** ficam na §10. Toda decisão tem um padrão: se você não responder, o plano segue por ele, e nada de irreversível acontece.

E a §10 por:

> **Agora**
>
> | # | Pergunta | Opções e custo | Se você não responder | Recomendo |
> |---|---|---|---|---|
> | **Dec-1** | Seu repositório no GitHub é público e contém páginas de livros. Isso contraria a sua regra (`SPEC.md:1097`). O que fazer? | **a)** Tornar privado: 2 min, você mesmo, em Settings. Não perde nada; cópias já feitas por outros continuam existindo. **b)** Continuar público e apagar os livros do histórico: 1 sessão, e reescreve o histórico. **c)** Não fazer nada | Continua público, e o plano não para | a |
> | **Dec-5** | Quanto do seu tempo vai para conferir o programa? | Ver a tabela A, B, C | A: 0 h | B, depois de M3 |
> | **Dec-6** | O ramo `lacunas-da-spec` tem 13 commits prontos: editor de área, número da área, gaveta. Junto? | **a)** Juntar depois de limpar a duplicação que a medida acusa: 1 sessão. **b)** Esperar | a | a |
> | **Dec-7** | Hoje, um glifo que você aceitou pode mudar sozinho no próximo Enter. Isso continua? (Só se o teste confirmar; senão, a pergunta sai.) | **a)** Nunca muda. Custo: se você aceitou um glifo errado, um padrão ensinado depois não o conserta; a Galeria conserta. **b)** Como hoje | a | a |
>
> **Depois, com número na mão**
>
> | # | Quando | Pergunta | Opções e custo | Se você não responder | Recomendo |
> |---|---|---|---|---|---|
> | **Dec-2** | Depois de M4 | Posso instalar um segundo leitor, para a 2.ª opinião? | **a)** Só o Tesseract: leve, de 3,5 a 15 min em 300 páginas, ajuda na prosa, quase nada em lance. **b)** Também o PP-OCRv6: até 2,5 GB de memória, ~1 h por livro (para deixar rodando quando você não estiver usando a máquina), um download grande; é melhor na prosa e permite aceitar em lote. **c)** Nenhum: fila de hoje, fila Lances, sem Dúvidas | a, se a medida aprovar; senão, c | a; b só se a máquina aguentar um teste de um livro |
> | **Dec-3** | Só com Dec-2 b | Aceitar sugestões em lote? | **a)** Não: você digita cada uma, com 2 teclas. **b)** Com prévia: 1 sessão. Os aceitos ficam como revisados e não voltam à fila. Medido: de cada 819 trocas, de 22 a 31 pioraram. **c)** Automático, sem prévia | a | b |
> | **Dec-4** | Depois de M5 | O Documento pode mostrar parágrafos em vez de linhas impressas? E pode ser o mesmo texto que vai ao EPUB? | **a)** Nada muda: você corrige linhas, e a exportação monta os parágrafos. Hoje o texto do Documento e o do EPUB saem por dois caminhos diferentes, e a medida A-5 vigia a diferença. **b)** Um botão "ver como parágrafos": médio, e a comparação por linha continua como padrão. **c)** Um texto só para os dois: grande; o que você vê é o que sai | a | decidir com o número de A-5 na mão |

### I10. Importante: decisões escondidas em item técnico

Tratamento de cada uma, para não crescer a §10:

| Onde | O que está escondido | Destino |
|---|---|---|
| D-5 | Muda o que acontece com glifo aceito. O roadmap só diz "se o usuário quiser" | **Dec-7** |
| L-4, `revisado = True` | Aceito em lote conta como revisado e nunca mais se marca | Dentro de **Dec-3 b** |
| L-9 | O programa decide sozinho que uma página não é texto | Fica como padrão, com I5, sem perguntar |
| F-1, dois modos | Muda o padrão da revisão | Fica em F-4; F7 volta à de hoje a qualquer momento |
| R-4, 1 em 20 | 15 páginas por livro | I2: 3 páginas, uma vez |
| T2, "C-6 pede decisão" | Não é dela: método de medida | Tirar a frase. **Texto:** "Meta que oscila passa à mediana de 5 rodadas." |
| X-3 | Que lado vai no FEN sem o livro dizer | Me1 |
| PP9, "pode vir antes, se o usuário quiser" | Sem custo nem ganho, ela não tem como querer | Tirar a frase |

---

## 6. A prioridade real

**Hoje, a régua é o produto, e a página perfeita é o pretexto.** Quatro números, três conjuntos, catraca, seis pontos de parada. Cada um foi defendido, com razão, para que o plano não se engane. Mas o que ela pediu é outra coisa: confiar nos lances de um livro de 300 páginas sem ler tudo com lupa, em menos tempo.

**O efeito maior é simples, e nenhum dos três itens abaixo usa OCR novo nem memória:**

1. **Fila Lances por linha** (F-4): cobre todos os lances legíveis, em cerca de 1 min por página. Não é sinal, é o olho dela bem servido.
2. **Legalidade na linha principal**, com o token marcado: pega o que o olho deixa passar, sem custo de RAM.
3. **Relatório de lances:** ao terminar um livro, ela sabe o que não foi conferido. É o que torna a confiança verificável.

Com isso em M2, o resto do plano muda de lugar: a 2.ª opinião é um ganho **de prosa**, de gravidade baixa pela própria tabela de classes, e passa a ser um passo de conforto. Faz sentido, mas não é onde o trabalho se ganha nem se perde.

### O que cortar

| Corta | Por quê, para ela | Economia |
|---|---|---|
| **PP6 como padrão** | Só existe com o motor pesado | 3 sessões |
| **L-7**, segmentação | P3, depende de L-4, sem evidência de que se pague | Grande |
| **Curva do Tesseract (PP9, item 2) e L-6f** | Prosa de gravidade baixa; treino pesado na máquina que trava | 3+ sessões |
| **X-5** | Coluna trocada aparece na hora na fila Lances | 1 sessão |
| **G2-d** | Não aprova nada, e ele mesmo se autodestrói se não se parecer com o real | 1 sessão |
| **Injeção de R-4** | Plantar erro no livro de quem teme erro | CA-R4.2 |
| **Marca fraca** | O F7 já faz isso | Um conceito a menos, uma tecla a menos |
| **Ordem por escore dentro da página** | Ela visita todas as marcas de qualquer modo | Nenhum salto de olho |
| **A-1, A-4, A-5 como trilha, e C-8** | Nada muda para ela. Só ao tocar no arquivo; A-2 só onde PP5 precisar | 3+ sessões |
| **Prova, antes de ela pedir um número** | Não decide nada, e é a parte mais cara do tempo dela | ~12 a 25 h |

Em §12, "Verificar gabarito custa caro ao usuário": trocar a contenção por "Dec-5 em níveis: o programa melhora com qualquer um deles".

---

## Resumo dos achados

| # | Classe | Achado |
|---|---|---|
| B1 | Bloqueante | Primeira marca em lance na sessão ~20; marcos M1 a M6 |
| B2 | Bloqueante | Dec-5: ~40 h (29 a 55), livros incoerentes, sem consequência; texto em A, B, C |
| B3 | Bloqueante | Sem ferramenta de verificação; verificar dentro do programa |
| B4 | Bloqueante | "Sem marca" lido como "conferido" |
| B5 | Bloqueante | Falta a fila Lances por linha |
| B6 | Bloqueante | Fluxo indefinido em 17 pontos; seção F-4 |
| I1 | Importante | Minutos por página não decidem nada |
| I2 | Importante | Releitura sem lembrete; R-4 cresce; injeção |
| I3 | Importante | □ e palavra desmentida fora do forte; captura em T0 |
| I4 | Importante | Lote só existe com dois motores |
| I5 | Importante | Página de texto tratada como imagem em silêncio |
| I6 | Importante | Quebra de linha separada de Dec-4 |
| I7 | Importante | Imagem em 22 % sem item |
| I8 | Importante | CA e prioridades de U-1, U-3, U-5, U-10, U-11, U-12 |
| I9 | Importante | §10 reescrita, com custo, padrão e "não fazer" |
| I10 | Importante | Decisões escondidas |
| Me1 a Me3 | Menor | FEN sem lado; diagrama inline grande; dica repetida |

## Limites

- As horas são estimativa, a partir da densidade contada e de tempos que supus. A regra de parada das 5 primeiras páginas existe para corrigi-las.
- O "1 min por página" da fila Lances é hipótese, por isso CA-F4.8 pode derrubá-la.
- Os cortes da prova mexem na régua: indiquei qual o dono dela precisa confirmar. Não avaliei o efeito estatístico, por regra desta revisão.
- As teclas F4, Alt+S, Ctrl+Shift+S e Ctrl+Shift+T não aparecem no `atalhos.yaml`, e F4 perde para o `combobox` com foco.
- Não avaliei o custo de adaptar o editor Palavra, feito para uma palavra, a uma linha inteira: as sessões de M2 são estimativa pela escala do roadmap.
- Não usei o programa: tudo sobre a experiência vem da spec, do código lido e das capturas.
