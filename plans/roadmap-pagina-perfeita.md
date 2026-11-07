# Roadmap: a página perfeita

Plano de execução da `docs/SPEC-pagina-perfeita.md`. Evidência em `docs/pesquisa/checkup-2026-11.md`. Base: `262d897`.

## Marcos, do ponto de vista de quem revisa

| Marco | O que você passa a ter | Passos | Sessões | Seu tempo |
|---|---|---|---|---|
| **M1. Não perco nada, e a janela volta como deixei** | Edição de diagrama sobrevive à troca de página; glifo aceito não muda sozinho; trecho da camada que falha não some; janela, divisores e último projeto voltam; Galeria aplica figurina; F8 não prende; Alt+3 escreve no Documento | PP0, PPE, PP1, T1 bloco 1 | 7 | Dec-1, Dec-6, Dec-7: 15 min |
| **M2. Vejo o lance errado** | Fila Lances: cada linha com lance, imagem sobre texto, Enter confere. Lance ilegal marcado, com o motivo. Lado nunca afirmado sem o livro dizer, com tecla. Relatório de lances do livro | PPL | 7 a 9 | 1 h: 8 erros do gabarito, 10 min de CA-F4.10 e 20 páginas reais |
| **M3. A tela mostra o que importa** | Capa fora da fila, com lista; □ e palavra desmentida se destacam; linha impressa não quebra a 1366 px; Imagem maior; etiqueta de progresso | PPT | 3 a 4 | 0 |
| **M4. Sei quanto vale** | Tabela por livro, em palavras. Daqui em diante, nada mais de leitura entra sem medida | PP2, PP2b; Dec-5 B | 4 a 5 | ~10 h, em pelo menos 7 dias |
| **M5. A fila encolhe** | Fila Dúvidas, com 2.ª opinião, na prosa. Consertos pequenos de leitura | PP2c, PP3, PP4, PP5 | 10 a 13 | 20 min; R-4: 1,5 h |
| **M6. Opcional, um por vez, se você pedir** | Segundo leitor pesado e aceitar em lote; legalidade com variantes e hipóteses; diagramas pelo texto; holdout da rede | Dec-2, Dec-3; PP6, PP7, PP8, PP9 | 9 a 11, fora da conta | Dec-2, Dec-3 |

**Sessão:** 1 a 2 h de agente, cerca de 4 CA, 300 a 800 linhas, medido em Q1 a Q6. Um marco com mais de 50 % além da estimativa volta ao usuário antes de seguir. Mover estrutura custa 10 vezes mais (Q7, Q8): por isso T4 não é trilha. **M1 a M5: 31 a 38 sessões. Com PP1b e as trilhas, 40 a 50, uns 60 a 100 h de agente. O calendário é decidido pelas 12 a 14 h suas e por duas esperas de 7 dias.**

**Regra.** Depois de cada marco, o programa está numa versão que você usa num livro real. Nenhum marco depende do seguinte. **M1 a M3 não pedem gabarito novo:** PP2b e CA-L9.2 leem os que já há. Só acrescentam sinal, e não trocam caractere. **A exceção é L-9:** a página classificada como imagem deixa de ser lida; por isso ela vai por último em PPT, com CA-L9.2 e a lista no fim do lote. D-3 e C-1 ficam em PP1b, logo depois de M2; se o próximo livro for um PDF digital, PP1b vem antes de PPL.

**Ordem de execução:** PP0, PPE, PP1, T1 bloco 1, PPL, PP1b, PPT, PP2, PP2b, PP2c, PP3, PP4, PP5. Fora dos marcos: T1 blocos 3 e 4, T2, T3, depois de M3, um item por vez, quando o usuário pedir.

**Por que essa ordem.**

- **O pior erro primeiro:** o lance errado sem sinal. A fila Lances, a legalidade na linha principal e o relatório de lances não usam OCR novo nem memória.
- **Marca a mais não troca letra:** por isso M2 e M3 podem vir antes da régua. O que muda a leitura vem depois de M4.
- **A 2.ª opinião é um ganho de prosa,** de gravidade baixa pela tabela de classes: faz sentido, mas não é onde o trabalho se ganha nem se perde.
- **T4 não corre em paralelo à leitura:** `leitor`, `zonas`, `pagina`, `ponte_de_leitura`, `fila_da_pagina` são tocados pelos dois. **A-2, se feito, vem antes de PP5,** e só onde PP5 precisar.

