//! What the default playback device is: speakers or headphones, from the Windows endpoint form factor (not from its name).
use serde_json::{json, Value};

/// `EndpointFormFactor` values of Windows (mmdeviceapi.h) -> (kind, is_headphones).
/// A headset counts as headphones: its speaker sits at the ear, so the microphone does not hear the playback.
pub fn classify(form_factor: u32) -> (&'static str, bool) {
    match form_factor {
        0 => ("network", false),
        1 => ("speakers", false),
        2 => ("line", false),
        3 => ("headphones", true),
        5 => ("headset", true),
        6 => ("handset", true),
        7 | 8 => ("digital", false),
        9 => ("display", false),
        _ => ("unknown", false),
    }
}

pub fn to_json(name: &str, id: &str, form_factor: u32) -> Value {
    let (kind, is_headphones) = classify(form_factor);
    json!({"ok": true, "name": name, "id": id, "form_factor": form_factor, "kind": kind, "is_headphones": is_headphones})
}

pub fn error_json(msg: &str) -> Value {
    json!({"ok": false, "error": msg})
}

#[cfg(windows)]
pub fn query_output() -> Value {
    match imp::default_render() {
        Ok((name, id, ff)) => to_json(&name, &id, ff),
        Err(e) => error_json(&e.to_string()),
    }
}

#[cfg(not(windows))]
pub fn query_output() -> Value {
    error_json("unsupported platform")
}

#[cfg(windows)]
mod imp {
    use windows::core::{GUID, PWSTR};
    use windows::Win32::Foundation::PROPERTYKEY;
    use windows::Win32::Media::Audio::{eConsole, eRender, IMMDeviceEnumerator, MMDeviceEnumerator};
    use windows::Win32::System::Com::{CoCreateInstance, CoInitializeEx, CoTaskMemFree, CoUninitialize, CLSCTX_ALL, COINIT_APARTMENTTHREADED, STGM_READ};
    use windows::Win32::System::Com::StructuredStorage::{PropVariantClear, PROPVARIANT};

    // PKEY_AudioEndpoint_FormFactor and PKEY_Device_FriendlyName
    const FORM_FACTOR: PROPERTYKEY = PROPERTYKEY { fmtid: GUID::from_u128(0x1da5d803_d492_4edd_8c23_e0c0ffee7f0e), pid: 0 };
    const FRIENDLY_NAME: PROPERTYKEY = PROPERTYKEY { fmtid: GUID::from_u128(0xa45c254e_df1c_4efd_8020_67d146a850e0), pid: 14 };

    /// One-shot, read-only: COM lives for exactly this call, in its own apartment.
    pub fn default_render() -> windows::core::Result<(String, String, u32)> {
        unsafe {
            let init = CoInitializeEx(None, COINIT_APARTMENTTHREADED);
            let res = (|| {
                let enumerator: IMMDeviceEnumerator = CoCreateInstance(&MMDeviceEnumerator, None, CLSCTX_ALL)?;
                let device = enumerator.GetDefaultAudioEndpoint(eRender, eConsole)?;
                let id = {
                    let p: PWSTR = device.GetId()?;
                    let s = p.to_string().unwrap_or_default();
                    CoTaskMemFree(Some(p.0 as *const _));
                    s
                };
                let store = device.OpenPropertyStore(STGM_READ)?;
                let name = {
                    let mut v: PROPVARIANT = store.GetValue(&FRIENDLY_NAME)?;
                    let s = v.to_string();
                    let _ = PropVariantClear(&mut v);
                    s
                };
                let ff = {
                    let mut v: PROPVARIANT = store.GetValue(&FORM_FACTOR)?;
                    let n = u32::try_from(&v).unwrap_or(10);
                    let _ = PropVariantClear(&mut v);
                    n
                };
                Ok((name, id, ff))
            })();
            if init.is_ok() {
                CoUninitialize();
            }
            res
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn headphones_and_headsets_are_headphones_everything_else_is_not() {
        for (ff, kind, hp) in [(1, "speakers", false), (3, "headphones", true), (5, "headset", true), (9, "display", false), (10, "unknown", false), (99, "unknown", false)] {
            assert_eq!(classify(ff), (kind, hp), "form factor {ff}");
        }
    }

    #[test]
    fn json_carries_the_verdict() {
        let v = to_json("Speakers (Realtek)", "{0.0.0}", 1);
        assert_eq!(v["ok"], true);
        assert_eq!(v["is_headphones"], false);
        assert_eq!(v["kind"], "speakers");
        assert_eq!(error_json("x")["ok"], false);
    }
}
