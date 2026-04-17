import SwiftUI

/// App settings and controls (notifications, auth, connection).
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
    @State private var tradingSettings = TradingSettingsOut(
        hybridTakeProfitEnabled: false,
        hybridTakeProfitMinBuyStrength: 0.5,
        oversoldFastlaneEnabled: true
    )
    @State private var updatingHybridMode = false
    @State private var updatingOversoldMode = false

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    if let authStatus {
                        HStack {
                            Text("Status")
                            Spacer()
                            HStack(spacing: 4) {
                                Circle()
                                    .fill(authStatus.registered ? Theme.positive : Theme.warning)
                                    .frame(width: 8, height: 8)
                                Text(authStatus.registered ? "Active" : "Disabled")
                            }
                        }

                        ForEach(authStatus.credentials) { cred in
                            HStack {
                                Image(systemName: "key.fill")
                                    .foregroundStyle(Theme.brand)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(cred.name)
                                        .fontWeight(.medium)
                                    if let date = cred.createdAt {
                                        Text(date.prefix(10))
                                            .font(.caption2)
                                            .foregroundStyle(Theme.textDimmed)
                                    }
                                }
                                Spacer()
                            }
                        }
                    }

                    Button {
                        Task { await registerPasskey() }
                    } label: {
                        HStack {
                            Image(systemName: "plus.circle.fill")
                            Text(isRegistering ? "Registering..." : "Register Passkey")
                        }
                    }
                    .disabled(isRegistering)
                    .foregroundStyle(Theme.brand)

                    if authManager.authRequired {
                        Button {
                            Task { await loginWithPasskey() }
                        } label: {
                            HStack {
                                Image(systemName: "key.fill")
                                Text("Re-authenticate")
                            }
                        }
                        .foregroundStyle(Theme.brand)
                    }

                    if let authError {
                        Text(authError)
                            .font(.caption)
                            .foregroundStyle(Theme.negative)
                    }
                } header: {
                    Text("Authentication")
                } footer: {
                    Text("Passkeys protect your API with biometric authentication. Once registered, all requests require a valid token.")
                }

                Section {
                    Toggle(
                        "Hybrid Profit-Taking",
                        isOn: Binding(
                            get: {
                                tradingSettings.hybridTakeProfitEnabled
                            },
                            set: { newValue in
                                Task { await setHybridProfitTaking(newValue) }
                            }
                        )
                    )
                    .disabled(updatingHybridMode || updatingOversoldMode)

                    Text(
                        tradingSettings.hybridTakeProfitEnabled
                            ? "When the take-profit target is reached, hold instead of auto-selling when signal remains a strong BUY (\(Int(tradingSettings.hybridTakeProfitMinBuyStrength * 100))%+). Existing stop and trailing protections still apply."
                            : "When the take-profit target is reached, winners are sold immediately to lock in profit."
                    )
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)

                    Toggle(
                        "Oversold Fast-Lane",
                        isOn: Binding(
                            get: {
                                tradingSettings.oversoldFastlaneEnabled
                            },
                            set: { newValue in
                                Task { await setOversoldFastlane(newValue) }
                            }
                        )
                    )
                    .disabled(updatingHybridMode || updatingOversoldMode)

                    Text(
                        tradingSettings.oversoldFastlaneEnabled
                            ? "Allows earlier BUY recommendations for guarded oversold reversals below the standard scan threshold. Bearish-crossover and sentiment guards still apply."
                            : "Only the standard BUY scan threshold is used. Oversold fast-lane entries are disabled."
                    )
                    .font(.caption)
                    .foregroundStyle(Theme.textMuted)
                } header: {
                    Text("Trading")
                } footer: {
                    Text("Use Hybrid mode if you want to let winners run when momentum is still strong.")
                }

                Section {
                    Toggle("Push Notifications", isOn: $notifEnabled)
                        .onChange(of: notifEnabled) { _, newValue in
                            Task { await toggleEnabled(newValue) }
                        }

                    Button(
                        isNotificationsMutedToday
                            ? "Unmute Notifications for Today"
                            : "Mute Notifications for Today"
                    ) {
                        Task { await toggleNotificationsMuteToday() }
                    }
                    .foregroundStyle(isNotificationsMutedToday ? Theme.positive : Theme.warning)

                    Button(
                        isCallsMutedToday
                            ? "Unmute Calls for Today"
                            : "Mute Calls for Today"
                    ) {
                        Task { await toggleCallsMuteToday() }
                    }
                    .foregroundStyle(isCallsMutedToday ? Theme.positive : Theme.warning)

                    if let token = pushManager.deviceToken {
                        LabeledContent("Device Token") {
                            Text(String(token.prefix(12)) + "...")
                                .font(.caption)
                                .foregroundStyle(Theme.textDimmed)
                        }
                    } else {
                        HStack {
                            Image(systemName: "exclamationmark.triangle")
                                .foregroundStyle(Theme.warning)
                            Text("VoIP push not registered")
                                .font(.caption)
                                .foregroundStyle(Theme.textMuted)
                        }
                    }
                } header: {
                    Text("Notifications")
                } footer: {
                    Text("When enabled, high-confidence signals will trigger a phone call via CallKit to get your attention, even in Do Not Disturb mode.")
                }

                if !notifHistory.isEmpty {
                    Section("Recent Notifications") {
                        ForEach(notifHistory) { notif in
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(notif.callerName)
                                        .fontWeight(.medium)
                                    Text(notif.sentAt)
                                        .font(.caption2)
                                        .foregroundStyle(Theme.textDimmed)
                                }
                                Spacer()
                                VStack(alignment: .trailing, spacing: 2) {
                                    SignalBadgeView(signal: notif.signal, strength: notif.strength)
                                    HStack(spacing: 4) {
                                        if notif.delivered {
                                            Image(systemName: "checkmark.circle.fill")
                                                .font(.caption2)
                                                .foregroundStyle(Theme.positive)
                                        }
                                        if notif.acknowledged {
                                            Image(systemName: "phone.fill")
                                                .font(.caption2)
                                                .foregroundStyle(Theme.positive)
                                        }
                                    }
                                }
                            }
                            .padding(.vertical, 2)
                        }
                    }
                }

                Section("Connection") {
                    LabeledContent("API Server") {
                        Text(config.apiBaseURL ?? "Not set")
                            .font(.caption)
                            .foregroundStyle(Theme.textDimmed)
                    }
                    Button("Disconnect & Reset", role: .destructive) {
                        config.reset()
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Settings")
            .refreshable { await loadAll() }
            .task { await loadAll() }
        }
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
        async let tradingSettingsTask = client.getTradingSettings()
        do {
            authStatus = try await authStatusTask
        } catch {}
        do {
            tradingSettings = try await tradingSettingsTask
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

        let current = tradingSettings
        let previous = current.hybridTakeProfitEnabled
        tradingSettings = TradingSettingsOut(
            hybridTakeProfitEnabled: enabled,
            hybridTakeProfitMinBuyStrength: current.hybridTakeProfitMinBuyStrength,
            oversoldFastlaneEnabled: current.oversoldFastlaneEnabled
        )

        do {
            let updated = try await client.updateTradingSettings(
                hybridTakeProfitEnabled: enabled
            )
            tradingSettings = updated
        } catch {
            tradingSettings = TradingSettingsOut(
                hybridTakeProfitEnabled: previous,
                hybridTakeProfitMinBuyStrength: current.hybridTakeProfitMinBuyStrength,
                oversoldFastlaneEnabled: current.oversoldFastlaneEnabled
            )
        }
    }

    private func setOversoldFastlane(_ enabled: Bool) async {
        updatingOversoldMode = true
        defer { updatingOversoldMode = false }

        let current = tradingSettings
        let previous = current.oversoldFastlaneEnabled
        tradingSettings = TradingSettingsOut(
            hybridTakeProfitEnabled: current.hybridTakeProfitEnabled,
            hybridTakeProfitMinBuyStrength: current.hybridTakeProfitMinBuyStrength,
            oversoldFastlaneEnabled: enabled
        )

        do {
            let updated = try await client.updateTradingSettings(
                oversoldFastlaneEnabled: enabled
            )
            tradingSettings = updated
        } catch {
            tradingSettings = TradingSettingsOut(
                hybridTakeProfitEnabled: current.hybridTakeProfitEnabled,
                hybridTakeProfitMinBuyStrength: current.hybridTakeProfitMinBuyStrength,
                oversoldFastlaneEnabled: previous
            )
        }
    }
}
