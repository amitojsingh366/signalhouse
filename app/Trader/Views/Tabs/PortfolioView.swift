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
                            .font(.system(size: 10, weight: .medium, design: .monospaced))
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
                                                .font(.system(size: 10, weight: .semibold))
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
                                    .font(.system(size: 13))
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
                    .font(.system(size: 14, weight: .semibold, design: .monospaced))
                    .foregroundStyle(Theme.textPrimary)
                Text("\(Formatting.number(holding.quantity, decimals: 4)) sh · avg \(Formatting.currency(holding.avgCost)) · now \(Formatting.currency(holding.currentPrice))")
                    .font(.system(size: 11, weight: .regular, design: .monospaced))
                    .foregroundStyle(Theme.textDimmed)
                    .lineLimit(1)
                MobileSignalPill(text: "\(holding.signal) · \(Int((holding.strength * 100).rounded()))%", style: signalStyle)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 5) {
                Text(Formatting.currency(holding.marketValue))
                    .font(.system(size: 14, weight: .semibold, design: .monospaced))
                    .foregroundStyle(Theme.textPrimary)
                Text(Formatting.percent(holding.pnlPct))
                    .font(.system(size: 11, weight: .semibold, design: .monospaced))
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
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.textMuted)
                    .padding(16)
            } else {
                ForEach(Array(sectors.prefix(4).enumerated()), id: \.offset) { index, sector in
                    HStack(spacing: 10) {
                        Text(sector.0.capitalized)
                            .font(.system(size: 12, weight: .medium))
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
                            .font(.system(size: 11, weight: .medium, design: .monospaced))
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

    private var totalScore: Double {
        holding.technicalScore + holding.sentimentScore + holding.commodityScore
    }

    var body: some View {
        MobileScreen {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 14) {
                    MobileSectionLabel("Position")
                    MobileCard {
                        MobileDefRow(label: "Symbol") { MobileValueLabel(text: holding.symbol, color: Theme.textPrimary) }
                        Divider().overlay(Theme.line)
                        MobileDefRow(label: "Quantity") { MobileValueLabel(text: Formatting.number(holding.quantity, decimals: 4)) }
                        Divider().overlay(Theme.line)
                        MobileDefRow(label: "Avg cost") { MobileValueLabel(text: Formatting.currency(holding.avgCost)) }
                        Divider().overlay(Theme.line)
                        MobileDefRow(label: "Current") { MobileValueLabel(text: Formatting.currency(holding.currentPrice)) }
                        Divider().overlay(Theme.line)
                        MobileDefRow(label: "Market value") { MobileValueLabel(text: Formatting.currency(holding.marketValue), color: Theme.textPrimary) }
                        Divider().overlay(Theme.line)
                        MobileDefRow(label: "P&L") {
                            MobileValueLabel(
                                text: "\(Formatting.currency(holding.pnl)) · \(Formatting.percent(holding.pnlPct))",
                                color: Formatting.pnlColor(holding.pnlPct)
                            )
                        }
                    }

                    MobileSectionLabel("Signal")
                    MobileCard {
                        MobileDefRow(label: "Recommendation") {
                            SignalBadgeView(signal: holding.signal, strength: holding.strength)
                        }
                        Divider().overlay(Theme.line)
                        MobileDefRow(label: "Action") {
                            MobileValueLabel(text: holding.action.uppercased(), color: Theme.textPrimary)
                        }
                        Divider().overlay(Theme.line)
                        Text(holding.actionDetail)
                            .font(.system(size: 12))
                            .foregroundStyle(Theme.textMuted)
                            .padding(16)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }

                    MobileSectionLabel("Score Breakdown")
                    MobileCard {
                        ScoreMixCard(
                            technical: holding.technicalScore,
                            sentiment: holding.sentimentScore,
                            commodity: holding.commodityScore,
                            total: totalScore
                        )
                        .padding(16)
                        ForEach(holding.reasons, id: \.self) { reason in
                            Divider().overlay(Theme.line)
                            HStack(spacing: 10) {
                                Circle()
                                    .fill(reason.contains("-") ? Theme.negative : Theme.positive)
                                    .frame(width: 6, height: 6)
                                ScoreReasonRow(text: reason)
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, 11)
                        }
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 8)
                .padding(.bottom, 60)
            }
        }
        .navigationTitle(holding.symbol)
        .navigationBarTitleDisplayMode(.inline)
    }
}
