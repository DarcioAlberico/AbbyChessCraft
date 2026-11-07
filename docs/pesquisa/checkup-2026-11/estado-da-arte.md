# OCR de livros impressos com símbolos especiais: estado da arte para livros de xadrez

Levantamento feito em 05/11/2026. Caso de uso: Windows 10, sem GPU confiável, CPU com pouca RAM, um livro por vez, 300 dpi típico, correção e treino por livro. O erro silencioso em lance é o pior erro.

**Como ler as marcas**

- **[F]** fato: artigo revisado por pares, ou comportamento descrito na documentação oficial do software.
- **[A]** alegação do autor: preprint, README ou benchmark medido por quem publica o sistema, sem reprodução independente que eu tenha visto.
- **[T]** vale testar neste caso. É proposta minha quando dito, não resultado publicado.
- **[?]** procurei e não achei.
- **[ANTIGA]** fonte anterior a novembro de 2022, ou projeto sem lançamento desde 2024. As referências com data estão na seção 9.

**Limite desta pesquisa.** A maioria das páginas foi lida por um extrator automático, e só alguns PDFs tiveram o texto lido direto (Reul, LV-ROVER, Graves, guia do ISRI, Eken). Antes de um número virar decisão de projeto, confira na fonte. Não instalei nem rodei nada, então nenhum tempo abaixo foi medido nesta máquina.

---

## 1. Conclusões

1. **O treino no domínio pesa mais que a arquitetura.** No único estudo que achei com motores treinados e VLMs lado a lado, o Kraken treinado no domínio ficou em primeiro nas duas línguas (grego CER 4,1%, árabe 3,1%), e o Tesseract de fábrica ficou abaixo da maioria dos VLMs [23, A]. As comparações em que o Tesseract perde feio usam o modelo de fábrica [24, 28j, A].
2. **VLM não serve como leitor principal aqui.** Não dá confiança por caractere nem coordenada por caractere. O erro típico é plausível, o hardware não cabe, e o ajuste por livro pede GPU e centenas de páginas. Serve, no máximo, como segundo leitor fora desta máquina. Ver seção 3.
3. **A legalidade é a alavanca mais forte que existe para este problema, e isso já se sabe desde 1990.** Baird e Thompson reduziram o erro em cerca de 30 vezes com a sintaxe e as regras do xadrez sobre a análise de forma [30, F, ANTIGA]. [?] Não achei nenhum trabalho moderno que aplique legalidade dentro da decodificação de uma rede em livro impresso. É a lacuna mais promissora.
4. **Legal não quer dizer certo.** ♘f3 e ♘d3 podem ser os dois legais. O uso correto da legalidade é **ordenar hipóteses e medir a margem entre a melhor e a segunda melhor legal**, e levantar a dúvida quando a margem for pequena. Forçar a saída para o lance legal mais próximo troca um erro visível por um erro silencioso. Conclusão minha, coerente com a escala de severidade de [26], onde o pior nível é o texto que "lê-se perfeitamente e é falso".
5. **Sinais de avaliação não têm rede de proteção.** Trocar ± por ∓ não muda a legalidade e custa um caractere no CER. Precisam de métrica própria e de revisão própria. [?] Não achei nenhum dado publicado de precisão em ⩲ ⩱ ± ∓, nem em livro nem em benchmark.
6. **A confiança da rede ajuda menos do que parece.** Redes de reconhecimento são consistentemente confiantes demais [18, A]. A escala por temperatura corrige o valor, mas não muda a ordem entre as previsões [19, A], logo não melhora a fila de revisão por si só. Num estudo com 36 pessoas sobre transcrição de fala, o realce por confiança não alterou a redução de erro, e cerca de metade dos erros seguiu sem correção em qualquer condição [38, A].
7. **Duas medidas faltam na literatura e valem ser feitas aqui:** a taxa de erro silencioso por classe de token e o erro residual depois da revisão. [?] Não achei estudo que meça revisão humana de OCR. A referência mais próxima é a "marked character efficiency" do ISRI, de 1996 [36, F, ANTIGA].

---

## 2. Motores abertos, locais, treináveis

"Tempo" é o que achei publicado, quase nunca em página de 300 dpi numa máquina como esta. [?] Não achei tempo por página publicado para Tesseract, Kraken, Calamari, EasyOCR nem TrOCR em CPU de mesa.

| Motor | Licença | CPU / GPU | Tempo publicado | Alternativas e confiança por caractere | Ajuste com poucas centenas de linhas | Alfabeto customizado |
|---|---|---|---|---|---|---|
| **Tesseract 5.5.4** [1, 2, 3, 4, 5] | Apache 2.0 (conhecimento geral; a página lida não diz) | Só CPU: "No GPU is needed. (No support.)" [3, F] | 98 a 100 ms por linha, hardware não dito [27, A] | **Sim.** `lstm_choice_mode` 1 ou 2, com `x_confs` por símbolo no hOCR [2, 5, F]. Caixa por caractere existe, mas "may be less precise" no LSTM [5, F]. A API C++ dá as saídas brutas por `RecognizeLine` + `NetworkIO` [6, F] | **Sim, é o caso documentado.** Exige `tessdata_best` e `--old_traineddata` se o conjunto mudar [4, F] | Por unicharset. Linha com caractere fora dele é ignorada no treino ("Encoding of string failed") [3, F] |
| **Kraken 7.1** [7, 8, 9] | Apache 2.0 | "Linux or Mac OS X"; Windows não é citado [8, F]. Python 3.10 a 3.13 | [?] | Confiança e polígono por code point (API 5.0.0) [9, F]. [?] Alternativas top-k não confirmadas | **Sim:** `--load`, `--resize union/new`, `--freeze-backbone` [7, F]. Sem quantidade mínima citada | Codec automático ou JSON; `--resize` adapta a saída [7, F] |
| **Calamari 2.3.1** [10, 11] | GPL-3.0 | TensorFlow. Exigências em Windows não confirmadas | [?] | **Sim e o mais completo:** `--extended_prediction_data` grava posição, probabilidades e alternativas; o formato `pred` traz os logits [11, F] | **Sim:** `calamari-cross-fold-train` (5 modelos por padrão), `--warmstart.model`, congelamento por regex [11, F] | `--codec.keep_loaded True` une alfabetos [11, F] |
| **PaddleOCR 3.x, PP-OCRv6 e v5** [12, 13, 14, 15, 16] | Apache 2.0 [16, A] | CPU e GPU. Exemplos de treino em GPU [13, F] | PP-OCRv6 em Xeon 8350C, por imagem, com pipeline inteiro: tiny 0,20 a 0,32 s; small 0,59 a 0,79 s; medium 1,40 a 3,31 s [14, A] | **Não documentado.** `rec_score` por linha; `return_word_box` por palavra [12, 13, F]. Cabeça CTC [14, A], então logits via ONNX são plausíveis [T] | Sim, com extensão de dicionário [14, 15, A]. Sem quantidade citada. Queixa de usuário sobre passar dicionário na inferência no v5 [fórum, 15] | `character_dict_path` no YAML de treino [15] |
| **docTR 1.1** [17a, 17b, 17c] | Apache 2.0 | CPU e GPU | CPU i7-11800H: detector `db_mobilenet_v3_large` 0,5 s/página; `crnn_mobilenet_v3_small` 0,05 s por lote de 64; `parseq` 2,2 s por lote [17b, A] | Confiança por palavra. Não documentado por caractere [17b, F] | Sim, por `references/recognition`. Sem quantidade citada [17c, F] | `vocab=` no construtor [17c, F] |
| **EasyOCR 1.7.2** [20a, 20b] | Apache 2.0 | CPU com `gpu=False` | [?] | Confiança por caixa. `decoder='wordbeamsearch'`, `allowlist` [20b, F] | Sim, por `custom_model.md`. Sem quantidade citada | Por modelo próprio. Último lançamento visto: set/2024 [ANTIGA] |
| **Surya 2.5** [21] | Código Apache 2.0. Pesos OpenRAIL-M modificados, grátis para uso pessoal e empresas abaixo de US$ 5 mi. O PyPI ainda indica GPL | VLM de 689M parâmetros. CPU por llama.cpp | M4 Max com Metal, 96 dpi: 38,9 s/página [21, A] | Confiança por bloco. Sem caixa por caractere [21, F] | **Não:** sem receita pública; o README manda contatar a empresa | Não se aplica |
| **TrOCR** [22, 27] | Não verifiquei a licença dos pesos | GPU na prática | A100: 70 ms por linha de fábrica, 284 a 414 ms ajustado [27, A] | [?] não documentado | Depende de ajuste: CER 15,46% de fábrica contra 3,62% ajustado em jornais antiqua [27, A] | Saída por wordpiece [22]. Figurinas exigiriam mexer no tokenizador (inferência minha) |
| **PARSeq** [17d] | Apache 2.0 na maior parte | CPU viável; mediana de 14,87 ms a 1 thread | Só o recorte, sem pipeline [A] | Rótulo e confiança; o README não detalha por caractere | Sim, com `pretrained=` | `charset` configurável. Feito para **texto em cena** e recortes curtos; não achei uso em linha de livro. Última atualização: fev/2024 [ANTIGA] |
| **ABINet** [17e] | BSD-2, mas "only free for academic research" | Treino em GPU; imagem Docker com torch 1.1 | [?] | [?] | Não recomendado | CVPR 2021. O modelo de linguagem embutido é justamente o que não se quer para lance [ANTIGA] |
| **OCRmyPDF 17** [17f, 17g] | MPL-2.0 | Conforme o motor | Conforme o motor | Herda, mas não expõe | **Não é motor, é pipeline.** Usa Tesseract 4.1.1 ou superior e plugins [17f, F] | `--mode skip`, `--redo-ocr`, `--sidecar`. O `--force-ocr` rasteriza e pode perder vetor [17g, F] |

