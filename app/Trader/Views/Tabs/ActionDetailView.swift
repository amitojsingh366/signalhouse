import Charts
import SwiftUI

/// Detail view for an action item — shows price chart + action details.
struct ActionDetailView: View {
    @EnvironmentObject private var config: AppConfig
    let action: ActionItem

    @State private var priceHistory: PriceHistory?
    @State private var isLoadingChart = true
    @State private var selectedRange = "1M"

    private let ranges = ["1W", "1M", "3M", "ALL"]

    private static let dateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    private var chartSymbol: String {
        if action.type == "SWAP" {
            return action.sellSymbol ?? action.buySymbol ?? ""
        }
        return action.symbol ?? ""
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

            // Action details
            Section("Action") {
                HStack {
                    Text("Type")
                    Spacer()
                    Text(action.type)
                        .fontWeight(.semibold)
                        .foregroundStyle(
                            action.type == "SELL" ? Theme.negative
                                : action.type == "BUY" ? Theme.positive
                                : Theme.brand
                        )
                }
                if action.type == "SWAP" {
                    LabeledContent("Sell", value: action.sellSymbol ?? "")
                    LabeledContent("Buy", value: action.buySymbol ?? "")
                }
                if let price = action.price {
                    LabeledContent("Price", value: Formatting.currency(price))
                }
                if let shares = action.shares {
                    LabeledContent("Shares", value: Formatting.number(shares, decimals: shares == shares.rounded() ? 0 : 4))
                }
                if let amount = action.dollarAmount {
                    LabeledContent("Value", value: Formatting.currency(amount))
                }
                if let pnl = action.pnlPct {
                    HStack {
                        Text("P&L")
                        Spacer()
                        Text(Formatting.percent(pnl))
                            .foregroundStyle(Formatting.pnlColor(pnl))
                            .fontWeight(.medium)
                    }
                }
                if !action.reason.isEmpty {
                    LabeledContent("Reason", value: action.reason)
                }
            }

            // Detail text
            if !action.detail.isEmpty {
                Section("Detail") {
                    Text(action.detail)
                        .font(.subheadline)
                }
            }

            // Score breakdown (for BUY actions)
            if let reasons = action.reasons, !reasons.isEmpty {
                Section("Score Breakdown") {
                    ForEach(reasons.filter { !$0.hasPrefix("Price:") && !$0.hasPrefix("ATR:") }, id: \.self) { reason in
                        ScoreReasonRow(text: reason)
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
        .navigationTitle(chartSymbol)
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

            let parsed = filteredBars.compactMap { bar -> (date: Date, close: Double)? in
                guard let d = Self.dateFormatter.date(from: bar.date) else { return nil }
                return (d, bar.close)
            }

            Chart(Array(parsed.enumerated()), id: \.offset) { _, item in
                AreaMark(
                    x: .value("Date", item.date),
                    y: .value("Price", item.close)
                )
                .foregroundStyle(
                    LinearGradient(
                        colors: [Theme.brand.opacity(0.3), Theme.brand.opacity(0.05)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )

                LineMark(
                    x: .value("Date", item.date),
                    y: .value("Price", item.close)
                )
                .foregroundStyle(Theme.brand)
                .lineStyle(StrokeStyle(lineWidth: 2))
            }
            .chartYScale(domain: .automatic(includesZero: false))
            .chartXAxis {
                AxisMarks(values: .automatic(desiredCount: 4)) { value in
                    AxisValueLabel {
                        if let d = value.as(Date.self) {
                            Text(d, format: .dateTime.month(.abbreviated).day())
                                .font(.caption2)
                        }
                    }
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
                    .frame(width: 100, height: 14)
                Spacer()
                HStack(spacing: 2) {
                    ForEach(0..<4, id: \.self) { _ in
                        RoundedRectangle(cornerRadius: 6)
                            .fill(Color.white.opacity(0.06))
                            .frame(width: 36, height: 24)
                    }
                }
                .frame(width: 200)
            }
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
        guard !chartSymbol.isEmpty else { return }
        do {
            priceHistory = try await client.getPriceHistory(symbol: chartSymbol)
        } catch {
            priceHistory = nil
        }
    }
}
