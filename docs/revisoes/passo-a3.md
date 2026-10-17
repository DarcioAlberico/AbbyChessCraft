# Passo A3 — Documento e sincronia (§6.1, §6.2)

Ramo `passo-a3-documento`, a partir da tag `passo-a2` (965b0fe).

## O que o passo fez

- **O Documento** (`abbychess/app/documento.py`, `VistaDoDocumento`): a página montada num
  `QTextDocument` a partir do documento derivado (`texto.montar`, agora com
  `com_os_nao_lidos` para a vista mostrar como □ os glifos que ninguém leu), no modo
  `impresso`. Uma linha impressa por parágrafo; título, margens (cabeçalho, rodapé, número de
  página, em cinza pequeno; Ctrl+Shift+H os oculta) e notas com formato próprio.
- **O mapa posição → gid** no `QTextBlockUserData` de cada parágrafo (o gid de cada
  caractere), não num formato por glifo. O documento anterior sai a cada montagem.
- **Os diagramas** no lugar deles: o desenho da posição lida (ou o recorte, se não lida), a
  linha do diagrama em monoespaçado, o estado e "Copiar FEN" (mouse e teclado).
- **O realce** (liga e desliga na barra do Documento): fundo laranja-claro no que vai para a
  revisão e no não lido, ondulado no desconhecido do léxico, pontilhado no virtual.
- **O corpo**: Ctrl++/−/0 com o foco no Documento mudam o corpo; na Imagem, o zoom.
- **Só leitura** até o D1.
- **A faixa Linha** (`abbychess/app/linha.py`, Ctrl+F5): a linha do glifo atual ampliada,
  a imagem em cima e o texto embaixo, glifo a glifo; 80 px, 96 em janelas altas.
- **A sincronia** (`app/espaco.py`): o clique numa palavra do Documento a contorna na Imagem
  (um item próprio, tracejado, que não apaga o da verificação) e leva o glifo ao Inspetor; o
  cursor andando contorna a palavra e mostra a Linha, e a Imagem rola só com Seguir; o clique
  na Imagem e a fila levam o cursor do Documento ao glifo e o mostram.
- **Sem perder o lugar** (CA-6.5): montar de novo devolve o cursor e a seleção aos mesmos
  glifos (gid e deslocamento) e a rolagem ao valor de antes.

## Decisões

| Decisão | Por quê |
|---|---|
| Uma linha impressa por parágrafo, sem refluir | refluir pede os parágrafos do layout (passo F); sem eles, o título e o corpo da mesma área se juntavam num parágrafo só (visto na captura) |
| Os glifos não lidos entram na vista como □ | o realce "aguardando leitura" e "sem leitura" de §6.1 é deles, e a Linha e o clique precisam deles; o texto e a exportação continuam só com os lidos |
| O contorno do cursor do Documento é outro item do visor | o da palavra em verificação continua o mesmo; os dois aparecem juntos |
| O estado "confiável pelos lances" fica para o H | depende da validação pelos lances, que é do passo H |
| A paleta (F2) não vale no Documento até o D1 | ela insere símbolos, e o Documento é só leitura; o teste do registro a declara |
| O CA-F.1 (gestos da fatia) continua pendente | o replay conta gestos contra as linhas com `texto_verificado`, e nenhuma está verificada ainda (é do usuário, `ferramentas/rotular.py`) |
| A x-height da Linha (CA-3.2, pendência do A2) | ≥ 12 px em 1366×768 e 1280×720, no índice 25 do livro de referência ([livro_real]) |

## Verificação

- Suíte rápida (671, 53 s depois de tirar o dicionário português dos testes do
  `lexico.txt`, onde ele não era o assunto), ruff limpo.
- `tests/test_documento.py`: o mapa (ida e volta, o caractere à direita do cursor, o espaço),
  montar de novo não deixa documentos vivos, as margens, o realce, o ondulado e o pontilhado,
  o corpo, só leitura, o diagrama com a linha, o estado e Copiar FEN; na janela, CA-6.1 (o
  contorno é o da palavra clicada), a Imagem e a fila levam o cursor, CA-6.5 (o cursor e a
  rolagem; a seleção), o cursor contorna a palavra certa e a Linha é a dela, o contorno da
  verificação fica, sem Seguir a Imagem não rola (com zoom de 4×), o clique no branco não
  escolhe, o último glifo de uma linha visual quebrada se acha, a Linha pela geometria,
  Ctrl+F5, o zoom do corpo, Ctrl+Shift+H; [livro_real] a x-height na Linha.
- [desempenho] o clique numa palavra do Documento (CA-6.1, `QTest.mouseClick`).

## Rodada 1 (código)

| Revisor | Notas | Veredito |
|---|---|---|
| Código e testes | Correção 6 · Simplicidade 8 · Testes 7 | volta |

| Achado | Correção |
|---|---|
| **1** Cada montagem deixava vivo o `QTextDocument` anterior, com as imagens dos diagramas | `deleteLater` do anterior, decidido antes do `setDocument` (que apaga o padrão do Qt) |
| **2** O teste dos formatos não via o vazamento | conta os `QTextDocument` vivos depois de 20 montagens; falha com a versão antiga |
| **3** O cursor do Documento apagava o contorno da palavra em verificação | um item próprio no visor; teste |
| **4** Sem Seguir, a Imagem rolava mesmo assim | o contorno não rola; só o Seguir; teste com zoom de 4× |
| 5–11 | o clique avisa uma vez e o desempenho mede o clique de verdade; o Documento mostra o glifo da Imagem e da fila sempre; a Linha pela geometria sem o mapa; o clique no branco; a seleção mantida; Copiar FEN pelo teclado; pequenas fragilidades |

