"""Operational Acceptance Test: o sistema se comporta bem em producao.

Cobre o que o suporte precisa: encerramento seguro, instancia unica, escolha de
navegador, pastas de dados, codigos de saida e integridade dos scripts de
empacotamento e agendamento.
"""
from __future__ import annotations

import importlib
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

import app as aplicacao
from simplesnacional import config, lote

from . import fixturas

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def cliente(pastas_temporarias, sessao_falsa, monkeypatch):
    monkeypatch.setattr(aplicacao, "_atual", None)
    monkeypatch.setattr(aplicacao, "_thread", None)
    with aplicacao.app.test_client() as teste:
        yield teste


@pytest.fixture
def encerramentos(monkeypatch):
    """Intercepta o encerramento para o teste nao matar o proprio pytest."""
    registrados = []
    monkeypatch.setattr(aplicacao, "_encerrar_processo", lambda atraso=0.6: registrados.append(atraso))
    return registrados


# ------------------------------------------------------- encerramento seguro
def test_botao_encerrar_desliga_o_sistema(cliente, encerramentos):
    resposta = cliente.post("/encerrar")

    assert resposta.status_code == 200
    assert "Sistema encerrado" in resposta.get_data(as_text=True)
    assert len(encerramentos) == 1


def test_encerrar_e_recusado_durante_um_lote(cliente, encerramentos, monkeypatch):
    segurar = threading.Event()
    monkeypatch.setattr(aplicacao, "_thread", threading.Thread(target=segurar.wait))
    aplicacao._thread.start()
    try:
        resposta = cliente.post("/encerrar")

        assert resposta.status_code == 302
        assert "/andamento" in resposta.headers["Location"]
        assert encerramentos == [], "o lote em andamento nao pode ser interrompido"
    finally:
        segurar.set()
        aplicacao._thread.join(timeout=5)


def test_pagina_de_encerramento_nao_pede_mais_sinal_de_vida(cliente, encerramentos):
    pagina = cliente.post("/encerrar").get_data(as_text=True)

    assert "/sinal" not in pagina
    assert "Encerrar</button>" not in pagina


def test_sinal_de_vida_adia_o_encerramento(cliente):
    antes = aplicacao._ultimo_sinal
    time.sleep(0.01)

    assert cliente.post("/sinal").status_code == 204
    assert aplicacao._ultimo_sinal > antes


def test_vigia_encerra_quando_ninguem_esta_olhando(monkeypatch):
    """Sem sinal de vida e sem lote, o sistema sai sozinho."""
    registrados = []
    monkeypatch.setattr(aplicacao, "_encerrar_processo", lambda atraso=0.6: registrados.append(atraso))
    monkeypatch.setattr(aplicacao, "INTERVALO_SINAL", 0.05)
    monkeypatch.setattr(aplicacao, "TOLERANCIA_SINAL", 0.1)
    monkeypatch.setattr(aplicacao, "_ultimo_sinal", time.monotonic() - 5)
    monkeypatch.setattr(aplicacao, "_encerrando", False)

    vigia = threading.Thread(target=aplicacao._vigiar_interface, daemon=True)
    vigia.start()
    vigia.join(timeout=3)

    assert registrados, "o vigia deveria ter encerrado o sistema"


def test_vigia_espera_o_lote_terminar(monkeypatch):
    registrados = []
    segurar = threading.Event()
    trabalho = threading.Thread(target=segurar.wait)
    trabalho.start()

    monkeypatch.setattr(aplicacao, "_encerrar_processo", lambda atraso=0.6: registrados.append(atraso))
    monkeypatch.setattr(aplicacao, "INTERVALO_SINAL", 0.05)
    monkeypatch.setattr(aplicacao, "TOLERANCIA_SINAL", 0.1)
    monkeypatch.setattr(aplicacao, "_ultimo_sinal", time.monotonic() - 5)
    monkeypatch.setattr(aplicacao, "_encerrando", False)
    monkeypatch.setattr(aplicacao, "_thread", trabalho)

    vigia = threading.Thread(target=aplicacao._vigiar_interface, daemon=True)
    vigia.start()
    time.sleep(0.5)
    try:
        assert registrados == [], "encerrou com lote em andamento"
    finally:
        segurar.set()
        trabalho.join(timeout=5)
        monkeypatch.setattr(aplicacao, "_encerrando", True)


# ------------------------------------------------------------ instancia unica
def test_detecta_sistema_ja_rodando():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
        servidor.bind(("127.0.0.1", 0))
        servidor.listen(1)
        porta = servidor.getsockname()[1]

        assert aplicacao._porta_ocupada(porta) is True
    assert aplicacao._porta_ocupada(porta) is False


def test_segunda_instancia_nao_sobe_servidor(monkeypatch):
    abertos = []
    monkeypatch.setattr(aplicacao.webbrowser, "open", lambda endereco: abertos.append(endereco))
    monkeypatch.setattr(aplicacao, "_porta_ocupada", lambda _porta: True)
    monkeypatch.setattr(aplicacao.app, "run", lambda **_: pytest.fail("subiu um segundo servidor"))

    aplicacao.iniciar_servidor(porta=5000)

    assert abertos == ["http://127.0.0.1:5000"]


# ------------------------------------------------------ ambiente e navegador
def test_navegador_pode_ser_apontado_por_variavel(monkeypatch, tmp_path):
    falso = tmp_path / "navegador.exe"
    falso.write_text("", encoding="utf-8")
    monkeypatch.setenv("CSN_NAVEGADOR", str(falso))

    assert config.detectar_navegador() == str(falso)


