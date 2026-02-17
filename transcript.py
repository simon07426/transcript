#!/usr/bin/env python3
"""Jednoduchý transkriptor M4A na slovenský text - všetko lokálne."""

import subprocess
import sys
import tempfile
import time
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from pathlib import Path


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


def transkribuj(súbor, model_názov="base"):
    """Transkribuje audio súbor do slovenčiny pomocou Whisper."""
    import whisper
    model = whisper.load_model(model_názov)
    výsledok = model.transcribe(str(súbor), language="sk")
    return výsledok["text"]


def run_transcribe_cli(vstup, výstup, model="tiny"):
    """Spustiteľné z príkazového riadku: zapíše transkript do súboru."""
    try:
        text = transkribuj(vstup, model_názov=model)
        Path(výstup).write_text(text, encoding="utf-8")
        sys.exit(0)
    except Exception as e:
        Path(výstup).write_text(f"CHYBA: {e}", encoding="utf-8")
        sys.exit(1)


def main():
    okno = tk.Tk()
    okno.title("M4A → Slovenský transkript")
    okno.geometry("600x450")
    okno.minsize(400, 300)

    vybraný_súbor = tk.StringVar()

    # Horná časť - výber súboru
    rámec = ttk.Frame(okno, padding=10)
    rámec.pack(fill=tk.X)

    ttk.Label(rámec, text="Audio súbor:").pack(anchor=tk.W)

    výber_rámec = ttk.Frame(rámec)
    výber_rámec.pack(fill=tk.X, pady=(0, 5))

    entry = ttk.Entry(výber_rámec, textvariable=vybraný_súbor, width=50)
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

    def vybrať_súbor():
        súbor = filedialog.askopenfilename(
            title="Vyber M4A súbor",
            filetypes=[("Audio", "*.m4a *.mp3 *.wav"), ("Všetky", "*.*")]
        )
        if súbor:
            vybraný_súbor.set(súbor)

    ttk.Button(výber_rámec, text="Vybrať...", command=vybrať_súbor).pack(side=tk.LEFT)

    # Výber modelu (tiny = rýchly, base = presnejší)
    model_rámec = ttk.Frame(rámec)
    model_rámec.pack(fill=tk.X, pady=(0, 5))
    ttk.Label(model_rámec, text="Model:").pack(side=tk.LEFT, padx=(0, 5))
    model_var = tk.StringVar(value="tiny")
    model_combo = ttk.Combobox(model_rámec, textvariable=model_var, values=["tiny", "base", "small"], state="readonly", width=8)
    model_combo.pack(side=tk.LEFT)
    ttk.Label(model_rámec, text=" (tiny = rýchly)").pack(side=tk.LEFT)

    # Textová oblasť pre transkript
    ttk.Label(rámec, text="Transkript:").pack(anchor=tk.W)
    text = scrolledtext.ScrolledText(rámec, wrap=tk.WORD, height=15)
    text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

    # Stav, progress bar a tlačidlo
    stav = tk.StringVar(value="Pripravené")
    ttk.Label(rámec, textvariable=stav).pack(anchor=tk.W)

    progress = ttk.Progressbar(rámec, mode="determinate", length=300, maximum=100)
    progress.pack(fill=tk.X, pady=(5, 5))
    progress.pack_forget()  # Skrytý na začiatku

    btn_transkribuj = ttk.Button(rámec, text="Transkribovať")
    btn_zrušiť = ttk.Button(rámec, text="Zrušiť")

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

        progress["value"] = pct
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

        text.delete(1.0, tk.END)
        progress_data["dokončené"] = False
        progress_data["start"] = time.time()
        model = model_var.get().strip() or "tiny"

        dĺžka = dĺžka_audia(súbor)
        progress_data["odhad_sek"] = max(30, dĺžka * 0.4) if dĺžka else 180

        progress["value"] = 0
        progress.pack(fill=tk.X, pady=(5, 5))
        btn_transkribuj.config(state=tk.DISABLED)
        btn_zrušiť.pack(pady=5)
        aktualizuj_progress()

        out_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        out_path = out_file.name
        out_file.close()
        progress_data["output_path"] = out_path

        script_path = Path(__file__).resolve()
        proc = subprocess.Popen(
            [sys.executable, str(script_path), "--transcribe", súbor, out_path, model],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        progress_data["process"] = proc

        def dokončené(výsledok, chyba):
            progress_data["dokončené"] = True
            progress_data["process"] = None
            progress_data["on_done"] = None
            if progress_data["timer_id"]:
                okno.after_cancel(progress_data["timer_id"])
                progress_data["timer_id"] = None

            progress["value"] = 100
            stav.set("Hotovo")
            progress.after(500, lambda: _skryť_progress(výsledok, chyba))

        def _skryť_progress(výsledok, chyba):
            progress.pack_forget()
            btn_zrušiť.pack_forget()
            btn_transkribuj.config(state=tk.NORMAL)
            if chyba:
                stav.set("Chyba!" if chyba != "Zrušené" else "Zrušené")
                if chyba == "Zrušené":
                    messagebox.showinfo("Zrušené", "Transkripcia bola zrušená.")
                else:
                    messagebox.showerror("Chyba", chyba)
            else:
                text.insert(tk.END, výsledok)
                txt_cesta = Path(súbor).with_suffix(".txt")
                txt_cesta.write_text(výsledok, encoding="utf-8")
                messagebox.showinfo("Hotovo", f"Transkript uložený do:\n{txt_cesta}")

        progress_data["on_done"] = dokončené

    btn_transkribuj.config(command=spustiť_transkripciu)
    btn_transkribuj.pack(pady=5)
    btn_zrušiť.config(command=zrušiť_transkripciu)

    okno.mainloop()


if __name__ == "__main__":
    if len(sys.argv) >= 5 and sys.argv[1] == "--transcribe":
        run_transcribe_cli(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        main()
