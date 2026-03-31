import SwiftUI

/// First-launch screen — user enters their API server URL.
struct OnboardingView: View {
    @EnvironmentObject private var config: AppConfig
    @State private var urlText = ""
    @State private var isChecking = false
    @State private var error: String?

    var body: some View {
        VStack(spacing: 32) {
            Spacer()

            // Logo
            Image(systemName: "chart.line.uptrend.xyaxis")
                .font(.system(size: 64))
                .foregroundStyle(Theme.brand)

            Text("Trader")
                .font(.largeTitle)
                .fontWeight(.bold)

            Text("Enter your API server URL to get started.")
                .font(.subheadline)
                .foregroundStyle(Theme.textMuted)
                .multilineTextAlignment(.center)

            // URL input
            VStack(alignment: .leading, spacing: 8) {
                TextField("https://trading.example.com", text: $urlText)
                    .textFieldStyle(.roundedBorder)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(.URL)

                if let error {
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(Theme.negative)
                }
            }
            .padding(.horizontal, 32)

            // Connect button
            Button {
                Task { await connect() }
            } label: {
                HStack {
                    if isChecking {
                        ProgressView()
                            .tint(.white)
                    }
                    Text(isChecking ? "Connecting..." : "Connect")
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
            }
            .buttonStyle(.borderedProminent)
            .tint(Theme.brand)
            .disabled(urlText.isEmpty || isChecking)
            .padding(.horizontal, 32)

            Spacer()
            Spacer()
        }
        .preferredColorScheme(.dark)
    }

    private func connect() async {
        error = nil
        isChecking = true
        defer { isChecking = false }

        var url = urlText.trimmingCharacters(in: .whitespacesAndNewlines)
        if !url.hasPrefix("http") {
            url = "https://\(url)"
        }
        url = url.trimmingCharacters(in: CharacterSet(charactersIn: "/"))

        let client = APIClient(baseURL: url)
        do {
            let ok = try await client.healthCheck()
            if ok {
                config.apiBaseURL = url
            } else {
                error = "Server responded but health check failed."
            }
        } catch {
            self.error = "Could not connect: \(error.localizedDescription)"
        }
    }
}
