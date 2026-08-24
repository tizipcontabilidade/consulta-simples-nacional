"""Historico das consultas: guarda o ultimo retrato de cada CNPJ e aponta o que mudou.

O arquivo `historico/estado.json` guarda, por CNPJ, um resumo da ultima consulta.
Na rodada seguinte o sistema compara o retrato novo com o antigo e diz o que
mudou - que e o que interessa em um acompanhamento recorrente.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import config

ARQUIVO_ESTADO = "estado.json"

PRIMEIRA = "PRIMEIRA CONSULTA"
SEM_MUDANCA = "SEM MUDANCA"
MUDOU = "MUDOU"


@dataclass
class Mudanca:
    """Uma diferenca pontual entre a consulta anterior e a atual."""

    tipo: str
    descricao: str

    def como_dicionario(self) -> dict:
        return {"tipo": self.tipo, "descricao": self.descricao}


def _caminho_estado(pasta: Optional[Path] = None) -> Path:
    pasta = pasta or config.PASTA_HISTORICO
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / ARQUIVO_ESTADO


def carregar(pasta: Optional[Path] = None) -> dict:
    caminho = _caminho_estado(pasta)
    if not caminho.exists():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def gravar(estado: dict, pasta: Optional[Path] = None) -> None:
    _caminho_estado(pasta).write_text(
        json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def retrato(dados: dict) -> dict:
    """Resumo comparavel de uma consulta - so o que importa acompanhar."""
    return {
        "status": dados.get("status", ""),
        "nome_empresarial": dados.get("nome_empresarial", ""),
        "situacao_simples": dados.get("situacao_simples", ""),
        "situacao_simei": dados.get("situacao_simei", ""),
        "eventos": sorted(
            f"{e.get('regime', '')} | {e.get('descricao', '')} | {e.get('data_efeito', '')}"
            for e in dados.get("exclusoes_futuras", [])
        ),
        "saidas": sorted(
            f"{s.get('regime', '')} | {s.get('detalhamento', '')} | {s.get('periodo', '')}"
            for s in dados.get("historico_saidas", [])
        ),
        "consultado_em": dados.get("data_consulta", "")
        or datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }


def comparar(anterior: Optional[dict], atual: dict) -> list:
    """Lista as diferencas entre dois retratos. Vazia = nada mudou."""
    if not anterior:
        return [Mudanca(PRIMEIRA, "Primeira consulta registrada para este CNPJ.")]

    mudancas = []

    if anterior.get("situacao_simples") != atual.get("situacao_simples"):
        mudancas.append(
            Mudanca(
                "Situacao no Simples Nacional",
                f"de \"{anterior.get('situacao_simples') or '-'}\" "
                f"para \"{atual.get('situacao_simples') or '-'}\"",
            )
        )

    if anterior.get("situacao_simei") != atual.get("situacao_simei"):
        mudancas.append(
            Mudanca(
                "Situacao no SIMEI",
                f"de \"{anterior.get('situacao_simei') or '-'}\" "
                f"para \"{atual.get('situacao_simei') or '-'}\"",
            )
        )

    eventos_antes = set(anterior.get("eventos", []))
    eventos_agora = set(atual.get("eventos", []))
    for novo in sorted(eventos_agora - eventos_antes):
        mudancas.append(Mudanca("Novo evento futuro", novo))
    for saiu in sorted(eventos_antes - eventos_agora):
        mudancas.append(Mudanca("Evento futuro deixou de constar", saiu))

    saidas_antes = set(anterior.get("saidas", []))
    saidas_agora = set(atual.get("saidas", []))
    for nova in sorted(saidas_agora - saidas_antes):
        mudancas.append(Mudanca("Nova exclusao / desenquadramento", nova))

    if anterior.get("status") != atual.get("status") and not mudancas:
        mudancas.append(
            Mudanca("Status", f"de {anterior.get('status')} para {atual.get('status')}")
        )

    return mudancas


def situacao(mudancas: list) -> str:
    """PRIMEIRA CONSULTA, SEM MUDANCA ou MUDOU."""
    if not mudancas:
        return SEM_MUDANCA
    if len(mudancas) == 1 and mudancas[0].tipo == PRIMEIRA:
        return PRIMEIRA
    return MUDOU


def registrar(itens: list, pasta: Optional[Path] = None) -> None:
    """Grava o retrato atual de cada CNPJ consultado com sucesso."""
    estado = carregar(pasta)
    for dados in itens:
        cnpj = dados.get("cnpj")
        if not cnpj or dados.get("erro"):
            continue  # consulta que falhou nao substitui o retrato anterior
        estado[cnpj] = retrato(dados)
    gravar(estado, pasta)
