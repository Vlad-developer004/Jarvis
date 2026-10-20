//! Input and output devices by name: what the settings screen lists and what the capture picks from.
use cpal::traits::{DeviceTrait, HostTrait};
use cpal::Device;
use serde_json::{json, Value};

pub fn name_of(d: &Device) -> String {
    d.description().map(|x| x.to_string()).unwrap_or_default().replace('\n', " ").trim().to_string()
}

fn id_of(d: &Device) -> String {
    d.id().map(|i| i.to_string()).unwrap_or_default()
}

/// The device a saved name refers to: an exact match first, then a case-insensitive "contains" (Windows appends and trims suffixes).
pub fn find_input(wanted: &str) -> Option<Device> {
    let host = cpal::default_host();
    let all: Vec<Device> = host.input_devices().ok()?.collect();
    let want = wanted.trim().to_lowercase();
    if want.is_empty() {
        return None;
    }
    all.iter().find(|d| name_of(d).to_lowercase() == want).or_else(|| all.iter().find(|d| name_of(d).to_lowercase().contains(&want))).cloned()
}

pub fn default_input() -> Option<Device> {
    cpal::default_host().default_input_device()
}

/// `{"ok", "inputs": [{"index", "id", "name", "default"}], "outputs": [...]}`; sound mappers and duplicates are not listed twice.
pub fn list() -> Value {
    let host = cpal::default_host();
    let default_in = host.default_input_device().map(|d| id_of(&d));
    let default_out = host.default_output_device().map(|d| id_of(&d));
    let describe = |devices: Vec<Device>, default: &Option<String>| -> Vec<Value> {
        devices
            .iter()
            .enumerate()
            .map(|(i, d)| {
                let id = id_of(d);
                json!({"index": i, "id": id, "name": name_of(d), "default": Some(&id) == default.as_ref()})
            })
            .collect()
    };
    let inputs = host.input_devices().map(|d| d.collect()).unwrap_or_default();
    let outputs = host.output_devices().map(|d| d.collect()).unwrap_or_default();
    json!({"ok": true, "inputs": describe(inputs, &default_in), "outputs": describe(outputs, &default_out)})
}
