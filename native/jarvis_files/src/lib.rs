//! jarvis_files: fast directory walking for file and folder search (see docs/native.md).
//! The matching itself (name variants, fuzzy scores) stays in Python; this only lists what is on disk.
use ignore::{WalkBuilder, WalkState};
use pyo3::prelude::*;
use std::collections::HashSet;
use std::path::Path;
use std::sync::{Arc, Mutex};
use std::time::UNIX_EPOCH;

/// Crate version, used by core/native.py to confirm the module loaded.
#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

fn ext_of(name: &str) -> String {
    match name.rfind('.') {
        Some(i) if i > 0 && i + 1 < name.len() => name[i..].to_lowercase(),
        _ => String::new(),
    }
}

/// List files or folders under `roots`, at most `max_depth` levels below each root (a root's children are level 1).
///
/// - `want`: "files" or "dirs".
/// - `exts` / `skip_exts`: lower-case suffixes with the dot (".pdf"); `exts=None` accepts every file type.
/// - `skip_dirs`: folder names (compared lower-case) that are neither listed nor entered; names starting with "." are skipped
///   too when `skip_hidden` is set.
///
/// Returns `(parent_dir, name, mtime_seconds)` sorted by path; `mtime` is 0.0 for folders. Unreadable entries are skipped.
/// Symbolic links are not followed, as with `os.walk`.
#[pyfunction]
#[allow(clippy::too_many_arguments)] // mirrors the keyword arguments of the Python call
#[pyo3(signature = (roots, max_depth, want="files", exts=None, skip_exts=Vec::new(), skip_dirs=Vec::new(), skip_hidden=true))]
fn walk(
    py: Python<'_>,
    roots: Vec<String>,
    max_depth: usize,
    want: &str,
    exts: Option<Vec<String>>,
    skip_exts: Vec<String>,
    skip_dirs: Vec<String>,
    skip_hidden: bool,
) -> PyResult<Vec<(String, String, f64)>> {
    let files = match want {
        "files" => true,
        "dirs" => false,
        _ => return Err(pyo3::exceptions::PyValueError::new_err("want must be 'files' or 'dirs'")),
    };
    let roots: Vec<String> = roots.into_iter().filter(|r| Path::new(r).is_dir()).collect();
    if roots.is_empty() || max_depth == 0 {
        return Ok(Vec::new());
    }
    let exts: Option<HashSet<String>> = exts.map(|v| v.into_iter().map(|e| e.to_lowercase()).collect());
    let skip_exts: HashSet<String> = skip_exts.into_iter().map(|e| e.to_lowercase()).collect();
    let skip_dirs: HashSet<String> = skip_dirs.into_iter().map(|d| d.to_lowercase()).collect();

    let found: Arc<Mutex<Vec<(String, String, f64)>>> = Arc::new(Mutex::new(Vec::new()));
    py.detach(|| {
        let mut builder = WalkBuilder::new(&roots[0]);
        for r in &roots[1..] {
            builder.add(r);
        }
        builder.standard_filters(false).hidden(false).follow_links(false).max_depth(Some(max_depth));
        let (hide, skip) = (skip_hidden, skip_dirs.clone());
        builder.filter_entry(move |e| {
            if e.depth() == 0 || !e.file_type().is_some_and(|t| t.is_dir()) {
                return true;
            }
            let name = e.file_name().to_string_lossy();
            !((hide && name.starts_with('.')) || skip.contains(&name.to_lowercase()))
        });
        builder.build_parallel().run(|| {
            let found = Arc::clone(&found);
            let (exts, skip_exts) = (exts.clone(), skip_exts.clone());
            Box::new(move |res| {
                let Ok(entry) = res else { return WalkState::Continue };
                if entry.depth() == 0 {
                    return WalkState::Continue;
                }
                let Some(ft) = entry.file_type() else { return WalkState::Continue };
                let name = entry.file_name().to_string_lossy().into_owned();
                let parent = entry.path().parent().map(|p| p.to_string_lossy().into_owned()).unwrap_or_default();
                if files {
                    if !ft.is_file() {
                        return WalkState::Continue;
                    }
                    let ext = ext_of(&name);
                    match &exts {
                        Some(set) if !set.contains(&ext) => return WalkState::Continue,
                        None if skip_exts.contains(&ext) => return WalkState::Continue,
                        _ => {}
                    }
                    let Ok(meta) = entry.metadata() else { return WalkState::Continue };
                    let mtime = meta.modified().ok().and_then(|t| t.duration_since(UNIX_EPOCH).ok()).map_or(0.0, |d| d.as_secs_f64());
                    found.lock().unwrap().push((parent, name, mtime));
                } else if ft.is_dir() {
                    found.lock().unwrap().push((parent, name, 0.0));
                }
                WalkState::Continue
            })
        });
    });
    let mut out = std::mem::take(&mut *found.lock().unwrap());
    out.sort_by(|a, b| (&a.0, &a.1).cmp(&(&b.0, &b.1)));
    Ok(out)
}

#[pymodule]
fn jarvis_files(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(walk, m)?)?;
    Ok(())
}