### Detalhes do Tesseract que importam

- **Ajuste para poucos caracteres.** O próprio manual usa **± como exemplo**: 14 linhas com o sinal, 3.600 iterações, e "todos os ± reconhecidos corretamente" na fonte de teste; o CER geral nessa fonte ficou em 2,38% [4, F]. É o caso mais próximo do nosso na documentação oficial, mas com texto renderizado, não com escaneamento.
- **Sobreajuste é real.** O ajuste por fonte parou em 400 iterações porque seguir adiante piorava o conjunto base [4, F]. O ADAM "does seem to overfit more" [4, F].
- **Trocar a camada do topo pede muitos dados** e o resultado do exemplo saiu "badly over-fitted" [4, F]. Não é o caminho para poucas centenas de linhas.
- **Treino no Windows: as fontes não batem.** O manual ainda diz "training only works on Linux" [3], enquanto a 5.5.4 corrige a compilação da ferramenta de treino no Windows com VS2022 [1]. Confirme na instalação do projeto.
- **`--user-patterns` não serve para SAN.** É "merely applied as a hint", funciona melhor com um padrão só, e padrões genéricos deixam o Tesseract lento [2b, F]. E não carrega estado: não sabe qual é a posição.
- **Lista de permitidos: fontes em conflito.** O manual atual marca `tessedit_char_whitelist` como válido nos dois motores [5, F]. A wiki diz que não há suporte no 4, e um mantenedor citado em issue diz que não funciona bem com LSTM [5b, 5c]. [T] Medir antes de usar.
- **A 5.5.4 corrige 17 avisos de segurança** [1, F]. O ano não aparece na página; pela sequência das versões, é 28/10/2026 (inferência). Atualize.

### Veredito para este caso

- **Manter Tesseract LSTM como base.** É o único com tudo junto: Windows, só CPU, alternativas por caractere, ajuste por livro documentado.
- **[T] Calamari como segundo leitor** é o melhor em dados expostos (logits e alternativas), mas o último lançamento é de nov/2024 e a licença é GPL. Verifique se TensorFlow cabe nesta RAM, e se a GPL é compatível com a distribuição do programa.
- **[T] PP-OCRv6 tiny ou small por ONNX** como leitor diverso e barato. Os números são de um Xeon de servidor e [?] a RAM não é informada. Evite o **PP-StructureV3**: mesmo na configuração leve em CPU, o pico foi de 13 a 14 GB [16b, A].
- **Kraken** só via WSL ou Linux. Vale pelo resultado em [23], mas o custo de ambiente é alto nesta máquina.

---

## 3. VLMs e modelos de OCR por visão com pesos locais

### O que existe

Pontos no olmOCR-Bench (testes unitários binários, não distância de edição) [28a]. O asterisco marca o que o próprio autor do sistema relatou; os demais foram reproduzidos pelos autores do olmOCR. Os resultados não são todos comparáveis: o LightOnOCR retira a categoria de cabeçalhos e rodapés.

| Modelo | Licença | Tamanho | Pontos | Hardware | Confiança | Coordenadas |
|---|---|---|---|---|---|---|
| olmOCR 2 [28a] | Apache 2.0 | 7B | 82,4 | Treino em 8 H100; inferência não informada | Não citada | Não citada |
| Chandra 0.1.0 [28a] | OpenRAIL-M | [?] | 83,1* | [?] | [?] | [?] |
| Surya 2.5 [21] | Ver seção 2 | 689M | 83,7* | H100 ou llama.cpp | Por bloco | Por bloco |
| LightOnOCR-2-1B [28b, 28c] | Apache 2.0 | 1B | 83,2* (sem cabeçalhos) | H100, 5,71 pág/s. Sem medida em CPU, embora o código aceite | Não citada | Só a variante bbox, e para imagens embutidas |
| dots.mocr / dots.ocr [28d] | MIT no repositório, mais um acordo de licença à parte, não lido | 3B e 1,7B | 83,9* / 79,1 | GPU nos exemplos; "CPU" remete a uma issue | Não citada | Bbox por elemento |
| PaddleOCR-VL / VL-1.5 [28a, 28e] | Apache 2.0 | 0,9B | 80,0*; 94,5% no OmniDocBench v1.5* | [?] CPU | [?] | Por bloco |
| MinerU 2.5.4 / 4.1 [28a, 28f] | Licença própria baseada em Apache, com condições extras | [?] | 75,2* | `basic` ONNX: 2 GB, CPU. `standard` ONNX + llama.cpp: 8 GB, CPU funciona | Não citada | Bbox por bloco |
| DeepSeek-OCR [28a] | MIT | [?] | 75,7 | [?] | [?] | [?] |
| Mistral OCR API [28a, 28g] | **Só API; não achei pesos** | - | 72,0 | Nuvem, fora de escopo | OCR 4.1: página, bloco e palavra | Por parágrafo |
| GOT-OCR2 [28h, 25] | Código Apache, dados CC BY-NC | [?] | 22,1 no olmOCR-Bench [25, A] | Referência CUDA; CPU só por contribuição da comunidade | Não citada | Entrada por caixa, não saída |
| Nougat [28i] | Código MIT, **pesos CC-BY-NC** | - | - | CPU lenta | Não | Não |

