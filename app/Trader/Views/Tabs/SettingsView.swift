import SwiftUI

/// Settings page (from More).
struct SettingsView: View {
    @EnvironmentObject private var config: AppConfig
    @EnvironmentObject private var pushManager: PushManager
    @EnvironmentObject private var authManager: AuthManager

    @State private var notifHistory: [NotificationLogOut] = []
    @State private var notifEnabled = true
    @State private var isNotificationsMutedToday = false
    @State private var isCallsMutedToday = false
    @State private var authStatus: AuthStatusOut?
    @State private var isRegistering = false
    @State private var authError: String?
    @State private var tradingSettings = TradingSettings(
        hybridTakeProfitEnabled: false,
        hybridTakeProfitMinBuyStrength: 0.5,
        oversoldFastlaneEnabled: true
    )
    @State private var updatingHybridMode = false
    @State private var updatingOversoldMode = false
    @State private var strategyRefreshTask: Task<Void, Never>?

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    var body: some View {
        MobileScreen {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 14) {
                    MobileKickerTitle(kicker: "TFSA", title: "Settings")

                    MobileSectionLabel("Authentication")
                    MobileCard {
                        MobileDefRow(label: "Status") {
                            HStack(spacing: 6) {
                                Circle()
                                    .fill((authStatus?.registered ?? false) ? Theme.positive : Theme.warning)
                                    .frame(width: 6, height: 6)
                                MobileValueLabel(text: (authStatus?.registered ?? false) ? "Active" : "Disabled", color: (authStatus?.registered ?? false) ? Theme.positive : Theme.warning)
                            }
                        }
                        Divider().overlay(Theme.line)
                        SettingsActionRow(title: "+ Register passkey", color: Theme.brand) {
                            Task { await registerPasskey() }
                        }
                        Divider().overlay(Theme.line)
                        SettingsActionRow(title: "Re-authenticate", color: Theme.brand) {
                            Task { await loginWithPasskey() }
                        }
                    }

                    if let authError {
                        Text(authError)
                            .font(.system(size: 11))
                            .foregroundStyle(Theme.negative)
                    }

                    MobileSectionLabel("Trading")
                    MobileCard {
                        ToggleRow(
                            title: "Hybrid profit-taking",
                            description: "Sell immediately when take-profit target is reached.",
                            isOn: Binding(
                                get: { tradingSettings.hybridTakeProfitEnabled },
                                set: { newValue in
                                    Task { await setHybridProfitTaking(newValue) }
                                }
                            )
                        )
                        .disabled(updatingHybridMode || updatingOversoldMode)
                        Divider().overlay(Theme.line)
                        ToggleRow(
                            title: "Oversold fast-lane",
                            description: "Allow earlier BUY for guarded oversold reversals.",
                            isOn: Binding(
                                get: { tradingSettings.oversoldFastlaneEnabled },
                                set: { newValue in
                                    Task { await setOversoldFastlane(newValue) }
                                }
                            )
                        )
                        .disabled(updatingHybridMode || updatingOversoldMode)
                        Divider().overlay(Theme.line)
                        MobileDefRow(label: "Take-profit target") {
                            MobileValueLabel(text: "+\(Int(tradingSettings.hybridTakeProfitMinBuyStrength * 100))%")
                        }
                        Divider().overlay(Theme.line)
                        MobileDefRow(label: "Stop-loss floor") {
                            MobileValueLabel(text: "−8.0%")
                        }
                        Divider().overlay(Theme.line)
                        MobileDefRow(label: "Max positions") {
                            MobileValueLabel(text: "5")
                        }
                    }

                    MobileSectionLabel("Notifications")
                    MobileCard {
                        ToggleRow(title: "Push notifications", description: nil, isOn: $notifEnabled)
                            .onChange(of: notifEnabled) { _, newValue in
                                Task { await toggleEnabled(newValue) }
                            }
                        Divider().overlay(Theme.line)
                        SettingsActionRow(
                            title: isNotificationsMutedToday ? "Unmute notifications for today" : "Mute notifications for today",
                            color: Theme.warning
                        ) {
                            Task { await toggleNotificationsMuteToday() }
                        }
                        Divider().overlay(Theme.line)
                        SettingsActionRow(
                            title: isCallsMutedToday ? "Unmute calls for today" : "Mute calls for today",
                            color: Theme.warning
                        ) {
                            Task { await toggleCallsMuteToday() }
                        }
                        Divider().overlay(Theme.line)
                        MobileDefRow(label: "Device token") {
                            MobileValueLabel(text: tokenPrefix)
                        }
                    }

                    MobileSectionLabel("Connection")
                    MobileCard {
                        MobileDefRow(label: "API server") {
                            MobileValueLabel(text: config.apiBaseURL ?? "Not set")
                        }
                        Divider().overlay(Theme.line)
                        SettingsActionRow(title: "Disconnect & reset", color: Theme.negative) {
                            config.reset()
                        }
                    }

                    if !notifHistory.isEmpty {
                        MobileSectionLabel("Recent Notifications")
                        MobileCard {
                            ForEach(Array(notifHistory.prefix(5).enumerated()), id: \.element.id) { index, notification in
                                NotificationHistoryRow(notification: notification)
                                if index < min(notifHistory.count, 5) - 1 {
                                    Divider().overlay(Theme.line)
                                }
                            }
                        }
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 10)
                .padding(.bottom, 40)
            }
        }
        .navigationTitle("Settings")
        .navigationBarTitleDisplayMode(.inline)
        .refreshable { await loadAll() }
        .task { await loadAll() }
        .onDisappear {
            strategyRefreshTask?.cancel()
            strategyRefreshTask = nil
        }
    }

    private var tokenPrefix: String {
        guard let token = pushManager.deviceToken else { return "Not registered" }
        return String(token.prefix(12)) + "..."
    }

    private func registerPasskey() async {
        isRegistering = true
        authError = nil
        defer { isRegistering = false }

        do {
            try await authManager.register(client: client)
            authStatus = try? await client.getAuthStatus()
        } catch {
            authError = error.localizedDescription
        }
    }

    private func loginWithPasskey() async {
        authError = nil
        do {
            try await authManager.login(client: client)
        } catch {
            authError = error.localizedDescription
        }
    }

    private func loadAll() async {
        async let authStatusTask = client.getAuthStatus()
        async let settingsConfigTask = client.getSettingsConfig()
        do {
            authStatus = try await authStatusTask
        } catch {}
        do {
            tradingSettings = TradingSettings.from(try await settingsConfigTask)
        } catch {}

        guard let token = pushManager.deviceToken else {
            notifHistory = []
            return
        }

        do {
            let prefs = try await client.getNotificationPrefs(token: token)
            notifEnabled = prefs.enabled
            let today = ISO8601DateFormatter().string(from: Date()).prefix(10)
            isNotificationsMutedToday = isMutedToday(
                specificDate: prefs.dailyDisabledNotificationsDate,
                fallbackDate: prefs.dailyDisabledDate,
                today: String(today)
            )
            isCallsMutedToday = isMutedToday(
                specificDate: prefs.dailyDisabledCallsDate,
                fallbackDate: prefs.dailyDisabledDate,
                today: String(today)
            )
        } catch {}

        do {
            notifHistory = try await client.getNotificationHistory(token: token)
        } catch {}
    }

    private func toggleEnabled(_ enabled: Bool) async {
        guard let token = pushManager.deviceToken else { return }
        do {
            _ = try await client.updateNotificationPrefs(
                token: token,
                enabled: enabled,
                dailyDisabled: nil
            )
        } catch {
            notifEnabled = !enabled
        }
    }

    private func toggleNotificationsMuteToday() async {
        guard let token = pushManager.deviceToken else { return }
        let newMuted = !isNotificationsMutedToday
        do {
            _ = try await client.updateNotificationPrefs(
                token: token,
                enabled: nil,
                dailyDisabled: nil,
                dailyDisabledNotifications: newMuted
            )
            isNotificationsMutedToday = newMuted
        } catch {}
    }

    private func toggleCallsMuteToday() async {
        guard let token = pushManager.deviceToken else { return }
        let newMuted = !isCallsMutedToday
        do {
            _ = try await client.updateNotificationPrefs(
                token: token,
                enabled: nil,
                dailyDisabled: nil,
                dailyDisabledCalls: newMuted
            )
            isCallsMutedToday = newMuted
        } catch {}
    }

    private func isMutedToday(specificDate: String?, fallbackDate: String?, today: String) -> Bool {
        if let specificDate {
            return specificDate == today
        }
        return fallbackDate == today
    }

    private func setHybridProfitTaking(_ enabled: Bool) async {
        updatingHybridMode = true
        defer { updatingHybridMode = false }

        let previous = tradingSettings.hybridTakeProfitEnabled
        tradingSettings.hybridTakeProfitEnabled = enabled

        do {
            let updated = try await client.updateSettings([
                "risk.hybrid_take_profit_enabled": .bool(enabled)
            ])
            tradingSettings = TradingSettings.from(updated)
            scheduleStrategyRefresh()
        } catch {
            tradingSettings.hybridTakeProfitEnabled = previous
        }
    }

    private func setOversoldFastlane(_ enabled: Bool) async {
        updatingOversoldMode = true
        defer { updatingOversoldMode = false }

        let previous = tradingSettings.oversoldFastlaneEnabled
        tradingSettings.oversoldFastlaneEnabled = enabled

        do {
            let updated = try await client.updateSettings([
                "strategy.oversold_fastlane.enabled": .bool(enabled)
            ])
            tradingSettings = TradingSettings.from(updated)
            scheduleStrategyRefresh()
        } catch {
            tradingSettings.oversoldFastlaneEnabled = previous
        }
    }

    private func scheduleStrategyRefresh() {
        strategyRefreshTask?.cancel()
        strategyRefreshTask = Task {
            do {
                try await Task.sleep(nanoseconds: 600_000_000)
            } catch {
                return
            }
            guard !Task.isCancelled else { return }
            await MainActor.run {
                NotificationCenter.default.post(name: .portfolioDidChange, object: nil)
            }
        }
    }
}

private struct ToggleRow: View {
    let title: String
    let description: String?
    @Binding var isOn: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.system(size: 15, weight: .medium))
                    .foregroundStyle(Theme.textPrimary)
                if let description {
                    Text(description)
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.textMuted)
                }
            }
            Spacer()
            Toggle("", isOn: $isOn)
                .labelsHidden()
                .tint(Theme.brand)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
    }
}

private struct SettingsActionRow: View {
    let title: String
    let color: Color
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(color)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 16)
                .padding(.vertical, 14)
        }
        .buttonStyle(.plain)
    }
}

private struct NotificationHistoryRow: View {
    let notification: NotificationLogOut

    var body: some View {
        HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 4) {
                Text(notification.symbol)
                    .font(.system(size: 13, weight: .semibold, design: .monospaced))
                    .foregroundStyle(Theme.textPrimary)
                Text(notification.sentAt)
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(Theme.textDimmed)
            }
            Spacer()
            SignalBadgeView(signal: notification.signal, strength: notification.strength)
        }
        .padding(16)
    }
}
