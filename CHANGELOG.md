# Histórico de versões

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [1.0.0] — 2026-08-24

Primeira versão distribuível.

### Adicionado

- Consulta de CNPJs, individual ou em lote, no portal Consulta Optantes do
  Simples Nacional (colar lista ou enviar `.txt`, `.csv`, `.xlsx`).
- Relatório de eventos futuros (exclusão de ofício), exclusões e
  desenquadramentos anteriores e situação atual no Simples Nacional e no SIMEI.
- Classificação em `ALERTA`, `NAO OPTANTE`, `ATENCAO`, `EM DIA` e `ERRO`;
  CNPJ em dia entra apenas no resumo, sem detalhamento.
- Histórico por CNPJ com comparação entre rodadas, apontando o que mudou.
- Exportação em Excel (abas Resumo e Ocorrências), CSV e JSON, com comprovante
  HTML das ocorrências.
- Interface web local, encerrada pelo botão **Encerrar** ou pelo fechamento da
  aba; nunca durante um lote em andamento.
- Linha de comando `consultar.exe` e script `agendar.ps1` para execução diária
  pelo Agendador de Tarefas do Windows.
- Instalador para Windows (sem exigir administrador) e versão portátil.

### Notas

- O instalador ainda não é assinado digitalmente: o SmartScreen avisa na
  primeira execução em cada máquina.
- A consulta depende de navegador visível por causa do hCaptcha do portal.
