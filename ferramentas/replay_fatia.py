r"""O replay da fatia (SPEC §15.4, CA-F.1): quantos gestos levam as páginas ao gabarito.

    .venv\Scripts\python.exe ferramentas\replay_fatia.py criar-snapshot --livro xv --indices 20-26
    .venv\Scripts\python.exe ferramentas\replay_fatia.py rodar --livro xv --passo 0
    .venv\Scripts\python.exe ferramentas\replay_fatia.py comparar <linha-de-base.json> <depois.json>

O **snapshot** é o projeto reconhecido (modelos globais, padrões vazios), guardado em
`tests/dados/fatia/<livro>-iAAA-BBB-inicial.zip` com o SHA-256 ao lado; toda medida parte
dele. O **replay** é uma simulação: percorre as diferenças entre a leitura e o gabarito,
na ordem de leitura, e aplica no núcleo do programa a correção de cada uma com o comando
de menor custo de `ferramentas/replay/comandos.yaml` disponível no passo (o ensinar
propaga, e a propagação pode corrigir ou estragar outras ocorrências). Os custos são
declarados no catálogo e conferidos com a interface real por `tests/test_custo_dos_comandos.py`.

As diferenças que nenhum comando do passo corrige ficam contadas como **impossíveis**, cada
uma com o custo fixo declarado no catálogo, e entram no total; o total sem elas também sai.
O critério do roadmap (≤ 85% depois do A3, ≤ 70% depois do D1) vale sobre o total `gestos`,
com os impossíveis: um passo que torna uma correção possível tem de baixar o total.

Os padrões ensinados valem para o resto da fatia, como no programa: ao chegar a uma página
depois de ter ensinado algo, o replay relê os pendentes (`reler_pendentes`, pela
propagação dos padrões do livro, que é o que a releitura muda) e cobra o comando. A
navegação (`pagina_seguinte` entre cada par de páginas) sai em `gestos_navegacao`.

Desde o catálogo 6, um passo com o ensinar em lote (Ctrl+Enter) o usa no lugar do ensinar
quando o lote da página (`contexto.lote`) deixa certos mais glifos do que o Enter simples,
com a propagação dele, deixaria (`_lote`).

Só entram as linhas de corpo com `texto_verificado: true` (o texto do gabarito é do
usuário) e os diagramas do gabarito. Sem linha verificada, o texto fica **pendente** e o
total não é número; os diagramas saem à parte (`gestos_diagramas`). O `estado` diz também
o que falta revisar nos gabaritos (FEN conferido, estrutura revisada). Duas medidas só se
comparam (`comparar`) se usaram o mesmo snapshot, o mesmo catálogo, as mesmas versões dos
gabaritos e o mesmo conjunto de linhas.

A linha de base (passo 0) é medida sempre com o código do passo 0: num worktree da tag
`passo-0` (`docs/medidas/protocolo-fatia.md`), porque o replay chama o núcleo do programa,
e o núcleo dos passos seguintes ensina e propaga de outro jeito.

Limite conhecido: um espaço errado colado a um glifo que falta ou sobra não é contado
(o par de glifos vizinhos tem de estar dos dois lados para a fronteira ser comparada).
"""

from __future__ import annotations

import argparse
import datetime
import difflib
import hashlib
import json
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "ferramentas"))

from comum import destino_da_medida, estado_do_git  # noqa: E402
from medir import casar, casas, fen_conferido_as_cegas  # noqa: E402
from rotular import PASTA_DOS_PDFS, VERDADE, _caixa_relativa, _indices, sha256_do_arquivo  # noqa: E402

FATIA = RAIZ / "tests" / "dados" / "fatia"
CATALOGO = RAIZ / "ferramentas" / "replay" / "comandos.yaml"
MEDIDAS = RAIZ / "docs" / "medidas"
SEM_LEITURA = "□"
LIMITE_DE_PASSOS = 5000


def carregar_catalogo(caminho: Path = CATALOGO) -> dict:
    import yaml

    return yaml.safe_load(caminho.read_text(encoding="utf-8"))


