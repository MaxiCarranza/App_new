
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
                                   QSizePolicy, QTextBrowser, QHBoxLayout, QVBoxLayout)

from src.controlm import validaciones
from src.controlm.record import ControlRecorder
from src.controlm.structures import ControlmFolder


class InterfazValidador(QMainWindow):

    def __init__(self):
        super().__init__()

        self.folder_path = None
        self.control_record = None
        self.malla_nombre = None

        self.setWindowTitle("Generador de Mallas Temporales - BBVA")
        self.setMinimumSize(1000, 600)
        self.setWindowIcon(QIcon(os.path.join(os.getcwd(), "src", "resources", "img", "bbva.ico")))
        self.setStyleSheet("background-color: #131c46;")

        self.grid_layout = QGridLayout()

        # Cargar y añadir la idasmagen de fondo (BBVA)
        image = QPixmap(os.path.join(os.getcwd(), "src", "resources", "img", "im_bbva.png")).scaled(110, 40, Qt.AspectRatioMode.KeepAspectRatio)
        image_label = QLabel()
        image_label.setPixmap(image)

        # Etiqueta de pie de página
        reli_label = QLabel("By Reliability Argentina")
        reli_label.setStyleSheet("color: white; font: bold 18px Arial;")

        dudas_label = QLabel("Dudas: ar-data-hub-solutions.group@bbva.com")
        dudas_label.setStyleSheet("color: white; font: 12px Arial;")

        self.setWindowTitle("Validador de mallas - BBVA")

        # Etiqueta de pie de página
        title_label = QLabel("VALIDADOR DE MALLAS", parent=self)
        title_label.setStyleSheet("color: #00b89f; font: bold 35px Arial;")
        title_label.setMinimumHeight(100)

        self.folder_label = QLabel("Adjunte una malla", parent=self)
        self.folder_label.setMinimumWidth(300)
        self.folder_label.setMinimumHeight(36)
        self.folder_label.setStyleSheet("color: grey; font: 15px Arial; background: white; padding-left: 3px;")
        self.folder_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        attachment_button = QPushButton("ADJUNTAR MALLA", parent=self)
        attachment_button.setStyleSheet(
            "color: white; font: bold 15px Arial; background: #414bb2; border-color: white; padding: 10px 10px;")
        attachment_button.clicked.connect(self.add_attachment)
        attachment_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        validate_button = QPushButton("VALIDAR MALLA", parent=self)
        validate_button.setStyleSheet("color: white; font: bold 25px Arial; background: #00b89f; "
                                      "border-color: white; padding: 6px;")
        validate_button.clicked.connect(self.validate)

        self.validation_layout = QVBoxLayout()
        self.validation_layout.setContentsMargins(30, 0, 30, 0)

        validation_label = QLabel("DETALLES DE VALIDACION", parent=self)
        validation_label.setStyleSheet("color: white; font: bold 15px Arial; background-color: #131c46;")
        self.validation_layout.addWidget(validation_label)

        self.validation_textbox = QTextEdit(self)
        self.validation_textbox.setReadOnly(True)
        self.validation_textbox.setPlaceholderText("Seleccione una malla para validar")
        self.validation_textbox.setStyleSheet(
            "color: #333333; background-color: #F0F8FF; font: 13px;"
        )
        self.validation_textbox.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.validation_layout.addWidget(self.validation_textbox)

        download_button = QPushButton("DESCARGAR DETALLES", parent=self)
        download_button.setStyleSheet(
            "color: white; font: bold 20px Arial; background: #414bb2; "
            "border-color: white; padding: 5px;")
        download_button.clicked.connect(self.download_log)
        self.validation_layout.addWidget(download_button, alignment=Qt.AlignmentFlag.AlignRight)

        spacer_horizontal = QSpacerItem(0, 30, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        # Grid config
        self.grid_layout.addWidget(image_label, 0, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignLeft)
        self.grid_layout.addWidget(title_label, 0, 0, 2, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid_layout.addWidget(self.folder_label, 2, 0, 1, 1, alignment=Qt.AlignmentFlag.AlignRight)
        self.grid_layout.addWidget(attachment_button, 2, 1, 1, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        self.grid_layout.addItem(spacer_horizontal, 3, 0, 1, 2)
        self.grid_layout.addWidget(validate_button, 4, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        self.grid_layout.addItem(spacer_horizontal, 5, 0, 1, 2)
        self.grid_layout.addLayout(self.validation_layout, 6, 0, 1, 2)
        self.grid_layout.addItem(spacer_horizontal, 7, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignRight)
        self.grid_layout.addWidget(reli_label, 8, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignRight)
        self.grid_layout.addWidget(dudas_label, 9, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignRight)

        widget = QWidget(self)
        widget.setLayout(self.grid_layout)
        self.setCentralWidget(widget)

    @staticmethod
    def alert(title: str, message: str):
        msg_box = QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowIcon(QIcon.fromTheme('dialog-information'))
        msg_box.exec()

    def add_attachment(self):
        file_path = QFileDialog.getOpenFileName(self, self.tr("Open Image"), os.getcwd(), self.tr("XML Files (*.xml)"))[0]
        if file_path:
            self.folder_label.setText(f"Malla seleccionada: {Path(file_path).name}")
            self.folder_label.setStyleSheet("color: black; font: 15px Arial; background: white; padding-left: 3px;")
        self.folder_path = file_path

    def validate(self):

        if not self.folder_path:
            self.alert(title="Alerta", message="No se encuentra una malla adjuntada")
            return

        self.control_record = ControlRecorder()

        malla = ControlmFolder(xml_input=self.folder_path)
        self.malla_nombre = malla.name

        for job in malla.jobs():
            try:
                validaciones.jobname(job, malla, self.control_record)
                validaciones.application(job, malla, self.control_record)
                validaciones.subapp(job, malla, self.control_record)
                validaciones.atributos(job, malla, self.control_record)
                validaciones.variables(job, malla, self.control_record)
                validaciones.marcas_in(job, malla, self.control_record)
                validaciones.marcas_out(job, malla, self.control_record)
                validaciones.acciones(job, malla, self.control_record)
                validaciones.tipo(job, malla, self.control_record)
                validaciones.recursos_cuantitativos(job, malla, self.control_record)

                if not job.es_spark_compactor():
                    # validaciones.verificar_variables_nuevas(job, self.control_record)
                    pass

            except Exception as control_error:
                # TODO: Lanzar cuadro de error
                msg = f"Ocurrió un error inesperado al realizar controles sobre el job [{job.name}]"
                raise Exception(msg) from control_error

        # La validación de cadenas es un control a nivel malla, no es puntual con los jobs, lo podemos dejar acá
        try:
            validaciones.cadena_smart_cleaner(malla, self.control_record)
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
        self.control_record.add_inicial(f"Cantidad jobs {malla.name}: {len(malla.jobs())}")
        self.control_record.add_inicial('-' * 70)

        msg_box = self.control_record.generate_log(informacion_extra_recorders)
        self.validation_textbox.setText(f"La malla contiene los siguientes errores:\n{msg_box}")

    def download_log(self):
        if not hasattr(self, 'malla_nombre') or self.malla_nombre is None:
            self.alert("Aviso", f"No existen logs para descargar.")
        else:
            download_path = QFileDialog.getExistingDirectory(self, os.getcwd())
            if download_path and download_path != '':
                file_path = os.path.join(download_path, f'CONTROLES_{self.malla_nombre}.log')
                self.control_record.write_log(file_path, {})
                self.alert("Generacion de log", f"Log descargado correctamente en {file_path}")
