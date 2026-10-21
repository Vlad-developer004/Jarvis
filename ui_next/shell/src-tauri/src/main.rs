// The Jarvis window: a Tauri shell around web/app.html, started by the Python core (ui_next/shell.py).
// The core feeds it through a local bridge; the tray menu's Quit ends the shell, and the core follows.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::atomic::{AtomicBool, Ordering};
use std::{thread, time::Duration};
use sysinfo::{Disks, Networks, System};
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Emitter, Manager, PhysicalPosition, PhysicalSize, WebviewUrl, WebviewWindow, WebviewWindowBuilder, WindowEvent};

/// Is the main window on screen (not in the tray, not minimized). WebView2 keeps reporting `document.hidden == false` for such a window, so the page
/// would go on drawing at the display rate: the shell tells it, and the sensor thread rests meanwhile.
static VISIBLE: AtomicBool = AtomicBool::new(true);

fn set_visible(app: &AppHandle, visible: bool) {
    if VISIBLE.swap(visible, Ordering::Relaxed) != visible {
        let _ = app.emit_to("main", "jarvis-visibility", visible);
    }
}

/// Discovery file written by the Python core ({port, token, pid}); None when the core is not running.
#[tauri::command]
fn bridge_info() -> Option<String> {
    for var in ["APPDATA", "LOCALAPPDATA"] {
        if let Ok(base) = std::env::var(var) {
            if let Ok(text) = std::fs::read_to_string(std::path::Path::new(&base).join("Jarvis").join("ui_bridge.json")) {
                return Some(text);
            }
        }
    }
    None
}

/// "full" or "lite": the effects level the page starts with (JARVIS_Q is set by tests and low-power setups).
#[tauri::command]
fn get_quality() -> String {
    std::env::var("JARVIS_Q").unwrap_or_else(|_| "full".into())
}

/// Window placement survives restarts; the file lives next to the core's other settings.
fn state_path() -> Option<std::path::PathBuf> {
    let base = std::env::var("LOCALAPPDATA").or_else(|_| std::env::var("APPDATA")).ok()?;
    Some(std::path::Path::new(&base).join("Jarvis").join("ui_window.json"))
}

fn save_state(win: &WebviewWindow) {
    let (Some(path), Ok(pos), Ok(size)) = (state_path(), win.outer_position(), win.inner_size()) else { return };
    let maximized = win.is_maximized().unwrap_or(false);
    // a maximized or minimized window reports the screen's geometry: keep the last normal one instead
    let old: serde_json::Value = std::fs::read_to_string(&path).ok().and_then(|t| serde_json::from_str(&t).ok()).unwrap_or_default();
    let minimized = win.is_minimized().unwrap_or(false);
    let normal = if maximized || minimized { old.get("normal").cloned() } else { Some(serde_json::json!([pos.x, pos.y, size.width, size.height])) };
    let _ = std::fs::create_dir_all(path.parent().unwrap());
    let _ = std::fs::write(path, serde_json::json!({ "normal": normal, "maximized": maximized }).to_string());
}

/// Puts the window where it was, unless that place is gone (a monitor was unplugged, the layout changed): then it stays centred.
fn restore_state(win: &WebviewWindow) {
    let Some(text) = state_path().and_then(|p| std::fs::read_to_string(p).ok()) else { return };
    let Ok(v) = serde_json::from_str::<serde_json::Value>(&text) else { return };
    if let Some([x, y, w, h]) = v.get("normal").and_then(|n| serde_json::from_value::<[i64; 4]>(n.clone()).ok()) {
        // the title bar must be reachable: at least 120x40 px of the window's top-left corner on some monitor
        let on_screen = win.available_monitors().unwrap_or_default().iter().any(|m| {
            let (p, s) = (m.position(), m.size());
            x + 120 <= p.x as i64 + s.width as i64 && x + w.min(120) > p.x as i64 && y + 40 <= p.y as i64 + s.height as i64 && y >= p.y as i64 - 8
        });
        if on_screen && w >= 560 && h >= 400 {
            let _ = win.set_size(PhysicalSize::new(w as u32, h as u32));
            let _ = win.set_position(PhysicalPosition::new(x as i32, y as i32));
        }
    }
    if v.get("maximized").and_then(|b| b.as_bool()).unwrap_or(false) {
        let _ = win.maximize();
    }
}

