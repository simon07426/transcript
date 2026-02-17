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
2. Klikni na „Transkribovať“
3. Transkript sa zobrazí v okne a automaticky uloží ako `.txt` vedľa pôvodného súboru

**Poznámka:** Pri prvom spustení sa stiahne model Whisper (~140 MB pre „base“). Transkripcia prebieha lokálne – žiadne dáta sa neodosielajú na internet.
