"""Aviso de versao nova pelos releases publicos do GitHub.

Nenhum teste aqui toca a rede: a API do GitHub e dublada, como o portal e dublado
no resto da suite. O que se verifica e a decisao do sistema diante da resposta.
"""
from __future__ import annotations

import io
import json
import urllib.error

import pytest

from simplesnacional import atualizacao
from simplesnacional.versao import VERSAO

REPO = "exemplo/repositorio"


def release(versao="9.9.9", anexos=None, **extra):
    """Resposta da API de releases, no formato que o GitHub devolve."""
    if anexos is None:
        anexos = [
            {
                "name": f"ConsultaSimplesNacional-{versao}-setup.exe",
                "browser_download_url": (
                    f"https://github.com/{REPO}/releases/download/v{versao}/"
                    f"ConsultaSimplesNacional-{versao}-setup.exe"
                ),
                "size": 54_000_000,
            }
        ]
    dados = {
        "tag_name": f"v{versao}",
        "body": "Corrige a importacao.",
        "published_at": "2026-09-02T12:00:00Z",
        "html_url": f"https://github.com/{REPO}/releases/tag/v{versao}",
        "assets": anexos,
    }
    dados.update(extra)
    return dados


@pytest.fixture
def api(monkeypatch):
    """Dubla a API. `api.resposta` define o que ela devolve nesta chamada."""

    class Api:
        resposta = None
        erro = None
        chamadas = []

    def falso_abrir(url, timeout):
        Api.chamadas.append(url)
        if Api.erro is not None:
            raise Api.erro
        corpo = json.dumps(Api.resposta).encode("utf-8")
        fluxo = io.BytesIO(corpo)
        fluxo.__enter__ = lambda: fluxo
        fluxo.__exit__ = lambda *_: None
        return fluxo

    monkeypatch.setattr(atualizacao, "_abrir", falso_abrir)
    return Api


# ------------------------------------------------------------------ deteccao
def test_avisa_quando_ha_release_mais_novo(api):
    api.resposta = release("9.9.9")

    achada = atualizacao.verificar(REPO)

    assert achada.disponivel is True
    assert achada.instalavel is True
    assert achada.versao == "9.9.9", "o 'v' da etiqueta nao entra na versao"
    assert achada.notas == "Corrige a importacao."
    assert achada.publicado_em == "2026-09-02"


def test_nao_avisa_quando_o_release_e_a_versao_instalada(api):
    api.resposta = release(VERSAO)

    assert atualizacao.verificar(REPO).disponivel is False


def test_nao_avisa_quando_o_release_e_mais_velho(api):
    api.resposta = release("0.0.1")

    assert atualizacao.verificar(REPO).disponivel is False


@pytest.mark.parametrize(
    "candidata, atual, esperado",
    [
        ("1.1.1", "1.1.0", True),
        ("1.0.10", "1.0.9", True),   # comparar como texto poria 1.0.10 antes
        ("1.10.0", "1.9.0", True),
        ("2.0", "1.9.9", True),
        ("1.1.0", "1.1.0", False),
        ("1.0.3", "1.1.0", False),
        ("", "1.1.0", False),
        ("sem numero", "1.1.0", False),
    ],
)
def test_comparacao_de_versao(candidata, atual, esperado):
    assert atualizacao.e_mais_nova(candidata, atual) is esperado


# --------------------------------------------------------------- tolerancia
# Sem internet, atras de proxy, API fora do ar: nada disso pode atrapalhar quem
# so quer consultar CNPJ.
def test_sem_internet_nao_quebra(api):
    api.erro = urllib.error.URLError("sem rede")

    achada = atualizacao.verificar(REPO)

    assert achada.disponivel is False
    assert achada.problema == ""


def test_timeout_nao_quebra(api):
    api.erro = TimeoutError()

    assert atualizacao.verificar(REPO).disponivel is False


def test_resposta_ilegivel_nao_quebra(api):
    api.resposta = "isto nao e um objeto de release"

    assert atualizacao.verificar(REPO).disponivel is False


def test_repositorio_desligado_nem_chama_a_api(api):
    assert atualizacao.verificar("").disponivel is False
    assert api.chamadas == []


def test_release_sem_instalador_avisa_o_problema(api):
    api.resposta = release("9.9.9", anexos=[])

    achada = atualizacao.verificar(REPO)

    assert achada.disponivel is True
    assert achada.instalavel is False, "sem anexo nao ha o que instalar"
    assert "nao traz o instalador" in achada.problema