/// The small always-on-top monitor (pinned, compact and transparent modes); one instance, brought forward when opened again.
#[tauri::command]
async fn open_perf_mini(app: AppHandle) -> Result<(), String> {
    if let Some(w) = app.get_webview_window("perfmini") {
        let _ = w.show();
        let _ = w.set_focus();
        return Ok(());
    }
    WebviewWindowBuilder::new(&app, "perfmini", WebviewUrl::App("perfmini.html".into()))
        .title("Jarvis: монитор")
        .inner_size(300.0, 232.0)
        .resizable(false)
        .decorations(false)
        .transparent(true)
        .shadow(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .build()
        .map(|_| ())
        .map_err(|e| e.to_string())
}

/// Width of the pop-up window in CSS pixels (the card is 24rem wide plus its margins); its height follows the content.
const POPUP_W: f64 = 440.0;
const POPUP_MARGIN: i32 = 8;

/// A transparent, always-on-top window in the corner of the screen for what the assistant tells the user (an answer card, a reminder): it is
/// visible over any program, also while the main window sits in the tray, and it never takes the keyboard focus. Hidden until it has content.
fn build_popup(app: &AppHandle) -> tauri::Result<WebviewWindow> {
    WebviewWindowBuilder::new(app, "popup", WebviewUrl::App("popup.html".into()))
        .title("Jarvis: уведомление")
        .inner_size(POPUP_W, 120.0)
        .resizable(false)
        .decorations(false)
        .transparent(true)
        .shadow(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .focusable(false)
        .focused(false)
        .visible(false)
        .build()
}

#[cfg(windows)]
mod user32 {
    #[link(name = "user32")]
    extern "system" {
        pub fn ShowWindow(hwnd: isize, cmd: i32) -> i32;
    }
}

/// Shows a window without activating it: `show()` makes the program the foreground one, which would take the keyboard from what the user is typing.
fn show_without_focus(win: &WebviewWindow) {
    #[cfg(windows)]
    if let Ok(hwnd) = win.hwnd() {
        const SW_SHOWNOACTIVATE: i32 = 4;
        // SAFETY: a plain Win32 call on the window handle of a live window
        unsafe { user32::ShowWindow(hwnd.0 as isize, SW_SHOWNOACTIVATE) };
        return;
    }
    let _ = win.show();
}

/// Sizes the pop-up to its content (`height` in CSS pixels), puts it in the bottom right corner of the primary monitor's work area (above the
/// taskbar) and shows it without activating it.
#[tauri::command]
fn popup_fit(app: AppHandle, height: f64) -> Result<(), String> {
    let win = app.get_webview_window("popup").ok_or("no pop-up window")?;
    let scale = win.scale_factor().map_err(|e| e.to_string())?;
    let (w, h) = ((POPUP_W * scale).round() as u32, (height.clamp(40.0, 1200.0) * scale).round() as u32);
    let monitor = win.primary_monitor().map_err(|e| e.to_string())?.ok_or("no monitor")?;
    let area = monitor.work_area();
    let x = area.position.x + area.size.width as i32 - w as i32 - POPUP_MARGIN;
    let y = area.position.y + area.size.height as i32 - h as i32 - POPUP_MARGIN;
    win.set_size(PhysicalSize::new(w, h)).map_err(|e| e.to_string())?;
    win.set_position(PhysicalPosition::new(x, y)).map_err(|e| e.to_string())?;
    if !win.is_visible().unwrap_or(false) {
        show_without_focus(&win);
    }
    Ok(())
}

#[tauri::command]
fn popup_hide(app: AppHandle) {
    if let Some(w) = app.get_webview_window("popup") {
        let _ = w.hide();
    }
}

fn show_main(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.unminimize();
        let _ = w.set_focus();
        set_visible(app, true);
    }
}

/// The core asks for the window (a spoken "open settings", a question that must be answered): out of the tray, in front.
#[tauri::command]
fn show_window(app: AppHandle) {
    show_main(&app);
}

fn main() {
    tauri::Builder::default()
        // a second launch brings the running window forward instead of opening another one
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| show_main(app)))
        .invoke_handler(tauri::generate_handler![bridge_info, get_quality, open_perf_mini, show_window, popup_fit, popup_hide])
        .setup(move |app| {
            // JARVIS_PAGE and JARVIS_SIZE (WxH) are for tests: another page, a fixed size without restoring the saved placement
            let page = std::env::var("JARVIS_PAGE").unwrap_or_else(|_| "app".into());
            let (w, h) = std::env::var("JARVIS_SIZE")
                .ok()
                .and_then(|v| v.split_once('x').and_then(|(a, b)| Some((a.parse::<f64>().ok()?, b.parse::<f64>().ok()?))))
                .unwrap_or((1280.0, 720.0));
            // the window starts hidden so a restored position does not flash the default one
            let restore = std::env::var("JARVIS_SIZE").is_err();
            let win = WebviewWindowBuilder::new(app, "main", WebviewUrl::App(format!("{page}.html").into()))
                .title("Jarvis")
                .inner_size(w, h)
                .min_inner_size(560.0, 400.0)
                .resizable(true)
                .decorations(true)
                .fullscreen(std::env::var("JARVIS_FULLSCREEN").is_ok())
                .visible(!restore)
                .build()?;
            if restore {
                restore_state(&win);
                let _ = win.show();
            }
            build_popup(app.handle())?;
            // the close button hides the window to the tray, the tray menu quits
            let closing = win.clone();
            win.on_window_event(move |ev| {
                match ev {
                    WindowEvent::CloseRequested { api, .. } => {
                        api.prevent_close();
                        save_state(&closing);
                        let _ = closing.hide();
                        set_visible(closing.app_handle(), false);
                    }
                    // a minimize and a restore both arrive as a resize
                    WindowEvent::Resized(_) => set_visible(closing.app_handle(), !closing.is_minimized().unwrap_or(false)),
                    _ => {}
                }
            });
            let open = MenuItem::with_id(app, "open", "Открыть Jarvis", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Выход", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open, &quit])?;
            let mut tray = TrayIconBuilder::new()
                .tooltip("Jarvis")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, ev| match ev.id().as_ref() {
                    "open" => show_main(app),
                    "quit" => {
                        if let Some(w) = app.get_webview_window("main") {
                            save_state(&w);
                        }
                        app.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, ev| {
                    if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. } = ev {
                        show_main(tray.app_handle());
                    }
                });
            if let Some(icon) = app.default_window_icon() {
                tray = tray.icon(icon.clone());
            }
            tray.build(app)?;
            // CPU, memory, disk and network numbers for the dashboard, once a second
            let handle = app.handle().clone();
            thread::spawn(move || {
                let mut sys = System::new();
                let mut disks = Disks::new_with_refreshed_list();
                let mut nets = Networks::new_with_refreshed_list();
                loop {
                    // nobody looks at the numbers while the main window is away, unless the small monitor is open
                    let monitor = handle.get_webview_window("perfmini").and_then(|w| w.is_visible().ok()).unwrap_or(false);
                    if !VISIBLE.load(Ordering::Relaxed) && !monitor {
                        thread::sleep(Duration::from_secs(2));
                        continue;
                    }
                    sys.refresh_cpu_usage();
                    sys.refresh_memory();
                    let cpu = sys.global_cpu_usage();
                    let ram = sys.used_memory() as f64 / sys.total_memory().max(1) as f64 * 100.0;
                    disks.refresh(true);
                    nets.refresh(true);
                    let disk = disks
                        .list()
                        .iter()
                        .find(|d| d.mount_point().to_string_lossy().starts_with("C:"))
                        .map(|d| (d.total_space() - d.available_space()) as f64 / d.total_space().max(1) as f64 * 100.0)
                        .unwrap_or(0.0);
                    let (rx, tx) = nets.iter().fold((0u64, 0u64), |a, (_, n)| (a.0 + n.received(), a.1 + n.transmitted()));
                    let _ = handle.emit("sensors", serde_json::json!({ "cpu": cpu, "ram": ram, "disk": disk, "down": rx as f64 / 1024.0, "up": tx as f64 / 1024.0 }));
                    thread::sleep(Duration::from_secs(1));
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
