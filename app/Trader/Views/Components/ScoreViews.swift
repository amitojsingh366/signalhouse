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

struct ScoreReasonRow: View {
    let text: String

    var body: some View {
        if let parsed = parseScoreReason(text) {
            HStack {
                Text(parsed.label)
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)
                Spacer()
                Text(parsed.rawScore)
                    .font(.caption2)
                    .fontDesign(.monospaced)
                    .foregroundStyle(Formatting.pnlColor(parsed.value))
            }
        } else {
            Text(text)
                .font(.caption)
                .foregroundStyle(Theme.textMuted)
        }
    }
}

struct ScoreMixCard: View {
    let technical: Double
    let sentiment: Double
    let commodity: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Score Mix")
                .font(.caption2)
                .foregroundStyle(Theme.textDimmed)
                .textCase(.uppercase)
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
    private func scoreRow(label: String, value: Double) -> some View {
        HStack {
            Text(label)
                .font(.caption)
                .foregroundStyle(Theme.textMuted)
            Spacer()
            Text("\(value > 0 ? "+" : "")\(String(format: "%.2f", value))")
                .font(.caption)
                .fontDesign(.monospaced)
                .foregroundStyle(Formatting.pnlColor(value))
        }
    }
}