**Pontos de parada.** Só fim de M2, fim de PP2, fim de PP5 e fim de M5 voltam ao usuário; os outros se aplicam sozinhos, com registro. **Sem resposta:** o passo mescla pelos CA que o agente prova, e o plano segue. Sem a resposta de M2, PP1b e PPT seguem, e a fila Lances fica no F4, sem abrir sozinha, como já é. Sem a de M5, a fila nova fica como opção.

| Ponto | Pergunta, com número | Se não |
|---|---|---|
| Em PPL, item 4 | Teto de cobertura ≥ 30 %, sem rebobinar, por página **ou** por seguimento; alarme da legalidade < 5 % nos lances certos | Os dois tetos baixos ou alarme alto: fica a fila Lances e o F-3, sem X-1 |
| Fim de M2 | Em 20 páginas reais, a mediana é de até 2 min por página, pelo registro de eventos; **e** CA-F4.10 corrige pelo menos 80 % dos lances errados conhecidos | A fila Lances fica só com os ilegais. Sem ela, nada em M3 a M5 ataca o lance errado e legal: PP7 passa a ser a proposta seguinte |
| Fim de PP2 | Auditoria feita; **em Prosa**, a discordância por token com o Tesseract (e o PP-OCRv6, se houver venv) pega ≥ 60 %, com precisão ≥ 70 %, na validação | Rever L-2 e L-3; não começar PP5 |
| Fim de PP4 | `cobertura@3` com limite inferior ≥ 40 % | X-1 fica sem hipóteses |
| Fim de PP5 | CA-F1.1 (a), e (b) se houver prova; e erro marcado corrigido em mais de 80 % (R-4) | Fila de hoje em lance; opinião só em prosa. Se o corrigido for baixo, volta ao usuário: F-2 já está em M3, e a fila nova fica como opção |
| Fim de M5 | Em 10 páginas revisadas **antes de PP5 entrar** (o usuário as faz no fim de M4; 20 min) e 10 depois, pelo registro de eventos, os minutos por página caem pelo menos 20 % | Mesmo com CA-F1.1 aprovado, a fila nova fica como opção, não como padrão. Sem a primeira amostra, "não medido", e também como opção |
| Fim de PP7 | Em `m` = 5 % dos tokens de lance, a margem pega ≥ 50 % dos errados; cobertura ≥ 30 % | Fica a marca de ilegal |

- **Parar de crescer o gabarito:** quando o IC de CA-F1.1 já estiver todo de um lado, ou a prova, se houver, tiver 1.600 tokens de lance.
- **Parar o plano de leitura:** se dois passos seguidos não tirarem pelo menos 20 % do silencioso em Lance na validação, volta ao usuário. Com limite ≤ 1 % e `m` ≤ 15 %, na prova, o resto do plano de leitura vira opcional.

## Quando o plano acaba

- **Fim curto, o padrão (Dec-5 A):** M1, M2, M3 e PP1b mesclados, com o ponto de parada de M2 respondido, ou registrado como sem resposta. O roadmap diz "parado em M3: sem gabarito". Nada fica pendente.
- **Fim completo (Dec-5 B ou C):** M4 e M5 mesclados, com o ponto de parada de M5 respondido: a fila nova como padrão ou como opção, e a tabela por livro no registro. CA-A5 é feito aqui, e Dec-4 é perguntada com o número.
- **Não é condição de fim:** os alvos da §1 da SPEC, sem prova; M6; T1 blocos 3 e 4; T2; T3.

**Andamento.** Ao fechar um passo, abaixo do título: `**Feito** em AAAA-MM-DD, ramo pp-<id> (docs/revisoes/pp-<id>.md): <o número ou a decisão>.`

## Como reverter

Cada marco é um merge `--no-ff`: `git revert -m 1 <merge>`.

| Marco | O que fica nos projetos depois de reverter | Efeito |
|---|---|---|
| M1 | `campos_do_box` em `projeto.json`; logs | Vai a `extras`. Nada a fazer |
| M2 | `letras_das_pecas`; `lances_por_conferir` e `fortes` em `livro.json`; `revisado` em massa; `"fila": "lances"` no espaço | `extras`; a chave a mais, confirmar com teste em PPL; `revisado` continua válido, e sai da fila de hoje; o espaço cai no padrão com aviso |
| M3 | Zona `figura` nas páginas de imagem | Continuam sem leitura; mudar a função e F5 |
| M4 | Nada no projeto; o gabarito sobe de versão | Não reverter o gabarito: ele é a verdade |
| M5 | `opinioes/`, descartável | Apagar a pasta |

**Regressão num marco:** o que reprova CA-F.1 ou o golden não entra. Depois de mesclado, reverte-se primeiro e investiga-se depois.

## O contrato de cada passo

