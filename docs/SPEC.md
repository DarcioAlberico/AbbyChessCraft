# AbbyChessCraft — especificação da aplicação completa

Versão 0.4, 2026-10-15. Revisada nas rodadas 1, 2 e 3 (arquitetura, produto e UX, QA); o
registro está em `docs/revisoes/`. O roadmap que executa esta spec é
`plans/abbychesscraft-roadmap.md`. Fontes: `docs/pesquisa/finereader.md` (o FineReader,
por documentação pública) e `docs/pesquisa/auditoria-2026-10.md` (o programa de hoje).

## 0. Como ler

- **DEVE**, **DEVERIA**, **PODE**: obrigatório, recomendado, opcional.
- Cada recurso traz **critérios de aceite** (`CA-x.y`). Pronto é todo CA passando, com teste
  automatizado onde for automatizável. A camada de teste vem entre colchetes quando não é a
  suíte rápida: [processo], [livro_real], [desempenho] (§15.1).
- **Páginas**: "p. N" é a página **impressa**; o índice do PDF vem explícito quando importa
  (no Xadrez Vitorioso, índice 25 = p. 26).
- **Livro de referência**: Xadrez Vitorioso – Estratégias (Seirawan e Silman), 230 páginas,
  ~250 dpi, só imagem (`C:\Python-Chess2\PyBoxEditor_Tkinter\PDF\Xadrez Vitorioso*\`),
  fixado por `pdf_sha256` no gabarito (§15.2).
- **Tempo** só se mede na camada [desempenho], pelo método de §15.3; as outras camadas só
  verificam correção.
- **Atalhos**: a fonte única é `docs/atalhos.yaml` (§3.4); as tabelas desta spec são extratos.
- O que a spec não decide está em **§18**.

## 1. Visão e princípios

**O AbbyChessCraft é a mesa de trabalho de quem transforma um livro de xadrez digitalizado
em texto, diagramas e partidas corretos.** O FineReader é a referência de fluxo; o que o
AbbyChessCraft acrescenta é o que o FineReader não sabe: figurinas, notação, diagramas em
FEN validados pelos lances, e o treino de padrões por livro no centro do trabalho.

Princípios, em ordem de prioridade:

1. **O tempo de correção manda.** Cada recurso se julga pelos gestos e segundos que tira da
   correção de uma página. As ações comuns cabem em um gesto de apontar mais o teclado e não
   pedem mouse e teclado ao mesmo tempo.
2. **O que o usuário decidiu não se perde.** Correção, conferência, padrão ensinado e decisão
   de layout só saem por ação explícita dele, inclusive quando a página é reconhecida de novo
   (§4.6); toda ação dele se desfaz ou se restaura (§14.2).
3. **A interface nunca trava e nunca ignora em silêncio.** Trabalho longo roda fora da thread
   da interface; o que não pode rodar agora diz por quê e onde está na fila.
4. **Uma verdade só.** O texto é função pura do modelo (§4.2); vista, busca e exportação leem
   o mesmo.
5. **Sala limpa e core como biblioteca.** Nada da ABBYY é descompilado; o PyBoxEditor é
   biblioteca instalada, não é editado daqui, e a base global `training_data` dele nunca é
   gravada.
6. **Medir antes de declarar**, contra gabarito rotulado (§15.2).

## 2. Usuário e metas

Um tipo de usuário: quem corrige um livro inteiro (150–800 páginas) em várias sessões, quase
todo no teclado, conhecendo o FineReader.

Toda meta de tempo é um **alvo**; o **corte** que reprova é alvo × 1,2 (§15.3).

| Meta (p95, §15.3) | Alvo |
|---|---|
| Trocar para página lida no cache | ≤ 150 ms |
| Trocar para página lida fora do cache | ≤ 600 ms |
| Enter (ensinar): box muda de cor | ≤ 100 ms |
| Releitura de um glifo (dividir, ajustar) com o lote rodando | ≤ 150 ms |
| Buscar regex no livro (230 páginas, índice pronto) | ≤ 1 s |
| Montar o índice da busca ao abrir (230 páginas) | ≤ 2 s, em segundo plano |
| Atraso de evento da interface durante o lote | p99 ≤ 50 ms, com as ações funcionando |
| Memória do desfazer (300 páginas × 20 ações) | ≤ 50 MB |
| Memória total com o lote rodando | ≤ 2,5 GB |
| Gestos para levar as p. 21–27 ao gabarito (replay, CA-F.1) | ≤ 70% da linha de base depois do D1 |

O número de hoje de cada meta não fica aqui: ele está no JSON da medida
(`docs/medidas/`) e na tabela que `ferramentas/resumo_medidas.py` gera no README
("A linha de base do roadmap"). Um número digitado num documento envelhece sem aviso
(§15.3).

## 3. O espaço de trabalho

### 3.1 Os painéis

```text
┌ Menu · Barra principal (32 px) ─────────────────────────────────────────────────┐
├gaveta┬───────────────────────┬────────────────────────────┬────────────────────┤
│Págs. │ Imagem                │ [Documento|Galeria|Padrões │ Inspetor do ITEM   │
│ F9   │ a página, boxes,      │  |Diagramas]               │ fila: modo ▸ 12/204│
│Alt+1 │ áreas, diagramas      │ barra Ctrl+F / Ctrl+H      │ um editor só:      │
│      │                       │ texto e diagramas          │ Glifo · Palavra ·  │
│      │                       │ reconhecidos, editáveis    │ Diagrama · Área    │
│      ├───────────────────────┴────────────────────────────┤                    │
│      │ Linha (Ctrl+F5): a linha atual, imagem sobre texto │                    │
├──────┴────────────────────────────────────────────────────┴────────────────────┤
│ Resultados / Avisos (abre por busca, relatório ou ⚠; Esc fecha)                 │
├────────────────────────────────────────────────────────────────────────────────┤
│ p.26/230 ● em revisão · fila: confiança/livro 12/204 · 85% · lote 41/230 ⏱18 min ✕ · ⚠2 │
└────────────────────────────────────────────────────────────────────────────────┘
```

- **Páginas** (gaveta; F9 ou Alt+1): lista com nº, estado (§4.4), pendentes e diagramas por
  conferir, ou miniaturas; Enter ou duplo clique abre; seleção múltipla para reconhecer,
  exportar, aplicar modelo de áreas; filtro por estado. Lê `livro.json`. No topo, o cartão
  **Saúde do livro** (§9.1). **Em projeto novo a gaveta abre e fica aberta até o primeiro
  lote** quando a janela tem ≥ 1600 px de largura; abaixo disso fica fechada, e o cartão
aparece só como estado vazio do Documento (para a Imagem não cair abaixo do CA-3.2).
- **Imagem**: o visor (§3.3).
- **Vista direita** (abas): **Documento** (§6), **Galeria** (§8.2), **Padrões** (§8.3),
  **Diagramas** do livro (§10). Alt+3 repetido cicla as abas. Enquanto a página não foi
  reconhecida, o estado vazio do Documento é o cartão Saúde do livro.
- **Linha** (Ctrl+F5): a linha atual ampliada, imagem em cima e texto embaixo, alinhados por
  glifo (o Zoom do FineReader).
- **Inspetor**: **um** editor, o do item atual: Glifo (o treino de hoje), Palavra
  (verificação), Diagrama (tabuleiro editável e paleta; o recorte impresso é a Imagem, que dá
  zoom no diagrama) ou Área (função, ordem). **Só troca por ação explícita** (clique num item,
  avanço da fila), nunca por foco. No cabeçalho, o seletor da fila (um `QToolButton` com
  menu, não um combo) e o contador; no rodapé, a dica das teclas do editor.
- **Resultados / Avisos**: busca, prévia de substituição, relatório da exportação, e o **log
  persistente** de avisos e erros (nada some com um `showMessage` de 5 s).
- **Barra de status**: página e estado, fila, zoom (caixa com `Qt.ClickFocus`), lote com
  tempo estimado e o **✕ que o cancela**, ocupado com a fila de tarefas, ⚠N.

Imagem e vista direita dividem a área central num `QSplitter` (horizontal ou vertical); os
demais são `QDockWidget`, que podem flutuar (segundo monitor). O arranjo é gravado por
projeto.

**Tamanhos padrão** (larguras incluem as alças de 4 px):

| Resolução | Páginas | Imagem | Vista direita | Inspetor | Linha | Resultados |
|---|---|---|---|---|---|---|
| 1366×768 | gaveta fechada | 556 | 500 | 296 | 80 | fechado |
| 1920×1080 | 150 | 760 | 680 | 320 | 96 | 200 quando aberto |

Abaixo de 1280 px de largura, o arranjo padrão vira **empilhado** (Ctrl+Shift+F7): Imagem
em cima, vista direita embaixo; o Inspetor fica.

**CA-3.1** Reabrir o projeto restaura docas visíveis e áreas, tamanhos do splitter (±2 px),
zoom, painel e aba ativos e página aberta (comparação estrutural).
**CA-3.2** Em 1366×768 no arranjo padrão: soma das larguras padrão ≤ 1366;
`minimumSizeHint().width() ≤ 1366`; no índice 25 do livro de referência, no zoom "largura",
a x-height mediana do gabarito tem ≥ 12 px na Linha e ≥ 6 px na Imagem; a casa do tabuleiro
no Inspetor tem ≥ 32 px (esta cláusula é verificada no passo H). Em 1280×720 o arranjo é o empilhado e os mesmos limites valem.

### 3.2 Arranjos e foco

| Ação | Perfil padrão | Perfil FineReader |
|---|---|---|
| Só Imagem (com Inspetor) | Ctrl+F6 | F6 |
| Lado a lado (padrão) | Ctrl+F7 | F7 |
| Empilhado | Ctrl+Shift+F7 | Shift+F7 |
| Só vista direita | Ctrl+F8 | F8 |
| Páginas | F9 | F5 |
| Linha | Ctrl+F5 | Ctrl+F5 |
| Foco: Páginas, Imagem, vista direita (repetido cicla as abas), Inspetor, Resultados | Alt+1 … Alt+5 | Alt+1 Páginas, Alt+2 Imagem, Alt+3 vista, Alt+4 Linha, Alt+5 Inspetor, Alt+6 Resultados |
| Painel seguinte / anterior | (só Alt+N) | Ctrl+Tab / Ctrl+Shift+Tab |

Shift+F10 e a tecla Menu abrem o menu de contexto em todo painel (convenção do Windows).

**CA-3.3** Cada arranjo produz a visibilidade e orientação de docas da tabela do teste; cada
Alt+N põe `QApplication.focusWidget()` dentro do painel certo (janela ativa, pytest-qt), nos
dois perfis.

### 3.3 Imagem: zoom, rolagem, navegação, desenho

- **Zoom** (no painel com foco):
  - Imagem: Ctrl+roda (ancorado no cursor), Ctrl++ / Ctrl+−, **Ctrl+0 página inteira**,
    **Ctrl+9 largura**, **Ctrl+8 100%**, **Ctrl+7 zoom no item atual**; limites 5%–800%.
  - Documento: Ctrl+roda e Ctrl++ / Ctrl+− mudam o corpo; Ctrl+0 volta ao corpo padrão;
    Ctrl+7/8/9 não fazem nada ali e a barra diz "zoom de página: foco na Imagem (Alt+2)".
  - Nada de Ctrl+Alt+qualquer (é AltGr no ABNT2 e no PT).
- **Rolagem** (Imagem): barras sempre visíveis; roda vertical, Shift+roda horizontal;
  **espaço** ou botão do meio arrastam (só na Imagem); PgUp/PgDn rolam uma tela e passam à
  página vizinha no fim; em "página inteira" e "largura" o zoom segue o redimensionamento.
- **Seguir** (Ctrl+Shift+L): o item atual fica visível nos dois painéis, margem de 120 px.
- **Páginas**: Ctrl+PgUp/PgDn; **Alt+Home / Alt+End** primeira e última (Ctrl+Home/End ficam
  com o cursor do Documento); **Ctrl+G** ir para a página; Alt+← / Alt+→ histórico de visitas.
- **Desenho**: um item só pinta os boxes, com índice espacial em grade, repintando só o
  retângulo que mudou. **Aceitos quase invisíveis** por padrão (contorno de 1 px a 25%);
  destacam-se pendente, sem leitura e "aguardando leitura" (§11). **V** (Imagem) liga
  "mostrar origem". A seleção é contorno duplo.

**CA-3.4** A cena tem exatamente 1 item de boxes; mudar um box chama `update(QRectF)` com
retângulo ≤ 2× a caixa dele (interceptado).
**CA-3.5** [desempenho] Com 2.000 boxes, `paint()` do item numa `QImage` 1920×1080, em 10
zooms de 5% a 800%: p95 ≤ 33 ms; clicar acha o box: p95 ≤ 2 ms em 1.000 cliques de semente
fixa.
**CA-3.6** No limite do zoom a barra diz "zoom máximo"/"zoom mínimo".
**CA-3.8** Cada atalho de navegação tem teste QTest com página e foco esperados: PgDn no fim
da página abre a seguinte no topo; Alt+← depois de Ctrl+G 50 volta à anterior; Alt+Home e
Alt+End; com Seguir, o item atual fica a ≥ 120 px da borda da viewport depois do comando
`proximo_da_fila` (por Alt+↓ a partir do A2).

### 3.4 Teclado

**Fonte única**: `docs/atalhos.yaml` (ação, sequência por perfil, escopo, descrição). O código
registra os atalhos a partir dele; `docs/ATALHOS.md` é gerado dele. Os perfis são
**padrão** e **FineReader**; todo atalho é reatribuível em Opções (passo K).

Regras:
1. Globais (`WindowShortcut`) e de painel (`WidgetWithChildrenShortcut`), com o escopo no
   YAML.
2. **Tab nunca é atalho**; no Documento, `setTabChangesFocus(True)`.
3. **Nenhuma letra sem modificador** como atalho num widget editável; nenhum Ctrl+Alt.
4. **Esc** fecha o que está por cima (busca, menu, seleção, Resultados), nesta ordem. Nunca
   cancela tarefa em segundo plano (isso é o ✕ da barra ou Projeto › Cancelar lote). Numa
   sessão de edição, Esc **restaura** a palavra, e Ctrl+Y reaplica (§6.3): nunca descarta
   trabalho confirmado.
5. **Enter confirma no contexto**: no Glifo e na Galeria, ensina; no Documento, confirma a
   palavra e avança. Ensinar fora do Glifo e da Galeria é **Ctrl+Enter**.
6. Exceção documentada: no campo de 1 caractere do Glifo, Shift+seta e Ctrl+Shift+seta movem
   as bordas e Del descarta o box (`ShortcutOverride` aceito), porque não há texto para
   selecionar nem apagar à direita. (Até o A1 o Del do treino não disparava com o foco no campo, o que o A2 corrigiu:
   achado da tabela de atalhos no passo 0.)

Extrato do perfil padrão, com o que muda em relação a hoje:

| Ação | Hoje | Novo | Escopo |
|---|---|---|---|
| Próximo / anterior da fila | Tab / Shift+Tab | Alt+↓ / Alt+↑ | global |
| Ciclar o modo da fila / alternar escopo página-livro | — | F7 / Shift+F7 | global |
| Próxima página com pendentes | F6 | F6 | global |
| Próximo diagrama por conferir do livro | Ctrl+G (conferir) | F8 | global |
| Página verificada (e abre a próxima não verificada) | — | Ctrl+T | global |
| Marcar glifo à mão (quadro) | Ctrl+T | Ctrl+M | global |
| Ir para a página | — | Ctrl+G | global |
| Reconhecer página / livro | F5 / Ctrl+Shift+F5 | F5 / Ctrl+Shift+F5 | global |
| Reler pendentes | Ctrl+R | Ctrl+R | global |
| Reconhecer a zona escolhida | — | Ctrl+Shift+R | Imagem, modo Áreas |
| Ajustar borda direita / baixo | Alt+seta | Shift+seta | Imagem; campo do Glifo |
| Ajustar borda esquerda / topo | Alt+Shift+seta | Ctrl+Shift+seta | Imagem; campo do Glifo |
| Ignorar palavra | Ctrl+I | Ctrl+Shift+I | Inspetor Palavra |
| Negrito / itálico / sublinhado | — | Ctrl+B / Ctrl+I / Ctrl+U | Documento |
| Confirmar palavra e avançar / sem avançar | — | Enter / Shift+Enter | Documento |
| Novo parágrafo antes da palavra | — | Ctrl+Shift+Enter | Documento |
| Mostrar/ocultar cabeçalhos e rodapés | — | Ctrl+Shift+H | Documento |
| Paleta de símbolos no cursor | — | F2 | Documento, Glifo, Galeria |
| Figurina ♔♕♖♗♘♙ (repetir alterna branca/preta) | — | Ctrl+Shift+K/Q/R/B/N/P | Documento, Galeria |
| Função da zona | — | T texto, H título, C cabeçalho, R rodapé, P nº de página, N nota, L legenda, D diagrama, X ignorar | Imagem, modo Áreas (não editável) |
| Mostrar origem dos boxes | — | V | Imagem |
| Padrões do livro | Ctrl+Shift+P | Alt+3 (ciclando as abas) | global |
| Sair | Ctrl+Q | Ctrl+Q | global |

No perfil FineReader, além de §3.2: Ctrl+F7 fila em modo palavras; **Ctrl+F9** reconhecer
página; **Ctrl+Shift+B** reconhecer a zona (Imagem, modo Áreas; disjunto do ♗ do
Documento); **Alt+PgDn** próxima página com pendentes (sem ligação nativa no `QTextEdit`);
Ctrl+F8 próximo diagrama; **Ctrl+Shift+F7 / Ctrl+Shift+F8** ciclar o modo da fila /
alternar o escopo; Ctrl+1…Ctrl+5 tipo de zona (no padrão, o tipo deriva da função). Ctrl+Tab
global encobre o Ctrl+Tab das abas da vista direita **de propósito** (Alt+3 cicla as abas):
é exceção declarada no YAML.

**CA-3.7** Desde o passo 0, um teste lê `docs/atalhos.yaml` e falha se, em qualquer perfil:
duas ações ativas no mesmo contexto efetivo têm a mesma sequência (global × painel
inclusive); um atalho de painel encobre ligação nativa do widget com foco (Ctrl+Backspace e
Shift+seta no `QLineEdit` fora da exceção 6; Alt+↓ no `QComboBox`; Ctrl+Tab no
`QTabWidget`; Ctrl+Home/End e Ctrl+Shift+seta no `QTextEdit`); uma letra sem modificador vale em widget
editável; aparece Ctrl+Alt; Shift+F10 ou Menu não abrem o menu de contexto. Cada entrada do
YAML tem `desde_passo`; a partir do A2, o mesmo teste monta a janela e confere que os
atalhos registrados são exatamente as entradas com `desde_passo ≤ passo atual`; também a partir do A2, um atalho citado em `SPEC.md` ou `README.md` que não existe no YAML reprova. Gera
`docs/ATALHOS.md` ordenado, com LF. Toda ação do YAML tem sequência em cada perfil, ou
`sem_atalho: true` explícito; exceções de encobrimento (como o Ctrl+Tab do perfil
FineReader) só passam declaradas no YAML com o motivo.

## 4. O modelo de dados (versão 2; a 3, com a sequência do livro, no passo L, §12.4)

### 4.1 Box e identidade

- `Box` é **composição**: `Box(gid, entry: BoxEntry, amostra: str | None, estilo: Estilo,
  revisado: bool)`. O `BoxEntry` é do core e não é estendido.
- **Página tem `pid` estável**, alocado por contador em `projeto.json` e nunca mudado por
  reordenar ou inserir páginas. A partir do passo L, a sequência em `projeto.json` (§12.4)
  dá a posição de cada `pid`, e `livro.json` é chaveado por `pid`.
- `gid = (pid << 20) | n`, com `proximo_n` gravado no JSON da página. Só a interface aloca
  (escritor único, §11). Nunca reaproveitado.
- As funções de edição de `pagina.py` devolvem `Diferenca(removidos: set[gid], novos:
  list[Box], mudados: set[gid], sucessores: {gid_velho: [gids_novos]})`; só a thread da
  interface aplica uma `Diferenca`, e o aplicador **reescreve as decisões** (§4.2) pelos
  sucessores.
- `amostra`: a amostra de padrão que produziu a leitura (procedência, §8.3), preenchida desde
  o passo 1b pelo leitor e pela propagação.
- `revisado`: o usuário viu e aceitou o glifo (palavra confirmada no Documento); tira da fila
  sem trocar a fonte, preservando a procedência e o histograma.
- `estilo`: negrito, itálico, sublinhado (medido por `core.negrito` ou posto pelo usuário).

### 4.2 Zona, decisões e documento

- **Zona** (a área da página, gravada): `Zona(id, tipo, caixa, funcao, ordem, automatica)`,
  `funcao ∈ {texto, titulo, cabecalho, rodape, numero_de_pagina, nota, legenda, diagrama,
  figura, tabela, ignorar}`. O tipo deriva da função (texto ← texto, título, cabeçalho,
  rodapé, nº de página, nota, legenda; diagrama ← diagrama; imagem ← figura; tabela ← tabela;
  ignorar ← ignorar), e escolher um tipo (Ctrl+1…5 no perfil FineReader) dá a função padrão
  dele (texto, diagrama, figura, tabela, ignorar). O layout divide zonas automáticas por
  função; zona do usuário não é dividida.
- **Decisões do usuário**, gravadas e chaveadas por gid: `quebras: set[gid]` (palavra nova
  antes do gid); `juncoes: set[(gid_a, gid_b)]`; `paragrafo_antes: set[gid]`; `virtuais:
  list[GlifoVirtual(gid, char, depois_de: gid | None, palavra_nova: bool, zona_id)]`;
  `hifen_de_quebra: set[gid]`. Pelos sucessores, "antes de g" vira "antes do primeiro
  sucessor" e "depois de g" vira "depois do último".
- **O glifo virtual não tem caixa**: não entra em `boxes`, na altura de referência, no
  clique, na ordem de leitura nem na camada do PDF; nunca ensina.
- **O documento é derivado**: `montar(pagina) -> Documento` é função pura de boxes, zonas,
  decisões e diagramas: `Documento(blocos)`, `Bloco(id, zona_id, funcao, linhas |
  diagrama_id)`, `Linha(palavras)`, `Palavra(gids)`.
- **`texto.py`**: normalização única, modos `impresso` (♘ como impresso; vista, busca, DOCX,
  EPUB) e `san` (N; PGN, validação).
- O `DiagramaLido` ganha `id` estável.

### 4.3 Persistência

- `paginas/p<pid>.json` com `"versao": 2`: boxes (gid, amostra, estilo, revisado), decisões,
  zonas, diagramas, estado, `proximo_n`. A partir do passo L (`"versao": 3`): sem o índice
  da página, e com a `geometria` (quadro e giro) em que os boxes estão (§12.4).
- **Migração** (feita uma vez, ao fim do passo 1b): na primeira abertura v2 de um projeto
  v1, `paginas/`, `zonas/` e `projeto.json` são copiados para `backup-v1/`; o `pid` da página
  v1 é o índice dela; cada página v1 é migrada **e gravada** na primeira leitura.
- `projeto.json`: campo desconhecido vai para `extras` e é regravado; `versao` maior que a do
  programa abre **só para leitura**, com aviso, e nada é gravado.
- Fonte do livro: caminho relativo quando dentro da pasta do projeto; se sumir, a abertura
  procura um arquivo com o mesmo SHA-256 dos primeiros 4 MB e o mesmo tamanho ao lado do
  caminho antigo, na pasta do projeto e na pasta-mãe dele (e avisa onde o achou); se não
  achar, pede para localizá-la e confere o SHA-256 e o tamanho. Em só leitura, a fonte achada
  ou indicada vale só na sessão.
- **Escrita atômica** em todo arquivo do projeto (páginas, `projeto.json`, `livro.json`,
  `inclinacoes.json`, `marcadas` migradas, `lexico.txt`, os metadados de padrões, o
  `saveState`): temporário, `fsync`, `os.replace`, com nova tentativa em `PermissionError`
  (5 × 50 ms); ao abrir, `*.tmp` sobrando são apagados.
- **Gravador assíncrono, escritor único**: a interface entrega um **instantâneo imutável**
  (tuplas e cópias rasas; a partir do 2a, `Box` e `BoxEntry` não são mutados no lugar: a
  `Diferenca` troca os objetos) à thread de gravação, que serializa e grava, com coalescência de
  500 ms; fechar o projeto espera o gravador; em modo só leitura, recusa.
- **`livro.json`** (cache derivado, recriado na migração e sempre que faltar): por página
  (por `pid`, desde o passo L), estado, pendentes, o histograma das confianças (para
  recalcular sem reler quando os limiares mudam) e diagramas por conferir; mesmo gravador.

### 4.4 Estado da página

| Estado | Entra quando | Sai para |
|---|---|---|
| `nao_reconhecida` | página nova | `glifos_marcados` (Ctrl+M) ou `reconhecida` (F5, lote) |
| `glifos_marcados` | quadro marcado antes do F5 | `reconhecida` (mantém os quadros) |
| `reconhecida` | F5 ou lote | `em_revisao` na primeira edição (marcar um glifo também é edição); `verificada` (Ctrl+T, a página que não precisou de correção) |
| `em_revisao` | primeira edição | `verificada` (Ctrl+T) |
| `verificada` | Ctrl+T | `em_revisao` em qualquer edição dela, ou quando um esquecer de padrão devolve glifos dela à fila (com aviso em Avisos) |

Reconhecer de novo uma página `em_revisao` ou `verificada` a deixa `em_revisao`. O lote
**pula páginas verificadas** por padrão.

### 4.5 Critérios do modelo

**CA-4.1** O projeto v1 de fixture (`tests/dados/projeto_v1/`: campo desconhecido, página sem
`tabuleiros`, `marcadas.json`, `inclinacoes.json`) abre, grava e reabre sem perder box,
padrão, zona, diagrama, inclinação nem página marcada (igualdade campo a campo); `backup-v1/`
existe; `versao: 99` abre só para leitura e nenhum arquivo muda (mtime e hash).
**CA-4.2** Para cada arquivo da lista de §4.3, a falha injetada ao escrever o temporário, no
`fsync` e no `os.replace` (`PermissionError` 3 vezes e depois sucesso; e falha permanente)
deixa o antigo inteiro ou o novo inteiro (verificado no 1a, para os arquivos que já
existem). No 2a: a falha permanente emite `falha_de_gravacao` e a página continua suja;
[processo] matar o gravador em 50 pontos aleatórios (semente fixa) não deixa JSON inválido.
No A2: a falha aparece em Avisos, e o `saveState` também é atômico.
**CA-4.3** Máquina de estados `hypothesis` sobre 1–60 boxes numa página de 900×400, que
cresce por passo: 1b `dividir`, `juntar`, `marcar`, `quebrar`, `juntar_palavras`, `virtual`
(invariantes de gid, decisões e `montar()`); 2a mais `pular` e `selecionar`; 2b mais
`desfazer` e `refazer` ("desfazer tudo volta à página inicial"); D1 mais `editar_palavra`. Invariantes, dentre os aplicáveis às regras já presentes, a cada
passo: gids únicos; aposentados ∩ vivos = ∅; pulados e seleção ⊂ vivos (o atual passa ao
primeiro sucessor); **nenhuma decisão referencia gid aposentado**; `montar()` cobre cada gid
vivo uma vez; desfazer tudo volta à página inicial. Suíte rápida `derandomize=True`,
`max_examples=200`; noturno 5.000.
**CA-4.4** 100 mudanças em 400 ms geram 1 gravação; fechar com a página suja grava antes de
voltar; `livro.json` é igual ao recalculado lendo todas as páginas depois de qualquer
sequência de gravações (no passo E, inclusive as vindas do servidor). [processo] Um filho
aplica uma edição a cada 20 ms com carimbo monotônico e é morto em T; ao reabrir, estão todas
as edições com carimbo ≤ T − 500 ms − t_fsync (t_fsync medido e registrado).
**CA-4.5** Copiar `backup-v1/` sobre o projeto reabre pela versão de hoje (fixture), sem
perda.
**CA-4.6** Depois de inserir uma página antes da primeira e reordenar 3 páginas (passo L),
nenhum gid se repete no projeto e cada amostra aponta para o glifo de origem.
**CA-4.7** A fonte movida é relocalizada pelo SHA-256 (arquivo renomeado em teste), e `*.tmp`
sobrando são apagados ao abrir.

### 4.6 Reconhecer de novo sem perder decisões

F5 numa página já reconhecida, e o lote com "refazer": mantém os boxes `manual` e
`revisado` (como o `manter_marcados` de hoje); transfere as decisões para os gids novos por
sobreposição de caixa (IoU ≥ 0,6); lista em Resultados o que não pôde transferir.

- **F5** é uma transação do desfazer (§14.2).
- **Lote com "refazer"** não entra no histórico (seria grande demais): antes de cada página,
  a interface copia o JSON para `paginas/.antes-do-lote/p<pid>.json`, e o menu **Página ›
  Voltar ao estado antes do lote** a restaura.

**CA-4.8** Reconhecer de novo uma página com 10 correções manuais, 2 quebras, 1 virtual e 1
função de zona mantém todas (fixture sintética); um Ctrl+Z volta à página de antes; depois de
um lote com "refazer", "Voltar ao estado antes do lote" devolve o JSON idêntico ao copiado.

## 5. A análise de layout

### 5.1 O que é detectado

Na ordem, cada etapa gravando zonas, funções e decisões:

1. **Endireitar** (existe). Linhas curvas: Editor de imagem (§12.4).
2. **Zonas**: as do usuário; senão, as automáticas (existe), divididas por função.
3. **Diagramas** em zonas `diagrama`, com a **legenda** ligada (a linha curta logo abaixo ou
   acima que começa por "Diagrama", "Teste", número, ou contém "jogam"/"to play").
4. **Colunas**, pelo `core.livro` (pedido de API pública se depender de privado, §18.2);
   ordem de leitura coluna a coluna.
5. **Cabeçalho, rodapé, número de página**: a regra de hoje (`exportar.margens_corridas`)
   vira etapa do layout e aprende por livro (o padrão dos títulos corridos confirmados,
   pares e ímpares).
6. **Títulos e parágrafos**: título por corpo ≥ 1,3× o do texto, ou linha curta isolada e
   centralizada; parágrafo por vão e recuo da primeira linha.
7. **Notas de rodapé**: corpo menor no pé, depois de fio ou vão grande.
8. **Tabelas**: fase posterior (`core.livro`, `core.pagina.Tabela`).

### 5.2 O usuário corrige o layout

- Modo Áreas (Ctrl+Shift+A): cada zona com a cor da função e o número da ordem.
- Função pelas letras de §3.4 ou menu de contexto, sem refazer o OCR.
- **Ordenar** (como o *Order Areas*): clicar as zonas na ordem; Esc cancela a ferramenta.
- **Modelo de áreas**: salvar zonas e funções de uma página e aplicar a pares, ímpares ou
  intervalo; resolução diferente é recusada com aviso.
- Reconhecer só a zona: Ctrl+Shift+R. Toda mudança de layout é transação do desfazer.

**CA-5.1** [livro_real] Contra `tests/verdade/xv/` (índices 20–26): cabeçalho com precisão
= revocação = 1,0; número de página e rodapé com precisão = 1,0; nenhum bloco de texto do
gabarito (IoU ≥ 0,5) sai como `cabecalho`; cada legenda ligada ao diagrama do gabarito
(100%).
**CA-5.2** [livro_real] Na página de duas colunas do Yusupov fixada no gabarito (arquivo por
`pdf_sha256`, lido **só como imagem** a 250 dpi, `usar_texto_nativo=False`): ordem de
leitura com Kendall = 0 e cada linha de FEN no bloco da coluna do diagrama.
**CA-5.3** Mudar a função de uma zona atualiza o Documento sem reconhecer de novo e se
desfaz com um Ctrl+Z; a partir do passo J, a exportação reflete a mudança (verificado no J).
**CA-5.4** O modelo de áreas aplicado às ímpares de um intervalo sintético cria as zonas só
nelas; resolução diferente é recusada.
**CA-5.5** Ordenar 4 zonas sintéticas na ordem inversa muda a ordem do Documento; Esc no meio
deixa a ordem como estava.

## 6. O Documento

### 6.1 O que mostra

- A página atual, montada do Documento (§4.2): títulos com estilo de título, parágrafos
  refluídos, cabeçalho e rodapé em cinza pequeno (Ctrl+Shift+H oculta), notas em corpo menor.
- **Diagramas inline e atômicos**: o desenho do FEN (quando lido) ou o recorte, a legenda, o
  estado ("conferido", "confiável pelos lances", "lido, não conferido", "não lido"), o FEN em
  monoespaçado e "Copiar FEN". Uma seleção que cruza um diagrama nunca o apaga.
- **Realce**: baixa confiança com fundo laranja-claro (liga e desliga pela barra do painel);
  fora do léxico com ondulado; virtual com pontilhado; aguardando leitura em cinza; manual e
  revisado sem realce.
- Fonte Segoe UI Symbol por padrão; corpo pelo zoom do painel.
- *Nota do passo A3*: até o layout do passo F dar a função das áreas e os parágrafos, o
  Documento mostra uma linha impressa por parágrafo (refluir juntaria título e corpo), as
  margens pela regra do cabeçalho corrido da exportação, e o glifo que ninguém leu como □
  com o fundo da baixa confiança.

### 6.2 Sincronia

- Cursor no Documento → glifo (ou palavra selecionada) destacado na Imagem e na Linha; com
  Seguir, a Imagem rola até ele.
- Clique na Imagem → cursor no glifo, e o Documento rola até ele.
- Fila → o item atual destacado e visível nos dois.
- O mapa posição→gid fica em `QTextBlockUserData` por bloco (não um `QTextCharFormat` por
  glifo: a coleção de formatos não libera e vazaria a cada montagem).

### 6.3 Edição: a sessão

- Editar **abre uma sessão** que cobre a **menor sequência de palavras** tocada por cada
  `contentsChange`, e cresce se a edição seguinte tocar palavras vizinhas. Ela guarda a
  sequência original de gids (com o espaço como símbolo). O `QTextDocument` tem
  `setUndoRedoEnabled(False)`; Ctrl+Z e Ctrl+Y vão ao controlador (`ShortcutOverride`).
- A cada `contentsChange`, o texto atual da sessão é **realinhado** contra o original
  (Levenshtein; desempate: substituição antes de inserir+apagar; alinhamento à esquerda),
  então teclas, IME, painel de emojis, colar, arrastar e autocompletar dão o mesmo resultado.
  Os caracteres que nenhum `contentsChange` tocou ficam com o glifo deles, e só os vãos entre
  eles são realinhados (D1: apagar o segundo "s" de "cassa" tira o segundo glifo).
- A sessão **confirma** ao sair dela (cursor ou clique fora), com Enter (e avança à próxima
  palavra duvidosa) ou Shift+Enter (sem avançar), como **um passo** do desfazer. Esc
  **restaura** a sessão (e Ctrl+Y a reaplica). Depois de confirmar, o bloco é
  **re-renderizado do modelo**.
- **Enter numa palavra sem mudança** a aceita: os glifos ficam `revisado` e saem da fila
  (como o Skip do FineReader). Só os que têm leitura (D1): o □ e o aguardando ficam na fila.
- Mapeamento dos trechos alinhados:

| Trecho | Vira | Passo |
|---|---|---|
| 1 → 1 | `char` do box, fonte `manual` | D1 |
| k → 0 | descartar os boxes (recuperáveis no desfazer) | D1 |
| espaço inserido | `quebras` | D1 |
| espaço apagado | `juncoes` | D1 |
| 0 → k (letra que faltou) | glifos virtuais; se houver tinta sem box no lugar, a Linha oferece "Ctrl+M marca o quadro" | D1 |
| k → 1 (rn → m) | `juntar` os k boxes, char manual | G |
| 1 → k (m → rn) | **dividir** pela tinta em k partes (o Ctrl+D de hoje, em sequência); sem vão, um box de k caracteres (como ligadura), que não ensina | G |
| Ctrl+Shift+Enter | `paragrafo_antes` | G |
| hífen de fim de linha apagado | junta a palavra e remove `hifen_de_quebra` | G |

- Até o passo G, um trecho sem tradução recusa a confirmação com o aviso "este tipo de
  edição chega numa próxima versão" e a sessão é restaurada; a prévia de substituição marca e
  desabilita esses casos.
- **Toda operação estrutural** (descartar, virtual, juntar, dividir) mostra na Linha um aviso
  não modal: "rn → m: 2 glifos juntados · Ctrl+Z desfaz".
- **Confirmar é revisar**: todos os glifos da sessão ficam `revisado`.
- **Ctrl+Enter** confirma e ensina o glifo sob o cursor (num virtual, a barra diz "glifo sem
  tinta não ensina"). Editar nunca ensina sozinho.
- Ctrl+B/I/U gravam o estilo nos boxes da seleção.

### 6.4 Entrada de notação

- Num token classificado como lance, a letra de peça maiúscula seguida de casa vira figurina
  ao confirmar, conforme o modo do livro (figurinas ou letras) e o idioma do projeto (pt:
  R D T B C; en: K Q R B N).
- Ctrl+Shift+K/Q/R/B/N/P inserem ♔♕♖♗♘♙ (repetir o atalho alterna para a preta); F2 abre a
  paleta no cursor.

**CA-6.1** Clicar numa palavra do Documento destaca os glifos dela na Imagem (destaque
gravado no item; [desempenho] p95 ≤ 50 ms).
**CA-6.2** "conc1uir" → "concluir" por **Backspace no 1 e digitar l** muda um box para `l`
manual, sem virtual, e tira a palavra da fila.
**CA-6.3** Inserir o espaço em "ganhartempos" dá duas palavras na vista, na busca e na
exportação, sem mexer em box.
**CA-6.4** Cada linha da tabela de §6.3 tem teste no passo indicado (inclusive IME por
`QInputMethodEvent` sintético e colar várias linhas) e se desfaz com um Ctrl+Z.
**CA-6.5** A vista mantém rolagem e cursor quando outra ação muda a página.
**CA-6.6** "m" → "rn" num "m" impresso dá dois boxes com tinta e nenhum virtual.
**CA-6.7** Num projeto sintético em modo figurinas e idioma pt, digitar "Cf3" num token de
lance dá "♘f3"; em modo letras, fica "Cf3".
**CA-6.8** Apagar uma seleção que cruza um diagrama apaga o texto e mantém o diagrama.
**CA-6.9** Esc numa sessão restaura a palavra e Ctrl+Y a reaplica; Enter numa palavra sem
mudança a tira da fila sem trocar a fonte dos glifos.

## 7. Localizar e substituir

### 7.1 Localizar (Ctrl+F)

- Barra no topo da vista direita: texto; **Aa**; **palavra inteira**; **.\*** (regex);
  **figurina = letra** (♘f3 casa Cf3 e Nf3); **escopo** (seleção, página, livro, intervalo);
  **onde** (prosa, notação, FEN, legendas, cabeçalhos).
- F3 / Shift+F3 próxima / anterior; Alt+Enter manda todas para Resultados.
- Pacote **`regex`** (compatível com `re`), Unicode, `concurrent=True` (solta o GIL) e
  `timeout` de 0,5 s; o **primeiro timeout aborta a busca inteira** com o aviso "padrão lento
  demais"; classes de xadrez expandidas antes de compilar, com a expansão numa dica: `\L`
  lance, `\P` peça (figurinas e letras do idioma), `\C` casa, `\V` valoração (± ∓ ⩲ ⩱ ! ? …).
- **Busca por glifo**: caractere + fonte (rede, base, livro, manual) + faixa de confiança;
  abre na Galeria.
- Resultados: página, linha, trecho com o casamento em negrito; contagem por página na
  gaveta; "45 páginas não reconhecidas ficaram fora" quando for o caso; "nada encontrado" na
  barra.

### 7.2 Substituir (Ctrl+H)

- Campo "substituir por", com `\1` e `\g<nome>`.
- Na página atual, **Substituir** e **Substituir todas** aplicam direto. Fora dela,
  Substituir todas **sempre** monta a prévia em Resultados (antes, depois, caixa de marcar,
  etiqueta prosa/notação; casos ainda sem tradução marcados e desabilitados) com "Aplicar N"
  (Enter).
- "Onde": **Prosa | Notação | Ambos**, padrão Prosa. FEN é pesquisável, nunca substituível.
- A substituição aplica as operações de §6.3, deixa os glifos `manual`, não ensina, e é **uma
  transação** do desfazer, mesmo no livro inteiro.

### 7.3 O índice

- Por página: texto da vista, mapa posição→gid e uma etiqueta por palavra (prosa, notação,
  legenda, cabeçalho, FEN). Montado em segundo plano ao abrir; atualizado pelo gravador; não
  gravado em disco. A busca roda numa thread, com cancelamento entre páginas ao digitar.

**CA-7.1** [desempenho] Sobre 230 páginas (o gabarito de 7 páginas repetido, sem OCR),
`buscar(r"(?<=\w)1(?=\w)")` termina com p95 ≤ 1 s e acha exatamente o que o `re` acha no
texto concatenado; cada resultado leva ao gid certo. A montagem do índice: p95 ≤ 2 s.
**CA-7.2** Substituir todas num livro sintético de 230 páginas e um Ctrl+Z volta todas.
**CA-7.3** Regex inválida mostra o erro na barra; `(\w+)+$` sobre texto longo aborta com o
aviso, e um `QTimer` de 16 ms continua disparando durante a busca. [desempenho] O atraso
de evento durante a busca fica p99 < 100 ms.
**CA-7.4** `\L`, `\P`, `\C`, `\V` com casos positivos e negativos, em pt e en.
**CA-7.5** Substituir todas fora da página nunca aplica sem a prévia; Prosa nunca toca token
de notação e Notação nunca toca prosa; FEN nunca é substituído; nada é ensinado.
**CA-7.6** Com "figurina = letra", buscar "Cf3" acha "♘f3" e "Nf3"; sem a opção, só "Cf3".

## 8. A revisão

### 8.1 A fila

- Modos: **confiança**, **ordem de leitura**, **por caractere**, **palavras desconhecidas**,
  **diagramas por conferir**; escopo página ou livro. F7 cicla o modo; Shift+F7 alterna o
  escopo; o seletor (`QToolButton` com menu) e o contador ficam no cabeçalho do Inspetor.
- **Alt+↓ / Alt+↑**: próximo / anterior item no modo e escopo atuais, em qualquer painel.
  **F6**: próxima *página* com pendentes.
- Recalculada incrementalmente, só para os gids tocados.

### 8.2 A Galeria por caractere

- Grade dos recortes de todos os glifos lidos como um caractere (ou de uma busca de glifo),
  da página ou do livro, por confiança, com a leitura embaixo e a página na dica.
- Seleção pelo teclado (setas, Shift, Ctrl+A); **digitar um caractere aplica à seleção**;
  Enter ensina a seleção (uma amostra por glifo); Shift+Enter só corrige.

### 8.3 Padrões e procedência

- Aba Padrões: busca por caractere, origem de cada amostra (página e glifo, "ir para"), altura
  relativa, efeito, e **esquecer que se desfaz**.
- **Procedência**: esquecer (ou desfazer) uma amostra devolve à fila, em segundo plano e pelo
  índice, todos os boxes lidos por ela; uma página verificada atingida volta a `em_revisao`,
  com aviso.
- Ao ensinar, o Inspetor avisa conflito ("este glifo está a 0,1 de 14 amostras de '1'") e
  mostra o efeito ("Enter ensina 'l' · 23 iguais nesta página · 410 no livro", a segunda
parte quando o escopo da fila é o livro).

### 8.4 Página verificada

- Ctrl+T marca a página verificada e abre a próxima não verificada. Com pendentes, a barra
  pede confirmação inline: "aceitar 12 pendentes como estão? Enter aceita · Esc não marca";
  esse Esc fecha só a pergunta.

**CA-8.1** Na Galeria, selecionar 40 glifos e digitar "l" corrige os 40 num passo do
desfazer; Shift+Enter só corrige (nenhum padrão novo).
**CA-8.2** Alt+↓ funciona com o foco em cada painel e nunca muda texto; F7 e Shift+F7 trocam
o modo e o escopo.
**CA-8.3** [desempenho] Do `abrir()` ao painel de Páginas com 230 linhas: p95 ≤ 300 ms. Mudar
os limiares recalcula os pendentes de todas as páginas sem reler JSON.
**CA-8.4** Esquecer uma amostra que leu 30 boxes em 3 páginas devolve os 30 à fila (e uma
página verificada entre elas volta a `em_revisao`); desfazer o esquecer os tira de novo.
**CA-8.5** As transições de §4.4 têm teste; o Esc da confirmação do Ctrl+T não fecha a busca
aberta; no passo E, o lote pula verificadas.
**CA-8.6** O aviso de conflito aparece quando a distância ao vizinho de outro caractere é
menor que a margem configurada (matriz montada à mão).

## 9. O treino

### 9.1 O livro novo (os primeiros 10 minutos)

1. Ctrl+N: arquivo, nome, idioma, intervalo do corpo do livro (pular capa e sumário).
2. O servidor de leitura (§11) carrega os modelos com progresso; a navegação já funciona e os
   boxes ficam "aguardando leitura".
3. PDF com texto nativo (`core.pdf_nativo`): oferece usá-lo em vez de OCR.
4. Reconhece 3 páginas de amostra (a 10%, 50% e 90% do intervalo) e abre a fila **por
   caractere** na amostra.
5. O cartão **Saúde do livro** (estado vazio do Documento; e a gaveta, quando aberta) mostra pendentes
   por página da amostra, antes e agora, e os padrões ensinados; "Reconhecer o livro" fica
   em destaque quando a amostra cai abaixo do limiar escolhido.

### 9.2 O que muda no treino

- Continua: Enter ensina, Shift+Enter corrige, dividir, juntar, ajustar, quadro (Ctrl+M),
  seleção múltipla, desfazer (que é o *Back* do FineReader).
- **Efeitos**: negrito e itálico (`core.negrito`) guardados com a amostra; o k-NN só compara
  amostras do mesmo efeito quando o efeito do glifo é conhecido.
- **Ligaduras**: padrão de vários caracteres (`ﬁ` como "fi"); no Documento, cada letra
  sincroniza com o mesmo gid.
- A faixa Linha no lugar do rótulo "Na linha".

**CA-9.1** [livro_real] Nas linhas de corpo do gabarito (p. 21–27), o CER depois de ensinar
as legendas em negrito é ≤ o de antes, e nenhum glifo de corpo certo passa a errado.
**CA-9.2** Uma ligadura `ﬁ` ensinada lê como um box "fi" nos dois modos de `texto.py`, e cada
letra no Documento sincroniza com o mesmo gid.
**CA-9.3** Amostras com efeito diferente nunca são vizinhas no k-NN quando o efeito do glifo
é conhecido (matriz montada à mão).
**CA-9.4** Com o servidor de leitura falso, do Ctrl+N ao primeiro Enter na fila: ≤ 3 gestos
além do diálogo de arquivo (contados por filtro de eventos). [desempenho] Com o real, o
atraso de evento fica p99 ≤ 50 ms durante o carregamento dos modelos.
**CA-9.5** Um PDF sintético com texto nativo mostra a oferta, e aceitá-la cria as páginas sem
OCR (o servidor não recebe pedido de leitura).

## 10. Os diagramas

- Zona `diagrama`; a conferência é o editor Diagrama do Inspetor, **não modal**: a Imagem dá
  zoom no diagrama e continua navegável; PgUp/PgDn no editor passam ao diagrama anterior ou
  seguinte do livro; F8 vai ao próximo por conferir.
- **Diagramas do livro** (aba da vista direita): grade com recorte, desenho e estado; filtros
  por conferir, lidos sem confiança, conferidos.
- **Validação pelos lances** (a ideia do chesspdf): os lances do texto depois do diagrama (até
  o próximo diagrama ou título), em SAN, jogados a partir do FEN (python-chess). Primeiro
  lance ilegal: aviso ("1.♘f3 do texto não é legal aqui") e o diagrama entra na fila de
  diagramas. Todos os lances da primeira linha legais: estado **confiável pelos lances**.
- **Roque**: rei e torre nas casas iniciais sugerem o roque, marcado "inferido", nunca
  afirmado sem conferência; en passant fica `-`.
- **PGN**: a posição e os lances seguintes de cada diagrama (`core.pgn`, `core.nags`).

**CA-10.1** [livro_real] Sobre os FEN do gabarito (p. 21–27) e sobre 100 versões perturbadas
deles (uma peça trocada, tirada ou movida, semente 1234, só posições legais): a precisão de
"confiável pelos lances" é 1,0 nos dois conjuntos; nas perturbadas, a validação detecta ≥ 60%
das que têm um lance do texto afetado pela perturbação (denominador calculado por
`ferramentas/medir.py`).
**CA-10.2** Com a conferência aberta, a Imagem aceita zoom e rolagem.
**CA-10.3** O roque inferido nunca sai afirmado no FEN exportado sem conferência.

## 11. O servidor de leitura

- **Um processo filho único**, aberto com o projeto (`spawn`; guarda `if __name__ ==
  "__main__"` em `__main__.py`; importa só `abbychess.servidor_de_leitura`, sem PySide6),
  guarda os modelos (a base global sozinha ocupa ~700 MB) e atende **toda** leitura global:
  F5, releituras de glifo (dividir, juntar, ajustar, quadro), lote, e a leitura e releitura
  de diagramas e de legendas pelo core. Prioridade `BELOW_NORMAL`,
  `torch.set_num_threads(max(1, núcleos − 2))`.
- **Se o servidor morrer**, a interface detecta, reinicia uma vez, reenvia os pedidos
  pendentes e registra em Avisos; na segunda falha, oferece reabrir o projeto.
- **A interface não importa torch**: tem só os padrões do livro, para a propagação e o aviso
  de conflito.
- **Preempção entre glifos**: o servidor atende pedidos interativos antes do próximo glifo do
  lote. Enquanto o servidor carrega ou atende, o box fica "aguardando leitura", sem bloquear.
- **Escritor único**: o servidor devolve resultados pela fila (boxes sem gid); a interface
  aplica a regra de conflito, dá os gids, aplica §4.6 e grava pelo gravador.
- **Conflito**: página aberta e suja não é sobrescrita; fica "reler depois". Desde o passo L,
  a leitura de uma página cuja geometria mudou depois do pedido é descartada e pedida de
  novo (§12.4).
- **Padrões**: a interface manda ao servidor os **deltas** (amostra criada ou apagada),
  aplicados antes de cada página e de cada pedido interativo.
- Lote: cancelar (✕ na barra ou Projeto › Cancelar lote; nunca o Esc), retomar do ponto,
  progresso na gaveta, tempo estimado na barra; páginas verificadas puladas.
- **Fábrica de leitor** importável por caminho, para os testes (leitor falso, sem torch).

**CA-11.1** [processo] Com o leitor falso (200 ms por página) e 50 páginas sintéticas,
roteiro de navegação, ensino e (a partir do passo B) busca durante o lote: todas as ações
têm efeito e nenhuma é ignorada. [desempenho] O atraso de um `QTimer` de 16 ms fica p99 ≤ 50
ms, primeiro com o falso e depois com o real.
**CA-11.2** Um padrão ensinado antes de o servidor começar a página k vale na página k.
**CA-11.3** [processo] Fechar com o lote ativo: o filho termina em ≤ 5 s (`join(5)`, depois
`terminate`), não sobra processo órfão (`psutil`) e todo JSON gravado carrega.
**CA-11.4** Página aberta e suja: o hash do arquivo não muda e ela entra em "reler depois".
**CA-11.5** Cancelar e retomar: a união das páginas lidas é o intervalo pedido, sem página
lida duas vezes.
**CA-11.6** [desempenho] Memória total (interface + servidor) com o lote rodando ≤ 2,5 GB.
**CA-11.7** [desempenho] Releitura de um glifo com o lote rodando: p95 ≤ 150 ms. Sem
servidor pronto, o box fica "aguardando leitura" e recebe a leitura quando o servidor
responde.
**CA-11.8** Um F5 pedido durante o lote é atendido antes da próxima página do lote (ordem
registrada pelo servidor falso).

## 12. Exportação e imagem

### 12.1 Formatos e opções

- PDF pesquisável (texto sob a imagem), DOCX e EPUB (texto formatado: títulos, parágrafos,
  notas, estilos, diagramas desenhados ou recortados), TXT e **PGN**.
- Opções: manter cabeçalhos e rodapés; manter quebras de linha e hífens; números de página;
  só páginas verificadas; intervalo; diagramas desenhados × recortados; realçar baixa
  confiança no DOCX.
- Lê o Documento (§4.2), não os boxes.

### 12.2 Pré-visualização e relatório

- Pré-visualização HTML (do mesmo Documento) antes de gravar.
- Relatório em Resultados: cabeçalhos tirados, diagramas recortados e o motivo, páginas não
  verificadas, pendentes.

### 12.3 Reprodutibilidade

- Com o mesmo `SOURCE_DATE_EPOCH`, duas exportações dão os mesmos bytes.

### 12.4 Editor de imagem e operações de página (passo L)

- Dividir páginas espelhadas, girar, cortar, endireitar à mão, aplicados a pares, ímpares ou
  intervalo; apagar, reordenar e inserir páginas (com `pid` estável, §4.1;
  `inclinacoes.json` passa a ser chaveado por `pid`).

**O modelo (decidido no início do passo L, 2026-10-22; revisado na mesma data).** Até o
passo K o índice da página no PDF era ao mesmo tempo a identidade dela e a posição no livro.
A partir do L:

- **A sequência do livro** fica em `projeto.json` (`versao` 3): uma lista ordenada de
  entradas `{pid, fonte, pagina, quadro, giro, metade, angulo}`. `fonte` é `"livro"` ou
  `"inseridas/<sha256>.<ext>"`; `pagina`, o índice dentro dela; `quadro`, o retângulo
  inteiro `[x0, y0, x1, y1]` em pixels da página da fonte renderizada no DPI do projeto
  (nulo: a página inteira); `giro`, 0, 90, 180 ou 270 graus no sentido horário, aplicado
  depois do quadro; `metade`, só um rótulo (`"esquerda"`, `"direita"` ou nulo) de quem veio
  de uma divisão; `angulo`, o endireitar à mão, ou nulo para o medido. Cortar e dividir só
  mudam o `quadro`: a composição fica fechada sob qualquer operação seguinte. **A posição no
  livro é o índice na sequência**, e é ela que a interface mostra e as exportações seguem.
  Todo dado de página (JSON, zonas, diagramas, inclinação, busca, `janela.json`,
  `livro.json`, as listas de páginas do `projeto.json`, amostras) é chaveado por `pid`; o
  número da página é derivado da sequência. O `indice` gravado nos JSON de página antigos
  deixa de valer.
- **Todas as páginas têm `pid`** desde a migração (as não editadas também), e o `pid` nunca
  muda nem é reaproveitado: reordenar mexe só na sequência.
- **A imagem da página** é: a página da fonte → endireitar (o `angulo` à mão, ou o medido) →
  `quadro` → `giro` (decidido na rodada 3, 2026-10-23, em lugar de quadro → giro →
  endireitar: endireitar gira em volta do centro, e o centro muda com o quadro; endireitando
  antes, cortar e girar de 90 em 90 graus são contas inteiras sobre a página endireitada, e
  a caixa passa de uma geometria a outra sem arredondar). O `quadro` é em pixels da página
  endireitada inteira, e a entrada com quadro ou giro grava o `tamanho` da página da fonte.
  A inclinação é medida na página inteira já girada (o texto de uma página escaneada de lado
  mede em pé; girar de 90 e endireitar comutam em volta do centro, a menos de um pixel na página que
  não é quadrada; a conta das caixas não depende disso, porque a fonte é endireitada antes) e guardada em
  `inclinacoes.json` como `p<pid>:inteira:<giro>`; ela é medida de novo quando o giro muda
  **só em página sem boxes**: com boxes, o ângulo em que ela foi lida fica.
- **Os glifos acompanham a imagem**: girar, cortar e dividir levam os boxes, as zonas, os
  diagramas e os tabuleiros com conta exata (`abbychess.geometria`; o `gid` fica). **Cada
  JSON de página (versão 3) grava a `geometria` (quadro e giro) em que os boxes estão** e o
  tamanho da fonte; ao carregar, se ela difere da entrada da sequência, os boxes são levados
  nessa hora (`modelo.reenquadrar`). Assim girar e cortar gravam só a sequência, o Ctrl+Z é
  a sequência de antes, e uma queda no meio não deixa boxes no quadro errado. **O glifo que
  não cabe no quadro fica guardado na página** (`fora`: o box na página endireitada inteira e
  o lugar dele na ordem de leitura): o Ctrl+Z, um quadro maior ou tirar o corte o devolvem,
  com o mesmo `gid`, mesmo depois de gravar e reabrir. As áreas são aparadas no quadro; o
  tabuleiro e o diagrama que não cabem saem; uns e outros ficam guardados na página
  (`areas_fora`, inteiros) e voltam como os glifos (a área aparada volta inteira se
  ninguém a mexeu; o diagrama que volta com o id tomado ganha outro). O `angulo` do glifo
  (o do texto impresso) acompanha o giro. Endireitar à mão desfaz a leitura da página
  (com pergunta): os glifos marcados à mão ficam, girados em volta do centro; os outros, as
  zonas automáticas e os diagramas saem; o estado vai a `glifos_marcados` (§4.4).
- **Dividir** uma página espelhada dá duas entradas, cada uma com metade do `quadro` (no `x`
  escolhido): a esquerda fica com o `pid`, a direita ganha um `pid` novo. Cada box vai para
  a metade do centro dele; os que mudam de página ganham `gid` novo (do `pid` novo), e o
  projeto guarda `gids_movidos` (velho → novo). As junções e os virtuais que ligam glifos das
  duas metades se desfazem; as zonas são cortadas pela divisão. Uma metade não se divide de
  novo.
- **Inserir** copia o PDF ou a imagem para `inseridas/` (nome pelo SHA-256): o projeto não
  depende do arquivo de fora. Cada página dele vira uma entrada com `pid` novo; a imagem
  solta é lida no DPI dela (sem DPI, o do projeto); PDF cifrado é recusado com aviso.
- **Apagar** tira a entrada da sequência para `apagadas` (com a posição de onde saiu): a
  página some do livro, da busca, da fila e das exportações, mas o JSON e as amostras
  ficam (a amostra continua ensinando); o Ctrl+Z e **Página › Páginas apagadas…** a
  devolvem com o mesmo `pid`. Um `p<pid>.json` que não está na sequência nem em `apagadas`
  (uma queda entre gravações) aparece em **Páginas apagadas…**.
- **A ordem das gravações**: o contador de `pid` e a sequência são gravados antes de qualquer
  arquivo de página.
- **A amostra acha o glifo de origem** pelo `gid` dela: `pid = gid >> 20`, depois
  `gids_movidos`; o nome do arquivo da amostra (com o número antigo da página) não é
  renomeado e não é usado para navegar. As amostras antigas sem `_g` vão à entrada
  `fonte="livro"` da página do nome (a metade esquerda, se ela foi dividida). Origem numa
  página apagada: oferece restaurá-la; glifo cortado fora: "o glifo de origem saiu da
  página".
- **Cada operação é uma transação do desfazer** (§14.2): a sequência antes e depois (aplica
  só se a sequência atual é a de depois) e a `Diferenca` de cada página cujos boxes mudaram.
  Desfazer uma divisão aposenta o `pid` novo (nunca reaproveitado) e tira os `gids_movidos`
  dela. A seleção (pares, ímpares, intervalo "3-7, 12") é resolvida em posições do livro na
  hora da operação, e a operação inteira é uma transação. O desfazer não sobrevive a fechar
  o projeto: depois de reabrir, o box tirado por um corte não volta (alargar o corte não o
  devolve).
- **O lote e o servidor de leitura**: o intervalo do lote é resolvido em `pid` ao começar, e
  um `pid` apagado no meio é pulado; o pedido ao servidor leva a geometria, e a leitura que
  chega com outra geometria é descartada e pedida de novo. Girar, cortar, dividir e
  endireitar ficam desligados na página que o servidor está lendo. Em projeto só para
  leitura, as operações de página ficam desligadas.

**CA-12.7** (migração v3) Um projeto v2 de 60 páginas com 3 páginas editadas (uma com `pid`
diferente do índice), páginas v1 ainda não migradas, `inclinacoes.json`, `janela.json` e as
listas de páginas do `projeto.json` abre na v3: `backup-v2/` com os arquivos de antes; a
sequência tem as 60 entradas na ordem do PDF; as editadas mantêm o `pid`, as v1 não
migradas ficam com `pid` = índice, as outras ganham `pid` novos acima de todos;
`inclinacoes.json`, `janela.json` e as listas passam a `pid`; todo `gid`, amostra, zona e
diagrama fica igual; reabrir não migra de novo; copiar `backup-v2/` de volta reabre igual; um
projeto v1 vai direto à v3 (CA-4.5 de novo). Só para leitura: a sequência é montada na
memória e nada é gravado. Sem a fonte do livro (o número de páginas não se sabe), a v3
espera: o projeto segue na v2 e migra na abertura em que o PDF estiver no lugar.
**CA-12.8** (reordenar) Mover as posições 2–4 para depois da 10 só reescreve a sequência
(nenhum JSON de página muda, pela data e pelo hash); o seletor, a gaveta de Páginas, a busca,
a fila do livro e as exportações mostram a ordem nova; a página aberta e `janela.json` seguem
o `pid`; o Ctrl+Z devolve a ordem, e o Ctrl+Z seguinte desfaz a edição de página feita antes
da reordenação.
**CA-12.9** (inserir) Inserir um PDF de 2 páginas e uma PNG depois da posição 5, e uma página
antes da primeira, cria entradas com `pid` novos, copia os arquivos para `inseridas/` (o
projeto abre igual com o original apagado) e cada página renderiza igual à fonte;
reconhecer, ensinar e exportar funcionam nelas. Um PDF cifrado é recusado com aviso e nada
muda.
**CA-12.10** (apagar) Apagar as posições 3 e 7 tira as duas da sequência, da gaveta, da busca,
da fila do livro, das contagens e das exportações; os JSON e as amostras continuam no disco;
o Ctrl+Z, e depois de reabrir **Páginas apagadas…**, as devolvem no lugar, com os mesmos
`pid` e boxes. Um `p<pid>.json` órfão aparece em **Páginas apagadas…**.
**CA-12.11** (girar) Numa página sem endireitar (ângulo 0), girar 90° as ímpares de 1–10: cada
imagem é `np.rot90(antes, k=-1)`; os boxes caem sobre os mesmos pixels (o recorte de cada um
é o de antes girado); os `gid` não mudam; 90° duas vezes dá o mesmo que 180°; o Ctrl+Z
volta tudo. Uma queda injetada depois de gravar a sequência e antes dos JSON de página
(CA-4.2) reabre com os boxes no lugar certo.
**CA-12.12** (cortar) Cortar um intervalo com um retângulo: a imagem é o recorte exato; os
boxes de dentro são deslocados (mesmos pixels); os de fora ficam guardados na página
(`fora`); o Ctrl+Z, e tirar o corte depois de gravar e reabrir, os devolvem com os `gid` de
antes e no lugar da ordem de leitura. A amostra cuja origem foi cortada diz "o glifo de
origem saiu da página".
**CA-12.13** (dividir) Dividir uma página dupla (sintética, com texto nas duas metades): duas
entradas no lugar dela, cada uma com a metade dos pixels; os boxes da direita têm `gid`
novos e `gids_movidos`; a amostra ensinada antes, num glifo da direita, abre o glifo certo
pelo "ir à origem"; a busca acha uma palavra de cada metade na página certa; dividir uma
metade é recusado; o Ctrl+Z junta de novo e aposenta o `pid` novo.
**CA-12.14** (endireitar à mão) O ângulo à mão vence o medido e é guardado por `pid`; a
página vai a `glifos_marcados`, com os glifos marcados à mão girados em volta do centro; o
Ctrl+Z devolve o ângulo e os boxes.
**CA-12.15** (seleção) "pares", "ímpares" e "3-7, 12" resolvem para posições do livro (não do
PDF), depois de uma reordenação também; a operação vale exatamente nelas, numa transação;
com o lote rodando ou em projeto só para leitura, as operações ficam desligadas e nenhum
arquivo muda.
**CA-12.16** (exportar depois das operações) TXT, DOCX e EPUB seguem a sequência; o PDF
pesquisável usa as imagens transformadas; a camada de texto nativa (§12.1) só vale nas
entradas `fonte="livro"` com `giro` 0, sem `quadro` e com ângulo efetivo 0.
**CA-4.6** vale também depois de dividir, de apagar e restaurar, e de inserir na posição 1.

**CA-12.1** Golden normalizado: DOCX = `word/document.xml` em C14N sem `w:rsid*`, texto por
parágrafo e estilo; EPUB = cada XHTML do spine em C14N (e o OPF sem `dc:identifier` e
`dcterms:modified`). Nas 4 combinações cabeçalhos × quebras, sobre página sintética com
cabeçalho e hífen, a forma normalizada é igual a `tests/golden/*.txt` (atualizar só com
`--atualizar-golden`).
**CA-12.2** O PGN de uma página com diagrama conferido e lances: `chess.pgn.read_game` sem
erros, `[FEN]` igual ao conferido, `[SetUp "1"]`, os lances do gabarito, NAGs mapeados.
**CA-12.3** `tests/golden/opcoes.yaml` declara, para cada opção, a diferença esperada na
forma normalizada (linhas acrescentadas ou removidas, por regex: cabeçalho, número de página,
hífen, desenho × recorte, realce); ligar a opção produz exatamente essa diferença e nenhuma
outra.
**CA-12.4** Pré-visualização e DOCX têm o mesmo texto por parágrafo.
**CA-12.5** O relatório lista os mesmos cabeçalhos, diagramas recortados (com motivo),
páginas não verificadas e pendentes que o Documento.
**CA-12.6** Duas exportações com o mesmo `SOURCE_DATE_EPOCH` são iguais byte a byte.

## 13. A aparência

- **Tokens** em `app/estilo.py` (cores, espaçamentos 4/8/12/16/24, raios, tipografia: Segoe UI
  9–10 pt na interface, Segoe UI Symbol no texto) e a folha de estilo Qt gerada deles; nenhuma
  cor literal fora dali.
- **Tema claro e escuro**, seguindo o sistema. **A página nunca inverte.** O contraste dos
  estados é medido contra o **papel de referência**: o cinza mediano do fundo do índice 25 do
  livro de referência, gravado no gabarito.
- **Estados por cor e traço** (Okabe-Ito; pen cosmético ≥ 1,5 px): pendente laranja tracejado;
  sem leitura vermelho pontilhado grosso; aguardando leitura cinza tracejado fino; aceitos
  discretos (§3.3); com V, manual roxo, livro verde, rede azul.
- **Ícones** SVG de licença permissiva, coloridos pelo tema; nada de marca.
- **Estados vazios** com instrução ("Página não reconhecida. F5 reconhece; Ctrl+M marca
  glifos à mão.") e **ocupado** sempre visível com a fila de tarefas.
- **Acessibilidade**: tudo pelo teclado; foco visível; `accessibleName` e dica em todo
  controle sem texto; alvos ≥ 24 px.

**CA-13.1** Um teste percorre os controles e falha se algum botão só com ícone não tiver
`accessibleName` e dica.
**CA-13.2** `ferramentas/capturas.py` (plataforma `windows`, janela visível) grava 8 PNG:
claro e escuro × 1366×768 e 1920×1080 × página com e sem leitura. Em offscreen, um teste
confere: contraste de cada token de estado ≥ 3:1 contra o papel de referência (WCAG); cada
estado com `Qt.PenStyle` distinto; nenhum widget fora da janela em 1366×768. A revisão humana
usa §16 e grava nota e data em `docs/revisoes/`.
**CA-13.3** Trocar o tema do sistema (`colorSchemeChanged` simulado) troca a paleta sem
reiniciar; uma varredura por AST não acha cor literal em `app/` fora de `estilo.py`.

## 14. Arquitetura

### 14.1 Controladores e eventos

- **Controladores sem Qt**: `ControladorDePagina` (página aberta, comandos, fila, sessão de
  edição), `ControladorDoLivro` (índice, busca, servidor, `livro.json`), `ControladorDeLayout`
  (zonas, funções, ordem, modelos). A janela só liga sinais a comandos.
- **Eventos finos**: `glifos_mudaram(gids)`, `layout_mudou(zona_ids)`, `pagina_trocou`; cada
  painel atualiza só o que o evento diz.
- **Cache** LRU de 5 páginas renderizadas e endireitadas, com pré-carga da seguinte.
- **Padrões incrementais**: esquecer e restaurar mexem na matriz, sem reler o disco.
- `exportar.py` deixa de importar privados do core (§18.2).

### 14.2 Desfazer do projeto

- `HistoricoDoProjeto` global de `Transacao(descricao, paginas: {pid: Diferenca(antes,
  depois, por gid)}, amostras_criadas, amostras_apagadas)`, e desde o passo L
  `sequencia: (antes, depois)` nas operações de página (§12.4: aplica só se a sequência atual
  é a de depois); limite de 50 MB, descartando as mais antigas.
- **Pré-condição por gid**: desfazer só aplica se o estado atual de cada gid da diferença é
  igual ao `depois`; senão recusa, com aviso, sem aplicar nada. A versão da página não entra.
- **A propagação de um Enter emenda o `depois`** da transação daquele Enter; desfazer com a
  propagação ainda rodando a invalida por um token, e os resultados dela são descartados.
- O lote com "refazer" fica fora do histórico (§4.6).
- A parte síncrona de um Enter (box `manual`, amostra gravada, delta ao servidor, cor nova)
  roda na hora; só a **propagação** dele entra na fila, depois da que já está rodando, e usa
  uma cópia da matriz que já inclui a amostra nova. Nada cancela uma propagação em curso.

**CA-14.1** `janela.py` < 500 linhas; um teste por AST reprova `def`/`lambda` aninhados em
`JanelaPrincipal` que chamem algo que não seja comando de controlador. Vale em todo passo
depois do 2a.
**CA-14.2** Desfazer com a página mudada por fora nos gids da transação é recusado com aviso;
mudança por fora em outros gids não impede o desfazer.
**CA-14.3** Ensinar, deixar a propagação terminar e desfazer volta a página toda (o Enter e o
que a propagação resolveu); desfazer com a propagação ainda rodando não aplica resultado
dela; um Enter durante uma propagação não perde nem duplica leitura (propagação lenta
injetada); [desempenho] com uma propagação lenta em curso, a cor do segundo Enter muda
dentro da meta de §2.

## 15. Qualidade

### 15.1 Pirâmide e marcadores

| Camada | Marcador | Conteúdo | Orçamento |
|---|---|---|---|
| Unitário puro | — | modelo, texto, layout sobre boxes sintéticos, regex, golden normalizado, atalhos | ≤ 15 s |
| Propriedade | — | máquinas de estado (gid, decisões, edição, desfazer), `derandomize` | ≤ 10 s |
| Controlador | — | `tmp_path`, páginas sintéticas, falhas injetadas | ≤ 15 s |
| Interface | — | pytest-qt offscreen, `waitUntil`, janela ativa | ≤ 15 s |
| **Suíte rápida** | `pytest -q` | as quatro acima | **< 60 s** (falha se passar) |
| Processo | `processo` | servidor com leitor falso, matança do gravador; só correção | ≤ 90 s |
| Livro real | `livro_real` | gabaritos, modelos reais, replay da fatia | ≤ 5 min |
| Desempenho | `desempenho` | §2 em p95, na máquina cadastrada | ≤ 10 min |
| Noturno | `noturno` | propriedade com 5.000 exemplos, 50 matanças | ≤ 30 min |
| Capturas | script | 8 PNG e revisão humana | manual |

- `pyproject.toml`: os marcadores; `addopts = -m "not livro_real and not desempenho and not
  processo and not noturno"`; `timeout = 60`; `[dev]` com hypothesis, pytest-qt,
  pytest-timeout, regex e psutil.
- **Portão**: com `ABBY_PORTAO=1`, um hook (`pytest_runtest_makereport`) transforma o
  skip de `livro_real` por PDF ausente em falha.
- `tests/conftest.py` central com a `QApplication` e as fixtures; `time.sleep` em laço vira
  `qtbot.waitUntil`.
- Determinismo: sem a Arial, o teste de página sintética **pula**; `torch.manual_seed` e
  `torch.set_num_threads(1)` nos testes com rede.

### 15.2 Gabaritos

- `tests/verdade/<livro>/iNNN.json` (índice do PDF): `pdf_sha256` (o que invalida o
  gabarito), `indice_pdf`, `pagina_impressa`, `render_sha256` e a versão do PyMuPDF (só
  aviso quando mudam), `verdade_versao`, `rotulado_por`, `revisado_por`; `blocos` (função,
  caixa relativa 0–1 sobre a renderização original, ordem, coluna, texto impresso);
  `diagramas` (caixa, FEN, lado, legenda, lances seguintes); `linhas_corpo` (caixa relativa,
  texto, negrito); `papel` (o cinza mediano do fundo).
- Páginas: Xadrez Vitorioso índices 20–26; Yusupov (Chess Evolution 1, um dos três PDFs da
  pasta, fixado por `pdf_sha256` no passo 0): uma de duas colunas e uma de uma; Darcy Lima
  índices 25–26 (p. 26–27 do PDF, impressas 27–28); três negativas (capa, sumário, sem
  diagrama).
- `ferramentas/rotular.py` exporta a leitura atual como rascunho (`docs/protocolo-rotulagem.md`).
  **O gabarito tem duas partes**: a **estrutura** (funções, ordem, colunas, negrito, caixas,
  diagramas com FEN, lado, legenda e primeiros lances), rotulada pelo assistente pelas faixas
  da página e revisada pelo usuário; e o **texto** de cada linha, que o assistente não
  transcreve (direito autoral do livro): começa como a leitura do programa, com
  `texto_verificado: false`, e o usuário o corrige por `texto-exportar` / `texto-importar`.
  As medidas de texto (CER, CA-9.1, CA-F.1) só contam linhas com `texto_verificado: true`;
  as de estrutura valem quando ela estiver revisada. Yusupov p. 33 tem uma transcrição
  revisada pelo usuário no corpus do PyBoxEditor (`benchmarks/corpus_v2`); trazê-la para o
  gabarito por ferramenta ficou para depois (registro do passo 0), e o usuário pode usá-la
  ao verificar o texto.
  **Conferência cega** (usuário ou outra pessoa): 1 página por livro transcrita do zero, sem a
  leitura, com concordância ≥ 99,5% dos caracteres; e 1 diagrama por livro montado sem ver o
  FEN do gabarito, que tem de dar o mesmo FEN. Mudar o gabarito sobe `verdade_versao`.
  Os gabaritos ficam fora de qualquer publicação.
- Métricas: P/R por função, Kendall da ordem, ligação de legenda, casas erradas no FEN, CER do
  corpo, P/R da validação pelos lances.

### 15.3 Método das medidas

- `tests/desempenho/` com `time.perf_counter_ns`, 5 aquecimentos descartados, 30 repetições,
  **p95**; o corte é o alvo × 1,2.
- Troca de página: de `ControladorDePagina.abrir(pid)` ao primeiro `paint()` completo do
  visor numa `QImage` 1600×1000; "no cache" = no LRU; "fora" = processo novo, modelos
  carregados (no servidor a partir do passo E; antes, no próprio processo, marcado no JSON
  da medida), PDF já lido uma vez.
- Enter: do `keyClick` à mudança de cor do box no item.
- Memória do desfazer: o que o histórico prende (`tracemalloc` ligado antes, o que se
  libera ao esvaziá-lo) num roteiro fixo de 60 ações em 3 páginas reais, extrapolado para
  300 páginas × 20 ações (declarado no JSON). Memória total: soma do RSS de interface e servidor (`psutil`) no
  pico de um lote de 20 páginas.
- Cada execução grava `docs/medidas/AAAA-MM-DD-<rótulo>.json` (`-linha-de-base`,
  `-qualidade-<livro>`, `-fatia-<livro>-passo-<passo>`; com a hora no nome se já houver um
  do dia, salvo `ABBY_SOBRESCREVER_MEDIDA=1`) (CPU, RAM, versões de Python, PySide6,
  PyMuPDF, torch, threads, commit). Falha só na máquina cadastrada em
  `docs/medidas/maquina.json`; noutra, só reporta.
- `ferramentas/medir.py --livro xv --indices 0,7,20-26` (as páginas da fatia e duas
  negativas) gera o JSON que o README cita; nenhum número é digitado à mão no README.

### 15.4 A medida da fatia

**CA-F.1** [livro_real] A partir de `tests/dados/fatia/xv-i020-026-inicial.zip` (projeto
reconhecido, padrões vazios, SHA-256 fixado), `ferramentas/replay_fatia.py` **simula** as
correções que levam as páginas ao gabarito (as `linhas_corpo` verificadas e os diagramas):
percorre as diferenças snapshot → gabarito na ordem de leitura e, para cada uma, aplica no
núcleo do programa o comando de menor custo de `ferramentas/replay/comandos.yaml`
(catálogo versionado: comando, passo em que existe, custo em gestos) e soma o custo
declarado. O custo de cada comando é conferido contra a interface real por
`tests/test_custo_dos_comandos.py`: QTest e um filtro de eventos que conta cliques, teclas
que não são modificador e atalhos disparados. O mesmo algoritmo e o mesmo catálogo,
filtrado por `passo ≤ atual`, rodam na linha de base e depois; o que nenhum comando do passo
corrige entra com o custo fixo de "impossível" declarado no catálogo. A linha de base é
sempre medida com o código da tag `passo-0` (o replay chama o núcleo, que muda); duas
medidas só se comparam com o mesmo snapshot, catálogo e versões dos gabaritos. O total
`gestos` (com os impossíveis) é ≤ 70% da linha de base depois do passo D1. (Até a versão
0.8 do roadmap havia também ≤ 85% depois do A3; saiu porque o A3 é só leitura e não muda o
custo de nenhum comando.)
**CA-F.2** (informativo, não reprova) Tempo humano pelo protocolo
`docs/medidas/protocolo-fatia.md`: o mesmo snapshot; o tempo vem do registro de gestos da
aplicação (`ABBY_REGISTRO_DE_EVENTOS`, somado por `ferramentas/tempo_da_fatia.py`),
descontados intervalos ociosos > 60 s; a linha de base num bloco de páginas, no programa da
tag `passo-0`, e a medida em outro bloco equivalente, invertendo os blocos numa segunda
sessão ≥ 7 dias depois; o resultado é segundos por erro do snapshot.

## 16. As revisões

Cada passo do roadmap fecha com três revisões independentes: **código** (correção,
simplicidade, testes); **produto e design** (com as capturas de CA-13.2, contra §1 e §2);
**medição** (`ferramentas/medir.py` e as camadas `livro_real` e `desempenho`). Os eixos
de nota são os de cada revisão: correção, simplicidade e testes (código); completude,
fidelidade das medidas e clareza para o usuário (produto e medição), mais produtividade e
layout quando o passo mexe na interface. Aprovação: nota ≥ 8 em todos; abaixo, o passo
volta. Registro em
`docs/revisoes/`.

## 17. Fora do escopo

- Descompilar ou imitar a marca da ABBYY; OCR de idiomas asiáticos; OCR na nuvem.
- Comparar documentos (talvez numa versão futura).
- Editar o PyBoxEditor daqui ou gravar na base global dele.
- Editar PDF (anotar, redigir, assinar).

## 18. Decisões em aberto

1. **Git**: o roadmap pede `git init` no passo 0. Precisa do sim do usuário.
2. **API pública no PyBoxEditor** para o que hoje é privado (`searchable_pdf`) e para
   `core.livro` (colunas, parágrafos): pedir lá ou reescrever aqui.
3. **Quem rotula os gabaritos** (o usuário, ou rotulagem assistida revisada por ele, com a
   conferência cega de §15.2).
4. **Rolagem contínua do livro** no Documento: depois do passo G, ou não.
5. ~~**Ícones**: Lucide (ISC) embutido, ou os padrão do Qt.~~ Decidido no passo K
   (2026-10-22): o Lucide 0.460.0 embutido, só os SVG usados, com a licença.
6. **Revisor externo**: o Codex não está instalado; as revisões usam revisores independentes
   do ambiente até ele ser instalado e autenticado.
