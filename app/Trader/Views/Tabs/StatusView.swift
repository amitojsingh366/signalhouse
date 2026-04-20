import SwiftUI

/// System status page (from More).
struct StatusView: View {
    @EnvironmentObject private var config: AppConfig

    @State private var status: StatusOut?
    @State private var isLoading = true

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    var body: some View {
        MobileScreen {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 14) {
                    MobileKickerTitle(
                        kicker: "All systems normal",
                        title: "Status",
                        kickerColor: Theme.positive
                    )

                    MobileSectionLabel("Scanner")
                    MobileCard {
                        if isLoading && status == nil {
                            ForEach(0..<6, id: \.self) { index in
                                StatusRowSkeleton()
                                    .padding(.horizontal, 16)
                                    .padding(.vertical, 11)
                                if index < 5 {
                                    Divider().overlay(Theme.line)
                                }
                            }
                        } else if let status {
                            MobileDefRow(label: "Symbols tracked") { MobileValueLabel(text: "\(status.symbolsTracked)", color: Theme.textPrimary) }
                            Divider().overlay(Theme.line)
                            MobileDefRow(label: "Holdings") { MobileValueLabel(text: "\(status.holdingsCount)", color: Theme.textPrimary) }
                            Divider().overlay(Theme.line)
                            MobileDefRow(label: "Market") {
                                HStack(spacing: 6) {
                                    Circle()
                                        .fill(status.marketOpen ? Theme.positive : Theme.negative)
                                        .frame(width: 6, height: 6)
                                    MobileValueLabel(text: status.marketOpen ? "Open" : "Closed", color: Theme.textPrimary)
                                }
                            }
                            Divider().overlay(Theme.line)
                            MobileDefRow(label: "Scan interval") {
                                MobileValueLabel(text: "\(status.scanIntervalMinutes) min")
                            }
                            Divider().overlay(Theme.line)
                            MobileDefRow(label: "Uptime") {
                                MobileValueLabel(text: "\(formatUptime(status.uptimeSeconds ?? 0)) · 100%")
                            }
                            Divider().overlay(Theme.line)
                            MobileDefRow(label: "Risk status") {
                                MobileValueLabel(text: status.riskHalted ? "Halted" : "Normal", color: status.riskHalted ? Theme.negative : Theme.positive)
                            }
                        }
                    }

                    MobileSectionLabel("Services · 6")
                    MobileCard {
                        ServiceRow(name: "Price feed", status: "Healthy", color: Theme.positive)
                        Divider().overlay(Theme.line)
                        ServiceRow(name: "Scanner", status: "Healthy", color: Theme.positive)
                        Divider().overlay(Theme.line)
                        ServiceRow(name: "OCR pipeline", status: "Healthy", color: Theme.positive)
                        Divider().overlay(Theme.line)
                        ServiceRow(
                            name: "Notifications",
                            status: status?.riskHalted == true ? "Degraded" : "Healthy",
                            color: status?.riskHalted == true ? Theme.warning : Theme.positive
                        )
                        Divider().overlay(Theme.line)
                        ServiceRow(name: "CDR sync", status: "Healthy", color: Theme.positive)
                        Divider().overlay(Theme.line)
                        ServiceRow(name: "Database", status: "Healthy", color: Theme.positive)
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 10)
                .padding(.bottom, 40)
            }
        }
        .navigationTitle("System")
        .navigationBarTitleDisplayMode(.inline)
        .refreshable { await loadStatus() }
        .task { await loadStatus() }
    }

    private func loadStatus() async {
        isLoading = true
        defer { isLoading = false }
        do {
            status = try await client.getStatus()
        } catch {}
    }

    private func formatUptime(_ seconds: Double) -> String {
        let totalMinutes = Int((seconds / 60).rounded())
        let days = totalMinutes / (24 * 60)
        let hours = (totalMinutes % (24 * 60)) / 60
        let minutes = totalMinutes % 60
        if days > 0 { return "\(days)d \(hours)h \(minutes)m" }
        if hours > 0 { return "\(hours)h \(minutes)m" }
        return "\(minutes)m"
    }
}

private struct ServiceRow: View {
    let name: String
    let status: String
    let color: Color

    var body: some View {
        HStack {
            Text(name)
                .font(.system(size: 14))
                .foregroundStyle(Theme.textPrimary)
            Spacer()
            HStack(spacing: 6) {
                Circle()
                    .fill(color)
                    .frame(width: 6, height: 6)
                Text(status)
                    .font(.system(size: 14, weight: .semibold, design: .monospaced))
                    .foregroundStyle(color)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }
}
