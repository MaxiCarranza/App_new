import sys
import os

from PySide6.QtWidgets import QApplication
from src.view.reli_ui import InterfazValidador

if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        window = InterfazValidador()
        window.show()
        sys.exit(app.exec())

    except Exception as e:
        from tkinter import messagebox
        import traceback
        import logging

        error_log_path = os.path.join(os.path.dirname(__file__), 'error_info.log')

        logging.basicConfig(filename=error_log_path, level=logging.DEBUG,
                            format='%(asctime)s %(levelname)s %(name)s %(message)s',
                            filemode='w')
        logger = logging.getLogger(__name__)

        msg = (f"Se ha encontrado un error inesperado. Por favor ponerse en contacto con "
               f"ar-data-hub-solutions.group@bbva.com:\n\n{str(e)}\n\nAdjuntar el archivo .log "
               f"generado en {error_log_path}")
        messagebox.showerror(title="Error inesperado", message=msg)
        logger.error(traceback.format_exc())

        exit(-1)
