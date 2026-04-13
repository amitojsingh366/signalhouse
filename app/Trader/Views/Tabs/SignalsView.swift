import Combine
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
    @State private var showSnoozed = false
    @State private var snoozeTarget: String?  // symbol to snooze (triggers sheet)

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

    private var activeSells: [ActionItem] {
        actionPlan?.actions.filter { $0.type == "SELL" && $0.snoozed != true } ?? []
    }
    private var activeSwaps: [ActionItem] {
        actionPlan?.actions.filter { $0.type == "SWAP" && $0.snoozed != true } ?? []
    }
    private var actionableBuys: [ActionItem] {
        actionPlan?.actions.filter { $0.type == "BUY" && $0.actionable != false } ?? []
    }
    private var signalOnlyBuys: [ActionItem] {
        actionPlan?.actions.filter { $0.type == "BUY" && $0.actionable == false } ?? []
    }
    private var snoozedActions: [ActionItem] {
        actionPlan?.actions.filter { $0.snoozed == true } ?? []
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
                if !activeSells.isEmpty {
                    Section {
                        ForEach(activeSells) { action in
                            NavigationLink {
                                ActionDetailView(action: action)
                            } label: {
                                SellActionRow(action: action)
                            }
                            .swipeActions(edge: .trailing) {
                                Button {
                                    snoozeTarget = action.symbol ?? action.sellSymbol ?? ""
                                } label: {
                                    Label("Snooze", systemImage: "bell.slash")
                                }
                                .tint(.gray)
                            }
                        }
                    } header: {
                        Label("Sells", systemImage: "arrow.down.circle.fill")
                            .foregroundStyle(Theme.negative)
                    } footer: {
                        Text("Execute these first — stops, profit-taking, and exit signals. Swipe left to snooze.")
                    }
                }

                // Swaps
                if !activeSwaps.isEmpty {
                    Section {
                        ForEach(activeSwaps) { action in
                            NavigationLink {
                                ActionDetailView(action: action)
                            } label: {
                                SwapActionRow(action: action)
                            }
                            .swipeActions(edge: .trailing) {
                                Button {
                                    Task { await snooze(action.sellSymbol ?? "") }
                                } label: {
                                    Label("Snooze", systemImage: "bell.slash")
                                }
                                .tint(.gray)
                            }
                        }
                    } header: {
                        Label("Swaps", systemImage: "arrow.left.arrow.right.circle.fill")
                            .foregroundStyle(Theme.brand)
                    } footer: {
                        Text("Replace weaker holdings with stronger opportunities")
                    }
                }

                // Actionable Buys
                if !actionableBuys.isEmpty {
                    Section {
                        ForEach(actionableBuys) { action in
                            NavigationLink {
                                ActionDetailView(action: action)
                            } label: {
                                BuyActionRow(action: action)
                            }
                        }
                    } header: {
                        Label("Buys", systemImage: "arrow.up.circle.fill")
                            .foregroundStyle(Theme.positive)
                    } footer: {
                        Text("You have the cash and slots to execute these")
                    }
                }

                // Signal-only Buys (not enough cash)
                if !signalOnlyBuys.isEmpty {
                    Section {
                        ForEach(signalOnlyBuys) { action in
                            NavigationLink {
                                ActionDetailView(action: action)
                            } label: {
                                SignalOnlyBuyRow(action: action)
                            }
                        }
                    } header: {
                        Label("Signals", systemImage: "dollarsign.circle.fill")
                            .foregroundStyle(Theme.warning)
                    } footer: {
                        Text("Strong buy signals, but not enough cash — free up funds or add cash to unlock")
                    }
                }

                // Snoozed actions
                if !snoozedActions.isEmpty {
                    Section {
                        DisclosureGroup(isExpanded: $showSnoozed) {
                            ForEach(snoozedActions) { action in
                                NavigationLink {
                                    ActionDetailView(action: action)
                                } label: {
                                    SnoozedActionRow(action: action)
                                }
                                .swipeActions(edge: .trailing) {
                                    Button {
                                        let sym = action.symbol ?? action.sellSymbol ?? ""
                                        Task { await unsnooze(sym) }
                                    } label: {
                                        Label("Unsnooze", systemImage: "bell")
                                    }
                                    .tint(Theme.brand)
                                }
                            }
                        } label: {
                            Label("\(snoozedActions.count) snoozed signal\(snoozedActions.count > 1 ? "s" : "")",
                                  systemImage: "bell.slash")
                                .foregroundStyle(Theme.textDimmed)
                        }
                    }
                }

                // No actions
                if !isLoading && actionPlan != nil && activeSells.isEmpty && activeSwaps.isEmpty && actionableBuys.isEmpty && signalOnlyBuys.isEmpty && snoozedActions.isEmpty {
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
            .sheet(isPresented: Binding(
                get: { snoozeTarget != nil },
                set: { if !$0 { snoozeTarget = nil } }
            )) {
                if let symbol = snoozeTarget {
                    SnoozeSheet(symbol: symbol) { hours, indefinite, phantomTrailingStop in
                        snoozeTarget = nil
                        Task { await snooze(symbol, hours: hours, indefinite: indefinite, phantomTrailingStop: phantomTrailingStop) }
                    }
                    .presentationDetents([.medium])
                    .presentationDragIndicator(.visible)
                }
            }
            .refreshable { await loadData() }
            .task { await loadData() }
            .onReceive(NotificationCenter.default.publisher(for: .portfolioDidChange)) { _ in
                Task { await loadData() }
            }
            .onChange(of: pushManager.deepLink) { _, link in
                if case .signalCheck(let symbol) = link {
                    searchText = symbol
                    Task { await checkSymbol(symbol) }
                }
            }
        }
    }

    private func snooze(_ symbol: String, hours: Double = 4, indefinite: Bool = false, phantomTrailingStop: Bool = true) async {
        guard !symbol.isEmpty else { return }
        do {
            _ = try await client.snoozeSignal(symbol: symbol, hours: hours, indefinite: indefinite, phantomTrailingStop: phantomTrailingStop)
            await loadData()
        } catch { /* ignore */ }
    }

    private func unsnooze(_ symbol: String) async {
        guard !symbol.isEmpty else { return }
        do {
            try await client.unsnoozeSignal(symbol: symbol)
            await loadData()
        } catch { /* ignore */ }
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

            if action.technicalScore != nil || action.sentimentScore != nil || action.commodityScore != nil {
                ScoreMixCard(
                    technical: action.technicalScore ?? 0,
                    sentiment: action.sentimentScore ?? 0,
                    commodity: action.commodityScore ?? 0
                )
            }

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

// MARK: - Signal-Only Buy Row (not enough cash)

private struct SignalOnlyBuyRow: View {
    let action: ActionItem

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "arrow.up.circle")
                    .foregroundStyle(Theme.textDimmed)
                Text(action.symbol ?? "")
                    .font(.headline)
                Spacer()
                Text("SIGNAL ONLY")
                    .font(.caption2)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Theme.warning.opacity(0.2))
                    .clipShape(Capsule())
                    .foregroundStyle(Theme.warning)
                if let strength = action.strength {
                    SignalBadgeView(signal: "BUY", strength: strength)
                }
            }

            Text(action.detail)
                .font(.subheadline)
                .foregroundStyle(Theme.warning)

            HStack(spacing: 12) {
                if let price = action.price {
                    Text("~\(Formatting.currency(price))")
                }
                if let sector = action.sector {
                    Text(sector)
                }
            }
            .font(.caption)
            .foregroundStyle(Theme.textDimmed)

            if action.technicalScore != nil || action.sentimentScore != nil || action.commodityScore != nil {
                ScoreMixCard(
                    technical: action.technicalScore ?? 0,
                    sentiment: action.sentimentScore ?? 0,
                    commodity: action.commodityScore ?? 0
                )
            }

            // Score reasons
            if let reasons = action.reasons {
                let filtered = reasons.filter { !$0.hasPrefix("Price:") && !$0.hasPrefix("ATR:") }.prefix(3)
                ForEach(Array(filtered.enumerated()), id: \.offset) { _, reason in
                    ScoreReasonRow(text: reason)
                }
            }
        }
        .padding(.vertical, 4)
        .opacity(0.75)
    }
}

