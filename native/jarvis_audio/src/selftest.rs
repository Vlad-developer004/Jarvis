//! `--selftest-playback`: play a quiet 440 Hz tone through the real player and record it back from the output device (WASAPI loopback),
//! then report whether it arrived whole: when it started, how long it lasted, whether it had dropouts and which pitch it had.
//! This is how the playback path is checked without anyone listening.
use crate::player::{Clip, Player};
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{Error, FromSample, Sample, SampleFormat, SizedSample};
use serde_json::{json, Value};
use std::sync::{Arc, Mutex};
use std::time::Duration;

const TONE_HZ: f32 = 440.0;
const TONE_RATE: u32 = 24000; // a rate the device does not use, so the resampler is part of the test
const TONE_MS: u64 = 1200;
/// The recorder must not be the weak link when the machine is busy: run it at high priority.
#[cfg(windows)]
fn prioritise() {
    use windows::Win32::System::Threading::{GetCurrentProcess, SetPriorityClass, HIGH_PRIORITY_CLASS};
    let _ = unsafe { SetPriorityClass(GetCurrentProcess(), HIGH_PRIORITY_CLASS) };
}

#[cfg(not(windows))]
fn prioritise() {}

fn record<T>(device: &cpal::Device, config: cpal::StreamConfig, sink: Arc<Mutex<Vec<f32>>>) -> Result<cpal::Stream, Error>
where
    T: SizedSample,
    f32: FromSample<T>,
{
    let channels = config.channels as usize;
    device.build_input_stream(
        config,
        move |data: &[T], _| {
            let mut v = sink.lock().unwrap();
            for frame in data.chunks(channels) {
                v.push(frame.iter().map(|s| f32::from_sample(*s)).sum::<f32>() / channels as f32);
            }
        },
        |_err: Error| {},
        None,
    )
}

pub struct Analysis {
    pub onset_ms: f64,
    pub span_ms: f64,
    /// Windows inside the tone where the 440 Hz component fell below half its normal level (the output went quiet).
    pub dropouts: usize,
    pub freq_hz: f64,
    pub peak_rms: f32,
    /// Windows inside the tone where the phase of the 440 Hz component jumped: samples were skipped or repeated, even without silence.
    pub glitches: usize,
}

/// Lock-in analysis at TONE_HZ over 5 ms windows: amplitude and phase of exactly the tone that was played, so other sounds on the machine
/// (music in a browser, notifications) hardly disturb the verdict.
pub fn analyse(x: &[f32], rate: u32) -> Option<Analysis> {
    let n = (rate as usize * 5 / 1000).max(8);
    let w = std::f64::consts::TAU * TONE_HZ as f64 / rate as f64;
    let mut amp = Vec::new();
    let mut phase = Vec::new();
    for (k, win) in x.chunks(n).enumerate().filter(|(_, c)| c.len() == n) {
        let (mut i, mut q) = (0.0f64, 0.0f64);
        for (j, v) in win.iter().enumerate() {
            let t = (k * n + j) as f64 * w;
            i += *v as f64 * t.cos();
            q += *v as f64 * t.sin();
        }
        amp.push(2.0 * (i * i + q * q).sqrt() / n as f64);
        phase.push(q.atan2(i));
    }
    let peak = amp.iter().cloned().fold(0.0f64, f64::max);
    if peak < 1e-3 {
        return None;
    }
    let first = amp.iter().position(|a| *a > peak * 0.5)?;
    let last = amp.iter().rposition(|a| *a > peak * 0.5)?;
    // judge the middle of the tone: the first and last 15 ms are its attack and decay
    let (from, to) = if last > first + 8 { (first + 3, last - 2) } else { (first, last) };
    let mut sorted: Vec<f64> = amp[from..=to].to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let median = sorted[sorted.len() / 2];
    let dropouts = amp[from..=to].iter().filter(|a| **a < median * 0.5).count();
    let mut glitches = 0;
    let mut drift = 0.0;
    for k in from + 1..=to {
        let mut d = phase[k] - phase[k - 1];
        while d > std::f64::consts::PI {
            d -= std::f64::consts::TAU;
        }
        while d < -std::f64::consts::PI {
            d += std::f64::consts::TAU;
        }
        drift += d;
        if d.abs() > 0.6 {
            glitches += 1;
        }
    }
    let span_s = (to - from) as f64 * n as f64 / rate as f64;
    let freq = TONE_HZ as f64 + if span_s > 0.0 { drift / std::f64::consts::TAU / span_s } else { 0.0 };
    let ms = |k: usize| k as f64 * n as f64 * 1000.0 / rate as f64;
    Some(Analysis { onset_ms: ms(first), span_ms: ms(last - first + 1), dropouts, freq_hz: freq, peak_rms: (peak / std::f64::consts::SQRT_2) as f32, glitches })
}

