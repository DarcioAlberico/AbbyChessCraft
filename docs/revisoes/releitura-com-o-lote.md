# CA-11.7: a releitura de um glifo com o lote rodando

Meta da §2: p95 ≤ 150 ms (corte 180). Com o portão de CA-C6 (ramo `c-6`, a mediana dos p95 de 5
rodadas, o lote recomeçado em cada uma), a `main` reprovou em 19/11: 243 a 293 ms, mediana 262.
Não oscilava: estava acima em todas as rodadas.

## Onde o tempo ia

Medido em 20/11 com um perfil à parte (o ambiente de `tests/desempenho/test_servidor.py`, a
fábrica de verdade no filho com o tempo de cada `ler` anotado, e os instantes de cada etapa na
janela), 40 releituras, o lote lendo as páginas 41 a 60:

| Etapa (`main`) | p50 (ms) | p95 (ms) |
|---|---:|---:|
| Do Alt+→ ao pedido ao servidor | 51 | 82 |
| O resto do `ajustar`, na interface | ~22 | ~60 |
| No filho: a fila e a espera do glifo do lote | 13 | 39 |
| No filho: a leitura do glifo | **1** | 2 |
| Do filho à janela | 2 | 29 |
| Na janela: aplicar a leitura e repintar | 35 | 77 |

A leitura custa 1 ms; quase todo o resto é a interface. O `cProfile` da thread da interface
apontou duas coisas:

- **O resumo da página a cada gravação.** `cache.agendar` calculava, na thread da interface, o
  resumo da página (`resumo_das_confiancas`, que julga a página inteira pelo contexto) a cada
  gravação, e o pedido ao servidor só saía depois dela. O julgamento vinha de uma página avulsa
  (`improvaveis_da_lista`), sem as decisões de palavra: a chave dele não era a da página aberta,
  o cache do contexto errava, e as entradas dele empurravam a da página aberta para fora. Eram
  ~6 julgamentos da página por releitura.
- **A página inteira convertida para recortar um glifo.** O pedido (`recortes_para_ler`) e a
  releitura do Alt+seta (`editar_boxes.ajustar`) recebiam a imagem PIL e a convertiam inteira
  para numpy (~7 ms, mais com a máquina carregada), quando a janela já guarda a matriz.

## O que mudou (ramo `releitura-com-o-lote`)

1. `agendar` não calcula o resumo: quem o pede (`resumos_pendentes`: `do_livro`, a régua do
   negrito) o calcula uma vez, e ele fica guardado até a página ser gravada ou mudar de novo.
2. Em `_mudou`, o recorte vai ao servidor antes da gravação: o filho lê enquanto a interface
   grava e repinta.
3. O pedido e o Alt+seta recortam da matriz que a janela já tem (`_cinza()`).

Nenhuma conta muda: o resumo é o mesmo, calculado mais tarde; o recorte é o mesmo, da mesma
página.

## Depois

O mesmo perfil, alternando a `main` e o ramo na mesma hora (duas rodadas de cada):

| | p50 (ms) | p95 (ms) | até o pedido, p50 (ms) |
|---|---:|---:|---:|
| `main` | 138 a 144 | 222 a 228 | 53 a 64 |
| ramo | **23 a 30** | **65 a 83** | **6** |

O portão de CA-C6 (o teste `test_releitura_de_um_glifo_com_o_lote_rodando` do ramo `c-6`, sobre
este ramo): os p95 das 5 rodadas deram 114, 78, 58, 73 e 93 ms, mediana 78. Passa.

## O que fica

- A fila de revisão ainda recalcula os pendentes da página 4 vezes por releitura (nos repintes
  de `glifos_mudaram`), com o julgamento já no cache: não foi preciso mexer.
- O F5 e o dividir (`ed.dividir`) ainda passam a imagem PIL: fora desta meta.
