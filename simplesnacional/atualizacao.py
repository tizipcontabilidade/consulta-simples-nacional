"""Aviso de versao nova a partir de um manifesto numa pasta compartilhada.

A distribuicao da equipe e por pasta do Google Drive sincronizada pelo Drive
para Desktop, entao o manifesto e o instalador sao arquivos locais comuns: sem
HTTP, sem token, sem a tela de "nao foi possivel verificar virus" que o Drive
mostra em download direto de arquivo grande.

O manifesto e um `versao.json` ao lado do instalador:

    {
      "versao": "1.0.4",
      "instalador": "ConsultaSimplesNacional-1.0.4-setup.exe",
      "sha256": "a1b2c3...",
      "notas": "Corrige X e Y.",
      "publicado_em": "2026-09-02"
    }

Nada aqui levanta excecao: sem o Drive montado, sem a pasta ou com o manifesto
quebrado, o sistema apenas nao avisa nada. Aviso de atualizacao nunca pode
atrapalhar quem so quer consultar CNPJ.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import config
from .versao import VERSAO

NOME_MANIFESTO = "versao.json"

# Tamanho maximo aceito para o instalador anunciado. Serve de sanidade: o
# manifesto e um arquivo de pasta compartilhada, e alguem pode trocar o que
# esta la por engano.
_LIMITE_INSTALADOR = 400 * 1024 * 1024


def _partes(versao: str) -> tuple:
    """1.0.10 vira (1, 0, 10) - comparar como texto poria 1.0.10 antes de 1.0.9."""
    return tuple(int(p) for p in re.findall(r"\d+", versao or ""))


def e_mais_nova(candidata: str, atual: str = VERSAO) -> bool:
    partes_candidata = _partes(candidata)
    return bool(partes_candidata) and partes_candidata > _partes(atual)


@dataclass
class Atualizacao:
    """O que o manifesto anuncia, ja conferido contra a versao instalada."""

    versao: str = ""
    notas: str = ""
    publicado_em: str = ""
    instalador: Optional[Path] = None
    sha256: str = ""
    problema: str = ""

    @property
    def disponivel(self) -> bool:
        return e_mais_nova(self.versao)

    @property
    def instalavel(self) -> bool:
        """Ha versao nova E o instalador dela esta acessivel agora."""
        return self.disponivel and self.instalador is not None

    def como_dicionario(self) -> dict:
        return {
            "versao_instalada": VERSAO,
            "versao": self.versao,
            "notas": self.notas,
            "publicado_em": self.publicado_em,
            "disponivel": self.disponivel,
            "instalavel": self.instalavel,
            "problema": self.problema,
        }


def _pasta(origem=None) -> Optional[Path]:
    escolhida = origem if origem is not None else config.PASTA_ATUALIZACAO
    if not escolhida:
        return None
    try:
        return Path(escolhida)
    except (TypeError, ValueError):
        return None


def _instalador_do_manifesto(pasta: Path, dados: dict) -> Optional[Path]:
    """Resolve o instalador anunciado, so dentro da pasta do manifesto.

    O campo e um nome de arquivo simples, nunca caminho nem endereco: assim um
    manifesto adulterado - por engano ou nao - nao consegue apontar o sistema
    para um executavel qualquer da maquina ou da rede.
    """
    nome = str(dados.get("instalador") or "").strip()
    if not nome or "/" in nome or "\\" in nome or nome in (".", ".."):
        return None
    candidato = pasta / nome
    try:
        if not candidato.is_file():
            return None
        if candidato.stat().st_size > _LIMITE_INSTALADOR:
            return None
        # Confere que o arquivo resolvido continua dentro da pasta anunciada.
        if candidato.resolve().parent != pasta.resolve():
            return None
    except OSError:
        return None
    return candidato


def verificar(origem=None) -> Atualizacao:
    """Le o manifesto e diz se ha versao nova. Nunca levanta excecao."""
    pasta = _pasta(origem)
    if pasta is None:
        return Atualizacao()

    try:
        bruto = (pasta / NOME_MANIFESTO).read_text(encoding="utf-8")
    except OSError:
        # Drive nao montado, pasta ausente, sem permissao: silencio e o certo.
        return Atualizacao()

    try:
        dados = json.loads(bruto)
    except (ValueError, TypeError):
        return Atualizacao(problema="o manifesto de versao esta ilegivel")
    if not isinstance(dados, dict):
        return Atualizacao(problema="o manifesto de versao esta ilegivel")

    atualizacao = Atualizacao(
        versao=str(dados.get("versao") or "").strip(),
        notas=str(dados.get("notas") or "").strip(),
        publicado_em=str(dados.get("publicado_em") or "").strip(),
        sha256=str(dados.get("sha256") or "").strip().lower(),
    )
    if not atualizacao.disponivel:
        return atualizacao

    atualizacao.instalador = _instalador_do_manifesto(pasta, dados)
    if atualizacao.instalador is None:
        atualizacao.problema = (
            f"a versao {atualizacao.versao} foi anunciada, mas o instalador dela "
            f"nao esta na pasta de atualizacao"
        )
    return atualizacao


def impressao_digital(caminho: Path) -> str:
    """SHA-256 do arquivo, em blocos - o instalador tem dezenas de MB."""
    resumo = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def conferir(atualizacao: Atualizacao) -> str:
    """Confere o instalador contra o SHA-256 do manifesto.

    Devolve "" quando esta tudo certo, ou a mensagem do problema. Enquanto nao
    houver certificado de code signing, esta e a unica prova de que o arquivo
    que vai rodar e o que foi publicado.
    """
    if atualizacao.instalador is None:
        return "o instalador da versao nova nao foi encontrado"
    if not atualizacao.sha256:
        return "o manifesto nao trouxe o SHA-256 do instalador"
    try:
        obtido = impressao_digital(atualizacao.instalador)
    except OSError as erro:
        return f"nao foi possivel ler o instalador: {erro}"
    if obtido != atualizacao.sha256:
        return (
            "o instalador na pasta compartilhada nao confere com o SHA-256 "
            "publicado no manifesto - a atualizacao foi interrompida"
        )
    return ""


def abrir_instalador(atualizacao: Atualizacao) -> str:
    """Confere a integridade e abre o instalador. Devolve "" se deu certo."""
    problema = conferir(atualizacao)
    if problema:
        return problema
    try:
        os.startfile(str(atualizacao.instalador))  # noqa: S606 - Windows
    except OSError as erro:
        return f"nao foi possivel abrir o instalador: {erro}"
    return ""