/// `--analyse-loopback <ms>`: only record the output device for `ms` and analyse it. Another program plays the tone meanwhile.
pub fn listen(ms: u64) -> Value {
    prioritise();
    let host = cpal::default_host();
    let Some(device) = host.default_output_device() else { return json!({"ok": false, "error": "no output device"}) };
    let Ok(supported) = device.default_output_config() else { return json!({"ok": false, "error": "no output config"}) };
    let rate = supported.sample_rate();
    let format = supported.sample_format();
    let config: cpal::StreamConfig = supported.into();
    let sink = Arc::new(Mutex::new(Vec::<f32>::new()));
    let stream = match format {
        SampleFormat::F32 => record::<f32>(&device, config, Arc::clone(&sink)),
        SampleFormat::I16 => record::<i16>(&device, config, Arc::clone(&sink)),
        SampleFormat::I32 => record::<i32>(&device, config, Arc::clone(&sink)),
        other => return json!({"ok": false, "error": format!("loopback format {other} not supported")}),
    };
    let Ok(stream) = stream else { return json!({"ok": false, "error": "loopback capture could not start"}) };
    if stream.play().is_err() {
        return json!({"ok": false, "error": "loopback capture could not play"});
    }
    std::thread::sleep(Duration::from_millis(ms));
    drop(stream);
    let rec = sink.lock().unwrap().clone();
    let seconds = rec.len() as f64 / rate as f64;
    match analyse(&rec, rate) {
        Some(a) => json!({"ok": true, "recorded_s": seconds, "onset_ms": a.onset_ms, "span_ms": a.span_ms, "dropouts": a.dropouts, "glitches": a.glitches, "freq_hz": a.freq_hz, "peak_rms": a.peak_rms}),
        None => json!({"ok": false, "error": "nothing was heard on the output device", "recorded_s": seconds}),
    }
}