Nougat é de 2023, treinado em artigos científicos, e falha em não latinos [ANTIGA]. Não serve.

### Risco de alucinação: o que está medido

Todos preprints, de 2026. Nenhum trata de xadrez.

- **"Reading or Guessing?"** [23, A] é o melhor estudo para esta questão.
  - Nas substituições, 27,2% (grego) e 44,5% (árabe) dos erros dos VLMs são **palavras reais**.
  - Com caracteres embaralhados, o CER dos VLMs sobe de 12,61 a 42,45 pontos em grego, contra 2,79 a 6,05 dos tradicionais. O menor aumento dos VLMs supera o maior dos tradicionais. Os autores admitem outra explicação possível (sequências desconhecidas).
  - Isso importa muito aqui: **um lance não tem a redundância de uma frase**. É uma sequência curta e pouco previsível.
  - Modos só de VLM: repetição, marcação espúria, troca de escrita.
  - **Nenhuma mitigação se transfere entre escritas.** A máscara de escrita, que é uma restrição dura, aumentou o CER em até 74,7 pontos no grego. Isso desaconselha importar sem medir a ideia de "gramática na saída do VLM".
- **"When Low CER is Not Enough"** [24, A]: VLMs vencem em CER nos 175 documentos do arquivo Berrutti, mas os erros preservam a fluência e mudam o conteúdo. Não dão taxa de alucinação, só análise qualitativa.
- **"Equal CER, Unequal Damage"** [26, A]: VLMs gerais formam palavras reais acima do acaso, os clássicos ficam perto do acaso. Com juiz LLM, os 10% piores capturam 81% a 92% do dano percebido, contra 29% a 55% pelo CER.
- **Avaliação por entidade** [24b, A]: o CER em entidades sempre superou o global; Qwen 3.6 custou 53,9 s/página, contra 0,57 s do docTR, hardware não dito.
- **Laços de repetição:** 1,14% caindo para 0,50% no LightOnOCR-2 [28b, A]. O olmOCR 2 aumenta a temperatura quando não sai o token de fim [28a, A].
- **KIE-HVQA** [24c, NeurIPS 2025, F]: modelos dependem do conhecimento linguístico quando a imagem degrada. O foco é carteiras de identidade e faturas.
- **ChessQueries** [33, A]: LLMs de fronteira acertaram 0% a 2,6% dos tabuleiros inteiros em fotos. É outra tarefa, mas é sinal contra usar VLM genérico em diagrama.

### Por que importa numa ferramenta de revisão

1. **Sem âncora de revisão.** A revisão por glifo, o realce por caractere e a busca por glifo precisam de caixa e de probabilidade por caractere. Nenhum VLM acima as entrega; o melhor caso é por bloco ou por palavra.
2. **Sem alternativas.** Sem hipóteses concorrentes, não há como calcular a margem entre lances legais.
3. **O erro é do tipo que o revisor não vê.** A saída é fluente e, em xadrez, tende a ser um lance plausível.
4. **Ajuste por livro está fora de alcance.** O caso que achei usou QLoRA em 707 páginas de treino com GPU [28j, A]. Não são poucas centenas de linhas, nem esta máquina.
5. **Hardware.** [?] Não achei tempo de nenhum VLM em CPU de mesa com pouca RAM. O número mais próximo é 38,9 s/página em M4 Max com GPU Metal a 96 dpi.

**Onde pode valer:** como leitor independente, fora desta máquina, só para páginas ruins e só para **levantar discordância**. A saída dele nunca entra no texto sem conferência. [T] Só se sobrar orçamento depois do resto.

---

## 4. Fusão, restrição, calibração e revisão ativa

### Consenso e combinação

- **Votação entre motores comerciais:** CER de 9,90 a 1,17% caindo para 0,85% (Rice et al., 1996; **número visto em citação secundária**) [29a, ANTIGA]. O `vote` do ISRI alinha por LCS e decide por maioria, e existe em UTF-8 no ocreval [36, 37].
- **Lund et al., ICDAR 2011:** alinhamento progressivo e seleção por entropia máxima; 24,6% de melhora relativa no WER sobre o melhor de cinco motores [29b, F, ANTIGA; vi o resumo, não o artigo].
- **Reul et al., JLCL 2018** é a mais útil para este caso [29c, F].
  - Um único motor com validação cruzada forma um comitê que vota com as alternativas e as confianças.
  - Pré-treino mais voto: 46% de melhora; com pré-treinos diferentes, 53%. A revisão ativa acrescenta 16% (em 3 de 6 livros).
  - **2,5% de erro com 60 linhas; abaixo de 1% com 1.000.**
  - O ganho do pré-treino cai com os dados: mais de 40% com 60 linhas, cerca de 15% com 250.
  - Ressalva: livros antigos, um motor antigo (OCRopus), texto corrido. Nada garante o mesmo em símbolos raros.
- **LV-ROVER-MLT, 2026** [29d, A] é a referência moderna mais parecida com "só Tesseract". Cinco fluxos de Tesseract com ajuste sintético e **arbitragem por palavra, com léxico como portão e vocabulário aberto preservado**. CER de 2,34% caindo para 0,70% no desenvolvimento, 0,74% no teste fechado, primeiro lugar na competição DocEng 2026. Húngaro: inconclusivo. Autor único, língua maltesa.
- **Calamari** faz o voto com confiança já pronto (`ConfidenceVoterDefaultCTC`) [11, F].

**[T] Proposta minha:** arbitrar **por token de lance**, não por caractere. A estrutura de xadrez já alinha os leitores (número, figurina, casa), o que evita o problema do alinhamento múltiplo.

### Decodificação com restrição

- **Word Beam Search** (ICFHR 2018): CTC restrito por dicionário, e que ainda aceita números e cadeias arbitrárias [29e, F, ANTIGA].
- **PyLaia** [19, A]: `ctc_decoder` do torchaudio com n-gramas, CER 11,9% melhor em média em 12 conjuntos, mas com efeito limitado ou negativo onde o erro já era baixo. **Atenção:** o torchaudio entrou em fase de manutenção, e o decodificador CUDA sai na 2.9; [?] o estado do decodificador de CPU não está claro [29f].
- **WFST:** [?] não achei aplicação a lance impresso. Parece mais máquina do que o problema pede.
- **O que achei de mais próximo em xadrez:** ver seção 5. Tudo é pós-processamento ou busca sobre listas já decodificadas.

