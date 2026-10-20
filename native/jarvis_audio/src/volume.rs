//! Core Audio sessions: list them, lower and restore them for ducking, set one app's or the master volume.
//! Everything runs on the thread that called `Audio::new()`, which keeps COM initialised for its whole life.
use crate::duck::{target_for, Counter, Step};
use serde_json::{json, Value};
use std::collections::HashMap;
use windows::core::{Interface, PWSTR};
use windows::Win32::Foundation::CloseHandle;
use windows::Win32::Media::Audio::Endpoints::IAudioEndpointVolume;
use windows::Win32::Media::Audio::{
    eConsole, eRender, IAudioSessionControl, IAudioSessionControl2, IAudioSessionManager2, IMMDeviceEnumerator,
    ISimpleAudioVolume, MMDeviceEnumerator,
};
use windows::Win32::System::Com::{CoCreateInstance, CoInitializeEx, CoTaskMemFree, CoUninitialize, CLSCTX_ALL, COINIT_APARTMENTTHREADED};
use windows::Win32::System::Threading::{OpenProcess, QueryFullProcessImageNameW, PROCESS_NAME_WIN32, PROCESS_QUERY_LIMITED_INFORMATION};

pub struct Session {
    pub pid: u32,
    pub id: String,
    pub name: String,
    pub volume: f32,
    pub muted: bool,
    pub system: bool,
    vol: ISimpleAudioVolume,
}

pub struct Audio {
    com: bool,
    counter: Counter,
    saved: HashMap<String, f32>,
}

fn wstr(p: PWSTR) -> String {
    let s = unsafe { p.to_string() }.unwrap_or_default();
    unsafe { CoTaskMemFree(Some(p.0 as *const _)) };
    s
}

fn process_name(pid: u32) -> String {
    if pid == 0 {
        return String::new();
    }
    unsafe {
        let Ok(h) = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, pid) else { return String::new() };
        let mut buf = [0u16; 520];
        let mut len = buf.len() as u32;
        let ok = QueryFullProcessImageNameW(h, PROCESS_NAME_WIN32, PWSTR(buf.as_mut_ptr()), &mut len).is_ok();
        let _ = CloseHandle(h);
        if !ok {
            return String::new();
        }
        let path = String::from_utf16_lossy(&buf[..len as usize]);
        path.rsplit(['\\', '/']).next().unwrap_or("").to_lowercase()
    }
}

fn sessions() -> windows::core::Result<Vec<Session>> {
    unsafe {
        let enumerator: IMMDeviceEnumerator = CoCreateInstance(&MMDeviceEnumerator, None, CLSCTX_ALL)?;
        let device = enumerator.GetDefaultAudioEndpoint(eRender, eConsole)?;
        let mgr: IAudioSessionManager2 = device.Activate(CLSCTX_ALL, None)?;
        let list = mgr.GetSessionEnumerator()?;
        let mut out = Vec::new();
        for i in 0..list.GetCount()? {
            let Ok(ctl): windows::core::Result<IAudioSessionControl> = list.GetSession(i) else { continue };
            let (Ok(c2), Ok(vol)) = (ctl.cast::<IAudioSessionControl2>(), ctl.cast::<ISimpleAudioVolume>()) else { continue };
            let pid = c2.GetProcessId().unwrap_or(0);
            let id = c2.GetSessionInstanceIdentifier().map(wstr).unwrap_or_default();
            let volume = vol.GetMasterVolume().unwrap_or(1.0);
            let muted = vol.GetMute().map(|b| b.as_bool()).unwrap_or(false);
            let system = c2.IsSystemSoundsSession().0 == 0; // S_OK means "this is the system sounds session"
            out.push(Session { pid, id, name: process_name(pid), volume, muted, system, vol });
        }
        Ok(out)
    }
}

fn master() -> windows::core::Result<IAudioEndpointVolume> {
    unsafe {
        let enumerator: IMMDeviceEnumerator = CoCreateInstance(&MMDeviceEnumerator, None, CLSCTX_ALL)?;
        enumerator.GetDefaultAudioEndpoint(eRender, eConsole)?.Activate(CLSCTX_ALL, None)
    }
}

fn err(e: windows::core::Error) -> Value {
    json!({"ok": false, "error": e.to_string()})
}

impl Audio {
    pub fn new() -> Self {
        let com = unsafe { CoInitializeEx(None, COINIT_APARTMENTTHREADED) }.is_ok();
        Audio { com, counter: Counter::default(), saved: HashMap::new() }
    }

