# Histórico de versões

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [1.1.0] — 2026-09-02

Numerada como *minor* e não *patch*: além das correções, a versão traz
suporte ao CNPJ alfanumérico e o aviso de atualização.

### Corrigido

- **Importação não descarta mais nenhuma entrada em silêncio.** O extrator só
  reconhecia a máscara oficial do CNPJ; qualquer entrada com máscara diferente
  desaparecia sem aviso — era a causa da planilha de 110 CNPJs virar 106. Agora
  toda sequência de 12 dígitos ou mais que é lida vira consulta ou vira linha de
  descarte com o motivo, e o total lido tem de bater com consultados + descartados.
  Repetições também deixam de sumir caladas: passam a ser relatadas.
- **Guia em branco não trava mais o lote.** Uma segunda aba aberta por cima da
  consulta (boas-vindas do navegador, restauração de sessão) roubava o foco, e o
  hCaptcha não monta o widget em aba de fundo — o lote parecia travado até alguém
  fechar a aba na mão. A sessão agora abre com `--no-first-run`, descarta
  qualquer aba extra e traz a aba da consulta para frente antes de cada CNPJ.

- **CAEPF deixa de virar erro.** Produtores rurais e demais pessoas físicas
  aparecem na carteira com 14 dígitos e máscara `NNN.NNN.NNN/NNN-NN`, e saíam
  como "dígito verificador não confere" — mandando a equipe caçar um erro que não
  existe. Passam a ser reconhecidos pela máscara e relatados como não
  consultáveis: o portal do Simples Nacional só atende CNPJ. Sem pontuação os
  dois formatos são indistinguíveis, e aí o número segue como CNPJ inválido.

- **CPF é avisado em vez de sumir.** Parte da carteira ainda sai do sistema de
  origem com CPF no lugar do CNPJ. Passa a ser reconhecido pela máscara, ou pelos
  11 dígitos crus quando o dígito verificador fecha — exigir o DV é o que separa
  CPF de telefone celular, que também tem 11 dígitos.

### Adicionado

- **Aviso de versão nova.** O sistema consulta o release mais recente deste
  repositório e mostra uma faixa com o botão **Atualizar agora**, que baixa o
  instalador anexado, o abre e se encerra para liberar os arquivos. Um lote em
  andamento sempre vence a atualização. Sendo o repositório público, a API
  responde sem autenticação — não há token embutido no executável. Sem internet
  ou com a API fora do ar, o sistema não avisa nada. A versão passa a ter fonte
  única em `simplesnacional/versao.py`, de onde o `construir.ps1` a tira para
  nomear o instalador.
- **Suporte ao CNPJ alfanumérico** (IN RFB 2.229/2024, em vigor desde julho de
  2026). As 12 primeiras posições aceitam letras de A a Z; os dois dígitos
  verificadores continuam numéricos. O cálculo do DV segue em módulo 11 com os
  mesmos pesos, convertendo cada caractere pelo código ASCII menos 48 — por isso
  todo CNPJ numérico valida exatamente como antes. Conferido contra o exemplo da
  própria Receita, `12.ABC.345/01DE-35`. Entrada em minúsculas é aceita.
- Aba **Não consultados** no relatório Excel, bloco equivalente no CSV, campo
  `descartados` no JSON e na API de estado, e seção própria na tela de resultado.
- A CLI lista o que não será consultado antes de iniciar o lote.

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
