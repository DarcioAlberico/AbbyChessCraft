# Rodada 2 de revisão (v0.2 → v0.3)

2026-10-15. Os mesmos três revisores da rodada 1, conferindo os próprios bloqueantes e
procurando os novos.

## Notas da v0.2

| Revisor | Eixos e notas |
|---|---|
| Arquitetura | Correção 7 · Viabilidade 7 · Sequenciamento 6 · Testabilidade 8 · Riscos 7 |
| Produto e UX | Produtividade 7 · Layout 7 · Teclado 5 · Revisão 7 · FineReader 7 · Valor cedo 6 |
| QA | Mensurabilidade 7 · Automação 7 · Determinismo 7 · Cobertura 7 · Gabarito 6 |

Reprovada: nenhum revisor deu ≥ 8 em todos os eixos.

## Bloqueantes novos e como a v0.3 os trata

| Bloqueante | Onde ficou |
|---|---|
| gid preso ao índice da página (quebra com reordenar/inserir) | §4.1: `pid` estável; CA-4.6 |
| Decisões apontando para gid aposentado | §4.1/§4.2: `Diferenca.sucessores` e reescrita; invariante no CA-4.3 |
| Desfazer recusa quase tudo (versão da página); lote não cabe no histórico | §14.2: pré-condição por gid, propagação emenda a transação; §4.6: `.antes-do-lote/` |
| §4.5 depois do servidor que precisa dele; I sem E; F antes de E | Roadmap: §4.6 no passo E; I ← E; F ← E |
| Formato da página mudando três vezes | 1a mantém v1; v2 inteira no 1b |
| Sessão por palavra não cobre espaço/colar; Esc contraditório; D sem semântica para parte | §6.3: sessão de várias palavras, Esc restaura, recusa com aviso até G |
| Quem lê o glifo na interação; torch duplicado | §11: interface sem torch, servidor com preempção; CA-11.7 |
| Colisões novas: Ctrl+Q, Shift+F10, Ctrl+Shift+B/P, H, Shift+Enter, Esc cancelando, Alt+↓ no combo, Shift+seta no `QLineEdit` | §3.4: `docs/atalhos.yaml` como fonte única, regras 1–6, tabela nova, perfil FineReader completo; CA-3.7 desde o passo 0 |
| Cartão do livro novo escondido em 1366; soma das larguras | §3.1: gaveta aberta em projeto novo, cartão como estado vazio, larguras somando ≤ 1366, empilhado abaixo de 1280 |
| Ordem serial ausente; D preso a B e C | Roadmap: ordem serial; D1 ← A3; D2 ← B, D1 |
| CA da fatia não reproduzível | §15.4: CA-F.1 por replay e gestos; CA-F.2 informativo |
| CA-10.1 circular | Perturbações com semente; revocação ≥ 60% |
| Tempo fora da camada `desempenho` | CA-9.4 e CA-11.1 separados; §0 |
| Yusupov não fixado | §15.2 por `pdf_sha256`; CA-5.2 só imagem |
| Escrita atômica e perda de 500 ms sem procedimento | §4.3 com a lista de arquivos; CA-4.4 com carimbo e matança |
| CA-12.3 sem oráculo | `tests/golden/opcoes.yaml` |
| Navegação e outros sem CA | CA-3.8, CA-4.7, CA-5.5, CA-6.8, CA-6.9, CA-7.6, CA-8.6, CA-9.5, CA-11.8 |

Importantes absorvidos: regex com `concurrent=True` e aborto no primeiro timeout; gravador
com instantâneo imutável; `Box.amostra` desde o 1b; `revisado` sem trocar a fonte; Enter
aceita palavra sem mudança; zona automática dividida por função; corte = alvo × 1,2;
`ABBY_PORTAO`; `render_sha256` só aviso; conferência cega; papel de referência fixado;
`psutil`; volta do backup v1 (CA-4.5).
