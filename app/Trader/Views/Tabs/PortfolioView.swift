import SwiftUI

/// Signalhouse portfolio tab and holding drill-in.
struct PortfolioView: View {
    @EnvironmentObject private var config: AppConfig

    @State private var portfolio: PortfolioSummary?
    @State private var actionPlan: ActionPlanOut?
    @State private var isLoading = true
    @State private var searchText = ""
    @State private var showCashEdit = false
    @State private var cashEditText = ""

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    private var filteredHoldings: [HoldingAdvice] {
        guard let holdings = portfolio?.holdings else { return [] }
        let query = searchText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else { return holdings }
        return holdings.filter { $0.symbol.localizedCaseInsensitiveContains(query) }
    }

    var body: some View {
        NavigationStack {
            MobileScreen {
                ScrollView(showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 14) {
                        Text("\(portfolio?.holdings.count ?? 0) positions")
                            .font(AppFont.mono(10, weight: .medium))
                            .tracking(1.4)
                            .foregroundStyle(Theme.brand)

                        MobileSearchField(placeholder: "Filter holdings", text: $searchText)

                        MobileSectionLabel("Summary")

                        MobileCard {
                            Button {
                                if let cash = portfolio?.cash {
                                    cashEditText = String(format: "%.2f", cash)
                                    showCashEdit = true
                                }
                            } label: {
                                VStack(spacing: 0) {
                                    MobileDefRow(label: "Total value") {
                                        MobileValueLabel(text: Formatting.currency(portfolio?.totalValue ?? 0), color: Theme.textPrimary)
                                    }
                                    Divider().overlay(Theme.line)
                                    MobileDefRow(label: "Cash") {
                                        HStack(spacing: 6) {
                                            MobileValueLabel(text: Formatting.currency(portfolio?.cash ?? 0), color: Theme.textPrimary)
                                            Image(systemName: "pencil")
                                                .font(AppFont.sans(10, weight: .semibold))
                                                .foregroundStyle(Theme.textDimmed)
                                        }
                                    }
                                    Divider().overlay(Theme.line)
                                    MobileDefRow(label: "Total P&L") {
                                        MobileValueLabel(
                                            text: "\(Formatting.currency(portfolio?.totalPnl ?? 0)) · \(Formatting.percent(portfolio?.totalPnlPct ?? 0))",
                                            color: Formatting.pnlColor(portfolio?.totalPnlPct ?? 0)
                                        )
                                    }
                                }
                            }
                            .buttonStyle(.plain)
                        }

                        MobileSectionLabel("Holdings · \(filteredHoldings.count)")

                        MobileCard {
                            if isLoading && portfolio == nil {
                                ForEach(0..<2, id: \.self) { idx in
                                    HoldingRowSkeleton()
                                        .padding(.horizontal, 16)
                                        .padding(.vertical, 10)
                                    if idx == 0 {
                                        Divider().overlay(Theme.line)
                                    }
                                }
                            } else if filteredHoldings.isEmpty {
                                Text("No holdings")
                                    .font(AppFont.sans(13))
                                    .foregroundStyle(Theme.textMuted)
                                    .padding(16)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            } else {
                                ForEach(Array(filteredHoldings.enumerated()), id: \.element.id) { index, holding in
                                    NavigationLink {
                                        HoldingDetailView(holding: holding)
                                    } label: {
                                        HoldingRow(holding: holding)
                                    }
                                    .buttonStyle(.plain)

                                    if index < filteredHoldings.count - 1 {
                                        Divider().overlay(Theme.line)
                                    }
                                }
                            }
                        }

                        MobileSectionLabel("Sector Exposure")

                        if let actionPlan {
                            SectorExposureCard(exposure: actionPlan.sectorExposure)
                        }
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 10)
                    .padding(.bottom, 140)
                }
            }
            .navigationTitle("Portfolio")
            .navigationBarTitleDisplayMode(.large)
            .refreshable { await loadData() }
            .task { await loadData() }
            .alert("Edit Cash Balance", isPresented: $showCashEdit) {
                TextField("Cash amount", text: $cashEditText)
                    .keyboardType(.decimalPad)
                Button("Cancel", role: .cancel) {}
                Button("Save") {
                    Task { await saveCash() }
                }
            } message: {
                Text("Enter new cash balance")
            }
        }
    }

    private func saveCash() async {
        guard let value = Double(cashEditText) else { return }
        do {
            try await client.updateCash(value)
            NotificationCenter.default.post(name: .portfolioDidChange, object: nil)
            await loadData()
        } catch {}
    }

    private func loadData() async {
        isLoading = true
        defer { isLoading = false }
        async let holdingsTask = client.getHoldings()
        async let actionPlanTask = client.getActionPlan()
        do { portfolio = try await holdingsTask } catch {}
        do { actionPlan = try await actionPlanTask } catch {}
    }
}

