# O FineReader PDF 15/16 como referência (fontes públicas)

Levantamento de 2026-10-15 para a spec do AbbyChessCraft (`docs/SPEC.md`). **Só fontes
públicas**: a ajuda online da ABBYY, o guia do usuário do FineReader PDF 16 em PDF, artigos do
suporte e páginas de produto. Nenhum software da ABBYY foi baixado, descompilado ou analisado:
o AbbyChessCraft é um projeto de sala limpa, que reproduz o que o produto faz, não como faz.

Fonte principal, citada como **[UG16 p.N]**: FineReader PDF 16 User's Guide,
<https://help.abbyy.com/assets/en-us/finereader/16/Users_Guide.pdf>.
**[NÃO VERIFICADO]** marca o que não achei em fonte oficial; **[INFERÊNCIA]**, dedução.

## 1. Os painéis do OCR Editor

Fontes: [UG16 p.187–190]; <https://help.abbyy.com/en-us/finereader/16/user_guide/ocrwindow>.

| Painel | O que faz |
|---|---|
| Pages | Miniaturas (*Thumbnails*) ou lista com propriedades (*Details*). Duplo clique abre a página; arrastar reordena; páginas se movem entre projetos e entre instâncias abertas. |
| Image | A página, com as áreas e o painel *Area Properties*. |
| Text | O texto reconhecido, com verificação ortográfica, edição e formatação, e o painel *Text Properties*. |
| Zoom | A **linha atual** ampliada, para comparar o desenho do caractere com o reconhecido. |
| Warnings | Avisos e erros da página. |

- **Sincronia** [UG16 p.224]: clicar numa palavra no Text destaca a região dela no Image e a
  amplia no Zoom; selecionar uma área mostra as propriedades dela. Rolagem sincronizada
  contínua Image↔Text não é documentada no OCR Editor **[NÃO VERIFICADO]**; só no *Compare
  Documents*.
