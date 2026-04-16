import SwiftUI

/// Status page for runtime/system health only.
struct StatusView: View {
    @EnvironmentObject private var config: AppConfig

    @State private var status: StatusOut?
    @State private var isLoading = true

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    var body: some View {
        NavigationStack {
            List {
                // System status
                Section("System") {
                    if isLoading && status == nil {
                        ForEach(0..<6, id: \.self) { _ in
                            StatusRowSkeleton()
                        }
                    } else if let status {
                        LabeledContent("Symbols Tracked", value: "\(status.symbolsTracked)")
                        LabeledContent("Holdings", value: "\(status.holdingsCount)")
                        HStack {
                            Text("Market")
                            Spacer()
                            HStack(spacing: 4) {
                                Circle()
                                    .fill(status.marketOpen ? Theme.positive : Theme.negative)
                                    .frame(width: 8, height: 8)
                                Text(status.marketOpen ? "Open" : "Closed")
                            }
                        }
                        LabeledContent("Scan Interval", value: "\(status.scanIntervalMinutes) min")
                        if let uptime = status.uptimeSeconds {
                            LabeledContent("Uptime", value: formatUptime(uptime))
                        }
                        HStack {
                            Text("Risk Status")
                            Spacer()
                            if status.riskHalted {
                                Text("HALTED")
                                    .font(.caption)
                                    .fontWeight(.semibold)
                                    .foregroundStyle(Theme.negative)
                            } else {
                                Text("Normal")
                                    .foregroundStyle(Theme.positive)
                            }
                        }
                        if status.riskHalted && !status.riskHaltReason.isEmpty {
                            Text(status.riskHaltReason)
                                .font(.caption)
                                .foregroundStyle(Theme.negative)
                        }
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Status")
            .refreshable { await loadStatus() }
            .task { await loadStatus() }
        }
    }

    private func loadStatus() async {
        isLoading = true
        defer { isLoading = false }

        do {
            status = try await client.getStatus()
        } catch {}
    }

    private func formatUptime(_ seconds: Double) -> String {
        // Round to nearest minute so UI doesn't look stale while seconds tick.
        let totalMinutes = Int((seconds / 60).rounded())
        let days = totalMinutes / (24 * 60)
        let hours = (totalMinutes % (24 * 60)) / 60
        let minutes = totalMinutes % 60

        if days > 0 { return "\(days)d \(hours)h \(minutes)m" }
        if hours > 0 { return "\(hours)h \(minutes)m" }
        return "\(minutes)m"
    }
}
