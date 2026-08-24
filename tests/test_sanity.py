"""Sanity test: cada peca faz o que promete, isoladamente."""
from __future__ import annotations

import pytest

from simplesnacional import historico
from simplesnacional.analise import ALERTA, ATENCAO, EM_DIA, ERRO, NAO_OPTANTE, avaliar
from simplesnacional.lote import extrair_cnpjs, validar_cnpj
from simplesnacional.parser import analisar, formatar_cnpj, somente_digitos

from . import fixturas


# ------------------------------------------------------------------- entrada
@pytest.mark.parametrize(
    "entrada,valido",
    [
        ("11222333000181", True),
        ("11.222.333/0001-81", True),
        ("00000000000191", True),
        ("11111111111111", False),   # todos iguais
        ("11222333000180", False),   # digito verificador errado
        ("1122233300018", False),    # curto demais
        ("", False),
    ],
)
def test_validacao_de_cnpj(entrada, valido):
    assert validar_cnpj(entrada) is valido


def test_extrai_cnpjs_de_texto_baguncado():
    texto = """# comentario com numero 2024
    11.222.333/0001-81, 00000000000191
    linha sem cnpj
    11222333000181
    telefone 4832221100 e cep 88010-000"""
    assert extrair_cnpjs(texto) == ["11222333000181", "00000000000191"]


def test_formatacao_de_cnpj():
    assert formatar_cnpj("11222333000181") == "11.222.333/0001-81"
    assert somente_digitos("11.222.333/0001-81") == "11222333000181"


# -------------------------------------------------------------------- parser
def test_parser_le_optante_com_eventos():
    consulta = analisar(fixturas.OPTANTE_COM_EVENTOS, fixturas.CNPJ_COM_EVENTOS)

    assert consulta.erro == ""
    assert consulta.cnpj == fixturas.CNPJ_COM_EVENTOS
    assert consulta.cnpj_formatado == "11.222.333/0001-81"
    assert consulta.nome_empresarial == "MARCENARIA MODELO LTDA"
    assert consulta.data_consulta == "24/08/2026 09:15:00"

    assert consulta.optante is True
    assert consulta.optante_desde == "01/01/2025"
    assert consulta.enquadrado_simei is False

    assert len(consulta.eventos_futuros_sn) == 1
    assert consulta.eventos_futuros_sn[0].descricao == "Exclusão de Ofício - Débitos"
    assert consulta.eventos_futuros_sn[0].data_efeito == "01/01/2027"

    assert len(consulta.periodos_anteriores_sn) == 1
    assert consulta.periodos_anteriores_sn[0].data_inicial == "01/01/2024"
    assert "Excluída por Ato Administrativo" in consulta.periodos_anteriores_sn[0].detalhamento

    assert len(consulta.periodos_anteriores_simei) == 1
    assert "Desenquadrada" in consulta.periodos_anteriores_simei[0].detalhamento

    assert consulta.eventos_futuros_simei == []
    assert consulta.mei_transportador == []


def test_parser_le_nao_optante():
    consulta = analisar(fixturas.NAO_OPTANTE, fixturas.CNPJ_NAO_OPTANTE)

    assert consulta.optante is False
    assert consulta.optante_desde == ""
    assert consulta.nome_empresarial == "EMPRESA GRANDE SA"
    assert consulta.periodos_anteriores_sn == []
    assert consulta.eventos_futuros_sn == []


def test_parser_le_optante_em_dia():
    consulta = analisar(fixturas.EM_DIA, fixturas.CNPJ_EM_DIA)

    assert consulta.optante is True
    assert consulta.optante_desde == "03/02/2021"
    assert consulta.eventos_futuros_sn == []
    assert consulta.periodos_anteriores_sn == []
    assert consulta.periodos_anteriores_simei == []


def test_parser_le_simei_enquadrado():
    consulta = analisar(fixturas.SO_HISTORICO_SIMEI, fixturas.CNPJ_EM_DIA)

    assert consulta.enquadrado_simei is True
    assert consulta.simei_desde == "01/01/2023"


def test_parser_reporta_erro_do_portal():
    consulta = analisar(fixturas.CNPJ_INVALIDO_HTML, fixturas.CNPJ_INVALIDO)

    assert consulta.erro == "Informe um CNPJ válido."
    assert consulta.nome_empresarial == ""


def test_parser_com_resposta_vazia():
    assert analisar("", "11222333000181").erro == "resposta vazia do portal"


# ------------------------------------------------------------------ analise
def test_classificacao_por_cenario():
    casos = {
        ALERTA: fixturas.OPTANTE_COM_EVENTOS,
        NAO_OPTANTE: fixturas.NAO_OPTANTE,
        EM_DIA: fixturas.EM_DIA,
        ATENCAO: fixturas.SO_HISTORICO_SIMEI,
        ERRO: fixturas.CNPJ_INVALIDO_HTML,
    }
    for esperado, html in casos.items():
        veredito = avaliar(analisar(html, "11222333000181"))
        assert veredito.status == esperado, f"esperava {esperado}, veio {veredito.status}"


def test_alerta_descreve_o_evento_no_resumo():
    veredito = avaliar(analisar(fixturas.OPTANTE_COM_EVENTOS, fixturas.CNPJ_COM_EVENTOS))

    assert veredito.em_dia is False
    assert len(veredito.exclusoes_futuras) == 1
    assert veredito.exclusoes_futuras[0]["data_efeito"] == "01/01/2027"
    assert "01/01/2027" in veredito.resumo
    # Historico de saida tambem e capturado, mesmo com o alerta em primeiro plano.
    assert len(veredito.historico_saidas) == 2


def test_em_dia_nao_tem_motivos():
    veredito = avaliar(analisar(fixturas.EM_DIA, fixturas.CNPJ_EM_DIA))

    assert veredito.em_dia is True
    assert veredito.motivos == []
    assert "Sem pendencias" in veredito.resumo


# ----------------------------------------------------------------- historico
def test_comparacao_entre_rodadas():
    antes = historico.retrato(
        {"status": EM_DIA, "situacao_simples": "Optante pelo Simples Nacional desde 01/01/2025",
         "situacao_simei": "NÃO enquadrado no SIMEI", "exclusoes_futuras": [], "historico_saidas": []}
    )
    depois = historico.retrato(
        {"status": ALERTA, "situacao_simples": "Optante pelo Simples Nacional desde 01/01/2025",
         "situacao_simei": "NÃO enquadrado no SIMEI",
         "exclusoes_futuras": [{"regime": "Simples Nacional",
                                "descricao": "Exclusão de Ofício - Débitos",
                                "data_efeito": "01/01/2027"}],
         "historico_saidas": []}
    )

    assert historico.situacao(historico.comparar(None, depois)) == historico.PRIMEIRA
    assert historico.situacao(historico.comparar(antes, antes)) == historico.SEM_MUDANCA

    mudancas = historico.comparar(antes, depois)
    assert historico.situacao(mudancas) == historico.MUDOU
    assert mudancas[0].tipo == "Novo evento futuro"


def test_comparacao_detecta_saida_do_regime():
    antes = historico.retrato({"situacao_simples": "Optante pelo Simples Nacional desde 01/01/2025",
                               "exclusoes_futuras": [], "historico_saidas": []})
    depois = historico.retrato({"situacao_simples": "NÃO optante pelo Simples Nacional",
                                "exclusoes_futuras": [], "historico_saidas": []})

    tipos = [m.tipo for m in historico.comparar(antes, depois)]
    assert "Situacao no Simples Nacional" in tipos
