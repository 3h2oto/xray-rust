#if DEBUG && (os(iOS) || os(tvOS))
import Foundation
@preconcurrency import NetworkExtension
import SwiftUI
import UIKit
import XrayAppleShared
import XrayMobileAdapter

@available(iOS 15.0, tvOS 17.0, *)
public struct XrayStartupProbeDeviceCheckView: View {
    @State private var status = "Preparing startup probe checks…"

    public init() {}

    public var body: some View {
        VStack(spacing: 16) {
            Text("Xray #69 device check").font(.headline)
            Text(verbatim: status).multilineTextAlignment(.center)
        }
        .padding()
        .task { await XrayStartupProbeDeviceCheck().run { status = $0 } }
    }
}

/// Opt-in physical-device check. Uses only its own VPN manager and config key.
/// The fixture supplies a controlled HTTP server with delayed probe responses.
@MainActor
@available(iOS 15.0, tvOS 17.0, *)
final class XrayStartupProbeDeviceCheck {
    private struct Fixture: Decodable {
        let baseURL: URL
        let trafficURL: URL
        let configJSON: String?
    }
    private enum Failure: Error { case fixture, startup, connectivity, shutdown }
    private let managerName = "Xray #69 Startup Probe Check"
    #if os(tvOS)
    private let documents = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
    #else
    private let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
    #endif
    private let store = XrayKeychainConfigStore()
    private let reference = "issue69.\(UUID().uuidString)"
    private var rows: [[String: Any]] = []
    private var phase = "setup"

    func run(update: (String) -> Void) async {
        let priorIdleTimer = UIApplication.shared.isIdleTimerDisabled
        UIApplication.shared.isIdleTimerDisabled = true
        defer { UIApplication.shared.isIdleTimerDisabled = priorIdleTimer }
        var manager: NETunnelProviderManager?
        var passed = false
        do {
            let input = documents.appendingPathComponent("issue69-probe.json")
            guard (try input.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0) < 16_384 else { throw Failure.fixture }
            let fixture = try JSONDecoder().decode(Fixture.self, from: Data(contentsOf: input))
            guard fixture.baseURL.scheme == "http", fixture.baseURL.host != nil,
                  fixture.trafficURL.scheme == "https" else { throw Failure.fixture }
            let info = XrayCore.ffiInfo
            emit(["event": "device", "systemVersion": UIDevice.current.systemVersion,
                  "abiMajor": info.version.major, "abiMinor": info.version.minor])
            let configJSON = fixture.configJSON ?? #"{"inbounds":[{"tag":"tun-in","protocol":"tun"}],"dns":{"servers":["1.1.1.1","8.8.8.8"]},"outbounds":[{"tag":"direct","protocol":"freedom"}]}"#
            if fixture.configJSON != nil {
                guard let root = try JSONSerialization.jsonObject(with: Data(configJSON.utf8)) as? [String: Any],
                      let outbounds = root["outbounds"] as? [[String: Any]], outbounds.count == 1,
                      let outbound = outbounds.first, outbound["protocol"] as? String == "vless",
                      let stream = outbound["streamSettings"] as? [String: Any], stream["security"] as? String == "reality",
                      let settings = outbound["settings"] as? [String: Any],
                      let servers = settings["vnext"] as? [[String: Any]], let server = servers.first,
                      let users = server["users"] as? [[String: Any]],
                      users.first?["flow"] as? String == "xtls-rprx-vision" else { throw Failure.fixture }
                emit(["event": "transport", "protocol": "vless", "security": "reality", "flow": "xtls-rprx-vision"])
            } else {
                emit(["event": "transport", "protocol": "freedom"])
            }
            let managers = try await NETunnelProviderManager.loadAllFromPreferences()
            for previous in managers where previous.localizedDescription == managerName {
                previous.connection.stopVPNTunnel()
                try await disconnected(previous)
                try await previous.removeFromPreferences()
            }
            let created = NETunnelProviderManager()
            manager = created
            let configuration = NETunnelProviderProtocol()
            configuration.providerBundleIdentifier = XrayClientProfile.defaultProviderBundleIdentifier(
                hostBundleIdentifier: Bundle.main.bundleIdentifier)
            configuration.serverAddress = "Startup probe device check"
            configuration.providerConfiguration = [
                XrayTunnelProviderMessage.providerConfigReferenceKey: reference,
                XrayTunnelProviderMessage.providerDebugLoggingKey: true,
            ]
            try store.store(configJSON: configJSON, reference: reference)
            created.protocolConfiguration = configuration
            created.localizedDescription = managerName
            created.isEnabled = true
            try await created.saveToPreferences()
            try await created.loadFromPreferences()
            let sessionConfiguration = URLSessionConfiguration.ephemeral
            sessionConfiguration.timeoutIntervalForRequest = 2
            sessionConfiguration.timeoutIntervalForResource = 3
            sessionConfiguration.urlCache = nil
            let client = URLSession(configuration: sessionConfiguration)
            defer { client.invalidateAndCancel() }

            // Each enabled probe holds connecting for several seconds. Sample
            // app-side HTTPS throughout, including the system DNS anchor path.
            for scenario in ["success", "failure", "timeout", "cancel", "disabled"] {
                phase = scenario + ":baseline"
                update("#69: \(scenario)")
                guard await request(client, url: fixture.trafficURL, manager: created) else { throw Failure.connectivity }
                let firstRow = rows.count
                let monitor = Task {
                    while !Task.isCancelled {
                        _ = await self.request(client, url: fixture.trafficURL, manager: created)
                        try? await Task.sleep(nanoseconds: 500_000_000)
                    }
                }
                let started = ProcessInfo.processInfo.systemUptime
                phase = scenario + ":connecting"
                guard let session = created.connection as? NETunnelProviderSession else { throw Failure.startup }
                let url = fixture.baseURL.appendingPathComponent(scenario)
                do {
                    try session.startTunnel(options: [
                        XrayTunnelProviderMessage.startupProbeEnabledOptionKey: NSNumber(value: scenario != "disabled"),
                        XrayTunnelProviderMessage.startupProbeURLOptionKey: url.absoluteString as NSString,
                        XrayTunnelProviderMessage.startupProbeTimeoutMsOptionKey: NSNumber(value: scenario == "timeout" ? 5_000 : 10_000),
                    ])
                    let connected: Bool
                    if scenario == "cancel" {
                        try await Task.sleep(nanoseconds: 2_000_000_000)
                        created.connection.stopVPNTunnel()
                        try await disconnected(created)
                        connected = false
                    } else {
                        connected = try await startupResult(created)
                    }
                    let seconds = ProcessInfo.processInfo.systemUptime - started
                    phase = scenario + ":after-start"
                    try await Task.sleep(nanoseconds: 1_000_000_000)
                    monitor.cancel()
                    await monitor.value
                    let samples = rows.dropFirst(firstRow).filter { $0["event"] as? String == "request" }
                    let failures = samples.filter { $0["result"] as? String == "failed" }
                    let connectingSuccesses = samples.filter {
                        $0["phase"] as? String == scenario + ":connecting" && $0["result"] as? String == "passed"
                    }.count
                    emit(["event": "scenario", "scenario": scenario, "connected": connected,
                          "seconds": seconds, "samples": samples.count, "failures": failures.count,
                          "connectingSuccesses": connectingSuccesses])
                    guard connected == (scenario == "success" || scenario == "disabled"), failures.isEmpty else {
                        throw Failure.connectivity
                    }
                    if scenario == "success" || scenario == "failure" || scenario == "timeout" {
                        guard seconds >= 4, connectingSuccesses >= 2 else { throw Failure.startup }
                    }
                    if connected {
                        phase = scenario + ":fresh-dns"
                        guard await request(client, url: URL(string: "https://www.example.com/")!, manager: created) else {
                            throw Failure.connectivity
                        }
                    }
                } catch {
                    monitor.cancel()
                    await monitor.value
                    throw error
                }
                created.connection.stopVPNTunnel()
                try await disconnected(created)
                try await Task.sleep(nanoseconds: 500_000_000)
            }
            passed = true
        } catch {
            let error = error as NSError
            emit(["event": "failure", "domain": error.domain, "code": error.code])
        }
        if let manager {
            manager.connection.stopVPNTunnel()
            do {
                try await disconnected(manager)
                try await manager.removeFromPreferences()
            } catch { passed = false; emit(["event": "cleanup", "result": "failed"]) }
        }
        try? store.remove(reference: reference)
        try? FileManager.default.removeItem(at: documents.appendingPathComponent("issue69-probe.json"))
        emit(["event": "complete", "result": passed ? "passed" : "failed"])
        update(passed ? "#69 checks passed; test VPN removed." : "#69 check failed; see issue69-result.json.")
    }

