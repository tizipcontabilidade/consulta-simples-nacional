# -*- mode: python ; coding: utf-8 -*-
"""Receita do PyInstaller: gera dist/ConsultaSimplesNacional/.

    pyinstaller empacotar.spec --noconfirm

O navegador NAO e embutido: a consulta usa o Brave, Chrome ou Edge ja instalado
na maquina. O que precisa ir junto e o driver do Playwright (node.exe), por isso
o collect_all abaixo.
"""
from PyInstaller.utils.hooks import collect_all

pacotes_playwright = collect_all("playwright")

analise = Analysis(
    ["principal.py"],
    pathex=["."],
    binaries=pacotes_playwright[1],
    datas=[
        ("templates", "templates"),
        ("static", "static"),
        ("README.md", "."),
    ]
    + pacotes_playwright[0],
    hiddenimports=[
        "consultar",
        "app",
        "simplesnacional.analise",
        "simplesnacional.config",
        "simplesnacional.exportar",
        "simplesnacional.historico",
        "simplesnacional.lote",
        "simplesnacional.parser",
        "simplesnacional.scraper",
    ]
    + pacotes_playwright[2],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "PyInstaller"],
    noarchive=False,
)

pyz = PYZ(analise.pure)

# Interface web: sem janela de console. Quem encerra o sistema e a propria
# tela (botao "Encerrar" ou o simples fechar da aba).
janela = EXE(
    pyz,
    analise.scripts,
    [],
    exclude_binaries=True,
    name="ConsultaSimplesNacional",
    console=False,
    disable_windowed_traceback=False,
    icon='static/logo.ico',
)

# Linha de comando: com console, para o Agendador de Tarefas e para scripts.
terminal = EXE(
    pyz,
    analise.scripts,
    [],
    exclude_binaries=True,
    name="consultar",
    console=True,
    disable_windowed_traceback=False,
    icon='static/logo.ico',
)

COLLECT(
    janela,
    terminal,
    analise.binaries,
    analise.datas,
    strip=False,
    upx=False,
    name="ConsultaSimplesNacional",
)