- **Arranjo** (<https://help.abbyy.com/en-us/finereader/15/user_guide/hotkeys>): F5 mostra ou
  esconde Pages; F6 só Image; F7 Image + Text; F8 só Text; Ctrl+F5 Zoom. Ctrl+Tab e
  Ctrl+Shift+Tab andam entre painéis; Alt+1 a Alt+4 vão a Pages, Image, Text e Zoom.
  Docking livre, janelas flutuantes e multimonitor não são documentados **[NÃO VERIFICADO]**.
- **Zoom e páginas**: Ctrl++, Ctrl+−, Ctrl+0 (Best Fit); Ctrl+G vai à página; Ctrl+↓/↑ e
  Ctrl+Home/End.
- **Barras**: a principal é fixa; a *Quick Access Bar* é personalizável; atalhos se
  reatribuem em Customize (<https://support.abbyy.com/hc/en-us/articles/21755986137363>).
- **Options › Areas and Text** [UG16 p.301]: cor do realce de baixa confiança, cor e
  espessura da borda por tipo de área, fonte do texto simples e regras da verificação.

## 2. A verificação

Fontes: [UG16 p.223–226]; <https://help.abbyy.com/en-us/finereader/16/user_guide/checkingtext>.

- Os caracteres de baixa confiança vêm realçados no Text, com um botão para ligar e desligar.
- **Alt+↓ / Alt+↑**: próximo e anterior erro. **Ctrl+T**: marcar o texto como verificado.
- **Diálogo Verification** (Ctrl+F7): Skip, Replace (pela sugestão), Add to Dictionary,
  troca de fonte e efeitos, *More Symbols…* por subconjunto Unicode ou código.
- Dicionários do usuário (Ctrl+Alt+D), compartilháveis em rede [UG16 p.199].
- Na exportação DOCX, "Highlight low-confidence characters" leva o realce ao Word
  (<https://help.abbyy.com/en-us/finereader/16/user_guide/docx_settings>).

## 3. Áreas

Fontes: [UG16 p.204–214]; <https://help.abbyy.com/en-us/finereader/16/user_guide/editareas>.

- Tipos: Recognition, Text, Picture, Background Picture, Table, Barcode (Ctrl+1 a Ctrl+6).
  Picture também serve para **não reconhecer** um trecho, que é como um diagrama de xadrez
  fica fora do texto.
- Desenho por ferramenta ou modificador (Ctrl+Shift texto, Alt+Shift imagem, Ctrl+Alt
  tabela); áreas poligonais (*Add Part*, *Delete Part*); Ctrl+clique seleciona várias;
  Ctrl+Shift+B reconhece só a área escolhida.
- **Ordem**: a ferramenta *Order Areas* deixa o usuário clicar as áreas na ordem de saída.
- **Area Properties**: idioma, **função** (cabeçalho, rodapé, nota de rodapé), orientação,
  tipo de impressão, inversão.
- **Templates** de áreas (.blk/.blkx) aplicados a páginas escolhidas ou a todas, com a mesma
  resolução [UG16 p.210].

## 4. Layout e estrutura

- Detecção de cabeçalhos e rodapés, notas, sumários e listas (Options › OCR, [UG16 p.335]);
  desligada, esses elementos saem como corpo do texto.
- Modos Thorough e Fast; PDF em Auto, Use OCR ou Use Only Text from PDF [UG16 p.333–334].
- **Style Editor** (<https://help.abbyy.com/en-us/finereader/16/user_guide/editstyle>):
  estilos detectados, editáveis e mescláveis, com navegação *Previous/Next Fragment* entre
  trechos do mesmo estilo.
- Exportação DOCX/RTF/ODT: manter cabeçalhos, rodapés e números de página; manter quebras de
  linha e hífens; manter quebras de página; manter negrito e itálico no texto simples.

## 5. Treino de padrões, idiomas e dicionários

Fontes: [UG16 p.216–221]; <https://help.abbyy.com/en-us/finereader/16/user_guide/createcustlang>.

- *Use training to recognize new characters and ligatures*, com ou sem os padrões embutidos.
- **Pattern Training**: a cada caractere desconhecido, o usuário digita o que é, com efeitos
  (negrito, itálico, sobrescrito, subscrito) e **Back** para voltar. Na documentação do
  FineReader Engine o quadro tem **Move Left/Right** para enquadrar o glifo ou a ligadura, e
  **Skip** (<https://help.abbyy.com/en-us/finereaderengine/12/user_guide/apireference_patterntrainingdialog>;
  igual no desktop **[NÃO VERIFICADO]**).
- Ligaduras de 2 ou 3 caracteres; até 1.000 caracteres por padrão; o padrão vale para a mesma
  fonte, tamanho e resolução; o contexto decide O ou 0.
- **Pattern Editor**: New, Edit (mudar caractere e efeito, apagar glifos mal cortados), Set
  Active (<https://support.abbyy.com/hc/en-us/articles/360012175859>).
- **Idiomas do usuário**: alfabeto editável, dicionário (nenhum, embutido, do usuário ou
  **expressão regular**), caracteres proibidos e de início e fim de palavra. A sintaxe de
  regex está em [UG16 p.348]. **Para xadrez**: um "dicionário" que é a regex dos lances.

## 6. Localizar, substituir e editar

- Ctrl+F, F3, Ctrl+H. **Regex ou curingas no Find/Replace não são documentados**: o guia só
  traz "Match Case" e "Whole word" **[NÃO VERIFICADO; provavelmente ausente]**. Regex só
  existe como dicionário de idioma. Aqui o AbbyChessCraft pode ser melhor que o FineReader.
- Ctrl+B, Ctrl+I, Ctrl+U; tabelas editáveis no Text; "Recognize and Copy Text" (Ctrl+C) e
  "Copy Area as Image" (Ctrl+Shift+C).

## 7. Lote e pré-processamento

- Ao abrir páginas: Recognize, Analyze ou só Preprocess [UG16 p.300, 330]; núcleos de CPU
  configuráveis.
- Pré-processamento [UG16 p.331]: dividir páginas espelhadas, orientação, deskew,
  **endireitar linhas**, resolução, bordas, branquear fundo, ruído, borrão, **trapézio**,
  cores invertidas, preto e branco, marcas coloridas.
- **Image Editor** (Ctrl+I; <https://help.abbyy.com/en-us/finereader/16/user_guide/adjustimage>):
  as mesmas ferramentas à mão, aplicáveis a páginas pares, ímpares, atual ou escolhidas.
- **Hot Folder** (<https://help.abbyy.com/en-us/finereader/16/user_guide/hotfolder>): tarefas
  por pasta, agendadas ou vigiando a pasta.

## 8. Exportação

Fontes: [UG16 p.231–239, 302–316].

- Modos: Exact copy, Editable copy, Formatted text, Plain text (e Flexible layout no HTML).
- PDF pesquisável: só texto e figuras, texto sobre a imagem, texto sob a imagem (MRC);
  PDF/A, PDF/UA, marcadores pelos títulos, tags
  (<https://support.abbyy.com/hc/en-us/articles/19098939370515>).
- DOCX, RTF, ODT, XLSX, CSV, PPTX, TXT, HTML (com sumário e divisão por título), EPUB e FB2
  (capa, fontes embutidas), DjVu.

## 9. Outros

- **Compare Documents** (<https://help.abbyy.com/en-us/finereader/16/user_guide/start_compare>):
  duas versões lado a lado com rolagem sincronizada e lista de diferenças.
- O projeto OCR guarda imagens, texto, configurações, padrões e idiomas.

## Ferramentas de xadrez

| Ferramenta | O que faz | Fonte |
|---|---|---|
| Chessvision.ai eBook Reader | Analisa o PDF uma vez; duplo clique no diagrama abre o tabuleiro com engine | <https://chessvision.ai/blog/ebook-reader-launch> |
| Chessify | Foto do diagrama → FEN; falha em fontes antigas | <https://ingram-braun.net/erga/2020/04/converting-chess-diagrams-to-machine-readable-fen-with-chessify/> |
| ChessOcr (Android) | Câmera → PGN/FEN | <https://apkcombo.com/chessocr-ocr-chess-diagrams/com.kgroth.chessocr/> |
| Chess PDF Browser | Java; OCR de diagrama para FEN e `pdf2pgn` | <https://www.sourceforge.net/p/chesspdfbrowser1> |
| chesspdf (PyPI) | PDF nativo decodificado; scan por modelo de visão; **aceita a posição só se a solução impressa for legal a partir dela** | <https://pypi.org/project/chesspdf/> |

Não achei OCR de livro escaneado da ChessBase, nem ferramenta pública que leia a notação com
figurinas (♘♗) de forma documentada **[NÃO VERIFICADO]**: é a lacuna que o AbbyChessCraft
ocupa.

## O que entra na spec

1. Os quatro painéis sincronizados e os presets de arranjo por tecla de função.
2. Verificação com Alt+↓/↑ e página verificada (Ctrl+T).
3. Áreas com função (cabeçalho, rodapé, nota, legenda), ordem de leitura editável e modelos
   de área para páginas pares e ímpares.
4. Localizar e substituir com regex no livro inteiro, que o FineReader não tem.
5. Diagrama como tipo de área próprio, com a posição validada pelos lances do texto (a ideia
   do chesspdf).
6. Regex de lances e alfabeto com figurinas como "idioma" do livro.
