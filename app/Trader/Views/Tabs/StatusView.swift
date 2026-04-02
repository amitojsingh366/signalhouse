import SwiftUI

/// Status page matching web's status/page.tsx + notification preferences.
struct StatusView: View {
    @EnvironmentObject private var config: AppConfig
    @EnvironmentObject private var pushManager: PushManager

    @EnvironmentObject private var authManager: AuthManager

    @State private var status: StatusOut?
    @State private var isLoading = true
    @State private var notifPrefs: NotificationPrefsOut?
    @State private var notifHistory: [NotificationLogOut] = []
    @State private var notifEnabled = true
    @State private var isMutedToday = false
    @State private var authStatus: AuthStatusOut?
    @State private var isRegistering = false
    @State private var authError: String?

    private var client: APIClient {
        APIClient(baseURL: config.apiBaseURL ?? "")
    }

    var body: some View {
        NavigationStack {
            List {
                // System status
                Section("System") {
                    if isLoading && status == nil {
                        ForEach(0..<6, id: \.self) { _ in
                            StatusRowSkeleton()
                        }
                    } else if let status {
                        LabeledContent("Symbols Tracked", value: "\(status.symbolsTracked)")
                        LabeledContent("Holdings", value: "\(status.holdingsCount)")
                        HStack {
                            Text("Market")
                            Spacer()
                            HStack(spacing: 4) {
                                Circle()
                                    .fill(status.marketOpen ? Theme.positive : Theme.negative)
                                    .frame(width: 8, height: 8)
                                Text(status.marketOpen ? "Open" : "Closed")
                            }
                        }
                        LabeledContent("Scan Interval", value: "\(status.scanIntervalMinutes) min")
                        if let uptime = status.uptimeSeconds {
                            LabeledContent("Uptime", value: formatUptime(uptime))
                        }
                        HStack {
                            Text("Risk Status")
                            Spacer()
                            if status.riskHalted {
                                Text("HALTED")
                                    .font(.caption)
                                    .fontWeight(.semibold)
                                    .foregroundStyle(Theme.negative)
                            } else {
                                Text("Normal")
                                    .foregroundStyle(Theme.positive)
                            }
                        }
                        if status.riskHalted && !status.riskHaltReason.isEmpty {
                            Text(status.riskHaltReason)
                                .font(.caption)
                                .foregroundStyle(Theme.negative)
                        }
                    }
                }

                // Notification preferences
                Section {
                    Toggle("Push Notifications", isOn: $notifEnabled)
                        .onChange(of: notifEnabled) { _, newValue in
                            Task { await toggleEnabled(newValue) }
                        }

                    Button(isMutedToday ? "Unmute for Today" : "Mute for Today") {
                        Task { await toggleMuteToday() }
                    }
                    .foregroundStyle(isMutedToday ? Theme.positive : Theme.warning)

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

                // Notification history
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

                // Authentication
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

                // Connection info
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
            .navigationTitle("Status")
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
        isLoading = true
        defer { isLoading = false }

        async let s = client.getStatus()
        async let a = client.getAuthStatus()
        do { status = try await s } catch {}
        do { authStatus = try await a } catch {}

        // Load notification prefs if we have a device token
        if let token = pushManager.deviceToken {
            do {
                let prefs = try await client.getNotificationPrefs(token: token)
                notifPrefs = prefs
                notifEnabled = prefs.enabled
                let today = ISO8601DateFormatter().string(from: Date()).prefix(10)
                isMutedToday = prefs.dailyDisabledDate == String(today)
            } catch {
                // Device may not be registered yet
            }

            do {
                notifHistory = try await client.getNotificationHistory(token: token)
            } catch {}
        }
    }

    private func toggleEnabled(_ enabled: Bool) async {
        guard let token = pushManager.deviceToken else { return }
        do {
            let prefs = try await client.updateNotificationPrefs(token: token, enabled: enabled, dailyDisabled: nil)
            notifPrefs = prefs
        } catch {
            notifEnabled = !enabled  // revert
        }
    }

    private func toggleMuteToday() async {
        guard let token = pushManager.deviceToken else { return }
        let newMuted = !isMutedToday
        do {
            let prefs = try await client.updateNotificationPrefs(token: token, enabled: nil, dailyDisabled: newMuted)
            notifPrefs = prefs
            isMutedToday = newMuted
        } catch {}
    }

    private func formatUptime(_ seconds: Double) -> String {
        let h = Int(seconds) / 3600
        let m = (Int(seconds) % 3600) / 60
        if h > 0 { return "\(h)h \(m)m" }
        return "\(m)m"
    }
}
