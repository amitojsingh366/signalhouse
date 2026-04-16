import Combine
import Foundation

/// REST API client mirroring web/lib/api.ts.
@MainActor
final class APIClient: ObservableObject {
    enum QueryPolicy {
        case networkOnly
        case cacheFirst(staleTime: TimeInterval)
        case staleWhileRevalidate(staleTime: TimeInterval)
    }

    private actor QueryCache {
        struct Entry {
            let data: Data
            let fetchedAt: Date
        }

        private var entries: [String: Entry] = [:]
        private var inFlight: [String: Task<Data, Error>] = [:]

        func query(
            key: String,
            policy: QueryPolicy,
            fetcher: @escaping @Sendable () async throws -> Data,
            onBackgroundRefresh: (@Sendable () -> Void)? = nil
        ) async throws -> Data {
            switch policy {
            case .networkOnly:
                let data = try await fetcher()
                entries[key] = Entry(data: data, fetchedAt: Date())
                return data
            case .cacheFirst(let staleTime):
                if let entry = entries[key], Date().timeIntervalSince(entry.fetchedAt) <= staleTime {
                    return entry.data
                }
                let fresh = try await runSharedFetch(for: key, fetcher: fetcher)
                entries[key] = Entry(data: fresh, fetchedAt: Date())
                return fresh
            case .staleWhileRevalidate(let staleTime):
                if let entry = entries[key] {
                    let isFresh = Date().timeIntervalSince(entry.fetchedAt) <= staleTime
                    if isFresh {
                        return entry.data
                    }

                    if inFlight[key] == nil {
                        inFlight[key] = Task {
                            do {
                                let fresh = try await fetcher()
                                await save(fresh, for: key)
                                await clearInFlight(for: key)
                                onBackgroundRefresh?()
                                return fresh
                            } catch {
                                await clearInFlight(for: key)
                                throw error
                            }
                        }
                    }
                    return entry.data
                }

                let fresh = try await runSharedFetch(for: key, fetcher: fetcher)
                entries[key] = Entry(data: fresh, fetchedAt: Date())
                return fresh
            }
        }

        func invalidate(_ key: String) {
            entries.removeValue(forKey: key)
        }

        func invalidate(prefix: String) {
            let keys = entries.keys.filter { $0.hasPrefix(prefix) }
            keys.forEach { entries.removeValue(forKey: $0) }
        }

        private func runSharedFetch(
            for key: String,
            fetcher: @escaping @Sendable () async throws -> Data
        ) async throws -> Data {
            if let task = inFlight[key] {
                return try await task.value
            }

            let task = Task<Data, Error> {
                do {
                    let fresh = try await fetcher()
                    await clearInFlight(for: key)
                    return fresh
                } catch {
                    await clearInFlight(for: key)
                    throw error
                }
            }
            inFlight[key] = task
            return try await task.value
        }

        private func clearInFlight(for key: String) {
            inFlight.removeValue(forKey: key)
        }

        private func save(_ data: Data, for key: String) {
            entries[key] = Entry(data: data, fetchedAt: Date())
        }
    }

    private static let cache = QueryCache()

    let baseURL: String
    private let session: URLSession
    private let decoder: JSONDecoder

    /// Called when a 401 is received — set by AuthManager
    var onUnauthorized: (() -> Void)?
    let cacheDidUpdate = PassthroughSubject<String, Never>()

    init(baseURL: String) {
        self.baseURL = baseURL.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        self.session = URLSession.shared
        self.decoder = JSONDecoder()
        self.decoder.keyDecodingStrategy = .convertFromSnakeCase
    }

    // MARK: - Generic fetch

