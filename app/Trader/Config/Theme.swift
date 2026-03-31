import SwiftUI

/// Design system colors and modifiers matching the web dashboard.
enum Theme {
    // Brand
    static let brand = Color(hex: "#8b5cf6")
    static let brandLight = Color(hex: "#a78bfa")

    // Semantic
    static let positive = Color(hex: "#34d399")  // emerald-400
    static let negative = Color(hex: "#f87171")  // red-400
    static let warning = Color(hex: "#fbbf24")   // amber-400

    // Surfaces
    static let background = Color(hex: "#09090b")
    static let cardBg = Color.white.opacity(0.03)
    static let cardBorder = Color.white.opacity(0.06)

    // Text
    static let textPrimary = Color(hex: "#fafafa")
    static let textMuted = Color(hex: "#94a3b8")   // slate-400
    static let textDimmed = Color(hex: "#64748b")   // slate-500
}

// MARK: - Glass Card Modifier

struct GlassCard: ViewModifier {
    func body(content: Content) -> some View {
        content
            .background(Color.white.opacity(0.03))
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.white.opacity(0.06), lineWidth: 1)
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
