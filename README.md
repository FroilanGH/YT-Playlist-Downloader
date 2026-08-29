# Music Downloader

Aplicación de escritorio para Windows que descarga playlists o videos de
YouTube y los convierte a MP3, con nombre de artista/canción, organizados
en carpetas por playlist.

![screenshot](docs/screenshot.png)

## Características

- Descarga playlists completas o videos sueltos (pegá varias URLs, una por
  línea, y se procesan en cola).
- Convierte automáticamente a MP3 con metadata (artista/canción) usando
  [yt-dlp](https://github.com/yt-dlp/yt-dlp) y [FFmpeg](https://ffmpeg.org/).
- Cada playlist se guarda en su propia carpeta, nombrada automáticamente.
- Barra de progreso con estimación de tiempo restante.
- Consola de detalles desplegable para ver qué está pasando en cada tema.

## Descargar

La forma más simple: bajá el instalador de la
[última Release](../../releases/latest) y corré `Setup.exe`. Instala todo
lo necesario (yt-dlp, FFmpeg, y el runtime de Deno que YouTube exige
actualmente para poder extraer los videos) — no hace falta instalar Python
ni nada por separado.

> **Nota:** como el instalador no está firmado digitalmente, es probable
> que Windows SmartScreen muestre un aviso de "Editor desconocido" la
> primera vez. Es normal para instaladores personales/no comerciales —
> tocá "Más información" → "Ejecutar de todas formas".

## Compilar desde el código

Si preferís armar vos mismo el ejecutable en vez de bajar la Release, ver
la guía completa en [`docs/BUILDING.md`](docs/BUILDING.md).

## Aviso

Este proyecto es una herramienta personal para uso propio (por ejemplo,
guardar copias de seguridad de tus propias playlists, o contenido con
licencia libre). Descargar contenido con derechos de autor de YouTube sin
autorización puede ir en contra de los
[Términos de Servicio de YouTube](https://www.youtube.com/t/terms) y de
las leyes de derechos de autor de tu país. El uso de esta herramienta es
responsabilidad de quien la usa.

## Licencia

[MIT](LICENSE)
