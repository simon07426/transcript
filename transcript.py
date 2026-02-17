#!/usr/bin/env python3
"""Jednoduchý transkriptor M4A na slovenský text - všetko lokálne."""

import os
import re
import subprocess
import sys
import tempfile
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

import customtkinter as ctk


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
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", súbor],
            capture_output=True, text=True, check=True, timeout=10
        )
        return float(out.stdout.strip())
    except Exception:
        return None


def transkribuj(súbor, model_názov="base", s_rečníkmi=False, hf_token=None):
    """Transkribuje audio súbor do slovenčiny. S rečníkmi = formát Hovoriaci 1/2."""
    import whisper
    model = whisper.load_model(model_názov)
    výsledok = model.transcribe(str(súbor), language="sk")
    text = výsledok["text"]
    segments = výsledok.get("segments", [])

    if s_rečníkmi and segments and hf_token:
        try:
            from pyannote.audio import Pipeline
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-community-1",
                token=hf_token
            )
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
            text = výsledok["text"] + f"\n\n(Pozn.: Rozpoznávanie rečníkov zlyhalo: {e})"

    return text


def run_transcribe_cli(vstup, výstup, model="tiny", s_rečníkmi=False, hf_token=None):
    """Spustiteľné z príkazového riadku: zapíše transkript do súboru."""
    try:
        text = transkribuj(vstup, model_názov=model, s_rečníkmi=s_rečníkmi, hf_token=hf_token)
        Path(výstup).write_text(text, encoding="utf-8")
        sys.exit(0)
    except Exception as e:
        Path(výstup).write_text(f"CHYBA: {e}", encoding="utf-8")
        sys.exit(1)


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    okno = ctk.CTk()
    okno.title("M4A → Slovenský transkript")
    okno.geometry("680x560")
    okno.minsize(480, 460)

    vybraný_súbor = tk.StringVar()
    model_var = tk.StringVar(value="large-v3")

    # Hlavný rámec s okrúhlymi rohmi
    rámec = ctk.CTkFrame(okno, fg_color="transparent")
    rámec.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    # Audio súbor
    ctk.CTkLabel(rámec, text="Audio súbor", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(0, 4))

    výber_rámec = ctk.CTkFrame(rámec, fg_color="transparent")
    výber_rámec.pack(fill="x", pady=(0, 12))

    entry = ctk.CTkEntry(výber_rámec, textvariable=vybraný_súbor, placeholder_text="Vyber súbor...", height=40, corner_radius=10)
    entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

    def vybrať_súbor():
        súbor = filedialog.askopenfilename(
            title="Vyber M4A súbor",
            filetypes=[("Audio", "*.m4a *.mp3 *.wav"), ("Všetky", "*.*")]
        )
        if súbor:
            vybraný_súbor.set(súbor)

    ctk.CTkButton(výber_rámec, text="Vybrať", command=vybrať_súbor, width=100, height=40, corner_radius=10).pack(side="left")

    # Výber modelu – CTkComboBox s viditeľnou farbou textu
    model_rámec = ctk.CTkFrame(rámec, fg_color="transparent")
    model_rámec.pack(fill="x", pady=(0, 8))
    ctk.CTkLabel(model_rámec, text="Model", font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=(0, 10))
    model_combo = ctk.CTkComboBox(
        model_rámec,
        values=["tiny", "base", "small", "medium", "large-v3"],
        variable=model_var,
        width=140,
        height=36,
        corner_radius=10,
        dropdown_fg_color="#2b2b2b",
        button_color="#3b82f6",
        button_hover_color="#2563eb",
    )
    model_combo.pack(side="left", padx=(0, 8))
    ctk.CTkLabel(model_rámec, text="(large-v3 = najpresnejší)", text_color="gray").pack(side="left")

    # Rozpoznávanie rečníkov
    rečníci_var = tk.BooleanVar(value=False)
    rečníci_check = ctk.CTkCheckBox(rámec, text="Rozpoznávať rečníkov (Hovoriaci 1, 2...)", variable=rečníci_var, corner_radius=6)
    rečníci_check.pack(anchor="w", pady=(0, 4))

    token_rámec = ctk.CTkFrame(rámec, fg_color="transparent")
    token_rámec.pack(fill="x", pady=(0, 12))
    ctk.CTkLabel(token_rámec, text="HuggingFace token (read)", text_color="gray").pack(side="left", padx=(0, 8))
    token_var = tk.StringVar(value=os.environ.get("HF_TOKEN", ""))
    token_entry = ctk.CTkEntry(token_rámec, textvariable=token_var, placeholder_text="hf_...", show="•", height=36, corner_radius=10)
    token_entry.pack(side="left", fill="x", expand=True)

    # Textová oblasť pre transkript
    ctk.CTkLabel(rámec, text="Transkript", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(12, 4))

    font_mono = ("Menlo", 12) if sys.platform == "darwin" else ("Consolas", 11)
    text = ctk.CTkTextbox(rámec, height=180, corner_radius=12, font=ctk.CTkFont(family=font_mono[0], size=font_mono[1]))
    text.pack(fill="both", expand=True, pady=(0, 12))

    # Stav a progress
    stav = tk.StringVar(value="Pripravené")
    lbl_stav = ctk.CTkLabel(rámec, textvariable=stav, text_color="gray")
    lbl_stav.pack(anchor="w", pady=(0, 4))

    progress = ctk.CTkProgressBar(rámec, height=8, corner_radius=4)
    progress.pack(fill="x", pady=(0, 12))
    progress.pack_forget()

    # Hlavné tlačidlo – veľké, výrazné
    btn_frame = ctk.CTkFrame(rámec, fg_color="transparent")
    btn_frame.pack(fill="x", pady=(8, 0))

    btn_transkribuj = ctk.CTkButton(
        btn_frame,
        text="▶  Transkribovať",
        height=48,
        corner_radius=12,
        font=ctk.CTkFont(size=16, weight="bold"),
        fg_color="#3b82f6",
        hover_color="#2563eb",
    )
    btn_transkribuj.pack(side="left", padx=(0, 10))

    btn_zrušiť = ctk.CTkButton(btn_frame, text="Zrušiť", height=48, corner_radius=12, fg_color="#6b7280", hover_color="#4b5563")
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

        text.delete("0.0", "end")
        progress_data["dokončené"] = False
        progress_data["start"] = time.time()
        model = model_var.get().strip() or "large-v3"
        s_rečníkmi = rečníci_var.get()
        hf_token = token_var.get().strip() or None

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

        script_path = Path(__file__).resolve()
        cmd = [sys.executable, str(script_path), "--transcribe", súbor, out_path, model]
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
    if len(sys.argv) >= 5 and sys.argv[1] == "--transcribe":
        vstup, výstup, model = sys.argv[2], sys.argv[3], sys.argv[4]
        s_rečníkmi = "--rečníci" in sys.argv
        hf_token = os.environ.get("HF_TOKEN") or None
        run_transcribe_cli(vstup, výstup, model, s_rečníkmi=s_rečníkmi, hf_token=hf_token)
    else:
        main()
