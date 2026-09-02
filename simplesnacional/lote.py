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
from .parser import (
    Consulta,
    analisar,
    formatar_cnpj,
    normalizar_cnpj,
    somente_digitos,
)
from .scraper import Sessao, pausa_entre_consultas


# Qualquer sequencia continua de caracteres de documento. E de proposito mais
# larga que a mascara oficial: o que nao virar consulta precisa aparecer no
# relatorio, e para aparecer precisa antes ser visto. Letras entram porque o
# CNPJ e alfanumerico desde julho de 2026; um pedaco sem digito nenhum e
# palavra, nao documento, e cai fora logo na entrada.
_PADRAO_CANDIDATO = re.compile(r"[0-9A-Za-z][0-9A-Za-z./-]*[0-9A-Za-z]|[0-9]")

# Estrutura do CNPJ alfanumerico (IN RFB 2.229/2024): 8 posicoes de raiz e 4 de
# ordem do estabelecimento, todas alfanumericas, e 2 digitos verificadores que
# continuam obrigatoriamente numericos.
_ESTRUTURA_CNPJ = re.compile(r"^[0-9A-Z]{12}[0-9]{2}$")

# CAEPF (produtor rural e demais pessoas fisicas equiparadas) tem 14 digitos,
# como o CNPJ, mas mascara propria: 3.3.3/3-2 contra 2.3.3/4-2 do CNPJ. A
# distincao e pela mascara, nao pelo digito verificador - o DV do CAEPF nao
# fecha por modulo 11 e nao ha como conferi-lo aqui. Sem pontuacao os dois sao
# indistinguiveis, e ai o numero segue como CNPJ e sai marcado como invalido.
_MASCARA_CAEPF = re.compile(r"^\d{3}\.\d{3}\.\d{3}/\d{3}-\d{2}$")