def comandos_do_passo(catalogo, passo: str, passos: list) -> dict:
    """{tipo de diferença: o comando mais barato disponível no passo}."""
    comandos = catalogo["comandos"] if isinstance(catalogo, dict) else catalogo
    if passo not in passos:
        raise SystemExit(f"passo {passo!r} desconhecido; os passos são {', '.join(passos)}")
    limite = passos.index(passo)
    melhor: dict = {}
    for c in comandos:
        if passos.index(str(c["passo"])) <= limite:
            atual = melhor.get(c["corrige"])
            if atual is None or c["custo"] < atual["custo"]:
                melhor[c["corrige"]] = c
    return melhor


# ----------------------------------------------------------------------
# Diferenças de uma página
# ----------------------------------------------------------------------

@dataclass
class Diferencas:
    #: Em ordem de leitura: ("substituicao", box, char) | ("sobra", box) | ("divisao", box) |
    #: ("juncao", box_a, box_b). Faltas e espaços só se contam (não há o que simular).
    acoes: list = field(default_factory=list)
    faltas: int = 0
    espacos: int = 0
    linhas_sem_par: int = 0
    #: Os caracteres (sem espaço) das linhas sem par, que custam por caractere.
    caracteres_sem_par: int = 0


def diferencas(boxes, linhas_lidas, caixas_lidas, palavra_do_box, gabarito) -> Diferencas:
    """As diferenças entre as linhas lidas e as linhas verificadas do gabarito."""
    from core.notacao import normalizar_saida

    dif = Diferencas()
    verificadas = [ln for ln in gabarito["linhas_corpo"] if ln.get("texto_verificado")]
    if not verificadas:
        return dif
    casados = {jv: ip for ip, jv in casar(caixas_lidas, [ln["caixa_rel"] for ln in verificadas])}
    for k, linha in enumerate(verificadas):
        if k not in casados:
            dif.linhas_sem_par += 1
            dif.caracteres_sem_par += sum(1 for c in linha["texto"] if not c.isspace())
            continue
        indices = list(linhas_lidas[casados[k]].indices)
        lidos = [normalizar_saida(boxes[i].char) or SEM_LEITURA for i in indices]
        certos = [c for c in linha["texto"] if not c.isspace()]
        mapa = {}                                      # posição no certo -> posição no lido
        for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, lidos, certos,
                                                          autojunk=False).get_opcodes():
            if op == "equal":
                mapa.update({b1 + t: a1 + t for t in range(a2 - a1)})
            elif a2 - a1 == 1 and b2 - b1 == 2:
                dif.acoes.append(("divisao", indices[a1]))       # um box com dois glifos
            elif a2 - a1 == 2 and b2 - b1 == 1:
                dif.acoes.append(("juncao", indices[a1], indices[a1 + 1]))
            else:
                comum = min(a2 - a1, b2 - b1)
                for t in range(comum):
                    dif.acoes.append(("substituicao", indices[a1 + t], certos[b1 + t]))
                    mapa[b1 + t] = a1 + t
                dif.acoes.extend(("sobra", i) for i in indices[a1 + comum:a2])
                dif.faltas += (b2 - b1) - comum
        palavra_certa = _palavras_por_glifo(linha["texto"])
        for b in range(1, len(certos)):
            if b in mapa and (b - 1) in mapa and mapa[b] == mapa[b - 1] + 1:
                mesma_certa = palavra_certa[b] == palavra_certa[b - 1]
                mesma_lida = (palavra_do_box.get(indices[mapa[b]])
                              == palavra_do_box.get(indices[mapa[b - 1]]))
                dif.espacos += int(mesma_certa != mesma_lida)
    return dif


def _palavras_por_glifo(texto: str):
    """Para cada caractere que não é espaço, o número da palavra a que ele pertence."""
    saida, palavra = [], 0
    for anterior, c in zip(" " + texto, texto):
        if c.isspace():
            if not anterior.isspace():
                palavra += 1
            continue
        saida.append(palavra)
    return saida


