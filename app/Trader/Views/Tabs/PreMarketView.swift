import SwiftUI

/// Pre-market movers view — shows CDR counterpart stocks with notable premarket moves.
struct PreMarketView: View {
    @EnvironmentObject private var config: AppConfig

    @State private var movers: [PremarketMover] = []
    @State private var isLoading = true

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    var body: some View {
        NavigationStack {
            List {
                if isLoading && movers.isEmpty {
                    Section {
                        ListLoadingView(rows: 6)
                    }
                } else if movers.isEmpty {
                    Section {
                        VStack(spacing: 12) {
                            Image(systemName: "clock.badge.questionmark")
                                .font(.system(size: 36))
                                .foregroundStyle(Theme.textDimmed)
                            Text("No Pre-Market Data")
                                .font(.headline)
                            Text("Movers appear weekdays around 8 AM ET when US premarket data is available.")
                                .font(.caption)
                                .foregroundStyle(Theme.textMuted)
                                .multilineTextAlignment(.center)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 32)
                    }
                } else {
                    Section("CDR Counterpart Moves") {
                        ForEach(movers) { mover in
                            PremarketMoverRow(mover: mover)
                        }
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Pre-Market")
            .refreshable { await loadData() }
            .task { await loadData() }
        }
    }

    private func loadData() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let response = try await client.getPremarketMovers()
            movers = response.movers.sorted { abs($0.changePct) > abs($1.changePct) }
        } catch {
            // Keep existing data on error; pull-to-refresh retries
        }
    }
}

// MARK: - Mover Row

private struct PremarketMoverRow: View {
    let mover: PremarketMover

    var body: some View {
        HStack(spacing: 12) {
            // Direction indicator
            Circle()
                .fill(mover.changePct >= 0 ? Theme.positive : Theme.negative)
                .frame(width: 10, height: 10)

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(mover.cdrSymbol)
                        .font(.headline)
                    Text("(\(mover.usSymbol))")
                        .font(.caption)
                        .foregroundStyle(Theme.textDimmed)
                }
                Text("Premarket: \(Formatting.currency(mover.premarketPrice))")
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)
            }

            Spacer()

            Text(String(format: "%+.1f%%", mover.changePct * 100))
                .font(.system(.body, design: .monospaced))
                .fontWeight(.semibold)
                .foregroundStyle(mover.changePct >= 0 ? Theme.positive : Theme.negative)
                .padding(.horizontal, 10)
                .padding(.vertical, 4)
                .background(
                    (mover.changePct >= 0 ? Theme.positive : Theme.negative).opacity(0.15)
                )
                .clipShape(Capsule())
        }
        .padding(.vertical, 4)
    }
}
