"""Paginas do portal reproduzidas para teste.

A marcacao segue exatamente a do Consulta Optantes (paineis Bootstrap com
`panel-title`, tabelas sem classe util, `spanValorVerde` nos valores), mas os
dados sao ficticios: nenhum comprovante de cliente entra no repositorio.
"""
from __future__ import annotations

CNPJ_COM_EVENTOS = "11222333000181"
CNPJ_EM_DIA = "11444777000161"
CNPJ_NAO_OPTANTE = "00000000000191"
CNPJ_INVALIDO = "11111111111111"


def _painel(titulo: str, corpo: str) -> str:
    return f"""
    <div class="panel panel-success">
        <div class="panel-heading">
            <h3 class="panel-title">{titulo}</h3>
        </div>
        <div class="panel-body">{corpo}</div>
    </div>"""


def _tabela(cabecalhos: list, linhas: list) -> str:
    cabecalho = "".join(f"<th>{c}</th>" for c in cabecalhos)
    corpo = "".join(
        "<tr>" + "".join(f"<td>\n  {celula}\n</td>" for celula in linha) + "</tr>"
        for linha in linhas
    )
    return f"""
            <table class="table">
                <thead><tr>{cabecalho}</tr></thead>
                <tbody>{corpo}</tbody>
            </table>"""


