"""Automacao do portal Consulta Optantes.

O botao "Consultar" do portal e protegido por hCaptcha. Por isso a consulta
roda em um navegador real e visivel: na maior parte das vezes o hCaptcha passa
sozinho e nada aparece na tela; quando o portal decide exibir um desafio, o
sistema pausa, avisa o operador e retoma o lote assim que ele resolve.
Nada aqui tenta burlar o captcha.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from playwright.sync_api import Error as PWError
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

from . import config

MARCADOR_RESULTADO = "Data da consulta"

# Resposta do portal quando o formulario chega sem um token valido de captcha.
_RECUSA_TOKEN = ("captcha", "token")


def _e_recusa_de_token(erro: str) -> bool:
    minusculo = (erro or "").lower()
    return all(termo in minusculo for termo in _RECUSA_TOKEN)


@dataclass
class RespostaBruta:
    """HTML cru devolvido pelo portal para um CNPJ."""

    cnpj: str
    html: str = ""
    url: str = ""
    ok: bool = False
    erro: str = ""
    precisou_captcha: bool = False


@dataclass
class Sessao:
    """Sessao de navegador reaproveitada por todo um lote de consultas."""

    visivel: bool = True
    ao_avisar: Optional[Callable[[str], None]] = None
    _pw: object = field(default=None, repr=False)
    _ctx: object = field(default=None, repr=False)
    _page: object = field(default=None, repr=False)

    # ------------------------------------------------------------------ ciclo
    def abrir(self) -> "Sessao":
        if not config.NAVEGADOR_EXECUTAVEL:
            raise RuntimeError(
                "nenhum navegador Chromium encontrado (Brave, Chrome ou Edge). "
                "Instale um deles ou aponte o caminho na variavel CSN_NAVEGADOR."
            )
        config.PERFIL_NAVEGADOR.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(config.PERFIL_NAVEGADOR),
            executable_path=config.NAVEGADOR_EXECUTAVEL,
            headless=not self.visivel,
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        self._page.set_default_timeout(30_000)
        return self

    def fechar(self) -> None:
        for alvo, metodo in ((self._ctx, "close"), (self._pw, "stop")):
            if alvo is not None:
                try:
                    getattr(alvo, metodo)()
                except Exception:
                    pass
        self._ctx = self._pw = self._page = None

    def __enter__(self) -> "Sessao":
        return self.abrir()

    def __exit__(self, *_exc) -> None:
        self.fechar()

    # ----------------------------------------------------------------- avisos
    def _avisar(self, mensagem: str) -> None:
        if self.ao_avisar:
            self.ao_avisar(mensagem)

    # --------------------------------------------------------------- consulta
    def consultar(self, cnpj: str) -> RespostaBruta:
        """Consulta um CNPJ, repetindo quando o portal recusa o token do captcha."""
        for tentativa in range(1, config.TENTATIVAS + 1):
            resposta = self._tentar(cnpj)
            if resposta.ok or not _e_recusa_de_token(resposta.erro):
                return resposta

            resposta.precisou_captcha = True
            if tentativa < config.TENTATIVAS:
                espera = 5 * tentativa
                self._avisar(
                    f"O portal recusou a verificacao do CNPJ {cnpj} "
                    f"(tentativa {tentativa} de {config.TENTATIVAS}). "
                    f"Nova tentativa em {espera}s."
                )
                time.sleep(espera)
        return resposta

    def _tentar(self, cnpj: str) -> RespostaBruta:
        """Uma passada pelo formulario: preenche, espera o captcha carregar e envia."""
        resposta = RespostaBruta(cnpj=cnpj)
        if self._page is None:
            resposta.erro = "sessao nao aberta"
            return resposta

        page = self._page
        try:
            page.goto(config.URL_FORMULARIO, wait_until="domcontentloaded")
            page.fill("#Cnpj", cnpj)
            self._esperar_captcha_pronto(page)
            page.click("button.h-captcha")
        except (PWTimeout, PWError) as exc:
            resposta.erro = f"falha ao enviar o formulario: {exc}"
            return resposta

        limite = time.monotonic() + config.ESPERA_CAPTCHA
        inicio = time.monotonic()
        avisou = False
        while time.monotonic() < limite:
            try:
                conteudo = page.content()
            except PWError:
                time.sleep(0.5)
                continue

            if MARCADOR_RESULTADO in conteudo:
                self._expandir_mais_informacoes(page)
                resposta.html = page.content()
                resposta.url = page.url
                resposta.ok = True
                return resposta

            erro_validacao = self._erro_de_validacao(page)
            if erro_validacao:
                resposta.erro = erro_validacao
                resposta.html = conteudo
                return resposta

            if time.monotonic() - inicio > 6 and self._desafio_visivel(page):
                resposta.precisou_captcha = True
                if not avisou:
                    avisou = True
                    self._avisar(
                        f"O portal pediu verificacao (captcha) para o CNPJ {cnpj}. "
                        "Resolva o desafio na janela do navegador; o lote continua sozinho."
                    )
            time.sleep(1.0)

        resposta.erro = (
            "tempo esgotado aguardando o resultado"
            + (" (desafio de captcha nao resolvido)" if resposta.precisou_captcha else "")
        )
        return resposta

    @staticmethod
    def _esperar_captcha_pronto(page) -> None:
        """Espera o hCaptcha registrar o widget no botao.

        O botao "Consultar" so envia um token valido depois que o script do
        hCaptcha (carregado de forma assincrona) renderiza o widget. Clicar
        antes disso faz o portal responder "Erro na validacao do Token".
        """
        try:
            page.wait_for_function(
                "() => { const b = document.querySelector('button.h-captcha');"
                " return !!window.hcaptcha && !!b && b.hasAttribute('data-hcaptcha-widget-id'); }",
                timeout=25_000,
            )
        except (PWTimeout, PWError):
            # Sem o widget o envio provavelmente falha, mas ainda vale tentar:
            # o erro do portal e tratado e a consulta e repetida.
            pass

    @staticmethod
    def _expandir_mais_informacoes(page) -> None:
        """Abre o bloco "Mais informacoes", carregado por AJAX apos o clique."""
        try:
            botao = page.query_selector("#btnMaisInfo")
            if botao is None:
                return
            botao.click()
            page.wait_for_function(
                "() => { const e = document.getElementById('maisInfo');"
                " return e && e.innerHTML.trim().length > 40; }",
                timeout=20_000,
            )
        except (PWTimeout, PWError):
            pass

    @staticmethod
    def _erro_de_validacao(page) -> str:
        """Mensagem de erro exibida pelo proprio portal, se houver."""
        for seletor in ("span.field-validation-error", "div.validation-summary-errors", ".text-danger"):
            try:
                for elemento in page.query_selector_all(seletor):
                    texto = (elemento.inner_text() or "").strip()
                    if texto:
                        return texto
            except PWError:
                continue
        return ""

    @staticmethod
    def _desafio_visivel(page) -> bool:
        """True quando o hCaptcha esta mostrando um desafio para o operador."""
        try:
            for iframe in page.query_selector_all('iframe[src*="hcaptcha.com"]'):
                if not iframe.is_visible():
                    continue
                caixa = iframe.bounding_box()
                if caixa and caixa.get("height", 0) > 200 and caixa.get("width", 0) > 200:
                    return True
        except PWError:
            pass
        return False


def pausa_entre_consultas() -> float:
    """Intervalo aleatorio entre consultas de um lote."""
    segundos = random.uniform(config.INTERVALO_MIN, config.INTERVALO_MAX)
    time.sleep(segundos)
    return segundos
