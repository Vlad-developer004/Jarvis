//! jarvis_win: window and process enumeration for Jarvis (see docs/native.md).
//! One call returns everything the window-picking code needs, instead of several Win32 calls per window from Python.
use pyo3::prelude::*;

/// Crate version, used by core/native.py to confirm the module loaded.
#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

/// Last path component of a Windows path, lower-cased ("C:\\Program Files\\Brave\\brave.exe" -> "brave.exe").
fn exe_name(path: &str) -> String {
    path.rsplit(['\\', '/']).next().unwrap_or("").to_lowercase()
}

/// A window as `(hwnd, title, exe, visible, iconic, class_name)`. `exe` is the lower-case file name of the owning process ("" when it
/// cannot be read, e.g. for protected processes).
type Row = (isize, String, String, bool, bool, String);

#[cfg(windows)]
mod imp {
    use super::{exe_name, Row};
    use windows::core::{BOOL, PWSTR};
    use windows::Win32::Foundation::{CloseHandle, HWND, LPARAM};
    use windows::Win32::System::Threading::{OpenProcess, QueryFullProcessImageNameW, PROCESS_NAME_WIN32, PROCESS_QUERY_LIMITED_INFORMATION};
    use windows::Win32::UI::WindowsAndMessaging::{
        EnumWindows, GetClassNameW, GetWindowTextLengthW, GetWindowTextW, GetWindowThreadProcessId, IsIconic, IsWindowVisible,
    };

    fn title_of(hwnd: HWND) -> String {
        unsafe {
            let n = GetWindowTextLengthW(hwnd);
            if n <= 0 {
                return String::new();
            }
            let mut buf = vec![0u16; n as usize + 1];
            let got = GetWindowTextW(hwnd, &mut buf);
            String::from_utf16_lossy(&buf[..got.max(0) as usize])
        }
    }

    fn class_of(hwnd: HWND) -> String {
        let mut buf = [0u16; 256];
        let n = unsafe { GetClassNameW(hwnd, &mut buf) };
        String::from_utf16_lossy(&buf[..n.max(0) as usize])
    }

    fn exe_of(pid: u32, cache: &mut std::collections::HashMap<u32, String>) -> String {
        if let Some(v) = cache.get(&pid) {
            return v.clone();
        }
        let name = unsafe {
            match OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, pid) {
                Ok(h) => {
                    let mut buf = [0u16; 520];
                    let mut len = buf.len() as u32;
                    let ok = QueryFullProcessImageNameW(h, PROCESS_NAME_WIN32, PWSTR(buf.as_mut_ptr()), &mut len).is_ok();
                    let _ = CloseHandle(h);
                    if ok {
                        exe_name(&String::from_utf16_lossy(&buf[..len as usize]))
                    } else {
                        String::new()
                    }
                }
                Err(_) => String::new(),
            }
        };
        cache.insert(pid, name.clone());
        name
    }

    struct State {
        rows: Vec<Row>,
        exes: std::collections::HashMap<u32, String>,
        visible_only: bool,
    }

    unsafe extern "system" fn each(hwnd: HWND, lparam: LPARAM) -> BOOL {
        let st = &mut *(lparam.0 as *mut State);
        let visible = IsWindowVisible(hwnd).as_bool();
        if st.visible_only && !visible {
            return BOOL(1);
        }
        let mut pid = 0u32;
        GetWindowThreadProcessId(hwnd, Some(&mut pid));
        let (title, exe) = (title_of(hwnd), exe_of(pid, &mut st.exes));
        st.rows.push((hwnd.0 as isize, title, exe, visible, IsIconic(hwnd).as_bool(), class_of(hwnd)));
        BOOL(1)
    }

    pub fn list(visible_only: bool) -> Vec<Row> {
        let mut st = State { rows: Vec::new(), exes: Default::default(), visible_only };
        unsafe {
            let _ = EnumWindows(Some(each), LPARAM(&mut st as *mut State as isize));
        }
        st.rows
    }
}

/// Every top-level window in z-order: `(hwnd, title, exe, visible, iconic, class_name)`; with `visible_only` the hidden ones are left out.
/// Windows with neither a title nor a readable process are returned too, so the caller keeps its own rules for what counts.
#[pyfunction]
#[pyo3(signature = (visible_only=false))]
fn list_windows(py: Python<'_>, visible_only: bool) -> Vec<Row> {
    #[cfg(windows)]
    {
        py.detach(|| imp::list(visible_only))
    }
    #[cfg(not(windows))]
    {
        let _ = (py, visible_only);
        Vec::new()
    }
}

#[pymodule]
fn jarvis_win(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(list_windows, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::exe_name;

    #[test]
    fn exe_name_is_the_lower_case_file_name() {
        assert_eq!(exe_name(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"), "brave.exe");
        assert_eq!(exe_name("C:/x/Chrome.EXE"), "chrome.exe");
        assert_eq!(exe_name("notepad.exe"), "notepad.exe");
        assert_eq!(exe_name(""), "");
    }
}
