import SwiftUI

/// Stat card matching web's stat-card.tsx — used on the dashboard.
struct StatCardView: View {
    let title: String
    let value: String
    let change: Double?
    let changeLabel: String?
    let icon: String

    init(
        title: String,
        value: String,
        change: Double? = nil,
        changeLabel: String? = nil,
        icon: String = "dollarsign"
    ) {
        self.title = title
        self.value = value
        self.change = change
        self.changeLabel = changeLabel
        self.icon = icon
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(title)
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)
                Spacer()
                Image(systemName: icon)
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)
            }

            Text(value)
                .font(.title2)
                .fontWeight(.semibold)

            if let change {
                HStack(spacing: 4) {
                    Text(Formatting.percent(change))
                        .font(.caption)
                        .foregroundStyle(Formatting.pnlColor(change))
                    if let changeLabel {
                        Text(changeLabel)
                            .font(.caption2)
                            .foregroundStyle(Theme.textDimmed)
                    }
                }
            }
        }
        .padding()
        .glassCard()
    }
}
