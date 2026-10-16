# Passo A1 — Visor novo (§3.3, §13)

Ramo `passo-a1-visor`, a partir da tag `passo-2b` (a188083).

## O que o passo fez

- **Um item só para os boxes** (`abbychess/app/item_dos_boxes.py`, CA-3.4): `ItemDosBoxes`
  guarda as caixas numa grade de células de 64 px (`abbychess/grade.py`, sem Qt), pinta só
  os boxes do retângulo exposto (alargado pelo alcance do traço, para não cortar o do
  vizinho) e, ao mudar um box, pede a repintura só do retângulo dele, com folga de até 20%
  do lado. O clique acha o box pela grade (o menor que contém o ponto).
- **Os estados e os tokens** (`abbychess/app/estilo.py`, §13): pendente, sem leitura,
  aguardando leitura e os três aceitos (manual, livro, rede), cada um com cor da paleta
  Okabe-Ito e traço próprios. Os aceitos ficam discretos (preto a 25%, 1 px); **V** mostra a
  origem. A legenda do painel de treino é gerada da mesma tabela e desenhada com o traço.
- **Zoom** de 5% a 800%: Ctrl+roda, Ctrl++/−, Ctrl+0 (página), Ctrl+9 (largura, que guarda
  a posição vertical ao redimensionar), Ctrl+8 (100%), Ctrl+7 (o glifo atual); a barra diz
  "zoom máximo"/"zoom mínimo" (CA-3.6); a caixa de zoom tem `ClickFocus` e o Enter devolve
  o foco ao visor.
- **Rolar e arrastar**: Shift+roda horizontal; espaço+arrastar e o botão do meio arrastam
  sem marcar; o foco que sai solta o espaço. PgDn/PgUp rolam uma tela e viram a página no
  fim/topo.
- **Navegação** (CA-3.8): Ctrl+G vai para a página; Alt+Home/End; Alt+←/→ pelas visitas
  (navegar no meio corta o que vinha adiante); Seguir (Ctrl+Shift+L); F8, o próximo
  diagrama do livro por conferir (antes era o Ctrl+G).
- **Cache e pré-carga** (`CacheDePaginas`): as 5 últimas páginas renderizadas, e a seguinte
  pré-carregada noutra thread; a mesma página pedida por duas threads é renderizada uma vez.
  A fonte renderiza uma página por vez (trava). A janela guarda os 5 últimos pixmaps e
  converte o da vizinha 400 ms depois de trocar.

## Decisões

| Decisão | Por quê |
|---|---|
| Uma grade de células fixa, não uma árvore | os boxes de uma página são pequenos e de tamanho parecido; a grade dá o clique em ~0,002 ms e é trivial de atualizar num Alt+seta |
| Os aceitos discretos por padrão | o que chama o olho é o que falta revisar (§13); a origem fica a um V |
| O traço não carrega o sentido só pela cor | daltonismo; cada estado tem estilo de linha e largura próprios |
| A pré-carga só da página seguinte | o caso comum é ler em ordem; a anterior fica no cache de 5 |
| A caixa de zoom devolve o foco no `returnPressed`, não no `editingFinished` | o `editingFinished` vem também quando a caixa perde o foco, e roubaria o clique dado noutro campo |

## Verificação

- Suíte rápida (597 passaram, 56 s), ruff limpo.
- CA-3.4: `test_visor.py` (a cena tem um item de boxes; o `update` interceptado fica ≤ 2× a
  caixa).
- CA-3.5 [desempenho]: `tests/desempenho/test_visor.py`, com os alvos estritos (33 e 2 ms),
  metade dos cliques no meio de um box.
- CA-3.6: os limites do zoom e a mensagem.
- CA-3.8: PgDn no fim abre a seguinte no topo, PgUp no topo a anterior no fim (também com a
  página inteira na vista); Alt+← depois de Ctrl+G 50; Alt+Home/End; Seguir a ≥ 120 px da
  borda, e desligado não move a vista.
- Mais: duas threads pedindo a mesma página (forçada, determinística), o traço do box logo
  fora do exposto (conferido contra a versão sem o alcance), o foco da caixa de zoom, o
  espaço solto quando o foco sai, o arraste no modo de treino não marca, F8 sem diagrama e na
  própria página, o corte das visitas, a troca do cache ao abrir outro projeto, o pixmap
  guardado só vale para a mesma imagem.

