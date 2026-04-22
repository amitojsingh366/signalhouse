import SwiftUI

/// Action drill-in view.
struct ActionDetailView: View {
    @EnvironmentObject private var config: AppConfig
    let action: ActionItem

    @State private var priceHistory: PriceHistory?
    @State private var isLoadingChart = true
    @State private var selectedRange = "1M"

    private let ranges = ["1W", "1M", "3M", "ALL"]

    private static let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
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
        return bars.filter { bar in
            guard let date = Self.dateFormatter.date(from: bar.date) else { return true }
            return date >= cutoff
        }
    }

    private var totalScore: Double {
        action.score ?? (action.technicalScore ?? 0) + (action.sentimentScore ?? 0) + (action.commodityScore ?? 0)
    }

    var body: some View {
        MobileScreen {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 14) {
                    MobileSectionLabel("Price history") {
                        Picker("Range", selection: $selectedRange) {
                            ForEach(ranges, id: \.self) { range in
                                Text(range).tag(range)
                            }
                        }
                        .pickerStyle(.segmented)
                        .frame(width: 200)
                        .tint(Theme.brand)
                    }

                    MobileCard {
                        if isLoadingChart {
                            RoundedRectangle(cornerRadius: 12)
                                .fill(Theme.surface0)
                                .frame(height: 140)
                                .padding(16)
                                .shimmer()
                        } else if filteredBars.isEmpty {
                            Text("No price data available")
                                .font(AppFont.sans(12))
                                .foregroundStyle(Theme.textMuted)
                                .padding(16)
                        } else {
                            PriceHistoryChartContent(bars: filteredBars)
                                .padding(16)
                        }
                    }

                    MobileSectionLabel("Action")
                    MobileCard {
                        MobileDefRow(label: "Type") {
                            MobileValueLabel(text: action.type, color: action.type == "SELL" ? Theme.negative : action.type == "BUY" ? Theme.positive : Theme.brand)
                        }
                        Divider().overlay(Theme.line)
                        if let price = action.price ?? action.sellPrice {
                            MobileDefRow(label: "Price") { MobileValueLabel(text: Formatting.currency(price), color: Theme.textPrimary) }
                            Divider().overlay(Theme.line)
                        }
                        if let shares = action.shares ?? action.sellShares {
                            MobileDefRow(label: "Shares") { MobileValueLabel(text: Formatting.number(shares, decimals: 4), color: Theme.textPrimary) }
                            Divider().overlay(Theme.line)
                        }
                        if let amount = action.dollarAmount ?? action.sellAmount {
                            MobileDefRow(label: "Value") { MobileValueLabel(text: Formatting.currency(amount), color: Theme.textPrimary) }
                            Divider().overlay(Theme.line)
                        }
                        if let pnl = action.pnlPct ?? action.sellPnlPct {
                            MobileDefRow(label: "P&L") { MobileValueLabel(text: Formatting.percent(pnl), color: Formatting.pnlColor(pnl)) }
                            Divider().overlay(Theme.line)
                        }
                        MobileDefRow(label: "Reason") { MobileValueLabel(text: action.reason) }
                    }

                    MobileSectionLabel("Score breakdown")
                    MobileCard {
                        MobileScoreBreakdownCard(
                            total: totalScore,
                            technical: action.technicalScore ?? 0,
                            sentiment: action.sentimentScore ?? 0,
                            commodity: action.commodityScore ?? 0,
                            reasons: action.reasons ?? []
                        )
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 8)
                .padding(.bottom, 60)
            }
        }
        .navigationTitle(chartSymbol)
        .navigationBarTitleDisplayMode(.inline)
        .task { await loadPriceHistory() }
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