## Rodada 2 (código)

Correção 9 · Simplicidade 8 · Testes 9 — **aceita**. O defeito menor que ela achou (o último
glifo de uma linha visual quebrada não se achava pelo clique) entrou junto (`b4fd450`), com
teste.

## As medidas

Três baterias, todas com a pasta limpa: a do `f058c02` (antes da revisão de produto,
`…-primeira-rodada-a3*`), a do `34001f8` (depois das correções da revisão, `…-segunda-rodada-a3*`:
mostrou montar o Documento em 52 ms e o atual_mudou mais lento, pelas margens recalculadas a
cada montagem e pela busca linear da Linha) e a final, do `271d582`, depois de corrigir as
duas. Uma quarta, do `276c689`, foi descartada inteira: a correção da chave do cache foi
escrita na worktree com ela rodando.

### Medidas finais (commit `271d582`)

- Portão: 16 passaram; `docs/medidas/2026-10-17-passo-a3.json`.
- 3 rodadas (`repeticao-a3`), na ordem em que rodaram:
  - o clique no Documento: mediana 2,44; 2,48; 2,46 ms e p95 2,72; 2,79; 2,76 (alvo de 50);
  - montar o Documento: mediana 31,1; 31,1; 31,1 e p95 32,1; 31,9; 32,7 (A2, o texto puro: ~22);
  - Enter até a cor: mediana 30,0; 21,3; 21,2 e p95 37,0; 22,9; 22,9 (a primeira rodada
    deslocada por igual; o portão, 21,1 e 22,4);
  - Enter com uma propagação lenta: p95 35,8; 22,6; 35,2;
  - Enter até o fim da propagação: mediana 89,3; 80,8; 80,7 (A2: 71,8–72,6);
  - troca no cache: mediana 14,3; 14,1; 14,1; fora do cache: 128,4; 129,4; 128,2;
  - releitura: mediana 14,1; 14,6; 14,4;
  - memória com o lote: 1807; 1807; 1806 MB (portão 1823; A2: 1781–1783);
  - atraso no lote: p99 21,0; 9,4; 9,7.
- Qualidade (`medir.py`, os três livros, no `271d582`) e fatia (`--passo A3`, no `b8ebe2a`,
  que só acrescenta os JSON): iguais às do A2. O CA-F.1 continua "gestos pendentes".

## Revisão de produto, rodada 1

| Revisor | Notas | Veredito |
|---|---|---|
| Produto, design e medição | Completude 7 · Fidelidade das medidas 6 · Clareza 8 · Produtividade 7 · Design 8 | volta |

| Achado | Correção |
|---|---|
| **M1** O CA-F.1 pendente, contra o prazo do roadmap (o gabarito verificado antes do fechamento do A3); e o replay não ganha nada com o A3 | levado ao usuário: **roadmap 0.8**, com o sim dele: o prazo passa ao D1, e o alvo de ≤ 85% depois do A3 sai |
| **M2** A formatação por função e o Ctrl+Shift+H não faziam nada numa página real (nenhuma área tem função até o F) | o cabeçalho e o rodapé corridos pela regra da exportação (`gids_de_margem`) saem em cinza, e o Ctrl+Shift+H os oculta; o README diz que título e nota são do F |
| **M3** O glifo atual da fila não ficava marcado no Documento sem o foco nele | `marcar_atual`: fundo próprio (extraSelection), refeito a cada montagem; teste |
| **M4** As rodadas descritas fora de ordem, e a do A2 chamada de deslocamento | a ordem pela hora dos arquivos; a do A2 é uma cauda (acima) |
| **M5** O Enter até o fim da propagação e a memória com o lote subiram sem dizer | ditos no README e aqui, com as causas prováveis; o que vinha do A3 mesmo (as margens recalculadas, a busca linear da Linha) foi corrigido antes da medida final |
| m1–m9 | as capturas com a página endireitada; o contorno velho sai quando a fila anda; o Documento vai junto com a fila (README); o corpo 10 abaixo de 1600 px; o CR no README; só o estado do diagrama no Documento; a página não reconhecida diz isso; o rótulo curto "Página inteira"; a nota na SPEC §6.1 |

## Rodadas 3 e 4 (código, sobre as correções do produto)

Rodada 3: Correção 8 · Simplicidade 8 · Testes 8 — **aceita**, com quatro menores, que
entraram (`320cdc3`): o bloco só de margem não deixa parágrafo vazio; a linha de margem com
□ ou virtual continua margem; a Linha do clique é a do glifo clicado; "Nada reconhecido
nesta página." para a página reconhecida e vazia; e `linha_de_texto(com_ressalva=False)` no
lugar do `replace` de string.

Rodada 4 (sobre a otimização do `276c689`): Correção 7 · Simplicidade 8 · Testes 8 — volta:
a chave do cache das margens só olhava os gids, e corrigir o número da página ("l2" → "12")
deixava a margem velha. A chave passou a ter o texto, a posição de cada glifo lido e a altura
da página (`271d582`), com o teste de invalidação (que falha com a chave antiga) e o de
"Nada reconhecido".
