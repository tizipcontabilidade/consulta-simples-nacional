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

    def is_closed(self):
        return False

    def bring_to_front(self):
        self.chamadas.append(("bring_to_front",))


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


# --------------------------------------------------------------------- R9
# Lote de 110 CNPJs chegando com 106 consultados, sem nenhum aviso na tela.
# A causa era o regex de importacao: ele so reconhecia a mascara oficial do
# CNPJ, e toda entrada com mascara diferente sumia calada.
# CNPJ valido, mas com a pontuacao fora do lugar: o regex antigo so aceitava a
# mascara oficial e engolia entradas assim.
_MASCARA_TORTA = "12.345.678.0001-95"


def test_r9_entrada_com_mascara_estranha_nao_some_calada():
    leitura = lote.ler(_MASCARA_TORTA)

    assert leitura.total_lido == 1, "a entrada tem de ser contada de algum lado"
    assert leitura.cnpjs == ["12345678000195"]


def test_r9_conta_de_entrada_bate_com_a_de_saida():
    """A regra que fecha o buraco: nada entra sem sair contado."""
    texto = "\n".join(
        [
            "12.345.678/0001-95",
            _MASCARA_TORTA,
            "1234567000195",
            "012.345.678/001-99",     # CAEPF, nao consultavel no portal
            "1234567890123",          # 13 digitos que nao fecham o DV
            "123456789012345678",     # numero longo demais
            "12.345.678/0001-95",     # repetido
            "linha sem documento nenhum",
        ]
    )
    leitura = lote.ler(texto)

    assert leitura.total_lido == 7
    assert len(leitura.cnpjs) == 2, "a mascara torta e a oficial sao o mesmo CNPJ"
    assert len(leitura.descartados) == 5
    assert all(d.motivo for d in leitura.descartados), "todo descarte precisa de motivo"


def test_r9_descartados_chegam_ao_relatorio(pastas_temporarias, sessao_falsa):
    """Descartado na importacao tem de aparecer no resultado do lote."""
    leitura = lote.ler("1234567890123 " + fixturas.CNPJ_EM_DIA)
    execucao = lote.Execucao(cnpjs=leitura.cnpjs, descartados=leitura.descartados)

    lote.executar(leitura.cnpjs, execucao=execucao, visivel=False)

    assert execucao.como_dicionario()["descartados"] == [
        {"bruto": "1234567890123", "motivo": lote.MOTIVO_DV_13}
    ]


def test_r9_ruido_de_planilha_nao_vira_alarme_falso():
    """Telefone, CEP e data nao sao documento truncado - nao poluem o aviso."""
    leitura = lote.ler("telefone 4832221100, cep 88010-000, data 01/01/2027")

    assert leitura.cnpjs == []
    assert leitura.descartados == []


# --------------------------------------------------------------------- R10
def test_r10_guia_extra_e_descartada_antes_da_consulta():
    """Guia em branco por cima da consulta rouba o foco; sem foco o hCaptcha
    nao monta o widget e o lote parece travado ate alguem fechar na mao."""
    from simplesnacional.scraper import Sessao

    class GuiaFalsa:
        def __init__(self, nome):
            self.nome = nome
            self.fechada = False

        def close(self):
            self.fechada = True

        def is_closed(self):
            return self.fechada

    consulta = GuiaFalsa("consulta")
    intrusa = GuiaFalsa("em branco")

    class ContextoFalso:
        pages = [consulta, intrusa]

    sessao = Sessao()
    sessao._ctx = ContextoFalso()
    sessao._page = consulta
    sessao._descartar_guias_extras()

    assert intrusa.fechada is True
    assert consulta.fechada is False

    # E a guia que aparecer depois, ja com o lote rodando, tambem cai.
    tardia = GuiaFalsa("tardia")
    sessao._ao_abrir_guia(tardia)
    assert tardia.fechada is True
    sessao._ao_abrir_guia(consulta)
    assert consulta.fechada is False


# --------------------------------------------------------------------- R11
def test_r11_caepf_e_reconhecido_pela_mascara():
    """CAEPF tem 14 digitos como o CNPJ, mas mascara 3.3.3/3-2. Confirmado com a
    responsavel pela planilha em 02/09/2026: sao produtores rurais e demais
    pessoas fisicas, que o portal do Simples Nacional nao consulta. Antes saiam
    como "digito verificador nao confere", mandando a equipe cacar erro que nao
    existe."""
    leitura = lote.ler("012.345.678/001-99")

    assert leitura.cnpjs == []
    assert [d.motivo for d in leitura.descartados] == [lote.MOTIVO_CAEPF]
    assert leitura.descartados[0].bruto == "012.345.678/001-99"


def test_r11_cnpj_de_verdade_nao_e_confundido_com_caepf():
    assert lote.ler("12.345.678/0001-95").cnpjs == ["12345678000195"]


