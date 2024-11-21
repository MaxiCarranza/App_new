"""Entry point"""


def excepthook(exc_type, exc_value, exc_tb):

    from tkinter import messagebox
    import traceback
    import logging

    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

    error_log_path = os.path.join(os.path.dirname(__file__), 'error_info.log')

    logging.basicConfig(filename=error_log_path, level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(name)s %(message)s',
                        filemode='w')
    logger = logging.getLogger(__name__)

    msg = (f"Se ha encontrado un error inesperado:\n\n{repr(exc_value)}\n\n"
           f"De ser necesario, por favor ponerse en contacto con ar-data-hub-solutions.group@bbva.com "
           f"adjuntando la malla y el archivo .log generado en {error_log_path}")
    messagebox.showerror(title="Error inesperado", message=msg)
    logger.error(tb)

    QApplication.quit()


if __name__ == '__main__':
    import sys
    import os

    from PySide6.QtWidgets import QApplication
    from src.view.reli_ui import InterfazValidador

    sys.excepthook = excepthook
    app = QApplication(sys.argv)
    window = InterfazValidador()
    window.show()

    sys.exit(app.exec())
