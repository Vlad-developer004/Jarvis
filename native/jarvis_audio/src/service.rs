//! `--serve`: one JSON request per line on stdin, one JSON answer per line on stdout. The Python core starts it once and keeps it.
//! When stdin closes (the core exited or crashed) the loop ends and `Audio::drop` gives every lowered volume back.
use serde_json::{json, Value};
use std::io::{BufRead, Write};

use crate::clips;
use crate::player::Player;
#[cfg(windows)]
use crate::volume::Audio;

fn f32_of(req: &Value, key: &str) -> Option<f32> {
    req.get(key).and_then(Value::as_f64).map(|v| v as f32)
}

/// Playback operations; `None` when `op` is not one of them.
fn playback(player: &Player, op: &str, req: &Value) -> Option<Value> {
    let gain = f32_of(req, "volume").unwrap_or(1.0).clamp(0.0, 4.0); // above 1 boosts (the mix is limited at the end)
    let sfx = req.get("channel").and_then(Value::as_str) == Some("sfx");
    let queue = |clip: Result<crate::player::Clip, String>| match clip {
        Ok(c) => {
            let seconds = c.seconds();
            if sfx {
                player.play_sfx(c);
            } else {
                player.play_tts(c);
            }
            json!({"ok": true, "seconds": seconds})
        }
        Err(e) => json!({"ok": false, "error": e}),
    };
    Some(match op {
        "play" => match req.get("path").and_then(Value::as_str) {
            Some(path) => queue(clips::from_file(path, gain)),
            None => json!({"ok": false, "error": "play needs path"}),
        },
        "play_pcm" => match req.get("data").and_then(Value::as_str) {
            Some(data) => {
                let channels = req.get("channels").and_then(Value::as_u64).unwrap_or(2) as usize;
                let rate = req.get("rate").and_then(Value::as_u64).unwrap_or(44100) as u32;
                queue(clips::from_pcm16_b64(data, channels, rate, gain))
            }
            None => json!({"ok": false, "error": "play_pcm needs data"}),
        },
        "stop" => {
            let which = req.get("channel").and_then(Value::as_str).unwrap_or("all");
            player.stop(which != "sfx", which != "tts");
            json!({"ok": true})
        }
        "player_status" => {
            let s = player.status();
            json!({"ok": true, "busy": s.busy, "queued": s.queued, "remaining": s.remaining, "ready": s.info.ready, "device": s.info.device,
                   "rate": s.info.rate, "channels": s.info.channels, "rebuilds": s.info.rebuilds, "error": s.info.last_error})
        }
        _ => return None,
    })
}

#[cfg(windows)]
fn handle(audio: &mut Audio, player: &Player, req: &Value) -> Value {
    let op = req.get("op").and_then(Value::as_str).unwrap_or("");
    if let Some(v) = playback(player, op, req) {
        return v;
    }
    match op {
        "ping" => json!({"ok": true, "version": env!("CARGO_PKG_VERSION")}),
        "sessions" => audio.list(),
        "duck" => {
            let enable = req.get("enable").and_then(Value::as_bool).unwrap_or(true);
            audio.duck(enable, req.get("skip_pid").and_then(Value::as_u64).unwrap_or(0) as u32)
        }
        "unduck" => audio.unduck(),
        "set_app" => match (req.get("name").and_then(Value::as_str), f32_of(req, "level")) {
            (Some(name), Some(level)) => audio.set_app(name, level),
            _ => json!({"ok": false, "error": "set_app needs name and level"}),
        },
        "set_session" => match (req.get("session").and_then(Value::as_str), f32_of(req, "level")) {
            (Some(id), Some(level)) => audio.set_session(id, level),
            _ => json!({"ok": false, "error": "set_session needs session and level"}),
        },
        "master_get" => audio.master_get(),
        "master_set" => audio.master_set(f32_of(req, "level"), req.get("muted").and_then(Value::as_bool)),
        other => json!({"ok": false, "error": format!("unknown op: {other}")}),
    }
}

#[cfg(windows)]
pub fn run() {
    let mut audio = Audio::new();
    let player = Player::new();
    let stdin = std::io::stdin();
    let mut out = std::io::stdout().lock();
    for line in stdin.lock().lines() {
        let Ok(line) = line else { break };
        if line.trim().is_empty() {
            continue;
        }
        let answer = match serde_json::from_str::<Value>(&line) {
            Ok(req) => {
                let mut a = handle(&mut audio, &player, &req);
                if let (Some(id), Some(obj)) = (req.get("id"), a.as_object_mut()) {
                    obj.insert("id".into(), id.clone()); // lets the client match answers to requests
                }
                a
            }
            Err(e) => json!({"ok": false, "error": format!("bad json: {e}")}),
        };
        if writeln!(out, "{answer}").and_then(|_| out.flush()).is_err() {
            break;
        }
    }
}

#[cfg(not(windows))]
pub fn run() {
    println!("{}", json!({"ok": false, "error": "unsupported platform"}));
}
