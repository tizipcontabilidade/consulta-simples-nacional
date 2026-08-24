"""Ponto de entrada dos executaveis.

Sao dois executaveis gerados da mesma base:

    ConsultaSimplesNacional.exe    sem janela de console - abre a interface web
    consultar.exe                  com console - linha de comando, para o agendador

A escolha e feita pelo nome do executavel; passar argumentos tambem leva para a
linha de comando. Sem console, `print` nao tem para onde escrever, entao a saida
padrao e desviada antes de qualquer coisa.
"""
from __future__ import annotations

import os
import sys


def _garantir_saida() -> None:
    """Evita quebra em `print` quando o executavel roda sem console."""
    for fluxo in ("stdout", "stderr"):
        if getattr(sys, fluxo, None) is None:
            setattr(sys, fluxo, open(os.devnull, "w", encoding="utf-8"))


def _modo_linha_de_comando(argumentos: list) -> bool:
    nome = os.path.basename(sys.executable if getattr(sys, "frozen", False) else sys.argv[0])
    if nome.lower().startswith("consultar"):
        return True
    return bool(argumentos) and argumentos[0] not in ("--web", "-w")


def main() -> int:
    _garantir_saida()
    argumentos = sys.argv[1:]

    if _modo_linha_de_comando(argumentos):
        from consultar import main as rodar_cli

        return rodar_cli()

    if argumentos and argumentos[0] in ("--web", "-w"):
        sys.argv = sys.argv[:1] + argumentos[1:]

    from app import iniciar_servidor

    iniciar_servidor()
    return 0


if __name__ == "__main__":
    sys.exit(main())
