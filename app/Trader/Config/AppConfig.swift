import Combine
import Foundation
import SwiftUI

// MARK: - Notification Names

extension Notification.Name {
    /// Posted when portfolio data changes (trade recorded, cash updated, holding edited).
    /// Listeners (e.g. SignalsView) should refresh their action plan.
    static let portfolioDidChange = Notification.Name("portfolioDidChange")
    static let openActionsTab = Notification.Name("openActionsTab")
}

/// Persistent app configuration — API URL stored in UserDefaults.
@MainActor
final class AppConfig: ObservableObject {
    private static let apiBaseURLKey = "apiBaseURL"

    @Published var apiBaseURL: String? {
        didSet {
            UserDefaults.standard.set(apiBaseURL, forKey: Self.apiBaseURLKey)
        }
    }

    var isOnboarded: Bool { apiBaseURL != nil }

    init() {
        self.apiBaseURL = UserDefaults.standard.string(forKey: Self.apiBaseURLKey)
    }

    func reset() {
        apiBaseURL = nil
    }
}
