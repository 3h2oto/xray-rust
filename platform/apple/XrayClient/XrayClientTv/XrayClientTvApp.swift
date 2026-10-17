import SwiftUI
import XrayAppleClient

@main
struct XrayClientTVApp: App {
    var body: some Scene {
        WindowGroup {
            if #available(tvOS 17.0, *) {
                #if DEBUG
                if ProcessInfo.processInfo.environment["XRAY_STARTUP_PROBE_DEVICE_CHECK"] == "1" {
                    XrayStartupProbeDeviceCheckView()
                } else {
                    XrayClientRootView()
                }
                #else
                XrayClientRootView()
                #endif
            } else {
                Text("Unsupported OS")
            }
        }
    }
}
