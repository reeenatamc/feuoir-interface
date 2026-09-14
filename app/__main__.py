"""Opens the live measurement app.

    .venv/bin/python -m app              own window, with pywebview
    .venv/bin/python -m app --browser    the same interface in the browser
"""
import argparse
import threading
import webbrowser

from app.server import Engine, start_in_thread


def main():
    parser = argparse.ArgumentParser(description="App de medición en vivo de feuoir-interface")
    parser.add_argument("--browser", action="store_true",
                        help="abre la interfaz en el navegador en vez de una ventana propia")
    parser.add_argument("--port", type=int, default=0,
                        help="puerto local; por defecto uno libre. Con npm run dev hace falta el 8750")
    args = parser.parse_args()

    engine = Engine()
    url = f"http://127.0.0.1:{start_in_thread(engine, args.port)}/"
    if args.browser:
        print(f"Interfaz en {url}  (Ctrl+C para cerrar)")
        webbrowser.open(url)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
    else:
        import webview   # only needed for the app's own window
        webview.create_window("Medición en vivo", url, width=1200, height=760, min_size=(960, 640))
        webview.start()
    engine.close()


if __name__ == "__main__":
    main()
