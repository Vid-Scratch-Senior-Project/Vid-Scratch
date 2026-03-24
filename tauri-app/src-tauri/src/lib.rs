use std::process::Command;
use tauri::Manager;
use tauri::Emitter;
use serde::{Deserialize, Serialize};

// ── Parameter mappings ──────────────────────────────────────────────────────

/// Intensity slider: 0 / 25 / 50 / 75 / 100 → Very Low / Low / Mid / High / Very High
fn intensity_params(value: u32) -> (f64, f64, f64, f64) {
    // Returns (noise_clamp, ssim_budget, noise_step, ssim_step)
    match value {
        0  => (0.005, 0.005, 0.002, 0.002),  // Very Low
        25 => (0.010, 0.010, 0.004, 0.004),  // Low
        50 => (0.020, 0.020, 0.005, 0.005),  // Mid
        75 => (0.030, 0.030, 0.010, 0.010),  // High
        _  => (0.040, 0.040, 0.010, 0.010),  // Very High (100)
    }
}

/// Render Quality slider: 0 / 50 / 100 → Low / Medium / High
fn quality_params(value: u32) -> (u32, u32, u32) {
    // Returns (max_iter, bo_iter, max_attempts)
    match value {
        0  => (80,  30, 10),   // Low
        50 => (150, 50, 20),   // Medium
        _  => (250, 80, 30),   // High (100)
    }
}

// ── Progress event ──────────────────────────────────────────────────────────

#[derive(Serialize, Deserialize, Clone)]
struct AttackProgress {
    stage: String,
    message: String,
}

// ── Engine resolution ───────────────────────────────────────────────────────

enum EngineMode {
    /// Compiled PyInstaller exe — for production
    Compiled(String),
    /// Raw python + attack.py — for development
    PythonDev(String),
}

/// Locate the attack engine.
///
/// Search order:
///   1. VIDSCRATCH_DIR env var
///   2. {resource_dir}/engine/  (bundled Tauri app)
///   3. Next to Tauri executable
///
/// If VIDSCRATCH_DIR contains attack.py but no compiled engine,
/// falls back to calling `python attack.py` (dev mode).
fn resolve_engine(app_handle: &tauri::AppHandle) -> Result<EngineMode, String> {
    let exe_name = if cfg!(windows) {
        "vidscratch_engine.exe"
    } else {
        "vidscratch_engine"
    };

    // 1. VIDSCRATCH_DIR env var
    if let Ok(dir) = std::env::var("VIDSCRATCH_DIR") {
        // Check for compiled engine first
        let compiled = std::path::Path::new(&dir).join(exe_name);
        if compiled.exists() {
            return Ok(EngineMode::Compiled(compiled.to_string_lossy().into()));
        }
        // Dev fallback: raw python
        let script = std::path::Path::new(&dir).join("attack.py");
        if script.exists() {
            eprintln!("[dev mode] Using python {}", script.display());
            return Ok(EngineMode::PythonDev(script.to_string_lossy().into()));
        }
    }

    // 2. Resource dir (bundled app)
    if let Ok(resource_dir) = app_handle.path().resource_dir() {
        let p = resource_dir.join("engine").join(exe_name);
        if p.exists() {
            return Ok(EngineMode::Compiled(p.to_string_lossy().into()));
        }
    }

    // 3. Next to executable
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
    // 4. Relative path: ../python/ (sibling of tauri-app/)
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(parent) = exe_path.parent() {
            // Walk up from target/debug/ to src-tauri/ to tauri-app/ to project root
            for ancestor in parent.ancestors() {
                let p = ancestor.join("python").join("attack.py");
                if p.exists() {
                    eprintln!("[auto-detect] Found python at {}", p.display());
                    return Ok(EngineMode::PythonDev(p.to_string_lossy().into()));
                }
            }
        }
    }

    // 5. Current working dir's parent
    if let Ok(cwd) = std::env::current_dir() {
        for ancestor in cwd.ancestors() {
            let p = ancestor.join("python").join("attack.py");
            if p.exists() {
                eprintln!("[auto-detect] Found python at {}", p.display());
                return Ok(EngineMode::PythonDev(p.to_string_lossy().into()));
            }
        }
    }

    Err(format!(
        "Cannot find attack engine.\n\
         • Development: set VIDSCRATCH_DIR=/path/to/python/ folder\n\
         • Production:  run build_engine.py first, then copy \
           dist/vidscratch_engine/ to src-tauri/engine/"
    ))
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
    // Validate
    if video_path.is_empty() {
        return Err("No video selected".into());
    }
    if output_dir.is_empty() {
        return Err("No output directory selected".into());
    }

    // Resolve engine
    let engine = resolve_engine(&app_handle)?;

    // Map parameters
    let (noise_clamp, ssim_budget, noise_step, ssim_step) = intensity_params(intensity);
    let (max_iter, bo_iter, max_attempts) = quality_params(quality);

    // Progress: starting
    let _ = app_handle.emit("attack-progress", AttackProgress {
        stage: "starting".into(),
        message: "Initializing attack engine...".into(),
    });

    // Build command based on engine mode
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

    // Progress: running
    let _ = app_handle.emit("attack-progress", AttackProgress {
        stage: "running".into(),
        message: format!(
            "Processing video (intensity={}, quality={})...",
            intensity, quality
        ),
    });

    // Execute
    // let output = cmd
    //     .output()
    //     .map_err(|e| {
    //         let hint = match &engine {
    //             EngineMode::PythonDev(_) =>
    //                 " Make sure Python is installed and in PATH.",
    //             EngineMode::Compiled(_) =>
    //                 " The engine binary may be corrupted or missing dependencies.",
    //         };
    //         format!("Failed to run engine: {}.{}", e, hint)
    //     })?;

    // let stderr = String::from_utf8_lossy(&output.stderr);
    // if !stderr.is_empty() {
    //     eprintln!("[engine stderr]\n{}", stderr);
    // }

    // Execute with real-time stderr logging
    let mut child = cmd
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::inherit())
        .spawn()
        .map_err(|e| {
            let hint = match &engine {
                EngineMode::PythonDev(_) =>
                    " Make sure Python is installed and in PATH.",
                EngineMode::Compiled(_) =>
                    " The engine binary may be corrupted or missing dependencies.",
            };
            format!("Failed to run engine: {}.{}", e, hint)
        })?;

    let output = child.wait_with_output()
        .map_err(|e| format!("Engine error: {}", e))?;

    if !output.status.success() {
        let _ = app_handle.emit("attack-progress", AttackProgress {
            stage: "error".into(),
            message: "Attack failed (see terminal for details)".into(),
            // message: format!("Attack failed: {}", stderr),
        });
        return Err(format!(
            "Engine exited with code {:?}",
            output.status.code(),
            // stderr
        ));
    }

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();

    // Progress: done
    let _ = app_handle.emit("attack-progress", AttackProgress {
        stage: "done".into(),
        message: "Attack completed successfully!".into(),
    });

    Ok(stdout)
}

// ── Greet (original) ────────────────────────────────────────────────────────

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
