import SwiftUI

/// Signalhouse mobile dashboard (tab 1).
struct DashboardView: View {
    @EnvironmentObject private var config: AppConfig

    @State private var portfolio: PortfolioSummary?
    @State private var pnl: PnlSummary?
    @State private var snapshots: [SnapshotOut] = []
    @State private var actionPlan: ActionPlanOut?
    @State private var tickerQuotes: [TickerQuote] = []
    @State private var isLoading = true

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    private var primaryActions: [ActionItem] {
        guard let actions = actionPlan?.actions else { return [] }
        let activeActions = actions.filter { $0.snoozed != true }
        let sells = activeActions.filter { $0.type == "SELL" }
        return Array((sells.isEmpty ? activeActions : sells).prefix(2))
    }

    var body: some View {
        NavigationStack {
            MobileScreen {
                ScrollView(showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 14) {
                        Text("TFSA · \(Date.now.formatted(date: .omitted, time: .shortened))")
                            .font(AppFont.mono(10, weight: .medium))
                            .tracking(1.4)
                            .foregroundStyle(Theme.brand)

                        TickerStrip(quotes: tickerQuotes)

                        LazyVGrid(columns: [.init(.flexible()), .init(.flexible())], spacing: 10) {
                            DashboardKPI(
                                title: "Portfolio",
                                value: Formatting.currency(portfolio?.totalValue ?? 0),
                                detail: "\(Formatting.percent(pnl?.totalPnlPct ?? 0)) total",
                                detailColor: Formatting.pnlColor(pnl?.totalPnlPct ?? 0)
                            )
                            DashboardKPI(
                                title: "Daily P&L",
                                value: Formatting.currency(pnl?.dailyPnl ?? 0),
                                detail: "\(Formatting.percent(pnl?.dailyPnlPct ?? 0)) today",
                                detailColor: Formatting.pnlColor(pnl?.dailyPnlPct ?? 0)
                            )
                            DashboardKPI(
                                title: "Cash",
                                value: Formatting.currency(portfolio?.cash ?? 0),
                                detail: "\(allocationText)",
                                detailColor: Theme.textDimmed
                            )
                            DashboardKPI(
                                title: "Holdings",
                                value: "\(portfolio?.holdings.count ?? 0)",
                                detail: actionPlan.map { "of \($0.maxPositions) max" } ?? "of — max",
                                detailColor: Theme.textDimmed
                            )
                        }

                        HStack {
                            MobileSectionLabel("Action Plan · \(primaryActions.count)")
                            Spacer()
                            Button("View all") {
                                NotificationCenter.default.post(name: .openActionsTab, object: nil)
                            }
                            .font(AppFont.sans(12, weight: .medium))
                            .foregroundStyle(Theme.brand)
                            .buttonStyle(.plain)
                        }

                        MobileCard {
                            if isLoading && actionPlan == nil {
                                ForEach(0..<2, id: \.self) { idx in
                                    DashboardSignalSkeleton()
                                        .padding(.horizontal, 16)
                                        .padding(.vertical, 8)
                                    if idx == 0 {
                                        Divider().overlay(Theme.line)
                                    }
                                }
                            } else if primaryActions.isEmpty {
                                Text("No immediate actions")
                                    .font(AppFont.sans(13))
                                    .foregroundStyle(Theme.textMuted)
                                    .padding(16)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            } else {
                                ForEach(Array(primaryActions.enumerated()), id: \.element.id) { index, action in
                                    if let detailSignal = signal(from: action) {
                                        NavigationLink {
                                            SignalDetailView(signal: detailSignal)
                                        } label: {
                                            DashboardActionRow(action: action)
                                        }
                                        .buttonStyle(.plain)
                                    } else {
                                        DashboardActionRow(action: action)
                                    }
                                    if index < primaryActions.count - 1 {
                                        Divider().overlay(Theme.line)
                                    }
                                }
                            }
                        }

                        MobileSectionLabel("Equity Curve")
                            .padding(.top, 2)

                        if isLoading && snapshots.isEmpty {
                            RoundedRectangle(cornerRadius: 16)
                                .fill(Theme.surface1)
                                .frame(height: 240)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 16)
                                        .stroke(Theme.line, lineWidth: 1)
                                )
                                .shimmer()
                        } else {
                            EquityChartView(snapshots: snapshots)
                        }
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 10)
                    .padding(.bottom, 140)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .navigationTitle("Dashboard")
            .navigationBarTitleDisplayMode(.large)
            .refreshable { await loadData() }
            .task { await loadData() }
            .onReceive(NotificationCenter.default.publisher(for: .portfolioDidChange)) { _ in
                Task { await loadData() }
            }
        }
    }

    private var allocationText: String {
        guard let portfolio, portfolio.totalValue > 0 else { return "0% allocated" }
        let allocated = ((portfolio.totalValue - portfolio.cash) / portfolio.totalValue) * 100
        return "\(Int(allocated.rounded()))% allocated"
    }

    private func signal(from action: ActionItem) -> SignalOut? {
        guard let symbol = action.symbol ?? action.sellSymbol ?? action.buySymbol, !symbol.isEmpty else {
            return nil
        }
        let technical = action.technicalScore ?? 0
        let sentiment = action.sentimentScore ?? 0
        let commodity = action.commodityScore ?? 0
        let total = action.score ?? (technical + sentiment + commodity)
        let reasons = (action.reasons?.isEmpty == false ? action.reasons : [action.reason]) ?? [action.reason]

        return SignalOut(
            symbol: symbol,
            signal: action.type,
            strength: action.strength ?? 0,
            score: total,
            technicalScore: technical,
            sentimentScore: sentiment,
            commodityScore: commodity,
            reasons: reasons,
            price: action.price ?? action.sellPrice ?? action.buyPrice,
            sector: action.sector
        )
    }

    private func loadData() async {
        isLoading = true
        defer { isLoading = false }

        async let portfolioTask = client.getHoldings()
        async let pnlTask = client.getPnl()
        async let snapshotsTask = client.getSnapshots()
        async let planTask = client.getActionPlan()
        async let tickerStripTask = client.getTickerStrip()

        do { portfolio = try await portfolioTask } catch {}
        do { pnl = try await pnlTask } catch {}
        do { snapshots = try await snapshotsTask } catch {}
        do { actionPlan = try await planTask } catch {}
        do {
            let items = try await tickerStripTask
            tickerQuotes = items.map(TickerQuote.init(item:))
        } catch {
            tickerQuotes = []
        }
    }
}