def _linhas_da_pagina(boxes, fonte, indice, ex):
    """As linhas lidas (com os boxes sem leitura dentro), as caixas relativas e a palavra
    de cada box, pelo mesmo corte em palavras que a exportação usa."""
    imagem = fonte.pagina(indice)
    altura, largura = imagem.height, imagem.width
    angulo = fonte.inclinacao(indice)
    sem_leitura = [b for b in boxes if not b.char]
    try:
        for b in sem_leitura:
            b.char = SEM_LEITURA          # sem leitura também é glifo a corrigir
        linhas = ex._linhas(boxes)
        palavra_do_box = {}
        for n, (_, grupo) in enumerate(p for linha in ex.palavras(boxes) for p in linha):
            palavra_do_box.update({i: n for i in grupo})
    finally:
        for b in sem_leitura:
            b.char = ""
    caixas = [_caixa_relativa((min(boxes[k].x1 for k in ln.indices), ln.topo,
                               max(boxes[k].x2 for k in ln.indices), ln.pe), angulo, largura, altura)
              for ln in linhas]
    return linhas, caixas, palavra_do_box


# ----------------------------------------------------------------------
# O replay
# ----------------------------------------------------------------------

class _Contas:
    def __init__(self, disponiveis: dict, impossiveis: dict):
        self.disponiveis, self.custos_impossiveis = disponiveis, impossiveis
        self.gestos = 0
        self.comandos: dict = {}
        self.impossiveis: dict = {}

    def usar(self, tipo: str, vezes: int = 1) -> bool:
        comando = self.disponiveis.get(tipo)
        if comando is None:
            self.impossiveis[tipo] = self.impossiveis.get(tipo, 0) + vezes
            return False
        self.usar_comando(comando, vezes)
        return True

    def usar_comando(self, comando: dict, vezes: int = 1) -> None:
        self.gestos += comando["custo"] * vezes
        self.comandos[comando["id"]] = self.comandos.get(comando["id"], 0) + vezes

    @property
    def custo_dos_impossiveis(self) -> int:
        return sum(self.custos_impossiveis.get(t, {}).get("custo", 0) * n
                   for t, n in self.impossiveis.items())


def replay(livro: str, snapshot: Path, passo: str, indices=None, verdade: Path = VERDADE) -> dict:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as pasta:
        return _replay(livro, snapshot, passo, indices, verdade, Path(pasta).resolve())


