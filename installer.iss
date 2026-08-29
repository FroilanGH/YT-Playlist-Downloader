; ============================================================
;  Instalador de YT Playlist -> MP3
;  Compilar con Inno Setup (https://jrsoftware.org/isinfo.php)
;
;  ANTES DE COMPILAR, la carpeta de este script debe tener:
;
;    dist\
;      yt_playlist_downloader.exe   <- generado con PyInstaller
;    bin\
;      yt-dlp.exe
;      ffmpeg.exe
;      ffprobe.exe
;      deno.exe
;
;  Ver BUILD_INSTRUCCIONES.md para el paso a paso completo.
; ============================================================

#define MyAppName "YT Playlist a MP3"
#define MyAppVersion "1.0"
#define MyAppExeName "yt_playlist_downloader.exe"

[Setup]
AppId={{B6C2B7B0-4C7E-4E6B-9B0C-YTPLAYLISTMP3}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=YT_Playlist_a_MP3_Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
; Sin firma de código: Windows SmartScreen puede avisar "Editor desconocido"
; la primera vez que se corre el instalador. Es normal en instaladores caseros.

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el Escritorio"; GroupDescription: "Accesos directos:"

[Files]
; El .exe de la app (ya compilado con PyInstaller)
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Las dependencias bundleadas: yt-dlp, ffmpeg (+ ffprobe, que yt-dlp también
; necesita) y deno.
; Deno tiene que estar en la MISMA carpeta que yt-dlp.exe para que
; yt-dlp lo detecte automáticamente (así lo pide su documentación).
Source: "bin\*"; DestDir: "{app}\bin"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
