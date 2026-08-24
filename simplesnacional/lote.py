"""Execucao de um lote de consultas, com progresso e gravacao dos resultados."""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterable, Optional

from . import config, historico
from .analise import EM_DIA, Veredito, avaliar, ordenar
from .parser import Consulta, analisar, formatar_cnpj, somente_digitos
from .scraper import Sessao, pausa_entre_consultas


def extrair_cnpjs(texto: str) -> list:
    """Extrai CNPJs de texto livre (colado, CSV, uma por linha...), sem repetir."""
    padrao = r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)"
    encontrados = re.findall(padrao, texto or "")
    limpos = []
    for bruto in encontrados:
        digitos = somente_digitos(bruto)
        if len(digitos) == 14 and digitos not in limpos:
            limpos.append(digitos)
    return limpos


def validar_cnpj(cnpj: str) -> bool:
    """Validacao dos dois digitos verificadores."""
    digitos = somente_digitos(cnpj)
    if len(digitos) != 14 or len(set(digitos)) == 1:
        return False
    numeros = [int(d) for d in digitos]
    for tamanho in (12, 13):
        pesos = list(range(tamanho - 7, 1, -1)) + list(range(9, 1, -1))
        soma = sum(n * p for n, p in zip(numeros[:tamanho], pesos))
        resto = soma % 11
        esperado = 0 if resto < 2 else 11 - resto
        if numeros[tamanho] != esperado:
            return False
    return True


@dataclass
class Item:
    """Uma linha do lote: o que foi consultado e o que o portal respondeu."""

    cnpj: str
    consulta: Optional[Consulta] = None
    veredito: Optional[Veredito] = None
    html: str = ""
    arquivo_comprovante: str = ""
    mudancas: list = field(default_factory=list)
    situacao_historico: str = ""

    def como_dicionario(self) -> dict:
        dados = self.consulta.como_dicionario() if self.consulta else {"cnpj": self.cnpj}
        dados["cnpj_formatado"] = dados.get("cnpj_formatado") or formatar_cnpj(self.cnpj)
        if self.veredito:
            dados["status"] = self.veredito.status
            dados["rotulo"] = self.veredito.rotulo
            dados["motivos"] = self.veredito.motivos
            dados["resumo"] = self.veredito.resumo
            dados["exclusoes_futuras"] = self.veredito.exclusoes_futuras
            dados["historico_saidas"] = self.veredito.historico_saidas
            dados["em_dia"] = self.veredito.em_dia
        dados["comprovante"] = self.arquivo_comprovante
        dados["mudancas"] = [m.como_dicionario() for m in self.mudancas]
        dados["situacao_historico"] = self.situacao_historico
        return dados


@dataclass
class Execucao:
    """Estado observavel de um lote em andamento."""

    cnpjs: list
    itens: list = field(default_factory=list)
    indice: int = 0
    mensagem: str = "Aguardando inicio."
    aguardando_captcha: bool = False
    concluido: bool = False
    cancelado: bool = False
    erro_fatal: str = ""
    inicio: datetime = field(default_factory=datetime.now)
    fim: Optional[datetime] = None
    _trava: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def total(self) -> int:
        return len(self.cnpjs)

    @property
    def percentual(self) -> int:
        return int(100 * self.indice / self.total) if self.total else 100

    def contagem(self) -> dict:
        contagem = {}
        for item in self.itens:
            if item.veredito:
                contagem[item.veredito.status] = contagem.get(item.veredito.status, 0) + 1
        return contagem

    def com_mudanca(self) -> list:
        """Itens cujo retrato mudou desde a consulta anterior."""
        return [i for i in self.itens if i.situacao_historico == historico.MUDOU]

    def resultados_ordenados(self) -> list:
        pares = [(i.consulta, i.veredito) for i in self.itens if i.consulta and i.veredito]
        ordenados = ordenar(pares)
        indice_por_cnpj = {c.cnpj or "": pos for pos, (c, _) in enumerate(ordenados)}
        return sorted(self.itens, key=lambda i: indice_por_cnpj.get(i.cnpj, 999_999))

    def como_dicionario(self) -> dict:
        return {
            "total": self.total,
            "processados": self.indice,
            "percentual": self.percentual,
            "mensagem": self.mensagem,
            "aguardando_captcha": self.aguardando_captcha,
            "concluido": self.concluido,
            "cancelado": self.cancelado,
            "erro_fatal": self.erro_fatal,
            "contagem": self.contagem(),
            "com_mudanca": len(self.com_mudanca()),
            "itens": [i.como_dicionario() for i in self.itens],
        }


