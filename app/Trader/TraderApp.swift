import SwiftUI

@main
struct TraderApp: App {
    @StateObject private var config = AppConfig()
    @StateObject private var pushManager = PushManager()
    @StateObject private var authManager = AuthManager()
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

    var body: some Scene {
        WindowGroup {
            Group {
                if config.isOnboarded {
                    AuthGateView()
                        .onAppear {
                            let client = APIClient(baseURL: config.apiBaseURL!)
                            pushManager.apiClient = client
                            pushManager.registerForVoIPPushes()
                            pushManager.registerForStandardPush()
                            appDelegate.pushManager = pushManager
                            client.onUnauthorized = {
                                authManager.isAuthenticated = false
                            }
                            Task {
                                await authManager.checkStatus(client: client)
                            }
                        }
                } else {
                    OnboardingView()
                }
            }
            .environmentObject(config)
            .environmentObject(pushManager)
            .environmentObject(authManager)
            .preferredColorScheme(.dark)
            .font(AppFont.sans(15))
            .tint(Theme.brand)
        }
    }
}

/// AppDelegate for receiving standard push token.
class AppDelegate: NSObject, UIApplicationDelegate {
    var pushManager: PushManager?

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        Task { @MainActor in
            pushManager?.didRegisterForRemoteNotifications(deviceToken: deviceToken)
        }
    }
}

/// Auth gate — shows passkey login if auth is required but not authenticated.
struct AuthGateView: View {
    @EnvironmentObject private var config: AppConfig
    @EnvironmentObject private var authManager: AuthManager

    @State private var error: String?
    @State private var isLoading = false

    var body: some View {
        Group {
            if authManager.isChecking {
                ProgressView("Connecting...")
            } else if authManager.authRequired && !authManager.isAuthenticated {
                VStack(spacing: 24) {
                    Image(systemName: "shield.lefthalf.filled")
                        .font(.system(size: 48))
                        .foregroundStyle(Theme.brand)

                    Text("Authentication Required")
                        .font(.title2)
                        .fontWeight(.bold)

                    Text("Sign in with your passkey to access the trading dashboard.")
                        .font(.subheadline)
                        .foregroundStyle(Theme.textMuted)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)

                    if let error {
                        Text(error)
                            .font(.caption)
                            .foregroundStyle(Theme.negative)
                            .padding(.horizontal)
                    }

                    Button {
                        Task { await login() }
                    } label: {
                        HStack {
                            Image(systemName: "key.fill")
                            Text(isLoading ? "Authenticating..." : "Sign In with Passkey")
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Theme.brand)
                        .foregroundStyle(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    .disabled(isLoading)
                    .padding(.horizontal, 32)
                }
            } else {
                MainTabView()
            }
        }
    }

    private func login() async {
        isLoading = true
        error = nil
        defer { isLoading = false }

        let client = APIClient(baseURL: config.apiBaseURL ?? "")
        do {
            try await authManager.login(client: client)
        } catch {
            self.error = error.localizedDescription
        }
    }
}

/// Main tab navigation matching the web sidebar.
struct MainTabView: View {
    @EnvironmentObject private var pushManager: PushManager

    @State private var selectedTab: AppTab = .dashboard
    @State private var morePath = NavigationPath()

    var body: some View {
        TabView(selection: $selectedTab) {
            DashboardView()
                .tabItem {
                    Label(AppTab.dashboard.title, systemImage: AppTab.dashboard.icon)
                }
                .tag(AppTab.dashboard)

            PortfolioView()
                .tabItem {
                    Label(AppTab.portfolio.title, systemImage: AppTab.portfolio.icon)
                }
                .tag(AppTab.portfolio)

            SignalsView()
                .tabItem {
                    Label(AppTab.actions.title, systemImage: AppTab.actions.icon)
                }
                .tag(AppTab.actions)

            TradesView()
                .tabItem {
                    Label(AppTab.trades.title, systemImage: AppTab.trades.icon)
                }
                .tag(AppTab.trades)

            MoreView(path: $morePath)
                .tabItem {
                    Label(AppTab.more.title, systemImage: AppTab.more.icon)
                }
                .tag(AppTab.more)
        }
        .tint(Theme.brand)
        .onReceive(NotificationCenter.default.publisher(for: .openActionsTab)) { _ in
            selectedTab = .actions
        }
        .onChange(of: pushManager.deepLink) { _, link in
            guard let link else { return }
            switch link {
            case .dashboard:
                selectedTab = .dashboard
            case .signals:
                selectedTab = .actions
            case .signalCheck:
                selectedTab = .actions
            case .premarket:
                selectedTab = .more
                morePath = NavigationPath()
                morePath.append(MoreRoute.premarket)
            }
            // Deep link is consumed by SignalsView, clear after a short delay
            if case .signalCheck = link {
                // Let SignalsView read it first
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                    pushManager.deepLink = nil
                }
            } else {
                pushManager.deepLink = nil
            }
        }
    }
}
