# Pedidos ao PyBoxEditor

O AbbyChessCraft usa o core do PyBoxEditor como biblioteca instalada, pela API pública dele
(contrato do roadmap, §18.2 da `docs/SPEC.md`). Onde ainda passa por um nome privado (`_x`),
o acesso está em `EXCECOES` de `tests/test_privados_do_core.py`, com um pedido aqui e um teste
de contrato em `tests/test_contrato_do_core.py` que fixa o comportamento usado (SPEC-qualidade
Q-E7, CA-Q-E7). Quando o core ganhar a API pedida, o programa passa a usá-la, o acesso sai da
lista e o pedido sai daqui.

O AbbyChessCraft não edita o PyBoxEditor: os pedidos são para quem o mantém.

## 1. O ponto de partida e o passo do desfazer do tabuleiro

- **Usa:** `TabuleiroEdicao._historico`, `TabuleiroEdicao._indice` e `TabuleiroEdicao._estado`
  (`abbychess/diagramas.py`, `DiagramaLido.edicao`): o tabuleiro aberto com o que já foi
  conferido (o lado, o roque, as casas) não deve ter o que desfazer antes disso, e o
  construtor guarda o estado da leitura crua. `TabuleiroEdicao._registrar`
  (`diagramas.afirmar_lado`): quem confere afirma o lado que já estava, só a procedência
  muda, e o `definir_lado` não registra nada quando o lado é o mesmo.
- **Pedido:** um `comecar_daqui()` público (o estado de agora como o primeiro do histórico) e
  um `registrar()` público, ou um `definir_lado(lado, origem, sempre=True)` que registre a
  troca de procedência.
- **Contrato:** `tests/test_contrato_do_core.py::test_contrato_do_historico_do_tabuleiro`.

## 2. A tinta do box e o vale mais fundo

- **Usa:** `BoxService._tinta_do_box` e `BoxService._vale_mais_fundo`
  (`abbychess/editar_boxes.py`): o corte sob o pingo do "i" e o corte entre as letras
  digitadas no Documento (a edição 1 → k) acham o vão vertical na tinta do box, pela mesma
  régua do `split_box`.
- **Pedido:** as duas públicas, ou um `split_box(box, cinza, eixo="x")` que corte no vale do
  eixo pedido (a edição 1 → k só precisa disso).
- **Contrato:** `tests/test_contrato_do_core.py::test_contrato_da_tinta_do_box` e
  `::test_contrato_do_vale_mais_fundo`.

## 3. A rede e a base do serviço de aprendizado

- **Usa:** `LearningService._predictor` (depois de `load_predictor()`) e
  `LearningService._get_learner` (`abbychess/leitor.py`): o leitor do livro monta a cadeia
  com a rede global e a base k-NN do PyBoxEditor, e o palpite usa só a rede.
- **Pedido:** uma propriedade `predictor` (None se não carregou) e uma `learner` públicas.
- **Contrato:** `tests/test_contrato_do_core.py::test_contrato_do_servico_de_aprendizado`.

## 4. A leitura de uma lista de palavras

- **Usa:** `lexico._ler` (`abbychess/verificacao.py`): a lista de nomes do core e as listas
  extras do usuário entram no léxico do livro, com a mesma leitura do core (minúsculas, sem
  linha vazia, o `.gz`, o byte torto trocado).
- **Pedido:** um `lexico.ler(caminho)` público.
- **Contrato:** `tests/test_contrato_do_core.py::test_contrato_da_lista_de_palavras`.

## 5. O que a camada tirou de cada página

- **Falta:** `pdf_nativo.extrair` chama `retirar_mobilia` e descarta o que ela devolve (um
  `Counter` do livro inteiro, sem a página). O relatório da exportação (§12.2, CA-12.5) lista as
  margens tiradas das páginas lidas pelos boxes; nas da camada, só avisa que não as lista.
- **Pedido:** `Extracao.retiradas`, `{página: [linhas tiradas]}`.