    pub fn list(&self) -> Value {
        match sessions() {
            Ok(v) => {
                let items: Vec<Value> = v
                    .iter()
                    .map(|s| json!({"pid": s.pid, "id": s.id, "name": s.name, "volume": s.volume, "muted": s.muted, "system": s.system}))
                    .collect();
                json!({"ok": true, "sessions": items})
            }
            Err(e) => err(e),
        }
    }

    /// Lower the other apps while Jarvis speaks. Nested calls are counted; `skip_pid` is Jarvis itself.
    pub fn duck(&mut self, enable: bool, skip_pid: u32) -> Value {
        let step = if enable { self.counter.enable() } else { self.counter.disable(!self.saved.is_empty()) };
        match step {
            Step::Lower => {
                self.saved.clear();
                let Ok(list) = sessions() else { return json!({"ok": true, "lowered": 0}) };
                let own = std::process::id(); // this program plays Jarvis's own voice: it is never lowered
                for s in list.iter().filter(|s| s.pid != 0 && s.pid != skip_pid && s.pid != own && !s.system) {
                    if let Some(t) = target_for(s.volume) {
                        if unsafe { s.vol.SetMasterVolume(t, std::ptr::null()) }.is_ok() {
                            self.saved.insert(s.id.clone(), s.volume);
                        }
                    }
                }
                json!({"ok": true, "lowered": self.saved.len()})
            }
            Step::Restore => json!({"ok": true, "restored": self.restore()}),
            Step::Nothing => json!({"ok": true}),
        }
    }

    /// Force everything back to its saved level and forget the nesting depth.
    pub fn unduck(&mut self) -> Value {
        self.counter.reset();
        json!({"ok": true, "restored": self.restore()})
    }

    fn restore(&mut self) -> usize {
        let saved = std::mem::take(&mut self.saved);
        if saved.is_empty() {
            return 0;
        }
        let Ok(list) = sessions() else { return 0 };
        let mut n = 0;
        for s in list {
            if let Some(v) = saved.get(&s.id) {
                if unsafe { s.vol.SetMasterVolume(*v, std::ptr::null()) }.is_ok() {
                    n += 1;
                }
            }
        }
        n
    }

    /// Set one app's volume (0.0..=1.0) by process name, e.g. "spotify.exe"; every session of that program changes.
    pub fn set_app(&mut self, name: &str, level: f32) -> Value {
        let level = level.clamp(0.0, 1.0);
        let want = name.to_lowercase();
        match sessions() {
            Ok(list) => {
                let mut n = 0;
                for s in list.iter().filter(|s| !s.name.is_empty() && s.name == want) {
                    if unsafe { s.vol.SetMasterVolume(level, std::ptr::null()) }.is_ok() {
                        n += 1;
                    }
                }
                json!({"ok": n > 0, "changed": n})
            }
            Err(e) => err(e),
        }
    }

    /// Set one session (by the `id` that `list` reports) to `level` (0.0..=1.0) and report the volume it ended up at.
    pub fn set_session(&mut self, id: &str, level: f32) -> Value {
        let level = level.clamp(0.0, 1.0);
        match sessions() {
            Ok(list) => match list.iter().find(|s| s.id == id) {
                Some(s) => match unsafe { s.vol.SetMasterVolume(level, std::ptr::null()).and_then(|_| s.vol.GetMasterVolume()) } {
                    Ok(v) => json!({"ok": true, "volume": v}),
                    Err(e) => err(e),
                },
                None => json!({"ok": false, "error": "no such session"}),
            },
            Err(e) => err(e),
        }
    }

    pub fn master_get(&self) -> Value {
        match master().and_then(|m| unsafe { Ok((m.GetMasterVolumeLevelScalar()?, m.GetMute()?.as_bool())) }) {
            Ok((level, muted)) => json!({"ok": true, "level": level, "muted": muted}),
            Err(e) => err(e),
        }
    }

    pub fn master_set(&self, level: Option<f32>, muted: Option<bool>) -> Value {
        let r = master().and_then(|m| unsafe {
            if let Some(l) = level {
                m.SetMasterVolumeLevelScalar(l.clamp(0.0, 1.0), std::ptr::null())?;
            }
            if let Some(b) = muted {
                m.SetMute(b, std::ptr::null())?;
            }
            Ok(())
        });
        match r {
            Ok(()) => self.master_get(),
            Err(e) => err(e),
        }
    }
}

impl Drop for Audio {
    /// Whatever the exit path (parent gone, protocol error), nothing stays lowered.
    fn drop(&mut self) {
        let _ = self.restore();
        if self.com {
            unsafe { CoUninitialize() };
        }
    }
}
