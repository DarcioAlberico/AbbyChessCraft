# Passo PPE: abrir espaço

| Ação | Motivo | O que ficou |
|---|---|---|
| A-3: o total da MRO, os privados entre objetos, os imports tardios e o maior ciclo em `tests/test_tamanho_dos_modulos.py` | 40 métodos e 500 linhas empurravam método sem reduzir nada, e as cinco classes da lista estavam no limite | Hoje: `JanelaPrincipal` 237 (teto 275), resto até 60 (limite 85), privados 230 (teto 300), tardios 333 (teto 360), ciclo 16 (teto 16). As 1.000 linhas ficam como alarme |
| `_escrever_as_linhas` e `_formato_novo` em `app/formatos_do_documento.py` | `documento.py` tinha 6 linhas de folga | Sem mudança de comportamento |

**O número de tardios difere do relatório** (185 lá, 333 aqui): o teste conta todo `import` dentro de função, em `app/` também. O teto é sobre a conta do teste.

**A medida:** suíte rápida 2.434 passaram, 3 pulados (sem EPUBCheck, Ace e Calibre), `ruff` limpo. **O portão deste passo foi somado ao do fim de PP1:** a mudança é mecânica, e cada rodada custa 17 min.