def _replay(livro, snapshot, passo, indices, verdade, pasta) -> dict:
    from abbychess import exportar as ex
    from abbychess import pagina as pg
    from abbychess.atalhos import carregar as carregar_atalhos
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro

    passos = carregar_atalhos().passos
    catalogo = carregar_catalogo()
    disponiveis = comandos_do_passo(catalogo, passo, passos)
    ensinar = next((c for c in catalogo["comandos"] if c["id"] == "ensinar_glifo"
                    and passos.index(str(c["passo"])) <= passos.index(passo)), None)
    with zipfile.ZipFile(snapshot) as z:
        z.extractall(pasta)
    projeto = ProjetoDeLivro.abrir(next(p.parent for p in pasta.rglob("projeto.json")))
    leitor = LeitorDoLivro(projeto.pasta_de_padroes, limiares=projeto.dados.limiares)
    fonte = pg.fonte_do_projeto(projeto)
    indices = indices or projeto.paginas_lidas()
    gabaritos = {i: json.loads((verdade / livro / f"i{i:03d}.json").read_text(encoding="utf-8"))
                 for i in indices}

    resultado = {"livro": livro, "passo": passo, "snapshot": snapshot.name,
                 "snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                 "catalogo_versao": catalogo.get("versao"),
                 "gabaritos": {f"i{i:03d}": {"verdade_versao": g.get("verdade_versao"),
                                              "sha256": sha256_do_arquivo(
                                                  verdade / livro / f"i{i:03d}.json")}
                               for i, g in gabaritos.items()},
                 "paginas": {}, "gestos_texto": 0, "gestos_diagramas": 0,
                 "gestos_navegacao": 0, "impossiveis": {}, "custo_dos_impossiveis": 0,
                 "linhas_usadas": []}
    navegacao = _Contas(disponiveis, catalogo.get("impossiveis", {}))
    ensinados: set = set()        # os padrões valem para o resto da fatia
    for posicao, indice in enumerate(indices):
        gabarito = gabaritos[indice]
        imagem = fonte.pagina(indice)
        boxes = projeto.carregar_pagina(indice) or []
        diagramas_conta = _Contas(disponiveis, catalogo.get("impossiveis", {}))
        texto_conta = _Contas(disponiveis, catalogo.get("impossiveis", {}))
        if posicao:
            navegacao.usar("trocar_pagina")
        # Os erros da página são os do snapshot, antes de qualquer correção (o reler
        # inclusive): o N da CA-F.2 não pode depender do passo nem da ordem das páginas.
        linhas, caixas, palavra = _linhas_da_pagina(boxes, fonte, indice, ex)
        inicial = diferencas(boxes, linhas, caixas, palavra, gabarito)
        erros_iniciais = (len(inicial.acoes) + inicial.faltas + inicial.espacos
                          + inicial.caracteres_sem_par)
        if ensinados and "reler" in disponiveis:
            pg.propagar_padroes(imagem, boxes, leitor)
            texto_conta.usar("reler")

        erros_diagramas = _replay_dos_diagramas(projeto, fonte, indice, imagem, gabarito,
                                                diagramas_conta)

        for _ in range(LIMITE_DE_PASSOS):
            linhas, caixas, palavra = _linhas_da_pagina(boxes, fonte, indice, ex)
            dif = diferencas(boxes, linhas, caixas, palavra, gabarito)
            acao, da_fila = _proxima_acao(dif, boxes, leitor, disponiveis)
            if acao is None:
                break
            if acao[0] == "substituicao":
                _, i, certo = acao
                if da_fila:
                    comando = disponiveis["substituicao_da_fila"]
                elif ensinar is not None and certo not in ensinados:
                    comando = ensinar
                else:
                    comando = disponiveis["substituicao"]
                if comando["id"] == "corrigir_no_documento":         # corrige sem ensinar
                    pg.confirmar(boxes, i, certo)
                    texto_conta.usar_comando(comando)
                    continue
                lida = boxes[i].char
                # O ensinar propaga depois do Enter; o lote entra antes da propagação.
                pg.ensinar(imagem, boxes, i, certo, leitor, projeto, indice, propagar=False)
                ensinados.add(certo)
                lote = _lote(dif, boxes, i, lida, certo, disponiveis, da_fila, imagem, leitor)
                if lote is not None:
                    comando, outros = lote
                    for j in outros:
                        pg.confirmar(boxes, j, certo)
                pg.propagar_padroes(imagem, boxes, leitor)
                texto_conta.usar_comando(comando)
                continue
            elif acao[0] == "sobra":
                pg.descartar(boxes, acao[1])
            elif acao[0] == "divisao":
                pg.dividir(imagem, boxes, acao[1], leitor)
            elif acao[0] == "juncao":
                pg.juntar(imagem, boxes, acao[1], acao[2], leitor)
            texto_conta.usar(acao[0])
        else:
            raise RuntimeError(f"i{indice:03d}: o replay não convergiu")

        linhas, caixas, palavra = _linhas_da_pagina(boxes, fonte, indice, ex)
        dif = diferencas(boxes, linhas, caixas, palavra, gabarito)
        if dif.faltas:
            texto_conta.usar("falta", dif.faltas)
        if dif.espacos:
            texto_conta.usar("espaco", dif.espacos)
        if dif.linhas_sem_par:
            texto_conta.usar("linha_nao_lida", dif.linhas_sem_par)
            texto_conta.usar("caractere_nao_lido", dif.caracteres_sem_par)
        if dif.acoes:
            texto_conta.usar("nao_convergiu", len(dif.acoes))

        verificadas = [ln["id"] for ln in gabarito["linhas_corpo"] if ln.get("texto_verificado")]
        resultado["linhas_usadas"].extend(f"i{indice:03d}:{v}" for v in verificadas)
        impossiveis = {**diagramas_conta.impossiveis}
        for tipo, n in texto_conta.impossiveis.items():
            impossiveis[tipo] = impossiveis.get(tipo, 0) + n
        resultado["paginas"][f"i{indice:03d}"] = {
            "gestos_texto": texto_conta.gestos, "gestos_diagramas": diagramas_conta.gestos,
            "comandos": {**diagramas_conta.comandos, **texto_conta.comandos},
            "impossiveis": impossiveis, "linhas_verificadas": len(verificadas),
            # As diferenças do snapshot contra o gabarito, antes de corrigir: o N da CA-F.2.
            "erros": {"texto": erros_iniciais, "diagramas": erros_diagramas}}
        resultado["gestos_texto"] += texto_conta.gestos
        resultado["gestos_diagramas"] += diagramas_conta.gestos
        resultado["custo_dos_impossiveis"] += (texto_conta.custo_dos_impossiveis
                                               + diagramas_conta.custo_dos_impossiveis)
        for tipo, n in impossiveis.items():
            resultado["impossiveis"][tipo] = resultado["impossiveis"].get(tipo, 0) + n

    resultado["gestos_navegacao"] = navegacao.gestos
    resultado["custo_dos_impossiveis"] += navegacao.custo_dos_impossiveis
    for tipo, n in navegacao.impossiveis.items():
        resultado["impossiveis"][tipo] = resultado["impossiveis"].get(tipo, 0) + n
    resultado["estado"] = _estado(resultado, gabaritos.values())
    if resultado["linhas_usadas"]:
        sem = (resultado["gestos_texto"] + resultado["gestos_diagramas"]
               + resultado["gestos_navegacao"])
        resultado["gestos_sem_impossiveis"] = sem
        resultado["gestos"] = sem + resultado["custo_dos_impossiveis"]
    else:
        resultado["gestos"] = resultado["gestos_sem_impossiveis"] = None
    return resultado


