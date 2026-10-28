"""Os atalhos da janela, registrados a partir de `docs/atalhos.yaml` (SPEC §3.4, CA-3.7).

Cada ação do YAML vira uma `QAction` com o nome do id (`objectName`), as sequências do perfil
e o contexto do escopo: `global` vale na janela inteira (`WindowShortcut`); os demais valem
com o foco dentro dos widgets do escopo (`WidgetWithChildrenShortcut`), que quem registra
passa. Só as ações com `desde_passo` até `PASSO` são registradas com atalho; o teste da
janela confere que o conjunto é exatamente esse.

Nos widgets em que a ligação nativa vence (o campo de um caractere do Glifo: Enter, Delete,
Shift+seta, a exceção 6 de §3.4), a tecla não dispara o atalho: chega ao `keyPressEvent`
do widget, que dispara a mesma ação (`AcoesDaTecla`).

**O perfil e as trocas (passo K, §3.4).** O perfil (`PERFIL`: "padrao" ou "finereader") e as
teclas que o usuário trocou (`trocas`, id -> sequências) são escolhidos em Opções › Teclado e
lembrados no `QSettings` (`carregar`, `gravar`). Toda troca passa pelas mesmas regras do
YAML (`problemas`: colisão no mesmo contexto, letra sem modificador em widget editável,
Ctrl+Alt, Alt+letra, encobrimento de ligação nativa) antes de valer, e `reaplicar` muda as
teclas das ações já criadas, sem reiniciar.
"""

from __future__ import annotations

import json
import logging
import re
import weakref
from dataclasses import replace
from functools import lru_cache
from typing import Dict, Iterable, List, Mapping, Optional

from PySide6.QtCore import QEvent, QKeyCombination, Qt
from PySide6.QtGui import QAction, QKeySequence

from abbychess import atalhos

log = logging.getLogger(__name__)

#: O passo do roadmap do programa: as ações do YAML até ele têm atalho.
PASSO = "L"
#: O perfil de teclado escolhido ("padrao" ou "finereader"); `definir` o troca.
PERFIL = "padrao"
#: As teclas que o usuário trocou no perfil (id -> sequências normalizadas; lista vazia tira).
trocas: Dict[str, List[str]] = {}

#: Onde o perfil e as trocas ficam no `QSettings` do aplicativo.
CHAVE_DO_PERFIL, CHAVE_DAS_TROCAS = "teclado/perfil", "teclado/trocas"

#: Grafias do YAML que o `QKeySequence` escreve de outro jeito.
_PARA_QT = {"PgDn": "PgDown", "Enter": "Return", "Delete": "Del"}


@lru_cache(maxsize=1)
def tabela() -> atalhos.Tabela:
    return atalhos.carregar()


def para_qt(sequencia: str) -> QKeySequence:
    """`Ctrl+PgDn` (normalizada) → `QKeySequence("Ctrl+PgDown")`."""
    partes, tecla = atalhos._partir(sequencia)
    return QKeySequence("+".join(partes + [_PARA_QT.get(tecla, tecla)]))


def do_qt(sequencia: QKeySequence) -> str:
    """O inverso, para comparar com o YAML: `Ctrl+PgDown` → `Ctrl+PgDn`."""
    return atalhos.normalizar(sequencia.toString(QKeySequence.SequenceFormat.PortableText))


def ativa(id_: str) -> bool:
    """A ação já tem atalho neste passo."""
    acao = tabela().da_acao(id_)
    passos = tabela().passos
    return passos.index(acao.desde_passo) <= passos.index(PASSO)


def sequencias_do_perfil(id_: str, perfil: Optional[str] = None,
                         trocas_: Optional[Mapping[str, List[str]]] = None) -> List[str]:
    """As sequências (normalizadas) da ação no perfil, com as trocas do usuário. As trocas
    guardadas são do perfil em uso: noutro perfil, só as passadas em `trocas_` valem."""
    perfil = perfil or PERFIL
    if trocas_ is None:
        trocas_ = trocas if perfil == PERFIL else {}
    if id_ in trocas_:
        return list(trocas_[id_])
    return list(tabela().da_acao(id_).sequencias.get(perfil, []))


