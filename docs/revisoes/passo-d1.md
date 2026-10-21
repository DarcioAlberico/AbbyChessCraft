# Passo D1 — Edição e notação (§6.3, linhas D1; §6.4)

Ramo `passo-d1-edicao`, a partir da tag `passo-e` (f2ddfae).

## O que o passo fez

- **A sessão de edição sem Qt** (`abbychess/sessao.py`): o texto de agora alinhado contra o
  original (Levenshtein; no empate, a substituição, e as lacunas à esquerda; a troca de
  letra por espaço custa 2), passando pelos caracteres que nenhuma edição tocou (os `fixos`
  da vista); sem fixos e com texto grande, ancorado nas palavras iguais e com um vão grande
  alinhado numa faixa. O plano: cada glifo fica (com a letra nova) ou sai; as letras novas
  viram glifos virtuais; as fronteiras viram quebras e junções entre os boxes. O que é do
  passo G recusa a sessão inteira: k glifos por 1 letra, 1 por k, a letra no meio de uma
  ligadura, apagar o hífen de fim de linha.
- **Onde os virtuais ficam** (`abbychess/ancoragem.py`): cada virtual logo depois (ou logo
  antes) da âncora dele, um box ou outro virtual (`texto._aplicar_decisoes`, com uma pilha);
  a sessão os ancora de novo como o usuário os deixou, antes de sair qualquer box; a
  palavra só de virtuais se apoia na vizinha da mesma linha (na página montada, sem fechar
  ciclo); e as palavras que a montagem do core parte ou junta quando um box sai voltam ao
  que o usuário digitou (e as de fora da sessão, ao que eram).
- **O Documento editável** (`app/documento.py`, `app/edicao_na_janela.py`): a sessão (em
  amarelo-claro) cresce com as edições; confirma ao sair dela, com Enter (e vai à próxima
  duvidosa), Shift+Enter ou Ctrl+Enter (e ensina, no mesmo passo do desfazer); Esc restaura
  e Ctrl+Y reaplica (as ações do menu Editar valem na sessão); Enter numa palavra sem mudança
  a aceita (os glifos com leitura ficam `revisado`); sair da página confirma antes, na
  página dela; o cursor volta onde estava. O colar entra só como texto. Os avisos (o
  estrutural no formato do §6.3, a recusa, a tinta sem box, a última duvidosa) vão à Linha e
  à barra de status.
- **As figurinas** (§6.4): no lance que o usuário mudou, a letra da peça vira figurina no
  modo do livro (figurinas, letras ou, o padrão, como o livro: pelo resumo das páginas no
  `livro.json`); Ctrl+Shift+K/Q/R/B/N/P no Documento e no campo do Glifo (repetir alterna a
  cor); F2.
- **O Ctrl+M ao lado de uma letra virtual** sugere a letra dela no campo do Glifo; o virtual
  sai só quando o usuário confirma o box com ela.
- **A máquina de estados do CA-4.3** ganhou `editar_palavra` (trocar, apagar, inserir antes,
  depois e no começo, espaço, trocar e partir, palavra nova, juntar) e os invariantes: o
  texto da página é o digitado; um box só sai se a letra dele foi apagada; a âncora de todo
  virtual está na página, sem ciclo.
- **Do E**: a volta de cada página do lote saiu da janela (o `lote.json` numa thread, a
  página seguinte num passo à parte do laço de eventos); o servidor fecha as filas do filho
  que caiu (o pytest ficava preso na saída).

## Decisões

| Decisão | Por quê |
|---|---|
| A âncora do virtual é o lugar exato (sem a regra antiga "o segundo depois do mesmo glifo vem depois do primeiro") | a sessão insere em qualquer posição; a regra contradizia o que foi digitado |
| Os virtuais da sessão são ancorados de novo a cada confirmação | a âncora que sai, a palavra partida ou juntada e o virtual no começo da palavra não precisam de caso especial |
| Uma linha que perde todos os boxes some, e o virtual que sobrou vai para a vizinha (a Linha avisa) | as linhas vêm dos boxes (o core); juntar linhas é do passo G |
| O □ e o aguardando não viram `revisado` com o Enter | sairiam da fila para sempre, e a §4.6 os protegeria da releitura |
| O Ctrl+M não grava a letra do virtual sozinho | a vírgula marcada ao lado de uma letra que faltava viraria essa letra, manual, em silêncio |
| "e8=D" não vira "e8=♕" | o §6.4 fala da letra de peça seguida de casa (o teste de antes fixa isso) |
| A máquina da suíte rápida roda 120 exemplos (a noturna, 5.000) | a suíte rápida tem de caber em 60 s |

## Revisões

| Rodada | Revisor | Notas | Veredito |
|---|---|---|---|
| Código 1 | código e testes | Correção 4 · Simplicidade 7 · Testes 5 | volta |
| Código 2 | código e testes | 7 · 7 · 7 | volta |
| Código 3 | código e testes | 8 · 8 · 8 | aceita |
| Produto 1 | produto, design e medição | Completude 6 · Fidelidade das medidas 7 · Clareza 6 · Produtividade 5 · Design 7 | volta |
| Código 4 | código e testes | 7 · 8 · 8 | volta |
| Produto 2 | produto, design e medição | 7 · 7 · 8 · 8 · 8 | volta |
| Código 5 | código e testes | 8 · 8 · 8 | aceita |
| Produto 3 | produto, design e medição | 8 · 7 (só o relato das medidas) · 8 · 8 · 8 | volta só pelo M5 |
| Produto 4 | produto, design e medição | 8 · 8 · 8 · 8 · 8 | aceita |