def pagina(
    cnpj: str,
    nome: str,
    situacao_sn: str,
    situacao_simei: str,
    periodos_sn: list = (),
    periodos_simei: list = (),
    eventos_sn: list = (),
    eventos_simei: list = (),
    mei_cargas: list = (),
    data: str = "24/08/2026 09:15:00",
) -> str:
    """Pagina de resultado completa, com o bloco "Mais informacoes" ja aberto."""
    formatado = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"

    identificacao = f"""
            CNPJ: <span class="spanValorVerde"> {formatado}</span><br>
            <input type="hidden" value="{cnpj}" id="hdnCnpj">
            <span style="font-size:small;color:gray">A op&ccedil;&atilde;o pelo Simples Nacional
            e/ou SIMEI abrange todos os estabelecimentos da empresa</span><br><br>
            Nome Empresarial: <span class="spanValorVerde">{nome}</span>"""

    situacao = f"""
            Situa&ccedil;&atilde;o no Simples Nacional: <span class="spanValorVerde">{situacao_sn}</span> <br>
            Situa&ccedil;&atilde;o no SIMEI: <span class="spanValorVerde">{situacao_simei}</span>"""

    colunas_periodo = ["Data Inicial", "Data Final", "Detalhamento"]
    if periodos_sn:
        bloco_sn = "<span>Op&ccedil;&otilde;es pelo Simples Nacional em Per&iacute;odos Anteriores: </span>"
        bloco_sn += _tabela(colunas_periodo, periodos_sn)
    else:
        bloco_sn = ("<span>Op&ccedil;&otilde;es pelo Simples Nacional em Per&iacute;odos Anteriores: "
                    '<span class="spanValorVerde">N&atilde;o Existem</span></span><br><br>')

    if periodos_simei:
        bloco_simei = "<span>Enquadramentos no SIMEI em Per&iacute;odos Anteriores: </span>"
        bloco_simei += _tabela(colunas_periodo, periodos_simei)
    else:
        bloco_simei = ("<span>Enquadramentos no SIMEI em Per&iacute;odos Anteriores: "
                       '<span class="spanValorVerde">N&atilde;o Existem</span></span>')

    colunas_evento = ["Descri&ccedil;&atilde;o do Evento", "Data Efeito"]
    futuros_sn = (
        _tabela(colunas_evento, eventos_sn)
        if eventos_sn
        else '<span class="spanValorVerde">N&atilde;o Existem</span>'
    )
    futuros_simei = (
        _tabela(colunas_evento, eventos_simei)
        if eventos_simei
        else '<span class="spanValorVerde">N&atilde;o Existem</span>'
    )
    cargas = (
        _tabela(colunas_periodo, mei_cargas)
        if mei_cargas
        else '<span><span class="spanValorVerde">N&atilde;o Existem</span></span>'
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Consulta Optantes</title></head>
<body>
<div id="conteudo" class="row">
    <h5><strong>Data da consulta:</strong>  <span>{data}</span></h5>
    {_painel("Identifica&ccedil;&atilde;o do Contribuinte - CNPJ Matriz", identificacao)}
    {_painel("Situa&ccedil;&atilde;o Atual", situacao)}
    <div class="panel">
        <button id="btnMaisInfo" class="btn btn-default">Mais informa&ccedil;&otilde;es</button>
        <div id="maisInfo" class="collapse in">
            {_painel("Per&iacute;odos Anteriores", bloco_sn + bloco_simei)}
            {_painel("Eventos Futuros (Simples Nacional)", futuros_sn)}
            {_painel("Eventos Futuros (SIMEI)", futuros_simei)}
            {_painel("Informa&ccedil;&otilde;es de Per&iacute;odos como MEI Transportador Aut&ocirc;nomo de Cargas ", cargas)}
        </div>
    </div>
</div>
</body></html>"""


def pagina_de_erro(mensagem: str) -> str:
    """Formulario devolvido com mensagem de erro (CNPJ invalido, captcha recusado)."""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Consulta Optantes</title></head>
<body>
<div class="row">
    <form action="/consultaoptantes" id="consultarForm" method="post">
        <label class="control-label" for="Cnpj">CNPJ</label>
        <input class="form-control" id="Cnpj" name="Cnpj" value="">
        <span class="text-danger field-validation-error">{mensagem}</span>
        <button class="btn btn-verde h-captcha" data-sitekey="x" data-callback="onSubmit">Consultar</button>
    </form>
</div>
</body></html>"""


# ------------------------------------------------------------------ cenarios
OPTANTE_COM_EVENTOS = pagina(
    cnpj=CNPJ_COM_EVENTOS,
    nome="MARCENARIA MODELO LTDA",
    situacao_sn="Optante pelo Simples Nacional desde 01/01/2025",
    situacao_simei="N&Atilde;O enquadrado no SIMEI",
    periodos_sn=[
        ["01/01/2024", "31/12/2024", "Exclu&iacute;da por Ato Administrativo praticado pela Receita Federal do Brasil"],
    ],
    periodos_simei=[
        ["17/01/2019", "31/12/2020", "Desenquadrada por Comunica&ccedil;&atilde;o Obrigat&oacute;ria do Contribuinte"],
    ],
    eventos_sn=[["Exclus&atilde;o de Of&iacute;cio - D&eacute;bitos", "01/01/2027"]],
)

EM_DIA = pagina(
    cnpj=CNPJ_EM_DIA,
    nome="PADARIA EXEMPLO ME",
    situacao_sn="Optante pelo Simples Nacional desde 03/02/2021",
    situacao_simei="N&Atilde;O enquadrado no SIMEI",
)

NAO_OPTANTE = pagina(
    cnpj=CNPJ_NAO_OPTANTE,
    nome="EMPRESA GRANDE SA",
    situacao_sn="N&Atilde;O optante pelo Simples Nacional",
    situacao_simei="N&Atilde;O enquadrado no SIMEI",
)

# Optante com historico apenas no SIMEI: o portal omite a tabela do Simples
# Nacional, entao a unica tabela da secao e a do SIMEI.
SO_HISTORICO_SIMEI = pagina(
    cnpj=CNPJ_EM_DIA,
    nome="ENTREGAS RAPIDAS MEI",
    situacao_sn="Optante pelo Simples Nacional desde 10/05/2018",
    situacao_simei="Enquadrado no SIMEI desde 01/01/2023",
    periodos_simei=[
        ["10/05/2018", "31/12/2022", "Desenquadrada por Comunica&ccedil;&atilde;o Obrigat&oacute;ria do Contribuinte"],
    ],
)

CNPJ_INVALIDO_HTML = pagina_de_erro("Informe um CNPJ v&aacute;lido.")
CAPTCHA_RECUSADO_HTML = pagina_de_erro(
    "Impedido por prote&ccedil;&atilde;o Captcha. Erro na valida&ccedil;&atilde;o do Token."
)
