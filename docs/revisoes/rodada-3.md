# Rodadas 3 e 4 de revisão (v0.3 → v0.4, aprovada)

2026-10-15. Os mesmos três revisores das rodadas anteriores.

## Rodada 3 (sobre a v0.3)

| Revisor | Notas | Veredito |
|---|---|---|
| Arquitetura | Correção 8 · Viabilidade 8 · Sequenciamento 9 · Testabilidade 8 · Riscos 8 | Aprovado com duas condições de texto |
| Produto e UX | Produtividade 8 · Layout 8 · Teclado 7 · Revisão 8 · FineReader 8 · Valor cedo 8 | Um eixo abaixo de 8 |
| QA | Mensurabilidade 7 · Automação 8 · Determinismo 7 · Cobertura 7 · Gabarito 8 | Reprovado por ordem e redação |

O que a v0.4 mudou:

| Ponto | Onde ficou |
|---|---|
| Enter "na fila" contra a meta de 100 ms | §14.2: a parte síncrona roda na hora, só a propagação entra na fila; CA-14.3 |
| Perfil FineReader colidindo consigo mesmo (Ctrl+Shift+R, Ctrl+Shift+↓, F7) | §3.4: Ctrl+F9, Ctrl+Shift+B (Áreas), Alt+PgDn, Ctrl+Shift+F7/F8; toda ação com sequência por perfil ou `sem_atalho`; exceção do Ctrl+Tab declarada |
| Replay da fatia sem regra de caminho | CA-F.1 com catálogo versionado de comandos e custo conferido |
| CAs verificados antes de poderem passar | CA-4.2 e CA-4.3 por partes (1a/1b/2a/2b/A2/D1); CA-3.8 por `proximo_da_fila`; CA-3.2 (tabuleiro) no H; CA-5.3 (exportação) no J; `desde_passo` no YAML |
| Tempo na suíte rápida (CA-7.3) | `QTimer` na rápida, p99 em [desempenho] |
| Nits | leitura de diagramas pelo servidor; reinício do servidor; Box imutável a partir do 2a; medida "fora do cache" antes do E; `inclinacoes.json` por pid; tipo × função das zonas; `livro.json` como cache derivado; Ctrl+R na tabela; figurinas na Galeria; gaveta só ≥ 1600 px; CA-6.7 sintético; capturas no A2 |

## Rodada 4 (confirmação da v0.4)

| Revisor | Notas | Veredito |
|---|---|---|
| Arquitetura | (aprovado na rodada 3; as duas condições entraram na v0.4) | **Aprovado** |
| Produto e UX | 8 em todos os seis eixos | **Aprovado** |
| QA | Mensurabilidade 8 · Automação 9 · Determinismo 8 · Cobertura 8 · Gabarito 8 | **Aprovado** |

Os três ajustes de redação da confirmação de QA (invariantes "dentre os aplicáveis" no
CA-4.3; a cláusula de atalhos citados no README só a partir do A2; redundância no A2) já
estão na v0.4.

O risco que resta, nas palavras do revisor de produto, é de execução e não de spec: o teste
de atalhos (CA-3.7) tem de existir e passar já no passo 0.
