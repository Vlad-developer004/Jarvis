//! Audio playback: TTS clips (one gapless queue) and short sound effects mixed into one output stream on the default device.
//!
//! The output stream lives on its own thread. It is rebuilt when the stream reports an error or the default output device changes
//! (headphones unplugged), keeping whatever is queued. Clips keep their own sample rate and are resampled linearly while mixing, so
//! a change of device rate needs no reprocessing.
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{BufferSize, Device, Error, ErrorKind, FromSample, SampleFormat, SizedSample, StreamConfig};
use std::collections::VecDeque;
use std::sync::atomic::{AtomicBool, AtomicU64, AtomicUsize, Ordering};
use std::sync::mpsc::{channel, Receiver, Sender};
use std::sync::{Arc, Mutex};
use std::time::Duration;

/// Output buffer length asked from the device (headroom against CPU spikes while the speech model runs).
const DEFAULT_BUFFER_MS: u32 = 40;

#[derive(Clone)]
pub struct Clip {
    data: Arc<Vec<f32>>, // interleaved
    channels: usize,
    rate: u32,
    pos: f64, // in frames
    gain: f32,
}

impl Clip {
    pub fn new(data: Vec<f32>, channels: usize, rate: u32, gain: f32) -> Option<Clip> {
        if channels == 0 || rate == 0 || data.len() < channels {
            return None;
        }
        Some(Clip { data: Arc::new(data), channels, rate, pos: 0.0, gain })
    }

    fn frames(&self) -> usize {
        self.data.len() / self.channels
    }

    pub fn seconds(&self) -> f64 {
        self.frames() as f64 / self.rate as f64
    }

    fn remaining_seconds(&self) -> f64 {
        ((self.frames() as f64 - self.pos).max(0.0)) / self.rate as f64
    }

    fn sample(&self, frame: usize, ch: usize) -> f32 {
        let c = if self.channels == 1 { 0 } else if ch < self.channels { ch } else { return 0.0 };
        self.data[frame.min(self.frames() - 1) * self.channels + c]
    }

    /// Value of output channel `ch` at the current position (linear interpolation).
    fn value(&self, ch: usize) -> f32 {
        let i = self.pos as usize;
        let frac = (self.pos - i as f64) as f32;
        let a = self.sample(i, ch);
        a + (self.sample(i + 1, ch) - a) * frac
    }
}

#[derive(Default)]
struct Mix {
    tts: VecDeque<Clip>,
    sfx: Vec<Clip>,
}

impl Mix {
    /// Fill `out` (interleaved, `channels` per frame) at `rate` Hz.
    fn render(&mut self, out: &mut [f32], channels: usize, rate: u32) {
        for frame in out.chunks_mut(channels) {
            for s in frame.iter_mut() {
                *s = 0.0;
            }
            // the TTS queue: when a clip ends, the next one continues in the same frame
            while let Some(clip) = self.tts.front_mut() {
                if clip.pos as usize >= clip.frames() {
                    self.tts.pop_front();
                    continue;
                }
                for (c, s) in frame.iter_mut().enumerate() {
                    *s += clip.value(c) * clip.gain;
                }
                clip.pos += clip.rate as f64 / rate as f64;
                break;
            }
            for clip in self.sfx.iter_mut() {
                if (clip.pos as usize) < clip.frames() {
                    for (c, s) in frame.iter_mut().enumerate() {
                        *s += clip.value(c) * clip.gain;
                    }
                    clip.pos += clip.rate as f64 / rate as f64;
                }
            }
            for s in frame.iter_mut() {
                *s = s.clamp(-1.0, 1.0);
            }
        }
        while self.tts.front().is_some_and(|c| c.pos as usize >= c.frames()) {
            self.tts.pop_front(); // a clip that just played its last frame is no longer busy
        }
        self.sfx.retain(|c| (c.pos as usize) < c.frames());
    }

    fn busy(&self) -> bool {
        !self.tts.is_empty() || !self.sfx.is_empty()
    }

    fn apply(&mut self, cmd: Cmd) {
        match cmd {
            Cmd::Tts(c) => self.tts.push_back(c),
            Cmd::Sfx(c) => self.sfx.push(c),
            Cmd::Stop { tts, sfx } => {
                if tts {
                    self.tts.clear();
                }
                if sfx {
                    self.sfx.clear();
                }
            }
        }
    }

    fn publish(&self, g: &Gauges) {
        g.mixing.store(self.busy(), Ordering::SeqCst);
        g.queued.store(self.tts.len(), Ordering::SeqCst);
        let secs: f64 = self.tts.iter().chain(self.sfx.iter()).map(Clip::remaining_seconds).sum();
        g.remaining_ms.store((secs * 1000.0) as u64, Ordering::SeqCst);
    }
}