def test_ignora_anexos_que_nao_sao_o_instalador(api):
    api.resposta = release(
        "9.9.9",
        anexos=[
            {"name": "codigo-fonte.zip", "browser_download_url":
             "https://github.com/x/y/releases/download/v9.9.9/codigo-fonte.zip", "size": 100},
            {"name": "ConsultaSimplesNacional-9.9.9-setup.exe", "browser_download_url":
             "https://github.com/x/y/releases/download/v9.9.9/ConsultaSimplesNacional-9.9.9-setup.exe",
             "size": 54_000_000},
        ],
    )

    assert atualizacao.verificar(REPO).url_instalador.endswith("-setup.exe")


# ---------------------------------------------------------------- seguranca
@pytest.mark.parametrize(
    "endereco",
    [
        "https://exemplo-malicioso.com/ConsultaSimplesNacional-9.9.9-setup.exe",
        "http://github.com/x/y/ConsultaSimplesNacional-9.9.9-setup.exe",   # sem TLS
        "file:///C:/Windows/System32/calc.exe",
        "",
    ],
)
def test_instalador_fora_do_github_e_recusado(api, endereco):
    """O sistema baixa e executa esse arquivo. O endereco tem de ser do GitHub."""
    api.resposta = release(
        "9.9.9",
        anexos=[{"name": "ConsultaSimplesNacional-9.9.9-setup.exe",
                 "browser_download_url": endereco, "size": 54_000_000}],
    )

    achada = atualizacao.verificar(REPO)

    assert achada.url_instalador == ""
    assert achada.instalavel is False


def test_anexo_grande_demais_e_recusado(api):
    api.resposta = release(
        "9.9.9",
        anexos=[{"name": "ConsultaSimplesNacional-9.9.9-setup.exe",
                 "browser_download_url": f"https://github.com/{REPO}/releases/download/v9/x-setup.exe",
                 "size": 10 * 1024 * 1024 * 1024}],
    )

    assert atualizacao.verificar(REPO).instalavel is False


def test_baixar_recusa_endereco_que_nao_e_do_github():
    achada = atualizacao.Atualizacao(
        versao="9.9.9", url_instalador="https://exemplo-malicioso.com/setup.exe"
    )

    assert "nao e do GitHub" in atualizacao.baixar(achada)


def test_download_truncado_e_descartado(api, monkeypatch, tmp_path):
    """Instalador pela metade nao pode ser executado."""
    api.resposta = release("9.9.9")
    achada = atualizacao.verificar(REPO)
    monkeypatch.setattr(atualizacao.tempfile, "gettempdir", lambda: str(tmp_path))

    def baixa_pela_metade(url, timeout):
        fluxo = io.BytesIO(b"apenas o comeco do arquivo")
        fluxo.__enter__ = lambda: fluxo
        fluxo.__exit__ = lambda *_: None
        return fluxo

    monkeypatch.setattr(atualizacao, "_abrir", baixa_pela_metade)

    problema = atualizacao.baixar(achada)

    assert "incompleto" in problema
    assert achada.baixado is None
    assert list(tmp_path.glob("*.exe")) == [], "o arquivo truncado tem de sumir"


# ------------------------------------------------------------- lote primeiro
def test_lote_em_andamento_vence_a_atualizacao(monkeypatch):
    """Atualizar no meio de uma consulta perderia o trabalho ja feito - que e
    exatamente o que este sistema existe para evitar."""
    import app as aplicacao
    from simplesnacional import lote

    monkeypatch.setattr(aplicacao, "_atualizacao_vista_em", 0.0)
    monkeypatch.setattr(
        aplicacao.atualizacao, "verificar", lambda *a, **k: atualizacao.Atualizacao(
            versao="9.9.9", url_instalador="https://github.com/x/y/z-setup.exe"
        )
    )

    aberturas, encerramentos = [], []
    monkeypatch.setattr(aplicacao.atualizacao, "abrir_instalador",
                        lambda a: aberturas.append(a) or "")
    monkeypatch.setattr(aplicacao, "_encerrar_processo",
                        lambda atraso=0.6: encerramentos.append(atraso))

    class ThreadViva:
        def is_alive(self):
            return True

    monkeypatch.setattr(aplicacao, "_thread", ThreadViva())
    monkeypatch.setattr(aplicacao, "_atual", lote.Execucao(cnpjs=["11222333000181"]))

    resposta = aplicacao.app.test_client().post("/atualizar")

    assert aberturas == [], "o instalador nao pode abrir durante um lote"
    assert encerramentos == [], "o sistema nao pode se encerrar durante um lote"
    assert "lote em andamento" in resposta.get_data(as_text=True).lower()