**[T] Proposta minha, a de maior potencial neste levantamento:**

1. Cada posição tem poucas dezenas de lances legais, então **não é preciso WFST nem léxico**. Basta enumerar.
2. Gerar o SAN de cada lance legal (com figurina) e **calcular a probabilidade exata daquela cadeia** pelo algoritmo forward do CTC sobre as saídas da rede. Graves et al. definem esse cálculo de p(l|x) por programação dinâmica [29g, F, ANTIGA, mas é fundamento, não está superado].
3. Reportar a melhor hipótese legal, a segunda melhor e a margem entre as duas. Margem pequena vira fila de revisão, mesmo que a leitura seja legal.
4. A leitura de fábrica ilegal **nunca é trocada em silêncio**. Livros têm erros de tipografia de verdade, e a saída tem de preservar o que está impresso (o resumo de [30] trata jogos com erros tipográficos à parte).
5. Variantes entre parênteses exigem uma pilha de posições. Os "..." e a numeração são âncoras de sincronização.

Limite técnico: `lstm_choice_mode` entrega alternativas já podadas. O cálculo exato pede as saídas brutas, em C++ pelo `NetworkIO` [6] ou por um motor que grava logits, como o Calamari [11]. Teste antes com as alternativas podadas, que é o caminho mais barato; pode bastar.

**Sobre LLM como corretor:** evidência fraca e contra. No `chess_ocr`, o CER médio foi de 17,41 para 17,28 com GPT, em 15 amostras, com métrica não definida no README [31, A]. Em [23], a correção pós-OCR só por texto piorou 6 de 7 sistemas em árabe e melhorou 4 de 7 em grego.

### Calibração

- **Guo et al., 2017:** redes modernas são mal calibradas, e a temperatura é surpreendentemente eficaz [18b, F].
- **Slossberg et al., 2020** [18, A]: ECE médio de 5,98 para cerca de 1,7 em nível de palavra, incluindo modelos CTC (6,9 para 2,2). Nos de atenção, calibrar caractere a caractere descalibra a palavra.
- **PyLaia** [19, A]: escores quase sempre entre 0,97 e 0,99; correlação linear com a taxa de acerto melhora (0,62 para 0,79 com T = 2); **Spearman não muda**.
- **Implicação:** a temperatura deixa o limiar interpretável, mas não reordena a fila dentro de um mesmo modelo. O que reordena é a informação nova: margem legal, discordância entre leitores, classe do caractere. Conclusão minha.
- **[T]** Calibrar **por lance e por classe** (figurina, casa, sinal de avaliação), em páginas do próprio livro já revisadas, porque cada ajuste por livro muda a calibração. Medir curva de confiabilidade, mas decidir pela curva risco-cobertura [18c], já que o ECE não diz quanto erro escapa.
- **[T]** Predição conforme [18d] daria conjuntos de candidatos com cobertura garantida, supondo dados intercambiáveis. Em páginas de um livro isso só vale aproximadamente. Ideia secundária.

### Confiança como detector, e revisão ativa

- **Revisão ativa por discordância:** Reul et al. selecionam as linhas em que os votantes mais discordam, com 16% de ganho [29c, F]. É o caminho direto para escolher o que transcrever a seguir, mas exige comitê. Mais barato, e [T]: linhas com margem legal pequena ou com figurina e sinal raro.
- **Confiança como sinal:** ConfBERT mostra que incorporar a confiança melhora a detecção automática de erro [29h, A]. Não extraí os números.
- **Realce:** ver Kuhn et al. na seção 7. O ganho não é automático. Realçar pouco funciona melhor do que realçar muito: a razão de chance de corrigir o erro realçado foi 2,64 com 4% das palavras marcadas, e deixou de ser significativa com 13 a 21% [38, A].

---

## 5. Específico de xadrez

### Notação em livro impresso

- **Baird e Thompson, "Reading Chess", IEEE TPAMI, junho de 1990** [30, F, ANTIGA, mas é o trabalho central]. Leram vários volumes da enciclopédia e do Informant com impressão ruim. Análise de layout de cima para baixo, busca heurística para caracteres danificados ou encostados, e, com a sintaxe das partidas e as regras do xadrez, **erro cerca de 30 vezes menor** que só por forma. Um resumo secundário cita 2.850 partidas, 945 páginas e 99,995% efetivo em cerca de um milhão de caracteres, com 98% das partidas sem erro tipográfico recebendo interpretação legal. **Esses detalhes vieram de resumo secundário; não li o artigo.** Vale conseguir o texto integral.
- **Eken et al., 2018** [32, F, ANTIGA]: FAN em página de duas colunas do Informant. Projeções horizontal e vertical, reconhecimento por k-NN (k = 1) de caracteres segmentados, usando negrito para separar lance de comentário. Base de 30 classes criada das 30 primeiras páginas de **um único livro**, dividida em 70/30. Figurinas com 100%, outros caracteres de 95 a 100%. O ganho da legalidade é descrito sem número. Como treino e teste vêm do mesmo livro, o resultado não diz nada sobre generalização; mas é sinal, modesto, de que **a figurina é fácil dentro de um livro**.
- **`chess_ocr`** [31, A]: notação sem figurinas, com `pgn-extract` para lances suspeitos. README: "does not currently support" figurinas.
- **chessPDFBrowser** [31b]: a página no SourceForge lista figurinas e detecção de FEN. Um usuário em fórum relata limites do Tesseract com figurinas, e o desenvolvedor dizia não suportar ainda, em data antiga. [?] Estado atual não verificado. Só fonte de baixo peso.
- **Conversor de diagrama em PGN, IJARCCE 2025** [31c]: deixa o OCR dos lances para trabalho futuro.
- **[?]** Não achei nenhum artigo de 2022 a 2026 sobre OCR de lances em livro com figurinas, nem conjunto de dados público com verdade de campo para isso.

### Folhas de partida manuscritas

| Trabalho | Dados | Sem pós-processamento | Com legalidade, automático | Com humano | Onde entra a legalidade |
|---|---|---|---|---|---|
| Majid e Eicher, J. Imaging, jan/2022 [34a, F] | HCS: 158 partidas, teste com 3.810 imagens de lance | Lance: 87,8% a 89% | 94,9% a 95,6% | **98,4% a 99,1% com 4% de interrupção** | **Pós-processamento**, com Stockfish 14.1, cruzando as folhas de brancas e pretas |
| Eicher et al., 2021 [34b, F, ANTIGA] | HCS | - | - | 97,2% com 7% de interrupção | Pós-processamento |
| Hayashi e Hirata, ICPR 2022 [34c, F, ANTIGA] | 492 folhas | Estudo sobre como a rede aprende | - | - | Não trata |
| `chess-scoresheet-scanner` [34d, A] | 228 folhas no teste de acurácia | **Sem número publicado** | Busca por **sequência legal sobre a partida inteira**, com custos por confusão (1/7, 3/8, 5/6...), e nova consulta ao modelo com a lista de lances legais | - | **Dentro da busca.** É o desenho mais parecido com o proposto, mas é só um repositório sem medida publicada e sem licença indicada |

