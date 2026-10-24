"""O replay da fatia (CA-F.1) sobre um PDF sintético de duas páginas de gabarito conhecido.

As duas páginas imprimem "abc abc abc" / "cab bca"; o gabarito diz "abcabc abc" (as duas
primeiras palavras juntas) e "cab bc" (sem o último a). Sem padrões nem rede, nenhum
glifo é lido: na primeira página o replay tem de ensinar a, b e c (a propagação resolve as
repetições) e descartar o a que sobra; ao chegar à segunda, os padrões ensinados valem
(Ctrl+R relê os pendentes) e só sobra descartar. A troca de página é navegação. No passo 0
a junção das palavras é impossível e conta pelo custo fixo do catálogo; no D1, não.

Os diagramas e as regras de divisão e junção têm testes próprios, com objetos falsos.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from abbychess import exportar as ex
from abbychess import livro as lv
from abbychess import pagina as pg
from abbychess.atalhos import carregar as carregar_atalhos
from abbychess.leitor import LeitorDoLivro
from abbychess.projeto import ProjetoDeLivro

from tests.test_treino_por_livro import _pagina_sintetica

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
import replay_fatia as rf  # noqa: E402

CATALOGO = rf.carregar_catalogo()
PASSOS = carregar_atalhos().passos
CUSTO = {c["id"]: c["custo"] for c in CATALOGO["comandos"]}
IMPOSSIVEL = {t: v["custo"] for t, v in CATALOGO["impossiveis"].items()}


def _pdf_de_duas_paginas(png: Path, destino: Path) -> Path:
    import fitz

    with fitz.open() as doc:
        for _ in range(2):
            pagina = doc.new_page(width=216, height=62)     # 900×260 px a 300 dpi
            pagina.insert_image(pagina.rect, filename=str(png))
        doc.save(str(destino))
    return destino


@pytest.fixture
def cenario(tmp_path):
    base = (tmp_path / "base").resolve()
    pdf = _pdf_de_duas_paginas(_pagina_sintetica(tmp_path / "p.png", ("abc abc abc", "cab bca")),
                               tmp_path / "fatia.pdf")
    projeto = ProjetoDeLivro.criar(base, "Fatia sintetica", pdf)
    leitor = LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)
    fonte = pg.fonte_do_projeto(projeto)
    lv.reconhecer_paginas(projeto, fonte, leitor, [0, 1])

    verdade = (tmp_path / "verdade").resolve()
    (verdade / "sint").mkdir(parents=True)
    certos = ["abcabc abc", "cab bc"]
    for indice in (0, 1):
        _, caixas, _ = rf._linhas_da_pagina(projeto.carregar_pagina(indice), fonte, indice, ex)
        gabarito = {"blocos": [], "diagramas": [], "revisado_por": "Teste", "verdade_versao": 1,
                    "linhas_corpo": [{"id": f"l{k}", "caixa_rel": caixas[k], "texto": certos[k],
                                      "texto_verificado": True} for k in range(2)]}
        if indice == 0:                     # a conferência cega de uma página da fatia
            gabarito["conferencia_cega"] = {"texto": {"aprovada": True, "verdade_versao": 1}}
        (verdade / "sint" / f"i{indice:03d}.json").write_text(json.dumps(gabarito),
                                                              encoding="utf-8")

    snapshot = tmp_path / "sint-i000-001-inicial.zip"
    with zipfile.ZipFile(snapshot, "w") as z:
        for arquivo in projeto.pasta.rglob("*"):
            if arquivo.is_file():
                z.write(arquivo, arquivo.relative_to(base).as_posix())
    return snapshot, verdade


def test_passo_0_ensina_rele_na_pagina_seguinte_e_cobra_o_espaco_impossivel(cenario):
    snapshot, verdade = cenario
    resultado = rf.replay("sint", snapshot, "0", verdade=verdade)
    primeira, segunda = resultado["paginas"]["i000"], resultado["paginas"]["i001"]
    # Sem leitura, tudo empata na fila: o glifo a corrigir é sempre o que a janela mostra.
    assert primeira["comandos"] == {"ensinar_da_fila": 3, "descartar_box": 1}
    # Os padrões da primeira página valem na segunda: Ctrl+R e nada de ensinar de novo.
    assert segunda["comandos"] == {"reler_pendentes": 1, "descartar_box": 1}
    assert resultado["gestos_navegacao"] == CUSTO["pagina_seguinte"]
    possiveis = (3 * CUSTO["ensinar_da_fila"] + 2 * CUSTO["descartar_box"]
                 + CUSTO["reler_pendentes"] + CUSTO["pagina_seguinte"])
    assert resultado["gestos_sem_impossiveis"] == possiveis
    assert resultado["impossiveis"] == {"espaco": 2}
    assert resultado["gestos"] == possiveis + 2 * IMPOSSIVEL["espaco"]
    assert resultado["estado"] == "medido"


def test_no_passo_d1_o_espaco_tem_comando(cenario):
    snapshot, verdade = cenario
    resultado = rf.replay("sint", snapshot, "D1", verdade=verdade)
    assert resultado["impossiveis"] == {}
    assert resultado["paginas"]["i000"]["comandos"]["espaco_no_documento"] == 1


def test_passo_que_so_acrescenta_comandos_nao_piora_a_medida(cenario):
    snapshot, verdade = cenario
    no_0 = rf.replay("sint", snapshot, "0", verdade=verdade)
    no_d1 = rf.replay("sint", snapshot, "D1", verdade=verdade)
    assert no_d1["paginas"]["i000"]["comandos"].get("ensinar_da_fila") == 3
    assert no_d1["gestos"] <= no_0["gestos"]
    assert rf.comparar(no_0, no_d1)["razao"] <= 1


def test_gabarito_sem_revisao_deixa_a_medida_provisoria(cenario):
    snapshot, verdade = cenario
    arquivo = verdade / "sint" / "i001.json"
    gabarito = json.loads(arquivo.read_text(encoding="utf-8"))
    gabarito["revisado_por"] = ""
    arquivo.write_text(json.dumps(gabarito), encoding="utf-8")
    resultado = rf.replay("sint", snapshot, "0", verdade=verdade)
    assert resultado["estado"] == "provisório: estrutura revisada em 1/2 páginas"
    assert resultado["gestos"] is not None


def test_sem_texto_verificado_a_medida_fica_pendente(cenario):
    snapshot, verdade = cenario
    for arquivo in (verdade / "sint").glob("i*.json"):
        gabarito = json.loads(arquivo.read_text(encoding="utf-8"))
        for linha in gabarito["linhas_corpo"]:
            linha["texto_verificado"] = False
        arquivo.write_text(json.dumps(gabarito), encoding="utf-8")
    resultado = rf.replay("sint", snapshot, "0", verdade=verdade)
    assert resultado["gestos"] is None and resultado["estado"].startswith("pendente")
    with pytest.raises(SystemExit):
        rf.comparar(resultado, resultado)


def test_comparar_recusa_medidas_que_nao_se_comparam(cenario):
    snapshot, verdade = cenario
    a = rf.replay("sint", snapshot, "0", verdade=verdade)
    with pytest.raises(SystemExit, match="conjuntos de linhas"):
        rf.comparar(a, dict(a, linhas_usadas=a["linhas_usadas"][:1]))
    with pytest.raises(SystemExit, match="catálogo"):
        rf.comparar(a, dict(a, catalogo_versao=-1))
    outros = {k: dict(v, verdade_versao=9) for k, v in a["gabaritos"].items()}
    with pytest.raises(SystemExit, match="gabaritos mudaram"):
        rf.comparar(a, dict(a, gabaritos=outros))


def test_passo_desconhecido_e_recusado():
    with pytest.raises(SystemExit, match="desconhecido"):
        rf.comandos_do_passo(CATALOGO, "Z9", PASSOS)


def test_catalogo_escolhe_o_mais_barato_do_passo():
    no_0 = rf.comandos_do_passo(CATALOGO, "0", PASSOS)
    no_d1 = rf.comandos_do_passo(CATALOGO, "D1", PASSOS)
    assert "espaco" not in no_0 and no_d1["espaco"]["id"] == "espaco_no_documento"
    assert no_0["substituicao"]["id"] == "ensinar_glifo"
    assert no_d1["substituicao"]["custo"] <= no_0["substituicao"]["custo"]


def test_todo_tipo_impossivel_tem_custo_e_motivo():
    for tipo, dados in CATALOGO["impossiveis"].items():
        assert dados["custo"] > 0 and dados["motivo"].strip(), tipo
    assert CATALOGO["convencao_de_gestos"].strip()


# ----------------------------------------------------------------------
# As diferenças de uma linha, com boxes falsos
# ----------------------------------------------------------------------

def _diferencas(lidos: str, certo: str, palavras=None):
    """Uma linha lida (um box por caractere) contra uma linha certa do gabarito."""
    boxes = [SimpleNamespace(char=c) for c in lidos]
    linha = SimpleNamespace(indices=list(range(len(boxes))))
    palavra = palavras if palavras is not None else {i: 0 for i in range(len(boxes))}
    gabarito = {"linhas_corpo": [{"caixa_rel": [0.1, 0.1, 0.9, 0.2], "texto": certo,
                                  "texto_verificado": True}]}
    return rf.diferencas(boxes, [linha], [[0.1, 0.1, 0.9, 0.2]], palavra, gabarito)


def test_um_box_com_dois_glifos_e_divisao():
    dif = _diferencas("axc", "abbc")          # o x é o "bb" colado
    assert dif.acoes == [("divisao", 1)]


def test_dois_boxes_de_um_glifo_e_juncao():
    dif = _diferencas("arnc", "amc")          # "rn" partiu o m
    assert dif.acoes == [("juncao", 1, 2)]


def test_cruz_do_rascunho_nao_e_substituicao_falsa():
    """O '✝' que a leitura dá ao sinal de mate sai como '#' em `normalizar_saida`."""
    from core.notacao import normalizar_saida

    assert normalizar_saida("✝") != "✝"
    dif = _diferencas("Qh7✝", "Qh7" + normalizar_saida("✝"))
    assert dif.acoes == [] and dif.faltas == 0


def test_espaco_errado_conta_na_fronteira():
    # Lido como uma palavra só ("abcd"); o certo é "ab cd".
    assert _diferencas("abcd", "ab cd").espacos == 1
    assert _diferencas("abcd", "ab cd", {0: 0, 1: 0, 2: 1, 3: 1}).espacos == 0


def test_linha_nao_lida_conta_os_caracteres():
    gabarito = {"linhas_corpo": [{"caixa_rel": [0.1, 0.5, 0.9, 0.6], "texto": "ab cd",
                                  "texto_verificado": True}]}
    dif = rf.diferencas([], [], [], {}, gabarito)
    assert (dif.linhas_sem_par, dif.caracteres_sem_par) == (1, 4)


# ----------------------------------------------------------------------
# Os diagramas, com um projeto e uma leitura falsos
# ----------------------------------------------------------------------

_INICIAL = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
_UMA_CASA = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR"     # e4 jogado: 2 casas mudam


def _conferir(lidos, verdade):
    """`lidos`: [(fen, lado, confiavel)], todos na mesma caixa da página 1000×1000."""
    diagramas = [SimpleNamespace(caixa=(100, 100, 500, 500), fen=f, lado=lado, confiavel=c)
                 for f, lado, c in lidos]
    projeto = SimpleNamespace(carregar_diagramas=lambda _i: diagramas)
    fonte = SimpleNamespace(inclinacao=lambda _i: 0.0)
    imagem = SimpleNamespace(width=1000, height=1000)
    gabarito = {"blocos": [{"id": "d0", "funcao": "diagrama", "caixa_rel": [0.1, 0.1, 0.5, 0.5]}],
                "diagramas": [{"id": "d0", **verdade}]}
    conta = rf._Contas(rf.comandos_do_passo(CATALOGO, "0", PASSOS), CATALOGO["impossiveis"])
    rf._replay_dos_diagramas(projeto, fonte, 0, imagem, gabarito, conta)
    return conta


def test_diagrama_certo_e_confiavel_nao_custa_nada():
    conta = _conferir([(_INICIAL, "w", True)], {"fen": _INICIAL, "lado": "w"})
    assert conta.gestos == 0 and conta.comandos == {}


def test_diagrama_sem_confianca_e_conferido_mesmo_certo():
    conta = _conferir([(_INICIAL, "w", False)], {"fen": _INICIAL, "lado": "?"})
    assert conta.comandos == {"abrir_diagrama": 1, "fechar_diagrama": 1}


def test_casas_e_lado_errados_custam_o_comando_de_cada_um():
    conta = _conferir([(_INICIAL, "w", True)], {"fen": _UMA_CASA, "lado": "b"})
    assert conta.comandos == {"abrir_diagrama": 1, "corrigir_casa": 2, "corrigir_lado": 1,
                              "fechar_diagrama": 1}
    assert conta.gestos == (CUSTO["abrir_diagrama"] + 2 * CUSTO["corrigir_casa"]
                            + CUSTO["corrigir_lado"] + CUSTO["fechar_diagrama"])


def test_lado_que_a_pagina_nao_diz_nao_e_cobrado():
    conta = _conferir([(_INICIAL, "b", True)], {"fen": _INICIAL, "lado": "?"})
    assert conta.gestos == 0


def test_diagrama_nao_achado_e_impossivel():
    conta = _conferir([], {"fen": _INICIAL, "lado": "w"})
    assert conta.impossiveis == {"diagrama_nao_achado": 1} and conta.gestos == 0
    assert conta.custo_dos_impossiveis == IMPOSSIVEL["diagrama_nao_achado"]


def _desfazer_verificacao(verdade, pagina, campo, valor):
    arquivo = verdade / "sint" / f"{pagina}.json"
    gabarito = json.loads(arquivo.read_text(encoding="utf-8"))
    campo(gabarito, valor)
    arquivo.write_text(json.dumps(gabarito), encoding="utf-8")


def test_texto_verificado_em_parte_deixa_a_medida_provisoria(cenario):
    snapshot, verdade = cenario
    _desfazer_verificacao(verdade, "i001", lambda g, v: g["linhas_corpo"][1].update(
        texto_verificado=v), False)
    resultado = rf.replay("sint", snapshot, "0", verdade=verdade)
    assert resultado["estado"] == "provisório: texto verificado em 3/4 linhas"


def test_conferencia_cega_velha_deixa_a_medida_provisoria(cenario):
    snapshot, verdade = cenario
    _desfazer_verificacao(verdade, "i000", lambda g, v: g.update(verdade_versao=v), 2)
    resultado = rf.replay("sint", snapshot, "0", verdade=verdade)
    assert resultado["estado"] == "provisório: sem conferência cega do texto aprovada e em dia"


def test_erros_iniciais_por_pagina_para_a_medida_humana(cenario):
    snapshot, verdade = cenario
    resultado = rf.replay("sint", snapshot, "0", verdade=verdade)
    # 14 glifos sem leitura que o gabarito tem, 1 a sobrar e 1 espaço errado, por página.
    assert resultado["paginas"]["i000"]["erros"] == {"texto": 16, "diagramas": 0}
    # Na segunda, o Ctrl+R corrige quase tudo, mas os erros são os do snapshot, de antes.
    assert resultado["paginas"]["i001"]["erros"] == {"texto": 16, "diagramas": 0}
    assert resultado["paginas"]["i001"]["comandos"].get("reler_pendentes") == 1


def test_glifo_fora_da_cabeca_da_fila_custa_o_clique():
    """Só o primeiro da fila sai mais barato: os outros pedem o clique no box."""
    from abbychess.projeto import Limiares

    from core.box_model import BoxEntry

    leitor = SimpleNamespace(limiares=Limiares())
    boxes = [BoxEntry("x", 10, 10, 20, 30, 0.95, "net"),         # não está na fila
             BoxEntry("", 40, 10, 50, 30, 0.0, "none")]           # o primeiro da fila
    dif = rf.Diferencas(acoes=[("substituicao", 0, "a"), ("substituicao", 1, "b")])
    disponiveis = rf.comandos_do_passo(CATALOGO, "0", PASSOS)
    assert rf._proxima_acao(dif, boxes, leitor, disponiveis) == (("substituicao", 1, "b"), True)
    dif = rf.Diferencas(acoes=[("substituicao", 0, "a")])
    assert rf._proxima_acao(dif, boxes, leitor, disponiveis) == (("substituicao", 0, "a"), False)


def _palavras(texto: str):
    """Uma linha de boxes de 10×20 px, 1 px entre letras e 12 px entre palavras."""
    from core.box_model import BoxEntry

    boxes, x = [], 40
    for c in texto:
        if c == " ":
            x += 12
            continue
        boxes.append(BoxEntry(c, x, 100, x + 10, 120, 0.99, "neural"))
        x += 11
    return boxes


class _LeitorFixo:
    """O k-NN do livro de mentira: lê todo pendente como `char` (ou não lê, com None)."""

    def __init__(self, char):
        from abbychess.projeto import Limiares

        self.char, self.limiares = char, Limiares()

    def ler_pelo_livro(self, recorte, referencia, efeito):
        return SimpleNamespace(char=self.char or "", fonte="livro", confianca=0.5, amostra=None)


def _lote(trocas, passo="L", da_fila=True, leitor=None):
    """O `_lote` do primeiro 0 de "c0l0ca b0l0s 1.e4", já ensinado como "o"."""
    from PIL import Image

    boxes = _palavras("c0l0ca b0l0s 1.e4")          # o 0 é o "o" em toda palavra
    boxes[1].char, boxes[1].source = "o", "manual"
    return rf._lote(rf.Diferencas(acoes=trocas), boxes, 1, "0", "o",
                    rf.comandos_do_passo(CATALOGO, passo, PASSOS), da_fila,
                    Image.new("L", (400, 200), 255), leitor or _LeitorFixo(None))


def test_o_lote_substitui_o_ensinar_quando_deixa_mais_glifos_certos():
    trocas = [("substituicao", i, "o") for i in (1, 3, 7, 9)]
    comando, outros = _lote(trocas)
    assert comando["id"] == "ensinar_em_lote_da_fila" and outros == [3, 7, 9]
    assert _lote(trocas, da_fila=False)[0]["id"] == "ensinar_em_lote"
    # No passo 0 não há lote; e um lote que acerta 1 e estraga 2 não é usado.
    assert _lote(trocas, passo="0") is None
    assert _lote(trocas[:2]) is None


def test_o_lote_nao_e_usado_se_a_propagacao_ja_acerta_o_mesmo():
    """O Enter simples propaga: se o padrão ensinado lê os outros 0 como "o", o lote não
    acerta nada a mais, e o replay não o cobra no lugar do ensinar."""
    trocas = [("substituicao", i, "o") for i in (1, 3, 7, 9)]
    assert _lote(trocas, leitor=_LeitorFixo("o")) is None


def test_o_lote_custa_o_mesmo_que_o_ensinar_que_ele_substitui():
    custo = {c["id"]: c["custo"] for c in CATALOGO["comandos"] if str(c["passo"]) in ("0", "L")}
    assert custo["ensinar_em_lote_da_fila"] == custo["ensinar_da_fila"]
    assert custo["ensinar_em_lote"] == custo["ensinar_glifo"]
