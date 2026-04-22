import Charts
import SwiftUI

struct PriceHistoryChartContent: View {
    let bars: [PriceBar]

    private static let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            let parsed = bars.compactMap { bar -> (Date, Double)? in
                guard let date = Self.dateFormatter.date(from: bar.date) else { return nil }
                return (date, bar.close)
            }

            let values = parsed.map(\.1)
            let minValue = values.min() ?? 0
            let maxValue = values.max() ?? 0
            let spread = max(maxValue - minValue, 0.01)
            let pad = spread * 0.1

            Chart(Array(parsed.enumerated()), id: \.offset) { _, item in
                AreaMark(
                    x: .value("Date", item.0),
                    y: .value("Price", item.1)
                )
                .foregroundStyle(
                    LinearGradient(
                        colors: [Theme.brand.opacity(0.35), Theme.brand.opacity(0.03)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )

                LineMark(
                    x: .value("Date", item.0),
                    y: .value("Price", item.1)
                )
                .foregroundStyle(Theme.brand)
                .lineStyle(StrokeStyle(lineWidth: 2))
            }
            .chartYAxis(.hidden)
            .chartXScale(range: .plotDimension(padding: 4))
            .chartYScale(domain: (minValue - pad)...(maxValue + pad))
            .frame(height: 130)

            if let firstDate = parsed.first?.0,
               let middleDate = parsed[safe: parsed.count / 2]?.0,
               let lastDate = parsed.last?.0,
               let lastPrice = parsed.last?.1 {
                HStack {
                    Text(formatShortDate(firstDate))
                    Spacer()
                    Text(formatShortDate(middleDate))
                    Spacer()
                    Text(formatShortDate(lastDate))
                    Spacer()
                    Text(Formatting.currency(lastPrice))
                }
                .font(AppFont.mono(10, weight: .medium))
                .foregroundStyle(Theme.textDimmed)
            }
        }
    }

    private func formatShortDate(_ date: Date) -> String {
        date.formatted(.dateTime.month(.abbreviated).day())
    }
}

private extension Array {
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
