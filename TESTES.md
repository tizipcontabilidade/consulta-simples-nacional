# Plano e resultado dos testes

Execução em 02/09/2026, sobre a versão 1.1.0 (Windows 11, Python 3.12).

```bash
python -m pytest -q
```

**139 testes automatizados, todos passando.** Os testes que dependem do portal da
Receita, do instalador e do Agendador de Tarefas são feitos à mão e estão
registrados aqui com o resultado observado.

| Tipo | Onde | Casos | Resultado |
|---|---|---|---|
| Smoke | `tests/test_smoke.py` | 19 | ✅ |
| Sanity | `tests/test_sanity.py` | 20 | ✅ |
| Regressão | `tests/test_regressao.py` | 16 | ✅ |
| Aceitação de sistema (SAT) | `tests/test_aceitacao_sistema.py` | 9 | ✅ |
| Aceitação do usuário (UAT) | `tests/test_aceitacao_usuario.py` + roteiro ao vivo | 10 + 4 | ✅ |
| Aceitação operacional (OAT) | `tests/test_aceitacao_operacional.py` + roteiro manual | 23 + 6 | ✅ |

Nenhum teste automatizado toca o portal: o navegador é substituído por uma sessão
falsa que devolve as páginas de `tests/fixturas.py`, que reproduzem a marcação real
do Consulta Optantes com **dados fictícios** — nenhum comprovante de cliente entra
no repositório.

---

## Smoke

Se um destes falha, não vale rodar o resto: todos os módulos importam, a
aplicação Flask sobe com templates e estáticos no lugar, as quatro rotas
principais respondem, a tela inicial traz formulário, botão Encerrar e sinal de
vida, os arquivos de projeto existem e a versão do instalador bate com o
CHANGELOG.

## Sanity

Cada peça isolada: validação de dígito verificador (7 casos), extração de CNPJ de
texto bagunçado, formatação; o parser sobre os cinco cenários do portal (optante
com eventos, em dia, não optante, SIMEI enquadrado, erro); a classificação nos
cinco status; e a comparação entre rodadas.

## Regressão

Cada caso nasceu de um defeito real encontrado durante a construção.

| # | Defeito original | Guarda |
|---|---|---|
| R1 | Regex guloso devolvia 1 CNPJ onde havia 3 na mesma linha | 2 testes |
| R2 | Clique antes de o hCaptcha registrar o widget → *"Erro na validação do Token"* | 4 testes: ordem espera→clique, detecção da recusa, 3 tentativas, e **não** repetir erro que não é de captcha |
| R3 | Consulta falha sobrescrevia o retrato anterior e gerava falso "mudou" | 1 teste |
| R4 | Seção "Períodos Anteriores" mapeada por posição lia tabela do SIMEI como sendo do Simples Nacional | 1 teste |
| R5 | CNPJ em dia não pode gerar comprovante nem linha detalhada | 2 testes |
| R6 | `header {}` sem escopo pintava o cabeçalho das ocorrências; `[hidden]` sem `!important` deixava botão visível | 1 teste |
| R7 | Lote abria navegador mesmo sem CNPJ válido; sessão reaproveitada no lote | 2 testes |
| R8 | CNPJ de 13 dígitos (zero à esquerda comido pela planilha) sumia do lote em silêncio | 3 testes |

## Aceitação de sistema (SAT)

Fluxo inteiro pela interface, como um usuário faria: `POST /consultar` com três
CNPJs → andamento → resultado → download nos três formatos. Verifica contagem por
status, ordem por gravidade, planilha com **Resumo** (todos) e **Ocorrências**
(sem os que estão em dia), CSV completo, JSON com a estrutura toda, comprovante
acessível, consulta por arquivo enviado, lista vazia avisando em vez de rodar e
deduplicação de CNPJ repetido.

## Aceitação do usuário (UAT)

Um teste por critério pedido, com o nome repetindo o pedido original:

- consulta de CNPJ único e em lote;
- informa desenquadramento e exclusões anteriores;
- avisa evento futuro de exclusão de ofício, com data de efeito;
- traz as demais informações do CNPJ (razão social, situações, períodos, MEI cargas);
- **CNPJ em dia aparece só no resumo**, sem detalhamento e sem comprovante;
- aponta o que mudou desde a consulta anterior, e nada aponta quando nada mudou.