Vale o de `plans/abbychesscraft-roadmap.md` (português, UTF-8 sem BOM, LF, nunca editar o PyBoxEditor, lógica sem Qt em `abbychess/`), mais esta lista:

0. **Onde.** Integração: `passo-i-treino`, igual a `origin/main`. **O `main` local está atrasado: não partir dele.** Uma worktree só, reaproveitada: `git worktree add ..\AbbyChessCraft-pp -b pp-<id> passo-i-treino`. O venv é o da pasta principal, e tudo roda da raiz da worktree, com `PYTHONPATH` nela:
   ```
   $env:PYTHONPATH = (Get-Location).Path; $py = "C:\Python-Chess2\AbbyChessCraft\.venv\Scripts\python.exe"
   & $py -m pytest -q -n 4                         # a rápida, nunca -n auto
   & $py ferramentas\qualidade.py                  # rápida, processo, CRAP e duplicação: ~6 min
   & $py ferramentas\portao.py                     # livro_real e desempenho, arquivo por arquivo, com o vigia: ~17 min
   ```
   Merge em `passo-i-treino` com `--no-ff`, depois de ler a suíte. **Push e PR para `main` só com o sim do usuário, pedido ao fim de cada marco.** Tecla nova: acrescentar o id do passo em `passos:` de `docs/atalhos.yaml` (a ordem importa), depois a ação, depois `ferramentas/atalhos.py`.

1. **Teste que falha primeiro**, num commit próprio, pelo motivo esperado.
2. **A menor correção**, num commit que diz por quê, o que mudou e como foi provado.
3. **Medir no fim, sozinho,** com a worktree intocada e RAM livre ≥ 3 GB. Interface: suíte rápida, `ruff` e `test_atalhos`. Dado ou exportação: isso, `-m processo` e portão no fim do passo. Leitura: isso, portão e a medida da regra de "melhorou". Fim de marco: `qualidade.py`, depois o portão, em comandos separados. **No máximo um portão por passo.** Reprovar por desempenho sem a máquina livre é rerrodado uma vez, sozinho, antes de investigar: CA-7.1 passou por 20 ms em 05/11.
4. **Registro** em `docs/revisoes/pp-N.md`: ação, motivo, o que ficou.
5. **Suíte e merge em comandos separados.** Ler o resultado antes de mesclar.
6. **Experimento de leitura, a regra de "melhorou":** ajustar só no ajuste. Antes de rodar a validação, escrever no registro a métrica, a classe e o efeito mínimo. Uma mudança entra quando, nas páginas de validação, com as duas versões sobre o mesmo gabarito:
   - a redução líquida é de pelo menos **10 %** e de pelo menos **5 eventos**;
   - o IC 95 % do bootstrap pareado, reamostrando **páginas dentro de cada livro** (2.000 réplicas, semente fixa), fica inteiro do lado do ganho;
   - o registro dá **erros tirados e criados**, separados, por classe, e nenhuma classe de maior gravidade piora mais que a margem declarada;
   - nenhum livro piora mais de 1 ponto.

   Sem isso, "não entra", mesmo com o sentido certo. Com menos de 20 páginas, um teste exato de sinal por página; se ele não puder dar menos de 0,05, o registro diz "não decidível". Com Dec-5 B são 16 páginas: vale o teste de sinal, e com um mesmo sinal em menos de 13 das 16, sai "não decidível".
7. **Uma carga por vez.** Worktree própria, `-n 4` no máximo, um motor pesado por vez.

## Passo PP0 — Fechar o que está aberto (M1)

**Feito** em 2026-11-05, ramo checkup-geral (docs/revisoes/pp-0.md): Dec-6 a; a medida passa; sem push (Dec-1 em aberto).

**Contexto.** O ramo `lacunas-da-spec` tem 13 commits sem mesclar. `qualidade.py` reprova nele por duplicação. O repositório é público (Dec-1).

**Fazer.**
0. **Versionar o plano,** com o sim do usuário: spec, roadmap, `docs/pesquisa/checkup-2026-11*`, `docs/revisoes/checkup-2026-11/`, as medidas de 05/11 e os dois `.txt` de qualidade, em commit local sobre `lacunas-da-spec`. **Sem push até Dec-1.** Conferir antes que nenhum desses arquivos traga trecho de livro além de palavras soltas.
1. Versionar o vigia como `ferramentas/portao.py`, a partir de `checkup-2026-11/experimentos/portao_por_arquivo.py`. Trocar `-n auto` por `-n 4` no README.
2. `janela.py:416 exportar` e `paginas_na_janela.py:104 exportar_as_selecionadas` numa função. `_cinza` de `coordenadas.py` e `diagramas.py` em `abbychess/geometria.py`; `controlador.py:204` é método de outra coisa, e o de `padroes.py:152` só entra se for igual.
3. `qualidade.py`, sozinho; depois o portão, sozinho.
4. Dec-1 e Dec-6 ao usuário.
5. Merge em `passo-i-treino`. **Com Dec-6 b, os passos seguintes partem de `lacunas-da-spec` do mesmo jeito:** as citações `arquivo:linha` e os tetos são desse commit. Dec-6 b só adia o push.

