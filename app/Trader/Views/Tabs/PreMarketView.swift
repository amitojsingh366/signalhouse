import SwiftUI
import Combine

/// Pre-market page (from More).
struct PreMarketView: View {
    @EnvironmentObject private var config: AppConfig

    @State private var movers: [PremarketMover] = []
    @State private var tickerQuotes: [TickerQuote] = []
    @State private var sortMode: PremarketSortMode = .magnitude
    @State private var isLoading = true
    @State private var now = Date()

    private let marketClock = Timer.publish(every: 30, on: .main, in: .common).autoconnect()

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    private var sortedMovers: [PremarketMover] {
        switch sortMode {
        case .magnitude:
            return movers.sorted { abs($0.changePct) > abs($1.changePct) }
        case .gainers:
            return movers.sorted { $0.changePct > $1.changePct }
        case .losers:
            return movers.sorted { $0.changePct < $1.changePct }
        case .symbol:
            return movers.sorted { $0.cdrSymbol < $1.cdrSymbol }
        }
    }

    var body: some View {
        MobileScreen {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 14) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(marketStatusLabel)
                            .font(.system(size: 10, weight: .medium, design: .monospaced))
                            .tracking(1.4)
                            .foregroundStyle(marketStatusColor)
                        Text("CDR counterparts trading now on US markets — use this as a preview of TSX open.")
                            .font(.system(size: 13))
                            .foregroundStyle(Theme.textMuted)
                    }

                    TickerStrip(quotes: tickerQuotes)

                    HStack {
                        MobileSectionLabel("CDR moves · \(sortedMovers.count)")
                        Spacer()
                        Menu {
                            ForEach(PremarketSortMode.allCases) { mode in
                                Button {
                                    sortMode = mode
                                } label: {
                                    if mode == sortMode {
                                        Label(mode.title, systemImage: "checkmark")
                                    } else {
                                        Text(mode.title)
                                    }
                                }
                            }
                        } label: {
                            Label(sortMode.title, systemImage: "arrow.up.arrow.down")
                                .font(.system(size: 12, weight: .medium))
                                .foregroundStyle(Theme.brand)
                        }
                    }

                    MobileCard {
                        if isLoading && sortedMovers.isEmpty {
                            ForEach(0..<6, id: \.self) { index in
                                PremarketMoverSkeleton()
                                    .padding(.horizontal, 16)
                                    .padding(.vertical, 10)
                                if index < 5 {
                                    Divider().overlay(Theme.line)
                                }
                            }
                        } else if sortedMovers.isEmpty {
                            Text("No pre-market data available")
                                .font(.system(size: 13))
                                .foregroundStyle(Theme.textMuted)
                                .padding(16)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        } else {
                            ForEach(Array(sortedMovers.enumerated()), id: \.element.id) { index, mover in
                                PreMarketRow(mover: mover)
                                if index < sortedMovers.count - 1 {
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
        .onReceive(marketClock) { now = $0 }
    }

    private func loadData() async {
        isLoading = true
        defer { isLoading = false }

        async let moversTask = client.getPremarketMovers()
        async let tickerStripTask = client.getTickerStrip()

        do {
            let response = try await moversTask
            movers = response.movers
        } catch {}

        do {
            let items = try await tickerStripTask
            tickerQuotes = items.map(TickerQuote.init(item:))
        } catch {
            tickerQuotes = []
        }
    }

    private var marketStatusLabel: String {
        let interval = marketSession(for: now)
        switch interval {
        case .beforeOpen(let open):
            return "OPENS IN \(countdown(to: open)) · 09:30 ET"
        case .open:
            return "MARKET OPEN · CLOSES 16:00 ET"
        case .afterClose(let nextOpen):
            return "NEXT OPEN IN \(countdown(to: nextOpen)) · 09:30 ET"
        }
    }

    private var marketStatusColor: Color {
        switch marketSession(for: now) {
        case .beforeOpen:
            return Theme.brand
        case .open:
            return Theme.positive
        case .afterClose:
            return Theme.warning
        }
    }

    private enum MarketSession {
        case beforeOpen(Date)
        case open
        case afterClose(Date)
    }

    private func marketSession(for date: Date) -> MarketSession {
        let calendar = marketCalendar
        let dayStart = calendar.startOfDay(for: date)
        let weekday = calendar.component(.weekday, from: dayStart)

        if isWeekend(weekday) {
            return .afterClose(nextMarketOpen(after: date))
        }

        guard
            let open = calendar.date(bySettingHour: 9, minute: 30, second: 0, of: dayStart),
            let close = calendar.date(bySettingHour: 16, minute: 0, second: 0, of: dayStart)
        else {
            return .afterClose(nextMarketOpen(after: date))
        }

        if date < open {
            return .beforeOpen(open)
        }
        if date < close {
            return .open
        }
        return .afterClose(nextMarketOpen(after: date))
    }

    private func nextMarketOpen(after date: Date) -> Date {
        let calendar = marketCalendar
        let start = calendar.startOfDay(for: date)
        for offset in 1...8 {
            guard let candidateDay = calendar.date(byAdding: .day, value: offset, to: start) else { continue }
            let weekday = calendar.component(.weekday, from: candidateDay)
            if isWeekend(weekday) { continue }
            if let open = calendar.date(bySettingHour: 9, minute: 30, second: 0, of: candidateDay) {
                return open
            }
        }
        return date
    }

    private func countdown(to target: Date) -> String {
        let totalSeconds = max(0, Int(target.timeIntervalSince(now)))
        let hours = totalSeconds / 3600
        let minutes = (totalSeconds % 3600) / 60
        if hours > 0 {
            return "\(hours)H \(minutes)M"
        }
        return "\(minutes)M"
    }

    private var marketCalendar: Calendar {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "America/New_York") ?? .current
        return calendar
    }

    private func isWeekend(_ weekday: Int) -> Bool {
        weekday == 1 || weekday == 7
    }
}

private enum PremarketSortMode: String, CaseIterable, Identifiable {
    case magnitude
    case gainers
    case losers
    case symbol

    var id: Self { self }

    var title: String {
        switch self {
        case .magnitude: return "By Move"
        case .gainers: return "Top Gainers"
        case .losers: return "Top Losers"
        case .symbol: return "Symbol"
        }
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
