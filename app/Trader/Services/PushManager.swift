import CallKit
import Combine
import PushKit
import SwiftUI
import UserNotifications

/// Manages VoIP push registration (PushKit), standard push (UNUserNotificationCenter),
/// incoming call UI (CallKit), and deep-link routing for notification taps.
@MainActor
final class PushManager: NSObject, ObservableObject {
    @Published var deviceToken: String?
    @Published var pushToken: String?
    /// Deep-link destination set when the user taps a notification.
    @Published var deepLink: DeepLink?

    private var voipRegistry: PKPushRegistry?
    private var provider: CXProvider?

    /// Weak reference to the API client — set by the app after onboarding.
    var apiClient: APIClient?

    // MARK: - Deep Link

    enum DeepLink: Equatable {
        case premarket
        case dashboard
        case signals
    }

    // MARK: - Setup

    func registerForVoIPPushes() {
        let registry = PKPushRegistry(queue: .main)
        registry.delegate = self
        registry.desiredPushTypes = [.voIP]
        self.voipRegistry = registry

        let config = CXProviderConfiguration()
        config.maximumCallsPerCallGroup = 1
        config.supportsVideo = false
        config.supportedHandleTypes = [.generic]

        let prov = CXProvider(configuration: config)
        prov.setDelegate(self, queue: .main)
        self.provider = prov
    }

    /// Register for standard (alert) push notifications.
    func registerForStandardPush() {
        UNUserNotificationCenter.current().delegate = self
        UNUserNotificationCenter.current().requestAuthorization(
            options: [.alert, .badge, .sound]
        ) { granted, error in
            if let error {
                print("[PushManager] Push auth error: \(error)")
            }
            guard granted else { return }
            DispatchQueue.main.async {
                UIApplication.shared.registerForRemoteNotifications()
            }
        }
    }

    /// Called from AppDelegate/SceneDelegate when standard push token arrives.
    func didRegisterForRemoteNotifications(deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        self.pushToken = token
        // Re-register with API including the push token
        Task {
            try? await apiClient?.registerDevice(
                token: self.deviceToken ?? "",
                pushToken: token
            )
        }
    }
}

// MARK: - UNUserNotificationCenterDelegate

extension PushManager: UNUserNotificationCenterDelegate {
    /// Show notification banners even when app is in foreground.
    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound, .badge])
    }

    /// Handle notification tap — route to appropriate deep link.
    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        let userInfo = response.notification.request.content.userInfo
        let type = userInfo["notification_type"] as? String ?? ""

        Task { @MainActor in
            switch type {
            case "premarket":
                self.deepLink = .premarket
            case "briefing", "recap", "close":
                self.deepLink = .dashboard
            default:
                self.deepLink = .signals
            }
        }
        completionHandler()
    }
}

// MARK: - PKPushRegistryDelegate

extension PushManager: PKPushRegistryDelegate {
    nonisolated func pushRegistry(
        _ registry: PKPushRegistry,
        didUpdate pushCredentials: PKPushCredentials,
        for type: PKPushType
    ) {
        let token = pushCredentials.token
            .map { String(format: "%02x", $0) }
            .joined()

        Task { @MainActor in
            self.deviceToken = token
            // Register with API server
            try? await apiClient?.registerDevice(token: token, pushToken: self.pushToken)
        }
    }

    nonisolated func pushRegistry(
        _ registry: PKPushRegistry,
        didReceiveIncomingPushWith payload: PKPushPayload,
        for type: PKPushType,
        completion: @escaping () -> Void
    ) {
        // MUST report a new incoming call to CallKit immediately.
        // If we don't, iOS will permanently stop delivering VoIP pushes.
        let data = payload.dictionaryPayload
        let uuidString = data["uuid"] as? String ?? UUID().uuidString
        let uuid = UUID(uuidString: uuidString) ?? UUID()
        let callerName = data["caller_name"] as? String ?? "Trading Signal"

        let update = CXCallUpdate()
        update.remoteHandle = CXHandle(type: .generic, value: "trader-signal")
        update.localizedCallerName = callerName
        update.hasVideo = false
        update.supportsGrouping = false
        update.supportsHolding = false
        update.supportsUngrouping = false

        Task { @MainActor in
            self.provider?.reportNewIncomingCall(with: uuid, update: update) { error in
                if let error {
                    print("[PushManager] Failed to report call: \(error)")
                }
                completion()
            }

            // Store notification_id for acknowledgment when answered
            if let notifId = data["notification_id"] as? Int {
                UserDefaults.standard.set(notifId, forKey: "pending_notification_\(uuid.uuidString)")
            }
        }
    }
}

// MARK: - CXProviderDelegate

extension PushManager: CXProviderDelegate {
    nonisolated func providerDidReset(_ provider: CXProvider) {}

    nonisolated func provider(_ provider: CXProvider, perform action: CXAnswerCallAction) {
        // User answered — acknowledge the notification to stop retry
        let uuid = action.callUUID
        let key = "pending_notification_\(uuid.uuidString)"
        let notifId = UserDefaults.standard.integer(forKey: key)

        if notifId > 0 {
            Task { @MainActor in
                try? await self.apiClient?.acknowledgeNotification(id: notifId)
                // Deep link to signals when answering a signal call
                self.deepLink = .signals
            }
            UserDefaults.standard.removeObject(forKey: key)
        }

        // End the call immediately — it's not a real call
        provider.reportCall(with: uuid, endedAt: nil, reason: .remoteEnded)
        action.fulfill()
    }

    nonisolated func provider(_ provider: CXProvider, perform action: CXEndCallAction) {
        // User declined — just clean up
        let uuid = action.callUUID
        UserDefaults.standard.removeObject(forKey: "pending_notification_\(uuid.uuidString)")
        action.fulfill()
    }
}
