# Passo B — Localizar (§7.1, §7.3)

Ramo `passo-b-busca`, a partir do D1 aceito (`a9428bf`; a tag `passo-d1` espera o CA-F.1).

## O que o passo fez

- **O índice da busca** (`abbychess/busca.py`): uma `PaginaIndexada` por página reconhecida,
  com o texto do Documento (`sessao.texto_e_unidades`), o gid de cada caractere, a etiqueta
  de cada palavra (prosa, notação, legenda, cabeçalho e rodapé, FEN) e os glifos; o FEN dos
  diagramas lidos numa linha própria. Montado ao abrir o projeto, em segundo plano, em 6
  processos (`spawn`) que o programa abre ao começar (`PoolDoIndice`, contados por uso,
  fechados quando o índice fica pronto ou depois de 5 min sem projeto); não vai para o
  disco. O cabeçalho e o rodapé saem de uma regra simples das linhas.
- **A busca**: o pacote `regex` com `concurrent=True` (a janela responde), MULTILINE, o
  tempo-limite de 0,5 s por casamento (um `search` em laço: o GIL e o Python entre os
  casamentos não contam) e a busca inteira abortada com `PadraoLento`; Aa, palavra inteira,
  regex; as classes `\L`, `\P`, `\C` e `\V` pelo idioma do livro, dentro de `(?-i:...)` e com
  fronteiras (a casa depois da desambiguação vale: Nbd7, Rae1, R1e2); figurina = letra
  quando a letra vem seguida de casa; os escopos livro, página, seleção (por gids, congelada)
  e intervalo; o filtro Onde.
- **O controlador** (`ControladorDaBusca`): a busca numa thread, com geração e número; antes
  de cada busca, refaz as páginas editadas (a versão no histórico), as relidas pelo F5 e
  pelo lote (`pagina_reconhecida`, `pagina_do_lote`) e as reconhecidas depois; tira as que
  deixaram de ser reconhecidas; cada leitura tem um número, e a mais nova vence no índice; o
  livro v1 é lido sem migrar (`projeto.ler_sem_migrar`, sob a trava do livro); os resultados
  voltam pela fila da interface. A busca por glifo, também numa thread.
- **A janela**: a barra (`app/barra_de_busca.py`, duas linhas, cabe em 1366×768) no topo da
  vista direita; Ctrl+F (volta à aba Documento; a seleção vira o texto ou o escopo Seleção,
  que diz a página e cai ao trocar de página), F3/Shift+F3 e Enter/Shift+Enter (dando a
  volta no livro, esperando a busca nova), Alt+Enter para Resultados (com o casamento em
  negrito) e a coluna Ach. na gaveta; os destaques no Documento (amarelo, a atual em
  laranja) e na Imagem; a edição com a barra aberta refaz a contagem e mantém a ocorrência;
  Editar › Buscar glifo…; os Avisos que citam uma página a abrem.
- **As medidas**: o CA-7.1 (o índice com os processos abertos e por abrir, e pela janela com o
  servidor), a busca, o atraso durante a busca e durante o aborto; o CA-11.1, com o leitor
  falso e o real, agora com uma busca a cada 2 s durante o lote.

## Decisões

| Decisão | Por quê |
|---|---|
| O índice em processos abertos com o programa, fechados depois do índice | montar 230 páginas leva ~5,5 s num processo; abrir os processos custa ~0,75 s; parados, ocupam ~290 MB |
| O índice só na memória | a busca é rápida (~13 ms) e o índice fica pronto em ~1,5 s; um arquivo a mais teria de acompanhar cada gravação |
| O tempo-limite por casamento, e não pela página inteira | muitos casamentos rápidos (ou outra thread com o GIL) davam um falso "padrão lento" |
| As classes de xadrez fora do "ignorar maiúsculas" | B, o bispo, não é b, a coluna |
| A página relida volta à busca pelo evento do lote, e não por um carimbo no disco | o lote não muda a versão no histórico; um contador de gravação no projeto fica para quando o índice crescer |
| A máquina de estados da suíte rápida roda 100 exemplos (a noturna, 5.000) | a suíte rápida tem de caber em 60 s com os testes do B |
| O portão do índice pela janela na mediana de 3 | a primeira janela de cada série é a mais lenta; o pior caso fica nas limitações |

## Revisões

| Rodada | Revisor | Notas | Veredito |
|---|---|---|---|
| Código 1 | código e testes | Correção 6 · Simplicidade 7 · Testes 6 | volta |
| Produto 1 | produto, design e medição | Completude 6 · Fidelidade das medidas 5 · Clareza 7 · Produtividade 6 · Design 6 | volta |
| Código 2 | código e testes | 7 · 7,5 · 7 | volta |
| Produto 2 | produto, design e medição | 8 · 8 · 8 · 7 · 8 | volta |
| Código 3 | código e testes | 8,5 · 8 · 8,5 | aceita |
| Produto 3 | produto, design e medição | 8 · 8 · 8 · 8 · 8 | aceita |

