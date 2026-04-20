import SwiftUI

enum MoreRoute: Hashable {
    case upload
    case premarket
    case status
    case settings
}

struct MoreView: View {
    @EnvironmentObject private var config: AppConfig
    @Binding var path: NavigationPath

    private var appVersion: String {
        let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
        let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1"
        return "\(version) · build \(build)"
    }

    var body: some View {
        NavigationStack(path: $path) {
            MobileScreen {
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        MobileKickerTitle(kicker: "TFSA", title: "More")

                        MobileSectionLabel("Tools")

                        MobileCard {
                            MoreRow(icon: "square.and.arrow.up", title: "Upload screenshot") {
                                path.append(MoreRoute.upload)
                            }
                            Divider().overlay(Theme.line)
                            MoreRow(icon: "sun.max", title: "Pre-market") {
                                path.append(MoreRoute.premarket)
                            }
                            Divider().overlay(Theme.line)
                            MoreRow(icon: "waveform.path.ecg", title: "System status") {
                                path.append(MoreRoute.status)
                            }
                            Divider().overlay(Theme.line)
                            MoreRow(icon: "gearshape", title: "Settings") {
                                path.append(MoreRoute.settings)
                            }
                        }

                        MobileSectionLabel("Account")

                        MobileCard {
                            MobileDefRow(label: "API server") {
                                MobileValueLabel(text: (config.apiBaseURL ?? "Not set").replacingOccurrences(of: "https://", with: ""))
                            }
                            Divider().overlay(Theme.line)
                            MobileDefRow(label: "Version") {
                                MobileValueLabel(text: appVersion)
                            }
                            Divider().overlay(Theme.line)
                            MobileDefRow(label: "Account type") {
                                MobileValueLabel(text: "TFSA")
                            }
                        }
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 10)
                    .padding(.bottom, 140)
                }
            }
            .navigationBarHidden(true)
            .navigationDestination(for: MoreRoute.self) { route in
                switch route {
                case .upload:
                    UploadView()
                case .premarket:
                    PreMarketView()
                case .status:
                    StatusView()
                case .settings:
                    SettingsView()
                }
            }
        }
    }
}

private struct MoreRow: View {
    let icon: String
    let title: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 14) {
                RoundedRectangle(cornerRadius: 7)
                    .fill(Theme.brand.opacity(0.12))
                    .frame(width: 28, height: 28)
                    .overlay(
                        Image(systemName: icon)
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundStyle(Theme.brand)
                    )
                Text(title)
                    .font(.system(size: 16, weight: .medium))
                    .foregroundStyle(Theme.textPrimary)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(Theme.textDimmed)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 16)
        }
        .buttonStyle(.plain)
    }
}