def test_r11_sem_pontuacao_o_caepf_segue_como_cnpj_invalido():
    """Sem a mascara nao ha como separar um do outro. O numero entra no lote e
    sai marcado como invalido - visivel, que e o que importa."""
    leitura = lote.ler("01234567800199")

    assert leitura.cnpjs == ["01234567800199"]
    assert lote.validar_cnpj("01234567800199") is False


# --------------------------------------------------------------------- R12
def test_r12_cpf_e_avisado_em_vez_de_sumir():
    """Parte da carteira sai do sistema de origem com CPF no lugar do CNPJ."""
    leitura = lote.ler("111.444.777-35")

    assert leitura.cnpjs == []
    assert [d.motivo for d in leitura.descartados] == [lote.MOTIVO_CPF]


def test_r12_cpf_sem_pontuacao_tambem_e_reconhecido():
    assert [d.motivo for d in lote.ler("11144477735").descartados] == [lote.MOTIVO_CPF]


def test_r12_telefone_de_onze_digitos_nao_vira_cpf():
    """Exigir que o DV feche e o que separa CPF de telefone celular."""
    leitura = lote.ler("48991234567")

    assert leitura.cnpjs == []
    assert leitura.descartados == []


# --------------------------------------------------------------------- R13
# CNPJ alfanumerico (IN RFB 2.229/2024, em vigor desde julho de 2026): as 12
# primeiras posicoes aceitam letras, os 2 digitos verificadores continuam
# numericos, e o DV segue em modulo 11 com o caractere valendo ASCII menos 48.
_CNPJ_ALFANUMERICO = "12.ABC.345/01DE-35"   # exemplo da propria Receita


def test_r13_valida_cnpj_alfanumerico():
    assert lote.validar_cnpj(_CNPJ_ALFANUMERICO) is True
    assert lote.validar_cnpj("12ABC34501DE35") is True
    assert lote.validar_cnpj("12.ABC.345/01DE-34") is False, "DV errado tem de reprovar"


def test_r13_minuscula_na_entrada_e_aceita():
    assert lote.ler("12abc34501de35").cnpjs == ["12ABC34501DE35"]


def test_r13_digito_verificador_com_letra_e_recusado():
    """As duas ultimas posicoes nunca sao letra."""
    leitura = lote.ler("12.ABC.345/01DE-3A")

    assert leitura.cnpjs == []
    assert [d.motivo for d in leitura.descartados] == [lote.MOTIVO_ESTRUTURA]


def test_r13_cnpj_numerico_valida_igual_a_antes():
    """A regra nova e extensao da antiga: digito vale ele mesmo (ASCII-48)."""
    assert lote.validar_cnpj("12.345.678/0001-95") is True
    assert lote.validar_cnpj("11.222.333/0001-81") is True
    assert lote.validar_cnpj("11.222.333/0001-82") is False


def test_r13_alfanumerico_atravessa_o_lote_inteiro(pastas_temporarias, sessao_falsa):
    """Nao basta validar: tem de sobreviver a normalizacao, ao historico e ao
    nome do comprovante sem virar so os digitos."""
    leitura = lote.ler(_CNPJ_ALFANUMERICO)
    execucao = lote.executar(leitura.cnpjs, visivel=False)

    assert execucao.cnpjs == ["12ABC34501DE35"]
    assert execucao.itens[0].cnpj == "12ABC34501DE35"
    assert execucao.itens[0].como_dicionario()["cnpj_formatado"] == _CNPJ_ALFANUMERICO


def test_r13_palavra_solta_nao_vira_candidato_a_cnpj():
    """Com letras em jogo, texto livre nao pode virar alarme falso."""
    leitura = lote.ler("EMPRESA COMERCIAL LTDA ME")

    assert leitura.cnpjs == []
    assert leitura.descartados == []


def test_r13_codigo_interno_com_letra_nao_vira_alarme_falso():
    """Planilha tem codigo de protocolo, nota, contrato. Nada disso e CNPJ
    truncado, e avisar sobre tudo faria a equipe parar de ler os avisos."""
    leitura = lote.ler("NFe202400123 PROTOCOLO12345 COMERCIAL2024")

    assert leitura.cnpjs == [], "nenhum deles pode ir parar no portal"
    # PROTOCOLO12345 tem a forma exata de um CNPJ alfanumerico (14 caracteres,
    # dois digitos no fim); so o DV o separa. Fica relatado, nunca consultado.
    assert [d.bruto for d in leitura.descartados] == ["PROTOCOLO12345"]
    assert leitura.descartados[0].motivo == lote.MOTIVO_DV_ALFANUMERICO


def test_r13_numero_puro_truncado_continua_avisando():
    """Mas numero puro de 12 ou 13 digitos ainda e CNPJ mutilado ate prova em
    contrario - esse aviso e o que fechou o buraco original."""
    assert [d.motivo for d in lote.ler("123456789012").descartados] == [lote.MOTIVO_TAMANHO]
