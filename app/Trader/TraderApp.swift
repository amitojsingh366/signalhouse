import SwiftUI

@main
struct TraderApp: App {
    @StateObject private var config = AppConfig()
    @StateObject private var pushManager = PushManager()

    var body: some Scene {
        WindowGroup {
            Group {
                if config.isOnboarded {
                    MainTabView()
                        .onAppear {
                            let client = APIClient(baseURL: config.apiBaseURL!)
                            pushManager.apiClient = client
                            pushManager.registerForVoIPPushes()
                        }
                } else {
                    OnboardingView()
                }
            }
            .environmentObject(config)
            .environmentObject(pushManager)
            .preferredColorScheme(.dark)
            .tint(Theme.brand)
        }
    }
}

/// Main tab navigation matching the web sidebar.
struct MainTabView: View {
    @EnvironmentObject private var config: AppConfig

    var body: some View {
        TabView {
            DashboardView()
                .tabItem {
                    Label("Dashboard", systemImage: "house")
                }

            PortfolioView()
                .tabItem {
                    Label("Portfolio", systemImage: "briefcase")
                }

            SignalsView()
                .tabItem {
                    Label("Signals", systemImage: "bolt")
                }

            TradesView()
                .tabItem {
                    Label("Trades", systemImage: "arrow.left.arrow.right")
                }

            UploadView()
                .tabItem {
                    Label("Upload", systemImage: "square.and.arrow.up")
                }

            StatusView()
                .tabItem {
                    Label("Status", systemImage: "waveform.path.ecg")
                }
        }
    }
}