Os autores de [34a] marcam em cores diferentes o lance ilegal e o de baixa confiança, e detalham quatro casos de intervenção, incluindo "conflito forte" (duas leituras válidas e confiantes que divergem). Modelo direto para a fila de revisão. Mas manuscrito não é impresso: a origem do erro difere.

### Diagramas

| Projeto | Licença | Alvo | Resultado publicado | Confiança por casa | Observação |
|---|---|---|---|---|---|
| **fenshot** [35a] | MIT | Tela e **diagrama hachurado de livro** (sintético) | Zero casas erradas nos casos positivos de um conjunto de capturas de tela reais; 29 testes de regressão [A]. Não é escaneamento | **Sim** | CNN de 330 mil parâmetros, ONNX de 1,3 MB, CPU. **[T] o primeiro a testar** |
| **Chess_diagram_to_FEN** [35b] | MIT | Tabuleiro, rotação e perspectiva | Sem métrica publicada | [?] | Roda em CPU |
| **chessboard-recognizer** [35c] | MIT | Imagem de tabuleiro | Sem métrica no README. Um usuário relata cerca de 97% num livro de Nunn, em fórum de 7 anos atrás [ANTIGA] | Sim, em `debug.html` | TensorFlow 2 |
| **tensorflow_chessbot** [35d] | MIT | Tela | ~73% em 71 posts [ANTIGA, 2015-16] | Sim | Baseline histórico |
| **Fenify-3D** [35e] | MIT | Foto, **não diagrama** | 0,852 em teste [ANTIGA, 2022] | Sim | Fora do alvo |
| **LiveChess2FEN** [35f] | [?] | Foto, Jetson Nano | 92% por peça, 95% por tabuleiro [ANTIGA, 2020] | [?] | Fora do alvo |
| **ChessReD** [35g] | Dados públicos | Foto | 15,26% de tabuleiros inteiros [A, 2023] | - | Fora do alvo |
| **ChessQueries** [33] | Dados CC BY-NC | Foto, transmissão, sintético | 99,2 a 99,5% em ChessReD; **não avalia diagrama impresso** [A] | - | ViT-L com treino em RTX 4090 |

Observação: a acurácia que importa é **por tabuleiro inteiro**, não por casa. O sucesso em foto não se transfere para diagrama impresso, onde a tarefa é muito mais fácil, mas o problema são os estilos de livro e o escaneamento.

**[T] Proposta minha, sobre a validação que a SPEC já faz** (lances depois do diagrama jogados a partir do FEN, §"Validação pelos lances"):

- Usar as casas de baixa confiança para **gerar FENs candidatos** e ver qual torna legal a linha seguinte.
- Fechar nos dois sentidos: a posição ao fim da linha de lances tem de coincidir com o diagrama seguinte, quando houver.
- Mesma cautela da seção 4: é sinal de conferência, não correção automática. "Confiável pelos lances" prova pouco para peça que não se moveu nos lances lidos.

### Sinais de avaliação e PGN

Figurinas ♘♗♖♕♔ e sinais ⩲ ⩱ ± ∓ não têm amostra em nenhum modelo de fábrica que eu tenha podido confirmar. Portanto o caminho é treinar. O manual do Tesseract documenta exatamente esse caso com ± [4]. Para raridade, a literatura de partituras achou instabilidade ao reponderar a perda e preferiu **sintetizar imagens com o símbolo raro** [39, ANTIGA]. O LV-ROVER também usa ajuste sintético [29d].

**[T]** Renderizar linhas com a fonte do livro (quando identificável), misturando ⩲ ⩱ ± ∓ em proporção alta, mais o ajuste nas linhas revisadas. Medir por classe, separadamente.

---

## 6. Análise de layout

| Modelo | Licença | Velocidade em CPU | Precisão | Ordem de leitura | Para este caso |
|---|---|---|---|---|---|
| **PP-DocLayout-S / M / L** [40, 41] | Apache 2.0 (PaddleOCR) | 18,5 / 43,4 / 503 ms em Xeon 6271C, 8 threads, **só inferência** [A]. O artigo cita 14,5 ms em CPU para o S | mAP@0,5 70,9 / 75,2 / 90,4 em base interna [A] | Não | **[T] O S ou o M**, se o layout atual falhar |
| **PP-DocLayoutV3 / RT-DocLayout** [42, A] | Pesos em HF; licença não lida | **[?] sem CPU**; 132 FPS em A100 | Pipeline 94,50 | Sim, integrada. Distância 0,042 contra 0,074 de XY-Cut em OmniDocBench | Bom, sem medida em CPU |
| **DocLayout-YOLO** [43] | **AGPL-3.0** | [?] Sem número no README | mAP 69,8 a 79,7 | Não (XY-Cut como pós) | A licença pesa |
| **Surya 2.5** [21] | Ver seção 2 | VLM, lento | 95,7 no próprio benchmark [A] | Por VLM | Não em CPU |
| **LayoutParser / Detectron2** [44] | Apache 2.0 | [?] | - | Não | Não vi lançamentos na página, com Detectron2 opcional. Não verifiquei o último commit. Não recomendo começar por aqui |
| **XY-Cut++** [45, A] | [?] Sem link de código confirmado | Algorítmico | 98,8 BLEU em base própria (DocBench-100) | É o foco | **[T]** A máscara de elementos interessa quando diagrama ou título cruza as colunas |
| **LayoutReader** [46, F, ANTIGA] | Repositório sem licença confirmada | Só caixas; sem número | "Quase perfeito" em docs Word | É o foco | Ver abaixo |

**O caso do LayoutReader é um aviso.** O artigo de 2021 relata desempenho "quase perfeito" em documentos convertidos do Word. Em 2026, em 140 páginas multicoluna, um estudo independente mede macro 24,6%, contra 75,3% do XY-Cut e 88,0% do método dele [47, A]. **Em livros (só 15 páginas), o XY-Cut venceu: 85,8 contra 82,0 e 53,7.** E o método dele custa 93,5 s/página em GPU A40. Para duas colunas com diagramas, o algoritmo simples é competitivo. O Tesseract 5 de fábrica já foi documentado misturando colunas em leitura em "Z" [25, A], por isso a segmentação em colunas fica melhor fora do motor.

**[T] Proposta minha:** a continuidade do lance é um teste de ordem de leitura. Salto na numeração ou lance ilegal logo depois de uma virada de coluna sugere ordem errada antes de sugerir OCR errado, e a fila de revisão pode dizer isso ao usuário.

---

## 7. Métricas e protocolo

### O que já existe