**Código 1** (12 cenários de borda, 7 errados): o virtual cuja âncora sai ia ao começo da
página; o 2º virtual na mesma âncora saía na ordem errada; a letra antes de um virtual no
começo da palavra levantava ValueError sem rollback; o confirmar agendado aceitava outra
palavra; o Enter revisava o □; e os médios e menores (o Ctrl+Y velho, as letras repetidas, o
espaço junto do virtual, a vista velha na fila, os invariantes, o colar, as figurinas com
pontuação, o `lote.json` ao fechar). **Código 2**: trocar uma letra encostada num espaço
digitado descartava o box (o custo da troca letra/espaço); a máquina não o pegaria; a edição
que não roda deixava a vista velha; a colocação dos virtuais foi para um módulo próprio.
**Código 3**: aceita; a colocação com pilha e a passada só nas linhas da sessão.

**Produto 1**: M1 Ctrl+Z e Ctrl+Y da sessão com a pilha vazia; M2 o cursor voltava à palavra
editada; M3 trocar de página perdia a sessão; M4 o hífen de fim de linha; M5 o relato das
medidas; e os menores (o formato do aviso e a barra de status, o Enter na última duvidosa, o
Ctrl+M, a palavra aceita fora do léxico, o modo das peças, o menu Editar e a sessão visível,
o colar da página inteira, o README, as figurinas no Glifo). **Código 4**: o Ctrl+M gravava a
letra do virtual no box errado; fechar com a fila ocupada; a página que saiu da memória; o
Ctrl+T com a sessão na fila; o cursor deslocado pela montagem. **Produto 2**: M6 apagar só o
hífen; o modo pelo livro; o colar com toda palavra mudada. **Código 5**: aceita; o contador
da fila ao trocar de projeto, as sessões da fila ao fechar, o `agora` pelo sinal, a faixa sem
a matriz inteira. **Produto 3**: a primeira confirmação no modo "como o livro" lia todas as
páginas (agora o resumo do `livro.json`). **Produto 4**: aceita (as tabelas idênticas ao gerador, os
números do relato conferidos com os JSON); os menores (uma frase que exagerava o p95 do
Enter, o atraso com o leitor falso, duas limitações levadas ao README, o nome da fatia da
primeira bateria) entraram no fechamento, fora do caminho medido.

## Verificação

- Suíte rápida: 822 testes em 56–60 s; ruff limpo; camada `processo`: 25; a máquina de
  estados com 5.000 exemplos (a noturna) passa.
- `tests/test_sessao.py`, `tests/test_ancoragem.py`, `tests/test_documento_edicao.py`, os
  testes do controlador (a sessão na fila, sair da página, o Ctrl+T, fechar, o modo do livro,
  a letra que faltava) e `tests/test_modelo_estados.py`.
- CA-6.2, CA-6.3, CA-6.7, CA-6.8 e CA-6.9; CA-6.4 nas linhas D1, por teclas, colar e IME (a
  composição com preedit incluída), cada uma desfeita com um Ctrl+Z; CA-4.3 completo.

## As medidas (commit `c955dff`, pasta limpa)

O portão (`ABBY_PORTAO=1`, 20 testes), 3 rodadas `repeticao-d1`, `medir.py` nos três livros e
a fatia. A troca, a releitura, o lote e a memória iguais aos do E; o Enter com a mesma
mediana e o p95 ~3 ms acima; montar o Documento com o p95 ~8 ms acima (a vista guarda a
unidade de cada caractere); o pico durante o lote de 132–137 para 92–105 ms. A qualidade e a
fatia iguais às do E. Detalhe no README ("A edição no Documento, desde o passo D1"). A
primeira bateria (`dd38d99`, antes das revisões de produto) está em
`docs/medidas/2026-10-17-primeira-rodada-d1*.json`.

**Fechamento.** As duas revisões aceitaram: código na rodada 5, produto na rodada 4.

## CA-F.1

**Não julgado** (bloqueado: o texto e os FEN das p. 21–27 do Xadrez Vitorioso não foram
verificados pelo usuário; a fatia segue "gestos pendentes"). Pela versão 0.8 do roadmap, o
prazo dessa verificação é o fechamento do D1; a escolha entre esperá-la para a tag ou adiar
o prazo no roadmap é do usuário.

## Limitações conhecidas

- O que é do passo G (juntar e dividir glifos, o parágrafo, os estilos, juntar linhas) é
  recusado com aviso.
- O Ctrl+T com uma sessão na fila recusa e pede para tentar de novo (não espera sozinho).
- Uma página gravada antes do D1 não tem o campo "figurinas" no resumo e só conta no modo
  "como o livro" quando for gravada de novo; uma figurina lida por engano liga o modo.
- A suíte rápida está perto do limite de 60 s.
