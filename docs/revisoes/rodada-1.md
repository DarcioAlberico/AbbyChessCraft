# Rodada 1 de revisão da spec e do roadmap (v0.1 → v0.2)

2026-10-15. Três revisores independentes, cada um com só os documentos e o código (o Codex,
pedido pelo usuário, não está instalado nesta máquina).

## Notas da v0.1

| Revisor | Eixos e notas |
|---|---|
| Arquitetura | Correção técnica 5 · Viabilidade 5 · Sequenciamento 4 · Testabilidade 6 · Riscos 4 |
| Produto e UX | Produtividade 6 · Layout 5 · Teclado 4 · Revisão 6 · FineReader 6 · Valor cedo 3 |
| QA | Mensurabilidade 4 · Automação 5 · Determinismo 4 · Cobertura 3 · Gabarito 2 |

Nenhum eixo chegou a 8; a v0.1 foi reprovada.

## Bloqueantes e como a v0.2 os trata

| Bloqueante | Onde ficou |
|---|---|
| Documento gravado × derivado; zona × bloco; virtual com caixa | §4.2: documento derivado de boxes + zonas + decisões por gid; virtual sem caixa |
| gid colide entre processos; subclasse copia o gid; migração em memória | §4.1: `Box` por composição, gid por página com `proximo_n`, `Diferenca`; §4.4: migração gravada |
| Edição tecla a tecla contradiz o CA-6.2; duas pilhas de desfazer; IME | §6.3: sessão por palavra com realinhamento, desfazer do widget desligado, re-render do modelo |
| rn → m e m → rn criam fantasmas sobre tinta | §6.3: k → 1 junta, 1 → k divide pela tinta; CA-6.6 |
| Desfazer espalhado e por página; CA-7.2 impossível | §14: `HistoricoDoProjeto` com transações; passo 2 |
| Lote: 700 MB por processo, escritor duplo, corrida, `PermissionError` | §11: servidor de leitura único, um escritor, deltas de padrões; §4.4 retry |
| F5 apaga decisões do usuário | §4.5 e CA-4.5 |
| Atalhos colidem com hoje e entre si (Alt+seta, Ctrl+T, Ctrl+G, AltGr, nativos) | §3.4: tabela nova, perfis; CA-3.7 com ligações nativas |
| Layout não cabe em 1366; Inspetor de abas | §3.1: gaveta, vista direita com abas, Inspetor de um editor, tabela de tamanhos; CA-3.2 |
| Sem entrada de figurinas | §6.4 e CA-6.7 |
| Valor só no passo 7 | Roadmap 0.2: fatia A1–A3 logo depois da fundação |
| Primeira sessão com livro novo | §9.1 e CA-9.4 |
| Metas sem método; tempo na suíte rápida | §15.3; marcador `desempenho` |
| Sem gabarito | §15.2 e passo 0 |
| Golden de zip instável | CA-12.1 normalizado, CA-12.6 |
| CAs faltando (treino, exportação, tema, migração, gravador, processo) | CA-4.1/4.2/4.4/4.5, 9.x, 11.x, 12.x, 13.2/13.3 |
| §9 sem passo; dependências erradas | Passo I; grafo novo |

Os importantes (procedência das leituras, regex com timeout, histograma no `livro.json`,
passo 1 em três, gravador e propagação, estados automáticos, notação na busca, prévia da
substituição, avisos persistentes, desenho discreto dos aceitos, editor de imagem) entraram
em §3.1, §3.3, §4.3, §7, §8.3, §11, §12.4, §13 e §14.
