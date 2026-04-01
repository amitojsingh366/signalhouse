import SwiftUI

/// Signals page matching web's signals/page.tsx — recommendations + symbol search.
struct SignalsView: View {
    @EnvironmentObject private var config: AppConfig

    @State private var recommendations: RecommendationOut?
    @State private var isLoading = true
    @State private var searchText = ""
    @State private var checkedSignal: SignalOut?
    @State private var isChecking = false
    @State private var expandedSymbol: String?
    @State private var allSymbols: [SymbolInfo] = []

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    /// Symbols filtered by search text for suggestions
    private var searchSuggestions: [SymbolInfo] {
        let query = searchText.trimmingCharacters(in: .whitespaces)
        guard query.count >= 1 else { return [] }
        let upper = query.uppercased()
        return allSymbols.filter {
            $0.symbol.uppercased().contains(upper) || $0.name.uppercased().contains(upper)
        }.prefix(8).map { $0 }
    }

    var body: some View {
        NavigationStack {
            List {
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

                // Exit alerts
                if let alerts = recommendations?.exitAlerts, !alerts.isEmpty {
                    Section("Exit Alerts") {
                        ForEach(alerts) { alert in
                            ExitAlertRow(alert: alert)
                        }
                    }
                }

                // Buys
                if let buys = recommendations?.buys, !buys.isEmpty {
                    Section("Buy Signals") {
                        ForEach(buys) { sig in
                            NavigationLink {
                                SignalDetailView(signal: sig)
                            } label: {
                                SignalCardContent(signal: sig)
                            }
                        }
                    }
                }

                // Sells
                if let sells = recommendations?.sells, !sells.isEmpty {
                    Section("Sell Signals") {
                        ForEach(sells) { sig in
                            NavigationLink {
                                SignalDetailView(signal: sig)
                            } label: {
                                SignalCardContent(signal: sig)
                            }
                        }
                    }
                }

                // Watchlist
                if let watchlist = recommendations?.watchlistSells, !watchlist.isEmpty {
                    Section("Watchlist Alerts") {
                        ForEach(watchlist) { sig in
                            NavigationLink {
                                SignalDetailView(signal: sig)
                            } label: {
                                SignalCardContent(signal: sig)
                            }
                        }
                    }
                }

                if isLoading && recommendations == nil {
                    Section {
                        ListLoadingView(rows: 5)
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Signals")
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

        async let recs = client.getRecommendations()
        async let syms = client.getSymbols()

        do {
            recommendations = try await recs
        } catch { /* pull-to-refresh retries */ }

        do {
            allSymbols = try await syms
        } catch { /* symbols are optional, suggestions just won't show */ }
    }
}

// MARK: - Signal Card Content

private struct SignalCardContent: View {
    let signal: SignalOut

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(signal.symbol)
                    .font(.headline)
                Spacer()
                if signal.score != 0 {
                    Text("\(signal.score > 0 ? "+" : "")\(String(format: "%.1f", signal.score))/8")
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

// MARK: - Exit Alert Row

private struct ExitAlertRow: View {
    let alert: ExitAlert

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "exclamationmark.triangle")
                    .foregroundStyle(alert.severity == "high" ? Theme.negative : Theme.warning)
                Text(alert.symbol)
                    .fontWeight(.medium)
                Spacer()
                Text(alert.reason)
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(
                        (alert.severity == "high" ? Theme.negative : Theme.warning).opacity(0.2)
                    )
                    .clipShape(Capsule())
                    .foregroundStyle(alert.severity == "high" ? Theme.negative : Theme.warning)
            }
            Text(alert.detail)
                .font(.caption)
                .foregroundStyle(Theme.textMuted)
            HStack(spacing: 16) {
                Text("Entry: \(Formatting.currency(alert.entryPrice))")
                Text("Current: \(Formatting.currency(alert.currentPrice))")
                Text(Formatting.percent(alert.pnlPct))
                    .foregroundStyle(Formatting.pnlColor(alert.pnlPct))
            }
            .font(.caption2)
            .foregroundStyle(Theme.textDimmed)
        }
        .padding(.vertical, 4)
    }
}
