import Foundation

// MARK: - Portfolio

struct HoldingAdvice: Codable, Identifiable {
    var id: String { symbol }
    let symbol: String
    let quantity: Double
    let avgCost: Double
    let currentPrice: Double
    let marketValue: Double
    let pnl: Double
    let pnlPct: Double
    let signal: String
    let strength: Double
    let technicalScore: Double
    let sentimentScore: Double
    let commodityScore: Double
    let action: String
    let actionDetail: String
    let reasons: [String]
    let alternative: [String: AnyCodable]?
}

struct PortfolioSummary: Codable {
    let holdings: [HoldingAdvice]
    let totalValue: Double
    let cash: Double
    let totalCost: Double
    let totalPnl: Double
    let totalPnlPct: Double
}

struct PnlSummary: Codable {
    let currentValue: Double
    let initialCapital: Double
    let cash: Double
    let dailyPnl: Double
    let dailyPnlPct: Double
    let totalPnl: Double
    let totalPnlPct: Double
    let recentTrades: [TradeOut]
}

// MARK: - Trades

struct TradeOut: Codable, Identifiable {
    var id: Int? { _id }
    let _id: Int?
    let symbol: String
    let action: String
    let quantity: Double
    let price: Double
    let total: Double
    let pnl: Double?
    let pnlPct: Double?
    let timestamp: String?

    enum CodingKeys: String, CodingKey {
        case _id = "id"
        case symbol, action, quantity, price, total, pnl, pnlPct, timestamp
    }
}

// MARK: - Signals

struct SignalOut: Codable, Identifiable {
    var id: String { symbol }
    let symbol: String
    let signal: String
    let strength: Double
    let score: Double
    let technicalScore: Double
    let sentimentScore: Double
    let commodityScore: Double
    let reasons: [String]
    let price: Double?
    let sector: String?
}

struct ExitAlert: Codable, Identifiable {
    var id: String { symbol }
    let symbol: String
    let reason: String
    let detail: String
    let severity: String
    let currentPrice: Double
    let entryPrice: Double
    let pnlPct: Double
    let quantity: Double?
    let action: String?
    let actionDetail: String?
}

struct RecommendationOut: Codable {
    let exitAlerts: [ExitAlert]
    let buys: [SignalOut]
    let sells: [SignalOut]
    let watchlistSells: [SignalOut]
    let funding: [[String: AnyCodable]]
    let sectorExposure: [String: AnyCodable]
}

// MARK: - Action Plan

struct ActionItem: Codable, Identifiable {
    var id: String {
        "\(type)-\(symbol ?? "")-\(sellSymbol ?? "")-\(buySymbol ?? "")"
    }
    let type: String  // "BUY", "SELL", "SWAP"
    let urgency: String  // "urgent", "normal", "low"
    let symbol: String?
    let shares: Double?
    let price: Double?
    let dollarAmount: Double?
    let pctOfPortfolio: Double?
    let pnlPct: Double?
    let entryPrice: Double?
    let strength: Double?
    let score: Double?
    let technicalScore: Double?
    let sentimentScore: Double?
    let commodityScore: Double?
    let reason: String
    let detail: String
    let sector: String?
    let reasons: [String]?
    // SWAP fields
    let sellSymbol: String?
    let sellShares: Double?
    let sellPrice: Double?
    let sellAmount: Double?
    let sellPnlPct: Double?
    let buySymbol: String?
    let buyShares: Double?
    let buyPrice: Double?
    let buyAmount: Double?
    let buyStrength: Double?
    let actionable: Bool?
    let snoozed: Bool?
}

struct SnoozeOut: Codable {
    let symbol: String
    let snoozedAt: String
    let expiresAt: String
    let pnlPctAtSnooze: Double
    let indefinite: Bool?
    let phantomTrailingStop: Bool?
}

struct ActionPlanOut: Codable {
    let actions: [ActionItem]
    let portfolioValue: Double
    let cash: Double
    let numPositions: Int
    let maxPositions: Int
    let sellsCount: Int
    let buysCount: Int
    let swapsCount: Int
    let sectorExposure: [String: AnyCodable]
}

// MARK: - Snapshots

struct SnapshotOut: Codable, Identifiable {
    var id: String { date }
    let date: String
    let portfolioValue: Double
    let cash: Double
    let positionsValue: Double
}

// MARK: - Status

struct StatusOut: Codable {
    let symbolsTracked: Int
    let holdingsCount: Int
    let marketOpen: Bool
    let uptimeSeconds: Double?
    let lastScanAt: String?
    let scanIntervalMinutes: Int
    let maxPositions: Int
    let riskHalted: Bool
    let riskHaltReason: String
}

struct TickerStripItem: Codable, Identifiable {
    var id: String { symbol }
    let symbol: String
    let label: String
    let displayPrice: String
    let changePct: Double?
    let changeLabel: String?
    let asOf: String
}

// MARK: - Trading Settings

/// One editable setting from `/api/settings/config`. `value` is dynamic (bool or number).
struct SettingItem: Codable {
    let key: String
    let type: String  // "bool" | "int" | "float"
    let group: String
    let label: String
    let description: String
    let value: SettingValue?
    let min: Double?
    let max: Double?
    let step: Double?
}

