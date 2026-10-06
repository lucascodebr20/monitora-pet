#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;

use tauri::{Manager, RunEvent, WindowEvent};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

struct BackendProcess(Mutex<Option<CommandChild>>);

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

fn main() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let sidecar = app
                .shell()
                .sidecar("vigiapet-backend")?
                .args(["--no-window"]);
            let (mut events, child) = sidecar.spawn()?;
            app.manage(BackendProcess(Mutex::new(Some(child))));

            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let mut output = String::new();
                while let Some(event) = events.recv().await {
                    match event {
                        CommandEvent::Stdout(bytes) => {
                            output.push_str(&String::from_utf8_lossy(&bytes));
                            if let Some(marker) = output.find("VIGIAPET_READY=") {
                                let value = &output[marker + "VIGIAPET_READY=".len()..];
                                if let Some(url) = value
                                    .lines()
                                    .next()
                                    .map(str::trim)
                                    .filter(|url| !url.is_empty())
                                {
                                    match url.parse() {
                                        Ok(parsed) => {
                                            if let Some(window) =
                                                app_handle.get_webview_window("main")
                                            {
                                                if let Err(error) = window.navigate(parsed) {
                                                    show_startup_error(
                                                        &app_handle,
                                                        &error.to_string(),
                                                    );
                                                }
                                            }
                                        }
                                        Err(error) => show_startup_error(
                                            &app_handle,
                                            &format!("Endereço local inválido: {error}"),
                                        ),
                                    }
                                    output.clear();
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
        .on_window_event(|window, event| {
            if matches!(event, WindowEvent::Destroyed) {
                stop_backend(window.app_handle());
            }
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
