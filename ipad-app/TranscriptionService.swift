import Foundation
import Speech
import AVFoundation

/// Služba pre transkripciu audio súborov pomocou Apple Speech framework.
/// Podporuje slovenčinu a funguje lokálne na zariadení.
class TranscriptionService: ObservableObject {
    @Published var isTranscribing = false
    @Published var progress: Double = 0
    @Published var statusText: String = ""
    
    private let speechRecognizer: SFSpeechRecognizer?
    
    init() {
        // Inicializácia s podporou slovenčiny
        speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "sk_SK"))
    }
    
    /// Transkribuje audio súbor do textu.
    /// - Parameter url: URL audio súboru (M4A, MP3, WAV, atď.)
    /// - Returns: Transkriptovaný text
    func transcribe(audioURL: URL) async throws -> String {
        guard let recognizer = speechRecognizer, recognizer.isAvailable else {
            throw TranscriptionError.recognizerNotAvailable
        }
        
        await MainActor.run {
            isTranscribing = true
            statusText = "Načítavam audio súbor…"
            progress = 0.1
        }
        
        // Konverzia audio súboru na formát, ktorý Speech framework rozumie
        let audioFile = try await prepareAudioFile(url: audioURL)
        
        await MainActor.run {
            statusText = "Prebieha transkripcia…"
            progress = 0.3
        }
        
        let request = SFSpeechURLRecognitionRequest(url: audioFile)
        request.shouldReportPartialResults = true
        
        return try await withCheckedThrowingContinuation { continuation in
            recognizer.recognitionTask(with: request) { [weak self] result, error in
                if let error = error {
                    continuation.resume(throwing: error)
                    return
                }
                
                if let result = result {
                    // Aktualizuj progress podľa čiastočných výsledkov
                    Task { @MainActor in
                        self?.progress = 0.3 + (result.isFinal ? 0.7 : 0.3)
                    }
                    
                    if result.isFinal {
                        Task { @MainActor in
                            self?.isTranscribing = false
                            self?.statusText = "Hotovo"
                            self?.progress = 1.0
                        }
                        continuation.resume(returning: result.bestTranscription.formattedString)
                    }
                }
            }
        }
    }
    
    /// Konvertuje audio súbor do formátu, ktorý Speech framework podporuje.
    /// Ak je súbor už vo formáte WAV/CAF, vráti ho. Inak ho konvertuje.
    private func prepareAudioFile(url: URL) async throws -> URL {
        let fileExtension = url.pathExtension.lowercased()
        
        // Ak je už vo formáte, ktorý Speech podporuje, použij ho priamo
        if ["wav", "caf", "m4a"].contains(fileExtension) {
            // Pre M4A môže byť potrebné konvertovať, skúsme najprv priamo
            if fileExtension == "m4a" {
                // Skúsme použiť M4A priamo (iOS 13+ podporuje)
                return url
            }
            return url
        }
        
        // Pre ostatné formáty konvertuj na CAF
        return try await convertToCAF(sourceURL: url)
    }
    
    /// Konvertuje audio súbor na CAF formát pomocou AVFoundation.
    private func convertToCAF(sourceURL: URL) async throws -> URL {
        let outputURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension("caf")
        
        let asset = AVAsset(url: sourceURL)
        guard let exportSession = AVAssetExportSession(asset: asset, presetName: AVAssetExportPresetAppleM4A) else {
            throw TranscriptionError.conversionFailed
        }
        
        exportSession.outputURL = outputURL
        exportSession.outputFileType = .m4a
        
        await exportSession.export()
        
        guard exportSession.status == .completed else {
            throw TranscriptionError.conversionFailed
        }
        
        return outputURL
    }
}

enum TranscriptionError: LocalizedError {
    case recognizerNotAvailable
    case conversionFailed
    
    var errorDescription: String? {
        switch self {
        case .recognizerNotAvailable:
            return "Rozpoznávanie reči nie je dostupné. Skontroluj nastavenia jazyka."
        case .conversionFailed:
            return "Nepodarilo sa konvertovať audio súbor."
        }
    }
}
