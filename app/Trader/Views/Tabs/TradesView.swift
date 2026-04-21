import SwiftUI

/// Signalhouse trades journal tab.
struct TradesView: View {
    @EnvironmentObject private var config: AppConfig

    fileprivate static let isoWithFractional: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()

    fileprivate static let isoWithoutFractional: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime]
        return formatter
    }()

    fileprivate static let csvFilenameFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd-HHmmss"
        return formatter
    }()

    enum TradeAction: String, CaseIterable {
        case buy = "BUY"
        case sell = "SELL"
    }

    private enum TradeField: Hashable {
        case symbol
        case quantity
        case price
    }

    @State private var action: TradeAction = .buy
    @State private var symbol = ""
    @State private var quantity = ""
    @State private var price = ""
    @State private var isSubmitting = false
    @State private var trades: [TradeOut] = []
    @State private var csvExportURL: URL?
    @State private var isLoading = true
    @State private var successMessage: String?
    @State private var errorMessage: String?
    @FocusState private var focusedField: TradeField?

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    var body: some View {
        NavigationStack {
            MobileScreen {
                ScrollView(showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 14) {
                        Text("JOURNAL")
                            .font(.system(size: 10, weight: .medium, design: .monospaced))
                            .tracking(1.4)
                            .foregroundStyle(Theme.brand)

                        MobileSectionLabel("Record Trade")
                        MobileCard {
                            VStack(spacing: 10) {
                                Picker("Action", selection: $action) {
                                    ForEach(TradeAction.allCases, id: \.self) { current in
                                        Text(current.rawValue.capitalized).tag(current)
                                    }
                                }
                                .pickerStyle(.segmented)

                                tradeInput(
                                    "Symbol (e.g. SHOP.TO)",
                                    text: $symbol,
                                    field: .symbol,
                                    keyboard: .asciiCapable,
                                    uppercase: true,
                                    submitLabel: .next
                                )
                                tradeInput(
                                    "Quantity",
                                    text: $quantity,
                                    field: .quantity,
                                    keyboard: .decimalPad,
                                    submitLabel: .next
                                )
                                tradeInput(
                                    "Price per share",
                                    text: $price,
                                    field: .price,
                                    keyboard: .decimalPad,
                                    submitLabel: .done
                                )

                                Button {
                                    Task { await submitTrade() }
                                } label: {
                                    HStack(spacing: 8) {
                                        if isSubmitting {
                                            ProgressView()
                                                .tint(Color.black)
                                        }
                                        Text(action == .buy ? "Record buy" : "Record sell")
                                            .font(.system(size: 14, weight: .semibold))
                                    }
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 14)
                                    .background(action == .buy ? Theme.brand : Theme.negative)
                                    .foregroundStyle(action == .buy ? Color.black : Color.white)
                                    .clipShape(RoundedRectangle(cornerRadius: 10))
                                }
                                .buttonStyle(.plain)
                                .disabled(symbol.isEmpty || quantity.isEmpty || price.isEmpty || isSubmitting)

                                if let successMessage {
                                    Text(successMessage)
                                        .font(.system(size: 11))
                                        .foregroundStyle(Theme.positive)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                }
                                if let errorMessage {
                                    Text(errorMessage)
                                        .font(.system(size: 11))
                                        .foregroundStyle(Theme.negative)
                                        .frame(maxWidth: .infinity, alignment: .leading)
                                }
                            }
                            .padding(14)
                        }

                        HStack {
                            MobileSectionLabel("Recent · 14 days")
                            Spacer()
                            if let csvExportURL {
                                ShareLink(item: csvExportURL) {
                                    Text("Export CSV")
                                        .font(.system(size: 12, weight: .medium))
                                        .foregroundStyle(Theme.brand)
                                }
                            } else {
                                Text("Export CSV")
                                    .font(.system(size: 12, weight: .medium))
                                    .foregroundStyle(Theme.textDimmed)
                            }
                        }

                        MobileCard {
                            if isLoading && trades.isEmpty {
                                ForEach(0..<4, id: \.self) { index in
                                    TradeRowSkeleton()
                                        .padding(.horizontal, 16)
                                        .padding(.vertical, 10)
                                    if index < 3 {
                                        Divider().overlay(Theme.line)
                                    }
                                }
                            } else if trades.isEmpty {
                                Text("No trades recorded")
                                    .font(.system(size: 13))
                                    .foregroundStyle(Theme.textMuted)
                                    .padding(16)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            } else {
                                ForEach(Array(trades.enumerated()), id: \.element.id) { index, trade in
                                    TradeRow(trade: trade)
                                    if index < trades.count - 1 {
                                        Divider().overlay(Theme.line)
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
            .navigationTitle("Trades")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button("Done") {
                        focusedField = nil
                    }
                    .font(AppFont.sans(15, weight: .semibold))
                }
            }
            .refreshable { await loadHistory() }
            .task { await loadHistory() }
        }
    }

    @ViewBuilder
    private func tradeInput(
        _ placeholder: String,
        text: Binding<String>,
        field: TradeField,
        keyboard: UIKeyboardType = .default,
        uppercase: Bool = false,
        submitLabel: SubmitLabel = .done
    ) -> some View {
        TextField(placeholder, text: text)
            .focused($focusedField, equals: field)
            .keyboardType(keyboard)
            .submitLabel(submitLabel)
            .textInputAutocapitalization(uppercase ? .characters : .never)
            .autocorrectionDisabled()
            .font(AppFont.sans(16))
            .foregroundStyle(Theme.textPrimary)
            .textFieldStyle(.roundedBorder)
            .onSubmit {
                advanceFocus(from: field)
            }
    }

    private func advanceFocus(from field: TradeField) {
        switch field {
        case .symbol:
            focusedField = .quantity
        case .quantity:
            focusedField = .price
        case .price:
            focusedField = nil
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

        let cleaned = symbol.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        do {
            let trade: TradeOut
            if action == .buy {
                trade = try await client.recordBuy(symbol: cleaned, quantity: qty, price: px)
            } else {
                trade = try await client.recordSell(symbol: cleaned, quantity: qty, price: px)
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
            let history = try await client.getTradeHistory()
            trades = history.sorted { lhs, rhs in
                let lhsTimestamp = timestamp(for: lhs)
                let rhsTimestamp = timestamp(for: rhs)
                if lhsTimestamp != rhsTimestamp {
                    return lhsTimestamp > rhsTimestamp
                }
                return (lhs.id ?? 0) > (rhs.id ?? 0)
            }
            refreshCSVExport()
        } catch {
            csvExportURL = nil
        }
    }

    private func timestamp(for trade: TradeOut) -> Date {
        guard let raw = trade.timestamp else { return .distantPast }
        if let parsed = Self.isoWithFractional.date(from: raw) { return parsed }
        if let parsed = Self.isoWithoutFractional.date(from: raw) { return parsed }
        return .distantPast
    }

    private func refreshCSVExport() {
        guard !trades.isEmpty else {
            csvExportURL = nil
            return
        }

        let filename = "signalhouse-trades-\(Self.csvFilenameFormatter.string(from: Date())).csv"
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(filename)
        let content = csvContent()

        do {
            try content.write(to: url, atomically: true, encoding: .utf8)
            csvExportURL = url
        } catch {
            csvExportURL = nil
        }
    }

    private func csvContent() -> String {
        let header = "id,timestamp,action,symbol,quantity,price,total,pnl,pnl_pct"
        let rows = trades.map(csvRow(for:))
        return ([header] + rows).joined(separator: "\n")
    }

    private func csvRow(for trade: TradeOut) -> String {
        [
            csvField(trade.id.map(String.init) ?? ""),
            csvField(trade.timestamp ?? ""),
            csvField(trade.action),
            csvField(trade.symbol),
            csvField(String(format: "%.4f", trade.quantity)),
            csvField(String(format: "%.2f", trade.price)),
            csvField(String(format: "%.2f", trade.total)),
            csvField(trade.pnl.map { String(format: "%.2f", $0) } ?? ""),
            csvField(trade.pnlPct.map { String(format: "%.4f", $0) } ?? ""),
        ].joined(separator: ",")
    }

    private func csvField(_ value: String) -> String {
        "\"\(value.replacingOccurrences(of: "\"", with: "\"\""))\""
    }
}

private struct TradeRow: View {
    let trade: TradeOut

    private var sideStyle: MobileSignalStyle {
        trade.action.uppercased() == "BUY" ? .buy : .sell
    }

    private var dateLabel: String {
        guard let raw = trade.timestamp else { return "—" }
        if let date = TradesView.isoWithFractional.date(from: raw) ?? TradesView.isoWithoutFractional.date(from: raw) {
            return date.formatted(date: .abbreviated, time: .omitted)
        }
        return "—"
    }

    var body: some View {
        HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 8) {
                    MobileSignalPill(text: trade.action, style: sideStyle)
                    Text(trade.symbol)
                        .font(.system(size: 13, weight: .semibold, design: .monospaced))
                        .foregroundStyle(Theme.textPrimary)
                }
                Text("\(dateLabel) · \(Formatting.number(trade.quantity, decimals: 4)) @ \(Formatting.currency(trade.price))")
                    .font(.system(size: 11, weight: .regular, design: .monospaced))
                    .foregroundStyle(Theme.textDimmed)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 4) {
                Text(Formatting.currency(trade.total))
                    .font(.system(size: 13, weight: .semibold, design: .monospaced))
                    .foregroundStyle(Theme.textPrimary)
                if let pnl = trade.pnl, let pnlPct = trade.pnlPct {
                    Text("\(Formatting.currency(pnl)) · \(Formatting.percent(pnlPct))")
                        .font(.system(size: 10, weight: .semibold, design: .monospaced))
                        .foregroundStyle(Formatting.pnlColor(pnl))
                }
            }
        }
        .padding(16)
    }
}