def executar(
    cnpjs: Iterable[str],
    execucao: Optional[Execucao] = None,
    visivel: bool = True,
    salvar_comprovante_em_dia: bool = False,
    usar_historico: bool = True,
    ao_progredir: Optional[Callable[[Execucao], None]] = None,
) -> Execucao:
    """Consulta a lista de CNPJs em sequencia, reaproveitando uma unica sessao."""
    lista = [somente_digitos(c) for c in cnpjs]
    execucao = execucao or Execucao(cnpjs=lista)
    execucao.cnpjs = lista

    config.preparar_pastas()
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    estado_anterior = historico.carregar() if usar_historico else {}

    def avisar(mensagem: str) -> None:
        execucao.aguardando_captcha = True
        execucao.mensagem = mensagem
        if ao_progredir:
            ao_progredir(execucao)

    # O navegador so e aberto quando ha de fato um CNPJ para consultar: um lote
    # so de CNPJs invalidos nao deve abrir janela nenhuma.
    sessao: Optional[Sessao] = None

    def obter_sessao() -> Sessao:
        nonlocal sessao
        if sessao is None:
            sessao = Sessao(visivel=visivel, ao_avisar=avisar)
            sessao.abrir()
        return sessao

    try:
        for posicao, cnpj in enumerate(lista, start=1):
            if execucao.cancelado:
                break

            execucao.mensagem = f"Consultando {formatar_cnpj(cnpj)} ({posicao} de {len(lista)})..."
            if ao_progredir:
                ao_progredir(execucao)

            item = Item(cnpj=cnpj)
            if not validar_cnpj(cnpj):
                item.consulta = Consulta(
                    cnpj=cnpj,
                    cnpj_formatado=formatar_cnpj(cnpj),
                    erro="CNPJ invalido (digito verificador nao confere) - nao foi consultado",
                )
            else:
                try:
                    ativa = obter_sessao()
                except Exception as exc:  # navegador ausente, perfil travado, etc.
                    execucao.erro_fatal = f"nao foi possivel abrir o navegador: {exc}"
                    break
                resposta = ativa.consultar(cnpj)
                execucao.aguardando_captcha = False
                item.html = resposta.html
                item.consulta = analisar(resposta.html, cnpj)
                if not resposta.ok and not item.consulta.erro:
                    item.consulta.erro = resposta.erro or "falha desconhecida na consulta"

            item.veredito = avaliar(item.consulta)

            if usar_historico and not item.consulta.erro:
                retrato = historico.retrato(item.como_dicionario())
                item.mudancas = historico.comparar(estado_anterior.get(cnpj), retrato)
                item.situacao_historico = historico.situacao(item.mudancas)

            precisa_comprovante = item.html and (
                salvar_comprovante_em_dia or item.veredito.status != EM_DIA
            )
            if precisa_comprovante:
                caminho = config.PASTA_COMPROVANTES / f"{carimbo}_{cnpj}.html"
                caminho.write_text(item.html, encoding="utf-8")
                item.arquivo_comprovante = caminho.name

            execucao.itens.append(item)
            execucao.indice = posicao
            if ao_progredir:
                ao_progredir(execucao)

            if posicao < len(lista) and not execucao.cancelado:
                pausa_entre_consultas()
    finally:
        if sessao is not None:
            sessao.fechar()

    if usar_historico and execucao.itens:
        historico.registrar([i.como_dicionario() for i in execucao.itens])

    execucao.concluido = True
    execucao.fim = datetime.now()
    if execucao.erro_fatal:
        execucao.mensagem = f"Lote interrompido: {execucao.erro_fatal}"
    elif execucao.cancelado:
        execucao.mensagem = "Lote cancelado pelo operador."
    else:
        execucao.mensagem = "Consulta concluida."
    if ao_progredir:
        ao_progredir(execucao)
    return execucao


def salvar_json(execucao: Execucao, caminho) -> None:
    dados = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "total": execucao.total,
        "contagem": execucao.contagem(),
        "resultados": [i.como_dicionario() for i in execucao.resultados_ordenados()],
    }
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
