import SwiftUI

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