**CA:** a medida não acusa par fora da lista. **Risco:** nenhum de dado; o par 0,88 é do fluxo de exportação, e o golden o vigia.

**Pronto quando:** a medida passa; `main` e `passo-i-treino` têm o trabalho, ou o usuário disse para esperar. Dec-1 não trava M1 a M3; M4 usa `ABBY_VERDADE` enquanto ela não vier.

**Custo:** pequeno. **Carga:** portão, 16 min, sozinho.

## Passo PPE — Abrir espaço (M1)

**Feito** em 2026-11-05, ramo pp-e (docs/revisoes/pp-e.md): a régua nova, com os tetos de hoje.

**Contexto.** As cinco classes da lista de tetos estão no limite (`VistaDoDocumento` 58, `EspacoDeTrabalho` 53, `VisorDePagina` 55, `ControladorDePagina` 61, `ProjetoDeLivro` 43), e `app/documento.py` tem 6 linhas de folga, pela conta do teste. Sem isto, o primeiro método de M1 reprova a rápida.

**Fazer, mecânico, um commit por item, com o golden como pino:**
1. **A-3:** a régua nova em `tests/test_tamanho_dos_modulos.py` e `tests/test_arquitetura.py`, sem mover método.
2. `app/documento.py`: `_escrever_as_linhas` e `_formato_novo` vão a `app/formatos_do_documento.py`.

**CA:** CA-A3. **Pronto quando:** golden e suíte iguais, e `VistaDoDocumento` aceita método novo. **Custo:** 1 sessão. **Carga:** portão uma vez, no fim. **Risco:** nenhum de dado.

## Passo PP1 — Não perder dado, não perder rastro (M1)

**Feito** em 2026-11-05, ramo pp-1 (docs/revisoes/pp-1.md): D-5 confirmado no teste, Dec-7 a pelo padrão; catraca em CER 2,76 %.

**Contexto.** Quatro falhas de dado confirmadas no código, e nenhum log em arquivo.

**Fazer, um commit por item, nesta ordem:**
0. **R-3 mínimo,** sobre o gabarito que já há: teste `livro_real` das 7 páginas, com rede carregada, `cer_corpo`, casas erradas, diagramas e linhas perdidas. É regressão: não aprova nada, por isso não pede auditoria. D-5, `letras_das_pecas` e L-9 mudam leitura antes de M4.
1. **C-2:** log em arquivo e `faulthandler`. Ajuda a diagnosticar todo o resto.
2. **C-5:** a suíte reprova erro logado. Espere vermelhos no primeiro dia: cada um é informação, e cada um vira correção ou marca. **Limite:** o que passar de 20 vermelhos ganha `erro_esperado`, com linha no registro, e vira pendência; C-5 não trava o passo.
3. **D-1:** `PaginaDeOutraVersao` e contrato de `as_state`.
4. **D-2:** tabuleiros editados sobrevivem à troca de página.
5. **D-4:** falha na camada mantém os trechos e avisa.
6. **D-5:** revisado não é relido. O teste vermelho vem primeiro: vem da leitura do código. **Dec-7 ao usuário, se o teste falhar.**

**CA:** CA-R3.1, CA-R3.2, CA-R3.3 (sem a parte por classe), CA-R3.5, CA-C2, CA-C5, CA-D1, CA-D2, CA-D4, CA-D5.

**Risco:** D-5 muda comportamento: se o usuário quiser a releitura de hoje, o Princípio 5 é reescrito, e a fila Lances não se faz.

**Pronto quando:** os CA passam, e nenhum golden muda sem motivo escrito.

**Custo:** 4 sessões. **Carga:** suíte rápida; portão no fim.

## Passo PPL — Ver o lance (M2)

**Feito** em 2026-11-05, ramo pp-l (docs/revisoes/pp-l.md): teto 32,4 %, alarme 0,3 %, X-1 marcou 0 de 107 errados. **Falta o ponto de parada, do usuário: CA-F4.8, CA-F4.10 e os 8 erros do gabarito.**

