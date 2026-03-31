import AuthenticationServices
import Combine
import Foundation
import SwiftUI

/// Manages passkey authentication and JWT token storage.
@MainActor
final class AuthManager: NSObject, ObservableObject {
    @Published var authRequired = false
    @Published var isAuthenticated = false
    @Published var isChecking = true

    private static let tokenKey = "trader_auth_token"

    private var registrationContinuation: CheckedContinuation<ASAuthorizationPlatformPublicKeyCredentialRegistration, Error>?
    private var authenticationContinuation: CheckedContinuation<ASAuthorizationPlatformPublicKeyCredentialAssertion, Error>?

    // MARK: - Token management (Keychain-backed via UserDefaults for simplicity)

    static func getToken() -> String? {
        UserDefaults.standard.string(forKey: tokenKey)
    }

    static func setToken(_ token: String) {
        UserDefaults.standard.set(token, forKey: tokenKey)
    }

    static func clearToken() {
        UserDefaults.standard.removeObject(forKey: tokenKey)
    }

    // MARK: - Check auth status

    func checkStatus(client: APIClient) async {
        isChecking = true
        defer { isChecking = false }

        do {
            let status = try await client.getAuthStatus()
            authRequired = status.registered
            isAuthenticated = status.registered && Self.getToken() != nil
        } catch {
            // Can't reach API — assume no auth needed
            authRequired = false
            isAuthenticated = true
        }
    }

    // MARK: - Passkey registration

    func register(client: APIClient) async throws {
        // 1. Get options from server
        let options = try await client.getRegisterOptions()

        // Parse options
        guard let challengeB64 = (options["challenge"] as? AnyCodable)?.value as? String,
              let challengeData = Self.base64URLDecode(challengeB64),
              let rpDict = (options["rp"] as? AnyCodable)?.value as? [String: Any],
              let rpId = rpDict["id"] as? String,
              let userDict = (options["user"] as? AnyCodable)?.value as? [String: Any],
              let userIdB64 = userDict["id"] as? String,
              let userId = Self.base64URLDecode(userIdB64),
              let userName = userDict["name"] as? String
        else {
            throw AuthError.invalidOptions
        }

        // 2. Create passkey via ASAuthorization
        let provider = ASAuthorizationPlatformPublicKeyCredentialProvider(relyingPartyIdentifier: rpId)
        let request = provider.createCredentialRegistrationRequest(
            challenge: challengeData,
            name: userName,
            userID: userId
        )

        let credential = try await performRegistration(request: request)

        // 3. Serialize and send to server
        let attestation = credential.rawAttestationObject ?? Data()
        let response: [String: Any] = [
            "id": Self.base64URLEncode(credential.credentialID),
            "rawId": Self.base64URLEncode(credential.credentialID),
            "type": "public-key",
            "response": [
                "clientDataJSON": Self.base64URLEncode(credential.rawClientDataJSON),
                "attestationObject": Self.base64URLEncode(attestation),
            ] as [String: Any],
        ]

        let result = try await client.verifyRegistration(credential: response)
        Self.setToken(result.token)
        authRequired = true
        isAuthenticated = true
    }

    // MARK: - Passkey authentication

