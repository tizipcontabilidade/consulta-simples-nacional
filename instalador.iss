; Instalador do Consulta Simples Nacional.
; Compilar com:  ISCC.exe instalador.iss   (depois de gerar dist\ com o PyInstaller)

#define Nome "Consulta Simples Nacional"
; A versao vem do construir.ps1, que a le de simplesnacionalersao.py.
; O valor abaixo e so uma rede de seguranca para compilar o .iss na mao.
#ifndef Versao
  #define Versao "1.2.0"
#endif
#define Publicador "Zip Contabilidade"
#define Executavel "ConsultaSimplesNacional.exe"

[Setup]
AppId={{8B3E0A21-4C77-4F0E-9B4E-5B0D2A1C77E1}
AppName={#Nome}
AppVersion={#Versao}
AppVerName={#Nome} {#Versao}
AppPublisher={#Publicador}
DefaultDirName={autopf}\ConsultaSimplesNacional
DefaultGroupName={#Nome}
DisableProgramGroupPage=yes
OutputDir=instalador
OutputBaseFilename=ConsultaSimplesNacional-{#Versao}-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Permite instalar sem admin (vai para a pasta do usuario) - facilita na equipe.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#Executavel}
SetupIconFile=static\logo.ico
LicenseFile=LICENSE
InfoBeforeFile=

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "atalhodesktop"; Description: "Criar atalho na area de trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "dist\ConsultaSimplesNacional\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "agendar.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
; O modelo e substituido a cada atualizacao: e exemplo do sistema, nao dado
; de ninguem. Quem agenda aponta para a propria lista, fora da instalacao.
Source: "exemplos\modelo-cnpjs.txt"; DestDir: "{app}\exemplos"; Flags: ignoreversion

[Icons]
Name: "{group}\{#Nome}"; Filename: "{app}\{#Executavel}"
Name: "{group}\Pasta de relatorios"; Filename: "{localappdata}\ConsultaSimplesNacional\saidas"
Name: "{group}\Desinstalar {#Nome}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#Nome}"; Filename: "{app}\{#Executavel}"; Tasks: atalhodesktop

[Run]
Filename: "{app}\{#Executavel}"; Description: "Abrir o {#Nome} agora"; Flags: nowait postinstall skipifsilent

[Code]
function TemNavegadorChromium(): Boolean;
var
  Bases: array[0..2] of String;
  Modelos: array[0..2] of String;
  I, J: Integer;
begin
  Result := False;
  Bases[0] := ExpandConstant('{commonpf}');
  Bases[1] := ExpandConstant('{commonpf32}');
  Bases[2] := ExpandConstant('{localappdata}');
  Modelos[0] := '\BraveSoftware\Brave-Browser\Application\brave.exe';
  Modelos[1] := '\Google\Chrome\Application\chrome.exe';
  Modelos[2] := '\Microsoft\Edge\Application\msedge.exe';
  for I := 0 to 2 do
    for J := 0 to 2 do
      if FileExists(Bases[I] + Modelos[J]) then
      begin
        Result := True;
        Exit;
      end;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if not TemNavegadorChromium() then
    Result := MsgBox(
      'Nao encontrei Brave, Chrome ou Edge nesta maquina.' + #13#10#13#10 +
      'A consulta precisa de um desses navegadores, porque o portal do Simples' + #13#10 +
      'Nacional exige verificacao (captcha) em janela visivel.' + #13#10#13#10 +
      'Deseja instalar mesmo assim?',
      mbConfirmation, MB_YESNO) = IDYES;
end;

[Code]
// Versoes ate a 1.1.0 publicavam exemplos\clientes.txt como exemplo, e o
// arquivo ficava para tras nas maquinas porque era instalado com
// onlyifdoesntexist. Aqui ele e removido - mas so quando ainda e o arquivo que
// publicamos, reconhecido pelo cabecalho que vinha nele. Se alguem trocou o
// conteudo pela propria lista, o arquivo e apenas renomeado: ninguem perde
// trabalho. O reconhecimento e pelo nosso proprio texto, nunca por um numero
// de documento - este arquivo e publico.
procedure LimparExemploAntigo();
var
  Caminho, Texto: string;
  Bruto: AnsiString;      // LoadStringFromFile so aceita AnsiString
begin
  Caminho := ExpandConstant('{app}\exemplos\clientes.txt');
  if not FileExists(Caminho) then
    Exit;

  if not LoadStringFromFile(Caminho, Bruto) then
    Exit;
  Texto := String(Bruto);

  if Pos('# Um CNPJ por linha', Texto) > 0 then
  begin
    if Length(Texto) < 200 then
      DeleteFile(Caminho)                                   // e o exemplo intacto
    else
      RenameFile(Caminho, Caminho + '.anterior');           // alguem mexeu: guarda
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    LimparExemploAntigo();
end;
