import SwiftUI

/// Action Plan page — prioritized, position-sized trade instructions.
struct SignalsView: View {
    @EnvironmentObject private var config: AppConfig
    @EnvironmentObject private var pushManager: PushManager

    @State private var actionPlan: ActionPlanOut?
    @State private var isLoading = true
    @State private var searchText = ""
    @State private var checkedSignal: SignalOut?
    @State private var isChecking = false
    @State private var allSymbols: [SymbolInfo] = []

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    private var searchSuggestions: [SymbolInfo] {
        let query = searchText.trimmingCharacters(in: .whitespaces)
        guard query.count >= 1 else { return [] }
        let upper = query.uppercased()
        return allSymbols.filter {
            $0.symbol.uppercased().contains(upper) || $0.name.uppercased().contains(upper)
        }.prefix(8).map { $0 }
    }

    private var sells: [ActionItem] {
        actionPlan?.actions.filter { $0.type == "SELL" } ?? []
    }
    private var swaps: [ActionItem] {
        actionPlan?.actions.filter { $0.type == "SWAP" } ?? []
    }
    private var buys: [ActionItem] {
        actionPlan?.actions.filter { $0.type == "BUY" } ?? []
    }

    var body: some View {
        NavigationStack {
            List {
                // Portfolio summary
                if let plan = actionPlan {
                    Section {
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Portfolio")
                                    .font(.caption)
                                    .foregroundStyle(Theme.textDimmed)
                                Text(Formatting.currency(plan.portfolioValue))
                                    .font(.headline)
                            }
                            Spacer()
                            VStack(alignment: .center, spacing: 2) {
                                Text("Cash")
                                    .font(.caption)
                                    .foregroundStyle(Theme.textDimmed)
                                Text(Formatting.currency(plan.cash))
                                    .font(.headline)
                            }
                            Spacer()
                            VStack(alignment: .trailing, spacing: 2) {
                                Text("Positions")
                                    .font(.caption)
                                    .foregroundStyle(Theme.textDimmed)
                                Text("\(plan.numPositions)/\(plan.maxPositions)")
                                    .font(.headline)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                }

                // Search result
                if let checkedSignal {
                    Section("Search Result") {
                        NavigationLink {
                            SignalDetailView(signal: checkedSignal)
                        } label: {
                            SignalCardContent(signal: checkedSignal)
                        }
                    }
                }

                // Sells
                if !sells.isEmpty {
                    Section {
                        ForEach(sells) { action in
                            SellActionRow(action: action)
                        }
                    } header: {
                        Label("Sells", systemImage: "arrow.down.circle.fill")
                            .foregroundStyle(Theme.negative)
                    } footer: {
                        Text("Execute these first — stops, profit-taking, and exit signals")
                    }
                }

                // Swaps
                if !swaps.isEmpty {
                    Section {
                        ForEach(swaps) { action in
                            SwapActionRow(action: action)
                        }
                    } header: {
                        Label("Swaps", systemImage: "arrow.left.arrow.right.circle.fill")
                            .foregroundStyle(Theme.brand)
                    } footer: {
                        Text("Replace weaker holdings with stronger opportunities")
                    }
                }

                // Buys
                if !buys.isEmpty {
                    Section {
                        ForEach(buys) { action in
                            BuyActionRow(action: action)
                        }
                    } header: {
                        Label("Buys", systemImage: "arrow.up.circle.fill")
                            .foregroundStyle(Theme.positive)
                    } footer: {
                        Text("New positions — only if you have available slots and cash")
                    }
                }

                // No actions
                if !isLoading && actionPlan != nil && sells.isEmpty && swaps.isEmpty && buys.isEmpty {
                    Section {
                        ContentUnavailableView {
                            Label("No Trades Needed", systemImage: "checkmark.circle")
                        } description: {
                            Text("Portfolio is on track. Check back later.")
                        }
                    }
                }

                // Loading
                if isLoading && actionPlan == nil {
                    Section {
                        ForEach(0..<4, id: \.self) { _ in
                            SignalCardSkeleton()
                        }
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Action Plan")
            .searchable(text: $searchText, prompt: "Search symbol (e.g. SHOP.TO)")
            .searchSuggestions {
                ForEach(searchSuggestions) { symbol in
                    Button {
                        searchText = symbol.symbol
                        Task { await checkSymbol(symbol.symbol) }
                    } label: {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(symbol.symbol)
                                .fontWeight(.medium)
                            Text("\(symbol.name) \u{2022} \(symbol.sector)")
                                .font(.caption)
                                .foregroundStyle(Theme.textDimmed)
                        }
                    }
                    .searchCompletion(symbol.symbol)
                }
            }
            .onSubmit(of: .search) {
                Task { await checkSymbol(nil) }
            }
            .refreshable { await loadData() }
            .task { await loadData() }
            .onChange(of: pushManager.deepLink) { _, link in
                if case .signalCheck(let symbol) = link {
                    searchText = symbol
                    Task { await checkSymbol(symbol) }
                }
            }
        }
    }

    private func checkSymbol(_ symbolOverride: String?) async {
        let symbol = (symbolOverride ?? searchText).trimmingCharacters(in: .whitespaces).uppercased()
        guard !symbol.isEmpty else { return }
        isChecking = true
        defer { isChecking = false }
        do {
            checkedSignal = try await client.checkSignal(symbol: symbol)
        } catch {
            checkedSignal = nil
        }
    }

    private func loadData() async {
        isLoading = true
        defer { isLoading = false }

        async let planTask = client.getActionPlan()
        async let symsTask = client.getSymbols()

        do {
            actionPlan = try await planTask
        } catch { /* pull-to-refresh retries */ }

        do {
            allSymbols = try await symsTask
        } catch { /* symbols are optional */ }
    }
}

// MARK: - Sell Action Row

private struct SellActionRow: View {
    let action: ActionItem

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: action.urgency == "urgent"
                      ? "exclamationmark.triangle.fill"
                      : "arrow.down.circle")
                    .foregroundStyle(action.urgency == "urgent" ? Theme.negative
                                     : action.urgency == "low" ? Theme.textDimmed
                                     : Theme.warning)
                Text(action.symbol ?? "")
                    .font(.headline)
                Spacer()
                Text(action.urgency == "urgent" ? "URGENT" : action.reason)
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(
                        (action.urgency == "urgent" ? Theme.negative : Theme.warning).opacity(0.2)
                    )
                    .clipShape(Capsule())
                    .foregroundStyle(action.urgency == "urgent" ? Theme.negative : Theme.warning)
            }

            Text(action.detail)
                .font(.subheadline)
                .fontWeight(.medium)

            HStack(spacing: 12) {
                if let shares = action.shares {
                    Text("\(Formatting.number(shares, decimals: 4)) sh")
                }
                if let price = action.price {
                    Text("@ \(Formatting.currency(price))")
                }
                if let amount = action.dollarAmount {
                    Text(Formatting.currency(amount))
                }
                if let pnl = action.pnlPct {
                    Text(Formatting.percent(pnl))
                        .foregroundStyle(Formatting.pnlColor(pnl))
                        .fontWeight(.medium)
                }
            }
            .font(.caption)
            .foregroundStyle(Theme.textDimmed)
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Swap Action Row

private struct SwapActionRow: View {
    let action: ActionItem

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "arrow.left.arrow.right")
                    .foregroundStyle(Theme.brand)
                Text("\(action.sellSymbol ?? "") → \(action.buySymbol ?? "")")
                    .font(.headline)
                Spacer()
                Text("SWAP")
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(Theme.brand.opacity(0.2))
                    .clipShape(Capsule())
                    .foregroundStyle(Theme.brand)
            }