    func login(client: APIClient) async throws {
        // 1. Get options from server
        let options = try await client.getLoginOptions()

        guard let challengeB64 = (options["challenge"] as? AnyCodable)?.value as? String,
              let challengeData = Self.base64URLDecode(challengeB64),
              let rpId = (options["rpId"] as? AnyCodable)?.value as? String
        else {
            throw AuthError.invalidOptions
        }

        // Parse allowCredentials
        var allowedCredentials: [ASAuthorizationPlatformPublicKeyCredentialDescriptor] = []
        if let allowList = (options["allowCredentials"] as? AnyCodable)?.value as? [[String: Any]] {
            for item in allowList {
                if let idB64 = item["id"] as? String,
                   let idData = Self.base64URLDecode(idB64) {
                    allowedCredentials.append(
                        ASAuthorizationPlatformPublicKeyCredentialDescriptor(credentialID: idData)
                    )
                }
            }
        }

        // 2. Authenticate via ASAuthorization
        let provider = ASAuthorizationPlatformPublicKeyCredentialProvider(relyingPartyIdentifier: rpId)
        let request = provider.createCredentialAssertionRequest(challenge: challengeData)
        if !allowedCredentials.isEmpty {
            request.allowedCredentials = allowedCredentials
        }

        let assertion = try await performAuthentication(request: request)

        // 3. Serialize and send to server
        let response: [String: Any] = [
            "id": Self.base64URLEncode(assertion.credentialID),
            "rawId": Self.base64URLEncode(assertion.credentialID),
            "type": "public-key",
            "response": [
                "clientDataJSON": Self.base64URLEncode(assertion.rawClientDataJSON),
                "authenticatorData": Self.base64URLEncode(assertion.rawAuthenticatorData),
                "signature": Self.base64URLEncode(assertion.signature),
                "userHandle": assertion.userID.map { Self.base64URLEncode($0) } as Any,
            ] as [String: Any],
        ]

        let result = try await client.verifyLogin(credential: response)
        Self.setToken(result.token)
        isAuthenticated = true
    }

    // MARK: - ASAuthorization helpers

    private func performRegistration(request: ASAuthorizationPlatformPublicKeyCredentialRegistrationRequest) async throws -> ASAuthorizationPlatformPublicKeyCredentialRegistration {
        try await withCheckedThrowingContinuation { continuation in
            self.registrationContinuation = continuation
            let controller = ASAuthorizationController(authorizationRequests: [request])
            controller.delegate = self
            controller.performRequests()
        }
    }

    private func performAuthentication(request: ASAuthorizationPlatformPublicKeyCredentialAssertionRequest) async throws -> ASAuthorizationPlatformPublicKeyCredentialAssertion {
        try await withCheckedThrowingContinuation { continuation in
            self.authenticationContinuation = continuation
            let controller = ASAuthorizationController(authorizationRequests: [request])
            controller.delegate = self
            controller.performRequests()
        }
    }

    // MARK: - Base64URL helpers

    static func base64URLEncode(_ data: Data) -> String {
        data.base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }

    static func base64URLDecode(_ string: String) -> Data? {
        var base64 = string
            .replacingOccurrences(of: "-", with: "+")
            .replacingOccurrences(of: "_", with: "/")
        // Pad to multiple of 4
        let remainder = base64.count % 4
        if remainder > 0 {
            base64 += String(repeating: "=", count: 4 - remainder)
        }
        return Data(base64Encoded: base64)
    }
}

// MARK: - ASAuthorizationControllerDelegate

extension AuthManager: ASAuthorizationControllerDelegate {
    nonisolated func authorizationController(
        controller: ASAuthorizationController,
        didCompleteWithAuthorization authorization: ASAuthorization
    ) {
        Task { @MainActor in
            if let registration = authorization.credential as? ASAuthorizationPlatformPublicKeyCredentialRegistration {
                registrationContinuation?.resume(returning: registration)
                registrationContinuation = nil
            } else if let assertion = authorization.credential as? ASAuthorizationPlatformPublicKeyCredentialAssertion {
                authenticationContinuation?.resume(returning: assertion)
                authenticationContinuation = nil
            }
        }
    }

    nonisolated func authorizationController(
        controller: ASAuthorizationController,
        didCompleteWithError error: Error
    ) {
        Task { @MainActor in
            registrationContinuation?.resume(throwing: error)
            registrationContinuation = nil
            authenticationContinuation?.resume(throwing: error)
            authenticationContinuation = nil
        }
    }
}

// MARK: - Errors

enum AuthError: LocalizedError {
    case invalidOptions

    var errorDescription: String? {
        switch self {
        case .invalidOptions: return "Invalid authentication options from server"
        }
    }
}
