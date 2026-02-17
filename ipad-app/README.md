# TranscriberPad – Kompletná iPadOS aplikácia

Natívna iPadOS aplikácia v SwiftUI pre transkripciu audio súborov (M4A, MP3, WAV) do slovenčiny.

## Funkcie

- ✅ **Lokálna transkripcia** – používa Apple Speech framework (SFSpeechRecognizer)
- ✅ **Podpora slovenčiny** – natívna podpora od iOS 13+
- ✅ **Jednoduché UI** – výber súboru, progress bar, zobrazenie transkriptu
- ✅ **Automatické uloženie** – transkript sa uloží ako `.txt` vedľa pôvodného súboru

## Ako vytvoriť Xcode projekt

1. **Otvor Xcode** a vytvor nový projekt:
   - Platforma: **iOS**
   - Šablóna: **App**
   - Interface: **SwiftUI**
   - Language: **Swift**
   - Názov: `TranscriberPad`
   - Bundle Identifier: napr. `com.tvojmeno.TranscriberPad`

2. **Nastavenie projektu:**
   - Deployment Target: **iPadOS 15.0** alebo vyššie
   - Device Family: **iPad** (odznač iPhone)

3. **Pridaj súbory:**
   - Skopíruj všetky `.swift` súbory z `ipad-app/` do projektu:
     - `TranscriberPadApp.swift` (nahraď existujúci)
     - `ContentView.swift` (nahraď existujúci)
     - `TranscriptionService.swift` (pridaj nový)

4. **Pridaj Info.plist nastavenia:**
   - V Xcode projekte nájdi `Info.plist` (alebo v Build Settings → Info.plist File)
   - Pridaj tieto kľúče:
     ```
     NSSpeechRecognitionUsageDescription: "Táto aplikácia používa rozpoznávanie reči na transkripciu audio súborov."
     NSMicrophoneUsageDescription: "Táto aplikácia môže používať mikrofón na nahrávanie audio pre transkripciu."
     ```
   - Alebo skopíruj obsah z `Info.plist` v tomto priečinku

5. **Povolenia:**
   - V Build Settings → Capabilities pridaj **Speech Recognition** (ak je dostupné)

## Spustenie

1. Pripoj iPad cez USB alebo použij simulátor
2. Vyber tvoje zariadenie v Xcode
3. Stlač ▶️ (Run)

**Poznámka:** Pri prvom spustení iOS môže požiadať o povolenie na rozpoznávanie reči.

## Ako to funguje

Aplikácia používa **Apple Speech framework** (`SFSpeechRecognizer`), ktorý:
- Je natívny na iOS/iPadOS
- Podporuje slovenčinu od iOS 13+
- Funguje lokálne (niektoré jazyky vyžadujú internet na prvý download modelu)
- Automaticky konvertuje audio formáty (M4A → formát, ktorý Speech rozumie)

## Rozdiely oproti Python verzii

- **Apple Speech** vs **Whisper**: Apple Speech je jednoduchší, ale môže byť menej presný než Whisper
- **Žiadne externé závislosti**: Všetko je natívne v iOS
- **Speaker diarization**: Apple Speech to nepodporuje priamo – na to by bolo potrebné použiť Whisper cez `whisper.cpp` alebo CoreML

## Vylepšenia (voliteľné)

Ak chceš lepšiu presnosť alebo speaker diarization:
- Integruj `whisper.cpp` ako C++ knižnicu
- Alebo použij CoreML model prekonvertovaný z Whisperu
- To vyžaduje komplikovanejšiu integráciu, ale poskytne lepšie výsledky