def sequencias(id_: str) -> List[QKeySequence]:
    if not ativa(id_):
        return []
    return [para_qt(s) for s in sequencias_do_perfil(id_)]


def tecla(id_: str, sem: str = "") -> str:
    """A primeira tecla da ação no perfil de agora (para o texto da interface); sem tecla,
    `sem` (o caminho do menu, por exemplo). Um id fora do YAML levanta `KeyError`
    (`tests/test_teclado.py` confere todos os modelos de texto)."""
    teclas = sequencias_do_perfil(id_) if ativa(id_) else []
    return teclas[0] if teclas else sem


#: O `{id}` de uma ação num modelo de texto.
MARCA_DE_TECLA = re.compile(r"\{([a-z][a-z0-9_]*)\}")


def com_teclas(texto: str, so_conhecidas: bool = False) -> str:
    """O texto com cada `{id}` trocado pela tecla da ação no perfil de agora: as dicas da
    interface não citam uma tecla que o perfil (ou a troca do usuário) mudou. Com
    `so_conhecidas` (as mensagens dos controladores, que podem trazer chaves de outra coisa),
    um `{nome}` que não é ação fica como está."""
    ids = {a.id for a in tabela().acoes} if so_conhecidas else None

    def trocar(m) -> str:
        if ids is not None and m.group(1) not in ids:
            return m.group(0)
        return tecla(m.group(1), "(sem tecla)")
    return MARCA_DE_TECLA.sub(trocar, texto)


#: (id do objeto, método) -> (o objeto, fraco; o modelo): os textos que citam tecla, para
#: `reaplicar` refazer. Um objeto Qt destruído sai na próxima vez.
_textos: Dict[tuple, tuple] = {}


def texto_vivo(objeto, metodo: str, modelo: str) -> None:
    """`objeto.metodo(com_teclas(modelo))` agora e de novo a cada `reaplicar`: o texto de um
    widget (a dica, o nome acessível, o rótulo) que cita uma tecla segue o perfil e as trocas.
    Chamar de novo com o mesmo objeto e método troca o modelo."""
    _textos[(id(objeto), metodo)] = (weakref.ref(objeto), modelo)
    getattr(objeto, metodo)(com_teclas(modelo))


#: Os métodos chamados a cada `reaplicar` (fracos: não seguram o dono).
_ouvintes: List[weakref.WeakMethod] = []


def quando_mudar(metodo) -> None:
    """Chama `metodo` (um método ligado, sem argumentos) a cada `reaplicar`: para o texto
    que depende do estado do painel (o cabeçalho do editor vazio, a dica do editor ativo), que
    `texto_vivo` não pode refazer sem atropelar o estado."""
    _ouvintes.append(weakref.WeakMethod(metodo))


def _refazer_os_textos() -> None:
    for chave, (ref, modelo) in list(_textos.items()):
        objeto = ref()
        try:
            if objeto is None:                  # o objeto Python já se foi
                _textos.pop(chave, None)
            else:
                getattr(objeto, chave[1])(com_teclas(modelo))
        except RuntimeError as erro:
            if not _apagado(erro):
                raise
            _textos.pop(chave, None)
    for ref in list(_ouvintes):
        metodo = ref()
        try:
            if metodo is None:
                _ouvintes.remove(ref)
            else:
                metodo()
        except RuntimeError as erro:
            if not _apagado(erro):
                raise
            _ouvintes.remove(ref)


def _apagado(erro: RuntimeError) -> bool:
    """O erro do PySide de um objeto cujo C++ já foi destruído (a janela fechada): o do
    método chamado nele e o do sinal que ele emitiria."""
    return "already deleted" in str(erro) or "Signal source has been deleted" in str(erro)


def _dica(q: QAction) -> str:
    """A dica de uma ação do YAML: o nome e as teclas de agora."""
    nome = q.text().replace("&", "").rstrip("…")
    teclas = ", ".join(do_qt(s) for s in q.shortcuts())
    return f"{nome} ({teclas})" if teclas else nome


def dica(q: QAction, modelo: str) -> None:
    """Uma dica própria que cita teclas por `{id}` (`com_teclas`): `reaplicar` a refaz quando
    o perfil ou uma troca mudam a tecla."""
    texto_vivo(q, "setToolTip", modelo)