- **CER/WER não bastam e nem são estáveis entre ferramentas.** Neudecker et al. rodaram cinco ferramentas em dois conjuntos e os resultados variam [48, F]. Fixe a ferramenta, a versão e a normalização Unicode, e declare como figurina e ⩲ são comparados. Isso é decisivo aqui: normalizações podem mexer em símbolos.
- **Revisão sistemática de 2026:** CER e WER tratam todo erro igual, e os autores pedem métricas plurais [25, A].
- **dinglehopper** [49]: Apache 2.0, aceita ALTO, PAGE e texto, gera diferença em HTML e JSON. Bom para ver.
- **ocreval / ISRI** [36, 37, F, ANTIGA, mas ativo em UTF-8 até 2021]. 17 programas. O `accuracy` dá acurácia **por classe de caractere**, erros marcados e não marcados, e confusões; há `synctext`, `groupacc`, `accci`, `vote`. Não verifiquei se o `accci` calcula o intervalo que queremos.
- **"Marked character efficiency"** [36]: mede o que acontece quando o usuário examina **só** o marcado. O exemplo do guia: marcar 1,72% do texto e corrigir os erros marcados leva a 96,96% de acurácia. É o conceito certo, e é de 1996.
- **FCA** [50, F]: comparação flexível de substrings, independente da ordem de leitura. Use para separar erro de ordem de erro de caractere.
- **Entity CER e Coverage@k** [24b, A]: CER só nas posições que importam, e fração de entidades recuperadas com até k edições. **Transplante direto para lance.** Nota dos autores: mede recall, então não penaliza o inventado.
- **semCER** [26, A]: peso de severidade por erro, com o nível máximo para "lê-se perfeitamente, é falso, sem sinal de erro". Os autores recomendam como complemento ao CER normalizado, para ordenar erros, não para substituí-lo. Em xadrez, a regra de severidade pode ser escrita à mão, sem juiz LLM.
- **olmOCR-Bench** [28a, A]: testes unitários binários. Dá para escrever testes por livro ("o lance 12 das brancas é ♘f3").

### Revisão humana: o que falta

- **Kuhn et al., CHI EA 2025** [38, A; revisado como resumo estendido]: 36 pessoas, transcrição de fala. Redução de WER de 0,47, 0,48 e 0,45 nas três condições, **sem diferença significativa** (p = 0,767), e cerca de 50% dos erros corrigidos. Confiança de palavras certas e erradas com grande sobreposição. **É fala, não OCR.**
- **Parasuraman e Manzey, 2010** [51, F, ANTIGA]: revisão sobre complacência e viés com automação; apoio imperfeito leva a erros de omissão e de comissão.
- **[?]** Não achei estudo de revisão humana de OCR que meça o erro restante nem o efeito do realce. O que está nesta seção é o substituto mais próximo; a transferência é hipótese.

### Protocolo proposto para este projeto (proposta minha)

**Unidade de medida: o token de xadrez, com classes separadas.**

| Classe | O que conta como erro | Gravidade |
|---|---|---|
| Lance | Figurina, casa, captura, xeque; o SAN normalizado | Máxima se a leitura errada for legal |
| Número de lance | Valor ou "..." | Média; serve de âncora |
| Sinal de avaliação / NAG | ⩲ ⩱ ± ∓ ! ? etc. | Alta: legal sempre |
| Texto corrido | CER e WER usuais | Baixa |
| Diagrama | FEN inteiro exato; casas erradas | Máxima |
| Ordem de leitura | FCA contra CER | Média |

**Quatro números, por classe, por livro:**

1. **Erro bruto:** antes de qualquer sinalização.
2. **Erro que chega ao usuário (silencioso):** token errado **e** sem nenhum sinal **e** legal. É a métrica primária.
3. **Trabalho de revisão:** itens sinalizados por página, tempo por página, e a precisão da fila (quantos sinais eram erro de fato). A curva risco-cobertura [18c] liga 2 e 3: quanto erro silencioso sobra para cada quantidade de sinais.
4. **Erro residual depois da revisão:** o que sobra depois que o usuário termina.
   - Reler de forma independente uma amostra de páginas já "terminadas", ou, melhor,
   - **injetar erros conhecidos**, avisando o usuário, e contar os achados. Dois revisores independentes em uma amostra permitem também estimar por captura e recaptura. Nenhum desses dois métodos está validado em OCR nas fontes que achei.

**Cuidado com o tamanho da amostra.** Com zero erro em N tokens, o limite superior de 95% é cerca de 3/N (regra de três). Com **300 lances** sem erro só se pode afirmar menos de 1%. Para afirmar menos de 0,01% são necessários **cerca de 30.000 lances**. Livros de teste precisam de PGN confiável para chegar lá; livros com partidas já em base são a saída [T].

**Protocolo de ajuste por livro:**

- Separar **por página**, nunca por linha, e reservar páginas de fim de capítulo que não entram em treino. Separar linhas da mesma página infla o resultado.
- Curva de aprendizado em 60, 150, 300, 600, 1.000 linhas, como em [29c]. Registrar também quantos exemplos de cada figurina e sinal entraram.
- Medir regressão no conjunto base. O ajuste por fonte do Tesseract degrada ao passar de 400 iterações [4].
- Testar em pelo menos um livro bom e um ruim. O Seirawan já é o livro de referência do projeto; o outro deveria ser um escaneado difícil.

---

## 8. O que testar, em ordem

Respeitando o limite de carga desta máquina (uma carga por vez).

| # | Teste | Pergunta | Medida de sucesso | Custo |
|---|---|---|---|---|
| 1 | **Linha de base de medição** nas classes da seção 7 | Quanto erro silencioso em lance existe hoje? | Número com intervalo | Baixo: precisa de PGN verdade |
| 2 | **Margem legal com `lstm_choice_mode` (podado)** | A margem pega erro legal? | Erro silencioso cai para a mesma quantidade de sinais | Baixo, sem treino |
| 3 | **Curva de linhas no Tesseract**, com ⩲ ⩱ ± ∓ e figurinas sintéticos + reais | Quantas linhas até estabilizar por classe? | Curva por classe | Médio |
| 4 | **Margem com saídas brutas** (forward exato, C++ ou Calamari) | Melhora sobre o podado? | Idem ao 2 | Médio a alto |
| 5 | **Comitê de 3 a 5 Tesseracts por validação cruzada** | O voto ou a discordância reduz o erro silencioso? | Idem; tempo de CPU | Alto em tempo; começar com 3 modelos |
| 6 | **Segundo leitor diverso:** PP-OCRv6 small/tiny ONNX ou Calamari | Discorda onde o Tesseract erra? | Precisão da discordância como sinal; pico de RAM | Médio |
| 7 | **fenshot** em diagramas escaneados do livro de referência | Melhor que o leitor atual? | FEN inteiro exato | Baixo |
| 8 | **Realce mais rarefeito** | Menos marcas corrigem mais? | Residual e tempo, com usuário real | Baixo; amostra pequena |

**O que eu não faria agora:**

- VLM como leitor principal.
- LLM para corrigir lance.
- Gramática de lance dura na saída (troca erro visível por silencioso; ver a máscara de escrita em [23]).
- `--user-patterns` para SAN.
- PP-StructureV3 nesta RAM.
- Kraken em Windows sem antes confirmar o ambiente.
- Trocar o CER como métrica de decisão: ele continua útil para texto, não para lance.

---

## 9. Fontes

Todas acessadas em 05/11/2026. "Sem data" significa que a página não mostrava data de versão. O rodapé "© 2026" do GitHub não foi tomado como data.

**Motores**