    private func startupResult(_ manager: NETunnelProviderManager) async throws -> Bool {
        let deadline = ProcessInfo.processInfo.systemUptime + 20
        var sawConnecting = false
        while ProcessInfo.processInfo.systemUptime < deadline {
            let status = manager.connection.status
            if status == .connected { return true }
            if status == .connecting { sawConnecting = true }
            if sawConnecting, status == .disconnected || status == .invalid { return false }
            try await Task.sleep(nanoseconds: 50_000_000)
        }
        throw Failure.startup
    }

    private func disconnected(_ manager: NETunnelProviderManager) async throws {
        for _ in 0..<100 {
            if manager.connection.status == .disconnected || manager.connection.status == .invalid { return }
            try await Task.sleep(nanoseconds: 100_000_000)
        }
        throw Failure.shutdown
    }

    private func request(_ client: URLSession, url: URL, manager: NETunnelProviderManager) async -> Bool {
        let started = ProcessInfo.processInfo.systemUptime
        let requestPhase = phase
        do {
            var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData)
            request.setValue("close", forHTTPHeaderField: "Connection")
            let (_, response) = try await client.data(for: request)
            guard let http = response as? HTTPURLResponse, (200..<400).contains(http.statusCode) else { throw Failure.connectivity }
            emit(["event": "request", "phase": requestPhase, "result": "passed",
                  "status": manager.connection.status.rawValue, "seconds": ProcessInfo.processInfo.systemUptime - started])
            return true
        } catch {
            if Task.isCancelled { return false }
            let error = error as NSError
            emit(["event": "request", "phase": requestPhase, "result": "failed", "domain": error.domain,
                  "code": error.code, "status": manager.connection.status.rawValue,
                  "seconds": ProcessInfo.processInfo.systemUptime - started])
            return false
        }
    }

    private func emit(_ values: [String: Any]) {
        var row = values
        row["time"] = ISO8601DateFormatter().string(from: Date())
        rows.append(row)
        if let data = try? JSONSerialization.data(withJSONObject: row, options: [.sortedKeys]),
           let line = String(data: data, encoding: .utf8) { print("XRAY_ISSUE69_DEVICE \(line)") }
        if let data = try? JSONSerialization.data(withJSONObject: rows, options: [.prettyPrinted, .sortedKeys]) {
            try? data.write(to: documents.appendingPathComponent("issue69-result.json"), options: [.atomic, .completeFileProtectionUnlessOpen])
        }
    }
}
#endif