# CPF ainda aparece no lugar do CNPJ em parte da carteira exportada.
_MASCARA_CPF = re.compile(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$")

# Abaixo disso um numero solto e telefone, CEP, data ou codigo interno - ruido
# de planilha que nao merece aviso. De 12 caracteres para cima ja parece
# documento truncado, e ai o silencio custa caro.
_TAMANHO_SUSPEITO = 12

MOTIVO_CAEPF = "CAEPF (pessoa fisica): o portal do Simples Nacional so consulta CNPJ"
MOTIVO_CPF = "CPF (pessoa fisica): o portal do Simples Nacional so consulta CNPJ"
MOTIVO_DV_13 = "13 digitos: nem recolocando o zero a esquerda o digito verificador fecha"
MOTIVO_TAMANHO = "nao tem os 14 caracteres de um CNPJ"
MOTIVO_ESTRUTURA = "os dois ultimos caracteres do CNPJ tem de ser numericos"
MOTIVO_DV_ALFANUMERICO = (
    "14 caracteres com letra, mas o digito verificador nao fecha: "
    "parece codigo interno, nao CNPJ"
)
MOTIVO_REPETIDO = "repetido na lista"


@dataclass
class Descartado:
    """Uma entrada que nao virou consulta, e o porque."""

    bruto: str
    motivo: str

    def como_dicionario(self) -> dict:
        return {"bruto": self.bruto, "motivo": self.motivo}


@dataclass
class Leitura:
    """O que a importacao aproveitou e o que deixou de fora.

    Existe para uma conta poder ser conferida: o total lido tem de bater com o
    total consultado mais o total descartado. Lote que encolhe sem explicacao e
    a pior falha possivel aqui - o cliente some e ninguem fica sabendo.
    """

    cnpjs: list = field(default_factory=list)
    descartados: list = field(default_factory=list)

    @property
    def total_lido(self) -> int:
        return len(self.cnpjs) + len(self.descartados)

    def mesclar(self, outra: "Leitura") -> "Leitura":
        """Junta outra leitura, marcando como repetido o que ja estava aqui."""
        for cnpj in outra.cnpjs:
            if cnpj in self.cnpjs:
                self.descartados.append(Descartado(formatar_cnpj(cnpj), MOTIVO_REPETIDO))
            else:
                self.cnpjs.append(cnpj)
        self.descartados.extend(outra.descartados)
        return self

    def como_dicionario(self) -> dict:
        return {
            "total_lido": self.total_lido,
            "aproveitados": len(self.cnpjs),
            "descartados": [d.como_dicionario() for d in self.descartados],
        }


def _e_cpf(bruto: str, digitos: str) -> bool:
    """CPF pela mascara, ou 11 digitos crus cujo DV de CPF fecha.

    Exigir o DV quando vem sem pontuacao evita confundir telefone com CPF.
    """
    if _MASCARA_CPF.match(bruto):
        return True
    return len(digitos) == 11 and bruto.isdigit() and validar_cpf(digitos)


def ler(texto: str) -> Leitura:
    """Le CNPJs de texto livre guardando tambem o que nao foi aproveitado.

    Um numero de 13 digitos so entra se, com o zero a esquerda de volta, os
    digitos verificadores fecharem - o preenchimento e um palpite, e o palpite
    precisa de prova. Ja um CNPJ de 14 caracteres bem formado entra mesmo com o
    digito verificador errado: o lote o marca como invalido e ele aparece no
    resultado, que e melhor do que sumir na importacao.
    """
    leitura = Leitura()
    for bruto in _PADRAO_CANDIDATO.findall(texto or ""):
        if not any(c.isdigit() for c in bruto):
            continue  # palavra solta, nao documento

        if _MASCARA_CAEPF.match(bruto):
            leitura.descartados.append(Descartado(bruto, MOTIVO_CAEPF))
            continue

        digitos = somente_digitos(bruto)
        if _e_cpf(bruto, digitos):
            leitura.descartados.append(Descartado(bruto, MOTIVO_CPF))
            continue

        limpo = normalizar_cnpj(bruto)

        # Planilha que guarda o CNPJ como numero come o zero a esquerda. So se
        # aplica a CNPJ inteiramente numerico: celula com letra nao vira numero.
        if len(limpo) == 13 and limpo.isdigit():
            candidato = limpo.zfill(14)
            if not validar_cnpj(candidato):
                leitura.descartados.append(Descartado(bruto, MOTIVO_DV_13))
                continue
            limpo = candidato

        if len(limpo) != 14:
            # Aviso so para numero puro truncado, que e o defeito real ja visto.
            # Codigo com letra e do tamanho errado e codigo interno de planilha,
            # nao CNPJ mutilado - avisar sobre ele treinaria a equipe a ignorar
            # a lista de descartes, que e justamente o que nao pode acontecer.
            if limpo.isdigit() and len(limpo) >= _TAMANHO_SUSPEITO:
                leitura.descartados.append(Descartado(bruto, MOTIVO_TAMANHO))
            continue

        if not _ESTRUTURA_CNPJ.match(limpo):
            leitura.descartados.append(Descartado(bruto, MOTIVO_ESTRUTURA))
            continue

        # CNPJ numerico de 14 digitos com DV errado entra assim mesmo: em lista
        # de clientes e quase sempre CNPJ com erro de digitacao, e merece uma
        # linha propria no resultado. Ja um codigo com letra do tamanho certo
        # (PROTOCOLO12345 e da forma de um CNPJ) so entra se o DV provar que e
        # CNPJ - senao vira descarte, relatado mas fora da consulta.
        if not limpo.isdigit() and not validar_cnpj(limpo):
            leitura.descartados.append(Descartado(bruto, MOTIVO_DV_ALFANUMERICO))
            continue

        if limpo in leitura.cnpjs:
            leitura.descartados.append(Descartado(bruto, MOTIVO_REPETIDO))
            continue

        leitura.cnpjs.append(limpo)
    return leitura


def extrair_cnpjs(texto: str) -> list:
    """So os CNPJs aproveitados; use ler() para saber o que ficou de fora."""
    return ler(texto).cnpjs


def _valor(caractere: str) -> int:
    """Valor do caractere no calculo do DV: codigo ASCII menos 48.

    Digitos ficam com o proprio valor (0-9) e letras seguem de A=17 a Z=42.
    E por isso que o CNPJ numerico antigo continua validando exatamente como
    sempre validou - a regra nova e uma extensao da antiga, nao uma troca.
    """
    return ord(caractere) - 48


def validar_cnpj(cnpj: str) -> bool:
    """Validacao dos dois digitos verificadores, numerico ou alfanumerico.

    Modulo 11 com os mesmos pesos de sempre; muda so a conversao do caractere
    em numero. Conferido contra o exemplo da Receita: 12.ABC.345/01DE-35.
    """
    limpo = normalizar_cnpj(cnpj)
    if not _ESTRUTURA_CNPJ.match(limpo) or len(set(limpo)) == 1:
        return False
    valores = [_valor(c) for c in limpo]
    for tamanho in (12, 13):
        pesos = list(range(tamanho - 7, 1, -1)) + list(range(9, 1, -1))
        soma = sum(v * p for v, p in zip(valores[:tamanho], pesos))
        resto = soma % 11
        esperado = 0 if resto < 2 else 11 - resto
        if valores[tamanho] != esperado:
            return False
    return True


def validar_cpf(cpf: str) -> bool:
    """Validacao dos dois digitos verificadores do CPF."""
    digitos = somente_digitos(cpf)
    if len(digitos) != 11 or len(set(digitos)) == 1:
        return False
    numeros = [int(d) for d in digitos]
    for tamanho in (9, 10):
        pesos = range(tamanho + 1, 1, -1)
        soma = sum(n * p for n, p in zip(numeros[:tamanho], pesos))
        resto = (soma * 10) % 11
        esperado = 0 if resto == 10 else resto
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
    # Entradas lidas na importacao que nao viraram consulta. Viajam junto com o
    # lote para aparecerem na tela e na exportacao, nunca em silencio.
    descartados: list = field(default_factory=list)
    indice: int = 0
    mensagem: str = "Aguardando inicio."
    aguardando_captcha: bool = False
    concluido: bool = False
    cancelado: bool = False
    erro_fatal: str = ""
    # Nome do relatorio gravado em disco quando o lote terminou.
    relatorio: str = ""
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
            "relatorio": self.relatorio,
            "contagem": self.contagem(),
            "com_mudanca": len(self.com_mudanca()),
            "descartados": [d.como_dicionario() for d in self.descartados],
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
    lista = [normalizar_cnpj(c) for c in cnpjs]
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
        "descartados": [d.como_dicionario() for d in execucao.descartados],
        "resultados": [i.como_dicionario() for i in execucao.resultados_ordenados()],
    }
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
