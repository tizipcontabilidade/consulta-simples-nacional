# Consulta Simples Nacional

Sistema local para consultar CNPJs — um a um ou em lote — no portal
**Consulta Optantes** do Simples Nacional (Receita Federal) e informar:

- situação atual no Simples Nacional e no SIMEI;
- **eventos futuros** (ex.: `Exclusão de Ofício - Débitos`, com data de efeito);
- **exclusões e desenquadramentos** em períodos anteriores;
- períodos como MEI Transportador Autônomo de Cargas;
- **o que mudou** desde a consulta anterior de cada CNPJ;
- razão social e data/hora da consulta.

CNPJ **em dia** (optante, sem evento futuro e sem histórico de saída) entra
apenas como uma linha no resumo — sem detalhamento e sem comprovante.

---

## Para a equipe: instalar e usar

Baixe a versão mais recente em
[Releases](https://github.com/tizipcontabilidade/consulta-simples-nacional/releases/latest)
— `...-setup.exe` para instalar, ou `...-portatil.zip` para rodar sem instalação
(inclusive de um compartilhamento de rede).

> Enquanto o repositório for privado, só quem tem acesso a ele consegue baixar
> pelo link. Para quem não tem conta no GitHub, distribua o arquivo direto.

1. Rode `ConsultaSimplesNacional-1.0.0-setup.exe`.
   Não precisa de administrador — instala na pasta do usuário.
2. Abra **Consulta Simples Nacional** pelo atalho. Não aparece janela preta de
   console: o sistema sobe em segundo plano e abre a tela no navegador padrão.
3. Cole os CNPJs (um por linha, com ou sem pontuação) ou envie um `.txt`,
   `.csv` ou `.xlsx`. O sistema varre o arquivo inteiro e recolhe todo CNPJ
   válido que encontrar, sem repetir.

   **Nada é descartado em silêncio.** O que foi lido e não vira consulta sai
   listado com o motivo, na tela e no relatório, em **Não consultados** — o
   total lido sempre bate com consultados + não consultados. Cai nessa lista:

   | Entrada | Por quê |
   |---|---|
   | CPF (`NNN.NNN.NNN-NN`) | o portal só consulta CNPJ |
   | CAEPF (`NNN.NNN.NNN/NNN-NN`) | pessoa física; o portal só consulta CNPJ |
   | Número truncado (12–13 dígitos) | não fecha como CNPJ nem recolocando o zero à esquerda |
   | CNPJ repetido | já estava na lista |

   O CNPJ **alfanumérico** (letras nas 12 primeiras posições, em vigor desde
   julho de 2026) é aceito normalmente, com ou sem pontuação e em maiúsculas ou
   minúsculas. Os dois dígitos verificadores continuam numéricos.
4. Para fechar: botão **Encerrar** no topo, ou simplesmente feche a aba.

### Atualização de versão

O sistema avisa sozinho quando há versão nova. A cada 6 horas ele consulta o
release mais recente deste repositório e, se a versão publicada for maior que a
instalada, mostra uma faixa com o botão **Atualizar agora** — que baixa o
instalador anexado ao release, o abre e encerra o sistema para liberar os
arquivos. **Um lote em andamento sempre vence:** a atualização espera terminar.

Como o repositório é público, a API de releases responde sem autenticação — não
há token embutido no executável instalado em cada máquina.

Sem internet, atrás de proxy ou com a API fora do ar, o sistema simplesmente não
avisa nada: o aviso nunca atrapalha quem só quer consultar CNPJ. Para desligar o
aviso ou apontar outro repositório, use `CSN_REPOSITORIO`.

Publicar uma versão nova é publicar um release com o instalador anexado — o
`construir.ps1` imprime o comando pronto ao final do build.

### Como o sistema é encerrado

Não há console para alguém fechar por engano no meio da consulta. Enquanto a
tela estiver aberta, a página manda um sinal de vida a cada 5 segundos; se a
aba (ou o navegador) for fechada, o sistema se encerra sozinho em cerca de
30 segundos. O botão **Encerrar** faz o mesmo na hora.

**Um lote em andamento nunca é interrompido por isso**: tanto o botão quanto o
encerramento automático esperam a consulta terminar e o relatório ser gravado.
Clicar em Encerrar durante um lote devolve você para a tela de andamento.

Abrir o atalho com o sistema já rodando não sobe uma segunda cópia — apenas
traz a tela de volta.

Requisito: **Brave, Chrome ou Edge** instalado — o Edge já vem no Windows, então
na prática qualquer máquina serve. O navegador da consulta é escolhido
automaticamente, nessa ordem de preferência.

Relatórios, comprovantes e histórico ficam em
`%LOCALAPPDATA%\ConsultaSimplesNacional` (o atalho "Pasta de relatórios" no menu
Iniciar leva direto lá). Desinstalar **não apaga** esses dados.

### Sobre o captcha

O botão "Consultar" do portal é protegido por **hCaptcha**. Por isso a consulta
roda em um navegador real e visível, com um perfil próprio. Na maioria das vezes
o hCaptcha passa sozinho; quando o portal recusa a verificação, o sistema
repete o CNPJ até 3 vezes com intervalo crescente, e se aparecer um desafio na
tela, a página de andamento avisa — **você resolve na janela do navegador** e o
lote continua automaticamente. Nada no sistema tenta burlar a verificação.

Consequência prática: rode os lotes com a máquina desbloqueada. Entre uma
consulta e outra há uma pausa aleatória de 4 a 8 segundos.

---

## Linha de comando

Mesmo motor da interface, para automação:

```bash
consultar.exe --arquivo minha-carteira.txt --formato xlsx
```

O `consultar.exe` (com console, instalado ao lado do principal) é a versão de
linha de comando; o `ConsultaSimplesNacional.exe` é só a interface.

| Opção | O que faz |
|---|---|
| `--arquivo`, `-a` | lista de CNPJs em `.txt`, `.csv` ou `.xlsx` |
| `--formato`, `-f` | `xlsx` (padrão), `csv`, `json` ou `nenhum` |
| `--saida`, `-s` | pasta onde gravar o relatório |
| `--somente-mudancas` | relata só quem mudou desde a consulta anterior |
| `--sem-historico` | não lê nem grava o histórico de comparação |
| `--oculto` | roda sem janela (se o portal pedir captcha, o CNPJ falha) |
| `--silencioso` | imprime só o resumo final |

Códigos de saída: `0` nada a tratar · `1` há ocorrência (ou mudança) ·
`2` erro de uso · `3` falha de execução. Rodando do código-fonte, troque
`consultar.exe` por `python consultar.py`.

## Rodar sozinho todo dia

```powershell
.\agendar.ps1 -Arquivo "C:\contabil\clientes.xlsx" -Hora 08:00
```

Cria uma tarefa no Agendador do Windows que consulta a carteira e gera a
planilha **só com o que mudou**. Opções: `-Frequencia Diaria|SemanalSegunda|Mensal`,
`-Nome`, `-PastaSaida`, `-TodasAsOcorrencias` (relata tudo, não só mudanças).

A tarefa roda no seu usuário e precisa de sessão aberta — o portal exige
navegador visível. Testar na hora: `Start-ScheduledTask -TaskName "Consulta Simples Nacional"`.

## Histórico e comparação

A cada rodada o sistema guarda um retrato de cada CNPJ em
`historico/estado.json` (situação, eventos futuros, exclusões). Na rodada
seguinte compara e aponta:

- mudança de situação no Simples Nacional ou no SIMEI;
- **novo evento futuro** (o caso que mais interessa: exclusão de ofício recém-publicada);
- evento futuro que deixou de constar;
- nova exclusão ou desenquadramento.

Consulta que falhou **não** substitui o retrato anterior, para não gerar
falso "mudou" na rodada seguinte.

---

## Saídas

| Onde | O quê |
|---|---|
| Tela de resultado | Mudanças, ocorrências detalhadas e tabela compacta dos que estão em dia |
| `saidas/*.xlsx` | Aba **Resumo** (todos) e aba **Ocorrências** (só quem tem algo a tratar) |
| `saidas/*.csv` | Resumo em CSV `;` (abre direto no Excel pt-BR) |
| `saidas/*.json` | Dados completos, para integrar em outro sistema |
| `saidas/comprovantes/` | HTML da página do portal, como prova da consulta |
| `historico/estado.json` | Último retrato de cada CNPJ |

## Classificação

| Status | Quando |
|---|---|
| `ALERTA` | Existe evento futuro (exclusão de ofício, etc.) |
| `NAO OPTANTE` | Não consta como optante hoje |
| `ATENCAO` | Optante hoje, mas com exclusão/desenquadramento anterior |
| `EM DIA` | Optante, sem evento futuro e sem histórico de saída |
| `ERRO` | CNPJ inválido ou falha na consulta |

---

## Para quem mantém o sistema

```bash
instalar.bat
```

Cria `.venv` e instala as dependências. Depois:

```bash
python app.py
```

### Testes

```bash
pip install -r requirements-dev.txt
```

```bash
python -m pytest -q
```

97 testes que não tocam o portal: o navegador é dublado e as páginas vêm de
`tests/fixturas.py`. O plano completo, incluindo os testes manuais de instalador
e agendamento, está em [TESTES.md](TESTES.md).

### Gerar o executável e o instalador

```powershell
.\construir.ps1
```

Produz `dist\ConsultaSimplesNacional\` (pasta portátil, pode ser copiada para
um compartilhamento de rede e rodada direto) e
`instalador\ConsultaSimplesNacional-1.0.0-setup.exe` (~53 MB), contendo os dois
executáveis: `ConsultaSimplesNacional.exe` (sem console, interface) e
`consultar.exe` (com console, linha de comando).

Opções: `-Versao 1.1.0`, `-SomenteExecutavel`, `-GerarZip`.

Precisa do Inno Setup uma única vez:

```bash
winget install --id JRSoftware.InnoSetup -e
```

O navegador **não** é embutido — o pacote leva só o driver do Playwright e usa
o Brave/Chrome/Edge da máquina.

### Ajustes por variável de ambiente

| Variável | Para quê |
|---|---|
| `CSN_DADOS` | pasta de dados (aponte para a rede se quiser histórico compartilhado) |
| `CSN_NAVEGADOR` | caminho de um navegador específico |
| `CSN_INTERVALO_MIN` / `CSN_INTERVALO_MAX` | pausa entre consultas |
| `CSN_TENTATIVAS` | repetições quando o portal recusa o token do captcha |
| `CSN_ESPERA_CAPTCHA` | tempo de espera por um desafio resolvido na tela |
| `CSN_TOLERANCIA_SINAL` | segundos sem a tela aberta antes de o sistema se encerrar (padrão 30) |

### Estrutura

```
principal.py                ponto de entrada dos dois executaveis (janela ou console)
app.py                      interface web (Flask)
consultar.py                linha de comando
agendar.ps1                 cria a tarefa agendada
construir.ps1               gera executavel + instalador
empacotar.spec              receita do PyInstaller
instalador.iss              receita do Inno Setup
simplesnacional/
  config.py                 caminhos, navegador, pausas
  scraper.py                automacao do portal (Playwright)
  parser.py                 HTML -> dados estruturados
  analise.py                classificacao
  historico.py              retrato e comparacao entre rodadas
  lote.py                   execucao do lote e progresso
  exportar.py               Excel e CSV
templates/  static/         telas
```

## Observações

- O portal expõe apenas dados públicos de optantes; não há login nem certificado.
- A página de resultado só existe dentro da sessão que fez a consulta — não
  adianta guardar a URL `...ConsultarCnpj?vc=...`; por isso o comprovante é
  salvo em HTML.
- Um lote por vez: a consulta depende de uma única janela de navegador.

## Licença

[MIT](LICENSE) — uso, cópia, modificação e distribuição livres, mantendo o aviso
de copyright. O software é fornecido "como está", sem garantias.
