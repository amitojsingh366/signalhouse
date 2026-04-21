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
        oversoldFastlaneEnabled: true,
        takeProfitPct: 0.08,
        stopLossPct: 0.05,
        maxPositions: 12
    )
    @State private var updatingHybridMode = false
    @State private var updatingOversoldMode = false
    @State private var updatingNotificationPrefs = false
    @State private var strategyRefreshTask: Task<Void, Never>?

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    var body: some View {
        MobileScreen {
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 14) {
                    Text("TFSA")
                        .font(.system(size: 10, weight: .medium, design: .monospaced))
                        .tracking(1.4)
                        .foregroundStyle(Theme.brand)

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
                    }

                    MobileSectionLabel("Notifications")
                    MobileCard {
                        ToggleRow(
                            title: "Push notifications",
                            description: nil,
                            isOn: Binding(
                                get: { notifEnabled },
                                set: { newValue in
                                    Task { await setPushNotificationsEnabled(newValue) }
                                }
                            )
                        )
                        .disabled(updatingNotificationPrefs || pushManager.deviceToken == nil)
                        Divider().overlay(Theme.line)
                        ToggleRow(
                            title: "Mute notifications for today",
                            description: nil,
                            isOn: Binding(
                                get: { isNotificationsMutedToday },
                                set: { newValue in
                                    Task { await setNotificationsMutedToday(newValue) }
                                }
                            )
                        )
                        .disabled(updatingNotificationPrefs || pushManager.deviceToken == nil)
                        Divider().overlay(Theme.line)
                        ToggleRow(
                            title: "Mute calls for today",
                            description: nil,
                            isOn: Binding(
                                get: { isCallsMutedToday },
                                set: { newValue in
                                    Task { await setCallsMutedToday(newValue) }
                                }
                            )
                        )
                        .disabled(updatingNotificationPrefs || pushManager.deviceToken == nil)
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
            notifEnabled = false
            isNotificationsMutedToday = false
            isCallsMutedToday = false
            return
        }

        do {
            let prefs = try await client.getNotificationPrefs(token: token)
            applyNotificationPrefs(prefs)
        } catch {}

        do {
            notifHistory = try await client.getNotificationHistory(token: token)
        } catch {}
    }

    private func applyNotificationPrefs(_ prefs: NotificationPrefsOut) {
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
    }

    private func setPushNotificationsEnabled(_ enabled: Bool) async {
        guard let token = pushManager.deviceToken else { return }
        guard !updatingNotificationPrefs else { return }
        let previous = notifEnabled
        notifEnabled = enabled
        updatingNotificationPrefs = true
        defer { updatingNotificationPrefs = false }

        do {
            let prefs = try await client.updateNotificationPrefs(
                token: token,
                enabled: enabled,
                dailyDisabled: nil
            )
            applyNotificationPrefs(prefs)
        } catch {
            notifEnabled = previous
        }
    }

    private func setNotificationsMutedToday(_ muted: Bool) async {
        guard let token = pushManager.deviceToken else { return }
        guard !updatingNotificationPrefs else { return }
        let previous = isNotificationsMutedToday
        isNotificationsMutedToday = muted
        updatingNotificationPrefs = true
        defer { updatingNotificationPrefs = false }

        do {
            let prefs = try await client.updateNotificationPrefs(
                token: token,
                enabled: nil,
                dailyDisabled: nil,
                dailyDisabledNotifications: muted
            )
            applyNotificationPrefs(prefs)
        } catch {
            isNotificationsMutedToday = previous
        }
    }

    private func setCallsMutedToday(_ muted: Bool) async {
        guard let token = pushManager.deviceToken else { return }
        guard !updatingNotificationPrefs else { return }
        let previous = isCallsMutedToday
        isCallsMutedToday = muted
        updatingNotificationPrefs = true
        defer { updatingNotificationPrefs = false }

        do {
            let prefs = try await client.updateNotificationPrefs(
                token: token,
                enabled: nil,
                dailyDisabled: nil,
                dailyDisabledCalls: muted
            )
            applyNotificationPrefs(prefs)
        } catch {
            isCallsMutedToday = previous
        }
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

private enum NotificationChannelKind {
    case call
    case text
    case both
}

private struct NotificationHistoryRow: View {
    let notification: NotificationLogOut

    private var channelKind: NotificationChannelKind {
        let kind = (notification.notificationType ?? "").lowercased()
        if kind.contains("call") || kind.contains("voip") {
            return .call
        }
        if kind.contains("text")
            || kind.contains("notification")
            || kind.contains("push")
            || kind.contains("alert")
            || kind.contains("premarket")
            || kind.contains("briefing")
            || kind.contains("close")
            || kind.contains("recap") {
            return .text
        }
        // Most trading signal logs are produced as call + alert together.
        return .both
    }

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
            VStack(alignment: .trailing, spacing: 8) {
                NotificationTypeBadge(kind: channelKind)
                SignalBadgeView(signal: notification.signal, strength: notification.strength)
            }
        }
        .padding(16)
    }
}

private struct NotificationTypeBadge: View {
    let kind: NotificationChannelKind

    var body: some View {
        HStack(spacing: 4) {
            switch kind {
            case .call:
                Image(systemName: "phone.fill")
            case .text:
                Image(systemName: "message.fill")
            case .both:
                Image(systemName: "message.fill")
                Image(systemName: "phone.fill")
            }
        }
        .font(AppFont.sans(10, weight: .bold))
        .foregroundStyle(Theme.brand)
        .padding(.horizontal, 8)
        .padding(.vertical, 5)
        .background(Theme.brand.opacity(0.14))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}
