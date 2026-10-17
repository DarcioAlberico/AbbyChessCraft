# Passo D2 — Substituir (§7.2)

Ramo `passo-d2-substituir`, a partir da tag `passo-b` (7e85860).

## O que o passo fez

- **Os casos** (`abbychess/substituir.py`, sem Qt): os casamentos sobre o índice da página
  (`busca.casamentos`, o laço do `search` com o tempo-limite, agora compartilhado com a
  busca), filtrados pela etiqueta de cada caractere: Prosa (a prosa, as legendas e os
  cabeçalhos), Notação ou Ambos, e o filtro Onde da busca; o FEN nunca. Os casamentos que
  tocam as mesmas palavras viram um caso só (a menor sequência de palavras inteiras), com o
  antes e o depois; o substituto aceita `\1` e `\g<nome>` com a regex (e `validar` recusa um
  grupo que não existe), e vai como está sem ela. Cada caso passa pela sessão de edição
  (`sessao.planejar`): o que é do passo G vem com o motivo, que nomeia o trecho.
- **Aplicar numa página** é uma sessão só, da página inteira, com os caracteres fora dos
  casos fixos: as operações do §6.3, os glifos corrigidos `manual`, nada ensinado nem
  revisado. Cada caso confere que as palavras dele ainda são as mesmas, inteiras.
- **O controlador** (`ControladorDaSubstituicao`): na página aberta, direto (um caso, ou
  todos); fora dela, a prévia numa thread, que lê (sem o cache e sem migrar) só as páginas em
  que o índice da busca, em dia, acha o padrão; cada `Previa` leva a página lida e o carimbo
  do arquivo. Aplicar edita as cópias na thread do executor (com o estado, os lados dos
  diagramas, a mudança do desfazer e o resumo do livro) e, na interface, adota a página lida
  (`projeto.adotar`, se o arquivo não mudou) ou a carrega, confere que é a mesma (glifos,
  decisões, áreas, diagramas, estado) e troca os campos; se mudou, aplica na de agora. Tudo
  numa `Transacao`: um Ctrl+Z volta o livro inteiro.
- **A janela**: Ctrl+H (a linha de substituir na barra de Localizar: o substituto, Prosa |
  Notação | Ambos, Substituir e Todas); Substituir troca a atual e vai à próxima, pulando as
  que já estão como o substituto; Todas no escopo Página ou Seleção aplica direto, e no Livro
  ou num intervalo monta sempre a prévia em Resultados: um modelo com todos os casos, caixas
  de marcar, Espaço na seleção, Enter aplica, Shift+Enter e o duplo clique vão ao caso; a
  prévia velha sai da tela. Os avisos: o que ficou fora do "onde", os sem tradução, as
  páginas que ficaram de fora, os passos do desfazer que saíram.
- **A sessão de edição** calcula o texto de cada gid e os vivos uma vez (a sessão da página
  inteira ficava quadrática: 125 ms por página, agora ~45).

## Decisões

| Decisão | Por quê |
|---|---|
| O que é do passo G fica de fora, também "casa" → "lar" | a tabela do §6.3; alinhar letra a letra daria ao glifo de um "s" a letra "r", `manual`: um rótulo errado e "confiável" (a revisão de produto concordou); as correções de leitura comuns têm tradução |
| Uma sessão da página inteira, com fixos fora dos casos | os casos de uma página não se atrapalham (os gids e as âncoras de um não mudam os de outro) |
| As cópias editadas na thread do executor, trocadas na interface | a interface é o escritor único (§11); editar 230 páginas na interface a prenderia por ~20 s |
| Adotar a página que a prévia leu, pelo carimbo do arquivo | carregar 230 JSON na interface custava ~3,5 s; adotada, a janela fica presa ~0,4 s |
| A prévia é um modelo, sem o limite de 2.000 linhas | Todas no livro tem de aplicar tudo numa transação (CA-7.2) |
| As figurinas não entram sozinhas no texto substituído | o §6.4 é da digitação; o substituto é o que o usuário escreveu |
| O formato do desfazer fica o do 2b | a transação de 230 páginas e 28 mil casos estima 43 MB; o aviso diz quantos passos saíram (limitação abaixo) |

## Revisões

| Rodada | Revisor | Notas | Veredito |
|---|---|---|---|
| Código 1 | código e testes | Correção 6 · Simplicidade 7 · Testes 6,5 | volta |
| Produto 1 | produto, design e medição | Completude 7 · Fidelidade das medidas 6 · Clareza 7 · Produtividade 6 · Design 7 | volta |
| Código 2 | código e testes | 8 · 8 · 8,5 | aceita |
| Produto 2 | produto, design e medição | 8 · 8 · 8 · 8 · 8 | aceita |