#[derive(Default, Clone)]
pub struct DeviceInfo {
    pub ready: bool,
    pub device: String,
    pub rate: u32,
    pub channels: u16,
    pub rebuilds: u32,
    pub last_error: String,
}

enum Cmd {
    Tts(Clip),
    Sfx(Clip),
    Stop { tts: bool, sfx: bool },
}

/// What the requests can read without touching the mixer: the audio callback updates these after every buffer.
#[derive(Default)]
struct Gauges {
    pending: AtomicUsize, // commands sent but not yet taken by the callback
    plays: AtomicUsize,   // the part of `pending` that starts a clip
    mixing: AtomicBool,
    queued: AtomicUsize,
    remaining_ms: AtomicU64,
}

pub struct Player {
    tx: Sender<Cmd>,
    gauges: Arc<Gauges>,
    info: Arc<Mutex<DeviceInfo>>,
}

pub struct Status {
    pub busy: bool,
    pub queued: usize,
    pub remaining: f64,
    pub info: DeviceInfo,
}

impl Player {
    pub fn new() -> Player {
        let (tx, rx) = channel();
        let mix = Arc::new(Mutex::new(Mix::default()));
        let gauges = Arc::new(Gauges::default());
        let info = Arc::new(Mutex::new(DeviceInfo::default()));
        let feed = Arc::new(Mutex::new(rx));
        let (m, g, i) = (Arc::clone(&mix), Arc::clone(&gauges), Arc::clone(&info));
        std::thread::Builder::new().name("player".into()).spawn(move || manage(m, feed, g, i)).expect("player thread");
        Player { tx, gauges, info }
    }

    fn send(&self, cmd: Cmd) {
        self.gauges.pending.fetch_add(1, Ordering::SeqCst);
        if !matches!(cmd, Cmd::Stop { .. }) {
            self.gauges.plays.fetch_add(1, Ordering::SeqCst);
        }
        let _ = self.tx.send(cmd);
    }

    pub fn play_tts(&self, clip: Clip) {
        self.send(Cmd::Tts(clip));
    }

    pub fn play_sfx(&self, clip: Clip) {
        self.send(Cmd::Sfx(clip));
    }

    /// Drop what is playing and queued: the TTS queue, the effects, or both.
    /// Returns once the audio callback has applied it (at most a moment later), so the status is right as soon as this returns.
    pub fn stop(&self, tts: bool, sfx: bool) {
        self.send(Cmd::Stop { tts, sfx });
        let end = std::time::Instant::now() + Duration::from_millis(250);
        while self.gauges.pending.load(Ordering::SeqCst) > 0 && std::time::Instant::now() < end {
            std::thread::sleep(Duration::from_millis(2));
        }
    }

    pub fn status(&self) -> Status {
        let g = &self.gauges;
        let plays = g.plays.load(Ordering::SeqCst);
        Status {
            busy: plays > 0 || g.mixing.load(Ordering::SeqCst),
            queued: g.queued.load(Ordering::SeqCst) + plays,
            remaining: g.remaining_ms.load(Ordering::SeqCst) as f64 / 1000.0,
            info: self.info.lock().unwrap().clone(),
        }
    }

    pub fn wait_ready(&self, timeout: Duration) -> bool {
        let end = std::time::Instant::now() + timeout;
        while std::time::Instant::now() < end {
            if self.info.lock().unwrap().ready {
                return true;
            }
            std::thread::sleep(Duration::from_millis(20));
        }
        false
    }
}

fn buffer_ms() -> u32 {
    std::env::var("JARVIS_AUDIO_BUFFER_MS").ok().and_then(|v| v.parse().ok()).filter(|v| (5..=500).contains(v)).unwrap_or(DEFAULT_BUFFER_MS)
}

/// Raise the audio callback thread to the Windows "Pro Audio" scheduling class once, from inside the callback.
#[cfg(windows)]
fn boost_thread() {
    use windows::core::w;
    use windows::Win32::System::Threading::AvSetMmThreadCharacteristicsW;
    let mut task = 0u32;
    let _ = unsafe { AvSetMmThreadCharacteristicsW(w!("Pro Audio"), &mut task) };
}

#[cfg(not(windows))]
fn boost_thread() {}

