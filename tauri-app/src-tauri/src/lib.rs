use std::io::{BufRead, BufReader};
use std::process::Command;
use tauri::Manager;
use tauri::Emitter;
use serde::{Deserialize, Serialize};

// ── Parameter mappings ──────────────────────────────────────────────────────

fn intensity_params(value: u32) -> (f64, f64, f64, f64) {
    match value {
        0  => (0.005, 0.005, 0.002, 0.002),
        25 => (0.010, 0.010, 0.004, 0.004),
        50 => (0.020, 0.020, 0.005, 0.005),
        75 => (0.030, 0.030, 0.010, 0.010),
        _  => (0.040, 0.040, 0.010, 0.010),
    }
}

fn quality_params(value: u32) -> (u32, u32, u32) {
    match value {
        0  => (80,  30, 10),
        50 => (150, 50, 20),
        _  => (250, 80, 30),
    }
}

// ── Progress event ──────────────────────────────────────────────────────────

#[derive(Serialize, Deserialize, Clone)]
struct AttackProgress {
    stage: String,
    message: String,
    percent: f64,
}

// ── Engine resolution ───────────────────────────────────────────────────────

enum EngineMode {
    Compiled(String),
    PythonDev(String),
}

fn resolve_engine(app_handle: &tauri::AppHandle) -> Result<EngineMode, String> {
    let exe_name = if cfg!(windows) {
        "vidscratch_engine.exe"
    } else {
        "vidscratch_engine"
    };

    if let Ok(dir) = std::env::var("VIDSCRATCH_DIR") {
        let compiled = std::path::Path::new(&dir).join(exe_name);
        if compiled.exists() {
            return Ok(EngineMode::Compiled(compiled.to_string_lossy().into()));
        }
        let script = std::path::Path::new(&dir).join("attack.py");
        if script.exists() {
            eprintln!("[dev mode] Using python {}", script.display());
            return Ok(EngineMode::PythonDev(script.to_string_lossy().into()));
        }
    }

    if let Ok(resource_dir) = app_handle.path().resource_dir() {
        let p = resource_dir.join("engine").join(exe_name);
        if p.exists() {
            return Ok(EngineMode::Compiled(p.to_string_lossy().into()));
        }
    }

    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(parent) = exe_path.parent() {
            for sub in &["engine", "."] {
                let p = parent.join(sub).join(exe_name);
                if p.exists() {
                    return Ok(EngineMode::Compiled(p.to_string_lossy().into()));
                }
            }
        }
    }

    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(parent) = exe_path.parent() {
            for ancestor in parent.ancestors() {
                let p = ancestor.join("python").join("attack.py");
                if p.exists() {
                    eprintln!("[auto-detect] Found python at {}", p.display());
                    return Ok(EngineMode::PythonDev(p.to_string_lossy().into()));
                }
            }
        }
    }

    if let Ok(cwd) = std::env::current_dir() {
        for ancestor in cwd.ancestors() {
            let p = ancestor.join("python").join("attack.py");
            if p.exists() {
                eprintln!("[auto-detect] Found python at {}", p.display());
                return Ok(EngineMode::PythonDev(p.to_string_lossy().into()));
            }
        }
    }

    Err(
        "Cannot find attack engine.\n\
         • Development: set VIDSCRATCH_DIR=/path/to/python/ folder\n\
         • Production: run build_engine.py first, then copy dist/vidscratch_engine/ to src-tauri/engine/"
            .into(),
    )
}

// ── Main attack command ─────────────────────────────────────────────────────

#[tauri::command]
async fn run_attack(
    app_handle: tauri::AppHandle,
    video_path: String,
    output_dir: String,
    intensity: u32,
    quality: u32,
) -> Result<String, String> {
    if video_path.is_empty() {
        return Err("No video selected".into());
    }
    if output_dir.is_empty() {
        return Err("No output directory selected".into());
    }

    let engine = resolve_engine(&app_handle)?;
    let (noise_clamp, ssim_budget, noise_step, ssim_step) = intensity_params(intensity);
    let (max_iter, bo_iter, max_attempts) = quality_params(quality);

    let _ = app_handle.emit("attack-progress", AttackProgress {
        stage: "starting".into(),
        message: "Initializing...".into(),
        percent: 0.0,
    });

    let mut cmd = match &engine {
        EngineMode::Compiled(path) => Command::new(path),
        EngineMode::PythonDev(script) => {
            let mut c = Command::new("python");
            c.arg(script);
            c
        }
    };

    cmd.arg("--video").arg(&video_path)
        .arg("--output-dir").arg(&output_dir)
        .arg("--shortcut")
        .arg("--noise-clamp").arg(format!("{:.4}", noise_clamp))
        .arg("--ssim-budget").arg(format!("{:.4}", ssim_budget))
        .arg("--noise-step").arg(format!("{:.4}", noise_step))
        .arg("--ssim-step").arg(format!("{:.4}", ssim_step))
        .arg("--max-iter").arg(max_iter.to_string())
        .arg("--bo-iter").arg(bo_iter.to_string())
        .arg("--max-attempts").arg(max_attempts.to_string())
        .arg("--json-output");

    // Spawn with piped stderr so we can read progress lines
    let mut child = cmd
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .map_err(|e| {
            let hint = match &engine {
                EngineMode::PythonDev(_) => " Make sure Python is installed and in PATH.",
                EngineMode::Compiled(_) => " The engine binary may be corrupted.",
            };
            format!("Failed to run engine: {}.{}", e, hint)
        })?;

    // Read stderr in a background thread, parse PROGRESS lines, emit events
    let stderr = child.stderr.take().unwrap();
    let app_for_thread = app_handle.clone();
    let stderr_thread = std::thread::spawn(move || {
        let reader = BufReader::new(stderr);
        for line in reader.lines() {
            if let Ok(line) = line {
                // Parse progress lines: "PROGRESS:45:Running BO..."
                if line.starts_with("PROGRESS:") {
                    let parts: Vec<&str> = line.splitn(3, ':').collect();
                    if parts.len() >= 3 {
                        if let Ok(pct) = parts[1].parse::<f64>() {
                            let msg = parts[2].to_string();
                            let _ = app_for_thread.emit("attack-progress", AttackProgress {
                                stage: "running".into(),
                                message: msg,
                                percent: pct,
                            });
                        }
                    }
                }
                // Always print to terminal too
                eprintln!("{}", line);
            }
        }
    });

    let output = child.wait_with_output().map_err(|e| format!("Engine error: {}", e))?;
    let _ = stderr_thread.join();

    if !output.status.success() {
        let _ = app_handle.emit("attack-progress", AttackProgress {
            stage: "error".into(),
            message: "Attack failed (see terminal for details)".into(),
            percent: 0.0,
        });
        return Err(format!("Engine exited with code {:?}", output.status.code()));
    }

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();

    let _ = app_handle.emit("attack-progress", AttackProgress {
        stage: "done".into(),
        message: "Attack completed successfully!".into(),
        percent: 100.0,
    });

    Ok(stdout)
}

// ── Greet ────────────────────────────────────────────────────────────────────

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

// ── App entry ───────────────────────────────────────────────────────────────

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![greet, run_attack])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}