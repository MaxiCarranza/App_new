"""Entry point"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.view.reli_ui import InterfazValidador


def resource_path(relative_path):
    """
    Get the absolute path to a resource, works for dev and frozen environments.
    Gracias stack overflow
    """
    if hasattr(sys, '_MEIPASS'):
        base_path = Path(sys._MEIPASS)
    else:  # For development
        base_path = Path(__file__).parent
    return base_path / relative_path


def excepthook(exc_type, exc_value, exc_tb):
    from PySide6.QtWidgets import QMessageBox
    from PySide6.QtGui import QIcon
    import traceback
    import logging

    raw_tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

    dev_path = str(Path(__file__).parent)
    runtime_path = str(Path(sys.executable).parent)

    processed_tb = raw_tb.replace(dev_path, "<dev_path>").replace(runtime_path, "<runtime_path>")

    if getattr(sys, 'frozen', False):  # If running as a frozen application
        log_dir = Path(sys.executable).parent
    else:
        log_dir = Path(__file__).parent

    error_log_path = log_dir / 'error_info.log'
    logging.basicConfig(
        filename=error_log_path,
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
        filemode='w'
    )
    logger = logging.getLogger(__name__)
    logger.error(processed_tb)

    if not QApplication.instance():
        logger.error("QApplication instance not found!")
        return

    msg = (f"Se ha encontrado un error inesperado:\n\n{repr(exc_value)}\n\n"
           f"De ser necesario, por favor ponerse en contacto con ar-data-hub-solutions.group@bbva.com "
           f"adjuntando la malla y el archivo .log generado en\n {error_log_path}")

    error_dialog = QMessageBox()
    error_dialog.setIcon(QMessageBox.Icon.Critical)
    error_dialog.setWindowIcon(QIcon())
    error_dialog.setWindowTitle("Error inesperado")
    error_dialog.setText(msg)
    error_dialog.exec()

    QApplication.quit()


def main():
    sys.excepthook = excepthook
    app = QApplication(sys.argv)
    window = InterfazValidador()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
