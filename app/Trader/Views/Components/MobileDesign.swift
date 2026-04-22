import SwiftUI

enum AppTab: Int, CaseIterable {
    case dashboard
    case portfolio
    case actions
    case trades
    case more

    var title: String {
        switch self {
        case .dashboard: return "Dashboard"
        case .portfolio: return "Portfolio"
        case .actions: return "Actions"
        case .trades: return "Trades"
        case .more: return "More"
        }
    }

    var icon: String {
        switch self {
        case .dashboard: return "house"
        case .portfolio: return "briefcase"
        case .actions: return "bolt"
        case .trades: return "arrow.left.arrow.right"
        case .more: return "ellipsis"
        }
    }
}

struct MobileSectionLabel<Trailing: View>: View {
    let title: String
    @ViewBuilder var trailing: Trailing

    init(_ title: String, @ViewBuilder trailing: () -> Trailing = { EmptyView() }) {
        self.title = title
        self.trailing = trailing()
    }

    var body: some View {
        HStack {
            Text(title.uppercased())
                .font(AppFont.mono(10, weight: .semibold))
                .tracking(1.4)
                .foregroundStyle(Theme.textDimmed)
            Spacer()
            trailing
        }
    }
}

struct MobileSearchField: View {
    let placeholder: String
    @Binding var text: String
    @FocusState private var isFocused: Bool

    var body: some View {
        HStack(spacing: 8) {
            HStack(spacing: 10) {
                Image(systemName: "magnifyingglass")
                    .font(AppFont.sans(14, weight: .medium))
                    .foregroundStyle(Theme.textDimmed)
                TextField(placeholder, text: $text)
                    .focused($isFocused)
                    .submitLabel(.search)
                    .textInputAutocapitalization(.characters)
                    .autocorrectionDisabled()
                    .foregroundStyle(Theme.textPrimary)
                if !text.isEmpty {
                    Button {
                        text = ""
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(Theme.textDimmed)
                    }
                    .buttonStyle(.plain)
                }
            }
            .font(AppFont.sans(15))
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(Theme.surface1)
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Theme.line, lineWidth: 1)
            )

            if isFocused || !text.isEmpty {
                Button {
                    text = ""
                    isFocused = false
                } label: {
                    Text("Cancel")
                        .font(AppFont.sans(14, weight: .medium))
                        .foregroundStyle(Theme.brand)
                }
                .buttonStyle(.plain)
            }
        }
        .animation(.easeInOut(duration: 0.16), value: isFocused || !text.isEmpty)
    }
}

enum MobileSignalStyle {
    case buy
    case sell
    case hold
    case urgent
    case neutral
}

struct MobileSignalPill: View {
    let text: String
    var style: MobileSignalStyle

    var body: some View {
        Text(text.uppercased())
            .font(AppFont.mono(11, weight: .semibold))
            .tracking(1)
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .background(background)
            .foregroundStyle(foreground)
            .clipShape(RoundedRectangle(cornerRadius: 6))
    }

    private var foreground: Color {
        switch style {
        case .buy: return Theme.brand
        case .sell, .urgent: return Theme.negative
        case .hold: return Theme.warning
        case .neutral: return Theme.textMuted
        }
    }

    private var background: Color {
        switch style {
        case .buy: return Theme.brand.opacity(0.14)
        case .sell: return Theme.negative.opacity(0.12)
        case .hold: return Theme.warning.opacity(0.12)
        case .urgent: return Theme.negative.opacity(0.16)
        case .neutral: return Theme.textDimmed.opacity(0.2)
        }
    }
}

struct MobileCard<Content: View>: View {
    let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        VStack(spacing: 0) {
            content
        }
        .background(Theme.surface1)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Theme.line, lineWidth: 1)
        )
    }
}

struct MobileDefRow<Value: View>: View {
    let label: String
    @ViewBuilder var value: Value

    var body: some View {
        HStack(spacing: 12) {
            Text(label)
                .font(AppFont.sans(15))
                .foregroundStyle(Theme.textPrimary)
            Spacer()
            value
                .font(AppFont.mono(15, weight: .medium))
                .foregroundStyle(Theme.textMuted)
                .multilineTextAlignment(.trailing)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }
}

struct MobileValueLabel: View {
    let text: String
    var color: Color = Theme.textMuted

