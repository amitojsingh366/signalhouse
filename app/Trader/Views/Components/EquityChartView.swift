import Charts
import SwiftUI

/// Equity curve chart matching web's equity-chart.tsx — uses Swift Charts.
struct EquityChartView: View {
    let snapshots: [SnapshotOut]

    @State private var selectedRange = "ALL"
    private let ranges = ["1W", "1M", "3M", "ALL"]

    private var filtered: [SnapshotOut] {
        guard !snapshots.isEmpty else { return [] }
        let now = Date()
        let cutoff: Date? = {
            switch selectedRange {
            case "1W": return Calendar.current.date(byAdding: .day, value: -7, to: now)
            case "1M": return Calendar.current.date(byAdding: .month, value: -1, to: now)
            case "3M": return Calendar.current.date(byAdding: .month, value: -3, to: now)
            default: return nil
            }
        }()

        guard let cutoff else { return snapshots }
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        return snapshots.filter { snap in
            if let d = formatter.date(from: snap.date) {
                return d >= cutoff
            }
            return true
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Equity Curve")
                    .font(.subheadline)
                    .foregroundStyle(Theme.textMuted)
                Spacer()
                Picker("Range", selection: $selectedRange) {
                    ForEach(ranges, id: \.self) { Text($0) }
                }
                .pickerStyle(.segmented)
                .frame(width: 200)
            }

            if filtered.isEmpty {
                Text("No snapshot data yet")
                    .font(.caption)
                    .foregroundStyle(Theme.textDimmed)
                    .frame(maxWidth: .infinity, minHeight: 200)
            } else {
                Chart(filtered) { snap in
                    AreaMark(
                        x: .value("Date", snap.date),
                        y: .value("Value", snap.portfolioValue)
                    )
                    .foregroundStyle(
                        LinearGradient(
                            colors: [Theme.brand.opacity(0.3), Theme.brand.opacity(0.05)],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )

                    LineMark(
                        x: .value("Date", snap.date),
                        y: .value("Value", snap.portfolioValue)
                    )
                    .foregroundStyle(Theme.brand)
                    .lineStyle(StrokeStyle(lineWidth: 2))
                }
                .chartYScale(domain: .automatic(includesZero: false))
                .chartXAxis {
                    AxisMarks(values: .automatic(desiredCount: 5)) { _ in
                        AxisValueLabel()
                            .foregroundStyle(Theme.textDimmed)
                    }
                }
                .chartYAxis {
                    AxisMarks { _ in
                        AxisGridLine(stroke: StrokeStyle(lineWidth: 0.5))
                            .foregroundStyle(Color.white.opacity(0.06))
                        AxisValueLabel()
                            .foregroundStyle(Theme.textDimmed)
                    }
                }
                .frame(height: 220)
            }
        }
        .padding()
        .glassCard()
    }
}
