import Charts
import SwiftUI

/// Detail view for a checked signal — shows signal info + price history chart.
struct SignalDetailView: View {
    @EnvironmentObject private var config: AppConfig
    let signal: SignalOut

    @State private var priceHistory: PriceHistory?
    @State private var isLoadingChart = true
    @State private var selectedRange = "1M"

    private let ranges = ["1W", "1M", "3M", "ALL"]

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    private var filteredBars: [PriceBar] {
        guard let bars = priceHistory?.bars, !bars.isEmpty else { return [] }
        let now = Date()
        let cutoff: Date? = {
            switch selectedRange {
            case "1W": return Calendar.current.date(byAdding: .day, value: -7, to: now)
            case "1M": return Calendar.current.date(byAdding: .month, value: -1, to: now)
            case "3M": return Calendar.current.date(byAdding: .month, value: -3, to: now)
            default: return nil
            }
        }()

        guard let cutoff else { return bars }
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return bars.filter { bar in
            if let d = formatter.date(from: bar.date) {
                return d >= cutoff
            }
            return true
        }
    }

    var body: some View {
        List {
            // Price chart
            Section {
                if isLoadingChart {
                    chartSkeleton
                } else if filteredBars.isEmpty {
                    Text("No price data available")
                        .font(.caption)
                        .foregroundStyle(Theme.textDimmed)
                        .frame(maxWidth: .infinity, minHeight: 200)
                } else {
                    priceChart
                }
            }

            // Signal overview
            Section("Signal") {
                HStack {
                    Text("Signal")
                    Spacer()
                    SignalBadgeView(signal: signal.signal, strength: signal.strength)
                }
                if signal.score != 0 {
                    HStack {
                        Text("Score")
                        Spacer()
                        Text("\(signal.score > 0 ? "+" : "")\(String(format: "%.1f", signal.score))/8")
                            .fontDesign(.monospaced)
                            .foregroundStyle(Formatting.pnlColor(signal.score))
                    }
                }
                if let price = signal.price {
                    LabeledContent("Price", value: Formatting.currency(price))
                }
                if let sector = signal.sector {
                    LabeledContent("Sector", value: sector)
                }
            }

            // Score breakdown
            if !signal.reasons.isEmpty {
                Section("Score Breakdown") {
                    ForEach(signal.reasons, id: \.self) { reason in
                        ScoreReasonRow(text: reason)
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
        .navigationTitle(signal.symbol)
        .navigationBarTitleDisplayMode(.inline)
        .task { await loadPriceHistory() }
    }

    // MARK: - Price Chart

    private var priceChart: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Price History")
                    .font(.subheadline)
                    .foregroundStyle(Theme.textMuted)
                Spacer()
                Picker("Range", selection: $selectedRange) {
                    ForEach(ranges, id: \.self) { Text($0) }
                }
                .pickerStyle(.segmented)
                .frame(width: 200)
            }

            Chart(Array(filteredBars.enumerated()), id: \.offset) { _, bar in
                AreaMark(
                    x: .value("Date", bar.date),
                    y: .value("Price", bar.close)
                )
                .foregroundStyle(
                    LinearGradient(
                        colors: [Theme.brand.opacity(0.3), Theme.brand.opacity(0.05)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )

                LineMark(
                    x: .value("Date", bar.date),
                    y: .value("Price", bar.close)
                )
                .foregroundStyle(Theme.brand)
                .lineStyle(StrokeStyle(lineWidth: 2))
            }
            .chartYScale(domain: .automatic(includesZero: false))
            .chartXAxis {
                AxisMarks(values: .automatic(desiredCount: 5)) { _ in
                    AxisValueLabel()
                        .foregroundStyle(Theme.textDimmed)
                }
            }
            .chartYAxis {
                AxisMarks { _ in
                    AxisGridLine(stroke: StrokeStyle(lineWidth: 0.5))
                        .foregroundStyle(Color.white.opacity(0.06))
                    AxisValueLabel()
                        .foregroundStyle(Theme.textDimmed)
                }
            }
            .frame(height: 220)
        }
        .listRowInsets(EdgeInsets(top: 12, leading: 16, bottom: 12, trailing: 16))
    }

    // MARK: - Chart Skeleton

    private var chartSkeleton: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.white.opacity(0.06))
                    .frame(width: 100, height: 14) // "Price History"
                Spacer()
                // Segmented picker placeholder (4 range buttons)
                HStack(spacing: 2) {
                    ForEach(0..<4, id: \.self) { _ in
                        RoundedRectangle(cornerRadius: 6)
                            .fill(Color.white.opacity(0.06))
                            .frame(width: 36, height: 24)
                    }
                }
                .frame(width: 200)
            }
            // Chart area matching actual frame(height: 220)
            RoundedRectangle(cornerRadius: 8)
                .fill(Color.white.opacity(0.04))
                .frame(height: 220)
        }
        .shimmer()
        .listRowInsets(EdgeInsets(top: 12, leading: 16, bottom: 12, trailing: 16))
    }

    private func loadPriceHistory() async {
        isLoadingChart = true
        defer { isLoadingChart = false }
        do {
            priceHistory = try await client.getPriceHistory(symbol: signal.symbol)
        } catch {
            priceHistory = nil
        }
    }
}
