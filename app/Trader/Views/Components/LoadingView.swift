import SwiftUI

// MARK: - Skeleton fill color

private let skelFill = Color.white.opacity(0.06)

// MARK: - Shimmer Effect

/// Smooth shimmer effect that adapts to the view's width using GeometryReader.
struct ShimmerModifier: ViewModifier {
    @State private var phase: CGFloat = -1

    func body(content: Content) -> some View {
        content
            .overlay(
                GeometryReader { geo in
                    let width = geo.size.width
                    let bandWidth = width * 0.6
                    LinearGradient(
                        stops: [
                            .init(color: .clear, location: 0),
                            .init(color: Color.white.opacity(0.08), location: 0.4),
                            .init(color: Color.white.opacity(0.12), location: 0.5),
                            .init(color: Color.white.opacity(0.08), location: 0.6),
                            .init(color: .clear, location: 1),
                        ],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                    .frame(width: bandWidth)
                    .offset(x: -bandWidth + phase * (width + bandWidth))
                    .onAppear {
                        withAnimation(
                            .easeInOut(duration: 1.4)
                            .repeatForever(autoreverses: false)
                        ) {
                            phase = 1
                        }
                    }
                }
            )
            .clipped()
    }
}

extension View {
    func shimmer() -> some View {
        modifier(ShimmerModifier())
    }
}

// MARK: - Holding Row Skeleton (matches HoldingRow)

/// Skeleton for portfolio holding rows — symbol/shares left, value/pnl right, bottom row with prices + badge.
struct HoldingRowSkeleton: View {
    var body: some View {
        VStack(spacing: 8) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(skelFill)
                        .frame(width: 70, height: 16) // symbol
                    RoundedRectangle(cornerRadius: 4)
                        .fill(skelFill)
                        .frame(width: 90, height: 11) // "X shares"
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 4) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(skelFill)
                        .frame(width: 75, height: 16) // market value
                    RoundedRectangle(cornerRadius: 4)
                        .fill(skelFill)
                        .frame(width: 50, height: 11) // pnl %
                }
            }
            HStack {
                RoundedRectangle(cornerRadius: 4)
                    .fill(skelFill)
                    .frame(width: 65, height: 10) // avg cost
                RoundedRectangle(cornerRadius: 4)
                    .fill(skelFill)
                    .frame(width: 65, height: 10) // current price
                Spacer()
                RoundedRectangle(cornerRadius: 10)
                    .fill(skelFill)
                    .frame(width: 55, height: 20) // signal badge
            }
        }
        .padding(.vertical, 4)
        .shimmer()
    }
}

// MARK: - Signal Card Skeleton (matches SignalCardContent)

/// Skeleton for signal list rows — symbol + score + badge, price, sector, reasons.
struct SignalCardSkeleton: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Header row: symbol, score, badge
            HStack {
                RoundedRectangle(cornerRadius: 4)
                    .fill(skelFill)
                    .frame(width: 80, height: 18) // headline symbol
                Spacer()
                RoundedRectangle(cornerRadius: 4)
                    .fill(skelFill)
                    .frame(width: 40, height: 12) // score
                RoundedRectangle(cornerRadius: 10)
                    .fill(skelFill)
                    .frame(width: 60, height: 22) // signal badge
            }
            // Price
            RoundedRectangle(cornerRadius: 4)
                .fill(skelFill)
                .frame(width: 100, height: 11)
            // Sector
            RoundedRectangle(cornerRadius: 4)
                .fill(skelFill)
                .frame(width: 70, height: 10)
            // 2-3 reason rows
            ForEach(0..<3, id: \.self) { i in
                HStack {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(skelFill)
                        .frame(height: 10)
                    RoundedRectangle(cornerRadius: 4)
                        .fill(skelFill)
                        .frame(width: 30, height: 10)
                }
                .frame(width: [180, 150, 120][i]) // varied widths
            }
        }
        .padding(.vertical, 4)
        .shimmer()
    }
}

