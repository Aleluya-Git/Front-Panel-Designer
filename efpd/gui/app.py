"""Punto de entrada de la aplicación gráfica."""
from __future__ import annotations

import os
import sys

_qt_translators = []


def _install_qt_translations(app, code):
    """Traducciones propias de Qt (botones estándar, diálogos de archivo…)."""
    from PySide6.QtCore import QLibraryInfo, QTranslator
    for t in _qt_translators:
        app.removeTranslator(t)
    _qt_translators.clear()
    path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    for base in ("qtbase", "qt"):
        t = QTranslator(app)
        if t.load(f"{base}_{code}", path):
            app.installTranslator(t)
            _qt_translators.append(t)
            break


def _windows_app_id():
    """En Windows, para que la barra de tareas muestre el icono propio y no el de Python."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EFPD.ElectronicFrontPanelDesigner.1")
        except (AttributeError, OSError):
            pass


def switch_language(old_window, code):
    """Cambia el idioma reconstruyendo la ventana y conservando el documento y el historial."""
    from PySide6.QtWidgets import QApplication

    from .. import i18n
    from .main_window import MainWindow
    app = QApplication.instance()
    i18n.set_language(code)
    _install_qt_translations(app, i18n.current())
    old_window.save_layout()
    carry = old_window.carry_state()
    sel = set(old_window.canvas.selected)
    view = (old_window.canvas.s, old_window.canvas.ox, old_window.canvas.oy)
    new = MainWindow(carry)
    new.canvas._fitted = True
    new.canvas.s, new.canvas.ox, new.canvas.oy = view
    new.canvas.set_selection(sel)
    if old_window.isMaximized():
        new.showMaximized()
    else:
        new.show()
    app._efpd_window = new
    old_window._switching = True
    old_window.close()
    old_window.deleteLater()
    new.status(i18n.tr("Idioma cambiado"))
    return new


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    from PySide6.QtCore import QCoreApplication, QSettings, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication, QMessageBox

    _windows_app_id()
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QCoreApplication.setOrganizationName("EFPD")
    QCoreApplication.setApplicationName("ElectronicFrontPanelDesigner")
    app = QApplication(argv)
    _install_excepthook()
    from .. import APP_NAME, i18n
    from . import icons, qt_text
    app.setApplicationDisplayName(APP_NAME)
    app.setWindowIcon(icons.app_icon())
    code = QSettings("EFPD", "ElectronicFrontPanelDesigner").value("language", "") or _system_language()
    i18n.set_language(code)
    _install_qt_translations(app, i18n.current())
    qt_text.install()
    from ..io import project
    from .main_window import MainWindow
    win = MainWindow()
    app._efpd_window = win
    _install_file_open_handler(app)
    win.show()
    if "--smoke-test" in argv:  # comprobación del programa empaquetado (instaladores)
        return _smoke_test(app, win)
    files = [a for a in argv[1:] if a.lower().endswith(".efpd") and os.path.exists(a)]
    pend = project.pending_autosave()
    if pend:
        r = QMessageBox.question(win, APP_NAME, i18n.tr("Se encontró un autoguardado de una sesión anterior que no se "
                                                        "cerró correctamente.\n¿Desea recuperarlo?"))
        if r == QMessageBox.StandardButton.Yes:
            win.load_path(pend[0], as_path=pend[1] or "")
            win.history.checkpoint(i18n.tr("Recuperado de autoguardado"))
            win.changed()
        else:
            project.clear_autosave()
    elif files:
        win.load_path(files[0])
    return app.exec()


def _smoke_test(app, win):
    """Abre la ventana, carga un ejemplo si lo encuentra, comprueba los recursos y sale.

    El resultado se escribe en EFPD_SMOKE_OUT (los .exe de ventana no tienen consola)."""
    from .. import __version__, i18n
    from . import icons
    lines, ok = [f"version {__version__}"], True
    try:
        app.processEvents()
        lines.append(f"icono {'OK' if not icons.app_icon().isNull() else 'FALTA'}")
        ok &= not icons.app_icon().isNull()
        langs = sorted(i18n.available())
        lines.append(f"idiomas {langs}")
        ok &= {"en", "de", "fr"} <= set(langs)
        n = len(i18n.all_strings())
        lines.append(f"textos traducibles {n}")
        ok &= n > 500
        from ..core.library import BUILTIN
        lines.append(f"componentes {len(BUILTIN)}")
        ok &= len(BUILTIN) > 50
        for path in (os.environ.get("EFPD_SMOKE_FILE") or "").split(os.pathsep):
            if path and os.path.exists(path):
                ok &= bool(win.load_path(path, as_path=""))
                lines.append(f"abierto {os.path.basename(path)}: {len(win.doc.entities)} entidades")
                win.canvas.grab()
        app.processEvents()
    except Exception as e:  # noqa: BLE001
        import traceback
        ok = False
        lines.append("ERROR " + "".join(traceback.format_exception(e)))
    lines.append("RESULTADO " + ("OK" if ok else "FALLO"))
    out = os.environ.get("EFPD_SMOKE_OUT")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    win.history.mark_clean()
    win.close()
    return 0 if ok else 1


def _install_file_open_handler(app):
    """macOS: abrir un .efpd con doble clic en el Finder llega como evento FileOpen, no como argumento."""
    from PySide6.QtCore import QEvent, QObject

    class _FileOpen(QObject):
        def eventFilter(self, obj, ev):  # noqa: N802 (nombre de Qt)
            if ev.type() == QEvent.Type.FileOpen:
                path = ev.file()
                win = getattr(app, "_efpd_window", None)
                if path and win is not None and path.lower().endswith(".efpd"):
                    if win.maybe_save():
                        win.load_path(path)
                    return True
            return False

    app._efpd_file_open = _FileOpen(app)
    app.installEventFilter(app._efpd_file_open)


def _system_language():
    from PySide6.QtCore import QLocale

    from .. import i18n
    code = QLocale.system().name().split("_")[0]
    return code if code in i18n.available() else "es"


def _install_excepthook():
    """Muestra los errores inesperados en lugar de cerrar la aplicación y los guarda en un registro."""
    import datetime
    import traceback

    from ..core.library import user_library_dir
    log_path = os.path.join(os.path.dirname(user_library_dir()), "errores.log")

    def hook(etype, value, tb):
        text = "".join(traceback.format_exception(etype, value, tb))
        sys.stderr.write(text)
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n--- {datetime.datetime.now().isoformat(timespec='seconds')}\n{text}")
        except OSError:
            pass
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance() is not None and not os.environ.get("EFPD_NO_DIALOGS"):
                QMessageBox.critical(None, "Error", f"{etype.__name__}: {value}\n\n{log_path}")
        except Exception:  # noqa: BLE001
            pass
    sys.excepthook = hook


if __name__ == "__main__":
    sys.exit(main())