def _proxima_acao(dif: Diferencas, boxes, leitor, disponiveis: dict):
    """A próxima correção: a do glifo que a janela mostra (o primeiro da fila de revisão),
    se ele tem uma substituição e o passo tem o comando da fila; senão, a primeira na ordem
    de leitura. Devolve (ação, se é a da fila)."""
    from abbychess import pagina as pg

    if "substituicao_da_fila" in disponiveis:
        fila = pg.fila_de_revisao(boxes, leitor)
        if fila:
            da_fila = next((a for a in dif.acoes if a[0] == "substituicao" and a[1] == fila[0]),
                           None)
            if da_fila is not None:
                return da_fila, True
    return next((a for a in dif.acoes if a[0] in disponiveis), None), False


def _lote(dif: Diferencas, boxes, i: int, lida: str, certo: str, disponiveis: dict,
          da_fila: bool, imagem, leitor):
    """O ensinar em lote no lugar do ensinar do glifo `i` (já ensinado, sem propagar; `lida`
    é a leitura dele antes), se o passo o tem e o lote (`contexto.lote`) deixa certos mais
    glifos do lote do que o Enter simples deixaria: a propagação pelos pendentes, numa cópia,
    também pode acertá-los, de graça. Fora do lote, a propagação lê igual nos dois. O certo
    de cada glifo é o do gabarito; sem substituição a fazer, a leitura dele já está certa.
    Devolve (comando, os índices do lote) ou `None`."""
    from dataclasses import replace

    from abbychess import contexto
    from abbychess import pagina as pg

    tipo = "confusao_da_fila" if da_fila else "confusao"
    if tipo not in disponiveis or not lida or lida == certo:
        return None
    outros = contexto.lote_da_lista(boxes, {lida}, certo, fora={i})
    if not outros:
        return None
    certos = {a[1]: a[2] for a in dif.acoes if a[0] == "substituicao"}
    verdade = {j: certos.get(j, boxes[j].char) for j in outros}
    simples = [replace(b) for b in boxes]
    pg.propagar_padroes(imagem, simples, leitor)
    sem_lote = sum(1 for j in outros if simples[j].char == verdade[j])
    com_lote = sum(1 for j in outros if verdade[j] == certo)
    return (disponiveis[tipo], outros) if com_lote > sem_lote else None