private struct DashboardKPI: View {
    let title: String
    let value: String
    let detail: String
    let detailColor: Color

    var body: some View {
        MobileCard {
            VStack(alignment: .leading, spacing: 10) {
                Text(title.uppercased())
                    .font(AppFont.mono(10, weight: .medium))
                    .tracking(1.2)
                    .foregroundStyle(Theme.textDimmed)
                Text(value)
                    .font(AppFont.sans(32, weight: .bold))
                    .tracking(-0.8)
                    .minimumScaleFactor(0.6)
                    .lineLimit(1)
                    .foregroundStyle(Theme.textPrimary)
                Text(detail)
                    .font(AppFont.mono(12, weight: .medium))
                    .foregroundStyle(detailColor)
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct DashboardActionRow: View {
    let action: ActionItem

    var body: some View {
        HStack(spacing: 12) {
            RoundedRectangle(cornerRadius: 8)
                .fill(actionColor.opacity(0.12))
                .frame(width: 32, height: 32)
                .overlay(
                    Image(systemName: actionIcon)
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(actionColor)
                )

            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 8) {
                    Text(actionLabel)
                        .font(AppFont.mono(11, weight: .semibold))
                        .tracking(1)
                        .foregroundStyle(actionColor)
                    Text(symbolText)
                        .font(AppFont.mono(13, weight: .semibold))
                        .foregroundStyle(Theme.textPrimary)
                }
                Text(action.reason)
                    .font(AppFont.sans(12))
                    .foregroundStyle(Theme.textMuted)
                    .lineLimit(1)
            }

            Spacer()

            if let pnl = action.pnlPct {
                Text(Formatting.percent(pnl))
                    .font(AppFont.mono(12, weight: .semibold))
                    .foregroundStyle(Formatting.pnlColor(pnl))
            }
        }
        .padding(16)
    }

    private var symbolText: String {
        if action.type == "SWAP" {
            return "\(action.sellSymbol ?? "") → \(action.buySymbol ?? "")"
        }
        return action.symbol ?? action.sellSymbol ?? ""
    }

    private var actionLabel: String {
        if action.type == "BUY", action.actionable == false {
            return "HOLD"
        }
        return action.type.uppercased()
    }

    private var actionColor: Color {
        switch action.type {
        case "SELL":
            return Theme.negative
        case "SWAP":
            return Theme.brand
        default:
            return action.actionable == false ? Theme.warning : Theme.positive
        }
    }

    private var actionIcon: String {
        switch action.type {
        case "SELL":
            return "exclamationmark.triangle"
        case "SWAP":
            return "arrow.left.arrow.right"
        default:
            return action.actionable == false ? "pause.fill" : "arrow.up.right"
        }
    }
}
