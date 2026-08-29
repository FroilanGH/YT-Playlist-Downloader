#!/usr/bin/env python3

import os
import re
import sys
import json
import time
import queue
import subprocess
import threading
import tkinter as tk

from tkinter import filedialog, messagebox, ttk


# ============================================================
# CONFIGURACIÓN
# ============================================================

CONFIG_FILE = os.path.join(
    os.path.expanduser("~"),
    ".yt_playlist_downloader.json"
)


def get_app_dir():
    """Carpeta donde vive el .exe instalado (o el .py si se corre sin
    empaquetar). Cuando PyInstaller arma el .exe, sys.executable apunta
    directo a él; si no, usamos la carpeta del propio script."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = get_app_dir()
BUNDLED_BIN_DIR = os.path.join(APP_DIR, "bin")


def default_bin_dir(exe_name):
    """Si el .exe (yt-dlp.exe, ffmpeg.exe) ya viene en la carpeta 'bin' al
    lado de la app instalada, la usamos como valor por defecto en vez de
    dejar el campo vacío."""
    candidate = os.path.join(BUNDLED_BIN_DIR, exe_name)
    if os.path.isfile(candidate):
        return BUNDLED_BIN_DIR
    return ""


# Líneas técnicas de yt-dlp que no le aportan nada al usuario (ruido de
# consultas internas, progreso porcentual repetido, limpieza de archivos
# temporales) — se ocultan del log para que quede más claro. Los errores y
# advertencias nunca se filtran, esto solo afecta líneas informativas.
NOISE_RE = re.compile(
    r"^\[youtube\] Extracting URL"
    r"|Downloading webpage"
    r"|Downloading .* player API JSON"
    r"|Downloading m3u8 information"
    r"|Sleeping [\d.]+ seconds"
    r"|^\[MetadataParser\]"
    r"|^\[Metadata\] Adding metadata"
    r"|Deleting original file"
    r"|^\[download\]\s+[\d.]+% of"
)


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    return {}


def save_config(data):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2
            )
    except Exception:
        pass


def sanitize_filename(name: str) -> str:
    """Quita caracteres inválidos para nombres de carpeta/archivo en Windows."""
    return re.sub(
        r'[<>:"/\\|?*]',
        "_",
        name
    ).strip()


def format_seconds(total_seconds: float) -> str:
    total_seconds = int(total_seconds)

    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)

    if h:
        return f"{h}h {m}m {s}s"

    if m:
        return f"{m}m {s}s"

    return f"{s}s"


def format_bytes(total_bytes: float) -> str:
    size = float(total_bytes)

    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"

        size /= 1024

    return f"{size:.1f} GB"


# ============================================================
# PALETA VISUAL
# ============================================================

BG_MAIN = "#12141a"
BG_CARD = "#1a1d25"
BG_INPUT = "#20242e"
BORDER = "#2b2f3a"
TEXT_PRIMARY = "#e9eaee"
TEXT_SECONDARY = "#8b93a1"
TEXT_MUTED = "#5c6270"
ACCENT = "#7c5cff"
ACCENT_HOVER = "#8f73ff"
ACCENT_PRESSED = "#6a4de0"
DANGER = "#ff5c6c"
DANGER_HOVER = "#2a1a1e"


# ============================================================
# APLICACIÓN
# ============================================================

class DownloaderApp:

    def __init__(self, root):

        self.root = root

        self.root.title("Music Downloader")
        self.root.geometry("760x780")
        self.root.minsize(680, 650)
        self.root.resizable(True, True)
        self.root.configure(bg=BG_MAIN)

        self.cfg = load_config()

        self.proc = None
        self.cancel_requested = False

        self.log_queue = queue.Queue()

        # ----------------------------------------------------
        # Variables visuales
        # ----------------------------------------------------

        self.current_song = tk.StringVar(
            value="Esperando descarga..."
        )

        self.progress_var = tk.DoubleVar(
            value=0
        )

        self.progress_text = tk.StringVar(
            value="0%"
        )

        self.song_count_text = tk.StringVar(
            value=""
        )

        self.eta_text = tk.StringVar(
            value=""
        )

        self.download_status = tk.StringVar(
            value="Listo para descargar"
        )

        # ----------------------------------------------------
        # Estado de paneles
        # ----------------------------------------------------

        self.advanced_visible = False
        self.console_visible = False

        # ----------------------------------------------------
        # Estilos
        # ----------------------------------------------------

        self.setup_styles()

        # ----------------------------------------------------
        # INTERFAZ
        # ----------------------------------------------------

        self.build_interface()

        # ----------------------------------------------------
        # Eventos
        # ----------------------------------------------------

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.on_close
        )

        self.root.after(
            150,
            self.poll_log_queue
        )

    # ========================================================
    # ESTILOS
    # ========================================================

    def setup_styles(self):

        try:
            style = ttk.Style()

            # "clam" es el único theme incluido en tkinter que permite
            # controlar los colores de fondo/texto de todos los widgets
            # (el "vista" nativo de Windows ignora casi cualquier color
            # custom), así que lo usamos como base para el look oscuro.
            style.theme_use("clam")

            style.configure(
                ".",
                background=BG_MAIN,
                foreground=TEXT_PRIMARY,
                font=("Segoe UI", 10),
                borderwidth=0,
                focuscolor=ACCENT,
            )

            # ------------------------------------------------
            # Frames
            # ------------------------------------------------

            style.configure("TFrame", background=BG_MAIN)

            style.configure(
                "Card.TFrame",
                background=BG_CARD,
            )

            # ------------------------------------------------
            # Labels
            # ------------------------------------------------

            style.configure(
                "TLabel",
                background=BG_MAIN,
                foreground=TEXT_PRIMARY,
            )

            style.configure(
                "Card.TLabel",
                background=BG_CARD,
                foreground=TEXT_PRIMARY,
            )

            style.configure(
                "Title.TLabel",
                background=BG_MAIN,
                foreground=TEXT_PRIMARY,
                font=("Segoe UI Semibold", 20),
            )

            style.configure(
                "Subtitle.TLabel",
                background=BG_MAIN,
                foreground=TEXT_SECONDARY,
                font=("Segoe UI", 10),
            )

            style.configure(
                "Hint.TLabel",
                background=BG_CARD,
                foreground=TEXT_MUTED,
                font=("Segoe UI", 9),
            )

            style.configure(
                "Progress.TLabel",
                background=BG_CARD,
                foreground=TEXT_SECONDARY,
                font=("Segoe UI", 9),
            )

            style.configure(
                "Status.TLabel",
                background=BG_CARD,
                foreground=TEXT_PRIMARY,
                font=("Segoe UI Semibold", 10),
            )

            style.configure(
                "Song.TLabel",
                background=BG_CARD,
                foreground=TEXT_SECONDARY,
                font=("Segoe UI", 11),
            )

            # ------------------------------------------------
            # Secciones (LabelFrame)
            # ------------------------------------------------

            style.configure(
                "Section.TLabelframe",
                background=BG_CARD,
                bordercolor=BORDER,
                darkcolor=BG_CARD,
                lightcolor=BG_CARD,
                relief="solid",
                borderwidth=1,
            )

            style.configure(
                "Section.TLabelframe.Label",
                background=BG_CARD,
                foreground=TEXT_SECONDARY,
                font=("Segoe UI Semibold", 9),
            )

            # ------------------------------------------------
            # Entradas de texto / combos
            # ------------------------------------------------

            style.configure(
                "TEntry",
                fieldbackground=BG_INPUT,
                foreground=TEXT_PRIMARY,
                bordercolor=BORDER,
                lightcolor=BG_INPUT,
                darkcolor=BG_INPUT,
                insertcolor=TEXT_PRIMARY,
                borderwidth=1,
                padding=6,
            )

            style.map(
                "TEntry",
                bordercolor=[("focus", ACCENT)],
            )

            style.configure(
                "TCombobox",
                fieldbackground=BG_INPUT,
                background=BG_INPUT,
                foreground=TEXT_PRIMARY,
                arrowcolor=TEXT_SECONDARY,
                bordercolor=BORDER,
                lightcolor=BG_INPUT,
                darkcolor=BG_INPUT,
                padding=5,
            )

            style.map(
                "TCombobox",
                fieldbackground=[("readonly", BG_INPUT)],
                foreground=[("readonly", TEXT_PRIMARY)],
                bordercolor=[("focus", ACCENT)],
            )

            self.root.option_add("*TCombobox*Listbox.background", BG_INPUT)
            self.root.option_add("*TCombobox*Listbox.foreground", TEXT_PRIMARY)
            self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)

            # ------------------------------------------------
            # Botones
            # ------------------------------------------------

            style.configure(
                "TButton",
                background=BG_INPUT,
                foreground=TEXT_PRIMARY,
                bordercolor=BORDER,
                lightcolor=BG_INPUT,
                darkcolor=BG_INPUT,
                borderwidth=1,
                padding=(10, 6),
                font=("Segoe UI", 9),
            )

            style.map(
                "TButton",
                background=[("active", BORDER)],
                bordercolor=[("active", TEXT_SECONDARY)],
            )

            style.configure(
                "Main.TButton",
                background=ACCENT,
                foreground="#ffffff",
                bordercolor=ACCENT,
                lightcolor=ACCENT,
                darkcolor=ACCENT,
                font=("Segoe UI Semibold", 11),
                padding=(20, 10),
            )

            style.map(
                "Main.TButton",
                background=[
                    ("pressed", ACCENT_PRESSED),
                    ("active", ACCENT_HOVER),
                ],
                bordercolor=[
                    ("pressed", ACCENT_PRESSED),
                    ("active", ACCENT_HOVER),
                ],
            )

            style.configure(
                "Cancel.TButton",
                background=BG_CARD,
                foreground=DANGER,
                bordercolor=DANGER,
                lightcolor=BG_CARD,
                darkcolor=BG_CARD,
                padding=(16, 9),
                font=("Segoe UI", 10),
            )

            style.map(
                "Cancel.TButton",
                background=[("active", DANGER_HOVER)],
                foreground=[("disabled", TEXT_MUTED)],
                bordercolor=[("disabled", BORDER)],
            )

            # ------------------------------------------------
            # Barra de progreso
            # ------------------------------------------------

            style.configure(
                "TProgressbar",
                background=ACCENT,
                troughcolor=BG_INPUT,
                bordercolor=BG_INPUT,
                lightcolor=ACCENT,
                darkcolor=ACCENT,
                thickness=8,
            )

            # ------------------------------------------------
            # Scrollbar
            # ------------------------------------------------

            style.configure(
                "TScrollbar",
                background=BG_CARD,
                troughcolor=BG_MAIN,
                bordercolor=BG_MAIN,
                arrowcolor=TEXT_SECONDARY,
                relief="flat",
            )

            style.map(
                "TScrollbar",
                background=[("active", BORDER)],
            )

        except Exception:
            pass

    # ========================================================
    # CONSTRUCCIÓN DE LA INTERFAZ
    # ========================================================

    def build_interface(self):

        # ----------------------------------------------------
        # Contenedor principal
        # ----------------------------------------------------

        main = ttk.Frame(self.root)

        main.pack(
            fill="both",
            expand=True,
            padx=24,
            pady=20
        )

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        header = ttk.Frame(main)

        header.pack(
            fill="x",
            pady=(0, 18)
        )

        ttk.Label(
            header,
            text="Music Downloader",
            style="Title.TLabel"
        ).pack(
            anchor="w"
        )

        ttk.Label(
            header,
            text="Descargá música de YouTube en formato MP3",
            style="Subtitle.TLabel"
        ).pack(
            anchor="w",
            pady=(2, 0)
        )

        # ----------------------------------------------------
        # URL
        # ----------------------------------------------------

        url_section = ttk.LabelFrame(
            main,
            text="  URL de YouTube  ",
            style="Section.TLabelframe",
            padding=14
        )

        url_section.pack(
            fill="x",
            pady=(0, 10)
        )

        self.url_text = tk.Text(
            url_section,
            height=2,
            wrap="word",
            font=("Segoe UI", 10),
            relief="flat",
            borderwidth=0,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            padx=8,
            pady=6,
        )

        self.url_text.pack(
            fill="x",
            expand=True
        )

        self.url_text.insert(
            "1.0",
            self.cfg.get(
                "last_url",
                ""
            )
        )

        ttk.Label(
            url_section,
            text="Podés pegar una playlist o varios videos, uno por línea.",
            style="Hint.TLabel"
        ).pack(
            anchor="w",
            pady=(6, 0)
        )

        # ----------------------------------------------------
        # DESTINO
        # ----------------------------------------------------

        destination_section = ttk.LabelFrame(
            main,
            text="  Carpeta de destino  ",
            style="Section.TLabelframe",
            padding=14
        )

        destination_section.pack(
            fill="x",
            pady=10
        )

        destination_row = ttk.Frame(
            destination_section,
            style="Card.TFrame"
        )

        destination_row.pack(
            fill="x"
        )

        self.outdir_var = tk.StringVar(
            value=self.cfg.get(
                "out_dir",
                os.path.join(
                    os.path.expanduser("~"),
                    "Music"
                )
            )
        )

        ttk.Entry(
            destination_row,
            textvariable=self.outdir_var,
            font=("Segoe UI", 10)
        ).pack(
            side="left",
            fill="x",
            expand=True,
            ipady=3,
        )

        ttk.Button(
            destination_row,
            text="Elegir",
            command=self.pick_outdir
        ).pack(
            side="left",
            padx=(8, 0)
        )

        # ----------------------------------------------------
        # OPCIONES
        # ----------------------------------------------------

        options_section = ttk.LabelFrame(
            main,
            text="  Opciones  ",
            style="Section.TLabelframe",
            padding=14
        )

        options_section.pack(
            fill="x",
            pady=10
        )

        quality_row = ttk.Frame(
            options_section,
            style="Card.TFrame"
        )

        quality_row.pack(
            fill="x"
        )

        ttk.Label(
            quality_row,
            text="Calidad MP3:",
            style="Card.TLabel"
        ).pack(
            side="left"
        )

        self.quality_var = tk.StringVar(
            value=self.cfg.get(
                "quality",
                "0 (mejor)"
            )
        )

        ttk.Combobox(
            quality_row,
            textvariable=self.quality_var,
            values=[
                "0 (mejor)",
                "2 (alta)",
                "5 (media)",
                "9 (baja)"
            ],
            state="readonly",
            width=15
        ).pack(
            side="left",
            padx=(8, 0)
        )

        # ----------------------------------------------------
        # CONFIGURACIÓN AVANZADA
        # ----------------------------------------------------

        self.advanced_button = ttk.Button(
            options_section,
            text="▸ Configuración avanzada",
            command=self.toggle_advanced
        )

        self.advanced_button.pack(
            anchor="w",
            pady=(14, 0)
        )

        self.advanced_frame = ttk.Frame(
            options_section,
            style="Card.TFrame"
        )

        # ----------------------------------------------------
        # yt-dlp
        # ----------------------------------------------------

        ttk.Label(
            self.advanced_frame,
            text="Carpeta con yt-dlp.exe:",
            style="Card.TLabel"
        ).grid(
            row=0,
            column=0,
            sticky="w",
            pady=(8, 3)
        )

        self.ytdlp_var = tk.StringVar(
            value=self.cfg.get("ytdlp_dir") or default_bin_dir("yt-dlp.exe")
        )

        ttk.Entry(
            self.advanced_frame,
            textvariable=self.ytdlp_var
        ).grid(
            row=1,
            column=0,
            sticky="ew",
            padx=(0, 8)
        )

        ttk.Button(
            self.advanced_frame,
            text="Elegir...",
            command=self.pick_ytdlp
        ).grid(
            row=1,
            column=1
        )

        # ----------------------------------------------------
        # FFmpeg
        # ----------------------------------------------------

        ttk.Label(
            self.advanced_frame,
            text="Carpeta con ffmpeg.exe:",
            style="Card.TLabel"
        ).grid(
            row=2,
            column=0,
            sticky="w",
            pady=(10, 3)
        )

        self.ffmpeg_var = tk.StringVar(
            value=self.cfg.get("ffmpeg_dir") or default_bin_dir("ffmpeg.exe")
        )

        ttk.Entry(
            self.advanced_frame,
            textvariable=self.ffmpeg_var
        ).grid(
            row=3,
            column=0,
            sticky="ew",
            padx=(0, 8)
        )

        ttk.Button(
            self.advanced_frame,
            text="Elegir...",
            command=self.pick_ffmpeg
        ).grid(
            row=3,
            column=1
        )

        self.advanced_frame.columnconfigure(
            0,
            weight=1
        )

        # ----------------------------------------------------
        # PROGRESO
        # ----------------------------------------------------

        progress_section = ttk.LabelFrame(
            main,
            text="  Progreso  ",
            style="Section.TLabelframe",
            padding=16
        )

        progress_section.pack(
            fill="x",
            pady=10
        )

        # Estado

        self.status_label = ttk.Label(
            progress_section,
            textvariable=self.download_status,
            style="Status.TLabel"
        )

        self.status_label.pack(
            anchor="w"
        )

        # Canción

        self.song_label = ttk.Label(
            progress_section,
            textvariable=self.current_song,
            style="Song.TLabel"
        )

        self.song_label.pack(
            anchor="w",
            pady=(4, 10)
        )

        # Barra

        self.progress_bar = ttk.Progressbar(
            progress_section,
            variable=self.progress_var,
            maximum=100,
            mode="determinate"
        )

        self.progress_bar.pack(
            fill="x",
            pady=(0, 8)
        )

        # Información

        progress_info = ttk.Frame(
            progress_section,
            style="Card.TFrame"
        )

        progress_info.pack(
            fill="x"
        )

        ttk.Label(
            progress_info,
            textvariable=self.song_count_text,
            style="Progress.TLabel"
        ).pack(
            side="left"
        )

        ttk.Label(
            progress_info,
            textvariable=self.eta_text,
            style="Progress.TLabel"
        ).pack(
            side="left",
            padx=(15, 0)
        )

        ttk.Label(
            progress_info,
            textvariable=self.progress_text,
            style="Progress.TLabel"
        ).pack(
            side="right"
        )

        # ----------------------------------------------------
        # BOTONES
        # ----------------------------------------------------

        button_frame = ttk.Frame(
            main
        )

        button_frame.pack(
            fill="x",
            pady=(4, 10)
        )

        self.start_btn = ttk.Button(
            button_frame,
            text="Descargar",
            command=self.start_download,
            style="Main.TButton"
        )

        self.start_btn.pack(
            side="left"
        )

        self.cancel_btn = ttk.Button(
            button_frame,
            text="Cancelar",
            command=self.cancel_download,
            state="disabled",
            style="Cancel.TButton"
        )

        self.cancel_btn.pack(
            side="left",
            padx=10
        )

        # ----------------------------------------------------
        # CONSOLA DESPLEGABLE
        # ----------------------------------------------------

        self.console_button = ttk.Button(
            main,
            text="▸ Mostrar detalles de descarga",
            command=self.toggle_console
        )

        self.console_button.pack(
            anchor="w",
            pady=(2, 6)
        )

        self.log_frame = ttk.Frame(
            main
        )

        self.log_box = tk.Text(
            self.log_frame,
            height=10,
            wrap="word",
            state="disabled",
            bg=BG_CARD,
            fg=TEXT_SECONDARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            font=("Cascadia Mono", 9),
            padx=10,
            pady=8,
        )

        log_scrollbar = ttk.Scrollbar(
            self.log_frame,
            orient="vertical",
            command=self.log_box.yview
        )

        self.log_box.configure(
            yscrollcommand=log_scrollbar.set
        )

        self.log_box.pack(
            side="left",
            fill="both",
            expand=True
        )

        log_scrollbar.pack(
            side="right",
            fill="y"
        )

    # ========================================================
    # CONFIGURACIÓN AVANZADA
    # ========================================================

    def toggle_advanced(self):

        if self.advanced_visible:

            self.advanced_frame.pack_forget()

            self.advanced_button.configure(
                text="▸ Configuración avanzada"
            )

            self.advanced_visible = False

        else:

            self.advanced_frame.pack(
                fill="x",
                pady=(5, 0)
            )

            self.advanced_button.configure(
                text="▼ Configuración avanzada"
            )

            self.advanced_visible = True

    # ========================================================
    # CONSOLA
    # ========================================================

    def toggle_console(self):

        if self.console_visible:

            self.log_frame.pack_forget()

            self.console_button.configure(
                text="▸ Mostrar detalles de descarga"
            )

            self.console_visible = False

        else:

            self.log_frame.pack(
                fill="both",
                expand=True,
                pady=(0, 8)
            )

            self.console_button.configure(
                text="▼ Ocultar detalles de descarga"
            )

            self.console_visible = True

    # ========================================================
    # SELECCIÓN DE CARPETAS
    # ========================================================

    def pick_ytdlp(self):

        d = filedialog.askdirectory(
            title="Elegí la carpeta que contiene yt-dlp.exe"
        )

        if d:
            self.ytdlp_var.set(d)

    def pick_ffmpeg(self):

        d = filedialog.askdirectory(
            title="Elegí la carpeta que contiene ffmpeg.exe"
        )

        if d:
            self.ffmpeg_var.set(d)

    def pick_outdir(self):

        d = filedialog.askdirectory(
            title="Elegí la carpeta de destino"
        )

        if d:
            self.outdir_var.set(d)

    # ========================================================
    # LOG
    # ========================================================

    def log(self, text, is_process_output=False):

        self.log_queue.put((text, is_process_output))

    def clear_log(self):

        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def poll_log_queue(self):

        try:

            while True:

                line, is_process_output = self.log_queue.get_nowait()

                was_at_bottom = (
                    self.log_box.yview()[1] >= 0.999
                )

                self.log_box.configure(
                    state="normal"
                )

                self.log_box.insert(
                    "end",
                    line + "\n"
                )

                if was_at_bottom:
                    self.log_box.see("end")

                self.log_box.configure(
                    state="disabled"
                )

        except queue.Empty:
            pass

        self.root.after(
            150,
            self.poll_log_queue
        )

    # ========================================================
    # VALIDACIONES
    # ========================================================

    def get_urls(self):

        raw = self.url_text.get(
            "1.0",
            "end"
        ).strip()

        return [
            line.strip()
            for line in raw.splitlines()
            if line.strip()
        ]

    def validate_and_get_config(self):

        ytdlp_dir = self.ytdlp_var.get().strip()
        ffmpeg_dir = self.ffmpeg_var.get().strip()
        out_dir = self.outdir_var.get().strip()

        ytdlp_exe = os.path.join(
            ytdlp_dir,
            "yt-dlp.exe"
        )

        if not os.path.isfile(ytdlp_exe):

            if (
                ytdlp_dir.lower().endswith("yt-dlp.exe")
                and os.path.isfile(ytdlp_dir)
            ):
                ytdlp_exe = ytdlp_dir

            else:

                messagebox.showerror(
                    "No se encontró yt-dlp.exe",
                    f"No encontré yt-dlp.exe en:\n{ytdlp_dir}"
                )

                return None

        ffmpeg_exe = os.path.join(
            ffmpeg_dir,
            "ffmpeg.exe"
        )

        if not os.path.isfile(ffmpeg_exe):

            if (
                ffmpeg_dir.lower().endswith("ffmpeg.exe")
                and os.path.isfile(ffmpeg_dir)
            ):
                ffmpeg_exe = ffmpeg_dir

            else:

                messagebox.showerror(
                    "No se encontró ffmpeg.exe",
                    f"No encontré ffmpeg.exe en:\n{ffmpeg_dir}"
                )

                return None

        if not out_dir:

            messagebox.showerror(
                "Falta carpeta de destino",
                "Elegí una carpeta de destino."
            )

            return None

        os.makedirs(
            out_dir,
            exist_ok=True
        )

        return {
            "ytdlp_exe": ytdlp_exe,
            "ffmpeg_dir": ffmpeg_dir,
            "out_dir": out_dir,
        }

    # ========================================================
    # INICIAR DESCARGA
    # ========================================================

    def start_download(self):

        urls = self.get_urls()

        if not urls:

            messagebox.showerror(
                "Falta la URL",
                "Pegá al menos una URL de playlist o video de YouTube."
            )

            return

        config = self.validate_and_get_config()

        if not config:
            return

        self.clear_log()

        # ----------------------------------------------------
        # Guardar configuración
        # ----------------------------------------------------

        save_config({
            "last_url": "\n".join(urls),
            "ytdlp_dir": self.ytdlp_var.get().strip(),
            "ffmpeg_dir": self.ffmpeg_var.get().strip(),
            "out_dir": config["out_dir"],
            "quality": self.quality_var.get(),
        })

        quality_code = self.quality_var.get().split(" ")[0]

        # ----------------------------------------------------
        # Estado visual
        # ----------------------------------------------------

        self.cancel_requested = False

        self.progress_var.set(0)
        self.progress_text.set("0%")

        self.current_song.set(
            "Preparando descarga..."
        )

        self.song_count_text.set("")
        self.eta_text.set("")

        self.download_status.set(
            "Preparando descarga..."
        )

        # ----------------------------------------------------
        # Botones
        # ----------------------------------------------------

        self.start_btn.configure(
            state="disabled"
        )

        self.cancel_btn.configure(
            state="normal"
        )

        # ----------------------------------------------------
        # Log inicial
        # ----------------------------------------------------

        if len(urls) > 1:

            self.log(
                f"=== Iniciando cola de {len(urls)} playlists/videos ==="
            )

        else:

            self.log(
                "=== Iniciando descarga ==="
            )

        # ----------------------------------------------------
        # Thread
        # ----------------------------------------------------

        t = threading.Thread(
            target=self.run_queue,
            args=(
                urls,
                config,
                quality_code
            ),
            daemon=True
        )

        t.start()

    # ========================================================
    # COLA
    # ========================================================

    def run_queue(
        self,
        urls,
        config,
        quality_code
    ):

        grand_total_items = 0
        grand_completed_items = 0
        grand_size = 0

        any_total_known = False

        processed = 0

        queue_start = time.time()

        for idx, url in enumerate(
            urls,
            start=1
        ):

            if self.cancel_requested:

                self.log(
                    "=== Cola cancelada por el usuario ==="
                )

                break

            processed = idx

            # ------------------------------------------------
            # Actualizar UI
            # ------------------------------------------------

            self.root.after(
                0,
                lambda i=idx, total=len(urls):
                    self.download_status.set(
                        f"Procesando enlace {i} de {total}"
                    )
            )

            if len(urls) > 1:

                self.log(
                    f"\n########## Link {idx} de {len(urls)}: {url} ##########"
                )

            result = self.run_single(
                url,
                config,
                quality_code
            )

            if result:

                if result["total"]:

                    grand_total_items += result["total"]

                    any_total_known = True

                grand_completed_items += result["completed"]

                grand_size += result["size"]

        queue_elapsed = time.time() - queue_start

        # ----------------------------------------------------
        # Resumen
        # ----------------------------------------------------

        if len(urls) > 1:

            self.log(
                "\n=== RESUMEN GENERAL DE LA COLA ==="
            )

            self.log(
                f"Links procesados: {processed} de {len(urls)}"
            )

            if any_total_known:

                self.log(
                    f"Temas descargados en total: "
                    f"{grand_completed_items} de "
                    f"{grand_total_items}"
                )

            else:

                self.log(
                    f"Temas descargados en total: "
                    f"{grand_completed_items}"
                )

            self.log(
                f"Tiempo total de la cola: "
                f"{format_seconds(queue_elapsed)}"
            )

            self.log(
                f"Peso total de la cola: "
                f"{format_bytes(grand_size)}"
            )

        self.root.after(
            0,
            self.on_download_finished
        )

    # ========================================================
    # DESCARGA INDIVIDUAL
    # ========================================================

    def run_single(
        self,
        url,
        config,
        quality_code
    ):

        # ----------------------------------------------------
        # Plantilla de salida
        # ----------------------------------------------------

        out_template = os.path.join(
            config["out_dir"],
            "%(playlist|Sueltos)s",
            "%(artist,uploader)s - %(track,title)s.%(ext)s"
        )

        # ----------------------------------------------------
        # COMANDO YT-DLP
        # ----------------------------------------------------

        cmd = [

            config["ytdlp_exe"],

            "-x",

            "--audio-format",
            "mp3",

            "--audio-quality",
            quality_code,

            "--embed-metadata",

            "--add-metadata",

            "--ffmpeg-location",
            config["ffmpeg_dir"],

            "--yes-playlist",

            # Reduce consultas por video, pero con respaldo: YouTube viene
            # desactivando las URLs directas de descarga ("SABR-only") de
            # forma intermitente en algunos clientes. Si el primero
            # (android, el más liviano) se queda sin URLs utilizables,
            # prueba con ios y después tv antes de resignarse a un formato
            # de peor calidad. Ver:
            # https://github.com/yt-dlp/yt-dlp/issues/12482
            "--extractor-args",
            "youtube:player_client=android,ios,tv;skip=hls",

            "--sleep-requests",
            "1",

            "--sleep-interval",
            "2",

            "--max-sleep-interval",
            "6",

            "--retries",
            "10",

            "--fragment-retries",
            "10",

            "--parse-metadata",
            "pre_process:%(title)s:%(artist)s - %(track)s",

            "-o",
            out_template,

            "--no-mtime",

            "--ignore-errors",

            "--newline",

            "--encoding",
            "utf-8",

            url,
        ]

        # ----------------------------------------------------
        # Regex
        # ----------------------------------------------------

        item_re = re.compile(
            r"Downloading item (\d+) of (\d+)"
        )

        extract_re = re.compile(
            r"^\[ExtractAudio\] Destination:\s*(.+)$"
        )

        total_items = None

        completed_items = 0

        completed_files = []

        start_time = time.time()

        try:

            # ------------------------------------------------
            # Windows
            # ------------------------------------------------

            creationflags = (
                subprocess.CREATE_NO_WINDOW
                if os.name == "nt"
                else 0
            )

            # ------------------------------------------------
            # UTF-8
            # ------------------------------------------------

            env = os.environ.copy()

            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"

            # ------------------------------------------------
            # Ejecutar
            # ------------------------------------------------

            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
                env=env
            )

            # ------------------------------------------------
            # Leer salida
            # ------------------------------------------------

            for line in self.proc.stdout:

                stripped = line.rstrip()

                # --------------------------------------------
                # Tema X de Y
                # --------------------------------------------

                m = item_re.search(
                    stripped
                )

                if m:

                    current_item = int(
                        m.group(1)
                    )

                    total_items = int(
                        m.group(2)
                    )

                    self.log(
                        f"--- Canción {current_item} de {total_items} ---"
                    )

                    self.root.after(
                        0,
                        lambda c=current_item, t=total_items:
                            self.song_count_text.set(
                                f"Canción {c} de {t}"
                            )
                    )

                    self.root.after(
                        0,
                        lambda c=current_item:
                            self.current_song.set(
                                f"Descargando canción {c}..."
                            )
                    )

                    continue

                # --------------------------------------------
                # MP3 terminado
                # --------------------------------------------

                if stripped.startswith(
                    "[ExtractAudio] Destination"
                ):

                    completed_items += 1

                    # ----------------------------------------
                    # Estimar tiempo restante en base al
                    # promedio real de lo que llevamos tardando
                    # ----------------------------------------

                    if total_items and completed_items > 0:

                        avg_per_song = (
                            (time.time() - start_time)
                            / completed_items
                        )

                        remaining = total_items - completed_items

                        eta_seconds = avg_per_song * remaining

                        if remaining > 0:

                            eta_str = (
                                f"⏱ Restante estimado: "
                                f"{format_seconds(eta_seconds)}"
                            )

                        else:

                            eta_str = ""

                        self.root.after(
                            0,
                            lambda s=eta_str:
                                self.eta_text.set(s)
                        )

                    self.root.after(
                        0,
                        lambda:
                            self.download_status.set(
                                "✓ Canción convertida a MP3"
                            )
                    )

                    m2 = extract_re.match(
                        stripped
                    )

                    if m2:

                        fpath = m2.group(1).strip()

                        completed_files.append(fpath)

                        self.log(
                            f"✓ {os.path.basename(fpath)}"
                        )

                    continue

                # --------------------------------------------
                # Empieza a bajar un tema
                # --------------------------------------------

                if stripped.startswith(
                    "[download] Destination:"
                ):

                    fname = stripped.split(
                        "Destination:", 1
                    )[1].strip()

                    self.log(
                        f"⬇ {os.path.basename(fname)}"
                    )

                    continue

                # --------------------------------------------
                # Ruido: se oculta del log
                # --------------------------------------------

                if NOISE_RE.search(stripped):

                    self.update_progress_from_line(
                        stripped,
                        total_items,
                        completed_items
                    )

                    continue

                # --------------------------------------------
                # Cualquier otra línea (errores, warnings, etc.)
                # --------------------------------------------

                self.log(
                    stripped,
                    is_process_output=True
                )

                self.update_progress_from_line(
                    stripped,
                    total_items,
                    completed_items
                )

            # ------------------------------------------------
            # Esperar proceso
            # ------------------------------------------------

            self.proc.wait()

            elapsed = (
                time.time()
                - start_time
            )

            # ------------------------------------------------
            # Calcular peso
            # ------------------------------------------------

            total_size = 0

            for fpath in completed_files:

                try:

                    total_size += os.path.getsize(
                        fpath
                    )

                except OSError:

                    pass

            # ------------------------------------------------
            # Resultados
            # ------------------------------------------------

            if total_items:

                self.log(
                    f"=== Resultado: "
                    f"{completed_items} de "
                    f"{total_items} canciones "
                    f"descargadas correctamente ==="
                )

            self.log(
                f"Tiempo total: "
                f"{format_seconds(elapsed)}"
            )

            if completed_files:

                self.log(
                    f"Peso total descargado: "
                    f"{format_bytes(total_size)}"
                )

            if self.proc.returncode == 0:

                self.log(
                    "=== Descarga completa ==="
                )

                self.log(
                    f'Revisá la carpeta: '
                    f'{config["out_dir"]}'
                )

            else:

                self.log(
                    f"=== Terminó con errores "
                    f"(código {self.proc.returncode}) ==="
                )

                if (
                    total_items
                    and completed_items < total_items
                ):

                    self.log(
                        f"Faltaron "
                        f"{total_items - completed_items} "
                        f"tema(s). Revisá las líneas "
                        f"'ERROR:' más arriba."
                    )

            return {
                "total": total_items,
                "completed": completed_items,
                "size": total_size
            }

        except FileNotFoundError as e:

            self.log(
                f"ERROR: no se pudo ejecutar "
                f"yt-dlp.exe ({e})"
            )

            return None

        except Exception as e:

            self.log(
                f"ERROR inesperado: {e}"
            )

            return None

        finally:

            self.proc = None

    # ========================================================
    # PROGRESO
    # ========================================================

    def update_progress_from_line(
        self,
        line,
        total_items,
        completed_items
    ):

        # ----------------------------------------------------
        # Detectar porcentaje
        # ----------------------------------------------------

        percent_match = re.search(
            r'(\d+(?:\.\d+)?)%',
            line
        )

        if percent_match:

            try:

                percent = float(
                    percent_match.group(1)
                )

                self.root.after(
                    0,
                    lambda p=percent:
                        self.progress_var.set(p)
                )

                self.root.after(
                    0,
                    lambda p=percent:
                        self.progress_text.set(
                            f"{p:.0f}%"
                        )
                )

                self.root.after(
                    0,
                    lambda:
                        self.download_status.set(
                            "Descargando..."
                        )
                )

            except ValueError:

                pass

        # ----------------------------------------------------
        # Detectar canción X de Y
        # ----------------------------------------------------

        item_match = re.search(
            r'Downloading item (\d+) of (\d+)',
            line
        )

        if item_match:

            current = int(
                item_match.group(1)
            )

            total = int(
                item_match.group(2)
            )

            self.root.after(
                0,
                lambda c=current, t=total:
                    self.song_count_text.set(
                        f"Canción {c} de {t}"
                    )
            )

            self.root.after(
                0,
                lambda c=current:
                    self.current_song.set(
                        f"Descargando canción {c}..."
                    )
            )

            self.root.after(
                0,
                lambda:
                    self.progress_var.set(0)
            )

            self.root.after(
                0,
                lambda:
                    self.progress_text.set("0%")
            )

    # ========================================================
    # FINALIZAR DESCARGA
    # ========================================================

    def on_download_finished(self):

        self.start_btn.configure(
            state="normal"
        )

        self.cancel_btn.configure(
            state="disabled"
        )

        self.progress_var.set(
            100
        )

        self.progress_text.set(
            "100%"
        )

        self.eta_text.set("")

        if self.cancel_requested:

            self.download_status.set(
                "✕ Descarga cancelada"
            )

            self.current_song.set(
                "La descarga fue cancelada por el usuario."
            )

        else:

            self.download_status.set(
                "✓ Descarga finalizada"
            )

            self.current_song.set(
                "Todas las canciones fueron procesadas correctamente."
            )

    # ========================================================
    # CANCELAR
    # ========================================================

    def cancel_download(self):

        self.cancel_requested = True

        self.download_status.set(
            "Cancelando descarga..."
        )

        if (
            self.proc
            and self.proc.poll() is None
        ):

            self.log(
                "Cancelando..."
            )

            pid = self.proc.pid

            try:

                if os.name == "nt":

                    subprocess.run(
                        [
                            "taskkill",
                            "/F",
                            "/T",
                            "/PID",
                            str(pid)
                        ],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )

                else:

                    self.proc.terminate()

            except Exception:

                pass

    # ========================================================
    # CERRAR
    # ========================================================

    def on_close(self):

        self.cancel_download()

        self.root.destroy()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    root = tk.Tk()

    app = DownloaderApp(
        root
    )

    root.mainloop()