#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::collections::VecDeque;
use std::fs::File;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;

use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    webview::PageLoadEvent,
    Manager, RunEvent, WindowEvent,
};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

struct BackendProcess(Mutex<Option<CommandChild>>);
struct JobRunning(AtomicBool);
struct HiddenToTray(AtomicBool);
struct StartupError(Mutex<Option<String>>);

const JOB_MARKER: &str = "MONITORAPET_JOB=";
const READY_MARKER: &str = "MONITORAPET_READY=";
const BACKEND_DIR: &str = "backend";
const BACKEND_EXECUTABLE: &str = "monitorapet-backend.exe";
const OUTPUT_TAIL_LINES: usize = 8;

struct BackendOutput {
    file: Option<File>,
    tail: VecDeque<String>,
}

impl BackendOutput {
    fn record(&mut self, stream: &str, line: &str) {
        if line.is_empty() {
            return;
        }
        if let Some(file) = self.file.as_mut() {
            let _ = writeln!(file, "[{stream}] {line}");
            let _ = file.flush();
        }
        if self.tail.len() == OUTPUT_TAIL_LINES {
            self.tail.pop_front();
        }
        self.tail.push_back(line.to_string());
    }
}

fn stop_backend(app: &tauri::AppHandle) {
    let state = app.state::<BackendProcess>();
    if let Ok(mut process) = state.0.lock() {
        if let Some(child) = process.take() {
            let _ = child.kill();
        }
    };
}

fn startup_error_script(message: &str) -> String {
    let encoded = serde_json::to_string(message).unwrap_or_else(|_| "\"\"".into());
    format!(
        "document.querySelector('h1').textContent='Não foi possível iniciar';const detail=document.querySelector('p');detail.textContent={encoded};detail.style.whiteSpace='pre-line';detail.style.userSelect='text';for(const selector of ['.mark','.bar']){{const element=document.querySelector(selector);if(element)element.style.display='none';}}"
    )
}

fn show_startup_error(app: &tauri::AppHandle, message: &str) {
    if let Ok(mut error) = app.state::<StartupError>().0.lock() {
        *error = Some(message.to_string());
    }
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.eval(startup_error_script(message));
    }
}

fn show_main_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
    app.state::<HiddenToTray>().0.store(false, Ordering::SeqCst);
}

fn quit(app: &tauri::AppHandle) {
    stop_backend(app);
    app.exit(0);
}

fn setup_tray(app: &tauri::AppHandle) -> tauri::Result<()> {
    if app.tray_by_id("main").is_some() {
        return Ok(());
    }
    let open = MenuItem::with_id(app, "open", "Abrir o Monitora Pet", true, None::<&str>)?;
    let quit_item = MenuItem::with_id(app, "quit", "Sair", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&open, &quit_item])?;
    let mut builder = TrayIconBuilder::with_id("main")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .tooltip("Monitora Pet · analisando gravações")
        .on_menu_event(|app, event| match event.id.as_ref() {
            "open" => show_main_window(app),
            "quit" => quit(app),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let tauri::tray::TrayIconEvent::DoubleClick { .. } = event {
                show_main_window(tray.app_handle());
            }
        });
    if let Some(icon) = app.default_window_icon() {
        builder = builder.icon(icon.clone());
    }
    builder.build(app)?;
    Ok(())
}

fn update_tray_tooltip(app: &tauri::AppHandle, text: &str) {
    if let Some(tray) = app.tray_by_id("main") {
        let _ = tray.set_tooltip(Some(text));
    }
}

fn handle_job_state(app: &tauri::AppHandle, state: &str) {
    let running = state == "running";
    app.state::<JobRunning>().0.store(running, Ordering::SeqCst);
    if running {
        update_tray_tooltip(app, "Monitora Pet · analisando gravações");
        return;
    }
    update_tray_tooltip(app, "Monitora Pet · análise concluída");
    if app.state::<HiddenToTray>().0.load(Ordering::SeqCst) {
        show_main_window(app);
    }
}

fn handle_ready(app: &tauri::AppHandle, url: &str) {
    match url.parse() {
        Ok(parsed) => {
            if let Some(window) = app.get_webview_window("main") {
                if let Err(error) = window.navigate(parsed) {
                    show_startup_error(app, &error.to_string());
                }
            }
        }
        Err(error) => show_startup_error(app, &format!("Endereço local inválido: {error}")),
    }
}

fn backend_log(app: &tauri::AppHandle) -> (Option<File>, Option<PathBuf>) {
    let Ok(dir) = app.path().app_log_dir() else {
        return (None, None);
    };
    if std::fs::create_dir_all(&dir).is_err() {
        return (None, None);
    }
    let path = dir.join("backend.log");
    (File::create(&path).ok(), Some(path))
}