    var body: some View {
        Text(text)
            .font(AppFont.mono(15, weight: .medium))
            .foregroundStyle(color)
    }
}

struct MobileScreen<Content: View>: View {
    let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            content
        }
    }
}

struct TickerQuote: Identifiable {
    var id: String { "\(symbol)-\(displayPrice)-\(change)" }
    let symbol: String
    let displayPrice: String
    let change: String
    let isPositive: Bool
}

extension TickerQuote {
    init(item: TickerStripItem) {
        let resolvedChange: String
        if let changeLabel = item.changeLabel, !changeLabel.isEmpty {
            resolvedChange = changeLabel
        } else if let changePct = item.changePct {
            resolvedChange = String(format: "%+.2f%%", changePct)
        } else {
            resolvedChange = "--"
        }

        let positive: Bool
        if let changePct = item.changePct {
            positive = changePct >= 0
        } else {
            positive = !resolvedChange.trimmingCharacters(in: .whitespaces).hasPrefix("-")
        }

        self.init(
            symbol: item.label,
            displayPrice: item.displayPrice,
            change: resolvedChange,
            isPositive: positive
        )
    }
}

struct TickerStrip: View {
    let quotes: [TickerQuote]
    @State private var singleTrackWidth: CGFloat = 1
    @State private var startTime = Date()

    private let itemSpacing: CGFloat = 18
    private let trackSpacing: CGFloat = 26
    private let speed: CGFloat = 34

    var body: some View {
        GeometryReader { proxy in
            let containerWidth = max(proxy.size.width, 1)
            ZStack {
                if quotes.isEmpty {
                    EmptyView()
                } else {
                    TimelineView(.animation(minimumInterval: 1.0 / 30.0)) { context in
                        let cycleWidth = max(singleTrackWidth + trackSpacing, 1)
                        let elapsed = CGFloat(context.date.timeIntervalSince(startTime))
                        let progress = elapsed * speed
                        let offset = -progress.truncatingRemainder(dividingBy: cycleWidth)

                        HStack(spacing: trackSpacing) {
                            tickerTrack
                                .fixedSize(horizontal: true, vertical: false)
                            tickerTrack
                                .fixedSize(horizontal: true, vertical: false)
                        }
                        .offset(x: offset)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .frame(width: containerWidth, alignment: .leading)
                    .mask(
                        LinearGradient(
                            stops: [
                                .init(color: .clear, location: 0),
                                .init(color: .black, location: 0.06),
                                .init(color: .black, location: 0.94),
                                .init(color: .clear, location: 1)
                            ],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .onPreferenceChange(TickerTrackWidthKey.self) { singleTrackWidth = max($0, 1) }
                    .onAppear { startTime = Date() }
                }
            }
            .frame(width: containerWidth, height: 18, alignment: .leading)
        }
        .frame(height: 18)
        .padding(.vertical, 10)
        .background(Theme.surface0)
        .overlay(
            Rectangle()
                .fill(Theme.line)
                .frame(height: 1),
            alignment: .top
        )
        .overlay(
            Rectangle()
                .fill(Theme.line)
                .frame(height: 1),
            alignment: .bottom
        )
        .clipped()
    }

    private var tickerTrack: some View {
        HStack(spacing: itemSpacing) {
            ForEach(Array(quotes.enumerated()), id: \.offset) { index, quote in
                HStack(spacing: 7) {
                    Text(quote.symbol)
                        .font(AppFont.mono(12, weight: .medium))
                        .foregroundStyle(Theme.textPrimary)
                    Text(quote.displayPrice)
                        .font(AppFont.mono(12, weight: .medium))
                        .foregroundStyle(Theme.textMuted)
                    Text(quote.change)
                        .font(AppFont.mono(12, weight: .semibold))
                        .foregroundStyle(quote.isPositive ? Theme.positive : Theme.negative)
                }
                if index < quotes.count - 1 {
                    Rectangle()
                        .fill(Theme.line)
                        .frame(width: 1, height: 12)
                }
            }
        }
        .background(
            GeometryReader { proxy in
                Color.clear.preference(key: TickerTrackWidthKey.self, value: proxy.size.width)
            }
        )
    }
}

private struct TickerTrackWidthKey: PreferenceKey {
    static var defaultValue: CGFloat = 1

    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
        value = max(value, nextValue())
    }
}