fn build<T>(device: &Device, config: StreamConfig, st: Shared) -> Result<cpal::Stream, Error>
where
    T: SizedSample + FromSample<f32>,
{
    let (channels, rate) = (config.channels as usize, config.sample_rate);
    let Shared { mix, feed, gauges, failed } = st;
    let mut scratch: Vec<f32> = Vec::new();
    let mut boosted = false;
    device.build_output_stream(
        config,
        move |data: &mut [T], _| {
            if !boosted {
                boosted = true;
                boost_thread();
            }
            scratch.resize(data.len(), 0.0);
            // Only this callback and the stream manager (while no stream exists) ever lock these, so they are never contended.
            let (mut m, rx) = (mix.lock().unwrap(), feed.lock().unwrap());
            while let Ok(cmd) = rx.try_recv() {
                let is_play = !matches!(cmd, Cmd::Stop { .. });
                m.apply(cmd);
                if is_play {
                    gauges.plays.fetch_sub(1, Ordering::SeqCst);
                }
                gauges.pending.fetch_sub(1, Ordering::SeqCst);
            }
            m.render(&mut scratch, channels, rate);
            m.publish(&gauges);
            for (o, s) in data.iter_mut().zip(scratch.iter()) {
                *o = T::from_sample(*s);
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

#[derive(Clone)]
struct Shared {
    mix: Arc<Mutex<Mix>>,
    feed: Arc<Mutex<Receiver<Cmd>>>,
    gauges: Arc<Gauges>,
    failed: Arc<AtomicBool>,
}

fn open(st: &Shared) -> Result<(cpal::Stream, DeviceInfo), String> {
    let host = cpal::default_host();
    let device = host.default_output_device().ok_or("no output device")?;
    let supported = device.default_output_config().map_err(|e| e.to_string())?;
    let format = supported.sample_format();
    let mut config: StreamConfig = supported.into();
    let name = device.id().map(|i| i.to_string()).unwrap_or_default();
    let want = BufferSize::Fixed(config.sample_rate * buffer_ms() / 1000);
    for attempt in [want, BufferSize::Default] {
        config.buffer_size = attempt;
        let built = match format {
            SampleFormat::F32 => build::<f32>(&device, config, st.clone()),
            SampleFormat::I16 => build::<i16>(&device, config, st.clone()),
            SampleFormat::I32 => build::<i32>(&device, config, st.clone()),
            SampleFormat::U16 => build::<u16>(&device, config, st.clone()),
            other => return Err(format!("unsupported sample format {other}")),
        };
        if let Ok(stream) = built {
            stream.play().map_err(|e| e.to_string())?;
            let info = DeviceInfo { ready: true, device: name, rate: config.sample_rate, channels: config.channels, rebuilds: 0, last_error: String::new() };
            return Ok((stream, info));
        }
    }
    Err("could not open the output stream".into())
}

fn default_id() -> String {
    cpal::default_host().default_output_device().and_then(|d| d.id().ok()).map(|i| i.to_string()).unwrap_or_default()
}

/// The thread that owns the stream: open it, and open it again when it fails or the default device really changed.
fn manage(mix: Arc<Mutex<Mix>>, feed: Arc<Mutex<Receiver<Cmd>>>, gauges: Arc<Gauges>, info: Arc<Mutex<DeviceInfo>>) {
    let st = Shared { mix, feed, gauges, failed: Arc::new(AtomicBool::new(false)) };
    let mut stream: Option<cpal::Stream> = None;
    let mut current = String::new();
    let mut rebuilds = 0u32;
    let mut changed_polls = 0u32;
    loop {
        if stream.is_none() {
            st.failed.store(false, Ordering::SeqCst);
            changed_polls = 0;
            match open(&st) {
                Ok((s, mut i)) => {
                    current = i.device.clone();
                    i.rebuilds = rebuilds;
                    *info.lock().unwrap() = i;
                    stream = Some(s);
                }
                Err(e) => {
                    // No output device right now: what was asked to play cannot be heard, and must not wait to be played minutes later
                    let rx = st.feed.lock().unwrap();
                    while let Ok(cmd) = rx.try_recv() {
                        if !matches!(cmd, Cmd::Stop { .. }) {
                            st.gauges.plays.fetch_sub(1, Ordering::SeqCst);
                        }
                        st.gauges.pending.fetch_sub(1, Ordering::SeqCst);
                    }
                    drop(rx);
                    st.mix.lock().unwrap().tts.clear();
                    st.mix.lock().unwrap().sfx.clear();
                    st.mix.lock().unwrap().publish(&st.gauges);
                    let mut i = info.lock().unwrap();
                    i.ready = false;
                    i.last_error = e;
                }
            }
        } else {
            // A busy machine can make the device lookup fail for a moment: only a different, non-empty id seen twice in a row counts.
            let now = default_id();
            changed_polls = if !now.is_empty() && now != current { changed_polls + 1 } else { 0 };
            if st.failed.load(Ordering::SeqCst) || changed_polls >= 2 {
                stream = None; // dropping the stream closes it; the queue stays in `mix`
                info.lock().unwrap().ready = false;
                rebuilds += 1;
                continue;
            }
        }
        std::thread::sleep(Duration::from_millis(250));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tone(frames: usize, rate: u32, v: f32) -> Clip {
        Clip::new(vec![v; frames], 1, rate, 1.0).unwrap()
    }

    #[test]
    fn clips_in_the_tts_queue_play_back_to_back_without_a_gap() {
        let mut m = Mix::default();
        m.tts.push_back(tone(4, 10, 0.25));
        m.tts.push_back(tone(4, 10, 0.5));
        let mut out = vec![0.0; 16];
        m.render(&mut out, 2, 10); // 8 frames of stereo
        let left: Vec<f32> = out.chunks(2).map(|f| f[0]).collect();
        assert_eq!(left, vec![0.25, 0.25, 0.25, 0.25, 0.5, 0.5, 0.5, 0.5]);
        assert!(!m.busy());
    }

    #[test]
    fn a_clip_is_resampled_to_the_device_rate() {
        let mut m = Mix::default();
        m.tts.push_back(tone(10, 10, 0.5)); // one second at 10 Hz
        let mut out = vec![0.0; 40];
        m.render(&mut out, 1, 20); // 40 frames at 20 Hz: the clip fills the first 20
        assert!(out[..20].iter().all(|v| (*v - 0.5).abs() < 1e-6));
        assert!(out[20..].iter().all(|v| *v == 0.0));
    }

    #[test]
    fn effects_mix_over_speech_and_the_sum_is_limited() {
        let mut m = Mix::default();
        m.tts.push_back(tone(4, 10, 0.75));
        m.sfx.push(tone(2, 10, 0.5));
        let mut out = vec![0.0; 4];
        m.render(&mut out, 1, 10);
        assert_eq!(out, vec![1.0, 1.0, 0.75, 0.75]);
        assert!(m.sfx.is_empty());
    }

    #[test]
    fn stopping_clears_what_was_asked_for() {
        let mut m = Mix::default();
        m.apply(Cmd::Tts(tone(100, 10, 0.1)));
        m.apply(Cmd::Sfx(tone(100, 10, 0.1)));
        m.apply(Cmd::Stop { tts: true, sfx: false });
        assert!(m.busy() && m.tts.is_empty() && m.sfx.len() == 1);
        m.apply(Cmd::Stop { tts: false, sfx: true });
        assert!(!m.busy());
    }

    #[test]
    fn the_status_counts_a_command_that_the_callback_has_not_taken_yet() {
        let (tx, _rx) = channel();
        let p = Player { tx, gauges: Arc::new(Gauges::default()), info: Arc::new(Mutex::new(DeviceInfo::default())) };
        assert!(!p.status().busy);
        p.play_tts(tone(10, 10, 0.1)); // nobody is reading the channel: the request is pending, and counts as busy
        let s = p.status();
        assert!(s.busy && s.queued == 1);
    }

    #[test]
    fn publishing_reports_what_is_left_to_play() {
        let mut m = Mix::default();
        m.apply(Cmd::Tts(tone(20, 10, 0.1))); // two seconds
        let g = Gauges::default();
        m.publish(&g);
        assert!(g.mixing.load(Ordering::SeqCst));
        assert_eq!(g.queued.load(Ordering::SeqCst), 1);
        assert_eq!(g.remaining_ms.load(Ordering::SeqCst), 2000);
    }

    #[test]
    fn mono_clips_fill_every_channel_and_stereo_clips_keep_theirs() {
        let mut m = Mix::default();
        m.tts.push_back(Clip::new(vec![0.1, 0.9], 2, 10, 1.0).unwrap());
        let mut out = vec![0.0; 3];
        m.render(&mut out, 3, 10);
        assert_eq!(out, vec![0.1, 0.9, 0.0]);
        let mono = Clip::new(vec![0.4], 1, 10, 1.0).unwrap();
        assert_eq!((mono.value(0), mono.value(1)), (0.4, 0.4));
    }

    #[test]
    fn bad_clips_are_refused() {
        assert!(Clip::new(vec![], 1, 10, 1.0).is_none());
        assert!(Clip::new(vec![0.0], 0, 10, 1.0).is_none());
        assert!(Clip::new(vec![0.0], 1, 0, 1.0).is_none());
    }
}
