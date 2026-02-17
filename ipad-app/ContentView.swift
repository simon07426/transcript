import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @StateObject private var transcriptionService = TranscriptionService()
    @State private var selectedURL: URL?
    @State private var transcript: String = ""
    @State private var showFilePicker = false
    @State private var showError = false
    @State private var errorMessage = ""

    var body: some View {
        NavigationView {
            VStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Audio súbor:")
                        .font(.headline)

                    HStack {
                        Text(selectedURL?.lastPathComponent ?? "Žiadny súbor nevybraný")
                            .lineLimit(1)
                            .truncationMode(.middle)
                            .foregroundColor(.secondary)

                        Button("Vybrať…") {
                            showFilePicker = true
                        }
                    }
                }

                Text("Transkript:")
                    .font(.headline)

                ScrollView {
                    Text(transcript.isEmpty ? "Transkript sa zobrazí tu…" : transcript)
                        .frame(maxWidth: .infinity, alignment: .topLeading)
                        .padding(8)
                }
                .background(Color(UIColor.secondarySystemBackground))
                .cornerRadius(8)
                .frame(minHeight: 200)

                VStack(alignment: .leading, spacing: 8) {
                    Text(transcriptionService.statusText.isEmpty ? "Pripravené" : transcriptionService.statusText)
                        .font(.subheadline)
                        .foregroundColor(.secondary)

                    if transcriptionService.isTranscribing {
                        ProgressView(value: transcriptionService.progress)
                            .progressViewStyle(.linear)
                    }
                }

                HStack {
                    Spacer()
                    Button("Transkribovať") {
                        Task {
                            await startTranscription()
                        }
                    }
                    .disabled(selectedURL == nil || transcriptionService.isTranscribing)
                    .buttonStyle(.borderedProminent)
                }
            }
            .padding()
            .navigationTitle("M4A → Slovenský transkript")
        }
        .fileImporter(
            isPresented: $showFilePicker,
            allowedContentTypes: [
                .audio,
                UTType(filenameExtension: "m4a")!,
                UTType(filenameExtension: "mp3")!,
                UTType(filenameExtension: "wav")!
            ],
            allowsMultipleSelection: false
        ) { result in
            switch result {
            case .success(let urls):
                if let url = urls.first {
                    // Získaj prístup k súboru
                    _ = url.startAccessingSecurityScopedResource()
                    selectedURL = url
                }
            case .failure:
                break
            }
        }
        .alert("Chyba", isPresented: $showError) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(errorMessage)
        }
    }

    private func startTranscription() async {
        guard let url = selectedURL else { return }
        
        transcript = ""
        
        do {
            let result = try await transcriptionService.transcribe(audioURL: url)
            await MainActor.run {
                transcript = result
                
                // Ulož transkript do súboru vedľa originálu
                if let originalURL = selectedURL {
                    let transcriptURL = originalURL.deletingPathExtension().appendingPathExtension("txt")
                    try? result.write(to: transcriptURL, atomically: true, encoding: .utf8)
                }
            }
        } catch {
            await MainActor.run {
                errorMessage = error.localizedDescription
                showError = true
                transcriptionService.isTranscribing = false
            }
        }
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
            .previewDevice("iPad Pro (11-inch) (4th generation)")
    }
}