enum SettingValue: Codable {
    case bool(Bool)
    case number(Double)

    var boolValue: Bool? {
        if case .bool(let v) = self { return v }
        return nil
    }

    var numberValue: Double? {
        if case .number(let v) = self { return v }
        return nil
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let b = try? container.decode(Bool.self) {
            self = .bool(b)
        } else {
            self = .number(try container.decode(Double.self))
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .bool(let v): try container.encode(v)
        case .number(let v): try container.encode(v)
        }
    }
}

struct SettingsGroupOut: Codable {
    let id: String
    let label: String
    let items: [SettingItem]
}

struct SettingsConfigOut: Codable {
    let groups: [SettingsGroupOut]

    func value(for key: String) -> SettingValue? {
        for group in groups {
            for item in group.items where item.key == key {
                return item.value
            }
        }
        return nil
    }
}

/// Flat projection of trading settings used by iOS.
struct TradingSettings {
    var hybridTakeProfitEnabled: Bool
    var hybridTakeProfitMinBuyStrength: Double
    var oversoldFastlaneEnabled: Bool
    var takeProfitPct: Double
    var stopLossPct: Double
    var maxPositions: Int

    static func from(_ config: SettingsConfigOut) -> TradingSettings {
        TradingSettings(
            hybridTakeProfitEnabled: config.value(for: "risk.hybrid_take_profit_enabled")?.boolValue ?? false,
            hybridTakeProfitMinBuyStrength: config.value(for: "risk.hybrid_take_profit_min_buy_strength")?.numberValue ?? 0.5,
            oversoldFastlaneEnabled: config.value(for: "strategy.oversold_fastlane.enabled")?.boolValue ?? true,
            takeProfitPct: config.value(for: "risk.take_profit_pct")?.numberValue ?? 0.08,
            stopLossPct: config.value(for: "risk.stop_loss_pct")?.numberValue ?? 0.05,
            maxPositions: Int((config.value(for: "risk.max_positions")?.numberValue ?? 12).rounded())
        )
    }
}

// MARK: - Upload

struct UploadHolding: Codable, Identifiable {
    var id: String { symbol }
    var symbol: String
    var quantity: Double
    var marketValueCad: Double
}

// MARK: - Symbols

struct SymbolInfo: Codable, Identifiable {
    var id: String { symbol }
    let symbol: String
    let name: String
    let sector: String
}

// MARK: - Notifications

struct NotificationPrefsOut: Codable {
    let deviceToken: String
    let enabled: Bool
    let dailyDisabledDate: String?
    let dailyDisabledNotificationsDate: String?
    let dailyDisabledCallsDate: String?
}

struct NotificationLogOut: Codable, Identifiable {
    let id: Int
    let notificationType: String?
    let symbol: String
    let signal: String
    let strength: Double
    let callerName: String
    let sentAt: String
    let delivered: Bool
    let acknowledged: Bool
}

// MARK: - Premarket Movers

struct PremarketMover: Codable, Identifiable {
    var id: String { cdrSymbol }
    let cdrSymbol: String
    let usSymbol: String
    let premarketPrice: Double
    let changePct: Double
}

struct PremarketResponse: Codable {
    let movers: [PremarketMover]
}

// MARK: - Insights

struct InsightsOut: Codable {
    let holdings: [[String: AnyCodable]]
    let premarket: [[String: AnyCodable]]
    let topMovers: [[String: AnyCodable]]
    let sectorExposure: [String: AnyCodable]
    let portfolioValue: Double
    let dailyPnl: Double
    let dailyPnlPct: Double
    let totalPnl: Double
    let totalPnlPct: Double
    let cash: Double
}

// MARK: - Price History

struct PriceBar: Codable {
    let date: String
    let open: Double
    let high: Double
    let low: Double
    let close: Double
    let volume: Double
}

struct PriceHistory: Codable {
    let symbol: String
    let bars: [PriceBar]
}

// MARK: - Auth

struct AuthStatusOut: Codable {
    let registered: Bool
    let credentials: [AuthCredentialInfo]
}

struct AuthCredentialInfo: Codable, Identifiable {
    let id: Int
    let name: String
    let createdAt: String?
}

struct AuthTokenOut: Codable {
    let status: String
    let token: String
}

// MARK: - AnyCodable (generic JSON value)

struct AnyCodable: Codable {
    let value: Any

    init(_ value: Any) {
        self.value = value
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            value = NSNull()
        } else if let bool = try? container.decode(Bool.self) {
            value = bool
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let string = try? container.decode(String.self) {
            value = string
        } else if let array = try? container.decode([AnyCodable].self) {
            value = array.map(\.value)
        } else if let dict = try? container.decode([String: AnyCodable].self) {
            value = dict.mapValues(\.value)
        } else {
            value = NSNull()
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch value {
        case is NSNull:
            try container.encodeNil()
        case let bool as Bool:
            try container.encode(bool)
        case let int as Int:
            try container.encode(int)
        case let double as Double:
            try container.encode(double)
        case let string as String:
            try container.encode(string)
        case let array as [Any]:
            try container.encode(array.map { AnyCodable($0) })
        case let dict as [String: Any]:
            try container.encode(dict.mapValues { AnyCodable($0) })
        default:
            try container.encodeNil()
        }
    }
}