- [1] Tesseract, releases, 5.5.4 em 28 de outubro (ano inferido: 2026). https://github.com/tesseract-ocr/tesseract/releases
- [2] Tesseract, API examples, `lstm_choice_mode`, sem data. https://tesseract-ocr.github.io/tessdoc/APIExample.html
- [2b] Tesseract, user patterns, sem data (exemplos de 2019). https://github.com/tesseract-ocr/tessdoc/blob/main/APIExample-user_patterns.md
- [3] Tesseract, Training Tesseract 5, sem data. https://github.com/tesseract-ocr/tessdoc/blob/main/tess5/TrainingTesseract-5.md
- [4] Tesseract, How to train 4.00, sem data; o mais detalhado sobre ajuste, ainda válido segundo o tess5 [ANTIGA]. https://tesseract-ocr.github.io/tessdoc/tess4/TrainingTesseract-4.00.html
- [5] Tesseract, manual tesseract(1), ramo main. https://github.com/tesseract-ocr/tesseract/blob/main/doc/tesseract.1.asc
- [5b] Tesseract, wiki ImproveQuality [ANTIGA]. https://github.com/tesseract-ocr/tesseract/wiki/ImproveQuality/6da308e6579e3d9c79da2ad937f8c0e9f94cc9dd
- [5c] Tesseract, issue 3070, data não lida. https://github.com/tesseract-ocr/tesseract/issues/3070
- [6] Tesseract, referência `LSTMRecognizer`, 5.x. https://tesseract-ocr.github.io/tessapi/5.x/a03506.html
- [7] Kraken 7.1, treino de reconhecimento, sem data. https://kraken.re/7.1/_sources/user_guide/training_recognition.rst.txt
- [8] Kraken, repositório, sem data. https://github.com/mittagessen/kraken
- [9] Kraken 5.0.0, referência da API [versão antiga]. https://kraken.re/5.0.0/api_docs.html
- [10] calamari-ocr no PyPI, 2.3.1 em 12/11/2024. https://pypi.org/project/calamari-ocr/
- [11] Calamari, uso pela linha de comando, sem data. https://calamari-ocr.readthedocs.io/en/latest/doc.command-line-usage.html
- [12] PaddleOCR, módulo de reconhecimento, sem data. https://www.paddleocr.ai/latest/en/version3.x/module_usage/text_recognition.html
- [13] PaddleOCR, pipeline OCR, sem data. https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html
- [14] PP-OCRv6, documentação, sem data. https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv6/PP-OCRv6.html
- [15] PP-OCRv5, documentação, e discussões de usuários no GitHub (dicionário, baixo peso), sem data. https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PP-OCRv5/PP-OCRv5.en.md e https://github.com/PaddlePaddle/PaddleOCR/discussions/15712
- [16] Cui et al., PaddleOCR 3.0 Technical Report, 08/07/2025. https://arxiv.org/abs/2507.05595
- [16b] PP-StructureV3, documentação, sem data; tempos e RAM em CPU. https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-StructureV3/PP-StructureV3.html
- [17a] docTR, repositório, v1.1.0, sem data. https://github.com/mindee/doctr
- [17b] docTR, modelos e benchmarks, sem data. https://mindee.github.io/doctr/using_doctr/using_models.html
- [17c] docTR, treino customizado, sem data. https://mindee.github.io/doctr/using_doctr/custom_models_training.html
- [17d] PARSeq, repositório, ECCV 2022, última atualização 22/02/2024 [ANTIGA]. https://github.com/baudm/parseq
- [17e] ABINet, repositório, CVPR 2021 [ANTIGA]. https://github.com/FangShancheng/ABINet
- [17f] OCRmyPDF, repositório, sem data. https://github.com/ocrmypdf/OCRmyPDF
- [17g] OCRmyPDF, cookbook, v17. https://ocrmypdf.readthedocs.io/en/latest/cookbook.html
- [20a] EasyOCR, repositório, 1.7.2 em 24/09/2024 [ANTIGA]. https://github.com/JaidedAI/EasyOCR
- [20b] EasyOCR, documentação, sem data. https://www.jaided.ai/easyocr/documentation/
- [21] Surya, repositório, Surya 2.5, sem data. https://github.com/datalab-to/surya
- [22] Li et al., TrOCR, 21/09/2021, revisto em 06/09/2022 [ANTIGA]. https://arxiv.org/abs/2109.10282

**VLMs e alucinação**

- [23] Karamolegkou et al., Reading or Guessing?, v2 em 07/09/2026. https://arxiv.org/html/2605.27750v2
- [24] Gardella et al., When Low CER is Not Enough, 27/07/2026. https://arxiv.org/html/2607.24077v1
- [24b] Mariño et al., Entity-Aware Evaluation of OCR Systems, v3 em 04/11/2026. https://arxiv.org/html/2610.33004
- [24c] He et al., KIE-HVQA, 25/06/2025, NeurIPS 2025. https://arxiv.org/abs/2506.20168
- [25] Beyene e Dancy, Survey of OCR Evaluation Methods, 26/03/2026. https://arxiv.org/html/2603.25761v1
- [26] Nguyen e Zang, Equal CER, Unequal Damage, out/2026 (pelo identificador). https://arxiv.org/html/2610.20461
- [27] Agbeti-Messan et al., State-Space Models vs. Transformers, 01/04/2026; melhor artigo na ICDAR 2026. https://arxiv.org/html/2604.00725v1
- [28a] Poznanski et al., olmOCR 2, 22/10/2025. https://arxiv.org/html/2510.19817v1
- [28b] Taghadouini et al., LightOnOCR, 20/01/2026, v2 em 30/06/2026. https://arxiv.org/html/2601.14251v1
- [28c] LightOnOCR-2-1B, cartão do modelo, jan/2026. https://huggingface.co/lightonai/LightOnOCR-2-1B
- [28d] dots.ocr, repositório, dots.mocr em 19/03/2026. https://github.com/rednote-hilab/dots.ocr
- [28e] Cui et al., PaddleOCR-VL-1.5, 29/01/2026, v2 em 03/04/2026. https://arxiv.org/abs/2601.21957
- [28f] MinerU, repositório, 4.1, sem data. https://github.com/opendatalab/MinerU
- [28g] Mistral, Introducing Mistral OCR 3 e changelog, datas em conflito na página. https://mistral.ai/news/mistral-ocr-3/ e https://docs.mistral.ai/resources/changelogs
- [28h] GOT-OCR 2.0, repositório, 03/09/2024. https://github.com/Ucas-HaoranWei/GOT-OCR2.0
- [28i] Nougat, repositório, 2023 [ANTIGA]. https://github.com/facebookresearch/nougat
- [28j] Dilhara e Jayatilleke, Cross-Temporal Sinhala OCR, 30/06/2026. https://arxiv.org/abs/2606.29378

**Fusão, restrição e calibração**

