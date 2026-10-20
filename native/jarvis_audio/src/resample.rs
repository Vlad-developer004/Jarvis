//! Sample-rate conversion for the microphone: windowed-sinc interpolation with the cut-off set below the lower Nyquist rate, so 48 kHz
//! to 16 kHz does not fold high frequencies back into the speech band. Works on a running stream: feed any number of input samples,
//! get whatever output samples are complete.

const HALF_WIDTH: usize = 24; // taps on each side of the output position, in input samples (scaled up when downsampling)
const MARGIN: f64 = 0.92; // cut-off as a share of the lower Nyquist rate

pub struct Resampler {
    step: f64,   // input samples per output sample
    cutoff: f64, // in cycles per input sample, <= 0.5
    reach: usize, // taps on each side
    pos: f64,    // position of the next output sample, in input samples counted from `buf[0]`
    buf: Vec<f32>,
    passthrough: bool,
}

fn sinc(x: f64) -> f64 {
    if x.abs() < 1e-9 {
        1.0
    } else {
        (std::f64::consts::PI * x).sin() / (std::f64::consts::PI * x)
    }
}

impl Resampler {
    pub fn new(in_rate: u32, out_rate: u32) -> Resampler {
        let step = in_rate as f64 / out_rate as f64;
        let cutoff = 0.5 * MARGIN / step.max(1.0);
        let reach = ((HALF_WIDTH as f64 * step.max(1.0)).ceil() as usize).max(HALF_WIDTH);
        Resampler { step, cutoff, reach, pos: 0.0, buf: Vec::new(), passthrough: in_rate == out_rate }
    }

    fn weight(&self, d: f64) -> f64 {
        let w = d / self.reach as f64; // -1..1
        let window = 0.42 + 0.5 * (std::f64::consts::PI * w).cos() + 0.08 * (2.0 * std::f64::consts::PI * w).cos(); // Blackman
        2.0 * self.cutoff * sinc(2.0 * self.cutoff * d) * window
    }

    /// Add input samples and return the output samples that can be computed so far.
    pub fn process(&mut self, input: &[f32]) -> Vec<f32> {
        if self.passthrough {
            return input.to_vec();
        }
        self.buf.extend_from_slice(input);
        let mut out = Vec::new();
        // an output sample needs `reach` input samples after its position
        while self.pos + self.reach as f64 + 1.0 < self.buf.len() as f64 {
            let centre = self.pos.floor() as isize;
            let lo = centre - self.reach as isize + 1;
            let hi = centre + self.reach as isize;
            let (mut acc, mut norm) = (0.0f64, 0.0f64);
            for n in lo..=hi {
                let w = self.weight(self.pos - n as f64);
                norm += w;
                if n >= 0 {
                    acc += self.buf[n as usize] as f64 * w;
                }
            }
            out.push((acc / norm) as f32);
            self.pos += self.step;
        }
        // forget input that no later output can reach
        let keep_from = (self.pos.floor() as isize - self.reach as isize).max(0) as usize;
        if keep_from > 0 {
            self.buf.drain(..keep_from);
            self.pos -= keep_from as f64;
        }
        out
    }
}

/// Collects samples and hands them out in chunks of exactly `size` samples.
pub struct Chunker {
    size: usize,
    pending: Vec<i16>,
}

impl Chunker {
    pub fn new(size: usize) -> Chunker {
        Chunker { size: size.max(1), pending: Vec::new() }
    }

    pub fn push(&mut self, samples: &[f32]) -> Vec<Vec<i16>> {
        self.pending.extend(samples.iter().map(|s| (s.clamp(-1.0, 1.0) * 32767.0).round() as i16));
        let mut out = Vec::new();
        while self.pending.len() >= self.size {
            out.push(self.pending.drain(..self.size).collect());
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sine(rate: u32, hz: f64, secs: f64, amp: f32) -> Vec<f32> {
        (0..(rate as f64 * secs) as usize).map(|i| (i as f64 * hz * std::f64::consts::TAU / rate as f64).sin() as f32 * amp).collect()
    }

    fn rms(x: &[f32]) -> f32 {
        (x.iter().map(|v| v * v).sum::<f32>() / x.len() as f32).sqrt()
    }

    fn feed_in_pieces(r: &mut Resampler, x: &[f32], piece: usize) -> Vec<f32> {
        x.chunks(piece).flat_map(|c| r.process(c)).collect()
    }

    #[test]
    fn downsampling_keeps_a_speech_tone_at_the_same_level_and_length() {
        let mut r = Resampler::new(48000, 16000);
        let out = feed_in_pieces(&mut r, &sine(48000, 1000.0, 2.0, 0.5), 480);
        assert!((out.len() as f64 - 32000.0).abs() < 100.0, "len {}", out.len());
        let level = rms(&out[2000..out.len() - 2000]);
        assert!((level - 0.5 / 2f32.sqrt()).abs() < 0.01, "rms {level}");
    }

    #[test]
    fn frequencies_above_the_new_nyquist_rate_are_removed_not_folded_down() {
        let mut r = Resampler::new(48000, 16000);
        // 12 kHz would alias to 4 kHz at 16 kHz if it were not filtered out first
        let out = feed_in_pieces(&mut r, &sine(48000, 12000.0, 1.0, 0.5), 480);
        assert!(rms(&out[2000..out.len() - 2000]) < 0.01, "leaked {}", rms(&out[2000..]));
    }

    #[test]
    fn the_result_does_not_depend_on_how_the_input_is_split() {
        let x = sine(44100, 700.0, 1.0, 0.4);
        let a = feed_in_pieces(&mut Resampler::new(44100, 16000), &x, 441);
        let b = feed_in_pieces(&mut Resampler::new(44100, 16000), &x, 4410);
        let n = a.len().min(b.len());
        assert!(n > 15000);
        assert!(a[..n].iter().zip(&b[..n]).all(|(p, q)| (p - q).abs() < 1e-5));
    }

    #[test]
    fn upsampling_and_equal_rates_work_too() {
        let mut up = Resampler::new(8000, 16000);
        let out = feed_in_pieces(&mut up, &sine(8000, 500.0, 1.0, 0.5), 160);
        assert!((out.len() as f64 - 16000.0).abs() < 100.0);
        assert!((rms(&out[2000..out.len() - 2000]) - 0.5 / 2f32.sqrt()).abs() < 0.01);
        let mut same = Resampler::new(16000, 16000);
        assert_eq!(same.process(&[0.1, 0.2, 0.3]), vec![0.1, 0.2, 0.3]);
    }

    #[test]
    fn dc_level_is_preserved() {
        let mut r = Resampler::new(48000, 16000);
        let out = feed_in_pieces(&mut r, &vec![0.25f32; 48000], 480);
        assert!(out[1000..out.len() - 1000].iter().all(|v| (v - 0.25).abs() < 1e-3));
    }

    #[test]
    fn chunker_hands_out_exact_chunks_and_keeps_the_rest() {
        let mut c = Chunker::new(4);
        assert!(c.push(&[0.0, 0.5]).is_empty());
        let out = c.push(&[1.0, -1.0, 0.25]);
        assert_eq!(out.len(), 1);
        assert_eq!(out[0], vec![0, 16384, 32767, -32767]);
        let more = c.push(&[0.0, 0.0, 0.0]);
        assert_eq!(more.len(), 1); // 0.25 from before plus three zeros
        assert_eq!(more[0][0], 8192);
    }
}
