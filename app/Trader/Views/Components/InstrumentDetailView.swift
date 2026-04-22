import SwiftUI

struct InstrumentSignalSnapshot {
    let symbol: String
    let signal: String
    let strength: Double
    let score: Double
    let technicalScore: Double
    let sentimentScore: Double
    let commodityScore: Double
    let reasons: [String]
    let price: Double?
    let sector: String?
    let actionText: String
    let actionDetail: String?
}

extension InstrumentSignalSnapshot {
    init(signal: SignalOut) {
        self.init(
            symbol: signal.symbol,
            signal: signal.signal,
            strength: signal.strength,
            score: signal.score,
            technicalScore: signal.technicalScore,
            sentimentScore: signal.sentimentScore,
            commodityScore: signal.commodityScore,
            reasons: signal.reasons,
            price: signal.price,
            sector: signal.sector,
            actionText: signal.signal,
            actionDetail: nil
        )
    }

    init(holding: HoldingAdvice) {
        self.init(
            symbol: holding.symbol,
            signal: holding.signal,
            strength: holding.strength,
            score: holding.technicalScore + holding.sentimentScore + holding.commodityScore,
            technicalScore: holding.technicalScore,
            sentimentScore: holding.sentimentScore,
            commodityScore: holding.commodityScore,
            reasons: holding.reasons,
            price: holding.currentPrice,
            sector: nil,
            actionText: holding.action,
            actionDetail: holding.actionDetail
        )
    }
}

struct InstrumentDetailView: View {
    @EnvironmentObject private var config: AppConfig

    let snapshot: InstrumentSignalSnapshot
    let position: HoldingAdvice?

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

                    if let position {
                        MobileSectionLabel("Position")
                        MobileCard {
                            MobileDefRow(label: "Symbol") { MobileValueLabel(text: position.symbol, color: Theme.textPrimary) }
                            Divider().overlay(Theme.line)
                            MobileDefRow(label: "Quantity") { MobileValueLabel(text: Formatting.number(position.quantity, decimals: 4)) }
                            Divider().overlay(Theme.line)
                            MobileDefRow(label: "Avg cost") { MobileValueLabel(text: Formatting.currency(position.avgCost)) }
                            Divider().overlay(Theme.line)
                            MobileDefRow(label: "Current") { MobileValueLabel(text: Formatting.currency(position.currentPrice)) }
                            Divider().overlay(Theme.line)
                            MobileDefRow(label: "Market value") { MobileValueLabel(text: Formatting.currency(position.marketValue), color: Theme.textPrimary) }
                            Divider().overlay(Theme.line)
                            MobileDefRow(label: "P&L") {
                                MobileValueLabel(
                                    text: "\(Formatting.currency(position.pnl)) · \(Formatting.percent(position.pnlPct))",
                                    color: Formatting.pnlColor(position.pnlPct)
                                )
                            }
                        }
                    }

                    MobileSectionLabel("Signal")
                    MobileCard {
                        MobileDefRow(label: "Recommendation") {
                            SignalBadgeView(signal: snapshot.signal, strength: snapshot.strength)
                        }
                        Divider().overlay(Theme.line)
                        MobileDefRow(label: "Action") {
                            MobileValueLabel(text: snapshot.actionText.uppercased(), color: Theme.textPrimary)
                        }
                        if let price = snapshot.price {
                            Divider().overlay(Theme.line)
                            MobileDefRow(label: "Price") {
                                MobileValueLabel(text: Formatting.currency(price), color: Theme.textPrimary)
                            }
                        }
                        if let sector = snapshot.sector {
                            Divider().overlay(Theme.line)
                            MobileDefRow(label: "Sector") {
                                MobileValueLabel(text: sector)
                            }
                        }
                        if let actionDetail = snapshot.actionDetail, !actionDetail.isEmpty {
                            Divider().overlay(Theme.line)
                            Text(actionDetail)
                                .font(AppFont.sans(13))
                                .foregroundStyle(Theme.textMuted)
                                .padding(16)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }

                    MobileSectionLabel("Score breakdown")
                    MobileCard {
                        MobileScoreBreakdownCard(
                            total: snapshot.score,
                            technical: snapshot.technicalScore,
                            sentiment: snapshot.sentimentScore,
                            commodity: snapshot.commodityScore,
                            reasons: snapshot.reasons
                        )
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 8)
                .padding(.bottom, 60)
            }
        }
        .navigationTitle(snapshot.symbol)
        .navigationBarTitleDisplayMode(.inline)
        .task { await loadPriceHistory() }
    }

    private func loadPriceHistory() async {
        isLoadingChart = true
        defer { isLoadingChart = false }
        do {
            priceHistory = try await client.getPriceHistory(symbol: snapshot.symbol)
        } catch {
            priceHistory = nil
        }
    }
}
