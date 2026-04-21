import SwiftUI

private struct ParsedScoreReason {
    let label: String
    let rawScore: String
    let value: Double
}

private func parseScoreReason(_ text: String) -> ParsedScoreReason? {
    guard let match = text.range(of: #"\[([+-][\d.]+)\]$"#, options: .regularExpression) else {
        return nil
    }
    let label = String(text[text.startIndex..<match.lowerBound]).trimmingCharacters(in: .whitespaces)
    let score = String(text[match])
        .replacingOccurrences(of: "[", with: "")
        .replacingOccurrences(of: "]", with: "")
    let value = Double(score) ?? 0
    return ParsedScoreReason(label: label, rawScore: score, value: value)
}

func scoreReasonDotColor(_ text: String) -> Color {
    guard let parsed = parseScoreReason(text) else {
        return Theme.textDimmed
    }
    return Formatting.pnlColor(parsed.value)
}

func scoreStyle(for total: Double) -> MobileSignalStyle {
    if total >= 3 { return .buy }
    if total <= -3 { return .sell }
    return .hold
}

func scoreLabel(for total: Double) -> String {
    switch scoreStyle(for: total) {
    case .buy:
        return "BUY"
    case .sell:
        return "SELL"
    default:
        return "HOLD"
    }
}

private func signedScore(_ value: Double, decimals: Int = 2) -> String {
    "\(value >= 0 ? "+" : "")\(String(format: "%.\(decimals)f", value))"
}

struct ScoreReasonRow: View {
    let text: String

    var body: some View {
        if let parsed = parseScoreReason(text) {
            HStack {
                Text(parsed.label)
                    .font(AppFont.sans(13))
                    .foregroundStyle(Theme.textMuted)
                Spacer()
                Text(parsed.rawScore)
                    .font(AppFont.mono(12, weight: .semibold))
                    .foregroundStyle(Formatting.pnlColor(parsed.value))
            }
        } else {
            Text(text)
                .font(AppFont.sans(13))
                .foregroundStyle(Theme.textMuted)
        }
    }
}

struct ScoreMixCard: View {
    let technical: Double
    let sentiment: Double
    let commodity: Double
    let total: Double?

    init(
        technical: Double,
        sentiment: Double,
        commodity: Double,
        total: Double? = nil
    ) {
        self.technical = technical
        self.sentiment = sentiment
        self.commodity = commodity
        self.total = total
    }

    private var resolvedTotal: Double {
        total ?? (technical + sentiment + commodity)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Score Mix")
                .font(AppFont.mono(10, weight: .medium))
                .foregroundStyle(Theme.textDimmed)
                .textCase(.uppercase)
            scoreRow(label: "Total", value: resolvedTotal, showScale: true)
            scoreRow(label: "Technical", value: technical)
            scoreRow(label: "Sentiment", value: sentiment)
            scoreRow(label: "Commodity", value: commodity)
        }
        .padding(10)
        .background(Theme.cardBg)
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(Theme.cardBorder, lineWidth: 1)
        )
    }

    @ViewBuilder
    private func scoreRow(label: String, value: Double, showScale: Bool = false) -> some View {
        HStack {
            Text(label)
                .font(AppFont.sans(13))
                .foregroundStyle(label == "Total" ? Theme.textPrimary : Theme.textMuted)
            Spacer()
            Text("\(signedScore(value))\(showScale ? " / 9" : "")")
                .font(AppFont.mono(12, weight: .semibold))
                .foregroundStyle(Formatting.pnlColor(value))
        }
    }
}

struct MobileScoreBreakdownCard: View {
    let total: Double
    let technical: Double
    let sentiment: Double
    let commodity: Double
    let reasons: [String]

    private var resolvedReasons: [String] {
        reasons.filter { !$0.hasPrefix("Price:") && !$0.hasPrefix("ATR:") }
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(signedScore(total))
                    .font(AppFont.mono(30, weight: .bold))
                    .foregroundStyle(Formatting.pnlColor(total))

                Text("/ 9.00")
                    .font(AppFont.mono(12, weight: .medium))
                    .foregroundStyle(Theme.textDimmed)

                Spacer()

                MobileSignalPill(text: scoreLabel(for: total), style: scoreStyle(for: total))
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 16)

            Divider().overlay(Theme.line)

            HStack(spacing: 0) {
                scoreMixCell(title: "Technical", value: technical)
                mixDivider
                scoreMixCell(title: "Sentiment", value: sentiment)
                mixDivider
                scoreMixCell(title: "Commodity", value: commodity)
            }

            if !resolvedReasons.isEmpty {
                Divider().overlay(Theme.line)
            }

            VStack(spacing: 0) {
                ForEach(Array(resolvedReasons.enumerated()), id: \.offset) { index, reason in
                    scoreReasonLine(reason)
                    if index < resolvedReasons.count - 1 {
                        Divider().overlay(Theme.line)
                    }
                }
            }
        }
    }

    private func scoreMixCell(title: String, value: Double) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(title.uppercased())
                .font(AppFont.mono(9, weight: .medium))
                .tracking(1.1)
                .foregroundStyle(Theme.textDimmed)
            Text(signedScore(value))
                .font(AppFont.mono(15, weight: .semibold))
                .foregroundStyle(Formatting.pnlColor(value))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
    }

    private var mixDivider: some View {
        Rectangle()
            .fill(Theme.line)
            .frame(width: 1)
    }

    private func scoreReasonLine(_ reason: String) -> some View {
        HStack(spacing: 10) {
            Circle()
                .fill(scoreReasonDotColor(reason))
                .frame(width: 6, height: 6)

            if let parsed = parseScoreReason(reason) {
                Text(parsed.label)
                    .font(AppFont.sans(13))
                    .foregroundStyle(Theme.textPrimary)
                    .frame(maxWidth: .infinity, alignment: .leading)

                Text(parsed.rawScore)
                    .font(AppFont.mono(12, weight: .semibold))
                    .foregroundStyle(Formatting.pnlColor(parsed.value))
            } else {
                Text(reason)
                    .font(AppFont.sans(13))
                    .foregroundStyle(Theme.textMuted)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 11)
    }
}
