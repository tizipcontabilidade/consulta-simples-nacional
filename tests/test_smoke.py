"""Smoke test: o sistema sobe e as pecas basicas respondem.

Se algum destes falhar, nao vale a pena rodar o resto.
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent

MODULOS = [
    "simplesnacional.config",
    "simplesnacional.scraper",
    "simplesnacional.parser",
    "simplesnacional.analise",
    "simplesnacional.historico",
    "simplesnacional.lote",
    "simplesnacional.exportar",
    "app",
    "consultar",
    "principal",
]


@pytest.mark.parametrize("nome", MODULOS)
def test_modulo_importa(nome):
    assert importlib.import_module(nome) is not None


def test_navegador_encontrado():
    from simplesnacional import config

    assert config.detectar_navegador(), "nenhum Chromium encontrado nesta maquina"


def test_aplicacao_flask_sobe():
    from app import app

    assert app.name == "app"
    assert Path(app.template_folder).is_dir()
    assert Path(app.static_folder).is_dir()


@pytest.mark.parametrize(
    "rota,esperado",
    [("/", 200), ("/andamento", 302), ("/resultado", 302), ("/api/estado", 200)],
)
def test_rotas_respondem(rota, esperado):
    from app import app

    with app.test_client() as cliente:
        assert cliente.get(rota).status_code == esperado


def test_tela_inicial_tem_formulario_e_botao_encerrar():
    from app import app

    with app.test_client() as cliente:
        pagina = cliente.get("/").get_data(as_text=True)
    assert 'name="cnpjs"' in pagina
    assert "Encerrar" in pagina
    assert "/sinal" in pagina, "faltou o sinal de vida da interface"


def test_arquivos_de_projeto_presentes():
    for nome in (
        "README.md",
        "LICENSE",
        "CHANGELOG.md",
        "requirements.txt",
        "empacotar.spec",
        "instalador.iss",
        "agendar.ps1",
        "construir.ps1",
    ):
        assert (RAIZ / nome).is_file(), f"faltando {nome}"


def test_versao_do_instalador_bate_com_o_changelog():
    iss = (RAIZ / "instalador.iss").read_text(encoding="utf-8")
    changelog = (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8")
    versao_iss = re.search(r'#define Versao "([\d.]+)"', iss).group(1)
    versao_log = re.search(r"## \[([\d.]+)\]", changelog).group(1)
    assert versao_iss == versao_log