    private func requestData(
        _ path: String,
        method: String = "GET",
        body: (any Encodable)? = nil
    ) async throws -> Data {
        guard let url = URL(string: "\(baseURL)\(path)") else {
            throw APIError.invalidURL(path)
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        if let token = AuthManager.getToken() {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        if let body {
            let encoder = JSONEncoder()
            encoder.keyEncodingStrategy = .convertToSnakeCase
            request.httpBody = try encoder.encode(AnyEncodable(body))
        }

        let (data, response) = try await session.data(for: request)

        guard let http = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        if http.statusCode == 401 {
            AuthManager.clearToken()
            onUnauthorized?()
            throw APIError.httpError(401, "Authentication required")
        }

        guard (200...299).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw APIError.httpError(http.statusCode, body)
        }

        return data
    }

    private func fetch<T: Decodable>(
        _ path: String,
        method: String = "GET",
        body: (any Encodable)? = nil
    ) async throws -> T {
        let data = try await requestData(path, method: method, body: body)
        return try decoder.decode(T.self, from: data)
    }

    private func fetchCached<T: Decodable>(
        _ path: String,
        policy: QueryPolicy
    ) async throws -> T {
        let key = "\(baseURL)\(path)"
        let data = try await Self.cache.query(
            key: key,
            policy: policy,
            fetcher: { [weak self] in
                guard let self else { throw APIError.invalidResponse }
                return try await self.requestData(path)
            },
            onBackgroundRefresh: { [weak self] in
                Task { @MainActor in
                    self?.cacheDidUpdate.send(path)
                }
            }
        )
        return try decoder.decode(T.self, from: data)
    }

    func queryPublisher<T: Decodable>(
        _ path: String,
        policy: QueryPolicy
    ) -> AnyPublisher<T, Error> {
        Future<T, Error> { [weak self] promise in
            Task {
                guard let self else {
                    promise(.failure(APIError.invalidResponse))
                    return
                }
                do {
                    let value: T = try await self.fetchCached(path, policy: policy)
                    promise(.success(value))
                } catch {
                    promise(.failure(error))
                }
            }
        }
        .eraseToAnyPublisher()
    }

    private func invalidatePortfolioQueries() async {
        await Self.cache.invalidate(prefix: "\(baseURL)/api/portfolio")
        await Self.cache.invalidate("\(baseURL)/api/signals/actions")
        await Self.cache.invalidate(prefix: "\(baseURL)/api/status")
    }

    private func invalidateSignalsQueries() async {
        await Self.cache.invalidate("\(baseURL)/api/signals/actions")
        await Self.cache.invalidate(prefix: "\(baseURL)/api/signals/check/")
        await Self.cache.invalidate(prefix: "\(baseURL)/api/signals/premarket")
        await Self.cache.invalidate(prefix: "\(baseURL)/api/signals/insights")
    }

    private func invalidateTradeQueries() async {
        await Self.cache.invalidate(prefix: "\(baseURL)/api/trades/history")
        await invalidatePortfolioQueries()
    }

    // MARK: - Portfolio

    func getHoldings() async throws -> PortfolioSummary {
        try await fetchCached("/api/portfolio/holdings", policy: .staleWhileRevalidate(staleTime: 30))
    }

    func getPnl() async throws -> PnlSummary {
        try await fetchCached("/api/portfolio/pnl", policy: .staleWhileRevalidate(staleTime: 30))
    }

    func getSnapshots() async throws -> [SnapshotOut] {
        try await fetchCached("/api/portfolio/snapshots", policy: .staleWhileRevalidate(staleTime: 30))
    }

    func updateHolding(symbol: String, quantity: Double?, avgCost: Double?) async throws {
        struct Body: Encodable { let symbol: String; let quantity: Double?; let avgCost: Double? }
        let _: [String: AnyCodable] = try await fetch(
            "/api/portfolio/holding", method: "PUT",
            body: Body(symbol: symbol, quantity: quantity, avgCost: avgCost)
        )
        await invalidatePortfolioQueries()
    }

    func deleteHolding(symbol: String) async throws {
        let encoded = symbol.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? symbol
        let _: [String: AnyCodable] = try await fetch(
            "/api/portfolio/holding/\(encoded)", method: "DELETE"
        )
        await invalidatePortfolioQueries()
    }

    func updateCash(_ cash: Double) async throws {
        struct Body: Encodable { let cash: Double }
        let _: [String: AnyCodable] = try await fetch(
            "/api/portfolio/cash", method: "PUT", body: Body(cash: cash)
        )
        await invalidatePortfolioQueries()
    }

    // MARK: - Trades

    func recordBuy(symbol: String, quantity: Double, price: Double) async throws -> TradeOut {
        struct Body: Encodable { let symbol: String; let quantity: Double; let price: Double }
        let trade: TradeOut = try await fetch(
            "/api/trades/buy", method: "POST",
            body: Body(symbol: symbol, quantity: quantity, price: price)
        )
        await invalidateTradeQueries()
        return trade
    }

    func recordSell(symbol: String, quantity: Double, price: Double) async throws -> TradeOut {
        struct Body: Encodable { let symbol: String; let quantity: Double; let price: Double }
        let trade: TradeOut = try await fetch(
            "/api/trades/sell", method: "POST",
            body: Body(symbol: symbol, quantity: quantity, price: price)
        )
        await invalidateTradeQueries()
        return trade
    }

    func getTradeHistory(limit: Int = 50) async throws -> [TradeOut] {
        try await fetchCached("/api/trades/history?limit=\(limit)", policy: .staleWhileRevalidate(staleTime: 20))
    }

    // MARK: - Signals

    func checkSignal(symbol: String) async throws -> SignalOut {
        let encoded = symbol.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? symbol
        return try await fetchCached("/api/signals/check/\(encoded)", policy: .cacheFirst(staleTime: 60))
    }

    func getRecommendations(n: Int = 5) async throws -> RecommendationOut {
        try await fetch("/api/signals/recommend?n=\(n)")
    }

    func getActionPlan() async throws -> ActionPlanOut {
        try await fetchCached("/api/signals/actions", policy: .staleWhileRevalidate(staleTime: 20))
    }

    func getPriceHistory(symbol: String, period: String = "60d") async throws -> PriceHistory {
        let encoded = symbol.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? symbol
        return try await fetch("/api/signals/history/\(encoded)?period=\(period)")
    }

    func snoozeSignal(symbol: String, hours: Double = 4, indefinite: Bool = false, phantomTrailingStop: Bool = true) async throws -> SnoozeOut {
        struct Body: Encodable {
            let symbol: String
            let hours: Double
            let indefinite: Bool
            let phantomTrailingStop: Bool

            enum CodingKeys: String, CodingKey {
                case symbol, hours, indefinite
                case phantomTrailingStop = "phantom_trailing_stop"
            }
        }
        let out: SnoozeOut = try await fetch(
            "/api/signals/snooze", method: "POST",
            body: Body(symbol: symbol, hours: hours, indefinite: indefinite, phantomTrailingStop: phantomTrailingStop)
        )
        await invalidateSignalsQueries()
        return out
    }

    func unsnoozeSignal(symbol: String) async throws {
        let encoded = symbol.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? symbol
        let _: [String: AnyCodable] = try await fetch(
            "/api/signals/snooze/\(encoded)", method: "DELETE"
        )
        await invalidateSignalsQueries()
    }

    // MARK: - Insights

    func getInsights() async throws -> InsightsOut {
        try await fetchCached("/api/signals/insights", policy: .staleWhileRevalidate(staleTime: 60))
    }

    func getPremarketMovers() async throws -> PremarketResponse {
        try await fetchCached("/api/signals/premarket", policy: .staleWhileRevalidate(staleTime: 60))
    }

    // MARK: - Status

    func getStatus() async throws -> StatusOut {
        try await fetchCached("/api/status", policy: .staleWhileRevalidate(staleTime: 20))
    }

    // MARK: - Upload

    func parseScreenshot(imageData: Data, mimeType: String = "image/png") async throws -> [UploadHolding] {
        guard let url = URL(string: "\(baseURL)/api/upload/parse") else {
            throw APIError.invalidURL("/api/upload/parse")
        }

        let boundary = UUID().uuidString
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        if let token = AuthManager.getToken() {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"screenshot.png\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: \(mimeType)\r\n\r\n".data(using: .utf8)!)
        body.append(imageData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        request.httpBody = body

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            let text = String(data: data, encoding: .utf8) ?? ""
            throw APIError.httpError((response as? HTTPURLResponse)?.statusCode ?? 0, text)
        }
        return try decoder.decode([UploadHolding].self, from: data)
    }

    func confirmUpload(holdings: [UploadHolding]) async throws {
        struct Body: Encodable { let holdings: [UploadHolding] }
        let _: [String: AnyCodable] = try await fetch(
            "/api/upload/confirm", method: "POST",
            body: Body(holdings: holdings)
        )
        await invalidatePortfolioQueries()
    }

    // MARK: - Symbols

    func getSymbols() async throws -> [SymbolInfo] {
        try await fetchCached("/api/symbols", policy: .cacheFirst(staleTime: 600))
    }

    // MARK: - Notifications

    func registerDevice(token: String, pushToken: String? = nil, platform: String = "ios") async throws {
        struct Body: Encodable { let deviceToken: String; let pushToken: String?; let platform: String }
        let _: [String: AnyCodable] = try await fetch(
            "/api/notifications/register", method: "POST",
            body: Body(deviceToken: token, pushToken: pushToken, platform: platform)
        )
    }

    func getNotificationPrefs(token: String) async throws -> NotificationPrefsOut {
        let encoded = token.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? token
        return try await fetchCached("/api/notifications/preferences?device_token=\(encoded)", policy: .staleWhileRevalidate(staleTime: 30))
    }

    func updateNotificationPrefs(
        token: String,
        enabled: Bool?,
        dailyDisabled: Bool?,
        dailyDisabledNotifications: Bool? = nil,
        dailyDisabledCalls: Bool? = nil
    ) async throws -> NotificationPrefsOut {
        let encoded = token.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? token
        struct Body: Encodable {
            let enabled: Bool?
            let dailyDisabled: Bool?
            let dailyDisabledNotifications: Bool?
            let dailyDisabledCalls: Bool?
        }
        let prefs: NotificationPrefsOut = try await fetch(
            "/api/notifications/preferences?device_token=\(encoded)", method: "PUT",
            body: Body(
                enabled: enabled,
                dailyDisabled: dailyDisabled,
                dailyDisabledNotifications: dailyDisabledNotifications,
                dailyDisabledCalls: dailyDisabledCalls
            )
        )
        await Self.cache.invalidate("\(baseURL)/api/notifications/preferences?device_token=\(encoded)")
        return prefs
    }

    func acknowledgeNotification(id: Int) async throws {
        let _: [String: AnyCodable] = try await fetch(
            "/api/notifications/acknowledge/\(id)", method: "POST"
        )
        await Self.cache.invalidate(prefix: "\(baseURL)/api/notifications/history")
    }

    func getNotificationHistory(token: String, limit: Int = 20) async throws -> [NotificationLogOut] {
        let encoded = token.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? token
        return try await fetchCached("/api/notifications/history?device_token=\(encoded)&limit=\(limit)", policy: .staleWhileRevalidate(staleTime: 20))
    }

    // MARK: - Auth

    func getAuthStatus() async throws -> AuthStatusOut {
        try await fetchCached("/api/auth/status", policy: .staleWhileRevalidate(staleTime: 30))
    }

    func getRegisterOptions() async throws -> [String: AnyCodable] {
        try await fetch("/api/auth/register/options", method: "POST")
    }

    func verifyRegistration(credential: [String: Any]) async throws -> AuthTokenOut {
        guard let url = URL(string: "\(baseURL)/api/auth/register/verify") else {
            throw APIError.invalidURL("/api/auth/register/verify")
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: credential)

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            let text = String(data: data, encoding: .utf8) ?? ""
            throw APIError.httpError((response as? HTTPURLResponse)?.statusCode ?? 0, text)
        }
        return try decoder.decode(AuthTokenOut.self, from: data)
    }