pub fn run() -> Value {
    let player = Player::new();
    if !player.wait_ready(Duration::from_secs(3)) {
        return json!({"ok": false, "error": "output stream did not open"});
    }
    let host = cpal::default_host();
    let Some(device) = host.default_output_device() else { return json!({"ok": false, "error": "no output device"}) };
    let Ok(supported) = device.default_output_config() else { return json!({"ok": false, "error": "no output config"}) };
    let rate = supported.sample_rate();
    let format = supported.sample_format();
    let config: cpal::StreamConfig = supported.into();
    let sink = Arc::new(Mutex::new(Vec::<f32>::new()));
    let stream = match format {
        SampleFormat::F32 => record::<f32>(&device, config, Arc::clone(&sink)),
        SampleFormat::I16 => record::<i16>(&device, config, Arc::clone(&sink)),
        SampleFormat::I32 => record::<i32>(&device, config, Arc::clone(&sink)),
        other => return json!({"ok": false, "error": format!("loopback format {other} not supported")}),
    };
    let Ok(stream) = stream else { return json!({"ok": false, "error": "loopback capture could not start"}) };
    if stream.play().is_err() {
        return json!({"ok": false, "error": "loopback capture could not play"});
    }
    std::thread::sleep(Duration::from_millis(300));
    let frames = (TONE_RATE as u64 * TONE_MS / 1000) as usize;
    let tone: Vec<f32> = (0..frames).map(|i| (i as f32 * TONE_HZ * std::f32::consts::TAU / TONE_RATE as f32).sin() * 0.25).collect();
    let Some(clip) = Clip::new(tone, 1, TONE_RATE, 1.0) else { return json!({"ok": false, "error": "tone"}) };
    player.play_tts(clip);
    std::thread::sleep(Duration::from_millis(TONE_MS + 700));
    let busy_after = player.status().busy;
    drop(stream);
    let rec = sink.lock().unwrap().clone();
    match analyse(&rec, rate) {
        Some(a) => json!({"ok": true, "loopback_rate": rate, "tone_ms": TONE_MS, "onset_ms": a.onset_ms, "span_ms": a.span_ms, "dropouts": a.dropouts,
                          "freq_hz": a.freq_hz, "peak_rms": a.peak_rms, "idle_after": !busy_after, "device": player.status().info.device}),
        None => json!({"ok": false, "error": "nothing was heard on the output device"}),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sine(rate: u32, hz: f32, ms: usize, amp: f32) -> Vec<f32> {
        (0..rate as usize * ms / 1000).map(|i| (i as f32 * hz * std::f32::consts::TAU / rate as f32).sin() * amp).collect()
    }

    #[test]
    fn a_clean_tone_has_the_right_length_pitch_and_no_defects() {
        let rate = 48000;
        let x = [vec![0.0; 14400], sine(rate, 440.0, 1200, 0.2), vec![0.0; 9600]].concat();
        let a = analyse(&x, rate).unwrap();
        assert!((a.onset_ms - 300.0).abs() <= 20.0, "onset {}", a.onset_ms);
        assert!((a.span_ms - 1200.0).abs() <= 30.0, "span {}", a.span_ms);
        assert_eq!((a.dropouts, a.glitches), (0, 0));
        assert!((a.freq_hz - 440.0).abs() < 3.0, "freq {}", a.freq_hz);
    }

    #[test]
    fn silence_inside_the_tone_is_counted_as_dropouts() {
        let rate = 48000;
        let x = [sine(rate, 440.0, 500, 0.2), vec![0.0; 48000 * 40 / 1000], sine(rate, 440.0, 500, 0.2)].concat();
        let a = analyse(&x, rate).unwrap();
        assert!(a.dropouts >= 6, "dropouts {}", a.dropouts);
    }

    #[test]
    fn skipped_samples_are_a_glitch_even_without_any_silence() {
        let rate = 48000;
        let mut x = [vec![0.0; 4800], sine(rate, 440.0, 1000, 0.2), vec![0.0; 4800]].concat();
        x.drain(24000..24000 + 55); // a few samples missing: the waveform jumps, nothing goes quiet
        let a = analyse(&x, rate).unwrap();
        assert!(a.glitches >= 1, "glitches {}", a.glitches);
        assert_eq!(a.dropouts, 0);
    }

    #[test]
    fn other_sounds_do_not_hide_or_fake_the_tone() {
        let rate = 48000;
        let tone = sine(rate, 440.0, 1000, 0.2);
        let noise = sine(rate, 1830.0, 1000, 0.15); // somebody's music at another pitch
        let x: Vec<f32> = tone.iter().zip(noise.iter()).map(|(a, b)| a + b).collect();
        let a = analyse(&x, rate).unwrap();
        assert_eq!((a.dropouts, a.glitches), (0, 0));
        assert!((a.freq_hz - 440.0).abs() < 3.0);
    }

    #[test]
    fn silence_is_reported_as_nothing_heard() {
        assert!(analyse(&vec![0.0; 48000], 48000).is_none());
    }
}
