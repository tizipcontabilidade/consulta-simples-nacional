# Segurança

## O que este sistema acessa

O Consulta Simples Nacional consulta o portal público
[Consulta Optantes](https://consopt.www8.receita.fazenda.gov.br/consultaoptantes)
da Receita Federal, em nome de quem o executa. Ele **não** usa certificado
digital, não acessa e-CAC, não faz login em nenhum sistema e não transmite dados
para servidores de terceiros.

## Onde ficam os dados

Tudo fica na máquina de quem executa:

| Conteúdo | Onde |
|---|---|
| Comprovantes e relatórios | `%LOCALAPPDATA%\ConsultaSimplesNacional\saidas` |
| Histórico de comparação | `%LOCALAPPDATA%\ConsultaSimplesNacional\historico` |
| Perfil do navegador | `%LOCALAPPDATA%\ConsultaSimplesNacional\.perfil-consulta` |

Nada disso entra no repositório: as pastas estão no `.gitignore`, e os testes
usam CNPJs sintéticos com dígito verificador válido, nunca dados de clientes.
Se for contribuir, **não** anexe planilhas, comprovantes ou relatórios reais a
issues ou pull requests.

## Captcha

O portal é protegido por hCaptcha. O sistema **não tenta burlar, resolver nem
contornar** o captcha: quando o portal exibe um desafio, o lote pausa e quem
está operando resolve na tela. Contribuições nessa direção não serão aceitas.

## Atualização automática

O sistema baixa e executa o instalador anexado ao release mais recente. Duas
salvaguardas, com testes que falham se forem removidas:

- o endereço do instalador precisa ser `https://github.com/...`;
- o download precisa ter exatamente o tamanho anunciado pela API, ou é descartado.

O instalador ainda **não é assinado digitalmente**. O aviso do SmartScreen na
primeira execução é esperado. Confira o SHA-256 publicado nas notas do release
se quiser validar o arquivo por conta própria.

## Relatar uma vulnerabilidade

Abra uma
[security advisory privada](https://github.com/tizipcontabilidade/consulta-simples-nacional/security/advisories/new)
em vez de uma issue pública. Respondemos em até 5 dias úteis.
