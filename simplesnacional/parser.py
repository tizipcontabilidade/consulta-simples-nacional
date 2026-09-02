"""Traducao do HTML do portal para uma estrutura de dados."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Optional

from bs4 import BeautifulSoup


def _normalizar(texto: str) -> str:
    """Minusculas, sem acento e com espacos colapsados - so para comparacoes."""
    limpo = unicodedata.normalize("NFKD", texto or "")
    limpo = "".join(c for c in limpo if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", limpo).strip().lower()


def _texto(no) -> str:
    return re.sub(r"\s+", " ", no.get_text(" ", strip=True)) if no else ""


@dataclass
class Linha:
    data_inicial: str = ""
    data_final: str = ""
    detalhamento: str = ""


@dataclass
class Evento:
    descricao: str = ""
    data_efeito: str = ""


@dataclass
class Consulta:
    """Resultado estruturado de um CNPJ."""

    cnpj: str = ""
    cnpj_formatado: str = ""
    nome_empresarial: str = ""
    data_consulta: str = ""

    situacao_simples: str = ""
    optante: Optional[bool] = None
    optante_desde: str = ""

    situacao_simei: str = ""
    enquadrado_simei: Optional[bool] = None
    simei_desde: str = ""

    periodos_anteriores_sn: list = field(default_factory=list)
    periodos_anteriores_simei: list = field(default_factory=list)
    eventos_futuros_sn: list = field(default_factory=list)
    eventos_futuros_simei: list = field(default_factory=list)
    mei_transportador: list = field(default_factory=list)

    erro: str = ""

    def como_dicionario(self) -> dict:
        return asdict(self)


def normalizar_cnpj(cnpj: str) -> str:
    """Os 14 caracteres uteis do CNPJ, em maiusculas.

    Desde julho de 2026 o CNPJ e alfanumerico (IN RFB 2.229/2024): as 12
    primeiras posicoes aceitam letras de A a Z alem dos digitos, e so os dois
    digitos verificadores continuam obrigatoriamente numericos. A mascara nao
    mudou. Minusculas sao aceitas na entrada e sobem para maiusculas.
    """
    return re.sub(r"[^0-9A-Za-z]", "", cnpj or "").upper()


def formatar_cnpj(cnpj: str) -> str:
    limpo = normalizar_cnpj(cnpj)
    if len(limpo) != 14:
        return cnpj or ""
    return f"{limpo[:2]}.{limpo[2:5]}.{limpo[5:8]}/{limpo[8:12]}-{limpo[12:]}"


def somente_digitos(cnpj: str) -> str:
    """So os digitos - para CPF e CAEPF, que continuam puramente numericos."""
    return re.sub(r"\D", "", cnpj or "")


def _painel(sopa: BeautifulSoup, titulo_normalizado: str):
    """Devolve o corpo do painel cujo titulo comeca com o texto informado."""
    for cabecalho in sopa.select("div.panel-heading h3.panel-title"):
        if _normalizar(_texto(cabecalho)).startswith(titulo_normalizado):
            painel = cabecalho.find_parent("div", class_="panel")
            if painel:
                return painel.find("div", class_="panel-body")
    return None


def _linhas(tabela) -> list:
    if tabela is None:
        return []
    saida = []
    for tr in tabela.select("tbody tr"):
        celulas = [_texto(td) for td in tr.find_all("td")]
        if any(celulas):
            saida.append(celulas)
    return saida


def _periodos(tabela) -> list:
    return [
        Linha(
            data_inicial=celulas[0] if len(celulas) > 0 else "",
            data_final=celulas[1] if len(celulas) > 1 else "",
            detalhamento=celulas[2] if len(celulas) > 2 else "",
        )
        for celulas in _linhas(tabela)
    ]


def _eventos(tabela) -> list:
    return [
        Evento(
            descricao=celulas[0] if len(celulas) > 0 else "",
            data_efeito=celulas[1] if len(celulas) > 1 else "",
        )
        for celulas in _linhas(tabela)
    ]


def _data_apos(texto: str) -> str:
    achado = re.search(r"(\d{2}/\d{2}/\d{4})", texto or "")
    return achado.group(1) if achado else ""


def analisar(html: str, cnpj_consultado: str = "") -> Consulta:
    """Converte o HTML da pagina de resultado em um objeto Consulta."""
    resultado = Consulta(
        cnpj=normalizar_cnpj(cnpj_consultado),
        cnpj_formatado=formatar_cnpj(cnpj_consultado),
    )
    if not html:
        resultado.erro = "resposta vazia do portal"
        return resultado

    sopa = BeautifulSoup(html, "lxml")

    cabecalho = sopa.find("h5")
    if cabecalho and "Data da consulta" in _texto(cabecalho):
        resultado.data_consulta = _texto(cabecalho).split(":", 1)[-1].strip()

    identificacao = _painel(sopa, "identificacao do contribuinte")
    if identificacao is None:
        mensagem = ""
        for seletor in ("span.field-validation-error", ".validation-summary-errors", ".text-danger"):
            achado = sopa.select_one(seletor)
            if achado and _texto(achado):
                mensagem = _texto(achado)
                break
        resultado.erro = mensagem or "pagina de resultado nao reconhecida"
        return resultado

    escondido = sopa.find("input", id="hdnCnpj")
    if escondido and escondido.get("value"):
        resultado.cnpj = normalizar_cnpj(escondido["value"])
        resultado.cnpj_formatado = formatar_cnpj(resultado.cnpj)

    valores = identificacao.find_all("span", class_="spanValorVerde")
    if valores:
        if not resultado.cnpj:
            resultado.cnpj = normalizar_cnpj(_texto(valores[0]))
            resultado.cnpj_formatado = formatar_cnpj(resultado.cnpj)
        if len(valores) > 1:
            resultado.nome_empresarial = _texto(valores[-1])

    situacao = _painel(sopa, "situacao atual")
    if situacao is not None:
        for parte in re.split(r"Situa[cç][aã]o no ", _texto(situacao)):
            parte = parte.strip()
            if not parte:
                continue
            normalizado = _normalizar(parte)
            valor = parte.split(":", 1)[-1].strip()
            if normalizado.startswith("simples nacional"):
                resultado.situacao_simples = valor
                resultado.optante = not _normalizar(valor).startswith("nao optante")
                if resultado.optante:
                    resultado.optante_desde = _data_apos(valor)
            elif normalizado.startswith("simei"):
                resultado.situacao_simei = valor
                resultado.enquadrado_simei = not _normalizar(valor).startswith("nao enquadrado")
                if resultado.enquadrado_simei:
                    resultado.simei_desde = _data_apos(valor)

    anteriores = _painel(sopa, "periodos anteriores")
    if anteriores is not None:
        tabelas = anteriores.find_all("table")
        # O portal lista primeiro o Simples Nacional e depois o SIMEI; quando uma
        # das listas nao tem registro, ele troca a tabela por "Nao Existem".
        texto_anteriores = _normalizar(_texto(anteriores))
        tem_sn = "opcoes pelo simples nacional em periodos anteriores: nao existem" not in texto_anteriores
        tem_simei = "enquadramentos no simei em periodos anteriores: nao existem" not in texto_anteriores
        indice = 0
        if tem_sn and indice < len(tabelas):
            resultado.periodos_anteriores_sn = _periodos(tabelas[indice])
            indice += 1
        if tem_simei and indice < len(tabelas):
            resultado.periodos_anteriores_simei = _periodos(tabelas[indice])

    futuros_sn = _painel(sopa, "eventos futuros (simples nacional)")
    if futuros_sn is not None:
        tabelas = futuros_sn.find_all("table")
        if tabelas:
            resultado.eventos_futuros_sn = _eventos(tabelas[0])

    futuros_simei = _painel(sopa, "eventos futuros (simei)")
    if futuros_simei is not None:
        tabelas = futuros_simei.find_all("table")
        if tabelas:
            resultado.eventos_futuros_simei = _eventos(tabelas[0])

    mei = _painel(sopa, "informacoes de periodos como mei transportador")
    if mei is not None:
        tabelas = mei.find_all("table")
        if tabelas:
            resultado.mei_transportador = _periodos(tabelas[0])

    return resultado
