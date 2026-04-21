import PhotosUI
import SwiftUI

/// Upload screenshot page (from More).
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
        MobileScreen {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 14) {
                    Text("OCR")
                        .font(.system(size: 10, weight: .medium, design: .monospaced))
                        .tracking(1.4)
                        .foregroundStyle(Theme.brand)

                    MobileSectionLabel("Import")
                    MobileCard {
                        VStack(alignment: .leading, spacing: 10) {
                            PhotosPicker(
                                selection: $selectedItem,
                                matching: .images,
                                photoLibrary: .shared()
                            ) {
                                Label("Select screenshot", systemImage: "photo.on.rectangle")
                                    .font(.system(size: 14, weight: .semibold))
                                    .foregroundStyle(Color.black)
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 14)
                                    .background(Theme.brand)
                                    .clipShape(RoundedRectangle(cornerRadius: 10))
                            }
                            .onChange(of: selectedItem) { _, newItem in
                                Task { await processImage(newItem) }
                            }

                            if isParsing {
                                HStack(spacing: 8) {
                                    ProgressView()
                                    Text("Parsing with Claude Vision...")
                                        .font(.system(size: 12))
                                        .foregroundStyle(Theme.textMuted)
                                }
                            }

                            if let error {
                                Text(error)
                                    .font(.system(size: 11))
                                    .foregroundStyle(Theme.negative)
                            }
                            if let success {
                                Text(success)
                                    .font(.system(size: 11))
                                    .foregroundStyle(Theme.positive)
                            }
                        }
                        .padding(14)
                    }

                    if let holdings = parsedHoldings {
                        MobileSectionLabel("Parsed holdings · \(holdings.count)")
                        MobileCard {
                            ForEach(Array(holdings.enumerated()), id: \.element.id) { index, holding in
                                HStack {
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(holding.symbol)
                                            .font(.system(size: 13, weight: .semibold, design: .monospaced))
                                            .foregroundStyle(Theme.textPrimary)
                                        Text("Qty: \(Formatting.number(holding.quantity, decimals: 4))")
                                            .font(.system(size: 11, design: .monospaced))
                                            .foregroundStyle(Theme.textDimmed)
                                    }
                                    Spacer()
                                    Text(Formatting.currency(holding.marketValueCad))
                                        .font(.system(size: 12, weight: .semibold, design: .monospaced))
                                        .foregroundStyle(Theme.textMuted)
                                }
                                .padding(16)

                                if index < holdings.count - 1 {
                                    Divider().overlay(Theme.line)
                                }
                            }
                        }

                        MobileCard {
                            VStack(spacing: 10) {
                                Button {
                                    Task { await confirmUpload() }
                                } label: {
                                    HStack(spacing: 8) {
                                        if isConfirming { ProgressView().tint(Color.black) }
                                        Text("Confirm & sync portfolio")
                                            .font(.system(size: 14, weight: .semibold))
                                    }
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 14)
                                    .background(Theme.brand)
                                    .foregroundStyle(Color.black)
                                    .clipShape(RoundedRectangle(cornerRadius: 10))
                                }
                                .buttonStyle(.plain)
                                .disabled(isConfirming)

                                Button("Cancel", role: .destructive) {
                                    parsedHoldings = nil
                                    selectedItem = nil
                                }
                                .frame(maxWidth: .infinity)
                            }
                            .padding(14)
                        }
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 10)
                .padding(.bottom, 40)
            }
        }
        .navigationTitle("Upload screenshot")
        .navigationBarTitleDisplayMode(.inline)
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
            NotificationCenter.default.post(name: .portfolioDidChange, object: nil)
        } catch {
            self.error = error.localizedDescription
        }
    }
}
