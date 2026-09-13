"""Abre la app de medición en vivo.

    .venv/bin/python -m app                ventana propia, con pywebview
    .venv/bin/python -m app --navegador    la misma interfaz en el navegador
"""
import argparse
import threading
import webbrowser

from app.servidor import Motor, arrancar_en_hilo


def main():
    p = argparse.ArgumentParser(description="App de medición en vivo de feuoir-interface")
    p.add_argument("--navegador", action="store_true",
                   help="abre la interfaz en el navegador en vez de una ventana propia")
    p.add_argument("--puerto", type=int, default=0,
                   help="puerto local; por defecto uno libre. Con npm run dev hace falta el 8750")
    args = p.parse_args()

    motor = Motor()
    url = f"http://127.0.0.1:{arrancar_en_hilo(motor, args.puerto)}/"
    if args.navegador:
        print(f"Interfaz en {url}  (Ctrl+C para cerrar)")
        webbrowser.open(url)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
    else:
        import webview   # solo hace falta para la ventana propia
        webview.create_window("Medición en vivo", url, width=1200, height=760, min_size=(960, 640))
        webview.start()
    motor.cerrar()


if __name__ == "__main__":
    main()
