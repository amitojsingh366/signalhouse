import SwiftUI

/// Dashboard matching web's page.tsx — stat cards, action plan preview, equity chart, sector exposure.
struct DashboardView: View {
    @EnvironmentObject private var config: AppConfig

    @State private var portfolio: PortfolioSummary?
    @State private var pnl: PnlSummary?
    @State private var snapshots: [SnapshotOut]?
    @State private var actionPlan: ActionPlanOut?
    @State private var isLoading = true
    @State private var error: String?

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    // Stat cards
                    if isLoading && portfolio == nil {
                        LazyVGrid(columns: [.init(.flexible()), .init(.flexible())], spacing: 12) {
                            StatCardSkeleton()
                            StatCardSkeleton()
                            StatCardSkeleton()
                            StatCardSkeleton()
                        }
                    } else {
                        LazyVGrid(columns: [.init(.flexible()), .init(.flexible())], spacing: 12) {
                            StatCardView(
                                title: "Portfolio Value",
                                value: Formatting.currency(portfolio?.totalValue ?? 0),
                                change: pnl?.totalPnlPct,
                                changeLabel: "total",
                                icon: "dollarsign"
                            )
                            StatCardView(
                                title: "Daily P&L",
                                value: Formatting.currency(pnl?.dailyPnl ?? 0),
                                change: pnl?.dailyPnlPct,
                                changeLabel: "today",
                                icon: "arrow.up.right"
                            )
                            StatCardView(
                                title: "Cash Available",
                                value: Formatting.currency(portfolio?.cash ?? 0),
                                icon: "wallet.pass"
                            )
                            StatCardView(
                                title: "Holdings",
                                value: "\(portfolio?.holdings.count ?? 0)",
                                icon: "briefcase"
                            )
                        }
                    }

                    // Action plan preview skeleton
                    if isLoading && actionPlan == nil {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(Color.white.opacity(0.06))
                                    .frame(width: 100, height: 14)
                                Spacer()
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(Color.white.opacity(0.06))
                                    .frame(width: 50, height: 12)
                            }
                            .shimmer()
                            ForEach(0..<3, id: \.self) { _ in
                                DashboardSignalSkeleton()
                            }
                        }
                        .shimmer()
                    }

                    // Action plan preview (max 3 on dashboard)
                    if let plan = actionPlan, !plan.actions.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text("Action Plan")
                                    .font(.subheadline)
                                    .foregroundStyle(Theme.textMuted)
                                Spacer()
                                NavigationLink("View all", destination: SignalsView())
                                    .font(.caption)
                            }

                            ForEach(plan.actions.prefix(3)) { action in
                                DashboardActionCard(action: action)
                            }
                        }
                    } else if !isLoading && actionPlan != nil {
                        VStack(spacing: 8) {
                            Image(systemName: "checkmark.circle")
                                .font(.title)
                                .foregroundStyle(Theme.textDimmed)
                            Text("No trades needed")
                                .font(.subheadline)
                                .foregroundStyle(Theme.textDimmed)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 24)
                        .glassCard()
                    }

                    // Equity chart
                    if isLoading && snapshots == nil {
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(Color.white.opacity(0.06))
                                    .frame(width: 90, height: 14)
                                Spacer()
                                HStack(spacing: 4) {
                                    ForEach(0..<4, id: \.self) { _ in
                                        RoundedRectangle(cornerRadius: 6)
                                            .fill(Color.white.opacity(0.06))
                                            .frame(width: 32, height: 24)
                                    }
                                }
                            }
                            RoundedRectangle(cornerRadius: 8)
                                .fill(Color.white.opacity(0.04))
                                .frame(height: 220)
                        }
                        .padding()
                        .glassCard()
                        .shimmer()
                    } else if let snapshots, !snapshots.isEmpty {
                        EquityChartView(snapshots: snapshots)
                    }

                    // Sector exposure
                    if isLoading && actionPlan == nil {
                        VStack(alignment: .leading, spacing: 12) {
                            RoundedRectangle(cornerRadius: 4)
                                .fill(Color.white.opacity(0.06))
                                .frame(width: 120, height: 14)
                            ForEach([0.75, 0.55, 0.35, 0.2], id: \.self) { pct in
                                HStack(spacing: 8) {
                                    RoundedRectangle(cornerRadius: 4)
                                        .fill(Color.white.opacity(0.06))
                                        .frame(width: 70, height: 14)
                                    GeometryReader { geo in
                                        RoundedRectangle(cornerRadius: 4)
                                            .fill(Color.white.opacity(0.06))
                                            .frame(width: geo.size.width * pct, height: 20)
                                    }
                                    .frame(height: 20)
                                }
                            }
                        }
                        .padding()
                        .glassCard()
                        .shimmer()
                    } else if let plan = actionPlan, !plan.sectorExposure.isEmpty {
                        SectorChartView(exposure: plan.sectorExposure)
                    }
                }
                .padding()
            }
            .navigationTitle("Dashboard")
            .refreshable { await loadData() }
            .task { await loadData() }
        }
    }

    private func loadData() async {
        isLoading = true
        defer { isLoading = false }

        async let p = client.getHoldings()
        async let pnlData = client.getPnl()
        async let snap = client.getSnapshots()
        async let plan = client.getActionPlan()

        do {
            portfolio = try await p
            pnl = try await pnlData
            snapshots = try await snap
            actionPlan = try await plan
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }
}

// MARK: - Dashboard Action Card

private struct DashboardActionCard: View {
    let action: ActionItem

    var body: some View {
        HStack {
            Image(systemName: actionIcon)
                .foregroundStyle(actionColor)

            VStack(alignment: .leading) {
                Text(actionTitle)
                    .fontWeight(.medium)
                Text(action.reason)
                    .font(.caption)
                    .foregroundStyle(Theme.textDimmed)
            }

            Spacer()

            if action.type == "SELL", let pnl = action.pnlPct {
                Text(Formatting.percent(pnl))
                    .font(.caption)
                    .foregroundStyle(Formatting.pnlColor(pnl))
            } else if action.type == "BUY", let strength = action.strength {
                Text("\(Int(strength * 100))%")
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundStyle(Theme.positive)
            }
        }
        .padding(12)
        .glassCard()
    }

    private var actionIcon: String {
        switch action.type {
        case "SELL": return action.urgency == "urgent"
            ? "exclamationmark.triangle.fill" : "arrow.down.circle"
        case "SWAP": return "arrow.left.arrow.right"
        case "BUY": return "arrow.up.circle"
        default: return "circle"
        }
    }

    private var actionColor: Color {
        switch action.type {
        case "SELL": return action.urgency == "urgent" ? Theme.negative : Theme.warning
        case "SWAP": return Theme.brand
        case "BUY": return Theme.positive
        default: return Theme.textMuted
        }
    }

    private var actionTitle: String {
        switch action.type {
        case "SELL": return "SELL \(action.symbol ?? "")"
        case "SWAP": return "\(action.sellSymbol ?? "") → \(action.buySymbol ?? "")"
        case "BUY": return "BUY \(action.symbol ?? "")"
        default: return action.type
        }
    }
}
