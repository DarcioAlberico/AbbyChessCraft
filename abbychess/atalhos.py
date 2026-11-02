"""Os atalhos do programa, lidos de `docs/atalhos.yaml` (a fonte única, SPEC §3.4).

Sem Qt: o teste do CA-3.7 confere a tabela antes de existir janela, e a janela (do
passo A2 em diante) registra os atalhos a partir daqui. As regras conferidas:

1. Toda ação tem sequência em cada perfil, ou está em `sem_atalho` para ele (e não
   as duas coisas).
2. Duas ações ativas no mesmo contexto não têm a mesma sequência no mesmo perfil.
3. Nenhum caractere sem Ctrl/Alt (letra, dígito, pontuação) vale num escopo editável
   nem num global: seria digitado. As teclas de edição (Space, Enter, Backspace,
   Delete) sem Ctrl/Alt também não, salvo com uma exceção declarada que diga quem
   fica com elas.
4. Nenhum Ctrl+Alt (é AltGr nos teclados ABNT2 e PT), nenhum Alt+letra (é dos
   menus), nenhum Tab sem Ctrl, nenhum Shift+F10 ou Menu (menu de contexto), nenhum
   F10 (barra de menus) nem Alt+F4 (fecha a janela).
5. Nenhum atalho encobre ou é encoberto por uma ligação nativa de widget no contexto
   dele sem uma exceção declarada; e nenhuma exceção declarada fica sem uso.

Antes das regras, a forma: cada ação tem `id`, `descricao`, `desde_passo` e um `escopo`
não vazio, e só as chaves conhecidas (um perfil escrito errado, como `finerader`, é
problema, e não uma ação que herda o padrão em silêncio).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

ARQUIVO = Path(__file__).resolve().parent.parent / "docs" / "atalhos.yaml"

MODIFICADORES = ("Ctrl", "Alt", "Shift", "Meta")
_SINONIMOS = {
    "return": "Enter", "enter": "Enter", "pgdown": "PgDn", "pagedown": "PgDn", "pgdn": "PgDn",
    "pageup": "PgUp", "pgup": "PgUp", "del": "Delete", "delete": "Delete", "escape": "Esc",
    "esc": "Esc", "space": "Space", "espaco": "Space", "backspace": "Backspace",
    "left": "Left", "right": "Right", "up": "Up", "down": "Down", "home": "Home", "end": "End",
    "tab": "Tab", "menu": "Menu", "insert": "Insert", "ins": "Insert",
    # Como o README e a SPEC escrevem: as setas e o sinal de menos tipográfico.
    "←": "Left", "→": "Right", "↑": "Up", "↓": "Down", "−": "-",
}
_TECLA_DE_FUNCAO = re.compile(r"[fF]([1-9]|1\d|2[0-4])")
_TECLAS_DE_EDICAO = {"Space", "Enter", "Backspace", "Delete"}
_CHAVES_DA_ACAO = {"id", "descricao", "escopo", "desde_passo", "sem_atalho", "excecoes"}


def _partir(sequencia: str) -> Tuple[List[str], str]:
    """`Ctrl++` → (["Ctrl"], "+"); `Ctrl+Shift+F5` → (["Ctrl", "Shift"], "F5"); sem normalizar."""
    texto = sequencia.strip()
    if texto.endswith("++"):
        resto = texto[:-2]
        return [m.strip() for m in resto.split("+") if m.strip()], "+"
    *partes, tecla = texto.split("+")
    return [m.strip() for m in partes if m.strip()], tecla.strip()


def normalizar(sequencia: str) -> str:
    """`ctrl+shift+pgdown` → `Ctrl+Shift+PgDn`: modificadores em ordem fixa, tecla canônica.

    Tecla desconhecida (`Ctrl+Foo`) ou vazia (`Ctrl+`) é erro, para uma grafia nova não
    escapar das regras por não ser igual a nenhuma outra.
    """
    partes, tecla = _partir(sequencia)
    mods = {m.capitalize() for m in partes}
    if len(mods) != len(partes):
        raise ValueError(f"modificador repetido em {sequencia!r}")
    desconhecidos = mods - set(MODIFICADORES)
    if desconhecidos:
        raise ValueError(f"modificador desconhecido em {sequencia!r}: {sorted(desconhecidos)}")
    if not tecla:
        raise ValueError(f"sequência sem tecla: {sequencia!r}")
    return "+".join([m for m in MODIFICADORES if m in mods] + [_tecla_canonica(sequencia, tecla)])


def _tecla_canonica(sequencia: str, tecla: str) -> str:
    if tecla.lower() in _SINONIMOS:
        return _SINONIMOS[tecla.lower()]
    if len(tecla) == 1 or _TECLA_DE_FUNCAO.fullmatch(tecla):
        return tecla.upper()
    raise ValueError(f"tecla desconhecida em {sequencia!r}: {tecla!r}")


def _modificadores(sequencia: str) -> Tuple[set, str]:
    partes, tecla = _partir(sequencia)
    return set(partes), tecla


@dataclass
class Excecao:
    tecla: str
    widget: str
    tipo: str
    motivo: str


@dataclass
class Acao:
    id: str
    descricao: str
    escopo: List[str]
    sequencias: Dict[str, List[str]]          # perfil -> sequências normalizadas
    sem_atalho: List[str]
    desde_passo: str
    excecoes: List[Excecao] = field(default_factory=list)
    #: Perfis com sequência própria no YAML (para reprovar sequência e `sem_atalho` juntos).
    declarados: List[str] = field(default_factory=list)
    #: O que faltou ou sobrou na forma do item do YAML (chave desconhecida, campo ausente).
    problemas_de_forma: List[str] = field(default_factory=list)


@dataclass
class Tabela:
    perfis: List[str]
    passos: List[str]
    escopos: Dict[str, dict]
    widgets_da_janela: List[str]
    nativos: Dict[str, Dict[str, List[str]]]
    acoes: List[Acao]

    def da_acao(self, id_: str) -> Acao:
        acao = next((a for a in self.acoes if a.id == id_), None)
        if acao is None:
            raise KeyError(f"não há ação {id_!r} em {ARQUIVO.name}")
        return acao

    def ativas(self, perfil: str, passo: Optional[str] = None) -> List[Tuple[Acao, List[str]]]:
        """As ações com sequência no perfil (e já registradas no `passo`, se dado)."""
        limite = self.passos.index(passo) if passo is not None else len(self.passos)
        return [(a, a.sequencias[perfil]) for a in self.acoes
                if a.sequencias.get(perfil) and a.desde_passo in self.passos
                and self.passos.index(a.desde_passo) <= limite]


def _lista(valor) -> List[str]:
    if valor is None:
        return []
    return [str(v) for v in valor] if isinstance(valor, list) else [str(valor)]


def carregar(caminho: Path = ARQUIVO) -> Tabela:
    import yaml

    bruto = yaml.safe_load(Path(caminho).read_text(encoding="utf-8"))
    perfis = list(bruto["perfis"])
    acoes = [_acao(n, item, perfis) for n, item in enumerate(bruto["acoes"])]
    return Tabela(perfis, [str(p) for p in bruto["passos"]], bruto["escopos"],
                  list(bruto["widgets_da_janela"]),
                  {w: {k: [normalizar(s) for s in v] for k, v in n.items()}
                   for w, n in bruto["nativos"].items()}, acoes)


def _acao(n: int, item: dict, perfis: List[str]) -> Acao:
    """A ação do item `n` do YAML, com o que faltou ou sobrou na forma dele."""
    forma = _problemas_de_forma(item, perfis)
    excecoes, sem_forma = _excecoes(item)
    forma += sem_forma
    sem = _lista(item.get("sem_atalho"))
    sequencias, declarados = _sequencias(item, perfis, sem)
    return Acao(
        id=str(item.get("id") or f"<ação {n + 1}>"), descricao=str(item.get("descricao", "")),
        escopo=_lista(item.get("escopo")), sequencias=sequencias, sem_atalho=sem,
        desde_passo=str(item.get("desde_passo", "")),
        excecoes=excecoes,
        declarados=declarados, problemas_de_forma=forma)


def _problemas_de_forma(item: dict, perfis: List[str]) -> List[str]:
    forma = [f"chave desconhecida {k!r}" for k in sorted(set(item) - _CHAVES_DA_ACAO
                                                         - set(perfis))]
    forma += [f"falta `{k}`" for k in ("id", "descricao", "desde_passo") if not item.get(k)]
    if not _lista(item.get("escopo")):
        forma.append("`escopo` vazio ou ausente")
    return forma


def _excecoes(item: dict) -> Tuple[List[Excecao], List[str]]:
    """As exceções declaradas e o problema de cada uma sem os quatro campos."""
    excecoes, forma = [], []
    for e in item.get("excecoes") or []:
        faltam = [k for k in ("tecla", "widget", "tipo", "motivo") if not isinstance(e, dict)
                  or k not in e]
        if faltam:
            forma.append(f"exceção sem {', '.join(faltam)}")
            continue
        excecoes.append(Excecao(normalizar(e["tecla"]), str(e["widget"]), str(e["tipo"]),
                                str(e["motivo"])))
    return excecoes, forma


def _sequencias(item: dict, perfis: List[str],
                sem: List[str]) -> Tuple[Dict[str, List[str]], List[str]]:
    """perfil -> as sequências (o primeiro perfil é o padrão dos outros), e os perfis com
    sequência própria no YAML."""
    padrao = _proprias(item, perfis[0])
    sequencias = {perfis[0]: [] if perfis[0] in sem else padrao}
    declarados = [perfis[0]] if padrao else []
    for perfil in perfis[1:]:
        proprio = _proprias(item, perfil)
        if proprio:
            declarados.append(perfil)
        sequencias[perfil] = [] if perfil in sem else (proprio or list(padrao))
    return sequencias, declarados


def _proprias(item: dict, perfil: str) -> List[str]:
    return [normalizar(s) for s in _lista(item.get(perfil))]


# ----------------------------------------------------------------------
# As regras
# ----------------------------------------------------------------------

def _ancestrais(tabela: Tabela, escopo: str) -> List[str]:
    cadeia = [escopo]
    while True:
        pai = tabela.escopos.get(cadeia[-1], {}).get("dentro_de")
        if not pai or pai in cadeia or pai not in tabela.escopos:
            return cadeia                    # ciclo e pai inexistente saem como problema
        cadeia.append(pai)


def _problemas_dos_escopos(tabela: Tabela) -> List[str]:
    problemas = []
    for nome, escopo in tabela.escopos.items():
        pai, vistos = escopo.get("dentro_de"), {nome}
        while pai:
            if pai not in tabela.escopos:
                problemas.append(f"escopo {nome}: `dentro_de` aponta para {pai!r}, que não existe")
                break
            if pai in vistos:
                problemas.append(f"escopo {nome}: ciclo em `dentro_de`")
                break
            vistos.add(pai)
            pai = tabela.escopos[pai].get("dentro_de")
    return problemas


def _sobrepoem(tabela: Tabela, a: Sequence[str], b: Sequence[str]) -> bool:
    if "global" in a or "global" in b:
        return True
    return any(set(_ancestrais(tabela, x)) & set(_ancestrais(tabela, y)) for x in a for y in b)


def _widgets(tabela: Tabela, escopos: Sequence[str]) -> List[str]:
    if "global" in escopos:
        return list(tabela.widgets_da_janela)
    vistos: List[str] = []
    for e in escopos:
        for w in tabela.escopos[e].get("widgets", []):
            if w not in vistos:
                vistos.append(w)
    return vistos


def _editavel(tabela: Tabela, escopos: Sequence[str]) -> bool:
    return "global" in escopos or any(tabela.escopos[e].get("editavel") for e in escopos)


def verificar(tabela: Tabela) -> List[str]:
    """Os problemas da tabela, em frases; lista vazia é tabela válida."""
    problemas: List[str] = _problemas_dos_escopos(tabela) + _ids_repetidos(tabela)
    for a in tabela.acoes:
        problemas.extend(_problemas_da_acao(tabela, a))
    if problemas:
        return sorted(set(problemas))

    for a in tabela.acoes:
        problemas.extend(_excecoes_sem_uso(tabela, a))
    problemas.extend(_problemas_das_teclas(tabela))
    return sorted(set(problemas))


def _ids_repetidos(tabela: Tabela) -> List[str]:
    ids = [a.id for a in tabela.acoes]
    return [f"id repetido: {repetido}" for repetido in sorted({i for i in ids if ids.count(i) > 1})]


def _problemas_da_acao(tabela: Tabela, a: Acao) -> List[str]:
    """A forma da ação, o passo, os escopos, os perfis e as exceções dela."""
    problemas = [f"{a.id}: {p}" for p in a.problemas_de_forma]
    if a.desde_passo not in tabela.passos:
        problemas.append(f"{a.id}: desde_passo {a.desde_passo!r} não é passo do roadmap")
    for e in a.escopo:
        if e not in tabela.escopos:
            problemas.append(f"{a.id}: escopo desconhecido {e!r}")
    problemas += _problemas_dos_perfis(tabela, a)
    for ex in a.excecoes:
        if ex.tipo not in ("redireciona", "substitui") or not ex.motivo.strip():
            problemas.append(f"{a.id}: exceção de {ex.tecla} sem tipo válido ou sem motivo")
    return problemas


def _problemas_dos_perfis(tabela: Tabela, a: Acao) -> List[str]:
    """Regra 1: sequência em cada perfil, ou `sem_atalho` para ele (e não as duas coisas)."""
    problemas = []
    for perfil in a.sem_atalho:
        if perfil not in tabela.perfis:
            problemas.append(f"{a.id}: perfil desconhecido em `sem_atalho`: {perfil!r}")
        elif perfil in a.declarados:
            problemas.append(f"{a.id}: perfil {perfil} em `sem_atalho` e com sequência")
    for perfil in tabela.perfis:
        if not a.sequencias.get(perfil) and perfil not in a.sem_atalho:
            problemas.append(f"{a.id}: sem sequência no perfil {perfil} e sem `sem_atalho`")
    return problemas


def _problemas_das_teclas(tabela: Tabela) -> List[str]:
    """As regras de cada sequência ativa (3 a 5) e as colisões entre elas (regra 2)."""
    problemas = []
    for perfil in tabela.perfis:
        ativas = tabela.ativas(perfil)
        for i, (a, seqs_a) in enumerate(ativas):
            for seq in seqs_a:
                problemas.extend(_regras_da_tecla(tabela, perfil, a, seq))
                for b, seqs_b in ativas[i + 1:]:
                    if seq in seqs_b and _sobrepoem(tabela, a.escopo, b.escopo):
                        problemas.append(f"[{perfil}] {seq}: {a.id} colide com {b.id}")
    return problemas


def _excecoes_sem_uso(tabela: Tabela, acao: Acao) -> List[str]:
    """Exceção que não corresponde a nada é obsoleta e esconderia um problema futuro."""
    problemas = []
    todas = {s for seqs in acao.sequencias.values() for s in seqs}
    widgets = _widgets(tabela, acao.escopo)
    for ex in acao.excecoes:
        lado = "vence" if ex.tipo == "redireciona" else "perde"
        if ex.tecla not in todas:
            problemas.append(f"{acao.id}: exceção de {ex.tecla}, que não é sequência da ação")
        elif ex.widget not in widgets:
            problemas.append(f"{acao.id}: exceção de {ex.tecla} para {ex.widget}, fora do escopo")
        elif ex.tecla not in tabela.nativos.get(ex.widget, {}).get(lado, []):
            problemas.append(f"{acao.id}: exceção `{ex.tipo}` de {ex.tecla} em {ex.widget} não "
                             f"corresponde a ligação nativa que {lado}")
    return problemas


#: Regra 4: as sequências que o Windows já usa, e o que cada uma faz.
_DO_WINDOWS = {
    "Shift+F10": "é o menu de contexto do Windows",
    "Menu": "é o menu de contexto do Windows",
    "F10": "F10 ativa a barra de menus no Windows",
    "Alt+F4": "Alt+F4 fecha a janela no Windows",
}


def _regras_da_tecla(tabela: Tabela, perfil: str, acao: Acao, seq: str) -> List[str]:
    mods, tecla = _modificadores(seq)
    rotulo = f"[{perfil}] {seq} ({acao.id})"
    declaradas = {(e.tecla, e.widget) for e in acao.excecoes}
    motivos = _do_teclado(mods, tecla)
    if seq in _DO_WINDOWS:
        motivos.append(_DO_WINDOWS[seq])
    digitada = _digitada(tabela, acao, mods, tecla, seq, declaradas)
    if digitada is not None:
        motivos.append(digitada)
    motivos += _nativas_encobertas(tabela, acao, seq, declaradas)
    return [f"{rotulo}: {motivo}" for motivo in motivos]


def _do_teclado(mods: set, tecla: str) -> List[str]:
    """Regra 4: o AltGr, os menus e o Tab."""
    motivos = []
    if {"Ctrl", "Alt"} <= mods:
        motivos.append("Ctrl+Alt é AltGr nos teclados ABNT2 e PT")
    if mods == {"Alt"} and len(tecla) == 1 and tecla.isalpha():
        motivos.append("Alt+letra é dos menus")
    if tecla == "Tab" and "Ctrl" not in mods:
        motivos.append("Tab nunca é atalho")
    return motivos


def _digitada(tabela: Tabela, acao: Acao, mods: set, tecla: str, seq: str,
              declaradas: set) -> Optional[str]:
    """Regra 3: o caractere e a tecla de edição sem Ctrl/Alt num escopo editável."""
    if mods & {"Ctrl", "Alt", "Meta"} or not _editavel(tabela, acao.escopo):
        return None
    if len(tecla) == 1:
        return "caractere sem Ctrl/Alt num escopo editável (seria digitado)"
    if tecla in _TECLAS_DE_EDICAO and not any(t == seq for t, _ in declaradas):
        return ("tecla de edição sem Ctrl/Alt num escopo editável, sem exceção que diga quem "
                "fica com ela")
    return None


def _nativas_encobertas(tabela: Tabela, acao: Acao, seq: str, declaradas: set) -> List[str]:
    """Regra 5: a ligação nativa de widget que a sequência encobre, ou que a encobre."""
    motivos = []
    for widget in _widgets(tabela, acao.escopo):
        for lado in ("vence", "perde"):
            if seq in tabela.nativos.get(widget, {}).get(lado, []) and (seq, widget) not in declaradas:
                quem = ("o widget fica com a tecla e o atalho não dispara" if lado == "vence"
                        else "o atalho apaga a ligação nativa")
                motivos.append(f"nativo de {widget} ({quem}) sem exceção declarada")
    return motivos


# ----------------------------------------------------------------------
# A documentação gerada
# ----------------------------------------------------------------------

_NOMES_DOS_PERFIS = {"padrao": "Padrão", "finereader": "FineReader"}


def markdown(tabela: Tabela) -> str:
    """`docs/ATALHOS.md`: uma tabela por escopo, com as duas colunas de perfil."""
    linhas = ["# Atalhos do AbbyChessCraft", "",
              "Gerado de `docs/atalhos.yaml` por `ferramentas/atalhos.py`; não edite à mão.", ""]
    for escopo in tabela.escopos:
        do_escopo = [a for a in tabela.acoes if a.escopo and a.escopo[0] == escopo]
        if do_escopo:
            linhas += _secao_do_escopo(tabela, escopo, do_escopo)
    return "\n".join(linhas)


def _secao_do_escopo(tabela: Tabela, escopo: str, do_escopo: List[Acao]) -> List[str]:
    linhas = [f"## {escopo}", "",
              "| Ação | " + " | ".join(_NOMES_DOS_PERFIS.get(p, p) for p in tabela.perfis)
              + " | Escopo | Desde |",
              "|---|" + "---|" * len(tabela.perfis) + "---|---|"]
    for a in sorted(do_escopo, key=lambda a: a.descricao.lower()):
        colunas = [" / ".join(a.sequencias.get(p) or []) or "—" for p in tabela.perfis]
        linhas.append(f"| {a.descricao} | " + " | ".join(colunas)
                      + f" | {', '.join(a.escopo)} | {a.desde_passo} |")
    linhas.append("")
    return linhas
