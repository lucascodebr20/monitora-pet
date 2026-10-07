#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;

use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Manager, RunEvent, WindowEvent,
};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

struct BackendProcess(Mutex<Option<CommandChild>>);
struct JobRunning(AtomicBool);
struct HiddenToTray(AtomicBool);

const JOB_MARKER: &str = "MONITORAPET_JOB=";
const READY_MARKER: &str = "MONITORAPET_READY=";

fn stop_backend(app: &tauri::AppHandle) {
    let state = app.state::<BackendProcess>();
    if let Ok(mut process) = state.0.lock() {
        if let Some(child) = process.take() {
            let _ = child.kill();
        }
    };
}

fn show_startup_error(app: &tauri::AppHandle, message: &str) {
    if let Some(window) = app.get_webview_window("main") {
        let escaped = message.replace('\\', "\\\\").replace('`', "\\`");
        let _ = window.eval(format!(
            "document.querySelector('h1').textContent='Não foi possível iniciar';document.querySelector('p').textContent=`{escaped}`;document.querySelector('.mark').style.display='none';"
        ));
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

fn main() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(JobRunning(AtomicBool::new(false)))
        .manage(HiddenToTray(AtomicBool::new(false)))
        .setup(|app| {
            let sidecar = app
                .shell()
                .sidecar("monitorapet-backend")?
                .args(["--no-window"]);
            let (mut events, child) = sidecar.spawn()?;
            app.manage(BackendProcess(Mutex::new(Some(child))));

            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let mut pending = String::new();
                while let Some(event) = events.recv().await {
                    match event {
                        CommandEvent::Stdout(bytes) => {
                            pending.push_str(&String::from_utf8_lossy(&bytes));
                            while let Some(newline) = pending.find('\n') {
                                let line = pending[..newline].trim().to_string();
                                pending.drain(..=newline);
                                if let Some(url) = line.strip_prefix(READY_MARKER) {
                                    if !url.is_empty() {
                                        handle_ready(&app_handle, url);
                                    }
                                } else if let Some(state) = line.strip_prefix(JOB_MARKER) {
                                    handle_job_state(&app_handle, state);
                                }
                            }
                        }
                        CommandEvent::Stderr(bytes) => {
                            eprintln!("{}", String::from_utf8_lossy(&bytes));
                        }
                        CommandEvent::Error(error) => show_startup_error(&app_handle, &error),
                        CommandEvent::Terminated(status) => {
                            if status.code != Some(0) {
                                show_startup_error(
                                    &app_handle,
                                    "O serviço local do Monitora Pet foi encerrado inesperadamente.",
                                );
                            }
                            break;
                        }
                        _ => {}
                    }
                }
            });
            Ok(())
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