- [18] Slossberg et al., On Calibration of Scene-Text Recognition Models, 23/12/2020 [ANTIGA]. https://arxiv.org/html/2012.12643
- [18b] Guo et al., On Calibration of Modern Neural Networks, ICML 2017 [ANTIGA]. https://arxiv.org/abs/1706.04599
- [18c] Geifman e El-Yaniv, Selective Classification for DNNs, 23/05/2017 [ANTIGA]. https://arxiv.org/abs/1705.08500
- [18d] Angelopoulos e Bates, Conformal Prediction, 15/07/2021 [ANTIGA]. https://arxiv.org/abs/2107.07511
- [19] Tarride et al., Language Models in PyLaia, 29/04/2024. https://arxiv.org/html/2404.18722
- [29a] ISRI e citação secundária de Rice et al. 1996, por Reul et al., 2017 [ANTIGA]. https://arxiv.org/pdf/1711.09670
- [29b] Lund, Walker e Ringger, ICDAR 2011 [ANTIGA; só o resumo]. https://bibtex.github.io/ICDAR-2011-LundWR.html
- [29c] Reul et al., JLCL 33(1), fev/2018 [ANTIGA, sem substituto achado]. https://arxiv.org/abs/1802.10038
- [29d] Darmanin, LV-ROVER-MLT, 31/08/2026. https://arxiv.org/pdf/2607.00250
- [29e] Scheidl et al., Word Beam Search, ICFHR 2018 [ANTIGA]. https://repositum.tuwien.ac.at/handle/20.500.12708/924
- [29f] Torchaudio 2.8, decodificadores; fase de manutenção. https://docs.pytorch.org/audio/2.8/models.decoder.html
- [29g] Graves et al., CTC, ICML 2006, §4.1 [ANTIGA, fundamento]. https://www.cs.toronto.edu/~graves/icml_2006.pdf
- [29h] Hemmer et al., Confidence-Aware OCR Error Detection, 06/09/2024. https://arxiv.org/abs/2409.04117

**Xadrez**

- [30] Baird e Thompson, Reading Chess, IEEE TPAMI 12(6), jun/1990 [ANTIGA; só resumo]. DOI 10.1109/34.56191. Registro: https://search.isc.ac/inventory/49/1368636.htm
- [31] `chess_ocr`, repositório, sem data. https://github.com/jamesk14022/chess_ocr
- [31b] chessPDFBrowser, SourceForge, e fórum do Chess.com (baixo peso). https://sourceforge.net/projects/chesspdfbrowser1/ e https://www.chess.com/forum/view/chess-equipment/convert-pdf-into-a-chess-format?page=2
- [31c] Automated Conversion of Chess Diagrams in PDF to PGN, IJARCCE, mai/2025 (periódico de baixo peso). https://ijarcce.com/wp-content/uploads/2025/05/IJARCCE.2025.14549.pdf
- [32] Eken et al., Framework for Recognition and Animation of Chess Moves, IAJIT 15(1), jan/2018 (recebido em 2015) [ANTIGA]. https://www.iajit.org/PDF/January%202018,%20No.%201/10599.pdf
- [33] Seytre, ChessQueries, ago/2026 (pelo identificador). https://arxiv.org/html/2608.30762v1
- [34a] Majid e Eicher, J. Imaging 8(2):31, 30/01/2022 [ANTIGA]. https://pmc.ncbi.nlm.nih.gov/articles/PMC8879196/
- [34b] Eicher et al., ICDAR Workshops 2021 [ANTIGA; só resumo]. https://dl.acm.org/doi/abs/10.1007/978-3-030-86198-8_18
- [34c] Hayashi e Hirata, ICPR 2022, arXiv 2024. https://arxiv.org/abs/2406.06538
- [34d] `chess-scoresheet-scanner`, repositório, sem data. https://github.com/Saahan2014/chess-scoresheet-scanner
- [35a] fenshot, repositório, sem data. https://github.com/scoriiu/fenshot
- [35b] Chess_diagram_to_FEN, repositório, sem data. https://github.com/tsoj/Chess_diagram_to_FEN
- [35c] chessboard-recognizer, repositório, e relato no Lichess (baixo peso, ~7 anos). https://github.com/linrock/chessboard-recognizer e https://lichess.org/forum/general-chess-discussion/open-source-tool-for-converting-chessboard-images-into-fen
- [35d] tensorflow_chessbot, repositório, 2015-16 [ANTIGA]. https://github.com/Elucidation/tensorflow_chessbot
- [35e] Fenify-3D, repositório, 2022 [ANTIGA]. https://github.com/notnil/fenify-3D
- [35f] Mallasén Quintana et al., LiveChess2FEN, 12/12/2020 [ANTIGA]. https://arxiv.org/abs/2012.06858
- [35g] Masouris e van Gemert, End-to-End Chess Recognition (ChessReD), VISAPP 2024. https://arxiv.org/abs/2310.04086

**Layout**

- [40] PaddleOCR, detecção de layout, sem data. https://www.paddleocr.ai/latest/en/version3.x/module_usage/layout_detection.html
- [41] PP-DocLayout, 21/03/2025. https://arxiv.org/abs/2503.17213
- [42] Cui et al., RT-DocLayout, jun/2026 (pelo identificador). https://arxiv.org/html/2606.23344v1
- [43] DocLayout-YOLO, repositório, out/2024. https://github.com/opendatalab/DocLayout-YOLO
- [44] LayoutParser, repositório, sem data. https://github.com/Layout-Parser/layout-parser
- [45] Liu et al., XY-Cut++, 14/04/2025, v3 em 28/01/2026. https://arxiv.org/abs/2504.10258
- [46] Wang et al., LayoutReader, EMNLP 2021 [ANTIGA]. https://arxiv.org/abs/2108.11591 ; repositório: https://github.com/ppaanngggg/layoutreader
- [47] Hakim et al., Reading Order Inference, 01/07/2026. https://arxiv.org/html/2607.01018v1

**Métricas e revisão**

- [36] Rice e Nartker, The ISRI Analytic Tools, TR-96-02, ago/1996 [ANTIGA, ainda útil]. https://github.com/eddieantonio/ocreval/raw/master/user-guide.pdf
- [37] ocreval, repositório, copyright até 2021 [ANTIGA]. https://github.com/eddieantonio/ocreval
- [38] Kuhn, Kersken e Zimmermann, Evaluating ASR Confidence Scores, CHI EA 2025. https://arxiv.org/html/2503.15124v1
- [39] Tuggener et al., Deep Learning in the Wild, 2018 [ANTIGA; só o trecho visto na busca]. https://arxiv.org/pdf/1807.04950
- [48] Neudecker et al., A Survey of OCR Evaluation Tools and Metrics, HIP 2021 [ANTIGA; só resumo]. https://primaresearch.org/publications/HIP21_CNeudecker_OcrEvalSurvey
- [49] dinglehopper, repositório, sem data. https://github.com/qurator-spk/dinglehopper
- [50] Clausner, Pletschacher e Antonacopoulos, Flexible Character Accuracy, Pattern Recognition Letters 131, 2020 [ANTIGA]. https://primaresearch.org/publications/PRL_Clausner_FlexibleCharacterAccuracy
- [51] Parasuraman e Manzey, Human Factors 52(3), 2010 [ANTIGA; só resumo]. https://pubmed.ncbi.nlm.nih.gov/21077562/

**Não consegui ler:** Unraveling Confidence (2023, HTTP 403): https://dl.acm.org/doi/10.1007/978-3-031-41734-4_7 . O texto integral de [30].