            Text(action.detail)
                .font(.subheadline)
                .fontWeight(.medium)

            HStack(spacing: 16) {
                // Sell side
                VStack(alignment: .leading, spacing: 2) {
                    Text("Sell \(action.sellSymbol ?? "")")
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundStyle(Theme.negative)
                    if let shares = action.sellShares, let price = action.sellPrice {
                        Text("\(Formatting.number(shares, decimals: 4)) sh @ \(Formatting.currency(price))")
                            .font(.caption2)
                            .foregroundStyle(Theme.textDimmed)
                    }
                }

                Spacer()

                // Buy side
                VStack(alignment: .trailing, spacing: 2) {
                    Text("Buy \(action.buySymbol ?? "")")
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundStyle(Theme.positive)
                    if let shares = action.buyShares, let price = action.buyPrice {
                        Text("\(Int(shares)) sh @ ~\(Formatting.currency(price))")
                            .font(.caption2)
                            .foregroundStyle(Theme.textDimmed)
                    }
                }
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Buy Action Row

private struct BuyActionRow: View {
    let action: ActionItem

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "arrow.up.circle")
                    .foregroundStyle(Theme.positive)
                Text(action.symbol ?? "")
                    .font(.headline)
                Spacer()
                if let strength = action.strength {
                    SignalBadgeView(signal: "BUY", strength: strength)
                }
            }

            Text(action.detail)
                .font(.subheadline)
                .fontWeight(.medium)

            HStack(spacing: 12) {
                if let shares = action.shares {
                    Text("\(Int(shares)) shares")
                }
                if let price = action.price {
                    Text("@ ~\(Formatting.currency(price))")
                }
                if let amount = action.dollarAmount {
                    Text(Formatting.currency(amount))
                }
            }
            .font(.caption)
            .foregroundStyle(Theme.textDimmed)

            HStack(spacing: 12) {
                if let pct = action.pctOfPortfolio {
                    Text("\(String(format: "%.1f", pct))% of portfolio")
                }
                if let sector = action.sector {
                    Text(sector)
                }
            }
            .font(.caption2)
            .foregroundStyle(Theme.textDimmed)

            // Score reasons
            if let reasons = action.reasons {
                let filtered = reasons.filter { !$0.hasPrefix("Price:") && !$0.hasPrefix("ATR:") }.prefix(3)
                ForEach(Array(filtered.enumerated()), id: \.offset) { _, reason in
                    ScoreReasonRow(text: reason)
                }
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Signal Card Content (for search results)

private struct SignalCardContent: View {
    let signal: SignalOut

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(signal.symbol)
                    .font(.headline)
                Spacer()
                if signal.score != 0 {
                    Text("\(signal.score > 0 ? "+" : "")\(String(format: "%.1f", signal.score))/9")
                        .font(.caption)
                        .fontDesign(.monospaced)
                        .foregroundStyle(Theme.textDimmed)
                }
                SignalBadgeView(signal: signal.signal, strength: signal.strength)
            }

            if let price = signal.price {
                Text("Price: \(Formatting.currency(price))")
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)
            }
            if let sector = signal.sector {
                Text(sector)
                    .font(.caption2)
                    .foregroundStyle(Theme.textDimmed)
            }

            ForEach(signal.reasons, id: \.self) { reason in
                ScoreReasonRow(text: reason)
            }
        }
        .padding(.vertical, 4)
    }
}