### Roteiro ao vivo (portal real, build instalado)

| Verificação | Resultado |
|---|---|
| Lote de 2 CNPJs pela interface instalada | 2/2 consultados, `ALERTA: 1, NAO OPTANTE: 1` |
| Dados conferem com o que o portal mostra | razão social, optante desde 01/01/2025, **Exclusão de Ofício – Débitos → 01/01/2027**, 2 exclusões por ato administrativo, 1 desenquadramento SIMEI |
| Comprovante salvo só para quem tem ocorrência | ✅ |
| Histórico reconhece rodada repetida | `SEM MUDANCA` nos dois |

## Aceitação operacional (OAT)

Automatizado: encerramento pelo botão; **encerramento recusado durante um lote**;
página de encerrado sem sinal de vida; sinal de vida adiando o desligamento;
vigia encerrando quando ninguém olha e esperando o lote terminar; detecção de
instância já rodando e segunda instância que não sobe servidor; navegador por
variável de ambiente e fallback quando o caminho não existe; pasta de dados
redirecionável para a rede; lote sem navegador avisando em vez de travar; lote só
de inválidos sem abrir navegador; códigos de saída da CLI (0/1/2); receita do
PyInstaller com os dois executáveis (console e sem console); instalador sem exigir
administrador, com licença e em português; scripts PowerShell compilando sem erro;
dados fora da pasta de instalação; `.gitignore` protegendo dados de cliente.

### Roteiro manual (build instalado)

| Verificação | Resultado |
|---|---|
| Instalação silenciosa sem administrador | `ConsultaSimplesNacional.exe` e `consultar.exe` instalados |
| Sem janela de console | processo ativo, título de janela vazio |
| Interface responde | HTTP 200 em `127.0.0.1:5000` |
| Abrir o atalho duas vezes | continua **1** processo |
| `agendar.ps1` registra a tarefa | programa, argumentos (`--somente-mudancas`) e gatilho diário 08:00 corretos |
| Tarefa executada de fato | `LastTaskResult = 0` (nada a tratar) e, corretamente, nenhum relatório gerado |
| Encerrar pela interface | processo finalizado |
| Desinstalação | pasta removida; **dados do usuário preservados** em `%LOCALAPPDATA%` |

A tarefa de teste foi registrada com nome temporário e removida ao final.


## Teste de volume (portal real)

Duas execuções contra o portal real, com listas de CNPJs reais de uso próprio.
Os números abaixo descrevem o **comportamento do sistema**; a composição das
listas não é publicada.

| Verificação | Resultado |
|---|---|
| Lote de ~100 CNPJs (24/08/2026) | consultados integralmente, nenhuma falha |
| Lote de ~1.200 CNPJs (02/09/2026) | consultados integralmente, 1 erro de portal |
| Desafios de hCaptcha | nenhum, nas duas execuções |
| Recusas de token | nenhuma |
| Ritmo observado | ~7,5 s por CNPJ, dos quais ~6 s são a pausa configurável |

O primeiro lote fechou a lacuna de cobertura mais importante: o caminho `EM DIA`
nunca tinha sido exercitado contra o portal real, e é a regra central do sistema.

O segundo lote validou o motor de importação reescrito na 1.1.0 — inclusive a
conferência de que o total lido bate com consultados mais descartados — e mostrou
que a frequência de acesso atual continua passando limpo em volume dez vezes
maior.

Cada lote também revelou um defeito, ambos do mesmo tipo: entrada descartada em
silêncio na importação. Ver R8 (1.0.2) e R9 (1.1.0).

---

## O que os testes não cobrem

- **Comportamento do hCaptcha em volumes muito altos.** Os lotes de ~100 e
  ~1.200 passaram limpos; não há garantia acima disso — é o motivo de a pausa
  entre consultas ser configurável.
- **Mudanças de layout no portal.** O parser é guiado pelos títulos dos painéis;
  se a Receita mudar a página, os testes continuam passando (usam fixturas) e a
  consulta real quebra. Um lote com resultado inesperadamente vazio é o sintoma.
- **Assinatura digital.** O instalador não é assinado; o aviso do SmartScreen é
  esperado e não é defeito.
