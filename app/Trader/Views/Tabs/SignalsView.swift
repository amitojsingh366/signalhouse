import Combine
import SwiftUI

/// Signalhouse action plan tab (named "Actions" in the handoff).
struct SignalsView: View {
    @EnvironmentObject private var config: AppConfig
    @EnvironmentObject private var pushManager: PushManager

    @State private var actionPlan: ActionPlanOut?
    @State private var isLoading = true
    @State private var searchText = ""
    @State private var checkedSignal: SignalOut?
    @State private var showSnoozed = false
    @State private var snoozeTarget: String?

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    private var activeSells: [ActionItem] {
        actionPlan?.actions.filter { $0.type == "SELL" && $0.snoozed != true } ?? []
    }

    private var activeSwaps: [ActionItem] {
        actionPlan?.actions.filter { $0.type == "SWAP" && $0.snoozed != true } ?? []
    }

    private var activeBuys: [ActionItem] {
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
            MobileScreen {
                ScrollView(showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 14) {
                        Text("LIVE · TSX OPEN")
                            .font(.system(size: 10, weight: .medium, design: .monospaced))
                            .tracking(1.4)
                            .foregroundStyle(Theme.brand)

                        MobileSearchField(placeholder: "Search symbol (e.g. SHOP.TO)", text: $searchText)
                            .onSubmit {
                                Task { await checkSymbol(nil) }
                            }

                        if let plan = actionPlan {
                            LazyVGrid(columns: [.init(.flexible()), .init(.flexible()), .init(.flexible())], spacing: 8) {
                                ActionSummaryCard(title: "Portfolio", value: Formatting.currency(plan.portfolioValue))
                                ActionSummaryCard(title: "Cash", value: Formatting.currency(plan.cash))
                                ActionSummaryCard(title: "Positions", value: "\(plan.numPositions) / \(plan.maxPositions)")
                            }
                        }

                        if let checkedSignal {
                            MobileSectionLabel("Search Result")
                            MobileCard {
                                NavigationLink {
                                    SignalDetailView(signal: checkedSignal)
                                } label: {
                                    SignalCardContent(signal: checkedSignal)
                                }
                                .buttonStyle(.plain)
                                .padding(16)
                            }
                        }

                        if !activeSells.isEmpty {
                            MobileSectionLabel("Sells · \(activeSells.count)")
                            ActionGroupCard(actions: activeSells, style: .sell) { action in
                                snoozeTarget = action.symbol ?? action.sellSymbol
                            }
                            Text("Execute these first — stops, profit-taking, and exit signals.")
                                .font(.system(size: 11))
                                .foregroundStyle(Theme.textDimmed)
                        }

                        if !activeSwaps.isEmpty {
                            MobileSectionLabel("Swaps · \(activeSwaps.count)")
                            ActionGroupCard(actions: activeSwaps, style: .swap) { action in
                                snoozeTarget = action.sellSymbol
                            }
                        }

                        if !activeBuys.isEmpty {
                            MobileSectionLabel("Buys · \(activeBuys.count)")
                            ActionGroupCard(actions: activeBuys, style: .buy, onSnooze: nil)
                        }

                        if !signalOnlyBuys.isEmpty {
                            MobileSectionLabel("Signal-only Buys · \(signalOnlyBuys.count)")
                            ActionGroupCard(actions: signalOnlyBuys, style: .signalOnly, onSnooze: nil)
                        }

                        if !snoozedActions.isEmpty {
                            Button {
                                withAnimation(.easeInOut(duration: 0.2)) {
                                    showSnoozed.toggle()
                                }
                            } label: {
                                MobileSectionLabel("\(snoozedActions.count) snoozed signal\(snoozedActions.count == 1 ? "" : "s")") {
                                    Image(systemName: showSnoozed ? "chevron.up" : "chevron.down")
                                        .font(.system(size: 11, weight: .semibold))
                                        .foregroundStyle(Theme.textDimmed)
                                }
                            }
                            .buttonStyle(.plain)

                            if showSnoozed {
                                ActionGroupCard(actions: snoozedActions, style: .snoozed) { action in
                                    let symbol = action.symbol ?? action.sellSymbol ?? ""
                                    Task { await unsnooze(symbol) }
                                }
                            }
                        }

                        if !isLoading && actionPlan != nil && activeSells.isEmpty && activeSwaps.isEmpty && activeBuys.isEmpty && signalOnlyBuys.isEmpty && snoozedActions.isEmpty {
                            MobileCard {
                                Text("No trades needed right now")
                                    .font(.system(size: 13))
                                    .foregroundStyle(Theme.textMuted)
                                    .padding(16)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
                        }

                        if isLoading && actionPlan == nil {
                            MobileCard {
                                VStack(spacing: 0) {
                                    ForEach(0..<3, id: \.self) { idx in
                                        DashboardSignalSkeleton()
                                            .padding(.horizontal, 8)
                                            .padding(.vertical, 8)
                                        if idx < 2 {
                                            Divider().overlay(Theme.line)
                                        }
                                    }
                                }
                            }
                        }
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 10)
                    .padding(.bottom, 140)
                }
            }
            .navigationTitle("Action plan")
            .navigationBarTitleDisplayMode(.large)
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
            .sheet(isPresented: Binding(
                get: { snoozeTarget != nil },
                set: { if !$0 { snoozeTarget = nil } }
            )) {
                if let symbol = snoozeTarget {
                    SnoozeSheet(symbol: symbol) { hours, indefinite, phantomTrailingStop in
                        snoozeTarget = nil
                        Task {
                            await snooze(symbol, hours: hours, indefinite: indefinite, phantomTrailingStop: phantomTrailingStop)
                        }
                    }
                    .presentationDetents([.medium])
                    .presentationDragIndicator(.visible)
                }
            }
        }
    }

    private func loadData() async {
        isLoading = true
        defer { isLoading = false }
        do {
            actionPlan = try await client.getActionPlan()
        } catch {}
    }

    private func checkSymbol(_ symbolOverride: String?) async {
        let symbol = (symbolOverride ?? searchText).trimmingCharacters(in: .whitespaces).uppercased()
        guard !symbol.isEmpty else { return }
        do {
            checkedSignal = try await client.checkSignal(symbol: symbol)
        } catch {
            checkedSignal = nil
        }
    }

    private func snooze(
        _ symbol: String,
        hours: Double = 4,
        indefinite: Bool = false,
        phantomTrailingStop: Bool = true
    ) async {
        guard !symbol.isEmpty else { return }
        do {
            _ = try await client.snoozeSignal(
                symbol: symbol,
                hours: hours,
                indefinite: indefinite,
                phantomTrailingStop: phantomTrailingStop
            )
            await loadData()
        } catch {}
    }

    private func unsnooze(_ symbol: String) async {
        guard !symbol.isEmpty else { return }
        do {
            try await client.unsnoozeSignal(symbol: symbol)
            await loadData()
        } catch {}
    }
}