def test_navegador_ignora_caminho_inexistente(monkeypatch):
    monkeypatch.setenv("CSN_NAVEGADOR", r"Z:\nao\existe\navegador.exe")

    encontrado = config.detectar_navegador()
    assert encontrado != r"Z:\nao\existe\navegador.exe"
    assert Path(encontrado).exists()


def test_pasta_de_dados_pode_ir_para_a_rede(monkeypatch, tmp_path):
    monkeypatch.setenv("CSN_DADOS", str(tmp_path / "compartilhada"))
    recarregado = importlib.reload(config)
    try:
        assert recarregado.PASTA_DADOS == tmp_path / "compartilhada"
        assert recarregado.PASTA_SAIDA == tmp_path / "compartilhada" / "saidas"
        recarregado.preparar_pastas()
        assert recarregado.PASTA_COMPROVANTES.is_dir()
        assert recarregado.PASTA_HISTORICO.is_dir()
    finally:
        monkeypatch.delenv("CSN_DADOS")
        importlib.reload(config)


def test_sem_navegador_o_lote_avisa_em_vez_de_travar(pastas_temporarias, monkeypatch):
    def recusar(**_):
        raise RuntimeError("nenhum navegador Chromium encontrado")

    monkeypatch.setattr(lote, "Sessao", recusar)

    execucao = lote.executar([fixturas.CNPJ_COM_EVENTOS], visivel=False)

    assert execucao.concluido is True
    assert "navegador" in execucao.erro_fatal
    assert "interrompido" in execucao.mensagem


def test_lote_so_de_invalidos_nao_abre_navegador(pastas_temporarias, monkeypatch):
    aberturas = []

    def registrar(**kwargs):
        aberturas.append(kwargs)
        raise AssertionError("nao deveria abrir o navegador")

    monkeypatch.setattr(lote, "Sessao", registrar)

    execucao = lote.executar([fixturas.CNPJ_INVALIDO], visivel=False)

    assert aberturas == []
    assert execucao.erro_fatal == ""
    assert execucao.itens[0].veredito.status == "ERRO"


# --------------------------------------------------------- linha de comando
def _rodar_cli(*argumentos):
    return subprocess.run(
        [sys.executable, "consultar.py", *argumentos],
        cwd=RAIZ, capture_output=True, text=True, timeout=120,
    )


def test_cli_codigo_2_para_arquivo_inexistente():
    resultado = _rodar_cli("--arquivo", "nao-existe.txt")

    assert resultado.returncode == 2
    assert "nao encontrado" in resultado.stderr


def test_cli_codigo_2_sem_cnpj():
    assert _rodar_cli("--formato", "nenhum").returncode == 2


def test_cli_codigo_1_quando_ha_ocorrencia():
    """CNPJ invalido e ocorrencia, e nao chega a abrir navegador."""
    resultado = _rodar_cli(fixturas.CNPJ_INVALIDO, "--formato", "nenhum",
                           "--sem-historico", "--silencioso")

    assert resultado.returncode == 1
    assert "ERRO" in resultado.stdout


def test_cli_tem_as_opcoes_documentadas():
    ajuda = _rodar_cli("--help").stdout

    for opcao in ("--arquivo", "--formato", "--saida", "--somente-mudancas",
                  "--sem-historico", "--oculto", "--silencioso"):
        assert opcao in ajuda


# ------------------------------------------------- empacotamento e agendamento
def test_receita_do_pyinstaller_gera_os_dois_executaveis():
    receita = (RAIZ / "empacotar.spec").read_text(encoding="utf-8")

    assert 'name="ConsultaSimplesNacional"' in receita
    assert 'name="consultar"' in receita
    assert "console=False" in receita, "a interface nao pode abrir janela de console"
    assert "console=True" in receita, "a CLI precisa de console para o agendador"


def test_instalador_nao_exige_administrador_e_tem_licenca():
    receita = (RAIZ / "instalador.iss").read_text(encoding="utf-8")

    assert "PrivilegesRequired=lowest" in receita
    assert "LicenseFile=LICENSE" in receita
    assert "BrazilianPortuguese" in receita


def test_scripts_powershell_sao_validos():
    """Compila os scripts sem executar nada."""
    for nome in ("agendar.ps1", "construir.ps1"):
        comando = (
            "$erros = $null; "
            f"[System.Management.Automation.Language.Parser]::ParseFile('{RAIZ / nome}', "
            "[ref]$null, [ref]$erros) | Out-Null; "
            "if ($erros) { $erros | ForEach-Object { $_.Message }; exit 1 } else { 'ok' }"
        )
        resultado = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", comando],
            capture_output=True, text=True, timeout=120,
        )
        assert resultado.returncode == 0, f"{nome}: {resultado.stdout}{resultado.stderr}"


def test_agendamento_usa_o_executavel_de_console():
    script = (RAIZ / "agendar.ps1").read_text(encoding="utf-8")

    assert "consultar.exe" in script
    assert "--somente-mudancas" in script
    assert "Register-ScheduledTask" in script


def test_dados_nao_ficam_na_pasta_de_instalacao(monkeypatch):
    """Instalado, o sistema grava em %LOCALAPPDATA% - pasta de programa costuma
    ser somente leitura para o usuario comum."""
    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    monkeypatch.delenv("CSN_DADOS", raising=False)
    recarregado = importlib.reload(config)
    try:
        assert recarregado.APLICACAO in str(recarregado.PASTA_DADOS)
        assert "AppData" in str(recarregado.PASTA_DADOS)
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_repositorio_nao_versiona_dados_de_cliente():
    ignorados = (RAIZ / ".gitignore").read_text(encoding="utf-8")

    for pasta in ("historico/", "saidas/", ".perfil-consulta/", "dist/", "instalador/"):
        assert pasta in ignorados, f"{pasta} precisa ficar fora do repositorio"
