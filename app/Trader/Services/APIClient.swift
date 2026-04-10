import Combine
import Foundation

/// REST API client mirroring web/lib/api.ts.
@MainActor
final class APIClient: ObservableObject {
    let baseURL: String
    private let session: URLSession
    private let decoder: JSONDecoder

    /// Called when a 401 is received — set by AuthManager
    var onUnauthorized: (() -> Void)?

    init(baseURL: String) {
        self.baseURL = baseURL.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        self.session = URLSession.shared
        self.decoder = JSONDecoder()
        self.decoder.keyDecodingStrategy = .convertFromSnakeCase
    }

    // MARK: - Generic fetch

    private func fetch<T: Decodable>(
        _ path: String,
        method: String = "GET",
        body: (any Encodable)? = nil
    ) async throws -> T {
        guard let url = URL(string: "\(baseURL)\(path)") else {
            throw APIError.invalidURL(path)
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        // Inject auth token if available
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

        return try decoder.decode(T.self, from: data)
    }

    // MARK: - Portfolio

    func getHoldings() async throws -> PortfolioSummary {
        try await fetch("/api/portfolio/holdings")
    }

    func getPnl() async throws -> PnlSummary {
        try await fetch("/api/portfolio/pnl")
    }

    func getSnapshots() async throws -> [SnapshotOut] {
        try await fetch("/api/portfolio/snapshots")
    }

    func updateHolding(symbol: String, quantity: Double?, avgCost: Double?) async throws {
        struct Body: Encodable { let symbol: String; let quantity: Double?; let avgCost: Double? }
        let _: [String: AnyCodable] = try await fetch(
            "/api/portfolio/holding", method: "PUT",
            body: Body(symbol: symbol, quantity: quantity, avgCost: avgCost)
        )
    }

    func deleteHolding(symbol: String) async throws {
        let encoded = symbol.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? symbol
        let _: [String: AnyCodable] = try await fetch(
            "/api/portfolio/holding/\(encoded)", method: "DELETE"
        )
    }

    func updateCash(_ cash: Double) async throws {
        struct Body: Encodable { let cash: Double }
        let _: [String: AnyCodable] = try await fetch(
            "/api/portfolio/cash", method: "PUT", body: Body(cash: cash)
        )
    }

    // MARK: - Trades

    func recordBuy(symbol: String, quantity: Double, price: Double) async throws -> TradeOut {
        struct Body: Encodable { let symbol: String; let quantity: Double; let price: Double }
        return try await fetch(
            "/api/trades/buy", method: "POST",
            body: Body(symbol: symbol, quantity: quantity, price: price)
        )
    }

    func recordSell(symbol: String, quantity: Double, price: Double) async throws -> TradeOut {
        struct Body: Encodable { let symbol: String; let quantity: Double; let price: Double }
        return try await fetch(
            "/api/trades/sell", method: "POST",
            body: Body(symbol: symbol, quantity: quantity, price: price)
        )
    }

    func getTradeHistory(limit: Int = 50) async throws -> [TradeOut] {
        try await fetch("/api/trades/history?limit=\(limit)")
    }

    // MARK: - Signals

    func checkSignal(symbol: String) async throws -> SignalOut {
        let encoded = symbol.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? symbol
        return try await fetch("/api/signals/check/\(encoded)")
    }

    func getRecommendations(n: Int = 5) async throws -> RecommendationOut {
        try await fetch("/api/signals/recommend?n=\(n)")
    }

    func getActionPlan() async throws -> ActionPlanOut {
        try await fetch("/api/signals/actions")
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
        return try await fetch(
            "/api/signals/snooze", method: "POST",
            body: Body(symbol: symbol, hours: hours, indefinite: indefinite, phantomTrailingStop: phantomTrailingStop)
        )
    }

    func unsnoozeSignal(symbol: String) async throws {
        let encoded = symbol.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? symbol
        let _: [String: AnyCodable] = try await fetch(
            "/api/signals/snooze/\(encoded)", method: "DELETE"
        )
    }

    // MARK: - Insights

    func getInsights() async throws -> InsightsOut {
        try await fetch("/api/signals/insights")
    }

    func getPremarketMovers() async throws -> PremarketResponse {
        try await fetch("/api/signals/premarket")
    }

    // MARK: - Status

    func getStatus() async throws -> StatusOut {
        try await fetch("/api/status")
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
    }

    // MARK: - Symbols

    func getSymbols() async throws -> [SymbolInfo] {
        try await fetch("/api/symbols")
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
        return try await fetch("/api/notifications/preferences?device_token=\(encoded)")
    }

    func updateNotificationPrefs(token: String, enabled: Bool?, dailyDisabled: Bool?) async throws -> NotificationPrefsOut {
        let encoded = token.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? token
        struct Body: Encodable { let enabled: Bool?; let dailyDisabled: Bool? }
        return try await fetch(
            "/api/notifications/preferences?device_token=\(encoded)", method: "PUT",
            body: Body(enabled: enabled, dailyDisabled: dailyDisabled)
        )
    }

    func acknowledgeNotification(id: Int) async throws {
        let _: [String: AnyCodable] = try await fetch(
            "/api/notifications/acknowledge/\(id)", method: "POST"
        )
    }

    func getNotificationHistory(token: String, limit: Int = 20) async throws -> [NotificationLogOut] {
        let encoded = token.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? token
        return try await fetch("/api/notifications/history?device_token=\(encoded)&limit=\(limit)")
    }

    // MARK: - Auth

    func getAuthStatus() async throws -> AuthStatusOut {
        try await fetch("/api/auth/status")
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
