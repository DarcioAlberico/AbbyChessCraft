# O que o PyBoxEditor dá ao AbbyChessCraft

Análise de `C:\Python-Chess2\PyBoxEditor_Tkinter` (commit `312d6d7`, 2026-10-10) para decidir
o que entra no AbbyChessCraft, o aplicativo de OCR de livros de xadrez com treino no estilo
do FineReader. Todos os números abaixo vêm dos relatórios e documentos do próprio
PyBoxEditor, que mede cada fase antes de dá-la por concluída.

## Veredito

O PyBoxEditor já resolve a parte difícil do AbbyChessCraft. O reconhecimento de glifos,
o treino, os diagramas, a leitura de PDF e a exportação existem, estão testados (cerca de
3.500 testes, cobertura de 87,5 %) e têm número medido. O que falta é a experiência de uso
no estilo do FineReader, e não o motor.

**Recomendação:** o AbbyChessCraft usa o `core/` do PyBoxEditor como biblioteca instalada
(`pip install -e C:\Python-Chess2\PyBoxEditor_Tkinter`), sem copiar código. O `core/` não
importa Tkinter nem nada de `ui/`, e o projeto já gera wheel. Copiar 40 mil linhas criaria
duas versões divergentes do mesmo leitor, e cada correção teria de ser feita duas vezes.
O AbbyChessCraft fica com a interface nova, o fluxo de treino por livro e o que estiver
listado em "Lacunas".

## O treino, que é o que mais importa

O PyBoxEditor tem três níveis de treino, e os três servem ao clone.

| Peça | O que faz | Medido | Uso no clone |
|---|---|---|---|
| `core/learner.py` (`CharacterLearner`) | Vizinho mais próximo sobre os recortes rotulados. Grava a amostra e a usa na leitura seguinte, sem retreinar nada | 3,7 ms por predição, carga em 0,2 s com cache; nos casos difíceis a cadeia com ele acerta 88,5 % contra 72,4 % da rede sozinha | **Direto.** É o equivalente do treino de padrões do FineReader: corrigiu, já vale |
| `core/neural_trainer.py` + `core/neural_model.py` (`SimpleCNN`) | Rede de glifos sobre recortes de 32×32, com aumento de dados, amostragem por classe, parada antecipada e relatório | 316 classes, 626 mil amostras; teste 99,76 % de acerto global e 99,14 % de recall macro | **Direto.** O relatório já lista as piores classes, as confusões e grava as amostras erradas |
| `core/learner.py` (`char_to_folder`, `folder_to_char`) | Formato da base: uma pasta por classe, com ligaduras (`ligature_ffi`), símbolos por código (`sym_9814` = ♖) e ida e volta estrita | Corrigiu um defeito em que 127 amostras treinavam a classe errada sem aviso | **Direto.** Adotar como formato da base do clone |
| `core/coleta.py` | Quarentena: o que a rede leu com baixa confiança vai para `revisao_ocr/<palpite>/`, o usuário confere, e só então é promovido à base | 3.943 recortes coletados em 264 páginas do Chess Evolution 1 | **Direto.** Impede treinar o modelo no próprio erro |
| `core/treino_diagrama.py` | A correção de um diagrama vira amostra das peças. Casa não tocada só entra com "conferi o diagrama inteiro" | Base atual: 2.271 peças e 5.076 casas de ocupação | **Direto** |
| `core/ocr_phase7.py` | Correções versionadas, divisão sem vazamento entre livros, amostragem ativa, calibração por domínio e manifesto de pesos com checksum | Testado; usado pelo treino de linhas | **Direto**, para o treino incremental ter proveniência |
| `core/linha_trainer.py` (CRNN/CTC por linha) | Treina a linha inteira, sem um box por caractere | **Não utilizável hoje.** O último treino terminou com 96,34 % de erro por caractere, com 333 linhas de treino contra 1.136 de validação, uma divisão invertida | **Refazer** antes de usar. O portão `modelo_utilizavel` (erro máximo de 15 %) já o bloqueia corretamente |

O fluxo da interface está em `ui/treino.py`: aprender com a página, verificar e corrigir a
base, treinar a rede, criar e promover recortes para revisão e treinar o modelo de
diagramas. A lógica é reaproveitável. A janela Tkinter, não.

## A leitura de glifos e da página

| Peça | O que faz | Medido |
|---|---|---|
| `core/livro.py` | O leitor de produção. A rede de glifos ancora os lances, o Tesseract lê a prosa e os dois se fundem palavra a palavra | 1,59 % de erro por caractere ponderado no corpus de referência, a 300 dpi |
| `core/geometria_da_linha.py` | Separa letras de mesmo desenho e corpo diferente (`s`/`S`, `o`/`O`/`0`) pela altura votada da linha | Usado nas exportações |
| `core/leitura_de_linha.py` | Lê a linha inteira com o EasyOCR e realinha o resultado aos boxes | 91,2 % por linha contra 72,8 % caractere a caractere |
| `core/notacao.py` | Usa a legalidade do lance, pela biblioteca `chess`, para escolher entre leituras | Descarta a maioria das leituras erradas sem treino |
| `core/lexico.py` | Dicionário da prosa. Palavra desconhecida é sinalizada, nunca corrigida | Não toca em notação |
| `config/profiles/` | Perfis de figurina: um jogo de peças para os dois lados, ou maiúscula branca e minúscula preta | Necessário por livro |

