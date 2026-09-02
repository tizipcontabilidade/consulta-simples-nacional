; Instalador do Consulta Simples Nacional.
; Compilar com:  ISCC.exe instalador.iss   (depois de gerar dist\ com o PyInstaller)

#define Nome "Consulta Simples Nacional"
#ifndef Versao
  #define Versao "1.0.3"
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
Source: "exemplos\clientes.txt"; DestDir: "{app}\exemplos"; Flags: ignoreversion onlyifdoesntexist

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
