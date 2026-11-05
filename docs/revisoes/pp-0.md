# Passo PP0: fechar o que está aberto

Base: `lacunas-da-spec` (`262d897`), ramo `checkup-geral`.

| Ação | Motivo | O que ficou |
|---|---|---|
| Plano versionado, sem push | O roadmap manda versionar; o repositório é público (Dec-1) | Nenhum trecho de livro além de palavras soltas; as capturas ficaram de fora |
| `ferramentas/portao.py` | O vigia estava em script solto | Arquivo por arquivo, cada um num processo, sob o vigia da RAM |
| README com `-n 4` | `-n auto` travou a máquina | — |
| `exportar` e `exportar_as_selecionadas` num caminho só | Par de 0,88 do dryer | `exportar` continua sem parâmetro: o PySide passaria o `checked` |
| `geometria.cinza` | Par de 1,00 do dryer | Os de `controlador.py` e `padroes.py` fazem outra coisa |

**Decisões, pelos padrões da SPEC, sem resposta do usuário:** Dec-6 a (mesclar). Dec-1 segue em aberto: nada vai para o remoto.

## A medida

- `qualidade.py`, sozinho: rápida e `processo` saída 0, cobertura 95 %, 9 funções com CRAP ≥ 10, nenhuma fora da lista; 1 par do dryer, na lista.
- Portão, em duas passagens:
  - `test_servidor` foi interrompido pelo vigia na primeira (0,68 GB livres, com outros programas abertos). Sozinho, passou: 4 de 4.
  - **`test_ca_7_1_o_indice_pela_janela_com_o_servidor` reprovou nas duas,** 2.498 ms contra o limite de 2.400 na primeira, com 3,9 GB livres antes de rodar. Passou em 05/11 com 5,49 GB livres, por 20 ms. O passo não toca no índice da busca; a meta oscila e é o C-6, fora dos marcos. **Fica registrado como não aprovado nesta máquina, nesta carga; não é regressão provada nem foi investigado.**
  - O resto: aprovado.
