import SwiftUI

/// Trades page matching web's trades/page.tsx — buy/sell form + trade history.
struct TradesView: View {
    @EnvironmentObject private var config: AppConfig

    enum TradeAction: String, CaseIterable {
        case buy = "Buy"
        case sell = "Sell"
    }

    @State private var action: TradeAction = .buy
    @State private var symbol = ""
    @State private var quantity = ""
    @State private var price = ""
    @State private var isSubmitting = false
    @State private var trades: [TradeOut] = []
    @State private var isLoading = true
    @State private var successMessage: String?
    @State private var errorMessage: String?

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    var body: some View {
        NavigationStack {
            List {
                // Trade form
                Section("Record Trade") {
                    Picker("Action", selection: $action) {
                        ForEach(TradeAction.allCases, id: \.self) { a in
                            Text(a.rawValue)
                        }
                    }
                    .pickerStyle(.segmented)

                    TextField("Symbol (e.g. SHOP.TO)", text: $symbol)
                        .textInputAutocapitalization(.characters)
                        .autocorrectionDisabled()

                    TextField("Quantity", text: $quantity)
                        .keyboardType(.decimalPad)

                    TextField("Price per share", text: $price)
                        .keyboardType(.decimalPad)

                    Button {
                        Task { await submitTrade() }
                    } label: {
                        HStack {
                            if isSubmitting {
                                ProgressView()
                                    .tint(.white)
                            }
                            Text(action == .buy ? "Record Buy" : "Record Sell")
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(action == .buy ? Theme.brand : Theme.negative)
                    .disabled(symbol.isEmpty || quantity.isEmpty || price.isEmpty || isSubmitting)

                    if let successMessage {
                        Text(successMessage)
                            .font(.caption)
                            .foregroundStyle(Theme.positive)
                    }
                    if let errorMessage {
                        Text(errorMessage)
                            .font(.caption)
                            .foregroundStyle(Theme.negative)
                    }
                }

                // Trade history
                Section("Recent Trades") {
                    if isLoading && trades.isEmpty {
                        ForEach(0..<5, id: \.self) { _ in
                            TradeRowSkeleton()
                        }
                    } else if trades.isEmpty {
                        Text("No trades recorded")
                            .foregroundStyle(Theme.textDimmed)
                    } else {
                        ForEach(trades) { trade in
                            TradeRow(trade: trade)
                        }
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Trades")
            .refreshable { await loadHistory() }
            .task { await loadHistory() }
        }
    }

    private func submitTrade() async {
        guard let qty = Double(quantity), let px = Double(price) else {
            errorMessage = "Invalid quantity or price"
            return
        }

        isSubmitting = true
        successMessage = nil
        errorMessage = nil
        defer { isSubmitting = false }

        let sym = symbol.trimmingCharacters(in: .whitespaces).uppercased()
        do {
            let trade: TradeOut
            if action == .buy {
                trade = try await client.recordBuy(symbol: sym, quantity: qty, price: px)
            } else {
                trade = try await client.recordSell(symbol: sym, quantity: qty, price: px)
            }
            successMessage = "\(trade.action) \(trade.symbol) x\(Formatting.number(trade.quantity, decimals: 4)) @ \(Formatting.currency(trade.price))"
            symbol = ""
            quantity = ""
            price = ""
            NotificationCenter.default.post(name: .portfolioDidChange, object: nil)
            await loadHistory()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func loadHistory() async {
        isLoading = true
        defer { isLoading = false }
        do {
            trades = try await client.getTradeHistory()
        } catch { /* pull-to-refresh */ }
    }
}

// MARK: - Trade Row

private struct TradeRow: View {
    let trade: TradeOut

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(trade.action)
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundStyle(trade.action == "BUY" ? Theme.brand : Theme.negative)
                    Text(trade.symbol)
                        .fontWeight(.medium)
                }
                Text("\(Formatting.number(trade.quantity, decimals: 4)) @ \(Formatting.currency(trade.price))")
                    .font(.caption)
                    .foregroundStyle(Theme.textDimmed)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text(Formatting.currency(trade.total))
                    .fontWeight(.medium)
                if let pnl = trade.pnl, let pnlPct = trade.pnlPct {
                    Text("\(Formatting.currency(pnl)) (\(Formatting.percent(pnlPct)))")
                        .font(.caption2)
                        .foregroundStyle(Formatting.pnlColor(pnl))
                }
            }
        }
        .padding(.vertical, 2)
    }
}