// MARK: - Trade Row Skeleton (matches TradeRow)

/// Skeleton for trade history rows — action+symbol left, total+pnl right.
struct TradeRowSkeleton: View {
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 6) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(skelFill)
                        .frame(width: 30, height: 12) // BUY/SELL
                    RoundedRectangle(cornerRadius: 4)
                        .fill(skelFill)
                        .frame(width: 65, height: 14) // symbol
                }
                RoundedRectangle(cornerRadius: 4)
                    .fill(skelFill)
                    .frame(width: 110, height: 11) // qty @ price
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 4) {
                RoundedRectangle(cornerRadius: 4)
                    .fill(skelFill)
                    .frame(width: 65, height: 14) // total
                RoundedRectangle(cornerRadius: 4)
                    .fill(skelFill)
                    .frame(width: 80, height: 10) // pnl
            }
        }
        .padding(.vertical, 2)
        .shimmer()
    }
}

// MARK: - Premarket Mover Skeleton (matches PremarketMoverRow)

/// Skeleton for premarket mover rows — circle + symbol/price left, percent badge right.
struct PremarketMoverSkeleton: View {
    var body: some View {
        HStack(spacing: 12) {
            Circle()
                .fill(skelFill)
                .frame(width: 10, height: 10)
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 6) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(skelFill)
                        .frame(width: 75, height: 16) // CDR symbol
                    RoundedRectangle(cornerRadius: 4)
                        .fill(skelFill)
                        .frame(width: 50, height: 11) // (US symbol)
                }
                RoundedRectangle(cornerRadius: 4)
                    .fill(skelFill)
                    .frame(width: 110, height: 11) // "Premarket: $XX.XX"
            }
            Spacer()
            RoundedRectangle(cornerRadius: 10)
                .fill(skelFill)
                .frame(width: 60, height: 26) // percent capsule
        }
        .padding(.vertical, 4)
        .shimmer()
    }
}

// MARK: - Status Row Skeleton (matches LabeledContent rows)

/// Skeleton for status page LabeledContent rows.
struct StatusRowSkeleton: View {
    var body: some View {
        HStack {
            RoundedRectangle(cornerRadius: 4)
                .fill(skelFill)
                .frame(width: 100, height: 14)
            Spacer()
            RoundedRectangle(cornerRadius: 4)
                .fill(skelFill)
                .frame(width: 60, height: 14)
        }
        .shimmer()
    }
}

// MARK: - Dashboard Signal Skeleton (matches dashboard signal cards)

/// Skeleton for dashboard signal preview cards — icon/symbol left, badge right.
struct DashboardSignalSkeleton: View {
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                RoundedRectangle(cornerRadius: 4)
                    .fill(skelFill)
                    .frame(width: 70, height: 14) // symbol
                RoundedRectangle(cornerRadius: 4)
                    .fill(skelFill)
                    .frame(width: 100, height: 10) // sector
            }
            Spacer()
            RoundedRectangle(cornerRadius: 4)
                .fill(skelFill)
                .frame(width: 50, height: 12) // price
            RoundedRectangle(cornerRadius: 10)
                .fill(skelFill)
                .frame(width: 60, height: 22) // signal badge
        }
        .padding(12)
        .glassCard()
    }
}

// MARK: - Generic List Loading (legacy compat)

/// Generic loading placeholder for list content.
struct ListLoadingView: View {
    let rows: Int

    var body: some View {
        ForEach(0..<rows, id: \.self) { _ in
            HStack {
                RoundedRectangle(cornerRadius: 4)
                    .fill(skelFill)
                    .frame(width: 60, height: 14)
                Spacer()
                RoundedRectangle(cornerRadius: 4)
                    .fill(skelFill)
                    .frame(width: 80, height: 14)
            }
            .padding(.vertical, 4)
            .shimmer()
        }
    }
}
