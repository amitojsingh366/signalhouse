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

struct MobileTabBar: View {
    @Binding var selectedTab: AppTab

    var body: some View {
        HStack(spacing: 2) {
            ForEach(AppTab.allCases, id: \.rawValue) { tab in
                Button {
                    selectedTab = tab
                } label: {
                    VStack(spacing: 4) {
                        Image(systemName: tab.icon)
                            .font(.system(size: 14, weight: .semibold))
                        Text(tab.title)
                            .font(.system(size: 10, weight: .medium))
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                    .foregroundStyle(selectedTab == tab ? Theme.brand : Theme.textDimmed)
                    .background(
                        Capsule()
                            .fill(selectedTab == tab ? Theme.brand.opacity(0.14) : .clear)
                    )
                }
                .buttonStyle(.plain)
            }
        }
        .padding(8)
        .background(.ultraThinMaterial)
        .background(Theme.surface1.opacity(0.88))
        .clipShape(Capsule())
        .overlay(
            Capsule()
                .stroke(Theme.lineStrong, lineWidth: 1)
        )
        .padding(.horizontal, 20)
        .padding(.bottom, 10)
    }
}

struct MobileKickerTitle: View {
    let kicker: String
    let title: String
    var subtitle: String? = nil
    var kickerColor: Color = Theme.brand

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Circle()
                    .fill(kickerColor)
                    .frame(width: 6, height: 6)
                Text(kicker.uppercased())
                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                    .tracking(1.4)
                    .foregroundStyle(kickerColor)
            }

            Text(title)
                .font(.system(size: 40, weight: .bold))
                .tracking(-1)
                .foregroundStyle(Theme.textPrimary)

            if let subtitle {
                Text(subtitle)
                    .font(.system(size: 13))
                    .foregroundStyle(Theme.textMuted)
            }
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
                .font(.system(size: 10, weight: .semibold, design: .monospaced))
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

    var body: some View {
        HStack(spacing: 10) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 14, weight: .medium))
                .foregroundStyle(Theme.textDimmed)
            TextField(placeholder, text: $text)
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
        .font(.system(size: 14))
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(Theme.surface1)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Theme.line, lineWidth: 1)
        )
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
            .font(.system(size: 10, weight: .semibold, design: .monospaced))
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
                .font(.system(size: 14))
                .foregroundStyle(Theme.textPrimary)
            Spacer()
            value
                .font(.system(size: 14, weight: .medium, design: .monospaced))
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
            .font(.system(size: 14, weight: .medium, design: .monospaced))
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
    let id = UUID()
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

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 22) {
                ForEach(quotes) { quote in
                    HStack(spacing: 7) {
                        Text(quote.symbol)
                            .font(.system(size: 12, weight: .medium, design: .monospaced))
                            .foregroundStyle(Theme.textPrimary)
                        Text(quote.displayPrice)
                            .font(.system(size: 12, weight: .medium, design: .monospaced))
                            .foregroundStyle(Theme.textMuted)
                        Text(quote.change)
                            .font(.system(size: 11, weight: .semibold, design: .monospaced))
                            .foregroundStyle(quote.isPositive ? Theme.positive : Theme.negative)
                    }
                }
            }
            .padding(.horizontal, 4)
        }
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
    }
}