**Código 1** (12 achados): as páginas relidas pelo lote se perdiam quando a busca era
abandonada; o índice migrava a v1 em segundo plano; o escopo Seleção apontava o trecho
errado depois de refazer a página; uma exceção nas threads deixava a busca pendurada; as
classes seguiam o "ignorar maiúsculas"; o tempo-limite contava o GIL; a página que deixou de
ser reconhecida voltava ao índice; a busca por glifo usava o índice velho; os casos de borda
da expansão e do figurina = letra; detalhes da interface; testes que não testavam o que
diziam; o desempenho do índice. **Produto 1**: M1 Enter logo depois de digitar ia à
ocorrência velha; M2 F3 para outra página não levava o Documento; M3 `\Px\C` achava "bxc5";
M4 Ctrl+F na aba Padrões; M5 a barra e a gaveta em 1366×768; M6 a fidelidade das medidas (o
CA-11.1 sem a busca, o aborto com o tempo-limite real, a conferência do gid); e 12 menores.

**Código 2**: trocar de projeto durante a montagem esvaziava o índice do novo (a montagem
velha fechava o pool da nova); uma busca velha que terminava depois desfazia a página
relida; a busca por glifo travava a janela depois de um lote; e os menores (a corrida da v1,
a seleção congelada, o teste do tempo-limite que não distinguia o conserto, os processos
parados). **Produto 2**: M1 o escopo Seleção ficava preso; M2 `\C` não achava a casa depois
da desambiguação (Nbd7, Rae1); os menores (a gaveta rolando na horizontal, as faixas do
README, a seleção azul cobrindo a ocorrência, o CA-11.1 com o leitor falso sem a busca).

**Código 3**: aceita; os menores (a corrida entre `devolver` e `obter`, `_velhas` fora da
interface, o status da busca por glifo) entraram antes da bateria; a busca de texto e a por
glifo ao mesmo tempo disputam as páginas relidas (passageiro: a busca seguinte acerta); a
atualização do índice está no limite da simplicidade. **Produto 3**: aceita; o portão na
mediana, as faixas do README e a memória dos processos entraram antes da bateria.

## Verificação

- Suíte rápida: 875 testes em ~60 s (60,3 s; o commit da rodada 1 mede 60,4 s na mesma
  máquina e na mesma hora: a máquina está mais lenta que no dia dos 58,5 s); ruff limpo;
  camada `processo`: 28.
- `tests/test_busca.py` (o núcleo, as classes, o controlador, o pool contra a série, a troca
  de projeto com o pool, a busca velha contra a relida), `tests/test_busca_janela.py`, e os
  testes da janela com o servidor (`tests/test_servidor_janela.py`: a busca no CA-11.1, o F3
  atravessando páginas).
- CA-7.1 a CA-7.6 (o CA-7.1 com a limitação abaixo); CA-11.1 com a busca.

## As medidas (commit `c96247f`, pasta limpa)

O portão (`ABBY_PORTAO=1`, 24 testes), 3 rodadas `repeticao-b`, `medir.py` nos três livros e
a fatia, todos passando. A troca, o Enter, a releitura, o lote e o atraso iguais aos do D1
(dentro da variação das rodadas); a qualidade e a fatia iguais. As metas novas: o índice de
230 páginas com p95 de 1,40 s (os processos abertos), a busca com p95 de 17 ms, o atraso
durante a busca e durante o aborto com p99 de 2 ms, o índice pela janela até 2,2 s; o
CA-11.1 com ~84 buscas durante o lote, o atraso no lote com p99 de 2,4–3,1 ms.

**A memória com o lote** subiu de 2.053 para 2.435–2.459 MB (o alvo é 2.560): a interface
termina com ~1.210 MB, contra 822 no D1. Quase tudo é da ordem dos testes: o
`tests/desempenho/test_busca.py` roda antes, no mesmo processo, monta três vezes o índice de
230 páginas e abre a janela com 230 páginas três vezes, e o Python não devolve essa memória
ao sistema. Medido sozinho, o CA-11.1 dá 1.681 MB (a interface com 449 MB). No programa, o
índice de 230 páginas ocupa ~68 MB na interface, e os 6 processos do índice, ~290 MB
enquanto estão abertos (antes de o índice ficar pronto). Detalhe no README ("Localizar
(passo B)").

**Fechamento.** As duas revisões aceitaram na rodada 3.

## CA-7.1, a montagem do índice

Cumprido com os processos já abertos pelo programa: p95 de 1,40 a 1,56 s (n = 10, em quatro
relatos). Na condição do programa, pela janela com o servidor subindo junto, de 1,66 a
2,40 s (a mediana de cada série abaixo de 2 s; a primeira janela de cada série é a mais
lenta). Com os processos por abrir (o projeto aberto logo ao abrir o programa, ou o segundo
projeto da sessão), de 2,0 a 2,9 s, acima do alvo. Fica como limitação conhecida, no README
e aqui; aceitá-la, ou mudar o alvo na SPEC, é decisão do usuário. A busca (p95 de ~13 ms) e
o atraso (p99 de ~2 ms) cumprem com folga.

## Limitações conhecidas

- O índice de 230 páginas cumpre os 2 s só com os processos já abertos (acima).
- Figurina = letra vale no texto literal (com a regex, use `\P`).
- O cabeçalho e o rodapé do índice saem de uma regra simples das linhas, e não da regra
  completa da exportação; a legenda ganha a etiqueta no passo H.
- A busca por glifo mostra uma lista em Resultados até a Galeria do passo C.
- A busca de texto e a por glifo ao mesmo tempo disputam as páginas relidas pelo lote (a
  busca seguinte acerta).
- A suíte rápida está no limite de 60 s.
