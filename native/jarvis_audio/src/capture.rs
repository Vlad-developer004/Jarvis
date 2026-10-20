//! `--capture --rate R --chunk N [--device NAME]`: records the microphone, converts it to mono 16-bit at rate R and writes it to stdout
//! in chunks of exactly N samples.
//!
//! Frames on stdout: one type byte, a 4-byte little-endian length, then the payload.
//!   type 1: PCM chunk (N little-endian i16 samples)
//!   type 2: an event as JSON text ({"event": "started" | "error" | "dropped", ...})
//! stdin carries control lines; a line `stop` or the end of stdin (Jarvis gone) ends the program.
//! The stream is re-opened by itself when the device fails or, with no device named, when the Windows default input changes.
use crate::devices;
use crate::resample::{Chunker, Resampler};
use cpal::traits::{DeviceTrait, StreamTrait};
use cpal::{Device, Error, ErrorKind, FromSample, Sample, SampleFormat, SizedSample, StreamConfig};
use serde_json::json;
use std::io::{BufRead, Write};
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::mpsc::{sync_channel, Receiver, SyncSender};
use std::sync::Arc;
use std::time::Duration;

const QUEUE_CHUNKS: usize = 128; // about four seconds at 32 ms: a stalled reader costs old audio, not memory

pub enum Frame {
    Pcm(Vec<i16>),
    Event(String),
}

pub fn write_frame(out: &mut impl Write, frame: &Frame) -> std::io::Result<()> {
    let (kind, payload): (u8, Vec<u8>) = match frame {
        Frame::Pcm(s) => (1, s.iter().flat_map(|v| v.to_le_bytes()).collect()),
        Frame::Event(t) => (2, t.as_bytes().to_vec()),
    };
    out.write_all(&[kind])?;
    out.write_all(&(payload.len() as u32).to_le_bytes())?;
    out.write_all(&payload)?;
    out.flush()
}

struct Shared {
    tx: SyncSender<Frame>,
    dropped: Arc<AtomicUsize>,
    failed: Arc<AtomicBool>,
}

fn build<T>(device: &Device, config: StreamConfig, rate: u32, chunk: usize, st: &Shared) -> Result<cpal::Stream, Error>
where
    T: SizedSample,
    f32: FromSample<T>,
{
    let channels = config.channels as usize;
    let mut resampler = Resampler::new(config.sample_rate, rate);
    let mut chunker = Chunker::new(chunk);
    let (tx, dropped, failed) = (st.tx.clone(), Arc::clone(&st.dropped), Arc::clone(&st.failed));
    let mut mono: Vec<f32> = Vec::new();
    device.build_input_stream(
        config,
        move |data: &[T], _| {
            mono.clear();
            mono.extend(data.chunks(channels).map(|f| f.iter().map(|s| f32::from_sample(*s)).sum::<f32>() / channels as f32));
            for c in chunker.push(&resampler.process(&mono)) {
                if tx.try_send(Frame::Pcm(c)).is_err() {
                    dropped.fetch_add(1, Ordering::SeqCst);
                }
            }
        },
        move |err: Error| {
            if !matches!(err.kind(), ErrorKind::Xrun | ErrorKind::RealtimeDenied) {
                failed.store(true, Ordering::SeqCst);
            }
        },
        None,
    )
}

fn open(wanted: &Option<String>, rate: u32, chunk: usize, st: &Shared) -> Result<(cpal::Stream, String), String> {
    let device = match wanted {
        Some(name) => devices::find_input(name).or_else(devices::default_input).ok_or("no input device")?,
        None => devices::default_input().ok_or("no input device")?,
    };
    let supported = device.default_input_config().map_err(|e| e.to_string())?;
    let format = supported.sample_format();
    let config: StreamConfig = supported.into();
    let stream = match format {
        SampleFormat::F32 => build::<f32>(&device, config, rate, chunk, st),
        SampleFormat::I16 => build::<i16>(&device, config, rate, chunk, st),
        SampleFormat::I32 => build::<i32>(&device, config, rate, chunk, st),
        SampleFormat::U16 => build::<u16>(&device, config, rate, chunk, st),
        other => return Err(format!("unsupported sample format {other}")),
    }
    .map_err(|e| e.to_string())?;
    stream.play().map_err(|e| e.to_string())?;
    Ok((stream, devices::name_of(&device)))
}

