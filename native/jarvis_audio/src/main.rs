//! jarvis_audio: sidecar for audio helpers (see docs/native.md). Started by the Python core.
//!
//! Commands:
//!   --version        print the version
//!   --query-output   describe the default playback device: {"ok", "name", "kind", "is_headphones", ...}
//!   --serve          line-based JSON service: volume (sessions, duck, unduck, set_app, set_session, master_get, master_set)
//!                    and playback (play, play_pcm, stop, player_status)
//!   --list-devices   input and output devices by name
//!   --capture --rate R --chunk N [--device NAME]   microphone as mono 16-bit PCM frames on stdout (see capture.rs)
//!   --selftest-playback   play a quiet tone and record it back from the output device (loopback), report dropouts and pitch
mod capture;
mod clips;
mod devices;
mod duck;
mod endpoint;
mod player;
mod resample;
mod selftest;
mod service;
#[cfg(windows)]
mod volume;

fn main() {
    match std::env::args().nth(1).unwrap_or_default().as_str() {
        "--version" => println!("{}", env!("CARGO_PKG_VERSION")),
        "--query-output" => {
            let out = endpoint::query_output();
            println!("{out}");
            if out["ok"] != true {
                std::process::exit(1);
            }
        }
        "--serve" => service::run(),
        "--list-devices" => println!("{}", devices::list()),
        "--capture" => {
            let args: Vec<String> = std::env::args().skip(2).collect();
            let get = |flag: &str| args.iter().position(|a| a == flag).and_then(|i| args.get(i + 1)).cloned();
            let rate = get("--rate").and_then(|v| v.parse().ok()).unwrap_or(16000);
            let chunk = get("--chunk").and_then(|v| v.parse().ok()).unwrap_or(512);
            capture::run(get("--device").filter(|d| !d.is_empty()), rate, chunk);
        }
        "--analyse-loopback" => {
            let ms = std::env::args().nth(2).and_then(|v| v.parse().ok()).unwrap_or(3000);
            println!("{}", selftest::listen(ms));
        }
        "--selftest-playback" => {
            let out = selftest::run();
            println!("{out}");
            if out["ok"] != true {
                std::process::exit(1);
            }
        }
        _ => {
            eprintln!("jarvis_audio: unknown command (use --version, --query-output or --serve)");
            std::process::exit(2);
        }
    }
}
