// towerwin — the native window Tower.app opens, and the owner of the server
// behind it.
//
// Compiled from source by build_towerapp.sh into the bundle; never committed
// as a binary, same philosophy as finance-tracker's docr.swift/askm.swift.
//
// Why Swift and not pywebview: the Tower is deliberately stdlib-Python with no
// dependencies (concept 07), and pywebview is not installed on this machine.
// A ~200-line AppKit shim keeps that property intact — the .app adds a window,
// not a dependency.
//
// This process OWNS the server rather than merely pointing at one:
//
//   * it picks a free port, spawns `python3 bin/tower --port N` as a child, and
//     waits for it to answer before showing anything;
//   * it terminates that child on quit, on window close, and on SIGINT/SIGTERM.
//     "Leave nothing running" is therefore structural, not a habit — there is
//     no path where the window goes away and the server survives, because the
//     server is this process's child and gets killed in applicationWillTerminate.
//
// Loopback is not configurable here on purpose: bin/tower binds 127.0.0.1
// unconditionally and takes no host flag, and this shim passes only --port. The
// window renders private session data, so there is deliberately no way to widen
// the bind from inside the wrapper.

import Cocoa
import WebKit

// --- where the repo and the interpreter are -------------------------------
// Written into Contents/Resources at build time rather than compiled in, so the
// binary stays generic and the paths are inspectable in a built bundle.
func resource(_ name: String) -> String? {
    guard let url = Bundle.main.url(forResource: name, withExtension: nil),
          let raw = try? String(contentsOf: url, encoding: .utf8) else { return nil }
    let value = raw.trimmingCharacters(in: .whitespacesAndNewlines)
    return value.isEmpty ? nil : value
}

func logLine(_ message: String) {
    let logDir = ("~/Library/Logs" as NSString).expandingTildeInPath
    let path = logDir + "/Tower.log"
    let stamp = ISO8601DateFormatter().string(from: Date())
    let line = "\(stamp) \(message)\n"
    if let data = line.data(using: .utf8) {
        if let handle = FileHandle(forWritingAtPath: path) {
            handle.seekToEndOfFile()
            handle.write(data)
            try? handle.close()
        } else {
            try? data.write(to: URL(fileURLWithPath: path))
        }
    }
    FileHandle.standardError.write(line.data(using: .utf8)!)
}

func die(_ message: String) -> Never {
    logLine("fatal: \(message)")
    let alert = NSAlert()
    alert.messageText = "Tower could not start"
    alert.informativeText = message + "\n\nDetails in ~/Library/Logs/Tower.log"
    alert.alertStyle = .critical
    alert.runModal()
    exit(1)
}

/// A port the OS says is free right now. Asked for rather than guessed, so a
/// Tower already running on 8890 from a terminal session does not collide with
/// the one the Dock opens.
func freePort() -> Int {
    let sock = socket(AF_INET, SOCK_STREAM, 0)
    guard sock >= 0 else { return 8890 }
    defer { close(sock) }
    var addr = sockaddr_in()
    addr.sin_family = sa_family_t(AF_INET)
    addr.sin_port = 0                                    // 0 = "assign me one"
    addr.sin_addr.s_addr = inet_addr("127.0.0.1")
    var reuse: Int32 = 1
    setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, &reuse, socklen_t(MemoryLayout<Int32>.size))
    let bound = withUnsafePointer(to: &addr) {
        $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
            bind(sock, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
        }
    }
    guard bound == 0 else { return 8890 }
    var out = sockaddr_in()
    var len = socklen_t(MemoryLayout<sockaddr_in>.size)
    let got = withUnsafeMutablePointer(to: &out) {
        $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { getsockname(sock, $0, &len) }
    }
    guard got == 0 else { return 8890 }
    return Int(UInt16(bigEndian: out.sin_port))
}

