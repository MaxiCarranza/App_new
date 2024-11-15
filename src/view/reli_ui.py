
import os
from datetime import datetime
from pathlib import Path

try:
    from PySide6.QtCore import Qt
except ImportError:
    from tkinter import messagebox
    messagebox.showerror(title="Error", message="No se pudo importar la librería PySide6, por favor ponerse en contacto con ar-data-hub-solutions.group@bbva.com")
else:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap, QIcon, QTextDocument
    from PySide6.QtWidgets import (QApplication, QMainWindow, QLabel, QGridLayout, QPushButton,
                                   QFileDialog, QMessageBox, QTextEdit, QWidget, QSpacerItem,
                                   QSizePolicy, QTextBrowser)

from src.controlm import validaciones
from src.controlm.record import ControlRecorder
from src.controlm.structures import ControlmFolder


class InterfazApp(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Generador de Mallas Temporales - BBVA")
        self.setMinimumSize(1000, 600)
        self.setWindowIcon(QIcon(os.path.join(os.getcwd(), "src", "resources", "img", "bbva.ico")))
        self.setStyleSheet("background-color: #131c46;")

        # Configurar el layout de grid
        self.grid_layout = QGridLayout()

        # Cargar y añadir la idasmagen de fondo (BBVA)
        image = QPixmap(os.path.join(os.getcwd(), "src", "resources", "img", "im_bbva.png")).scaled(110, 40, Qt.AspectRatioMode.KeepAspectRatio)
        image_label = QLabel()
        image_label.setPixmap(image)

        self.grid_layout.addWidget(image_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)

        # Etiqueta de pie de página
        reli_label = QLabel("By Reliability Argentina")
        reli_label.setStyleSheet("color: white; font: bold 18px Arial;")
        self.grid_layout.addWidget(reli_label, 8, 0, 1, 10, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)

        dudas_label = QLabel("Dudas: ar-data-hub-solutions.group@bbva.com")
        dudas_label.setStyleSheet("color: white; font: 12px Arial;")
        self.grid_layout.addWidget(dudas_label, 9, 0, 1, 10, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)

        widget = QWidget(self)
        widget.setLayout(self.grid_layout)
        self.setCentralWidget(widget)


class InterfazValidador(InterfazApp):

    def __init__(self):
        super().__init__()

        self.folder_path = None
        self.control_record = None
        self.malla_nombre = None

        self.setWindowTitle("Validador de mallas - BBVA")

        # Etiqueta de pie de página
        title_label = QLabel("VALIDADOR DE MALLAS", parent=self)
        title_label.setStyleSheet("color: #00b89f;; font: bold 35px Arial; margin-bottom: 50px;")

        self.folder_label = QLabel("Adjunte una malla", parent=self)
        self.folder_label.setMinimumWidth(300)
        self.folder_label.setStyleSheet("color: black; font: 15px Arial; background: white; padding-left: 3px;")

        attachment_button = QPushButton("ADJUNTAR MALLA", parent=self)
        attachment_button.setStyleSheet(
            "color: white; font: bold 15px Arial; background: #414bb2; border-color: white; border-style: solid; border-width: 1px; padding: 10px 10px;")
        attachment_button.clicked.connect(self.add_attachment)

        validate_button = QPushButton("VALIDAR MALLA", parent=self)
        validate_button.setStyleSheet("color: white; font: bold 25px Arial; background: #00b89f; "
                                      "border-color: white; border-width: 3px; border-style: solid; padding: 5px;"
                                      "margin-top: 20px; margin-bottom: 15px;")
        validate_button.clicked.connect(self.validate)

        validation_label = QLabel("DETALLES DE VALIDACION", parent=self)
        validation_label.setStyleSheet("color: white; font: bold 13px Arial; background-color: #131c46; margin-left: 30px;")

        self.validation_textbox = QTextEdit(self)
        self.validation_textbox.setReadOnly(True)
        self.validation_textbox.setPlaceholderText("Seleccione una malla para validar")
        self.validation_textbox.setStyleSheet(
            "color: #333333; background-color: #F0F8FF; margin-left: 30px; margin-right: 30px; font: 13px"
        )
        self.validation_textbox.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        download_button = QPushButton("DESCARGAR DETALLES", parent=self)
        download_button.setStyleSheet(
            "color: white; font: bold 20px Arial; margin-right: 30px; background: #414bb2; "
            "border-color: white; border-style: solid; border-width: 1px; padding: 5px;")
        download_button.clicked.connect(self.download_log)

        spacer_download_relilabel = QSpacerItem(0, 30, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        self.grid_layout.addWidget(title_label, 1, 0, 1, 10, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid_layout.addWidget(self.folder_label, 2, 0, 1, 5, alignment=Qt.AlignmentFlag.AlignRight)
        self.grid_layout.addWidget(attachment_button, 2, 5, 1, 5, alignment=Qt.AlignmentFlag.AlignLeft)
        self.grid_layout.addWidget(validate_button, 3, 0, 1, 10, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid_layout.addWidget(validation_label, 4, 0)
        self.grid_layout.addWidget(self.validation_textbox, 5, 0, 1, 10)
        self.grid_layout.addWidget(download_button, 6, 9, alignment=Qt.AlignmentFlag.AlignRight)
        self.grid_layout.addItem(spacer_download_relilabel, 7, 9)

    def add_attachment(self):
        file_path = QFileDialog.getOpenFileName(self, self.tr("Open Image"), os.getcwd(), self.tr("XML Files (*.xml)"))[0]
        if file_path:
            self.folder_label.setText(f"Malla seleccionada: {Path(file_path).name}")
        self.folder_path = file_path

    def validate(self):
        if not self.folder_path:
            msg_box = QMessageBox()
            msg_box.setText("No se encuentra una malla adjuntada")
            msg_box.exec()
            return

        self.control_record = ControlRecorder()

        malla = ControlmFolder(xml_input=self.folder_path)
        self.malla_nombre = malla.name

        for work_job in malla.jobs():
            try:
                validaciones.jobname(work_job, malla, self.control_record)
                validaciones.application(work_job, malla, self.control_record)
                validaciones.subapp(work_job, malla, self.control_record)
                validaciones.atributos(work_job, malla, self.control_record)
                validaciones.variables(work_job, malla, self.control_record)
                validaciones.marcas_in(work_job, malla, self.control_record)
                validaciones.marcas_out(work_job, malla, self.control_record)
                validaciones.acciones(work_job, malla, self.control_record)
                validaciones.tipo(work_job, malla, self.control_record)
                validaciones.recursos_cuantitativos(work_job, malla, self.control_record)
            except Exception as control_error:
                # TODO: Lanzar cuadro de error
                msg = f"Ocurrió un error inesperado al realizar controles sobre el job [{work_job.name}] contactar a Tongas"
                raise Exception(msg) from control_error

        # La validación de cadenas es un control a nivel malla, no es puntual con los jobs, lo podemos dejar acá
        try:
            validaciones.cadenas_malla(malla, self.control_record)
        except Exception as error_cadenas:
            msg = f"Ocurrió un error inesperado al analizar las cadenas de la malla"
            raise Exception(msg) from error_cadenas

        informacion_extra_recorders = {
            'jobnames_nuevos': [],
            'jobnames_modificados': [],
            'jobnames_ruta_critica': [job.name for job in malla.jobs() if job.es_ruta_critica()]
        }

        self.control_record.add_inicial(f"Fecha de generación [{datetime.now()}]")
        self.control_record.add_inicial(f"Malla analizada [{malla.name}]")
        self.control_record.add_inicial(f"UUAA: {malla.uuaa}")
        self.control_record.add_inicial(f"Periodicidad: {malla.periodicidad}")
        self.control_record.add_inicial(
            f"Cantidad jobs {malla.name}: {len(malla.jobs())}")
        self.control_record.add_inicial('-' * 70)

        msg_box = self.control_record.generate_log(informacion_extra_recorders)
        self.validation_textbox.setText(f"La malla contiene los siguientes errores:\n{msg_box}")

    def download_log(self):
        if not hasattr(self, 'malla_nombre'):
            msg_box = QMessageBox()
            msg_box.setText("No existen logs para descargar.")
            msg_box.exec()
        else:
            download_path = QFileDialog.getExistingDirectory(self, os.getcwd())
            if download_path:
                self.control_record.write_log(os.path.join(download_path, f'CONTROLES_{self.malla_nombre}.log'), {})
                msg_box = QMessageBox()
                msg_box.setText(f"Log descargado correctamente en {download_path}")
                msg_box.exec()
