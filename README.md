# M4A Transkriptor

Jednoduchý nástroj na lokálnu transkripciu audio súborov (M4A, MP3, WAV) do slovenčiny.

## Požiadavky

1. **Python 3.8–3.11**
2. **FFmpeg** – nainštaluj napr. cez Homebrew: `brew install ffmpeg`
3. **Whisper** – nainštaluje sa cez pip

## Spustenie

```bash
pip install -r requirements.txt
python transcript.py
```

## Použitie

1. Klikni na „Vybrať...“ a vyber M4A (alebo MP3/WAV) súbor
2. Voliteľne: zapni „Rozpoznávať rečníkov“ pre formát „Hovoriaci 1: text / Hovoriaci 2: text“
3. Klikni na „Transkribovať“
4. Transkript sa zobrazí v okne a automaticky uloží ako `.txt` a `.md` vedľa pôvodného súboru

## Export Markdown (.md)

Transkript sa automaticky exportuje aj do **Markdown** formátu – prehľadnejší, s nadpismi pre rečníkov. Súbor `.md` otvoríš na **Android** (Obsidian, Markor), **iPhone/iPad** (Notes, Bear, Obsidian), **Windows** (VS Code, Notepad++, Obsidian) alebo ktoromkoľvek zariadení s aplikáciou na Markdown.

## Rozpoznávanie rečníkov

Ak chceš formát s označením kto hovorí:
1. Zaškrtni „Rozpoznávať rečníkov“
2. Vytvor účet na [huggingface.co](https://huggingface.co)
3. Súhlas s podmienkami modelu: [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) (a súvisiacich modelov)
4. Vytvor token na [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
5. Vlož token do poľa v aplikácii

**Poznámka:** Pri prvom spustení sa stiahne model Whisper (~140 MB pre „base“). Transkripcia prebieha lokálne – žiadne dáta sa neodosielajú na internet (okrem sťahovania modelov).
