# Passo Q5 — tirar antes de pôr (2026-10-31, ramo `qualidade-q5`)

Sexto passo de `plans/roadmap-qualidade.md`, empilhado no `qualidade-q4` (`0f29bca`, ainda
não mesclado), na worktree irmã `C:\Python-Chess2\AbbyChessCraft-qualidade`. A decisão §13.2
da spec foi do usuário: uma função para as faixas de páginas, o separador por parâmetro.

## O que foi feito

### Código morto (CA-Q-Z1), um commit por item

| Commit | Saiu | Conferido por |
|---|---|---|
| `0f964bd` | `leitor.FONTE_LIVRO_FRACO` | `git grep`: nenhum uso (o `"livro?"` gravado em projetos antigos continua com nome no painel) |
| `4e63679` | `Documento.ir_ao_fim_do_gid` | `git grep`: nenhum chamador |
| `15613eb` | `PainelDeResultados.mostrar_glifos` | `git grep`: de antes da Galeria, ninguém chama |
| `efd13e5` | `pagina.efeitos_de_impressao` | só os testes; passam a chamar `efeitos_da_pagina` |
| `0836af8` | o `indices_v1` de `sequencia.da_v2` | sempre `()` desde o Q1 (a v1 migra na abertura) |
| `647e4ab` | o `avisar` de `controlador._pode_ler` | a função o ignorava |

Ficaram, com chamador no programa: `projeto._arquivo_da_pagina`, `modelo.n_de`,
`historico.descartar_desfazer`/`descartar_refazer`, `emendou`. Ficaram como a porta que o
teste usa: `salvar_zonas`, `exportar.exportar`, `paragrafos`, `grade.ACEITOS`,
`diagramas.amostras_guardadas`. O alias `editar = tem` de `acoes.py` sai com o
`EstadoDaJanela` (Q-A2, no Q7). `migrar_tudo` já não existia.

### Duplicação (CA-Q-D1): de 16 pares a 1

| Commit | Par | Destino |
|---|---|---|
| `d0526e8` | `trocar_tipo` ↔ `trocar_funcao` | `_trocar_na_area` |
| `b170b0a` | `sessao._linha_original` ↔ `_palavras_originais` | `_contados(unidades, separadores)` |
| `1ea1179` | `controlador.documento` ↔ `texto`; `voltar_visita` ↔ `avancar_visita` | `_pagina_do_documento`, `_andar_na_visita(passo)` |
| `b6dabf7` | `lote._paginas` ↔ `dialogo_paginas.texto_da_selecao` | `sequencia.faixas_de_paginas(posicoes, separador)` (§13.2: "–" de mostrar, "-" do campo) |
| `ed97b12` | `busca._paginas_do_escopo` ↔ `controladores._paginas`; `diagramas.com_ids` ↔ `zonas.com_ids` | `busca.paginas_do_escopo`, `zonas.ids_livres(itens, prefixo)` |
| `1d9e353` | `visor.marcar_palavra*`; as duas `abrir_paleta`; `paginas_na_janela` (mover, apagar, tirar o corte) | `_contornar`, `painel_treino.menu_da_paleta`, `_perguntar_pela_selecao` |
| `7aed956` | os três "rever": `diagramas.mesclar` ↔ `para_caixas`, `padroes.esquecer` ↔ `restaurar`, `edicao.corrigir` ↔ `ajustar` | `_o_de_antes`; `_do_livro` (e `restaurar` de um só saiu: o programa só usa `restaurar_varios`); `corrigir` chama `trocar` |
| `4f8131a` → `ba2f7b9` | a regra | `dryer.py --aceitos ferramentas/pares_aceitos.txt` sai 1 com par novo ou aceito sumido; `qualidade.py` põe as contagens no resumo e falha |

O par que fica, aceito com motivo: `barra_de_busca._botao` ↔ `_acao_simples` (alternar uma
opção e agir uma vez são botões de natureza diferente).

### Q-A3 (`86d6335`)

- O lote rodando: `ControladorDoLivro._trocar_condutor` muda o condutor e o `lote_rodando`
  da página juntos; o `_largar_lote` deixava o flag de pé até a página religar.
- `AVISO_LONGO_MS` no lugar dos 33 "8000" (controlador e janela; a mensagem do commit diz
  32, por erro de conta).
- `TEMPO_DO_PEDIDO` no `servidor_de_leitura`; o lote o importa de lá.
- `Zona.contem_o_centro` no lugar das seis contas do centro (a spec contava três; havia mais
  três em `zonas.py`).
- O modo da fila **fica**: `ordem_da_fila` é a ordem dos glifos, que guarda o último modo de
  glifos enquanto a fila está em palavras ou diagramas; só `ControladorDaFila.definir` a
  escreve. Não é espelho, é outro dado.

## Desvio da spec

O CA-Q-D1 pedia "o teste de arquitetura na rápida". O dryer leva 18 s sobre o `abbychess`
(cada par contra cada par), o que come um quinto do teto de 90 s. A regra ficou na medida
(`qualidade.py`, que já roda o dryer), e a rápida tem o teste do mecanismo sobre um pacote de
brinquedo (par fora da lista, aceito sumido, a contagem no resumo).

## Verificação

- A suíte rápida inteira no `86d6335`, com -n 4 e a máquina livre: 1878 passaram e 3 pularam
  em 74 s.
- `ferramentas/qualidade.py` no `86d6335` (árvore limpa,
  `docs/medidas/qualidade/2026-10-31-qualidade.json`): a rápida (109 s com cobertura) e a
  `processo` (210 s; 35 s no Q4) passam; cobertura 92,0 % (91,9); 281 funções com CRAP ≥ 10
  (285); 1 par do dryer (16), 0 fora da lista, 0 aceitos sumidos.
- Portão `ABBY_PORTAO=1 pytest -m livro_real` no `86d6335`, com os validadores, sozinho na
  máquina: 21 passaram, 1 reprovou (`docs/medidas/2026-10-31-medida-falhou-012802.json`): o
  mesmo índice da busca pela janela (CA-7.1) que reprova na base, mediana 2416 ms e máximo
  2931 ms (no Q4, 2692 ms; a base deu 2548–2894 ms).
- A `processo` levou 210 s com cobertura (35 s no Q4) e passou; não investiguei a diferença
  nesta rodada: fica para a próxima medida conferir se é da máquina.
- O ruff do portão passa.

## Registro

| Ação | Por quê |
|---|---|
| Conferi cada item morto da §11 por `git grep` antes de apagar | a lista da análise tinha itens com chamador (`emendou`, `descartar_desfazer`, `n_de`, `_arquivo_da_pagina`) |
| Perguntei a §13.2 antes de juntar as faixas | o "–" e o "-" podiam ser de propósito; eram (mostrar contra digitar) |
| Rodei os testes de cada área a cada par, e a rápida inteira no fim | um passo pequeno conferido de cada vez; uma carga pesada só no fim |
| Tirei `padroes.restaurar` em vez de juntá-lo | só os testes o chamavam, e `restaurar_varios([a])` faz o mesmo |
| Aceitei o par dos botões em vez de fundi-lo | um parâmetro `alternar` esconderia duas naturezas |
| Pus a regra do dryer na medida, não na rápida | 18 s; registrado como desvio |
| Deixei o modo da fila | os dois valores diferem de propósito |
| Corrigi a recursão que o meu script de troca do centro criou em `contem_o_centro` | o padrão casou a própria definição; vi no `git grep` antes de rodar |
| Medi e rodei o portão com a worktree parada | a regra da casa |
