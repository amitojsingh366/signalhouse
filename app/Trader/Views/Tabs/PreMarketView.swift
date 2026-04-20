import SwiftUI

/// Pre-market page (from More).
struct PreMarketView: View {
    @EnvironmentObject private var config: AppConfig

    @State private var movers: [PremarketMover] = []
    @State private var isLoading = true

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    private var tickerQuotes: [TickerQuote] {
        [
            .init(symbol: "SU.TO", price: "49.30", change: "-1.42%", isPositive: false),
            .init(symbol: "CP.TO", price: "110.76", change: "+0.44%", isPositive: true),
            .init(symbol: "MNT.TO", price: "67.01", change: "-11.56%", isPositive: false),
            .init(symbol: "IBIT.NE", price: "31.33", change: "+11.14%", isPositive: true),
        ]
    }

    var body: some View {
        MobileScreen {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 14) {
                    MobileKickerTitle(
                        kicker: "Opens in 47m · 09:30 ET",
                        title: "Pre-market",
                        subtitle: "CDR counterparts trading now on US markets — use this as a preview of TSX open."
                    )

                    TickerStrip(quotes: tickerQuotes)

                    HStack {
                        MobileSectionLabel("CDR moves · \(movers.count)")
                        Spacer()
                        Text("Sort")
                            .font(.system(size: 12, weight: .medium))
                            .foregroundStyle(Theme.brand)
                    }

                    MobileCard {
                        if isLoading && movers.isEmpty {
                            ForEach(0..<6, id: \.self) { index in
                                PremarketMoverSkeleton()
                                    .padding(.horizontal, 16)
                                    .padding(.vertical, 10)
                                if index < 5 {
                                    Divider().overlay(Theme.line)
                                }
                            }
                        } else if movers.isEmpty {
                            Text("No pre-market data available")
                                .font(.system(size: 13))
                                .foregroundStyle(Theme.textMuted)
                                .padding(16)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        } else {
                            ForEach(Array(movers.enumerated()), id: \.element.id) { index, mover in
                                PreMarketRow(mover: mover)
                                if index < movers.count - 1 {
                                    Divider().overlay(Theme.line)
                                }
                            }
                        }
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 10)
                .padding(.bottom, 40)
            }
        }
        .navigationTitle("Pre-market")
        .navigationBarTitleDisplayMode(.inline)
        .refreshable { await loadData() }
        .task { await loadData() }
    }

    private func loadData() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let response = try await client.getPremarketMovers()
            movers = response.movers.sorted { abs($0.changePct) > abs($1.changePct) }
        } catch {}
    }
}

private struct PreMarketRow: View {
    let mover: PremarketMover

    var body: some View {
        HStack(spacing: 12) {
            Circle()
                .fill(mover.changePct >= 0 ? Theme.positive : Theme.negative)
                .frame(width: 8, height: 8)

            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 6) {
                    Text(mover.cdrSymbol)
                        .font(.system(size: 13, weight: .semibold, design: .monospaced))
                        .foregroundStyle(Theme.textPrimary)
                    Text("(\(mover.usSymbol))")
                        .font(.system(size: 11, weight: .medium, design: .monospaced))
                        .foregroundStyle(Theme.textDimmed)
                }
                Text("Premarket \(Formatting.currency(mover.premarketPrice))")
                    .font(.system(size: 11, weight: .regular, design: .monospaced))
                    .foregroundStyle(Theme.textDimmed)
            }

            Spacer()

            Text(String(format: "%+.1f%%", mover.changePct * 100))
                .font(.system(size: 11, weight: .semibold, design: .monospaced))
                .foregroundStyle(mover.changePct >= 0 ? Theme.positive : Theme.negative)
                .padding(.horizontal, 9)
                .padding(.vertical, 5)
                .background((mover.changePct >= 0 ? Theme.positive : Theme.negative).opacity(0.1))
                .clipShape(RoundedRectangle(cornerRadius: 6))
        }
        .padding(16)
    }
}
