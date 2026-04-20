import SwiftUI

/// Signalhouse mobile dashboard (tab 1).
struct DashboardView: View {
    @EnvironmentObject private var config: AppConfig

    @State private var portfolio: PortfolioSummary?
    @State private var pnl: PnlSummary?
    @State private var snapshots: [SnapshotOut] = []
    @State private var actionPlan: ActionPlanOut?
    @State private var isLoading = true

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    private var tickerQuotes: [TickerQuote] {
        [
            .init(symbol: "SU.TO", price: "49.30", change: "-1.42%", isPositive: false),
            .init(symbol: "CP.TO", price: "110.76", change: "+0.44%", isPositive: true),
            .init(symbol: "MNT.TO", price: "67.01", change: "-11.56%", isPositive: false),
            .init(symbol: "IBIT.NE", price: "31.33", change: "+11.14%", isPositive: true),
            .init(symbol: "BNS.TO", price: "66.41", change: "-0.12%", isPositive: false),
            .init(symbol: "BMO.TO", price: "138.22", change: "+1.08%", isPositive: true),
        ]
    }

    private var primaryActions: [ActionItem] {
        guard let actions = actionPlan?.actions else { return [] }
        let sells = actions.filter { $0.type == "SELL" && $0.snoozed != true }
        return Array((sells.isEmpty ? actions : sells).prefix(2))
    }

    var body: some View {
        NavigationStack {
            MobileScreen {
                ScrollView(showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 14) {
                        MobileKickerTitle(
                            kicker: "TFSA · \(Date.now.formatted(date: .omitted, time: .shortened))",
                            title: "Dashboard"
                        )

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
                                detail: "of \(actionPlan?.maxPositions ?? 5) max",
                                detailColor: Theme.textDimmed
                            )
                        }

                        HStack {
                            MobileSectionLabel("Action Plan · \(primaryActions.count)")
                            Spacer()
                            NavigationLink("View all", destination: SignalsView())
                                .font(.system(size: 12, weight: .medium))
                                .foregroundStyle(Theme.brand)
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
                                    .font(.system(size: 13))
                                    .foregroundStyle(Theme.textMuted)
                                    .padding(16)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            } else {
                                ForEach(Array(primaryActions.enumerated()), id: \.element.id) { index, action in
                                    DashboardActionRow(action: action)
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
                }
            }
            .navigationBarHidden(true)
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

    private func loadData() async {
        isLoading = true
        defer { isLoading = false }

        async let portfolioTask = client.getHoldings()
        async let pnlTask = client.getPnl()
        async let snapshotsTask = client.getSnapshots()
        async let planTask = client.getActionPlan()

        do { portfolio = try await portfolioTask } catch {}
        do { pnl = try await pnlTask } catch {}
        do { snapshots = try await snapshotsTask } catch {}
        do { actionPlan = try await planTask } catch {}
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
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                    .tracking(1.2)
                    .foregroundStyle(Theme.textDimmed)
                Text(value)
                    .font(.system(size: 34, weight: .bold, design: .rounded))
                    .tracking(-0.8)
                    .minimumScaleFactor(0.6)
                    .lineLimit(1)
                    .foregroundStyle(Theme.textPrimary)
                Text(detail)
                    .font(.system(size: 11, weight: .medium, design: .monospaced))
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
                .fill(Theme.negative.opacity(0.12))
                .frame(width: 32, height: 32)
                .overlay(
                    Image(systemName: "exclamationmark.triangle")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(Theme.negative)
                )

            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 8) {
                    Text(action.type.uppercased())
                        .font(.system(size: 11, weight: .semibold, design: .monospaced))
                        .tracking(1)
                        .foregroundStyle(Theme.negative)
                    Text(action.symbol ?? action.sellSymbol ?? "")
                        .font(.system(size: 13, weight: .semibold, design: .monospaced))
                        .foregroundStyle(Theme.textPrimary)
                }
                Text(action.reason)
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.textMuted)
                    .lineLimit(1)
            }

            Spacer()

            if let pnl = action.pnlPct {
                Text(Formatting.percent(pnl))
                    .font(.system(size: 12, weight: .semibold, design: .monospaced))
                    .foregroundStyle(Formatting.pnlColor(pnl))
            }
        }
        .padding(16)
    }
}