**Código 1**: o mesmo caso aplicado duas vezes (a prévia velha depois de Todas na página:
"casass"); Todas no livro aplicava só os 2.000 casos mostrados (um segundo Aplicar, outra
transação); as áreas, os diagramas e o estado mudados depois da prévia sumiam ao aplicar; a
prévia relia o livro inteiro; as leituras num `_lidas` compartilhado; testes que faltavam.
**Produto 1**: M1 o duplo clique no caso não ia a ele; M2 o limite de 2.000 (o CA-7.2 não
passava pela janela); M3 "Cf3" → "Nf3" com Prosa dizia só "Nada a substituir"; M4 o desfazer
de uma troca no livro inteiro, não medido nem dito; e os menores (o progresso das cópias,
Substituir um a um terminando em erro, a dica genérica, desmarcar em bloco, a regra no
README, a prévia lenta).

**Código 2**: aceita; os menores entraram antes da bateria: a prévia trata como fora de dia as
páginas que uma busca em voo está refazendo; Substituir avisa a ocorrência que está no outro
"onde" (e só pula a que já está como o substituto). Ficam: os três caminhos do `_trocar`, no
limite da simplicidade. **Produto 2**: aceita; o menor entrou antes da bateria: Substituir um
a um pula também, sem ir até ela, a ocorrência de outra página que já está como o
substituto.

## Verificação

- Suíte rápida: 909 testes em ~63–65 s nesta máquina (ver abaixo); ruff limpo; camada
  `processo`: 28.
- `tests/test_substituir.py` (o núcleo, o controlador, a prévia velha, as áreas, o carimbo, o
  padrão lento, o "onde", o índice, a busca em voo, o desfazer cheio),
  `tests/test_substituir_janela.py` (Ctrl+H, Substituir e a próxima, a prévia com Espaço e
  Enter, 2.250 casos e um Ctrl+Z, ir ao caso, pular o já trocado, a prévia velha) e
  `tests/desempenho/test_substituir.py`.
- CA-7.2: 230 páginas, 28.693 casos, uma transação, um Ctrl+Z volta tudo (glifos, decisões,
  estado, áreas, lados) e o Ctrl+Y refaz. CA-7.5: a prévia antes de aplicar fora da página;
  Prosa e Notação separadas; o FEN nunca; nada ensinado.

## As medidas (commit `6a6564a`, pasta limpa)

O portão (`ABBY_PORTAO=1`, 25 testes), 3 rodadas `repeticao-d2`, `medir.py` nos três livros e
a fatia, todos passando. A qualidade e a fatia iguais às do B. As metas novas: substituir "e"
por "E" nas 230 páginas (28.693 casos) prende a janela por 371 ms, o Ctrl+Z leva 563 ms e a
transação ocupa 43,4 MB do desfazer (o limite é 50); a prévia e as cópias, ~9 s cada, em
segundo plano.

**O Enter e a releitura** saíram mais altos nas rodadas repetidas (o p50 do Enter de ~24 para
35–47 ms; a releitura de ~41 para 42–46 ms). O D2 não muda esse caminho; medidos lado a lado
logo depois da bateria, no mesmo processo e na mesma máquina, o B (tag `passo-b`) e o D2 dão
o mesmo: o Enter com p50 de 25,1 e 26,9 ms (B) contra 25,5 e 26,4 ms (D2), e a releitura com
p50 de 42,1 e 45,8 ms (B) contra 42,2 e 43,6 ms (D2). A diferença é da máquina nesta tarde
(a suíte rápida também oscilou de 61 a 71 s no mesmo código).

**Fechamento.** As duas revisões aceitaram na rodada 2.

## A suíte rápida

O contrato pede menos de 60 s. Nesta máquina, hoje, o commit do B (7e85860) mede ~60–62 s e
o D2, 63–65 s: os testes do D2 somam ~4 s (um deles, 0,8 s, aplica 2.250 casos pela janela).
Reduzir os exemplos da máquina de estados de 100 para 60 não mudou o total além da variação
entre rodadas (61–71 s), e foi desfeito. Fica para o usuário decidir entre rever o
orçamento de 60 s ou mover testes para outra camada.

## Limitações conhecidas

- O que é do passo G fica de fora (desabilitado na prévia): o caso comum é "rn" → "m".
- Uma troca no livro inteiro pode ocupar quase todo o desfazer (~43 MB em 230 páginas e 28 mil
  casos); a partir de ~270 páginas com uma troca tão comum, ela fica sozinha no desfazer (a
  barra de status diz quantos passos saíram).
- A prévia lê as páginas candidatas uma a uma (~40 ms cada): ~9 s quando o padrão casa nas 230
  páginas; as cópias, outros ~9 s, com a fila de comandos esperando.
- As figurinas não entram sozinhas no texto substituído.
- A suíte rápida passa de 60 s nesta máquina (acima).