## Rodada 1 (código)

| Revisor | Notas | Veredito |
|---|---|---|
| Código e testes | Correção 7 · Simplicidade 8 · Testes 7 | volta |

| Achado | Correção |
|---|---|
| **M1** A legenda do painel ainda vinha das cores antigas (`cores.LEGENDA`), sem o traço; código morto em `cores.py` | a legenda vem de `estilo.LEGENDA`, com a amostra do traço; `LIVRO`, `LEGENDA` e `cor_do_box` saíram |
| **M2** A pré-carga e o clique podiam renderizar a mesma página duas vezes | `_em_curso` com um `Event` por índice: quem chega depois espera |
| **M3** O espaço ficava preso se o foco saísse com ele apertado | `focusOutEvent` solta o espaço e o panorama |
| **M4** O `paint` cortava o traço de um box logo fora do retângulo exposto | a consulta alarga pelo alcance do traço em pixels da tela |
| menores 1, 2, 4, 6–10 | o pedido de pré-carga perdido; a inclinação sob a trava; a posição vertical no modo largura; as visitas só andam se a página abriu; código morto; `atualizar` com só os índices mudados; os pixmaps esvaziados na troca de projeto; o foco devolvido pela caixa de zoom |
| testes pedidos | os da lista acima; o CA-3.5 sem a folga de 20% |

## Rodada 2 (código)

Correção 7 · Simplicidade 9 · Testes 7 — volta: a caixa de zoom devolvia o foco também ao
perder o foco (`editingFinished`), o que poderia roubar o clique noutro campo (não se
reproduziu no offscreen, nem com a versão antiga; a troca para `returnPressed` fica pelo
gatilho certo); o teste das duas threads não forçava a corrida; o M4 não tinha teste; a
legenda tinha perdido o diagrama e a seleção. Tudo corrigido no `21dda8f`.

## Rodada 3 (código)

Correção 9 · Simplicidade 9 · Testes 9 — **aceita**.

Adiados, registrados no roadmap: o widget `combobox` do `proximo_da_fila` no
`docs/atalhos.yaml` (a caixa de zoom é `QSpinBox`), para o A2. O menor 3 (o lote e a janela
disputam a trava da fonte) ganhou comentário; o 11 (o Seguir não persiste, e religá-lo só
vale no próximo glifo) está no README; o 5 se resolveu com o `ir_ao_topo` em toda página
mostrada.

## Medidas (commit `4e974a5`, pasta limpa)

- Portão (`ABBY_PORTAO=1 -m "livro_real or desempenho"`): 11 passaram;
  `docs/medidas/2026-10-16-passo-a1.json`.
- Rodadas repetidas: 3 (`repeticao-a1`), sem o A/B do congelamento (roadmap 0.7).
  - Troca de página no cache: mediana 13,9–14,0 ms, p95 14,6–14,8 (alvo de 150 no cache;
    2b, sem cache: 153–158 na mediana).
  - Fora do cache: mediana 213–215 ms, p95 229–239 (alvo de 600; o portão, 244).
  - Pintura de 2.000 boxes (CA-3.5): p95 10,4–13,5 ms (alvo de 33); clique: p95 ~0,002 ms
    (alvo de 2).
  - Enter até a cor mudar: mediana 20,5–30,2 ms, p95 25,6–33,5 (alvo de 100; 2b: 20,6–21,5
    na mediana); uma rodada mais alta, e o portão com p95 de 37.
  - Releitura: mediana 14,0–14,9 ms (2b: 13,3–15,3). Texto da página: 22,2–22,5.
  - Memória do desfazer: 8,0 MB (estimativa). Memória com o lote: 1784–1803 MB (2b: ~1654;
    o cache de páginas e de pixmaps; alvo de 2560).
  - Atraso no lote: p99 10,0–21,7 ms, máximo 95–106 (alvo de 50 no p99).
- Qualidade (`medir.py`, os três livros) e fatia (`replay_fatia.py --passo A1`): iguais às
  do 2b; o lote do xv, 445,5 s (2b: 446,6).
