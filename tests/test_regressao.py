"""Regression test: defeitos ja corridos, para nao voltarem.

Cada teste aqui nasceu de um problema real encontrado durante a construcao.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from simplesnacional import config, historico, lote, scraper
from simplesnacional.analise import EM_DIA
from simplesnacional.lote import extrair_cnpjs
from simplesnacional.parser import analisar

from . import fixturas

RAIZ = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------- R1
def test_r1_varios_cnpjs_na_mesma_linha():
    """A primeira versao do regex era gulosa e engolia a linha inteira,
    devolvendo um unico CNPJ onde havia tres."""
    texto = "12.345.678/0001-95, 00000000000191\n11.222.333/0001-81"

    assert extrair_cnpjs(texto) == ["12345678000195", "00000000000191", "11222333000181"]


def test_r1_nao_confunde_numero_longo_com_cnpj():
    assert extrair_cnpjs("123456789012345678") == []


# --------------------------------------------------------------------- R2
class PaginaFalsa:
    """Pagina de navegador simulada, so com o que o scraper usa."""

    def __init__(self, html: str, url: str = "http://teste"):
        self.html = html
        self.url = url
        self.chamadas = []

    def goto(self, endereco, **_):
        self.chamadas.append(("goto", endereco))

    def fill(self, seletor, valor):
        self.chamadas.append(("fill", seletor, valor))

    def click(self, seletor):
        self.chamadas.append(("click", seletor))

    def wait_for_function(self, expressao, **_):
        self.chamadas.append(("wait_for_function", expressao))

    def content(self):
        return self.html

    def query_selector(self, _seletor):
        return None

    def query_selector_all(self, seletor):
        if "text-danger" in seletor or "field-validation" in seletor:
            import re

            achado = re.search(r'field-validation-error">([^<]+)<', self.html)
            if achado:
                return [ElementoFalso(achado.group(1))]
        return []

    def set_default_timeout(self, _):
        pass


class ElementoFalso:
    def __init__(self, texto: str):
        self.texto = texto

    def inner_text(self):
        return self.texto

    def is_visible(self):
        return False

    def bounding_box(self):
        return None


def _sessao_com(pagina):
    sessao = scraper.Sessao(visivel=False)
    sessao._page = pagina
    return sessao


def test_r2_espera_o_captcha_antes_de_clicar(monkeypatch):
    """O portal respondia "Erro na validacao do Token" porque o clique acontecia
    antes de o widget do hCaptcha existir. A espera tem que vir antes do clique."""
    monkeypatch.setattr(scraper.time, "sleep", lambda _s: None)
    pagina = PaginaFalsa(fixturas.OPTANTE_COM_EVENTOS)

    resposta = _sessao_com(pagina).consultar(fixturas.CNPJ_COM_EVENTOS)

    assert resposta.ok
    acoes = [c[0] for c in pagina.chamadas]
    assert acoes.index("wait_for_function") < acoes.index("click")
    expressao = next(c[1] for c in pagina.chamadas if c[0] == "wait_for_function")
    assert "data-hcaptcha-widget-id" in expressao


def test_r2_recusa_de_token_e_reconhecida():
    assert scraper._e_recusa_de_token(
        "Impedido por proteção Captcha. Erro na validação do Token."
    )
    assert not scraper._e_recusa_de_token("Informe um CNPJ válido.")


def test_r2_repete_quando_o_portal_recusa_o_token(monkeypatch):
    monkeypatch.setattr(scraper.time, "sleep", lambda _s: None)
    monkeypatch.setattr(config, "TENTATIVAS", 3)
    pagina = PaginaFalsa(fixturas.CAPTCHA_RECUSADO_HTML)

    resposta = _sessao_com(pagina).consultar(fixturas.CNPJ_COM_EVENTOS)

    assert resposta.ok is False
    assert resposta.precisou_captcha is True
    assert [c[0] for c in pagina.chamadas].count("click") == 3


def test_r2_nao_repete_erro_que_nao_e_de_captcha(monkeypatch):
    monkeypatch.setattr(scraper.time, "sleep", lambda _s: None)
    pagina = PaginaFalsa(fixturas.CNPJ_INVALIDO_HTML)

    resposta = _sessao_com(pagina).consultar(fixturas.CNPJ_INVALIDO)

    assert resposta.ok is False
    assert [c[0] for c in pagina.chamadas].count("click") == 1


# --------------------------------------------------------------------- R3
def test_r3_consulta_com_erro_nao_apaga_o_retrato_anterior(pastas_temporarias):
    """Se a rodada de hoje falhar, o retrato de ontem tem que continuar valendo -
    senao a proxima rodada acusaria "mudou" sem nada ter mudado."""
    bom = analisar(fixturas.OPTANTE_COM_EVENTOS, fixturas.CNPJ_COM_EVENTOS)
    historico.registrar([{**bom.como_dicionario(), "exclusoes_futuras": [], "historico_saidas": []}])
    guardado = historico.carregar()[fixturas.CNPJ_COM_EVENTOS]

    falha = {"cnpj": fixturas.CNPJ_COM_EVENTOS, "erro": "tempo esgotado aguardando o resultado"}
    historico.registrar([falha])

    assert historico.carregar()[fixturas.CNPJ_COM_EVENTOS] == guardado


# --------------------------------------------------------------------- R4
def test_r4_historico_so_no_simei_nao_vira_historico_do_simples():
    """Quando uma das listas de "Periodos Anteriores" nao existe, o portal omite a
    tabela inteira. Mapear por posicao fazia a tabela do SIMEI ser lida como
    sendo do Simples Nacional."""
    consulta = analisar(fixturas.SO_HISTORICO_SIMEI, fixturas.CNPJ_EM_DIA)

    assert consulta.periodos_anteriores_sn == []
    assert len(consulta.periodos_anteriores_simei) == 1
    assert consulta.periodos_anteriores_simei[0].data_final == "31/12/2022"


# --------------------------------------------------------------------- R5
def test_r5_em_dia_nao_gera_comprovante(pastas_temporarias, sessao_falsa):
    execucao = lote.executar([fixturas.CNPJ_EM_DIA], visivel=False)
    item = execucao.itens[0]

    assert item.veredito.status == EM_DIA
    assert item.arquivo_comprovante == ""
    assert list(config.PASTA_COMPROVANTES.iterdir()) == []


def test_r5_ocorrencia_gera_comprovante(pastas_temporarias, sessao_falsa):
    execucao = lote.executar([fixturas.CNPJ_COM_EVENTOS], visivel=False)
    item = execucao.itens[0]

    assert item.arquivo_comprovante.endswith(f"{fixturas.CNPJ_COM_EVENTOS}.html")
    assert (config.PASTA_COMPROVANTES / item.arquivo_comprovante).is_file()


# --------------------------------------------------------------------- R6
def test_r6_estilo_do_cabecalho_nao_vaza_para_os_cartoes():
    """`header {}` sem escopo pintava de verde escuro o cabecalho de cada
    ocorrencia; `[hidden]` sem !important deixava o botao "Ver resultado" visivel."""
    css = (RAIZ / "static" / "estilo.css").read_text(encoding="utf-8")

    assert "body > header {" in css
    assert "body > footer {" in css
    assert "[hidden] { display: none !important; }" in css


# --------------------------------------------------------------------- R7
def test_r7_cnpj_invalido_nao_chega_ao_portal(pastas_temporarias, sessao_falsa):
    """Validacao local antes da rede: CNPJ com digito errado nao consome consulta -
    e, num lote so de invalidos, nem chega a abrir sessao de navegador."""
    execucao = lote.executar([fixturas.CNPJ_INVALIDO], visivel=False)

    assert sessao_falsa == []
    assert "invalido" in execucao.itens[0].consulta.erro


def test_r7_lote_misto_abre_uma_sessao_so(pastas_temporarias, sessao_falsa):
    execucao = lote.executar(
        [fixturas.CNPJ_INVALIDO, fixturas.CNPJ_EM_DIA, fixturas.CNPJ_COM_EVENTOS],
        visivel=False,
    )

    assert len(sessao_falsa) == 1, "cada CNPJ nao pode abrir um navegador novo"
    assert sessao_falsa[0].consultados == [fixturas.CNPJ_EM_DIA, fixturas.CNPJ_COM_EVENTOS]
    assert sessao_falsa[0].fechada is True
    assert len(execucao.itens) == 3


# --------------------------------------------------------------------- R8
def test_r8_cnpj_com_zero_a_esquerda_comido_pela_planilha():
    """Planilha que guarda CNPJ como numero perde o zero a esquerda e entrega 13
    digitos. Sem tratamento, o cliente sumia do lote em silencio - a pior falha
    possivel aqui."""
    assert extrair_cnpjs("1234567000195") == ["01234567000195"]
    assert extrair_cnpjs("01234567000195") == ["01234567000195"]


def test_r8_numero_de_13_digitos_sem_sentido_e_ignorado():
    """O zero a esquerda so entra se os digitos verificadores fecharem."""
    assert extrair_cnpjs("1234567890123") == []


def test_r8_nao_confunde_com_cnpj_completo_ao_lado():
    texto = "1234567000195 e 98.765.432/0001-98"
    assert extrair_cnpjs(texto) == ["01234567000195", "98765432000198"]