def tabela_com_trocas(perfil: str, trocas_: Mapping[str, List[str]]) -> atalhos.Tabela:
    """A tabela do YAML com as trocas no perfil (para conferir pelas mesmas regras)."""
    base = tabela()
    acoes = []
    for a in base.acoes:
        if a.id in trocas_:
            sequencias_ = dict(a.sequencias)
            sequencias_[perfil] = [atalhos.normalizar(s) for s in trocas_[a.id]]
            sem = ([p for p in a.sem_atalho if p != perfil] if sequencias_[perfil]
                   else sorted(set(a.sem_atalho) | {perfil}))      # tirar a tecla é declarar
            declarados = (sorted(set(a.declarados) | {perfil}) if sequencias_[perfil]
                          else [p for p in a.declarados if p != perfil])
            a = replace(a, sequencias=sequencias_, sem_atalho=sem, declarados=declarados)
        acoes.append(a)
    return replace(base, acoes=acoes)


def problemas(perfil: str, trocas_: Mapping[str, List[str]]) -> List[str]:
    """O que as trocas quebram nas regras do YAML (§3.4), só no perfil delas; vazio é ok.
    Uma sequência que não se escreve (`Ctrl+Xyz`) também é problema."""
    if perfil not in tabela().perfis:
        return [f"perfil desconhecido: {perfil!r}"]
    erros = []
    for id_, lista in trocas_.items():
        try:
            tabela().da_acao(id_)
        except KeyError:
            erros.append(f"ação desconhecida: {id_}")
            continue
        for s in lista:
            try:
                atalhos.normalizar(s)
            except ValueError as erro:
                erros.append(f"{id_}: {erro}")
    if erros:
        return erros
    marca = f"[{perfil}]"
    outros = [p for p in tabela().perfis if p != perfil]
    return [p for p in atalhos.verificar(tabela_com_trocas(perfil, trocas_))
            if not any(p.startswith(f"[{o}]") for o in outros)
            and (p.startswith(marca) or not p.startswith("["))]


def definir(perfil: str, trocas_: Optional[Mapping[str, List[str]]] = None) -> None:
    """Troca o perfil e as trocas (depois de `problemas` vazio); `reaplicar` as põe nas
    ações já criadas."""
    global PERFIL, trocas
    if perfil not in tabela().perfis:
        raise ValueError(f"perfil desconhecido: {perfil!r}")
    novas = {k: [atalhos.normalizar(s) for s in v] for k, v in (trocas_ or {}).items()}
    PERFIL, trocas = perfil, novas              # as duas juntas, ou nenhuma (ValueError acima)


def carregar(config) -> List[str]:
    """O perfil e as trocas gravados (`QSettings`). Um perfil desconhecido volta ao padrão.
    Cada troca vale sozinha: a ilegível, a de uma ação que saiu do YAML ou a que passou a
    colidir (com uma ação nova, por exemplo) fica de lado, e as outras ficam. Devolve as
    ações das trocas deixadas de lado, para a janela avisar."""
    perfil = str(config.value(CHAVE_DO_PERFIL, "padrao"))
    if perfil not in tabela().perfis:
        perfil = "padrao"
    try:
        gravadas = json.loads(config.value(CHAVE_DAS_TROCAS, "") or "{}")
    except (TypeError, ValueError):
        gravadas = {}
    if not isinstance(gravadas, dict):
        gravadas = {"(as trocas gravadas)": None}
    validas: Dict[str, List[str]] = {}
    fora = []
    for id_, lista in sorted(gravadas.items()):
        legivel = isinstance(lista, list) and all(isinstance(s, str) for s in lista)
        if legivel and not problemas(perfil, {**validas, id_: lista}):
            validas[id_] = lista
        else:
            fora.append(str(id_))
    if fora:
        log.warning("trocas de teclado deixadas de lado: %s", ", ".join(fora))
    definir(perfil, validas)
    return fora


def gravar(config) -> None:
    config.setValue(CHAVE_DO_PERFIL, PERFIL)
    config.setValue(CHAVE_DAS_TROCAS, json.dumps(trocas, ensure_ascii=False, sort_keys=True))