private struct ActionSummaryCard: View {
    let title: String
    let value: String

    var body: some View {
        MobileCard {
            VStack(alignment: .leading, spacing: 8) {
                Text(title.uppercased())
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                    .tracking(1.2)
                    .foregroundStyle(Theme.textDimmed)
                Text(value)
                    .font(.system(size: 16, weight: .bold, design: .monospaced))
                    .foregroundStyle(Theme.textPrimary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.65)
            }
            .padding(11)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private enum ActionRowStyle {
    case sell
    case swap
    case buy
    case signalOnly
    case snoozed
}

private struct ActionGroupCard: View {
    let actions: [ActionItem]
    let style: ActionRowStyle
    let onSnooze: ((ActionItem) -> Void)?

    var body: some View {
        MobileCard {
            ForEach(Array(actions.enumerated()), id: \.element.id) { index, action in
                NavigationLink {
                    ActionDetailView(action: action)
                } label: {
                    ActionRow(action: action, style: style, onSnooze: onSnooze)
                }
                .buttonStyle(.plain)

                if index < actions.count - 1 {
                    Divider().overlay(Theme.line)
                }
            }
        }
    }
}

private struct ActionRow: View {
    let action: ActionItem
    let style: ActionRowStyle
    let onSnooze: ((ActionItem) -> Void)?

    private var isSellLike: Bool {
        style == .sell || style == .snoozed
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack(spacing: 8) {
                Text(symbolTitle)
                    .font(.system(size: 14, weight: .semibold, design: .monospaced))
                    .foregroundStyle(Theme.textPrimary)
                if style == .sell && action.urgency == "urgent" {
                    MobileSignalPill(text: "Urgent", style: .urgent)
                } else if style == .signalOnly {
                    MobileSignalPill(text: "Signal only", style: .hold)
                } else if style == .snoozed {
                    MobileSignalPill(text: "Snoozed", style: .neutral)
                }
                Spacer()
                if let pnl = action.pnlPct {
                    Text(Formatting.percent(pnl))
                        .font(.system(size: 12, weight: .semibold, design: .monospaced))
                        .foregroundStyle(Formatting.pnlColor(pnl))
                }
            }

            Text(action.detail)
                .font(.system(size: 12))
                .foregroundStyle(style == .signalOnly ? Theme.warning : Theme.textMuted)

            HStack(spacing: 10) {
                if let shares = action.shares {
                    Text("\(Formatting.number(shares, decimals: 2)) sh")
                } else if let shares = action.sellShares {
                    Text("\(Formatting.number(shares, decimals: 2)) sh")
                }
                if let price = action.price {
                    Text("@ \(Formatting.currency(price))")
                } else if let price = action.sellPrice {
                    Text("@ \(Formatting.currency(price))")
                }
                if let amount = action.dollarAmount ?? action.sellAmount {
                    Text(Formatting.currency(amount))
                }
                Spacer()
                if let onSnooze {
                    Button(isSellLike ? "Snooze" : "Unsnooze") {
                        onSnooze(action)
                    }
                    .font(.system(size: 10, weight: .semibold, design: .monospaced))
                    .foregroundStyle(Theme.textDimmed)
                }
            }
            .font(.system(size: 10, weight: .medium, design: .monospaced))
            .foregroundStyle(Theme.textDimmed)
        }
        .padding(16)
    }

    private var symbolTitle: String {
        if action.type == "SWAP" {
            return "\(action.sellSymbol ?? "") → \(action.buySymbol ?? "")"
        }
        return action.symbol ?? ""
    }
}

private struct SignalCardContent: View {
    let signal: SignalOut

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(signal.symbol)
                    .font(.system(size: 14, weight: .semibold, design: .monospaced))
                    .foregroundStyle(Theme.textPrimary)
                Spacer()
                Text("\(signal.score > 0 ? "+" : "")\(String(format: "%.2f", signal.score)) / 9")
                    .font(.system(size: 12, weight: .medium, design: .monospaced))
                    .foregroundStyle(Formatting.pnlColor(signal.score))
                SignalBadgeView(signal: signal.signal, strength: signal.strength)
            }

            if let price = signal.price {
                Text("Price: \(Formatting.currency(price))")
                    .font(.system(size: 11, weight: .medium, design: .monospaced))
                    .foregroundStyle(Theme.textDimmed)
            }
            if let sector = signal.sector {
                Text(sector)
                    .font(.system(size: 11))
                    .foregroundStyle(Theme.textDimmed)
            }
            ScoreMixCard(
                technical: signal.technicalScore,
                sentiment: signal.sentimentScore,
                commodity: signal.commodityScore,
                total: signal.score
            )
        }
    }
}

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
                    ForEach(SnoozeDuration.options) { duration in
                        Button {
                            selectedDuration = duration.id
                            indefinite = false
                        } label: {
                            HStack {
                                Text(duration.label)
                                    .foregroundStyle(Color.primary)
                                Spacer()
                                if !indefinite && selectedDuration == duration.id {
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