fn backend_failure_message(code: Option<i32>, output: &BackendOutput, log_path: Option<&Path>) -> String {
    let code = code.map_or_else(|| "desconhecido".to_string(), |code| code.to_string());
    let mut message = format!("O serviço local do Monitora Pet foi encerrado inesperadamente (código {code}).");
    if !output.tail.is_empty() {
        message.push_str("\n\n");
        message.push_str(&output.tail.iter().cloned().collect::<Vec<_>>().join("\n"));
    }
    if let Some(path) = log_path {
        message.push_str(&format!("\n\nDetalhes em {}", path.display()));
    }
    message
}

fn start_backend(app: &tauri::AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    let backend_dir = app.path().resource_dir()?.join(BACKEND_DIR);
    let executable = backend_dir.join(BACKEND_EXECUTABLE);
    if !executable.is_file() {
        return Err(format!("arquivo ausente: {}", executable.display()).into());
    }
    let (file, log_path) = backend_log(app);
    let (mut events, child) = app
        .shell()
        .command(&executable)
        .args(["--no-window"])
        .current_dir(&backend_dir)
        .spawn()?;
    if let Ok(mut process) = app.state::<BackendProcess>().0.lock() {
        *process = Some(child);
    }

    let app_handle = app.clone();
    tauri::async_runtime::spawn(async move {
        let mut output = BackendOutput { file, tail: VecDeque::new() };
        let mut pending_stdout = String::new();
        let mut pending_stderr = String::new();
        while let Some(event) = events.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    pending_stdout.push_str(&String::from_utf8_lossy(&bytes));
                    while let Some(newline) = pending_stdout.find('\n') {
                        let line = pending_stdout[..newline].trim().to_string();
                        pending_stdout.drain(..=newline);
                        if let Some(url) = line.strip_prefix(READY_MARKER) {
                            output.record("stdout", "serviço pronto");
                            if !url.is_empty() {
                                handle_ready(&app_handle, url);
                            }
                        } else {
                            if let Some(state) = line.strip_prefix(JOB_MARKER) {
                                handle_job_state(&app_handle, state);
                            }
                            output.record("stdout", &line);
                        }
                    }
                }
                CommandEvent::Stderr(bytes) => {
                    pending_stderr.push_str(&String::from_utf8_lossy(&bytes));
                    while let Some(newline) = pending_stderr.find('\n') {
                        let line = pending_stderr[..newline].trim_end().to_string();
                        pending_stderr.drain(..=newline);
                        output.record("stderr", &line);
                    }
                }
                CommandEvent::Error(error) => {
                    output.record("erro", &error);
                    show_startup_error(&app_handle, &error);
                }
                CommandEvent::Terminated(status) => {
                    output.record("stdout", pending_stdout.trim());
                    output.record("stderr", pending_stderr.trim_end());
                    output.record("fim", &format!("código {:?}", status.code));
                    if status.code != Some(0) {
                        show_startup_error(
                            &app_handle,
                            &backend_failure_message(status.code, &output, log_path.as_deref()),
                        );
                    }
                    break;
                }
                _ => {}
            }
        }
    });
    Ok(())
}

fn main() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(JobRunning(AtomicBool::new(false)))
        .manage(HiddenToTray(AtomicBool::new(false)))
        .manage(BackendProcess(Mutex::new(None)))
        .manage(StartupError(Mutex::new(None)))
        .setup(|app| {
            let handle = app.handle().clone();
            if let Err(error) = start_backend(&handle) {
                show_startup_error(
                    &handle,
                    &format!("Não foi possível abrir o serviço local do Monitora Pet ({error})."),
                );
            }
            Ok(())
        })
        .on_page_load(|webview, payload| {
            if payload.event() != PageLoadEvent::Finished {
                return;
            }
            let message = webview
                .app_handle()
                .state::<StartupError>()
                .0
                .lock()
                .ok()
                .and_then(|error| error.clone());
            if let Some(message) = message {
                let _ = webview.eval(startup_error_script(&message));
            }
        })
        .on_window_event(|window, event| match event {
            WindowEvent::CloseRequested { api, .. } => {
                let app = window.app_handle();
                if app.state::<JobRunning>().0.load(Ordering::SeqCst) {
                    api.prevent_close();
                    if setup_tray(app).is_ok() {
                        let _ = window.hide();
                        app.state::<HiddenToTray>().0.store(true, Ordering::SeqCst);
                    } else {
                        quit(app);
                    }
                } else {
                    stop_backend(app);
                }
            }
            WindowEvent::Destroyed => stop_backend(window.app_handle()),
            _ => {}
        });

    builder
        .build(tauri::generate_context!())
        .expect("erro ao construir o aplicativo Monitora Pet")
        .run(|app, event| {
            if matches!(event, RunEvent::Exit | RunEvent::ExitRequested { .. }) {
                stop_backend(app);
            }
        });
}