def reaplicar(janela) -> int:
    """As teclas do perfil de agora nas ações da janela e nos widgets que repassam teclas
    (`AcoesDaTecla`). Devolve quantas ações mudaram."""
    ids = {a.id for a in tabela().acoes}
    mudaram = 0
    for q in janela.findChildren(QAction):
        if q.objectName() in ids:
            novas = sequencias(q.objectName())
            if [do_qt(s) for s in q.shortcuts()] != [do_qt(s) for s in novas]:
                gerada = q.toolTip() == _dica(q)      # a dica era a nossa: segue a tecla
                q.setShortcuts(novas)
                if gerada:
                    q.setToolTip(_dica(q))
                mudaram += 1
    _refazer_os_textos()
    for teclas in list(_com_teclas):
        try:
            teclas.religar()
        except RuntimeError as erro:            # a ação de uma janela já fechada
            if not _apagado(erro):
                raise
            _com_teclas.discard(teclas)
    return mudaram


#: Os `AcoesDaTecla` vivos, para `reaplicar` refazer o mapa deles.
_com_teclas: "weakref.WeakSet[AcoesDaTecla]" = weakref.WeakSet()


def acao(janela, id_: str, funcao, *, texto: Optional[str] = None,
         widgets: Iterable = (), barra=None, marcavel: bool = False) -> QAction:
    """A `QAction` do id, ligada a `funcao`. `widgets`: onde vale, se o escopo não é global."""
    yaml = tabela().da_acao(id_)
    q = QAction(texto or yaml.descricao, janela)
    q.setObjectName(id_)
    q.setShortcuts(sequencias(id_))
    q.setToolTip(_dica(q))                      # quem dá outra dica a põe depois
    q.setCheckable(marcavel)
    widgets = list(widgets)
    if yaml.escopo == ["global"]:
        q.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        janela.addAction(q)
    else:
        q.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        for w in widgets:
            w.addAction(q)
    q.triggered.connect(funcao)                 # não o toggled: um setChecked não comanda
    if barra is not None:
        barra.addAction(q)
    return q


def sem_atalho(janela, texto: str, funcao) -> QAction:
    """Uma ação só de menu, fora do YAML (sem tecla)."""
    q = QAction(texto, janela)
    q.triggered.connect(funcao)
    return q


class AcoesDaTecla:
    """As teclas que um widget de ligação nativa vencedora toma para si e passa às ações:
    o `event` dele aceita o `ShortcutOverride` dessas teclas e o `keyPressEvent` as dispara."""

    def __init__(self):
        self._acoes: Dict[str, QAction] = {}
        self._ligadas: List[QAction] = []
        _com_teclas.add(self)

    def ligar(self, q: QAction) -> None:
        if q not in self._ligadas:
            self._ligadas.append(q)
        for s in q.shortcuts():
            self._acoes[do_qt(s)] = q

    def religar(self) -> None:
        """O mapa de novo, com as teclas de agora das ações ligadas (o perfil mudou)."""
        self._acoes = {}
        for q in self._ligadas:
            for s in q.shortcuts():
                self._acoes[do_qt(s)] = q

    def _da(self, evento) -> Optional[QAction]:
        """A ação da tecla do evento. O teclado numérico conta como o principal: o Enter dele
        ensina como o Return, e as setas dele movem as bordas."""
        modificadores = evento.modifiers() & ~Qt.KeyboardModifier.KeypadModifier
        tecla = Qt.Key.Key_Return if evento.key() == Qt.Key.Key_Enter else Qt.Key(evento.key())
        try:
            nome = do_qt(QKeySequence(QKeyCombination(modificadores, tecla)))
        except ValueError:                      # uma tecla sem nome (um modificador sozinho)
            return None
        return self._acoes.get(nome)

    def sobrepor(self, evento) -> bool:
        """No `event`: o `ShortcutOverride` de uma tecla nossa fica com o widget."""
        if evento.type() == QEvent.Type.ShortcutOverride and self._da(evento) is not None:
            evento.accept()
            return True
        return False

    def disparar(self, evento) -> bool:
        """No `keyPressEvent`: a tecla nossa dispara a ação (se ligada) e não segue."""
        q = self._da(evento)
        if q is None:
            return False
        if q.isEnabled():
            q.trigger()
        return True
