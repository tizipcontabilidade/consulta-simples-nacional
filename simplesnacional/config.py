"""Configuracoes centrais do sistema.

Os caminhos se adaptam a forma de execucao:

- rodando do codigo-fonte, tudo fica na pasta do projeto;
- instalado (executavel gerado pelo PyInstaller), os dados vao para
  %LOCALAPPDATA%\\ConsultaSimplesNacional, porque a pasta de instalacao
  costuma ser somente leitura para o usuario comum.

A variavel de ambiente CSN_DADOS sobrepoe a escolha automatica - util para
apontar todo o time para uma pasta de rede compartilhada.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APLICACAO = "ConsultaSimplesNacional"

EMPACOTADO = getattr(sys, "frozen", False)
RAIZ_CODIGO = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def _pasta_de_dados() -> Path:
    escolhido = os.environ.get("CSN_DADOS")
    if escolhido:
        return Path(escolhido).expanduser()
    if EMPACOTADO:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / APLICACAO
    return Path(__file__).resolve().parent.parent


PASTA_DADOS = _pasta_de_dados()
PASTA_SAIDA = PASTA_DADOS / "saidas"
PASTA_COMPROVANTES = PASTA_SAIDA / "comprovantes"
PASTA_HISTORICO = PASTA_DADOS / "historico"
PERFIL_NAVEGADOR = PASTA_DADOS / ".perfil-consulta"

URL_FORMULARIO = "https://consopt.www8.receita.fazenda.gov.br/consultaoptantes"

# Navegadores baseados em Chromium aceitos, na ordem de preferencia. O portal
# exige captcha (hCaptcha), entao a consulta roda em um navegador real; quando
# aparece desafio, o operador resolve na tela e o lote continua.
_CANDIDATOS = (
    r"{p}\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"{p}\Google\Chrome\Application\chrome.exe",
    r"{p}\Microsoft\Edge\Application\msedge.exe",
)


def detectar_navegador() -> str:
    """Primeiro navegador Chromium encontrado na maquina ("" se nenhum)."""
    escolhido = os.environ.get("CSN_NAVEGADOR")
    if escolhido and Path(escolhido).exists():
        return escolhido

    bases = [
        os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        os.environ.get("LOCALAPPDATA", ""),
    ]
    for modelo in _CANDIDATOS:
        for base in bases:
            if not base:
                continue
            caminho = Path(modelo.format(p=base))
            if caminho.exists():
                return str(caminho)
    return ""


NAVEGADOR_EXECUTAVEL = detectar_navegador()

# Intervalo (segundos) entre consultas de um lote, para nao martelar o portal.
INTERVALO_MIN = float(os.environ.get("CSN_INTERVALO_MIN", 4.0))
INTERVALO_MAX = float(os.environ.get("CSN_INTERVALO_MAX", 8.0))

# Tempo maximo (segundos) que o sistema aguarda o operador resolver um desafio
# de captcha antes de desistir daquele CNPJ.
ESPERA_CAPTCHA = int(os.environ.get("CSN_ESPERA_CAPTCHA", 180))

# Quantas vezes repetir um CNPJ quando o portal recusa o token do captcha.
TENTATIVAS = int(os.environ.get("CSN_TENTATIVAS", 3))

# Repositorio publico de onde vem o aviso de versao nova. Sendo publico, a API
# de releases do GitHub responde sem autenticacao - nao ha token para embutir no
# executavel instalado em cada maquina da equipe. Vazio desliga o aviso.
REPOSITORIO = os.environ.get(
    "CSN_REPOSITORIO", "tizipcontabilidade/consulta-simples-nacional"
)

# De quanto em quanto tempo perguntar a API por versao nova.
INTERVALO_ATUALIZACAO = int(os.environ.get("CSN_INTERVALO_ATUALIZACAO", 21600))

# A consulta de versao roda no caminho de uma requisicao da tela: tem de
# desistir depressa quando nao ha internet, senao trava a interface.
TIMEOUT_ATUALIZACAO = int(os.environ.get("CSN_TIMEOUT_ATUALIZACAO", 6))
TIMEOUT_DOWNLOAD = int(os.environ.get("CSN_TIMEOUT_DOWNLOAD", 120))

# Segundos sem sinal de vida da interface antes de o sistema se encerrar
# sozinho (aba fechada, navegador fechado). Nunca encerra durante um lote.
TOLERANCIA_SINAL = int(os.environ.get("CSN_TOLERANCIA_SINAL", 300))


def preparar_pastas() -> None:
    for pasta in (PASTA_SAIDA, PASTA_COMPROVANTES, PASTA_HISTORICO, PERFIL_NAVEGADOR):
        pasta.mkdir(parents=True, exist_ok=True)
