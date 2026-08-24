"""Classificacao do resultado: o que exige atencao e o que esta em dia."""
from __future__ import annotations

from dataclasses import dataclass, field

from .parser import Consulta, _normalizar

# Ordem de gravidade, do mais grave para o menos grave.
ERRO = "ERRO"
ALERTA = "ALERTA"
NAO_OPTANTE = "NAO OPTANTE"
ATENCAO = "ATENCAO"
EM_DIA = "EM DIA"

ORDEM = {ERRO: 0, ALERTA: 1, NAO_OPTANTE: 2, ATENCAO: 3, EM_DIA: 4}

ROTULOS = {
    ERRO: "Erro na consulta",
    ALERTA: "Evento futuro / exclusao programada",
    NAO_OPTANTE: "Nao optante pelo Simples Nacional",
    ATENCAO: "Optante, com historico de exclusao ou desenquadramento",
    EM_DIA: "Em dia",
}

# Termos que indicam saida do regime em um periodo ja encerrado.
_TERMOS_SAIDA = ("exclu", "desenquadr", "impedid", "cancelad")


@dataclass
class Veredito:
    """Leitura pratica do resultado de um CNPJ."""

    status: str = EM_DIA
    motivos: list = field(default_factory=list)
    exclusoes_futuras: list = field(default_factory=list)
    historico_saidas: list = field(default_factory=list)

    @property
    def em_dia(self) -> bool:
        return self.status == EM_DIA

    @property
    def rotulo(self) -> str:
        return ROTULOS.get(self.status, self.status)

    @property
    def resumo(self) -> str:
        return "; ".join(self.motivos) if self.motivos else "Sem pendencias no Simples Nacional."


def _e_saida(detalhamento: str) -> bool:
    normalizado = _normalizar(detalhamento)
    return any(termo in normalizado for termo in _TERMOS_SAIDA)


def avaliar(consulta: Consulta) -> Veredito:
    """Traduz a consulta em status, motivos e listas de ocorrencias."""
    veredito = Veredito()

    if consulta.erro:
        veredito.status = ERRO
        veredito.motivos.append(consulta.erro)
        return veredito

    for evento in consulta.eventos_futuros_sn:
        veredito.exclusoes_futuras.append(
            {"regime": "Simples Nacional", "descricao": evento.descricao, "data_efeito": evento.data_efeito}
        )
    for evento in consulta.eventos_futuros_simei:
        veredito.exclusoes_futuras.append(
            {"regime": "SIMEI", "descricao": evento.descricao, "data_efeito": evento.data_efeito}
        )

    for periodo in consulta.periodos_anteriores_sn:
        if _e_saida(periodo.detalhamento):
            veredito.historico_saidas.append(
                {
                    "regime": "Simples Nacional",
                    "periodo": f"{periodo.data_inicial} a {periodo.data_final}",
                    "detalhamento": periodo.detalhamento,
                }
            )
    for periodo in consulta.periodos_anteriores_simei:
        if _e_saida(periodo.detalhamento):
            veredito.historico_saidas.append(
                {
                    "regime": "SIMEI",
                    "periodo": f"{periodo.data_inicial} a {periodo.data_final}",
                    "detalhamento": periodo.detalhamento,
                }
            )

    if veredito.exclusoes_futuras:
        veredito.status = ALERTA
        for ocorrencia in veredito.exclusoes_futuras:
            veredito.motivos.append(
                f"{ocorrencia['regime']}: {ocorrencia['descricao']} com efeito em {ocorrencia['data_efeito']}"
            )
    elif consulta.optante is False:
        veredito.status = NAO_OPTANTE
        veredito.motivos.append(consulta.situacao_simples or "Nao optante pelo Simples Nacional")
    elif veredito.historico_saidas:
        veredito.status = ATENCAO
        for ocorrencia in veredito.historico_saidas:
            veredito.motivos.append(
                f"{ocorrencia['regime']}: {ocorrencia['detalhamento']} ({ocorrencia['periodo']})"
            )
    else:
        veredito.status = EM_DIA

    return veredito


def ordenar(itens: list) -> list:
    """Ordena pares (consulta, veredito) do mais grave para o menos grave."""
    return sorted(itens, key=lambda par: (ORDEM.get(par[1].status, 9), par[0].cnpj))
