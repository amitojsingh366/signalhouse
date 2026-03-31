import SwiftUI

/// Horizontal bar chart for sector exposure, matching web's sector-chart.tsx.
struct SectorChartView: View {
    let exposure: [String: AnyCodable]

    private var sectors: [(name: String, pct: Double)] {
        exposure.compactMap { key, val in
            // sector_exposure values are dicts with "pct" key, or raw doubles
            if let dict = val.value as? [String: Any], let pct = dict["pct"] as? Double {
                return (key, pct)
            } else if let pct = val.value as? Double {
                return (key, pct)
            }
            return nil
        }
        .sorted { $0.pct > $1.pct }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Sector Exposure")
                .font(.subheadline)
                .foregroundStyle(Theme.textMuted)

            if sectors.isEmpty {
                Text("No sector data")
                    .font(.caption)
                    .foregroundStyle(Theme.textDimmed)
            } else {
                VStack(spacing: 8) {
                    ForEach(Array(sectors.enumerated()), id: \.element.name) { index, sector in
                        HStack(spacing: 8) {
                            Text(sector.name.capitalized)
                                .font(.caption)
                                .foregroundStyle(Theme.textMuted)
                                .frame(width: 100, alignment: .trailing)

                            GeometryReader { geo in
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(barColor(index: index))
                                    .frame(width: max(geo.size.width * sector.pct, 4))
                            }
                            .frame(height: 16)

                            Text(Formatting.percent(sector.pct * 100).replacingOccurrences(of: "+", with: ""))
                                .font(.caption2)
                                .foregroundStyle(Theme.textDimmed)
                                .frame(width: 50, alignment: .trailing)
                        }
                    }
                }
            }
        }
        .padding()
        .glassCard()
    }

    private func barColor(index: Int) -> Color {
        // Purple gradient — brightest to dimmest
        let opacity = max(1.0 - Double(index) * 0.12, 0.3)
        return Theme.brand.opacity(opacity)
    }
}
