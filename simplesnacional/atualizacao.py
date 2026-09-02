"""Aviso de versao nova, a partir dos releases publicos do GitHub.

O repositorio e publico, entao a API de releases responde sem autenticacao: nao
ha token para embutir no executavel instalado em cada maquina - que seria o
problema se o repositorio fosse privado.

O sistema le apenas o release mais recente, compara com a versao instalada e,
havendo versao nova, oferece o instalador anexado ao release.

Nada aqui levanta excecao: sem internet, com a API fora do ar ou com o release
sem instalador anexado, o sistema apenas nao avisa nada. Aviso de atualizacao
nunca pode atrapalhar quem so quer consultar CNPJ.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import config
from .versao import VERSAO

# Sufixo do arquivo anexado ao release que interessa ao sistema.
SUFIXO_INSTALADOR = "-setup.exe"

# Sanidade para o anexo anunciado pela API.
_LIMITE_INSTALADOR = 400 * 1024 * 1024


def _partes(versao: str) -> tuple:
    """1.0.10 vira (1, 0, 10) - comparar como texto poria 1.0.10 antes de 1.0.9."""
    return tuple(int(p) for p in re.findall(r"\d+", versao or ""))


def e_mais_nova(candidata: str, atual: str = VERSAO) -> bool:
    partes_candidata = _partes(candidata)
    return bool(partes_candidata) and partes_candidata > _partes(atual)


@dataclass
class Atualizacao:
    """O que o release anuncia, ja conferido contra a versao instalada."""

    versao: str = ""
    notas: str = ""
    publicado_em: str = ""
    url_instalador: str = ""
    tamanho: int = 0
    pagina: str = ""
    baixado: Optional[Path] = None
    problema: str = ""

    @property
    def disponivel(self) -> bool:
        return e_mais_nova(self.versao)

    @property
    def instalavel(self) -> bool:
        """Ha versao nova E ela tem instalador anexado ao release."""
        return self.disponivel and bool(self.url_instalador)

    def como_dicionario(self) -> dict:
        return {
            "versao_instalada": VERSAO,
            "versao": self.versao,
            "notas": self.notas,
            "publicado_em": self.publicado_em,
            "pagina": self.pagina,
            "disponivel": self.disponivel,
            "instalavel": self.instalavel,
            "problema": self.problema,
        }


def _abrir(url: str, timeout: int):
    pedido = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"ConsultaSimplesNacional/{VERSAO}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    return urllib.request.urlopen(pedido, timeout=timeout, context=ssl.create_default_context())


# A faixa da tela mostra texto simples, e as notas do release vem em Markdown.
# Sem tratamento, "### Corrigido" e "**negrito**" vazam como texto e a frase
# ainda era cortada no meio. Na faixa cabe o resumo; o detalhe fica no link para
# as notas, que a equipe abre se quiser - e em geral nao quer.
_LIMITE_RESUMO = 180

_MARCACOES = (
    (re.compile(r"`{1,3}([^`]*)`{1,3}"), r"\1"),           # `codigo`
    (re.compile(r"\*\*([^*]+)\*\*"), r"\1"),               # **negrito**
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),         # [texto](link)
    (re.compile(r"^#{1,6}\s*", re.MULTILINE), ""),         # ### titulo
    (re.compile(r"^[-*]\s+", re.MULTILINE), ""),             # - item
)

_PARAGRAFOS = re.compile(r"\n\s*\n")


def resumir_notas(corpo: str) -> str:
    """Primeiro paragrafo das notas, em texto simples e curto."""
    # A BOM entra quando as notas sao escritas por ferramenta do Windows.
    texto = (corpo or "").lstrip("﻿").strip()
    if not texto:
        return ""

    # So o primeiro paragrafo: o resto do release e detalhe tecnico.
    paragrafo = _PARAGRAFOS.split(texto, maxsplit=1)[0]
    for padrao, troca in _MARCACOES:
        paragrafo = padrao.sub(troca, paragrafo)
    paragrafo = " ".join(paragrafo.split())

    if len(paragrafo) <= _LIMITE_RESUMO:
        return paragrafo
    # Corta em espaco, nunca no meio de uma palavra.
    cortado = paragrafo[:_LIMITE_RESUMO].rsplit(" ", 1)[0]
    return cortado.rstrip(" ,;:.") + "..."


def _instalador_do_release(dados: dict) -> tuple:
    """Escolhe o anexo do instalador entre os arquivos do release.

    So aceita endereco do proprio dominio de downloads do GitHub: assim um
    release adulterado nao consegue apontar o sistema para outro servidor.
    """
    for anexo in dados.get("assets") or []:
        nome = str(anexo.get("name") or "")
        url = str(anexo.get("browser_download_url") or "")
        tamanho = int(anexo.get("size") or 0)
        if not nome.lower().endswith(SUFIXO_INSTALADOR):
            continue
        if not url.startswith("https://github.com/"):
            continue
        if tamanho <= 0 or tamanho > _LIMITE_INSTALADOR:
            continue
        return url, tamanho
    return "", 0


def verificar(repositorio: str = None, timeout: int = None) -> Atualizacao:
    """Le o release mais recente e diz se ha versao nova. Nunca levanta excecao."""
    repositorio = repositorio if repositorio is not None else config.REPOSITORIO
    if not repositorio:
        return Atualizacao()
    timeout = timeout if timeout is not None else config.TIMEOUT_ATUALIZACAO

    url = f"https://api.github.com/repos/{repositorio}/releases/latest"
    try:
        with _abrir(url, timeout) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        # Sem internet, atras de proxy, API fora do ar: silencio e o certo.
        return Atualizacao()
    if not isinstance(dados, dict):
        return Atualizacao()

    etiqueta = str(dados.get("tag_name") or "").strip()
    atualizacao = Atualizacao(
        versao=etiqueta.lstrip("vV"),
        notas=resumir_notas(str(dados.get("body") or "")),
        publicado_em=str(dados.get("published_at") or "")[:10],
        pagina=str(dados.get("html_url") or ""),
    )
    if not atualizacao.disponivel:
        return atualizacao

    atualizacao.url_instalador, atualizacao.tamanho = _instalador_do_release(dados)
    if not atualizacao.url_instalador:
        atualizacao.problema = (
            f"a versao {atualizacao.versao} foi publicada, mas o release nao traz "
            f"o instalador anexado"
        )
    return atualizacao


def impressao_digital(caminho: Path) -> str:
    """SHA-256 do arquivo, em blocos - o instalador tem dezenas de MB."""
    resumo = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def baixar(atualizacao: Atualizacao) -> str:
    """Baixa o instalador do release para uma pasta temporaria.

    Devolve "" quando deu certo, ou a mensagem do problema. O arquivo so e
    aceito se vier do dominio do GitHub e tiver o tamanho anunciado pela API -
    a conferencia mais barata contra download truncado.
    """
    if not atualizacao.url_instalador:
        return "esta versao nao tem instalador publicado"
    if not atualizacao.url_instalador.startswith("https://github.com/"):
        return "o endereco do instalador nao e do GitHub"

    destino = Path(tempfile.gettempdir()) / f"ConsultaSimplesNacional-{atualizacao.versao}-setup.exe"
    try:
        with _abrir(atualizacao.url_instalador, config.TIMEOUT_DOWNLOAD) as resposta:
            with open(destino, "wb") as arquivo:
                while bloco := resposta.read(1024 * 1024):
                    arquivo.write(bloco)
    except (urllib.error.URLError, OSError, TimeoutError) as erro:
        return f"nao foi possivel baixar o instalador: {erro}"

    if atualizacao.tamanho and destino.stat().st_size != atualizacao.tamanho:
        try:
            destino.unlink()
        except OSError:
            pass
        return "o download do instalador veio incompleto - a atualizacao foi interrompida"

    atualizacao.baixado = destino
    return ""


def abrir_instalador(atualizacao: Atualizacao) -> str:
    """Baixa e abre o instalador da versao nova. Devolve "" se deu certo."""
    problema = baixar(atualizacao)
    if problema:
        return problema
    try:
        os.startfile(str(atualizacao.baixado))  # noqa: S606 - Windows
    except OSError as erro:
        return f"nao foi possivel abrir o instalador: {erro}"
    return ""
