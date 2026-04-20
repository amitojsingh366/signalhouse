import SwiftUI

/// Signal badge matching web's signal-badge.tsx — BUY/SELL/HOLD with strength %.
struct SignalBadgeView: View {
    let signal: String
    let strength: Double?

    var body: some View {
        HStack(spacing: 4) {
            Text(signal.uppercased())
                .font(.system(size: 10, weight: .semibold, design: .monospaced))
                .fontWeight(.semibold)
            if let strength {
                Text("\(Int(strength * 100))%")
                    .font(.system(size: 10, weight: .semibold, design: .monospaced))
                    .opacity(0.75)
            }
        }
        .padding(.horizontal, 9)
        .padding(.vertical, 5)
        .background(badgeBackground)
        .foregroundStyle(badgeForeground)
        .clipShape(RoundedRectangle(cornerRadius: 6))
        .overlay(RoundedRectangle(cornerRadius: 6).stroke(badgeBorder, lineWidth: 1))
    }

    private var badgeBackground: Color {
        switch signal.uppercased() {
        case "BUY": return Theme.brand.opacity(0.15)
        case "SELL": return Theme.negative.opacity(0.15)
        case "HOLD": return Theme.warning.opacity(0.15)
        default: return Color.gray.opacity(0.15)
        }
    }

    private var badgeForeground: Color {
        switch signal.uppercased() {
        case "BUY": return Theme.brandLight
        case "SELL": return Theme.negative
        case "HOLD": return Theme.warning
        default: return Theme.textMuted
        }
    }

    private var badgeBorder: Color {
        switch signal.uppercased() {
        case "BUY": return Theme.brand.opacity(0.25)
        case "SELL": return Theme.negative.opacity(0.25)
        case "HOLD": return Theme.warning.opacity(0.25)
        default: return Color.gray.opacity(0.25)
        }
    }
}
