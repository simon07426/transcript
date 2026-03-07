#!/usr/bin/env python3
"""Jednoduchý transkriptor M4A na slovenský text - všetko lokálne."""

import os
import re
import subprocess
import sys
import tempfile
import time
import platform
import importlib.util
import argparse
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
import json

def text_do_markdown(text: str) -> str:
    """Konvertuje transkript do prehľadného Markdown formátu."""
    if not text.strip():
        return "# Transkript\n\n*(prázdne)*"
    # Formát "Hovoriaci 1: text" -> ## Hovoriaci 1\n\ntext
    bloky = []
    for blok in text.strip().split("\n\n"):
        m = re.match(r"^(Hovoriaci \d+):\s*(.*)$", blok, re.DOTALL)
        if m:
            bloky.append(f"## {m.group(1)}\n\n{m.group(2).strip()}")
        else:
            bloky.append(blok)
    return "# Transkript\n\n" + "\n\n".join(bloky)


def dĺžka_audia(súbor):
    """Vráti dĺžku audio súboru v sekundách (cez ffprobe)."""
    try:
        _, ffprobe_bin = over_ffmpeg()
        out = subprocess.run(
            [ffprobe_bin, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", súbor],
            capture_output=True, text=True, check=True, timeout=10
        )
        return float(out.stdout.strip())
    except Exception:
        return None


def priprav_path_pre_ffmpeg():
    """Doplní bežné macOS cesty, kde býva Homebrew FFmpeg."""
    kandidáti = ["/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin"]
    path_hodnota = os.environ.get("PATH", "")
    cesty = [c for c in path_hodnota.split(os.pathsep) if c] if path_hodnota else []
    for cesta in kandidáti:
        if Path(cesta).exists() and cesta not in cesty:
            cesty.insert(0, cesta)
    os.environ["PATH"] = os.pathsep.join(cesty)


def over_ffmpeg():
    """Overí, že ffmpeg aj ffprobe sú dostupné."""
    priprav_path_pre_ffmpeg()
    ffmpeg_bin = shutil.which("ffmpeg")
    ffprobe_bin = shutil.which("ffprobe")
    if not ffmpeg_bin or not ffprobe_bin:
        raise RuntimeError(
            "Chýba FFmpeg (ffmpeg/ffprobe).\n"
            "Nainštaluj: brew install ffmpeg\n"
            "Potom appku vypni a znova spusti."
        )
    return ffmpeg_bin, ffprobe_bin


def priprav_pyannote_assets():
    """V zabalenom .app dorovná pyannote telemetry config na miesto, kde ho balík čaká."""
    if not getattr(sys, "frozen", False):
        return
    try:
        import pyannote.audio as pyannote_audio  # type: ignore
    except Exception:
        return

    pkg_dir = Path(pyannote_audio.__file__).resolve().parent
    cieľ = pkg_dir / "telemetry" / "config.yaml"
    if cieľ.exists():
        return

    kandidáti = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        kandidáti.append(Path(meipass) / "pyannote" / "audio" / "telemetry" / "config.yaml")

    exe = Path(sys.executable).resolve()
    # .app/Contents/MacOS/<exe> -> .app/Contents/Resources/...
    kandidáti.append(exe.parent.parent / "Resources" / "pyannote" / "audio" / "telemetry" / "config.yaml")

    zdroj = next((p for p in kandidáti if p.exists()), None)
    if not zdroj:
        return

    cieľ.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(zdroj, cieľ)


CONFIG_DIR = Path.home() / ".m4a_transkriptor"
CONFIG_PATH = CONFIG_DIR / "config.json"


def load_config():
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(data: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def je_apple_silicon():
    return sys.platform == "darwin" and platform.machine() == "arm64"


def dostupné_backendy():
    """Vráti backendy v preferovanom poradí pre dané zariadenie."""
    backendy = []
    if je_apple_silicon() and importlib.util.find_spec("mlx_whisper"):
        backendy.append("mlx")
    try:
        import torch  # type: ignore
        if torch.backends.mps.is_available():
            backendy.append("mps")
        if torch.cuda.is_available():
            backendy.append("cuda")
    except Exception:
        pass
    backendy.append("cpu")
    # odstráni duplicity pri zachovaní poradia
    return list(dict.fromkeys(backendy))


def zvoľ_backend(preferovaný="auto"):
    backendy = dostupné_backendy()
    if preferovaný != "auto":
        if preferovaný in backendy:
            return preferovaný
        return backendy[0]
    return backendy[0]


def _mlx_model_name(model_názov: str) -> str:
    mapa = {
        "tiny": "mlx-community/whisper-tiny",
        "base": "mlx-community/whisper-base",
        "small": "mlx-community/whisper-small",
        "medium": "mlx-community/whisper-medium",
        "large-v3": "mlx-community/whisper-large-v3",
    }
    return mapa.get(model_názov, model_názov)


def transkribuj(
    súbor,
    model_názov="base",
    s_rečníkmi=False,
    hf_token=None,
    backend="auto",
    jazyk="auto",
    preložiť_do_en=False,
):
    """Transkribuje audio súbor do slovenčiny. S rečníkmi = formát Hovoriaci 1/2."""
    over_ffmpeg()
    backend = zvoľ_backend(backend)

    výsledok = None
    segments = []

    # Preferujeme MLX na Apple Silicon (zvyčajne najrýchlejšie na M1/M2/M3).
    if backend == "mlx":
        try:
            import mlx_whisper  # type: ignore
            výsledok = mlx_whisper.transcribe(
                str(súbor),
                path_or_hf_repo=_mlx_model_name(model_názov),
                language="sk",
            )
            segments = výsledok.get("segments", [])
        except Exception:
            backend = "mps" if "mps" in dostupné_backendy() else "cpu"

    import torch
    import whisper

    if výsledok is None:
        device = backend if backend in {"mps", "cuda", "cpu"} else "cpu"
        if device == "cpu":
            torch.set_num_threads(max(1, (os.cpu_count() or 1) - 1))
        model = whisper.load_model(model_názov, device=device)
        params = {}
        if jazyk and jazyk != "auto":
            params["language"] = jazyk
        if preložiť_do_en:
            params["task"] = "translate"
        výsledok = model.transcribe(str(súbor), **params)
        segments = výsledok.get("segments", [])
    text = (výsledok.get("text") or "").strip()

    if s_rečníkmi and segments and hf_token:
        try:
            priprav_pyannote_assets()
            from pyannote.audio import Pipeline
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-community-1",
                token=hf_token
            )
            # Pyannote na MPS niekedy produkuje NaN; používame CPU pre stabilitu
            import torch  # type: ignore
            pipeline.to(torch.device("cpu"))
            diarization = pipeline(str(súbor))

            # Zoznam (start, end, speaker) z pyannote
            speaker_segments = []
            ann = getattr(diarization, "speaker_diarization", diarization)
            for segment, _, speaker in ann.itertracks(yield_label=True):
                speaker_segments.append((segment.start, segment.end, speaker))

            def speaker_pre_segment(seg_start, seg_end):
                best_speaker, best_overlap = None, 0
                for spk_start, spk_end, speaker in speaker_segments:
                    overlap = max(0, min(seg_end, spk_end) - max(seg_start, spk_start))
                    if overlap > best_overlap:
                        best_overlap, best_speaker = overlap, speaker
                return best_speaker

            # Mapovanie SPEAKER_00 -> Hovoriaci 1
            speaker_map = {}
            riadky = []
            for seg in segments:
                seg_start = seg.get("start", 0)
                seg_end = seg.get("end", seg_start + 1)
                seg_text = (seg.get("text") or "").strip()
                if not seg_text:
                    continue
                spk = speaker_pre_segment(seg_start, seg_end) or "SPEAKER_00"
                if spk not in speaker_map:
                    speaker_map[spk] = f"Hovoriaci {len(speaker_map) + 1}"
                hovoriaci = speaker_map[spk]
                riadky.append((hovoriaci, seg_text))

            # Zlúčiť po sebe idúcich rovnakých rečníkov
            výstup = []
            predošlý = None
            for hov, txt in riadky:
                if hov == predošlý:
                    výstup[-1] = (hov, výstup[-1][1] + " " + txt)
                else:
                    výstup.append((hov, txt))
                    predošlý = hov

            text = "\n\n".join(f"{h}: {t}" for h, t in výstup)
        except Exception as e:
            text = (výsledok.get("text") or "").strip() + f"\n\n(Pozn.: Rozpoznávanie rečníkov zlyhalo: {e})"

    return text, backend


def run_transcribe_cli(vstup, výstup, model="tiny", s_rečníkmi=False, hf_token=None, backend="auto", export_md=False):
    """Spustiteľné z príkazového riadku: zapíše transkript do súboru."""
    try:
        vstup_cesta = Path(vstup)
        výstup_cesta = Path(výstup)
        if not vstup_cesta.exists():
            raise FileNotFoundError(f"Súbor neexistuje: {vstup}")
        if vstup_cesta.resolve() == výstup_cesta.resolve():
            raise ValueError("Výstup nesmie byť rovnaký súbor ako vstup.")
        if výstup_cesta.suffix.lower() in {".m4a", ".mp3", ".wav"}:
            raise ValueError("Výstup musí byť textový súbor (.txt), nie audio súbor.")
        text, použitý_backend = transkribuj(
            vstup,
            model_názov=model,
            s_rečníkmi=s_rečníkmi,
            hf_token=hf_token,
            backend=backend,
            jazyk="auto",
            preložiť_do_en=False,
        )
        výstup_cesta.write_text(text, encoding="utf-8")
        if export_md:
            výstup_cesta.with_suffix(".md").write_text(text_do_markdown(text), encoding="utf-8")
        print(f"Backend: {použitý_backend}")
        sys.exit(0)
    except Exception as e:
        Path(výstup).write_text(f"CHYBA: {e}", encoding="utf-8")
        sys.exit(1)


def main():
    try:
        import customtkinter as ctk  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Chýba customtkinter. Nainštaluj závislosti: pip install -r requirements.txt"
        ) from e

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    okno = ctk.CTk()
    okno.title("M4A Slovenský transkript")
    okno.geometry("860x740")
    okno.minsize(640, 580)

    vybraný_súbor = tk.StringVar()
    model_var = tk.StringVar(value="medium")
    backend_var = tk.StringVar(value="auto")
    jazyk_var = tk.StringVar(value="auto")
    preklad_var = tk.StringVar(value="none")
    zapamätaj_token_var = tk.BooleanVar(value=True)
    rečníci_var = tk.BooleanVar(value=False)
    config_data = load_config()
    token_var = tk.StringVar(value=config_data.get("hf_token") or os.environ.get("HF_TOKEN", ""))

    # --- Paleta ---
    bg = "#0c1222"
    card = "#151c2c"
    accent = "#3b82f6"
    accent_hover = "#2563eb"
    success = "#22c55e"
    muted = "#64748b"
    border = "#1e293b"

    okno.configure(fg_color=bg)

    # --- Scrollovateľný obsah ---
    scroll = ctk.CTkScrollableFrame(okno, fg_color="transparent")
    scroll.pack(fill=tk.BOTH, expand=True, padx=24, pady=20)

    # --- Hero ---
    hero = ctk.CTkFrame(scroll, fg_color="transparent")
    hero.pack(fill="x", pady=(0, 20))
    ctk.CTkLabel(hero, text="Transkriptor", font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w")
    ctk.CTkLabel(hero, text="Vyber audio, zvoľ nastavenia a stlač Spustiť. Výsledok uložíš ako .txt aj .md.", text_color=muted, font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(4, 0))

    # --- Karta: Výber súboru ---
    file_card = ctk.CTkFrame(scroll, fg_color=card, corner_radius=14, border_width=1, border_color=border)
    file_card.pack(fill="x", pady=(0, 12))

    file_inner = ctk.CTkFrame(file_card, fg_color="transparent")
    file_inner.pack(fill="x", padx=16, pady=14)

    ctk.CTkLabel(file_inner, text="Audio súbor", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(0, 6))

    file_row = ctk.CTkFrame(file_inner, fg_color="transparent")
    file_row.pack(fill="x")

    entry = ctk.CTkEntry(file_row, textvariable=vybraný_súbor, placeholder_text="Žiadny súbor – klikni Vybrať", height=44, corner_radius=12, border_color=border)
    entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

    def vybrať_súbor():
        súbor = filedialog.askopenfilename(
            title="Vyber audio súbor",
            filetypes=[
                ("Audio", "*.m4a *.mp3 *.wav *.flac *.aac *.ogg *.opus *.wma *.m4b *.mp4 *.mkv"),
                ("Všetky", "*.*"),
            ]
        )
        if súbor:
            vybraný_súbor.set(súbor)

    ctk.CTkButton(file_row, text="Vybrať", command=vybrať_súbor, width=110, height=44, corner_radius=12, fg_color=accent, hover_color=accent_hover).pack(side="left")

    # --- Karta: Nastavenia ---
    sett_card = ctk.CTkFrame(scroll, fg_color=card, corner_radius=14, border_width=1, border_color=border)
    sett_card.pack(fill="x", pady=(0, 12))

    sett_inner = ctk.CTkFrame(sett_card, fg_color="transparent")
    sett_inner.pack(fill="x", padx=16, pady=14)

    ctk.CTkLabel(sett_inner, text="Nastavenia", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(0, 10))

    # Riadok 1: Model, Backend
    row1 = ctk.CTkFrame(sett_inner, fg_color="transparent")
    row1.pack(fill="x", pady=4)
    ctk.CTkLabel(row1, text="Model", width=70, anchor="w", text_color=muted).pack(side="left", padx=(0, 6))
    model_combo = ctk.CTkComboBox(row1, values=["tiny", "base", "small", "medium", "large-v3"], variable=model_var, width=120, height=36, corner_radius=10, dropdown_fg_color="#1e293b", button_color=accent, button_hover_color=accent_hover)
    model_combo.pack(side="left", padx=(0, 16))
    ctk.CTkLabel(row1, text="Backend", width=70, anchor="w", text_color=muted).pack(side="left", padx=(0, 6))
    backend_combo = ctk.CTkComboBox(row1, values=["auto", "mlx", "mps", "cuda", "cpu"], variable=backend_var, width=100, height=36, corner_radius=10, dropdown_fg_color="#1e293b", button_color=accent, button_hover_color=accent_hover)
    backend_combo.pack(side="left", padx=(0, 8))
    ctk.CTkLabel(row1, text="auto = najrýchlejší", text_color=muted, font=ctk.CTkFont(size=12)).pack(side="left")

    # Riadok 2: Jazyk, Preklad
    row2 = ctk.CTkFrame(sett_inner, fg_color="transparent")
    row2.pack(fill="x", pady=4)
    ctk.CTkLabel(row2, text="Jazyk", width=70, anchor="w", text_color=muted).pack(side="left", padx=(0, 6))
    jazyk_combo = ctk.CTkComboBox(row2, values=["auto", "sk", "cs", "en", "de", "pl", "es", "fr", "it", "ru"], variable=jazyk_var, width=100, height=36, corner_radius=10, dropdown_fg_color="#1e293b", button_color=success, button_hover_color="#16a34a")
    jazyk_combo.pack(side="left", padx=(0, 16))
    ctk.CTkLabel(row2, text="Preklad", width=70, anchor="w", text_color=muted).pack(side="left", padx=(0, 6))
    preklad_combo = ctk.CTkComboBox(row2, values=["none", "english"], variable=preklad_var, width=100, height=36, corner_radius=10, dropdown_fg_color="#1e293b", button_color=success, button_hover_color="#16a34a")
    preklad_combo.pack(side="left")

    # Riadok 3: Rečníci
    row3 = ctk.CTkFrame(sett_inner, fg_color="transparent")
    row3.pack(fill="x", pady=6)
    rečníci_check = ctk.CTkCheckBox(row3, text="Rozpoznávať rečníkov (Hovoriaci 1, 2...)", variable=rečníci_var, corner_radius=8)
    rečníci_check.pack(side="left")

    # Riadok 4: Token
    row4 = ctk.CTkFrame(sett_inner, fg_color="transparent")
    row4.pack(fill="x", pady=4)
    ctk.CTkLabel(row4, text="HF token", width=70, anchor="w", text_color=muted).pack(side="left", padx=(0, 6))
    token_entry = ctk.CTkEntry(row4, textvariable=token_var, placeholder_text="hf_... (len pre rečníkov)", show="•", height=36, corner_radius=10, border_color=border)
    token_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
    zapamätaj = ctk.CTkCheckBox(row4, text="Zapamätať", variable=zapamätaj_token_var, corner_radius=6)
    zapamätaj.pack(side="left")

    # --- Karta: Transkript ---
    trans_card = ctk.CTkFrame(scroll, fg_color=card, corner_radius=14, border_width=1, border_color=border)
    trans_card.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

    trans_inner = ctk.CTkFrame(trans_card, fg_color="transparent")
    trans_inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=14)

    trans_header = ctk.CTkFrame(trans_inner, fg_color="transparent")
    trans_header.pack(fill="x", pady=(0, 6))
    ctk.CTkLabel(trans_header, text="Transkript", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")

    font_mono = ("Menlo", 12) if sys.platform == "darwin" else ("Consolas", 11)
    text = ctk.CTkTextbox(trans_inner, height=200, corner_radius=12, font=ctk.CTkFont(family=font_mono[0], size=font_mono[1]), border_width=1, border_color=border)
    text.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

    stav = tk.StringVar(value="Pripravené. Vyber súbor a stlač Spustiť.")
    lbl_stav = ctk.CTkLabel(trans_inner, textvariable=stav, text_color=muted, font=ctk.CTkFont(size=12))
    lbl_stav.pack(anchor="w", pady=(0, 4))

    progress = ctk.CTkProgressBar(trans_inner, height=6, corner_radius=3)
    progress.pack(fill="x", pady=(0, 12))
    progress.pack_forget()

    # --- Tlačidlá ---
    btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
    btn_frame.pack(fill="x", pady=(4, 0))

    btn_transkribuj = ctk.CTkButton(
        btn_frame,
        text="▶  Spustiť transkripciu",
        height=52,
        corner_radius=14,
        font=ctk.CTkFont(size=16, weight="bold"),
        fg_color=accent,
        hover_color=accent_hover,
    )
    btn_transkribuj.pack(side="left", padx=(0, 10))

    btn_zrušiť = ctk.CTkButton(btn_frame, text="Zrušiť", height=52, corner_radius=14, fg_color=muted, hover_color="#475569")
    # btn_zrušiť sa zobrazí len počas transkripcie (pack v spustiť_transkripciu)

    # Zdieľané údaje pre progress
    progress_data = {"start": 0.0, "odhad_sek": 60.0, "dokončené": False, "timer_id": None, "process": None, "output_path": None, "on_done": None}

    def formátuj_čas(sekundy):
        if sekundy < 60:
            return f"{int(sekundy)} s"
        minúty = int(sekundy // 60)
        s = int(sekundy % 60)
        return f"{minúty} min {s} s"

    def skontroluj_dokončenie():
        """Skontroluje, či subprocess skončil."""
        proc = progress_data.get("process")
        if proc and proc.poll() is not None:
            on_done = progress_data.get("on_done")
            if not on_done:
                return True
            output_path = progress_data.get("output_path")
            # Zrušené používateľom (SIGTERM / negatívny return code)
            if proc.returncode and proc.returncode < 0:
                okno.after(0, lambda: on_done(None, "Zrušené"))
                return True
            if output_path and Path(output_path).exists():
                obsah = Path(output_path).read_text(encoding="utf-8")
                if obsah.startswith("CHYBA:"):
                    okno.after(0, lambda: on_done(None, obsah[6:].strip()))
                else:
                    okno.after(0, lambda: on_done(obsah, None))
            else:
                okno.after(0, lambda: on_done(None, "Subprocess skončil bez výstupu"))
            return True
        return False

    def aktualizuj_progress():
        if progress_data["dokončené"]:
            return
        if skontroluj_dokončenie():
            return
        elapsed = time.time() - progress_data["start"]
        odhad = progress_data["odhad_sek"]
        pct = min(95, int((elapsed / odhad) * 100)) if odhad > 0 else 0
        zostáva = max(0, odhad - elapsed)

        progress.set(pct / 100)
        if elapsed > odhad:
            stav.set(f"Spracováva sa... {pct}% (odhad prekročený – {formátuj_čas(elapsed)} uplynulo)")
        else:
            stav.set(f"Prebieha transkripcia... {pct}% (~{formátuj_čas(zostáva)} zostáva)")

        progress_data["timer_id"] = okno.after(500, aktualizuj_progress)

    def zrušiť_transkripciu():
        proc = progress_data.get("process")
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()

    def spustiť_transkripciu():
        súbor = vybraný_súbor.get().strip()
        if not súbor:
            messagebox.showwarning("Upozornenie", "Najprv vyber audio súbor.")
            return
        if not Path(súbor).exists():
            messagebox.showerror("Chyba", f"Súbor neexistuje: {súbor}")
            return
        try:
            over_ffmpeg()
        except Exception as e:
            messagebox.showerror("Chýba FFmpeg", str(e))
            return

        text.delete("0.0", "end")
        progress_data["dokončené"] = False
        progress_data["start"] = time.time()
        model = model_var.get().strip() or "large-v3"
        backend = backend_var.get().strip() or "auto"
        jazyk = jazyk_var.get().strip() or "auto"
        preložiť_do_en = preklad_var.get() == "english"
        s_rečníkmi = rečníci_var.get()
        hf_token = token_var.get().strip() or None
        if zapamätaj_token_var.get():
            cfg = load_config()
            cfg["hf_token"] = hf_token or ""
            save_config(cfg)

        if s_rečníkmi and not hf_token:
            messagebox.showwarning(
                "Token potrebný",
                "Pre rozpoznávanie rečníkov potrebuješ HuggingFace token.\n\n"
                "1. Vytvor účet na huggingface.co\n"
                "2. Súhlas s podmienkami modelu: huggingface.co/pyannote/speaker-diarization-community-1\n"
                "3. Vytvor token: huggingface.co/settings/tokens\n"
                "4. Vlož token do poľa vyššie."
            )
            return

        dĺžka = dĺžka_audia(súbor)
        # large-v3 je pomalší (~1× realtime), tiny/base rýchlejšie
        koef = {"tiny": 0.2, "base": 0.3, "small": 0.5, "medium": 0.7, "large-v3": 1.0}.get(model, 0.5)
        odhad = max(30, dĺžka * koef) if dĺžka else 300
        if s_rečníkmi:
            odhad = int(odhad * 2)
        progress_data["odhad_sek"] = odhad

        progress.set(0)
        progress.pack(fill="x", pady=(0, 12))
        btn_transkribuj.configure(state="disabled")
        btn_zrušiť.pack(side="left")
        aktualizuj_progress()

        out_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        out_path = out_file.name
        out_file.close()
        progress_data["output_path"] = out_path

        if getattr(sys, "frozen", False):
            # Zabalená .app: spúšťa sa rovnaký executable bez "script_path" argumentu.
            cmd = [sys.executable, "--transcribe", súbor, out_path, model, "--backend", backend]
        else:
            script_path = Path(__file__).resolve()
            cmd = [sys.executable, str(script_path), "--transcribe", súbor, out_path, model, "--backend", backend]
        if s_rečníkmi:
            cmd.append("--rečníci")
        env = os.environ.copy()
        if hf_token:
            env["HF_TOKEN"] = hf_token
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env
        )
        progress_data["process"] = proc

        def dokončené(výsledok, chyba):
            progress_data["dokončené"] = True
            progress_data["process"] = None
            progress_data["on_done"] = None
            if progress_data["timer_id"]:
                okno.after_cancel(progress_data["timer_id"])
                progress_data["timer_id"] = None

            progress.set(1.0)
            stav.set("Hotovo")
            progress.after(500, lambda: _skryť_progress(výsledok, chyba))

        def _skryť_progress(výsledok, chyba):
            progress.pack_forget()
            btn_zrušiť.pack_forget()
            btn_transkribuj.configure(state="normal")
            if chyba:
                stav.set("Chyba!" if chyba != "Zrušené" else "Zrušené")
                if chyba == "Zrušené":
                    messagebox.showinfo("Zrušené", "Transkripcia bola zrušená.")
                else:
                    messagebox.showerror("Chyba", chyba)
            else:
                text.insert("end", výsledok)
                base = Path(súbor).with_suffix("")
                txt_cesta = base.with_suffix(".txt")
                md_cesta = base.with_suffix(".md")
                txt_cesta.write_text(výsledok, encoding="utf-8")
                md_cesta.write_text(text_do_markdown(výsledok), encoding="utf-8")
                messagebox.showinfo("Hotovo", f"Transkript uložený:\n• {txt_cesta.name}\n• {md_cesta.name}\n\nPriečinok: {base.parent}")

        progress_data["on_done"] = dokončené

    btn_transkribuj.configure(command=spustiť_transkripciu)
    btn_zrušiť.configure(command=zrušiť_transkripciu)

    okno.mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--transcribe", action="store_true", help=argparse.SUPPRESS)  # interný režim pre GUI
    parser.add_argument("--input", help="Vstupný audio súbor (.m4a/.mp3/.wav)")
    parser.add_argument("--output", help="Výstupný .txt súbor")
    parser.add_argument("--model", default="large-v3", help="Whisper model: tiny/base/small/medium/large-v3")
    parser.add_argument("--rečníci", action="store_true", help="Zapne rozpoznávanie rečníkov (vyžaduje HF token)")
    parser.add_argument("--hf-token", default=os.environ.get("HF_TOKEN"), help="HuggingFace token pre diarizáciu")
    parser.add_argument("--backend", default="auto", choices=["auto", "mlx", "mps", "cuda", "cpu"], help="Výpočtový backend")

    args, zvyšok = parser.parse_known_args()

    # Legacy interné volanie z GUI:
    # python transcript.py --transcribe <vstup> <výstup> <model> [--rečníci] [--backend X]
    if args.transcribe:
        # Ochrana proti starému chybnému volaniu v zabalenej .app, kde sa
        # omylom posunuli argumenty o script path.
        if len(zvyšok) >= 4 and Path(zvyšok[0]).suffix == ".py":
            zvyšok = zvyšok[1:]
        if len(zvyšok) < 3:
            raise SystemExit("Chýbajú argumenty pre interný režim --transcribe.")
        vstup, výstup, model = zvyšok[0], zvyšok[1], zvyšok[2]
        s_rečníkmi = args.rečníci or ("--rečníci" in zvyšok)
        run_transcribe_cli(
            vstup,
            výstup,
            model,
            s_rečníkmi=s_rečníkmi,
            hf_token=args.hf_token,
            backend=args.backend,
            export_md=False,
        )
    elif args.input and args.output:
        run_transcribe_cli(
            args.input,
            args.output,
            args.model,
            s_rečníkmi=args.rečníci,
            hf_token=args.hf_token,
            backend=args.backend,
            export_md=True,
        )
    else:
        try:
            main()
        except tk.TclError as e:
            raise SystemExit(
                "GUI sa nepodarilo spustiť (Tk/Tcl problém).\n"
                "Skús:\n"
                "1) pyenv local 3.11.11\n"
                "2) python3 -m pip install -r requirements.txt\n"
                "3) python3 transcript.py\n\n"
                f"Detail: {e}"
            )
