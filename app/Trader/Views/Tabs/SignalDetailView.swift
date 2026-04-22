import SwiftUI

/// Detail view for a checked signal with a shared layout used by holding detail.
struct SignalDetailView: View {
    @EnvironmentObject private var config: AppConfig
    let signal: SignalOut

    @State private var matchingHolding: HoldingAdvice?

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    var body: some View {
        InstrumentDetailView(
            snapshot: InstrumentSignalSnapshot(signal: signal),
            position: matchingHolding
        )
        .task { await loadMatchingHolding() }
    }

    private func loadMatchingHolding() async {
        do {
            let portfolio = try await client.getHoldings()
            matchingHolding = portfolio.holdings.first {
                $0.symbol.caseInsensitiveCompare(signal.symbol) == .orderedSame
            }
        } catch {
            matchingHolding = nil
        }
    }
}