    func getLoginOptions() async throws -> [String: AnyCodable] {
        try await fetch("/api/auth/login/options", method: "POST")
    }

    func verifyLogin(credential: [String: Any]) async throws -> AuthTokenOut {
        guard let url = URL(string: "\(baseURL)/api/auth/login/verify") else {
            throw APIError.invalidURL("/api/auth/login/verify")
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: credential)

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            let text = String(data: data, encoding: .utf8) ?? ""
            throw APIError.httpError((response as? HTTPURLResponse)?.statusCode ?? 0, text)
        }
        return try decoder.decode(AuthTokenOut.self, from: data)
    }

    // MARK: - Health check (for onboarding)

    func healthCheck() async throws -> Bool {
        struct Health: Decodable { let status: String }
        let result: Health = try await fetch("/api/health")
        return result.status == "ok"
    }
}

// MARK: - Error types

enum APIError: LocalizedError {
    case invalidURL(String)
    case invalidResponse
    case httpError(Int, String)

    var errorDescription: String? {
        switch self {
        case .invalidURL(let path): return "Invalid URL: \(path)"
        case .invalidResponse: return "Invalid response from server"
        case .httpError(let code, let body): return "HTTP \(code): \(body)"
        }
    }
}

// MARK: - AnyEncodable wrapper

private struct AnyEncodable: Encodable {
    let value: any Encodable

    init(_ value: any Encodable) {
        self.value = value
    }

    func encode(to encoder: Encoder) throws {
        try value.encode(to: encoder)
    }
}
