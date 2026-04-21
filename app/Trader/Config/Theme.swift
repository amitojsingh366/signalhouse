import SwiftUI

/// Signalhouse mobile design tokens ported from the handoff bundle.
enum Theme {
    // Brand
    static let brand = Color(hex: "#a78bfa")
    static let brandStrong = Color(hex: "#8b5cf6")
    static let brandDim = Color(hex: "#6b4edc")
    static let brandLight = Color(hex: "#c4b5fd")

    // Semantic
    static let positive = Color(hex: "#34d399")
    static let negative = Color(hex: "#f87171")
    static let warning = Color(hex: "#fbbf24")

    // Surfaces
    static let background = Color(hex: "#07070a")
    static let surface0 = Color(hex: "#0b0b10")
    static let surface1 = Color(hex: "#12121a")
    static let surface2 = Color(hex: "#1a1a24")
    static let line = Color.white.opacity(0.06)
    static let lineStrong = Color.white.opacity(0.09)
    static let cardBg = surface1
    static let cardBorder = line

    // Text
    static let textPrimary = Color(hex: "#f3f3f6")
    static let textMuted = Color(hex: "#9898a8")
    static let textDimmed = Color(hex: "#5a5a6a")

}

// MARK: - Glass Card Modifier

struct GlassCard: ViewModifier {
    func body(content: Content) -> some View {
        content
            .background(Theme.cardBg)
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(Theme.cardBorder, lineWidth: 1)
            )
    }
}

extension View {
    func glassCard() -> some View {
        modifier(GlassCard())
    }
}

// MARK: - Color hex init

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet(charactersIn: "#"))
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let r = Double((int >> 16) & 0xFF) / 255.0
        let g = Double((int >> 8) & 0xFF) / 255.0
        let b = Double(int & 0xFF) / 255.0
        self.init(red: r, green: g, blue: b)
    }
}
