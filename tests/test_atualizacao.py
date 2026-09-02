"""Aviso de versao nova a partir do manifesto na pasta compartilhada.

O canal e uma pasta do Google Drive sincronizada pelo Drive para Desktop, entao
tudo aqui e leitura de arquivo local - nao ha rede para simular.
"""
from __future__ import annotations

import json

import pytest

from simplesnacional import atualizacao
from simplesnacional.versao import VERSAO


def publicar(pasta, versao="9.9.9", conteudo=b"instalador de mentira", **extra):
    """Monta uma pasta de atualizacao completa e devolve o manifesto gravado."""
    nome = f"ConsultaSimplesNacional-{versao}-setup.exe"
    (pasta / nome).write_bytes(conteudo)
    dados = {
        "versao": versao,
        "instalador": nome,
        "sha256": atualizacao.impressao_digital(pasta / nome),
        "notas": "Corrige a importacao.",
        "publicado_em": "2026-09-02",
    }
    dados.update(extra)
    (pasta / atualizacao.NOME_MANIFESTO).write_text(json.dumps(dados), encoding="utf-8")
    return dados


# ------------------------------------------------------------------ deteccao
def test_avisa_quando_ha_versao_nova(tmp_path):
    publicar(tmp_path)

    achada = atualizacao.verificar(tmp_path)

    assert achada.disponivel is True
    assert achada.instalavel is True
    assert achada.versao == "9.9.9"
    assert achada.notas == "Corrige a importacao."


def test_nao_avisa_quando_a_versao_publicada_e_a_instalada(tmp_path):
    publicar(tmp_path, versao=VERSAO)

    assert atualizacao.verificar(tmp_path).disponivel is False


def test_nao_avisa_quando_a_publicada_e_mais_velha(tmp_path):
    publicar(tmp_path, versao="0.0.1")

    assert atualizacao.verificar(tmp_path).disponivel is False


@pytest.mark.parametrize(
    "candidata, atual, esperado",
    [
        ("1.0.4", "1.0.3", True),
        ("1.0.10", "1.0.9", True),   # comparar como texto poria 1.0.10 antes
        ("1.10.0", "1.9.0", True),
        ("2.0", "1.9.9", True),
        ("1.0.3", "1.0.3", False),
        ("1.0.2", "1.0.3", False),
        ("", "1.0.3", False),
        ("sem numero", "1.0.3", False),
    ],
)
def test_comparacao_de_versao(candidata, atual, esperado):
    assert atualizacao.e_mais_nova(candidata, atual) is esperado


# --------------------------------------------------------------- tolerancia
# Drive nao montado, pasta ainda nao criada, manifesto pela metade: nada disso
# pode atrapalhar quem so quer consultar CNPJ.
def test_pasta_inexistente_nao_quebra(tmp_path):
    achada = atualizacao.verificar(tmp_path / "nao-existe")

    assert achada.disponivel is False
    assert achada.problema == ""


def test_pasta_desligada_nao_quebra():
    assert atualizacao.verificar("").disponivel is False


def test_manifesto_ilegivel_nao_quebra(tmp_path):
    (tmp_path / atualizacao.NOME_MANIFESTO).write_text("{ isto nao e json", encoding="utf-8")

    achada = atualizacao.verificar(tmp_path)

    assert achada.disponivel is False
    assert "ilegivel" in achada.problema


def test_versao_anunciada_sem_instalador_avisa_o_problema(tmp_path):
    (tmp_path / atualizacao.NOME_MANIFESTO).write_text(
        json.dumps({"versao": "9.9.9", "instalador": "que-nao-existe.exe"}), encoding="utf-8"
    )

    achada = atualizacao.verificar(tmp_path)

    assert achada.disponivel is True
    assert achada.instalavel is False, "sem o arquivo nao ha o que instalar"
    assert "nao esta na pasta" in achada.problema


# ---------------------------------------------------------------- seguranca
# Sem certificado de code signing, o SHA-256 do manifesto e a unica prova de que
# o arquivo que vai rodar e o que a TI publicou.
def test_instalador_adulterado_nao_e_aberto(tmp_path):
    publicar(tmp_path)
    achada = atualizacao.verificar(tmp_path)
    achada.instalador.write_bytes(b"outra coisa qualquer")

    problema = atualizacao.conferir(achada)

    assert "nao confere" in problema


def test_manifesto_sem_hash_nao_deixa_instalar(tmp_path):
    publicar(tmp_path, sha256="")

    assert "SHA-256" in atualizacao.conferir(atualizacao.verificar(tmp_path))


@pytest.mark.parametrize(
    "nome",
    [
        r"..\..\Windows\System32\calc.exe",
        "../../algo.exe",
        r"C:\Windows\System32\calc.exe",
        r"\\servidor\publico\algo.exe",
        "..",
    ],
)
def test_manifesto_nao_pode_apontar_para_fora_da_propria_pasta(tmp_path, nome):
    """Manifesto e arquivo em pasta compartilhada: muita gente pode escrever
    nele. Ele nao pode virar um jeito de fazer o sistema abrir qualquer .exe."""
    (tmp_path / atualizacao.NOME_MANIFESTO).write_text(
        json.dumps({"versao": "9.9.9", "instalador": nome}), encoding="utf-8"
    )

    achada = atualizacao.verificar(tmp_path)

    assert achada.instalador is None
    assert achada.instalavel is False


# ------------------------------------------------------------- lote primeiro
def test_lote_em_andamento_vence_a_atualizacao(tmp_path, monkeypatch):
    """Atualizar no meio de uma consulta perderia o trabalho ja feito - que e
    exatamente o que este sistema existe para evitar."""
    import app as aplicacao
    from simplesnacional import config, lote

    publicar(tmp_path)
    monkeypatch.setattr(config, "PASTA_ATUALIZACAO", str(tmp_path))
    monkeypatch.setattr(aplicacao, "_atualizacao_vista_em", 0.0)

    aberturas, encerramentos = [], []
    monkeypatch.setattr(aplicacao.atualizacao, "abrir_instalador",
                        lambda a: aberturas.append(a) or "")
    monkeypatch.setattr(aplicacao, "_encerrar_processo",
                        lambda atraso=0.6: encerramentos.append(atraso))

    class ThreadViva:
        def is_alive(self):
            return True

    monkeypatch.setattr(aplicacao, "_thread", ThreadViva())
    monkeypatch.setattr(aplicacao, "_atual", lote.Execucao(cnpjs=["11222333000181"]))

    resposta = aplicacao.app.test_client().post("/atualizar")

    assert aberturas == [], "o instalador nao pode abrir durante um lote"
    assert encerramentos == [], "o sistema nao pode se encerrar durante um lote"
    assert "lote em andamento" in resposta.get_data(as_text=True).lower()