// MARK: - Snoozed Action Row

private struct SnoozedActionRow: View {
    let action: ActionItem

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Image(systemName: "bell.slash")
                    .foregroundStyle(Theme.textDimmed)
                Text(action.symbol ?? action.sellSymbol ?? "")
                    .font(.headline)
                    .foregroundStyle(Theme.textMuted)
                Spacer()
                Text(action.type)
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(Color.gray.opacity(0.2))
                    .clipShape(Capsule())
                    .foregroundStyle(Theme.textDimmed)
            }
            Text(action.detail)
                .font(.caption)
                .foregroundStyle(Theme.textDimmed)
            Text("Swipe left to unsnooze")
                .font(.caption2)
                .foregroundStyle(Theme.textDimmed.opacity(0.6))
        }
        .padding(.vertical, 4)
        .opacity(0.6)
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
            ScoreMixCard(
                technical: signal.technicalScore,
                sentiment: signal.sentimentScore,
                commodity: signal.commodityScore
            )

            ForEach(signal.reasons, id: \.self) { reason in
                ScoreReasonRow(text: reason)
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Snooze Sheet

private struct SnoozeDuration: Identifiable {
    let id: String
    let label: String
    let hours: Double

    static let options: [SnoozeDuration] = [
        .init(id: "1h", label: "1 hour", hours: 1),
        .init(id: "4h", label: "4 hours", hours: 4),
        .init(id: "8h", label: "8 hours", hours: 8),
        .init(id: "24h", label: "24 hours", hours: 24),
        .init(id: "3d", label: "3 days", hours: 72),
        .init(id: "7d", label: "7 days", hours: 168),
    ]
}

private struct SnoozeSheet: View {
    let symbol: String
    let onConfirm: (_ hours: Double, _ indefinite: Bool, _ phantomTrailingStop: Bool) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var selectedDuration = "4h"
    @State private var indefinite = false
    @State private var phantomTrailingStop = true

    var body: some View {
        NavigationStack {
            List {
                Section {
                    ForEach(SnoozeDuration.options) { dur in
                        Button {
                            selectedDuration = dur.id
                            indefinite = false
                        } label: {
                            HStack {
                                Text(dur.label)
                                    .foregroundStyle(Color.primary)
                                Spacer()
                                if !indefinite && selectedDuration == dur.id {
                                    Image(systemName: "checkmark")
                                        .foregroundStyle(Theme.brand)
                                }
                            }
                        }
                    }

                    Button {
                        indefinite.toggle()
                    } label: {
                        HStack {
                            Label("Indefinite", systemImage: "infinity")
                                .foregroundStyle(Color.primary)
                            Spacer()
                            if indefinite {
                                Image(systemName: "checkmark")
                                    .foregroundStyle(Theme.brand)
                            }
                        }
                    }
                } header: {
                    Text("Duration")
                }

                Section {
                    Toggle(isOn: $phantomTrailingStop) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Phantom trailing stop")
                            Text("Auto-unsnooze and notify if loss worsens by 3%+ from current level")
                                .font(.caption)
                                .foregroundStyle(Theme.textDimmed)
                        }
                    }
                    .tint(Theme.brand)
                } header: {
                    Text("Safety")
                }
            }
            .navigationTitle("Snooze \(symbol)")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Snooze") {
                        let hours = SnoozeDuration.options.first { $0.id == selectedDuration }?.hours ?? 4
                        onConfirm(hours, indefinite, phantomTrailingStop)
                    }
                    .fontWeight(.semibold)
                }
            }
        }
    }
}
