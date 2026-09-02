"""Infraestrutura comum dos testes.

Nenhum teste automatizado toca o portal da Receita: o navegador e substituido
por uma sessao falsa que devolve as paginas de `fixturas.py`. Os testes contra
o portal de verdade sao feitos a mao e registrados no relatorio de testes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from simplesnacional import config  # noqa: E402
from simplesnacional.scraper import RespostaBruta  # noqa: E402

from . import fixturas  # noqa: E402


class SessaoFalsa:
    """Dubla a sessao de navegador: devolve HTML pronto, sem rede."""

    def __init__(self, respostas: dict, visivel: bool = True, minimizada: bool = True,
                 ao_avisar=None):
        self.respostas = respostas
        self.visivel = visivel
        self.minimizada = minimizada
        self.ao_avisar = ao_avisar
        self.consultados = []
        self.aberta = False
        self.fechada = False

    def abrir(self):
        self.aberta = True
        return self

    def fechar(self):
        self.fechada = True

    def __enter__(self):
        return self.abrir()

    def __exit__(self, *_):
        self.fechar()

    def consultar(self, cnpj: str) -> RespostaBruta:
        self.consultados.append(cnpj)
        html = self.respostas.get(cnpj)
        if html is None:
            return RespostaBruta(cnpj=cnpj, erro="CNPJ nao previsto no teste")
        if "field-validation-error" in html:
            return RespostaBruta(cnpj=cnpj, html=html, erro="erro devolvido pelo portal")
        return RespostaBruta(cnpj=cnpj, html=html, ok=True, url=f"http://teste/{cnpj}")


RESPOSTAS_PADRAO = {
    fixturas.CNPJ_COM_EVENTOS: fixturas.OPTANTE_COM_EVENTOS,
    fixturas.CNPJ_EM_DIA: fixturas.EM_DIA,
    fixturas.CNPJ_NAO_OPTANTE: fixturas.NAO_OPTANTE,
}


@pytest.fixture
def pastas_temporarias(tmp_path, monkeypatch):
    """Isola saidas, comprovantes e historico em uma pasta descartavel."""
    for atributo, nome in (
        ("PASTA_DADOS", "."),
        ("PASTA_SAIDA", "saidas"),
        ("PASTA_COMPROVANTES", "saidas/comprovantes"),
        ("PASTA_HISTORICO", "historico"),
        ("PERFIL_NAVEGADOR", ".perfil"),
    ):
        destino = tmp_path / nome
        destino.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(config, atributo, destino)
    return tmp_path


@pytest.fixture
def sessao_falsa(monkeypatch):
    """Substitui a sessao real do scraper em todo o pacote."""
    criadas = []

    def fabricar(**kwargs):
        sessao = SessaoFalsa(RESPOSTAS_PADRAO, **kwargs)
        criadas.append(sessao)
        return sessao

    from simplesnacional import lote

    monkeypatch.setattr(lote, "Sessao", fabricar)
    monkeypatch.setattr(lote, "pausa_entre_consultas", lambda: 0.0)
    return criadas
