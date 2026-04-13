import SwiftUI

/// Portfolio page matching web's portfolio/page.tsx — holdings list with P&L and advice.
struct PortfolioView: View {
    @EnvironmentObject private var config: AppConfig

    @State private var portfolio: PortfolioSummary?
    @State private var isLoading = true
    @State private var selectedHolding: HoldingAdvice?
    @State private var searchText = ""
    @State private var showCashEdit = false
    @State private var cashEditText = ""
    @State private var isSavingCash = false

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    private var filteredHoldings: [HoldingAdvice] {
        guard let holdings = portfolio?.holdings else { return [] }
        if searchText.isEmpty { return holdings }
        return holdings.filter { $0.symbol.localizedCaseInsensitiveContains(searchText) }
    }

    var body: some View {
        NavigationStack {
            List {
                // Summary section
                if let portfolio {
                    Section {
                        HStack {
                            Text("Total Value")
                            Spacer()
                            Text(Formatting.currency(portfolio.totalValue))
                                .fontWeight(.semibold)
                        }
                        Button {
                            cashEditText = String(format: "%.2f", portfolio.cash)
                            showCashEdit = true
                        } label: {
                            HStack {
                                Text("Cash")
                                Spacer()
                                Text(Formatting.currency(portfolio.cash))
                                Image(systemName: "pencil")
                                    .font(.caption2)
                                    .foregroundStyle(Theme.textDimmed)
                            }
                        }
                        .buttonStyle(.plain)
                        HStack {
                            Text("Total P&L")
                            Spacer()
                            Text(Formatting.currency(portfolio.totalPnl))
                                .foregroundStyle(Formatting.pnlColor(portfolio.totalPnl))
                            Text(Formatting.percent(portfolio.totalPnlPct))
                                .font(.caption)
                                .foregroundStyle(Formatting.pnlColor(portfolio.totalPnlPct))
                        }
                    } header: {
                        Text("Summary")
                    }
                }

                // Holdings
                Section {
                    if isLoading && portfolio == nil {
                        ForEach(0..<4, id: \.self) { _ in
                            HoldingRowSkeleton()
                        }
                    } else if filteredHoldings.isEmpty {
                        Text("No holdings")
                            .foregroundStyle(Theme.textDimmed)
                    } else {
                        ForEach(filteredHoldings) { holding in
                            Button {
                                selectedHolding = holding
                            } label: {
                                HoldingRow(holding: holding)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                } header: {
                    Text("Holdings (\(portfolio?.holdings.count ?? 0))")
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Portfolio")
            .searchable(text: $searchText, prompt: "Filter holdings")
            .refreshable { await loadData() }
            .task { await loadData() }
            .sheet(item: $selectedHolding) { holding in
                HoldingDetailSheet(holding: holding, client: client) {
                    await loadData()
                }
            }
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
        isSavingCash = true
        defer { isSavingCash = false }
        do {
            try await client.updateCash(value)
            NotificationCenter.default.post(name: .portfolioDidChange, object: nil)
            await loadData()
        } catch { /* silent */ }
    }

    private func loadData() async {
        isLoading = true
        defer { isLoading = false }
        do {
            portfolio = try await client.getHoldings()
        } catch {
            // Silent — pull-to-refresh will retry
        }
    }
}

// MARK: - Holding Row

private struct HoldingRow: View {
    let holding: HoldingAdvice

    var body: some View {
        VStack(spacing: 8) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(holding.symbol)
                        .fontWeight(.medium)
                    Text("\(Formatting.number(holding.quantity, decimals: 4)) shares")
                        .font(.caption)
                        .foregroundStyle(Theme.textDimmed)
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 2) {
                    Text(Formatting.currency(holding.marketValue))
                        .fontWeight(.medium)
                    Text(Formatting.percent(holding.pnlPct))
                        .font(.caption)
                        .foregroundStyle(Formatting.pnlColor(holding.pnlPct))
                }
            }
            HStack {
                Text("Avg: \(Formatting.currency(holding.avgCost))")
                    .font(.caption2)
                    .foregroundStyle(Theme.textDimmed)
                Text("Now: \(Formatting.currency(holding.currentPrice))")
                    .font(.caption2)
                    .foregroundStyle(Theme.textDimmed)
                Spacer()
                SignalBadgeView(signal: holding.signal, strength: holding.strength)
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Holding Detail Sheet

private struct HoldingDetailSheet: View {
    let holding: HoldingAdvice
    let client: APIClient
    let onDismiss: () async -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var editQuantity: String = ""
    @State private var editAvgCost: String = ""
    @State private var isSaving = false

    var body: some View {
        NavigationStack {
            List {
                Section("Position") {
                    LabeledContent("Symbol", value: holding.symbol)
                    LabeledContent("Quantity", value: Formatting.number(holding.quantity, decimals: 4))
                    LabeledContent("Avg Cost", value: Formatting.currency(holding.avgCost))
                    LabeledContent("Current Price", value: Formatting.currency(holding.currentPrice))
                    LabeledContent("Market Value", value: Formatting.currency(holding.marketValue))
                    HStack {
                        Text("P&L")
                        Spacer()
                        Text(Formatting.currency(holding.pnl))
                            .foregroundStyle(Formatting.pnlColor(holding.pnl))
                        Text(Formatting.percent(holding.pnlPct))
                            .font(.caption)
                            .foregroundStyle(Formatting.pnlColor(holding.pnlPct))
                    }
                }

                Section("Signal") {
                    HStack {
                        Text("Signal")
                        Spacer()
                        SignalBadgeView(signal: holding.signal, strength: holding.strength)
                    }
                    LabeledContent("Action", value: holding.action)
                    Text(holding.actionDetail)
                        .font(.caption)
                        .foregroundStyle(Theme.textMuted)
                }

                Section("Score Breakdown") {
                    ScoreMixCard(
                        technical: holding.technicalScore,
                        sentiment: holding.sentimentScore,
                        commodity: holding.commodityScore,
                        total: holding.technicalScore + holding.sentimentScore + holding.commodityScore
                    )
                    ForEach(holding.reasons, id: \.self) { reason in
                        ScoreReasonRow(text: reason)
                    }
                }

                Section("Edit") {
                    TextField("New quantity", text: $editQuantity)
                        .keyboardType(.decimalPad)
                    TextField("New avg cost", text: $editAvgCost)
                        .keyboardType(.decimalPad)

                    Button("Save Changes") {
                        Task { await saveEdits() }
                    }
                    .disabled(isSaving || (editQuantity.isEmpty && editAvgCost.isEmpty))

                    Button("Delete Holding", role: .destructive) {
                        Task { await deleteHolding() }
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle(holding.symbol)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }

    private func saveEdits() async {
        isSaving = true
        defer { isSaving = false }
        let qty = Double(editQuantity)
        let cost = Double(editAvgCost)
        do {
            try await client.updateHolding(symbol: holding.symbol, quantity: qty, avgCost: cost)
            NotificationCenter.default.post(name: .portfolioDidChange, object: nil)
            await onDismiss()
            dismiss()
        } catch { /* toast would be nice */ }
    }

    private func deleteHolding() async {
        do {
            try await client.deleteHolding(symbol: holding.symbol)
            NotificationCenter.default.post(name: .portfolioDidChange, object: nil)
            await onDismiss()
            dismiss()
        } catch { /* toast */ }
    }
}