fn event(value: serde_json::Value) -> Frame {
    Frame::Event(value.to_string())
}

/// The thread that owns the stream and re-opens it; frames leave through `tx`.
fn manage(wanted: Option<String>, rate: u32, chunk: usize, st: Shared, quit: Arc<AtomicBool>) {
    let mut stream: Option<cpal::Stream> = None;
    let mut current_default = String::new();
    let mut last_error = String::new();
    let mut default_changed = 0u32;
    while !quit.load(Ordering::SeqCst) {
        if stream.is_none() {
            st.failed.store(false, Ordering::SeqCst);
            default_changed = 0;
            match open(&wanted, rate, chunk, &st) {
                Ok((s, name)) => {
                    current_default = devices::default_input().and_then(|d| d.id().ok()).map(|i| i.to_string()).unwrap_or_default();
                    let _ = st.tx.try_send(event(json!({"event": "started", "device": name, "rate": rate, "chunk": chunk})));
                    stream = Some(s);
                    last_error.clear();
                }
                Err(e) => {
                    if e != last_error {
                        let _ = st.tx.try_send(event(json!({"event": "error", "error": e})));
                        last_error = e;
                    }
                    std::thread::sleep(Duration::from_millis(1000));
                    continue;
                }
            }
        } else {
            let lost = st.dropped.swap(0, Ordering::SeqCst);
            if lost > 0 {
                let _ = st.tx.try_send(event(json!({"event": "dropped", "chunks": lost})));
            }
            if wanted.is_none() {
                let now = devices::default_input().and_then(|d| d.id().ok()).map(|i| i.to_string()).unwrap_or_default();
                default_changed = if !now.is_empty() && now != current_default { default_changed + 1 } else { 0 };
            }
            if st.failed.load(Ordering::SeqCst) || default_changed >= 2 {
                stream = None; // closes it; the loop opens it again
                let _ = st.tx.try_send(event(json!({"event": "reopening"})));
                continue;
            }
        }
        std::thread::sleep(Duration::from_millis(250));
    }
}

/// Entry point of `--capture`; returns when stdin ends or says `stop`, or when stdout is gone.
pub fn run(wanted: Option<String>, rate: u32, chunk: usize) {
    let (tx, rx): (SyncSender<Frame>, Receiver<Frame>) = sync_channel(QUEUE_CHUNKS);
    let quit = Arc::new(AtomicBool::new(false));
    let st = Shared { tx: tx.clone(), dropped: Arc::new(AtomicUsize::new(0)), failed: Arc::new(AtomicBool::new(false)) };
    let q = Arc::clone(&quit);
    std::thread::spawn(move || manage(wanted, rate, chunk, st, q));
    // control: `stop` or the end of stdin
    let q = Arc::clone(&quit);
    std::thread::spawn(move || {
        for line in std::io::stdin().lock().lines() {
            match line {
                Ok(l) if l.trim() == "stop" => break,
                Ok(_) => {}
                Err(_) => break,
            }
        }
        q.store(true, Ordering::SeqCst);
    });
    let mut out = std::io::stdout().lock();
    while !quit.load(Ordering::SeqCst) {
        match rx.recv_timeout(Duration::from_millis(100)) {
            Ok(frame) => {
                if write_frame(&mut out, &frame).is_err() {
                    break;
                }
            }
            Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {}
            Err(_) => break,
        }
    }
    quit.store(true, Ordering::SeqCst);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pcm_frames_carry_a_type_a_length_and_little_endian_samples() {
        let mut out = Vec::new();
        write_frame(&mut out, &Frame::Pcm(vec![1, -2, 256])).unwrap();
        assert_eq!(out, vec![1, 6, 0, 0, 0, 1, 0, 0xFE, 0xFF, 0, 1]);
    }

    #[test]
    fn event_frames_carry_json_text() {
        let mut out = Vec::new();
        write_frame(&mut out, &Frame::Event("{\"event\":\"started\"}".into())).unwrap();
        assert_eq!(out[0], 2);
        assert_eq!(u32::from_le_bytes([out[1], out[2], out[3], out[4]]) as usize, out.len() - 5);
        assert_eq!(&out[5..], b"{\"event\":\"started\"}");
    }
}
