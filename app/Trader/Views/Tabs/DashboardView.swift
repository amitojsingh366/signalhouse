import SwiftUI

/// Dashboard matching web's page.tsx — stat cards, signals, equity chart, sector exposure.
struct DashboardView: View {
    @EnvironmentObject private var config: AppConfig

    @State private var portfolio: PortfolioSummary?
    @State private var pnl: PnlSummary?
    @State private var snapshots: [SnapshotOut]?
    @State private var signals: RecommendationOut?
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

                    // Latest signals skeleton
                    if isLoading && signals == nil {
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

                    // Latest signals (max 3 on dashboard)
                    if let signals, !signals.buys.isEmpty || !signals.sells.isEmpty || !signals.exitAlerts.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text("Latest Signals")
                                    .font(.subheadline)
                                    .foregroundStyle(Theme.textMuted)
                                Spacer()
                                NavigationLink("View all", destination: SignalsView())
                                    .font(.caption)
                            }

                            let exitAlertsCapped = Array(signals.exitAlerts.prefix(3))
                            let remaining = max(0, 3 - exitAlertsCapped.count)

                            // Exit alerts (priority)
                            ForEach(exitAlertsCapped) { alert in
                                HStack {
                                    Image(systemName: "exclamationmark.triangle")
                                        .foregroundStyle(alert.severity == "high" ? Theme.negative : Theme.warning)
                                    VStack(alignment: .leading) {
                                        Text(alert.symbol).fontWeight(.medium)
                                        Text(alert.reason).font(.caption).foregroundStyle(Theme.textDimmed)
                                    }
                                    Spacer()
                                    Text(Formatting.percent(alert.pnlPct))
                                        .font(.caption)
                                        .foregroundStyle(Formatting.pnlColor(alert.pnlPct))
                                }
                                .padding(12)
                                .glassCard()
                            }

                            // Buy/sell signals (fill remaining slots up to 3 total)
                            if remaining > 0 {
                                let allSignals = signals.buys + signals.sells + signals.watchlistSells
                                ForEach(allSignals.prefix(remaining)) { sig in
                                    HStack {
                                        VStack(alignment: .leading) {
                                            Text(sig.symbol).fontWeight(.medium)
                                            if let sector = sig.sector {
                                                Text(sector).font(.caption).foregroundStyle(Theme.textDimmed)
                                            }
                                        }
                                        Spacer()
                                        if let price = sig.price {
                                            Text(Formatting.currency(price))
                                                .font(.caption)
                                                .foregroundStyle(Theme.textMuted)
                                        }
                                        SignalBadgeView(signal: sig.signal, strength: sig.strength)
                                    }
                                    .padding(12)
                                    .glassCard()
                                }
                            }
                        }
                    }

                    // Equity chart
                    if isLoading && snapshots == nil {
                        VStack(alignment: .leading, spacing: 12) {
                            // Header: "Equity Curve" + range picker buttons
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
                            // Chart area
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
                    if isLoading && signals == nil {
                        VStack(alignment: .leading, spacing: 12) {
                            RoundedRectangle(cornerRadius: 4)
                                .fill(Color.white.opacity(0.06))
                                .frame(width: 120, height: 14)
                            // Horizontal bars of varying width like a bar chart
                            ForEach([0.75, 0.55, 0.35, 0.2], id: \.self) { pct in
                                HStack(spacing: 8) {
                                    RoundedRectangle(cornerRadius: 4)
                                        .fill(Color.white.opacity(0.06))
                                        .frame(width: 70, height: 14) // sector label
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
                    } else if let signals, !signals.sectorExposure.isEmpty {
                        SectorChartView(exposure: signals.sectorExposure)
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
        async let sigs = client.getRecommendations()

        do {
            portfolio = try await p
            pnl = try await pnlData
            snapshots = try await snap
            signals = try await sigs
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }
}