def _estado(resultado: dict, gabaritos) -> str:
    """'medido', 'pendente: …' (sem texto verificado) ou 'provisório: …' (gabarito por revisar)."""
    gabaritos = list(gabaritos)
    diagramas = [d for g in gabaritos for d in g["diagramas"]]
    falta = []
    revisados = sum(1 for g in gabaritos if g.get("revisado_por"))
    if revisados < len(gabaritos):
        falta.append(f"estrutura revisada em {revisados}/{len(gabaritos)} páginas")
    conferidos = sum(1 for d in diagramas if d.get("fen_verificado"))
    if conferidos < len(diagramas):
        falta.append(f"FEN conferido em {conferidos}/{len(diagramas)} diagramas")
    linhas = sum(len(g["linhas_corpo"]) for g in gabaritos)
    if len(resultado["linhas_usadas"]) < linhas:
        falta.append(f"texto verificado em {len(resultado['linhas_usadas'])}/{linhas} linhas")
    if not any(g.get("conferencia_cega", {}).get("texto", {}).get("aprovada")
               and g["conferencia_cega"]["texto"].get("verdade_versao") == g.get("verdade_versao")
               for g in gabaritos):
        falta.append("sem conferência cega do texto aprovada e em dia")
    if diagramas and not any(fen_conferido_as_cegas(d) for d in diagramas):
        falta.append("sem conferência cega de FEN igual")
    if not resultado["linhas_usadas"]:
        falta = [f for f in falta if not f.startswith("texto verificado")]
        return "pendente: nenhuma linha com texto verificado" + "".join(f"; {f}" for f in falta)
    return "provisório: " + "; ".join(falta) if falta else "medido"


def _replay_dos_diagramas(projeto, fonte, indice, imagem, gabarito, conta: _Contas) -> int:
    """Conferir um diagrama: abrir, corrigir casas e lado, fechar. O que não merece confiança
    é conferido mesmo sem erro (o usuário tem de olhar). Devolve os erros da página: casas
    erradas, lados errados e diagramas não achados."""
    erros = 0
    diagramas = projeto.carregar_diagramas(indice)
    angulo = fonte.inclinacao(indice)
    lidos = [_caixa_relativa(d.caixa, angulo, imagem.width, imagem.height) for d in diagramas]
    blocos = [b for b in gabarito["blocos"] if b["funcao"] == "diagrama"]
    casados = {jv: ip for ip, jv in casar(lidos, [b["caixa_rel"] for b in blocos])}
    for jv, bloco in enumerate(blocos):
        verdade = next(d for d in gabarito["diagramas"] if d["id"] == bloco["id"])
        certo = casas(verdade["fen"])
        if certo is None:
            raise SystemExit(f"i{indice:03d} {bloco['id']}: FEN do gabarito malformado")
        if jv not in casados:
            conta.usar("diagrama_nao_achado")
            erros += 1
            continue
        lido = diagramas[casados[jv]]
        previsto = casas(lido.fen) or ["?"] * 64
        erradas = sum(a != b for a, b in zip(certo, previsto))
        lado_errado = verdade.get("lado") in ("w", "b") and lido.lado != verdade["lado"]
        erros += erradas + int(lado_errado)
        if erradas or lado_errado or not lido.confiavel:
            conta.usar("abrir_diagrama")
            if erradas:
                conta.usar("casa", erradas)
            if lado_errado:
                conta.usar("lado")
            conta.usar("fechar_diagrama")
    return erros


def comparar(base: dict, depois: dict) -> dict:
    """A razão de gestos entre duas medidas, recusada se não forem comparáveis."""
    if base["snapshot_sha256"] != depois["snapshot_sha256"]:
        raise SystemExit("as medidas partiram de snapshots diferentes")
    if base.get("catalogo_versao") != depois.get("catalogo_versao"):
        raise SystemExit("as medidas usaram versões diferentes do catálogo de comandos")
    if base.get("gabaritos") != depois.get("gabaritos"):
        raise SystemExit("os gabaritos mudaram entre as medidas (verdade_versao ou conteúdo): "
                         "meça a linha de base de novo, no worktree da tag passo-0")
    if sorted(base["linhas_usadas"]) != sorted(depois["linhas_usadas"]):
        raise SystemExit("as medidas usaram conjuntos de linhas verificadas diferentes")
    if base.get("gestos") is None or depois.get("gestos") is None:
        raise SystemExit("uma das medidas está pendente (sem linha verificada)")
    return {"base": base["gestos"], "depois": depois["gestos"],
            "razao": round(depois["gestos"] / base["gestos"], 4) if base["gestos"] else None}