private struct HoldingRow: View {
    let holding: HoldingAdvice

    private var signalStyle: MobileSignalStyle {
        switch holding.signal.uppercased() {
        case "BUY": return .buy
        case "SELL": return .sell
        case "HOLD": return .hold
        default: return .neutral
        }
    }

    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 5) {
                Text(holding.symbol)
                    .font(AppFont.mono(14, weight: .semibold))
                    .foregroundStyle(Theme.textPrimary)
                Text("\(Formatting.number(holding.quantity, decimals: 4)) sh · avg \(Formatting.currency(holding.avgCost)) · now \(Formatting.currency(holding.currentPrice))")
                    .font(AppFont.mono(12, weight: .regular))
                    .foregroundStyle(Theme.textDimmed)
                    .lineLimit(1)
                MobileSignalPill(text: "\(holding.signal) · \(Int((holding.strength * 100).rounded()))%", style: signalStyle)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 5) {
                Text(Formatting.currency(holding.marketValue))
                    .font(AppFont.mono(14, weight: .semibold))
                    .foregroundStyle(Theme.textPrimary)
                Text(Formatting.percent(holding.pnlPct))
                    .font(AppFont.mono(12, weight: .semibold))
                    .foregroundStyle(Formatting.pnlColor(holding.pnlPct))
            }
        }
        .padding(16)
    }
}

private struct SectorExposureCard: View {
    let exposure: [String: AnyCodable]

    private var sectors: [(String, Double)] {
        exposure.compactMap { key, value in
            if let dict = value.value as? [String: Any], let pct = dict["pct"] as? Double {
                return (key, pct)
            }
            if let pct = value.value as? Double {
                return (key, pct)
            }
            return nil
        }
        .sorted { $0.1 > $1.1 }
    }

    var body: some View {
        MobileCard {
            if sectors.isEmpty {
                Text("No sector data")
                    .font(AppFont.sans(12))
                    .foregroundStyle(Theme.textMuted)
                    .padding(16)
            } else {
                ForEach(Array(sectors.prefix(4).enumerated()), id: \.offset) { index, sector in
                    HStack(spacing: 10) {
                        Text(sector.0.capitalized)
                            .font(AppFont.sans(12, weight: .medium))
                            .foregroundStyle(Theme.textPrimary)
                            .frame(width: 90, alignment: .leading)

                        GeometryReader { geo in
                            RoundedRectangle(cornerRadius: 4)
                                .fill(Theme.surface2)
                                .overlay(alignment: .leading) {
                                    RoundedRectangle(cornerRadius: 4)
                                        .fill(
                                            LinearGradient(
                                                colors: [Theme.brand, Theme.brandStrong],
                                                startPoint: .leading,
                                                endPoint: .trailing
                                            )
                                        )
                                        .frame(width: max(geo.size.width * min(max(sector.1, 0), 1), 2))
                                }
                        }
                        .frame(height: 8)

                        Text(Formatting.percent(sector.1 * 100))
                            .font(AppFont.mono(12, weight: .medium))
                            .foregroundStyle(Theme.brand)
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)

                    if index < min(sectors.count, 4) - 1 {
                        Divider().overlay(Theme.line)
                    }
                }
            }
        }
    }
}

struct HoldingDetailView: View {
    let holding: HoldingAdvice

    var body: some View {
        InstrumentDetailView(
            snapshot: InstrumentSignalSnapshot(holding: holding),
            position: holding
        )
    }
}
