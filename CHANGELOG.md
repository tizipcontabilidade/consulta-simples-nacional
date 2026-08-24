# Histórico de versões

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [1.0.2] — 2026-08-24

### Corrigido

- **CNPJ com zero à esquerda não é mais descartado em silêncio.** Planilha que
  guarda o CNPJ como número entrega 13 dígitos; o extrator ignorava esses casos e
  o cliente simplesmente não era consultado, sem aviso. Agora o zero é
  reconstituído, mas o CNPJ só entra no lote se os dígitos verificadores fecharem.

### Testes

- Primeiro lote de volume contra o portal real: 105 CNPJs, sem nenhuma falha e
  sem bloqueio de captcha. Resultado registrado em `TESTES.md`.

## [1.0.1] — 2026-08-24

### Adicionado

- Licença MIT, exibida também durante a instalação.
- Suíte de testes automatizados (`tests/`, 94 casos): smoke, sanity, regressão e
  aceitação de sistema, de usuário e operacional.

### Corrigido

- Lote formado apenas por CNPJs inválidos não abre mais o navegador à toa; a
  sessão passa a ser aberta sob demanda, no primeiro CNPJ que realmente vai
  ao portal.
- Falha ao abrir o navegador no meio do lote agora encerra com mensagem
  explicativa em vez de mensagem de conclusão normal.

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
