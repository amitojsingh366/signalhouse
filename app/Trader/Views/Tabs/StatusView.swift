import SwiftUI

/// System status page (from More).
struct StatusView: View {
    @EnvironmentObject private var config: AppConfig

    @State private var status: StatusOut?
    @State private var isLoading = true
    @State private var loadFailed = false

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    var body: some View {
        MobileScreen {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 14) {
                    Text(statusHeaderText)
                        .font(.system(size: 10, weight: .medium, design: .monospaced))
                        .tracking(1.4)
                        .foregroundStyle(statusHeaderColor)

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

                    MobileSectionLabel("Services · \(serviceRows.count)")
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
                        } else {
                            ForEach(Array(serviceRows.enumerated()), id: \.element.id) { index, item in
                                ServiceRow(name: item.name, status: item.status, color: item.level.color)
                                if index < serviceRows.count - 1 {
                                    Divider().overlay(Theme.line)
                                }
                            }
                        }
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
            loadFailed = false
        } catch {
            status = nil
            loadFailed = true
        }
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

    private var statusHeaderText: String {
        if status?.riskHalted == true {
            return "RISK HALT ACTIVE"
        }
        if loadFailed {
            return "STATUS UNAVAILABLE"
        }
        if hasDegradedServices {
            return "SYSTEM DEGRADED"
        }
        if status != nil {
            return "ALL SYSTEMS NORMAL"
        }
        return "CHECKING SYSTEM STATUS"
    }

    private var statusHeaderColor: Color {
        if status?.riskHalted == true {
            return Theme.negative
        }
        if loadFailed || hasDegradedServices {
            return Theme.warning
        }
        if status != nil {
            return Theme.positive
        }
        return Theme.textDimmed
    }

    private var hasDegradedServices: Bool {
        serviceRows.contains { $0.level == .warning || $0.level == .critical }
    }

    private var serviceRows: [ServiceHealth] {
        guard let status else {
            if loadFailed {
                return [
                    .init(name: "Price feed", status: "Unavailable", level: .critical),
                    .init(name: "Scanner", status: "Unavailable", level: .critical),
                    .init(name: "OCR pipeline", status: "Unavailable", level: .critical),
                    .init(name: "Notifications", status: "Unavailable", level: .critical),
                    .init(name: "CDR sync", status: "Unavailable", level: .critical),
                    .init(name: "Database", status: "Unavailable", level: .critical),
                ]
            }
            return [
                .init(name: "Price feed", status: "Checking", level: .unknown),
                .init(name: "Scanner", status: "Checking", level: .unknown),
                .init(name: "OCR pipeline", status: "Checking", level: .unknown),
                .init(name: "Notifications", status: "Checking", level: .unknown),
                .init(name: "CDR sync", status: "Checking", level: .unknown),
                .init(name: "Database", status: "Checking", level: .unknown),
            ]
        }

        let scannerFresh = isScannerFresh(status)
        let scannerLevel: HealthLevel = status.marketOpen
            ? (scannerFresh ? .healthy : .warning)
            : .unknown
        let scannerStatus = status.marketOpen
            ? (scannerFresh ? "Healthy" : "Lagging")
            : "Idle"

        let priceFeedLevel: HealthLevel = status.marketOpen
            ? (scannerFresh ? .healthy : .warning)
            : .unknown
        let priceFeedStatus = status.marketOpen
            ? (scannerFresh ? "Live" : "Delayed")
            : "Standby"

        let notificationsLevel: HealthLevel = status.riskHalted ? .warning : .healthy
        let notificationsStatus = status.riskHalted ? "Degraded" : "Healthy"

        let cdrSyncLevel: HealthLevel = status.marketOpen ? .healthy : .unknown
        let cdrSyncStatus = status.marketOpen ? "Live" : "Waiting"

        let ocrLevel: HealthLevel = status.holdingsCount > 0 ? .healthy : .unknown
        let ocrStatus = status.holdingsCount > 0 ? "Healthy" : "Idle"

        return [
            .init(name: "Price feed", status: priceFeedStatus, level: priceFeedLevel),
            .init(name: "Scanner", status: scannerStatus, level: scannerLevel),
            .init(name: "OCR pipeline", status: ocrStatus, level: ocrLevel),
            .init(name: "Notifications", status: notificationsStatus, level: notificationsLevel),
            .init(name: "CDR sync", status: cdrSyncStatus, level: cdrSyncLevel),
            .init(name: "Database", status: "Healthy", level: .healthy),
        ]
    }

    private func isScannerFresh(_ status: StatusOut) -> Bool {
        guard let rawLastScan = status.lastScanAt, let lastScan = parseISODate(rawLastScan) else {
            return false
        }
        let tolerance = max(120.0, Double(status.scanIntervalMinutes * 60 * 2))
        return Date().timeIntervalSince(lastScan) <= tolerance
    }

    private func parseISODate(_ value: String) -> Date? {
        if let parsed = Self.isoWithFractional.date(from: value) { return parsed }
        if let parsed = Self.isoWithoutFractional.date(from: value) { return parsed }
        return nil
    }

    private static let isoWithFractional: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    private static let isoWithoutFractional: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter
    }()
}

private struct ServiceHealth: Identifiable {
    let id = UUID()
    let name: String
    let status: String
    let level: HealthLevel
}

private enum HealthLevel: Equatable {
    case healthy
    case warning
    case critical
    case unknown

    var color: Color {
        switch self {
        case .healthy:
            return Theme.positive
        case .warning:
            return Theme.warning
        case .critical:
            return Theme.negative
        case .unknown:
            return Theme.textDimmed
        }
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