final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    var window: NSWindow!
    var webView: WKWebView!
    var server: Process?
    var port: Int = 0

    func applicationDidFinishLaunching(_ note: Notification) {
        guard let repo = resource("repo_path") else { die("repo_path missing from the bundle") }
        guard let python = resource("python_path") else { die("python_path missing from the bundle") }
        let tower = repo + "/bin/tower"
        guard FileManager.default.fileExists(atPath: tower) else {
            die("bin/tower not found at \(tower).\nThe app launches the Tower in this repo; if the repo moved, rebuild with ./build_towerapp.sh")
        }
        guard FileManager.default.isExecutableFile(atPath: python) else {
            die("python3 not executable at \(python)")
        }

        port = freePort()
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: python)
        proc.arguments = [tower, "--port", String(port)]
        proc.currentDirectoryURL = URL(fileURLWithPath: repo)
        // Whether this child registers with apprun depends on how the app was
        // launched, and both outcomes are the right one:
        //
        //   * Double-clicked from the Dock — the normal case — there is no
        //     CLAUDE_CODE_SESSION_ID in the environment, so bin/tower skips
        //     registration by its own rule (apprun refuses ownerless entries).
        //     Correct: this server belongs to a Dock app, and an entry no
        //     session owns is the exact "orphan" apprun exists to surface.
        //
        //   * Launched from an agent session's shell (`open -a Tower` inside a
        //     task), macOS propagates that shell's environment to the app, the
        //     session id comes with it, and the server registers owned by that
        //     session. Also correct — that session stops what it started, and
        //     the entry deregisters on quit.
        //
        // An earlier version of this comment claimed the first case
        // unconditionally. It was wrong, and wrong in the direction that
        // matters: the first real install was launched from a session shell,
        // registered under it, and would have looked like an orphan once that
        // session ended. Measured both ways on 2026-08-06 rather than reasoned
        // about — `ps eww` on the child, and apprun list before and after quit.
        let log = FileHandle(forWritingAtPath: ("~/Library/Logs/Tower.log" as NSString).expandingTildeInPath)
        if let log = log {
            log.seekToEndOfFile()
            proc.standardOutput = log
            proc.standardError = log
        }
        do { try proc.run() } catch { die("could not start bin/tower: \(error.localizedDescription)") }
        server = proc
        logLine("started bin/tower pid \(proc.processIdentifier) on 127.0.0.1:\(port)")

        // Kill the child even on signals, so a Force Quit or a terminal ^C does
        // not strand a bound port. NSApp.terminate runs the delegate hook below.
        for sig in [SIGINT, SIGTERM] {
            signal(sig, SIG_IGN)
            let src = DispatchSource.makeSignalSource(signal: sig, queue: .main)
            src.setEventHandler { NSApp.terminate(nil) }
            src.resume()
            signalSources.append(src)
        }

        buildWindow()
        waitForServerThenLoad()
    }

    var signalSources: [DispatchSourceSignal] = []

    func buildWindow() {
        let config = WKWebViewConfiguration()
        webView = WKWebView(frame: .zero, configuration: config)
        webView.setValue(false, forKey: "drawsBackground")

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1280, height: 900),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "Tower"
        window.setFrameAutosaveName("TowerWindow")
        window.contentView = webView
        window.delegate = self
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    /// Poll the child until it serves, then load. Without this the window shows
    /// a connection error for the second or two the Python server takes to bind,
    /// which reads as "the app is broken" on every single launch.
    func waitForServerThenLoad(attempt: Int = 0) {
        let url = URL(string: "http://127.0.0.1:\(port)/")!
        var probe = URLRequest(url: url)
        probe.httpMethod = "HEAD"
        probe.timeoutInterval = 1.5
        URLSession.shared.dataTask(with: probe) { _, response, _ in
            DispatchQueue.main.async {
                if (response as? HTTPURLResponse) != nil {
                    self.webView.load(URLRequest(url: url))
                    return
                }
                if self.server?.isRunning != true {
                    die("bin/tower exited before serving. See ~/Library/Logs/Tower.log")
                }
                if attempt >= 40 {                        // 40 × 0.25s = 10s
                    die("bin/tower did not answer on 127.0.0.1:\(self.port) within 10s")
                }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) {
                    self.waitForServerThenLoad(attempt: attempt + 1)
                }
            }
        }.resume()
    }

    // Closing the window quits the app. A Tower with no window is a server with
    // no reason to be up, and leaving it running is the thing this is for.
    func applicationShouldTerminateAfterLastWindowClosed(_ app: NSApplication) -> Bool { true }

    func applicationWillTerminate(_ note: Notification) {
        guard let proc = server, proc.isRunning else { return }
        proc.terminate()                                   // SIGTERM
        // bin/tower handles SIGTERM and deregisters/exits; give it a moment,
        // then insist. Never leave the port bound.
        let deadline = Date().addingTimeInterval(3)
        while proc.isRunning && Date() < deadline { usleep(50_000) }
        if proc.isRunning { kill(proc.processIdentifier, SIGKILL) }
        logLine("stopped bin/tower")
    }
}

// --- exactly one copy -----------------------------------------------------
// macOS already activates a running app when its Dock icon is clicked, but
// `open -n` and a stray double-launch can still start a second. A second copy
// would bind a second port and show a second window over the same data, which
// is the "which window am I looking at" problem the run rules exist to prevent.
let me = Bundle.main.bundleIdentifier ?? "local.tower"
let others = NSRunningApplication.runningApplications(withBundleIdentifier: me)
    .filter { $0.processIdentifier != ProcessInfo.processInfo.processIdentifier }
if let existing = others.first {
    existing.activate(options: [.activateAllWindows])
    exit(0)
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let delegate = AppDelegate()
app.delegate = delegate
app.run()
