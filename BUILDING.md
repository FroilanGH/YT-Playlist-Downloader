# Cómo armar el instalador de escritorio

Esto se hace una sola vez (o cada vez que actualices la app). El resultado final
es un solo `YT_Playlist_a_MP3_Setup.exe` que le das a cualquiera, y con eso
instala la app, yt-dlp, ffmpeg y deno sin que la persona tenga que instalar
Python ni buscar nada por su cuenta.

Necesitás hacer esto en una PC con **Windows** (PyInstaller arma ejecutables
para el sistema operativo en el que corre, así que no se puede generar el
.exe de Windows desde Linux/Mac).

## Paso 1 — Preparar la carpeta de trabajo

Creá una carpeta, por ejemplo `yt-playlist-app\`, y poné adentro:

```
yt-playlist-app\
  yt_playlist_downloader.py      <- el script que ya tenés
  installer.iss                  <- el script de Inno Setup
  bin\
    yt-dlp.exe
    ffmpeg.exe
    ffprobe.exe
    deno.exe
```

- `yt-dlp.exe`: bajalo de https://github.com/yt-dlp/yt-dlp/releases (el
  archivo que se llama `yt-dlp.exe`, no el que dice `.tar` ni el de Linux).
- `ffmpeg.exe` y `ffprobe.exe`: bajalo de
  https://www.gyan.dev/ffmpeg/builds/ (build "release essentials"), y de
  adentro del zip sacá **los dos** archivos de la carpeta `bin\` (yt-dlp usa
  ffmpeg para convertir el audio y ffprobe para inspeccionar los archivos —
  necesita ambos juntos en la misma carpeta).
- `deno.exe`: bajalo de https://github.com/denoland/deno/releases, el
  archivo `deno-x86_64-pc-windows-msvc.zip`, y de adentro sacá `deno.exe`.

## Paso 2 — Instalar Python (una sola vez, en tu PC de desarrollo)

Si no lo tenés: https://www.python.org/downloads/ (tildá "Add Python to
PATH" al instalar).

Después, en una consola (cmd o PowerShell), instalá PyInstaller:

```
pip install pyinstaller
```

## Paso 3 — Empaquetar el script como .exe con PyInstaller

Parado dentro de la carpeta `yt-playlist-app\`, corré:

```
pyinstaller --onefile --windowed --name yt_playlist_downloader yt_playlist_downloader.py
```

- `--onefile`: genera un solo .exe (más simple de distribuir).
- `--windowed`: evita que se abra una consola negra atrás de la ventana.

Esto genera una carpeta `dist\` con `yt_playlist_downloader.exe` adentro.
Ese es el ejecutable que ya no necesita Python instalado en la PC que lo
reciba — PyInstaller empaquetó el intérprete adentro.

Podés probarlo directamente haciendo doble clic en
`dist\yt_playlist_downloader.exe` antes de seguir, para confirmar que abre
bien.

## Paso 4 — Instalar Inno Setup (una sola vez)

Bajalo de https://jrsoftware.org/isdl.php e instalalo (es gratis).

## Paso 5 — Compilar el instalador

Abrí `installer.iss` con Inno Setup (clic derecho > "Open with Inno Setup
Compiler", o abrilo desde el programa) y tocá **Build > Compile** (o F9).

Esto revisa que existan `dist\yt_playlist_downloader.exe` y la carpeta
`bin\` con los cuatro .exe (yt-dlp, ffmpeg, ffprobe, deno), y genera:

```
output\YT_Playlist_a_MP3_Setup.exe
```

Ese archivo es el instalador final. Cualquiera que lo corra va a tener:

- Un ícono en el Escritorio y en el Menú Inicio.
- Todo instalado en `Archivos de programa\YT Playlist a MP3\`, con la
  carpeta `bin\` adentro conteniendo yt-dlp, ffmpeg y deno.
- Un desinstalador estándar de Windows (aparece en "Agregar o quitar
  programas").

La app ya viene preparada para detectar automáticamente esa carpeta `bin\`
al lado del .exe y precargar las rutas de yt-dlp/ffmpeg solo — no hace
falta que el usuario final las configure a mano.

## Notas

- **Windows SmartScreen**: como el instalador no está firmado digitalmente
  (eso cuesta un certificado pago), es probable que la primera vez Windows
  muestre un aviso de "Editor desconocido". Es normal para instaladores
  caseros/no comerciales — el usuario tiene que tocar "Más información" >
  "Ejecutar de todas formas".
- **Actualizar yt-dlp/ffmpeg/deno más adelante**: simplemente reemplazá los
  archivos dentro de `bin\` en esta carpeta de trabajo y volvé a compilar el
  instalador (Paso 5). No hace falta repetir el Paso 3 si no cambiaste el
  código Python.
- **Tamaño del instalador**: va a pesar bastante (yt-dlp + ffmpeg + deno +
  el runtime de Python empaquetado suman fácil 150-250 MB). Es normal para
  este tipo de app todo-en-uno.
