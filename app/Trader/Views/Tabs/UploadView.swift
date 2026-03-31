import PhotosUI
import SwiftUI

/// Upload page matching web's upload/page.tsx — pick photo, parse, confirm.
struct UploadView: View {
    @EnvironmentObject private var config: AppConfig

    @State private var selectedItem: PhotosPickerItem?
    @State private var isParsing = false
    @State private var parsedHoldings: [UploadHolding]?
    @State private var isConfirming = false
    @State private var error: String?
    @State private var success: String?

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    var body: some View {
        NavigationStack {
            List {
                // Photo picker
                Section {
                    PhotosPicker(
                        selection: $selectedItem,
                        matching: .images,
                        photoLibrary: .shared()
                    ) {
                        HStack {
                            Image(systemName: "photo.on.rectangle")
                                .foregroundStyle(Theme.brand)
                            Text("Select Screenshot")
                        }
                    }
                    .onChange(of: selectedItem) { _, newItem in
                        Task { await processImage(newItem) }
                    }

                    if isParsing {
                        HStack {
                            ProgressView()
                            Text("Parsing with Claude Vision...")
                                .font(.caption)
                                .foregroundStyle(Theme.textMuted)
                        }
                    }

                    if let error {
                        Text(error)
                            .font(.caption)
                            .foregroundStyle(Theme.negative)
                    }
                    if let success {
                        Text(success)
                            .font(.caption)
                            .foregroundStyle(Theme.positive)
                    }
                } header: {
                    Text("Upload Brokerage Screenshot")
                } footer: {
                    Text("Take a screenshot of your holdings in your brokerage app, then select it here. Claude Vision will parse the positions automatically.")
                }

                // Parsed holdings
                if let holdings = parsedHoldings {
                    Section("Parsed Holdings (\(holdings.count))") {
                        ForEach(Array(holdings.enumerated()), id: \.element.symbol) { index, holding in
                            HStack {
                                VStack(alignment: .leading) {
                                    Text(holding.symbol)
                                        .fontWeight(.medium)
                                    Text("Qty: \(Formatting.number(holding.quantity, decimals: 4))")
                                        .font(.caption)
                                        .foregroundStyle(Theme.textDimmed)
                                }
                                Spacer()
                                Text(Formatting.currency(holding.marketValueCad))
                                    .foregroundStyle(Theme.textMuted)
                            }
                        }
                    }

                    Section {
                        Button {
                            Task { await confirmUpload() }
                        } label: {
                            HStack {
                                if isConfirming { ProgressView().tint(.white) }
                                Text("Confirm & Sync Portfolio")
                            }
                            .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(Theme.brand)
                        .disabled(isConfirming)

                        Button("Cancel", role: .destructive) {
                            parsedHoldings = nil
                            selectedItem = nil
                        }
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Upload")
        }
    }

    private func processImage(_ item: PhotosPickerItem?) async {
        guard let item else { return }
        isParsing = true
        error = nil
        success = nil
        parsedHoldings = nil
        defer { isParsing = false }

        do {
            guard let data = try await item.loadTransferable(type: Data.self) else {
                error = "Could not load image data"
                return
            }
            parsedHoldings = try await client.parseScreenshot(imageData: data)
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func confirmUpload() async {
        guard let holdings = parsedHoldings else { return }
        isConfirming = true
        defer { isConfirming = false }
        do {
            try await client.confirmUpload(holdings: holdings)
            success = "Portfolio synced with \(holdings.count) holdings"
            parsedHoldings = nil
            selectedItem = nil
        } catch {
            self.error = error.localizedDescription
        }
    }
}
