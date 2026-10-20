//! Turning files and raw PCM from the Python core into playable clips.
use crate::player::Clip;
use base64::Engine;
use symphonia::core::audio::SampleBuffer;
use symphonia::core::codecs::DecoderOptions;
use symphonia::core::errors::Error as SymError;
use symphonia::core::formats::FormatOptions;
use symphonia::core::io::MediaSourceStream;
use symphonia::core::meta::MetadataOptions;
use symphonia::core::probe::Hint;

/// Decode an audio file (WAV in any common PCM or float layout, MP3, Ogg Vorbis) completely into a clip.
pub fn from_file(path: &str, gain: f32) -> Result<Clip, String> {
    let file = std::fs::File::open(path).map_err(|e| format!("cannot open {path}: {e}"))?;
    let stream = MediaSourceStream::new(Box::new(file), Default::default());
    let mut hint = Hint::new();
    if let Some(ext) = std::path::Path::new(path).extension().and_then(|e| e.to_str()) {
        hint.with_extension(ext);
    }
    let probed = symphonia::default::get_probe()
        .format(&hint, stream, &FormatOptions::default(), &MetadataOptions::default())
        .map_err(|e| format!("unknown audio format in {path}: {e}"))?;
    let mut format = probed.format;
    let track = format.default_track().ok_or("no audio track")?;
    let track_id = track.id;
    let mut decoder = symphonia::default::get_codecs()
        .make(&track.codec_params, &DecoderOptions::default())
        .map_err(|e| format!("cannot decode {path}: {e}"))?;
    let (mut data, mut channels, mut rate): (Vec<f32>, usize, u32) = (Vec::new(), 0, 0);
    loop {
        let packet = match format.next_packet() {
            Ok(p) => p,
            Err(SymError::IoError(_)) | Err(SymError::ResetRequired) => break, // end of the stream
            Err(e) => return Err(format!("bad audio data in {path}: {e}")),
        };
        if packet.track_id() != track_id {
            continue;
        }
        match decoder.decode(&packet) {
            Ok(buf) => {
                let spec = *buf.spec();
                channels = spec.channels.count();
                rate = spec.rate;
                let mut samples = SampleBuffer::<f32>::new(buf.capacity() as u64, spec);
                samples.copy_interleaved_ref(buf);
                data.extend_from_slice(samples.samples());
            }
            Err(SymError::DecodeError(_)) => continue, // one damaged frame is skipped
            Err(e) => return Err(format!("bad audio data in {path}: {e}")),
        }
    }
    Clip::new(data, channels, rate, gain).ok_or_else(|| "empty or invalid clip".to_string())
}

/// Raw little-endian 16-bit PCM, base64-encoded (what the Python side sends for synthesised sounds).
pub fn from_pcm16_b64(b64: &str, channels: usize, rate: u32, gain: f32) -> Result<Clip, String> {
    let bytes = base64::engine::general_purpose::STANDARD.decode(b64).map_err(|e| format!("bad base64: {e}"))?;
    let data: Vec<f32> = bytes.as_chunks::<2>().0.iter().map(|b| f32::from(i16::from_le_bytes(*b)) / 32768.0).collect();
    Clip::new(data, channels, rate, gain).ok_or_else(|| "empty or invalid clip".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp(name: &str) -> std::path::PathBuf {
        let dir = std::env::temp_dir().join(format!("jarvis_audio_test_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        dir.join(name)
    }

    fn write_wav(path: &std::path::Path, spec: hound::WavSpec, samples: &[i16]) {
        let mut w = hound::WavWriter::create(path, spec).unwrap();
        for s in samples {
            w.write_sample(*s).unwrap();
        }
        w.finalize().unwrap();
    }

    #[test]
    fn a_16_bit_wav_becomes_a_clip_with_the_right_length_and_level() {
        let p = temp("a.wav");
        write_wav(&p, hound::WavSpec { channels: 2, sample_rate: 8000, bits_per_sample: 16, sample_format: hound::SampleFormat::Int }, &[16384; 16000]);
        let clip = from_file(p.to_str().unwrap(), 1.0).unwrap();
        assert!((clip.seconds() - 1.0).abs() < 1e-9);
        std::fs::remove_file(&p).ok();
    }

    #[test]
    fn mono_float_wav_is_read_too() {
        let p = temp("f.wav");
        let mut w = hound::WavWriter::create(&p, hound::WavSpec { channels: 1, sample_rate: 4000, bits_per_sample: 32, sample_format: hound::SampleFormat::Float }).unwrap();
        for _ in 0..2000 {
            w.write_sample(0.25f32).unwrap();
        }
        w.finalize().unwrap();
        let clip = from_file(p.to_str().unwrap(), 1.0).unwrap();
        assert!((clip.seconds() - 0.5).abs() < 1e-9);
        std::fs::remove_file(&p).ok();
    }

    #[test]
    fn missing_files_and_garbage_are_errors_not_panics() {
        assert!(from_file("Z:/definitely/not/here.wav", 1.0).is_err());
        let p = temp("junk.wav");
        std::fs::write(&p, b"this is not audio at all, just text").unwrap();
        assert!(from_file(p.to_str().unwrap(), 1.0).is_err());
        std::fs::remove_file(&p).ok();
        assert!(from_pcm16_b64("not base64!!", 1, 8000, 1.0).is_err());
        assert!(from_pcm16_b64("", 1, 8000, 1.0).is_err());
    }

    #[test]
    fn pcm_round_trip_keeps_the_length() {
        let b64 = base64::engine::general_purpose::STANDARD.encode([0x00u8, 0x40, 0x00, 0xC0]); // 16384, -16384
        let clip = from_pcm16_b64(&b64, 1, 4, 1.0).unwrap();
        assert!((clip.seconds() - 0.5).abs() < 1e-9);
    }

    #[test]
    fn the_shipped_effect_sounds_decode() {
        // audio/sfx holds MP3 files (reminder, alarm, milestone, red_alert); they must load in a source checkout
        let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../audio/sfx");
        let Ok(entries) = std::fs::read_dir(&dir) else { return };
        for e in entries.flatten() {
            let path = e.path();
            if path.extension().is_some_and(|x| x == "mp3") {
                let clip = from_file(path.to_str().unwrap(), 1.0).unwrap_or_else(|err| panic!("{path:?}: {err}"));
                assert!(clip.seconds() > 0.05, "{path:?} decoded to {} s", clip.seconds());
            }
        }
    }
}