## Os diagramas

| Peça | O que faz | Medido |
|---|---|---|
| `core/deteccao_de_tabuleiro.py` | Acha o tabuleiro direto na imagem e corrige a perspectiva, sem depender da segmentação de caracteres | Resolveu uma página que levava 256 s |
| `core/diagrama.py` | Lê o resíduo de cada casa (casa menos o fundo mediano), com uma rede para ocupação e outra para a peça, e arbitra pela legalidade da posição | Ocupação 99,31 %; peça 98,0 % num livro fora do treino; tabuleiro inteiro 92,5 % |
| `core/lado_a_jogar.py` | Lê de quem é a vez na legenda e nunca assume brancas em silêncio | — |
| `core/render_diagrama.py` | Redesenha o diagrama a partir do FEN com fonte de xadrez (SkakNew-Diagram, ChessMerida-Diagram) | — |
| `core/tabuleiro_edicao.py` | O estado da edição casa a casa, sem Tk | — |

Um tabuleiro em cada treze ainda sai com algum erro. Por isso o clone precisa manter a
conferência lado a lado, recorte e posição na mesma escala, como faz `ui/dialogo_diagrama.py`.

## PDF, revisão e exportação

| Peça | O que faz | Medido |
|---|---|---|
| `core/pdf_nativo.py` | Lê o PDF nascido digital pela própria camada de texto e decodifica os diagramas compostos em fonte de xadrez. A régua decide por página | Dvoretsky 2025: 815 de 816 páginas, 1.273 diagramas exatos |
| `core/mapa_glifos.py` | Reescreve só a tabela `ToUnicode` de PDFs com figurinas sem mapa. A página não muda um pixel | 216 glifos corrigidos no Yusupov |
| `core/searchable_pdf.py` | Acrescenta a camada de texto invisível sem rasterizar a página | — |
| `core/editorial_model.py` e `editorial_review.py` | Documento intermediário versionado e fila de suspeitas com diário de decisões | 23 linhas apontadas, 23 erros reais, nenhum falso positivo |
| `core/exportar.py` e `core/editor/` | EPUB e DOCX com a fonte embutida; HTML, TXT, PDF e PGN pelo editor | Mesma sequência de blocos em todos os formatos |

## O que não levar

- **A interface Tkinter** (`ui/`). A janela principal tem 1.961 linhas e foi feita para editar
  boxes. O clone precisa de outra experiência, descrita abaixo.
- **`core/biblioteca/`.** O próprio projeto a classifica como biblioteca de inspeção, fora da
  produção. Inclui `abbyy_ocr.py`, a integração com o FineReader instalado, que ninguém chama.
- **Os scripts de medida** (`scripts/medidas/`). Ficam no PyBoxEditor, que é onde se mede.

## Lacunas para o AbbyChessCraft

1. **Treino por livro.** Hoje a base é única para todos os livros. O FineReader guarda um
   conjunto de padrões por documento. Proposta: uma camada do k-NN por livro sobre a rede
   global, para que a correção de um livro não contamine outro e possa ser descartada.
2. **Edição de zonas na página.** Não há marcação manual de áreas de texto, diagrama, tabela e
   imagem. O analisador de layout que existe está na biblioteca e erra colunas quando uma
   linha cruza a calha.
3. **Modelo de linhas.** O CRNN/CTC precisa ser retreinado com a divisão correta antes de entrar
   na cadeia.
4. **Fluxo de verificação no estilo do FineReader.** Imagem e texto lado a lado, caracteres
   duvidosos destacados, correção com uma tecla e a correção alimentando o treino na hora.
   As peças existem (`editorial_review`, `coleta`, `learner`). Falta a tela.
5. **Fonte de diagrama nova.** Num livro novo a peça acerta 98 %, mas uma fonte de peças nunca
   vista pede amostras. O clone deve oferecer a colheita a partir da conferência desde o
   primeiro diagrama.

## Riscos a acompanhar

- **Duas versões de PyTorch.** O aplicativo roda no Python 3.13 do sistema com torch 2.14, e a
  suíte roda no `.venv` com torch 2.10. O clone deve fixar uma versão.
- **Pesos e bases fora do git.** `custom_model.pth` (2,8 MB) e `training_data.7z` (241 MB) não
  estão versionados. O clone depende deles e precisa saber de onde carregá-los, de preferência
  pelo pacote verificável de `scripts/empacotar_modelo.py`.
- **Tesseract é executável à parte**, procurado em `C:\Program Files\Tesseract-OCR`.