**Contexto.** O revisor confere lance no meio da prosa, em corpo 10 a 11. A faixa Linha já mostra imagem sobre texto, alinhados por glifo. Nada disso pede OCR novo nem memória. Estimativa: de 10 a 15 linhas por página, cerca de 1 min, **de 3 a 6 horas em 300 páginas, com cobertura dos lances cuja linha a leitura reconhece.** Hipótese: CA-F4.8 e CA-F4.10 podem derrubá-la.

**Fazer, nesta ordem, um commit vermelho e um verde por item:**
0. **Viabilidade, meia hora, sem commit:** abrir uma linha em `PainelDeVerificacao` com `vf.Desconhecida(palavra=<linha>, indices=<índices dela>, motivo="lance")`, e corrigir por `ControladorDeVerificacao.corrigir`. Se não servir, avisar o usuário: é uma sessão a mais. Na mesma meia hora, a 1366 px: uma linha de 70 caracteres com figurinas se lê na Linha, sem letra sobre letra? Se não, o tamanho da letra entra no item 9.
1. `abbychess/tokens.py`, sem Qt: `normalizar`, `alinhar` e `classificar_token`, com a tabela de 60 em `tests/dados/tokens_rotulados.yaml` (CA-R1.6). `Projeto.letras_das_pecas`, com o campo nas Opções, abaixo de Notação.
2. Os 8 erros do Seirawan (`docs/revisoes/checkup-2026-11/erros-do-gabarito.md`, 15 min do usuário), com `verdade_versao` subindo.
3. `abbychess/decodificador_de_lances.py`: sementes e sincronia sem rebobinar, sem interface.
4. **PP2b sobre o gabarito que já há:** `ferramentas/medir_sincronia.py`. Teto de cobertura e alarme, na linha principal. **Carga: uma leitura das 7 páginas do Seirawan e das 4 do `corpus_v2`.**
5. **F-3,** com `abbychess/evidencia.py`: `EvidenciaDaPagina` só com `{gid: (motivo, sugestão)}` e os `fortes`; PP5 acrescenta os escores.
6. **X-3.**
7. **X-1 sem hipóteses,** se o item 4 passou: tarefa leve de 500 ms, e a marca de ilegal.
8. **Registro por página.** `RegistroDeEventos` acrescenta `{"evento": "pagina", "pid": n, "fila": modo}` a cada troca de página ou de fila; sem texto de livro. `ferramentas/tempo_da_fatia.py --por-pagina` soma o tempo por `pid`. A partir daqui, o programa liga o registro por padrão em `%LOCALAPPDATA%\AbbyChessCraft\`, com a opção de desligar nas Opções: só instantes e tipos.
9. **F-4:** a fila Lances, o F4, o relatório de lances, a pergunta do Ctrl+T, `lances_por_conferir` no resumo.

**CA:** CA-R1.6, CA-F3.*, CA-X3.*, CA-X1.2, CA-X1.3, CA-X1.4, a primeira metade de CA-X1.5 (sem marca falsa), CA-X1.6, CA-F4.1, CA-F4.2, CA-F4.7a, CA-F4.8, CA-F4.9, CA-F4.10, CA-F4.11.

**Risco:** o editor Palavra foi feito para uma palavra: o item 0 o testa primeiro. Os glifos `revisado` por linha conferida saem da fila de hoje: é o desejado na fila, e ninguém mede o efeito no treino: SPEC §12. `ControladorDaFila.andar` e `_formato_do_glifo` estão em cc 9: modo e estado novos entram por tabela.

**Pronto quando:** os CA passam, salvo CA-F4.8 e CA-F4.10, que são do ponto de parada, e CA-F.1 não sobe no portão.

**Ponto de parada:** ver a tabela.

**Custo:** 7 a 9 sessões. **Carga:** suíte rápida; **portão no fim,** porque CA-X1.6 e CA-F.1 são dele; a medida em 20 páginas reais é do uso.

## Passo PP1b — Página nativa e servidor órfão

**Feito** em 2026-11-05, ramo pp-1b (docs/revisoes/pp-t.md): D-3 e C-1.

**Quando:** logo depois de M2; **antes de PPL, se o próximo livro for PDF digital.**

**Fazer:** D-3, `nativo.remendar`; C-1, `vigiar_o_pai` no começo de `_principal`, antes de carregar os modelos.

**CA:** CA-D3, CA-C1. **Risco:** D-3 é o item mais difícil: `difflib` e relatório do que não se aplica. **Pronto quando:** os CA passam, e o golden muda só com motivo. **Custo:** 2 sessões. **Carga:** portão no fim.

## Passo PPT — A tela mostra o que importa (M3)

**Feito** em 2026-11-05, ramo pp-1b (docs/revisoes/pp-t.md): só capas tratadas como imagem na varredura. **Falta CA-F2.3 e a captura de CA-U13.**

**Contexto.** A 1366 px, a linha impressa quebra e a Imagem abre em 22 %. O realce satura. A capa do Seirawan inventa 1.442 linhas. Nada aqui usa 2.ª opinião.

**Fazer, um commit vermelho e um verde por item, nesta ordem:**
1. **U-13 e U-14:** `app/documento.py`, `app/visor.py`.
2. **F-2,** com `fortes` = □ e palavra desmentida, mais os ilegais de PPL, por cima do realce de hoje.
3. **U-3:** usa `lances_por_conferir` do resumo. **U-10.**
4. **L-9,** por último: é o único item de M1 a M3 que muda o que se lê. `abbychess/tipo_de_pagina.py`, `servidor_de_leitura.ler_pagina`, `arrumacao.aplicar_lida`, a exportação e o filtro da gaveta.

**CA:** CA-U13, CA-U14, CA-F2.*, CA-F4.6, CA-U3, CA-U10, CA-L9.*.

**Risco:** L-9 pode esconder página de texto: o fim do lote lista, e Ctrl+Shift+T desfaz. `tests/verdade/xv/i000.json` é a capa e tem blocos: em CA-L9.2, "gabarito de texto" é página com pelo menos uma linha rotulada.

**Pronto quando:** os CA passam; a capa lê em menos de 5 s; o golden muda só com motivo escrito.

**Custo:** 3 a 4 sessões. **Carga:** suíte rápida; portão no fim, por L-9. CA-F2.3 e CA-U13 pedem capturas, uma vez.

## Passo PP2 — A régua (M4)

**Contexto.** Nenhuma camada reprova por OCR. A medida não diz o erro silencioso, nem o commit do core, nem o SHA do modelo. Os experimentos de 05/11 estão em scripts soltos.

**Fazer.**
0. Rodar a auditoria no `corpus_v2`. O gabarito do core não se edita: as páginas auditadas ficam em `tests/verdade/corpus_v2/`, com `origem` apontando para o core, e o que achar vai a `docs/pedidos-ao-pyboxeditor.md`.
1. `tokens.py` vem de PPL.
2. `ferramentas/medir_motores.py`, com teste, a partir de `checkup-2026-11/experimentos/`: **fazer uma unidade à mão, depois a ferramenta igualar.**
3. Ambiente completo em toda medida (CA-R1.4). Listar as fontes da base de treino da CNN: fecha "não se sabe" sobre o vazamento em figurina.
4. Ferramenta da auditoria e do sorteio (CA-R2.1, CA-R2.4, CA-R2.5). **Com o repositório público, os gabaritos novos ficam em `%LOCALAPPDATA%\AbbyChessCraft\verdade\`, pela variável `ABBY_VERDADE`, fora do git, com backup dela.** Dec-1 a volta a pô-los em `tests/verdade`.
5. Gerador G2 (CA-R2.2). Verificar dentro do programa, e a grade da dupla leitura.
6. A catraca passa a ser por classe, com `tokens.py` (CA-R3.3 e CA-R3.4).
7. Fixar a configuração do Tesseract no ajuste (`medir_motores --motor tesseract --varrer`, a primeira metade de CA-L3.1). Depois, primeira medida completa com ela, **por token e por classe, na validação;** na prova só no nível C de Dec-5.

**Decisão de entrada: Dec-5 B ou C, antes do item 1.** Sem ela, PP2 não começa, e o plano acaba em M3.

`ferramentas/conferir_core.py` compara o commit do core com o gravado na referência da medida, e o portão avisa (CA-R3.4).

**CA:** CA-R1.1 a CA-R1.5, CA-R1.7, CA-R2.*, CA-R3.3, CA-R3.4, CA-L3.1 (a primeira metade).

**Risco:** o gabarito custar mais que ~10 h: a regra de parada do Dec-5 corta.

**Pronto quando:** auditoria registrada, catraca no portão, primeira tabela na validação, alvos revistos com o usuário.

**Ponto de parada:** apresentar a tabela. Rever os alvos da §1 com o usuário.

**Custo:** 3 a 4 sessões, mais o tempo do usuário, com **pelo menos 7 dias de calendário** por causa da amostra cega. **Carga:** 2 a 3 medidas de ~10 min.

## Passo PP2b — A primeira pergunta sobre lance (M4)

**Contexto.** A métrica primária é lance. Parte desta pergunta entra em PPL, sobre o gabarito que já há; a tabela completa sai aqui, com a validação.

**Fazer, só com leitura de JSON:**
1. **Teto de cobertura:** `ferramentas/medir_sincronia.py` sobre o **texto do gabarito**, em duas versões: **sem rebobinar**, que é a de M2 e decide o ponto de parada de PPL, e **com rebobinar**, que só existe na ferramenta e decide PP7. Cada uma por página e, em 20 páginas seguidas de um livro, por seguimento.
2. **Sinal da legalidade:** na leitura do programa, que fração dos tokens errados dá ilegal ou fora de sincronia, e qual a dos certos?
3. A tabela `token de lance errado × (fila, discordância, legalidade, nenhum)`, por livro.

**Pronto quando:** a tabela está no registro, com os dois tetos e o alarme. **Custo:** uma sessão. **Carga:** uma leitura.

## Passo PP2c — T0 × T1: o efeito do treino (M5)

**Contexto.** Tudo foi medido com padrões vazios, e o treino por livro é o diferencial. Ele pode reduzir justo as confusões que a discordância pega.

**Fazer.** No Seirawan, i020 a i026, ensinando as 3 primeiras e lendo as 4 seguintes. Em outro livro, só se o usuário já tiver 5 páginas seguidas verificadas fora da validação. Reporta os quatro números e a tabela `lance errado × sinal`, em T0 e T1. Com um livro só, o registro diz "só Seirawan", e o ponto de parada vale como indício: PP5 segue, com CA-F1.1 decidindo.

**Pronto quando:** os números estão no registro, e o ponto de parada foi aplicado.

**Custo:** pequeno. **Carga:** uma medida.

## Passo PP3 — Consertos pequenos de leitura (M5)

**Contexto.** Há consertos pequenos, confirmados no código. Nenhum foi medido.

**Fazer, um por vez, antes e depois no mesmo JSON:**
1. **L-6b, L-6c, L-6d:** idioma, escala, aviso. Menor risco primeiro.
2. **L-6a:** árbitro. Com a regra de que o que o livro lê inteiro não se corta.
3. **L-5:** k-NN global. Três variantes.
4. **L-6e:** conflito.

L-9 já entrou em M3.

**CA:** CA-L6, CA-L5.*.

**Pronto quando:** cada conserto tem "entra" ou "não entra" no registro, pelo contrato, item 6.

**Risco:** cada conserto mexe em leitura que a catraca vigia. Se a catraca reprovar, o conserto volta.

**Custo:** médio. **Carga:** uma medida por item.

## Passo PP4 — Margem e cobertura (M5)

**Contexto.** A margem do k-NN é descartada, e `box.margem` já é campo gravado. Top-3 só importa se cobrir os erros: isso se mede sem mudar o programa.

**Fazer.**
0. `pagina.py`: `FonteDePaginas`, `CacheDePaginas` e geometria vão a `fonte_de_paginas.py`, com reexportação. Os `monkeypatch` em `pg.*` dos itens movidos passam ao módulo novo no mesmo commit. L-1b precisa disso: `pagina.py` está em 1.000 linhas.
1. L-1a: `ferramentas/medir_hipoteses.py`, em T0 e T1.
2. L-1b: a margem gravada. L-1c fica em PP7, se a parte a passar.

**CA:** CA-L1.*. **Pronto quando:** `cobertura@3` tem IC no registro, e CA-L1.1 e CA-L1.2 passam. **Risco:** cc e tempo do invólucro. **Custo:** 1 a 2 sessões. **Carga:** uma medida; CA-L1.2 são 5 rodadas A/B, sozinhas.

## Passo PP5 — Segunda opinião e sinal (M5)

**Contexto.** É o maior ganho medido **em prosa** e não é evidência sobre a métrica primária (relatório, §4). Não muda nenhum caractere, mas pode criar erro silencioso: CA-F1.1 vigia por classe.

**Fazer, nesta ordem:**
1. **L-3:** a segunda metade de CA-L3.1, na validação, com a configuração de PP2. Dec-2 ao usuário.
2. **A-2 só nos acessos de `ponte_de_leitura.py` e `fila_da_pagina.py` a privados do controlador.** Sem catraca do total.
3. `opiniao.py`, os escores em `EvidenciaDaPagina`, a thread e `opinioes/`, com o motor vencedor, e o extra `[opiniao-tesseract]` e `psutil` no `pyproject.toml` (E-6, CA-E6).
4. F-1: `escore.py`, e a fila Dúvidas de F-4, com a etiqueta, o Glifo e a sugestão por palavra.
5. R-4: releitura cega de 3 páginas, com o usuário, antes do ponto de parada.

**CA:** CA-L2.*, CA-L3.1, CA-F1.*, CA-F4.3, CA-F4.4, CA-F4.5, CA-F4.7b, CA-R4.1, CA-E6.

**Pronto quando:** os CA passam, R-4 feita, e o usuário respondeu aos pontos de parada de PP5 e de M5.

**Ponto de parada:** ver a tabela. Conferência à mão, numa página, com o usuário.

**Risco:** o Tesseract de página não foi medido: se perder, o motor lê por faixa, e o resto não muda. O segundo plano suja a medida: `medir` e `replay_fatia` ligam o programa sem o trabalhador.

**Custo:** grande, 5 a 6 sessões. **Carga:** uma medida por motor, sozinha.

## Passo PP6 — Aceitar em lote (M6)

De PP6 a PP9, os campos se escrevem quando o usuário pedir o passo.

**Só com Dec-2 b e Dec-3 b.** Sem o segundo leitor, este passo não existe: a sugestão por palavra já entrou em PP5.

**Fazer.** L-4: lote só 1:1, por `edicao.trocar_varios`, com prévia.

**CA:** CA-L4.*.

**Custo:** 1 sessão.

## Passo PP7 — Lances com variantes e hipóteses (M6)

**Contexto.** A fila Lances, o F-3, o X-3 e a linha principal já estão em PPL. Aqui entra o que dá margem de verdade.

**Fazer, nesta ordem:**
1. Rebobinar e variantes. 1 a 2 sessões.
2. **L-1c e X-1 com hipóteses,** se `cobertura@3` passou.

**CA:** CA-X1.1, a segunda metade de CA-X1.5 (o lance 13 fica com posição), CA-X1.7.

**Ponto de parada:** ver a tabela.

**Risco:** falsa correção; FEN errado que contamina. Por isso nada troca sozinho.

**Custo:** grande.

## Passo PP8 — Diagramas e sinais (M6)

**Fazer.** X-2 e X-4.

**CA:** CA-X2.*, CA-X4.1.

**Custo:** médio.

## Passo PP9 — O número real da rede (M6)

**Fazer.** Holdout por livro da CNN: **o número real do modelo de hoje.** Só avaliação. Se a lista das fontes (PP2, item 3) mostrar que os livros testados estão na base, vem antes de PP5.

**CA:** CA-L8.1.

## Trilha T1 — Interface

**Bloco 1 está em M1; o 2, em M3. O resto fica fora dos marcos:** depois de M3, um item por vez, quando o usuário pedir, um PR por item, com suíte rápida, e portão só onde o item mexe em leitura ou exportação.

**Fazer, nesta ordem.** Confirmar à mão primeiro o que depende de foco e teclado. **Bloco 1 pronto quando:** CA-U4, CA-U5a, CA-U8 e CA-U1a passam; 1 sessão, suíte rápida.

1. **Em M1, uma sessão:** U-4, U-8, U-5a, U-11, foco de U-1.
2. **Em M3:** progresso (U-3), U-10, U-13, U-14.
3. **Duas sessões:** indicador de foco e de modo (U-1, U-2), falha (U-6).
4. **Depois:** U-5b, U-5c, U-7, U-9.

## Trilha T2 — Confiabilidade

Fora dos marcos, como T1 fora do bloco 1. C-3 e C-4 (lote), depois C-7 e C-6: meta que oscila passa à mediana de 5 rodadas. **CA:** CA-C3, CA-C4, CA-C6, CA-C7.

## Trilha T3 — Entrega

Fora dos marcos, como T1 fora do bloco 1. E-1 (dependências, um OpenCV, YAML no pacote, lock, venv limpo), depois E-2, E-4 e E-5, independentes do resto do plano. E-6 está em PP5. **CA:** CA-E1, CA-E2, CA-E4, CA-E5.

## Trilha T4 — Arquitetura

A-3 está em PPE. A-6 ao tocar. **A-1, A-2, A-4 e A-5 não são trilha:** nada muda para quem revisa. Só ao tocar no arquivo, em janela sem passo de leitura em voo, e A-2 só onde PP5 precisar. A-7 ao tocar. **A conversão da janela em objetos, mixin por mixin, só quando uma função tocar o mixin,** começando pela Galeria.

## Antipadrões

- Olhar a lista de erros da validação ou da prova.
- Medir em gabarito não auditado e aprovar CA.
- Mover método só para passar em teto, sem a régua nova (A-3).
- Citar "99,76 %" ou "1,59 %" como se fossem do programa.
