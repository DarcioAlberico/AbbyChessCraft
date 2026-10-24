"""Os nomes dos controles que o próprio Qt cria (SPEC §13, CA-13.1).

As docas, as barras, as abas e o campo com botão de limpar ganham botões que o Qt desenha
só com ícone e sem nome nem dica: o leitor de tela anuncia "botão" e mais nada. Eles são
reconhecidos pelo `objectName` que o Qt lhes dá (ou, o de limpar, pelo dono `QLineEdit`) e
recebem nome e dica aqui. Chamar de novo é inofensivo: o que já tem nome fica.
"""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractButton, QLineEdit

#: objectName do botão interno -> (nome, dica).
NOMES_DO_QT = {
    "qt_dockwidget_floatbutton": ("Soltar o painel",
                                  "Solta o painel da janela, ou o devolve ao lugar"),
    "qt_dockwidget_closebutton": ("Fechar o painel", "Fecha o painel (o menu Exibir o reabre)"),
    "qt_toolbar_ext_button": ("Mais ações", "As ações da barra que não couberam"),
    "qt_menubar_ext_button": ("Mais menus", "Os menus que não couberam"),
    "ScrollLeftButton": ("Abas anteriores", "Rola as abas para a esquerda"),
    "ScrollRightButton": ("Abas seguintes", "Rola as abas para a direita"),
}


def nomear_os_controles_do_qt(raiz) -> int:
    """Dá nome e dica aos botões internos do Qt dentro de `raiz`; devolve quantos."""
    feitos = 0
    for botao in raiz.findChildren(QAbstractButton):
        if botao.accessibleName() and botao.toolTip():
            continue
        par = NOMES_DO_QT.get(botao.objectName())
        if par is None and isinstance(botao.parent(), QLineEdit):
            par = ("Limpar o campo", "Apaga o que está escrito no campo")
        if par is None:
            continue
        nome, dica = par
        if not botao.accessibleName():
            botao.setAccessibleName(nome)
        if not botao.toolTip():
            botao.setToolTip(dica)
        feitos += 1
    return feitos