def criar_snapshot(livro: str, pdf: Path, indices) -> Path:
    from abbychess import livro as lv
    from abbychess import pagina as pg
    from abbychess.leitor import LeitorDoLivro
    from abbychess.projeto import ProjetoDeLivro

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporaria:
        base = Path(temporaria).resolve()
        projeto = ProjetoDeLivro.criar(base, f"fatia-{livro}", pdf)
        leitor = LeitorDoLivro.com_modelos_globais(projeto.pasta_de_padroes,
                                                   limiares=projeto.dados.limiares)
        lv.reconhecer_paginas(projeto, pg.fonte_do_projeto(projeto), leitor, indices)
        FATIA.mkdir(parents=True, exist_ok=True)
        destino = FATIA / f"{livro}-i{min(indices):03d}-{max(indices):03d}-inicial.zip"
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
            for arquivo in sorted(projeto.pasta.rglob("*")):
                if arquivo.is_file():
                    info = zipfile.ZipInfo(arquivo.relative_to(base).as_posix(), (2026, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    z.writestr(info, arquivo.read_bytes())
    destino.with_suffix(".sha256").write_text(
        hashlib.sha256(destino.read_bytes()).hexdigest() + "\n", encoding="utf-8", newline="\n")
    return destino


def main(argv=None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = analisador.add_subparsers(dest="comando", required=True)
    s = sub.add_parser("criar-snapshot")
    s.add_argument("--livro", required=True)
    s.add_argument("--indices", required=True)
    s.add_argument("--pdf", type=Path)
    r = sub.add_parser("rodar")
    r.add_argument("--livro", required=True)
    r.add_argument("--passo", required=True)
    r.add_argument("--snapshot", type=Path)
    c = sub.add_parser("comparar")
    c.add_argument("base", type=Path)
    c.add_argument("depois", type=Path)
    args = analisador.parse_args(argv)
    if args.comando == "criar-snapshot":
        indices = _indices(args.indices)
        g = json.loads((VERDADE / args.livro / f"i{indices[0]:03d}.json").read_text(encoding="utf-8"))
        pdf = args.pdf or next(PASTA_DOS_PDFS.rglob(g["pdf"]), None)
        if pdf is None:
            raise SystemExit(f"o PDF {g['pdf']!r} não está em {PASTA_DOS_PDFS}; passe --pdf "
                             "ou defina ABBY_PASTA_DOS_PDFS")
        print(criar_snapshot(args.livro, pdf, indices).relative_to(RAIZ))
        return 0
    if args.comando == "comparar":
        base, depois = (json.loads(p.read_text(encoding="utf-8")) for p in (args.base, args.depois))
        print(json.dumps(comparar(base, depois), ensure_ascii=False))
        return 0
    candidatos = sorted(FATIA.glob(f"{args.livro}-*-inicial.zip"))
    snapshot = args.snapshot or (candidatos[-1] if candidatos else None)
    if snapshot is None:
        raise SystemExit(f"não há snapshot de {args.livro}; rode criar-snapshot")
    esperado = snapshot.with_suffix(".sha256").read_text(encoding="utf-8").strip()
    if hashlib.sha256(snapshot.read_bytes()).hexdigest() != esperado:
        raise SystemExit(f"{snapshot.name}: SHA-256 não confere com {snapshot.with_suffix('.sha256').name}")
    resultado = replay(args.livro, snapshot, args.passo)
    resultado["data"] = datetime.date.today().isoformat()
    resultado.update(estado_do_git())
    MEDIDAS.mkdir(parents=True, exist_ok=True)
    destino = destino_da_medida(resultado["data"], f"fatia-{args.livro}-passo-{args.passo}")
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
    print(json.dumps({k: resultado[k] for k in ("estado", "gestos", "gestos_diagramas",
                                                "gestos_navegacao", "impossiveis")},
                     ensure_ascii=False, indent=1))
    print(destino.relative_to(RAIZ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
