import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from datetime import datetime

import src.controlm.diferencia as diferencia

from src.controlm.diferencia import DiffRecorder
from src.controlm.structures import ControlmFolder


class FolderComparisonApp:

    DEFAULT_TEXT_1 = "Malla 1: "
    DEFAULT_TEXT_2 = "Malla 2: "

    def __init__(self, root_app: tk.Tk):
        self.root = root_app
        self.root.title("Comparador de mallas")
        self.root.geometry("400x250")

        self.path_foder1 = None
        self.path_foder2 = None

        # Labels to show selected files
        self.label_file1 = tk.Label(self.root, text=self.DEFAULT_TEXT_1 + "Sin seleccionar", wraplength=300)
        self.label_file1.pack(pady=10)

        self.label_file2 = tk.Label(self.root, text=self.DEFAULT_TEXT_2 + "Sin seleccionar", wraplength=300)
        self.label_file2.pack(pady=10)

        # Buttons for selecting files
        self.button_file1 = tk.Button(self.root, text="Seleccionar malla 1", command=self.select_file1)
        self.button_file1.pack(pady=5)

        self.button_file2 = tk.Button(self.root, text="Seleccionar malla 2", command=self.select_file2)
        self.button_file2.pack(pady=5)

        # Button to compare files
        self.button_compare = tk.Button(self.root, text="Comparar", command=self.compare_folders, bg="#414bb2", fg="white", font=("Arial", 12, "bold"), width=15, height=2)
        self.button_compare.pack(pady=10)

        # Footer label
        self.footer_label = tk.Label(self.root, text="By Reliability Argentina", font=("Arial", 10, "italic"))
        self.footer_label.pack(side="bottom", anchor="se", padx=10, pady=5)

    def _selecion_complete(self):
        return False if (self.path_foder1 is None or self.path_foder2 is None) else True

    def select_file1(self):
        """Open file dialog to select the first file."""
        file1 = filedialog.askopenfilename(title="Seleccionar malla 1")
        if file1:
            self.path_foder1 = Path(file1)
            self.label_file1.config(text=self.DEFAULT_TEXT_1 + self.path_foder1.name)

    def select_file2(self):
        """Open file dialog to select the second file."""
        file2 = filedialog.askopenfilename(title="Seleccionar malla 2")
        if file2:
            self.path_foder2 = Path(file2)
            self.label_file2.config(text=self.DEFAULT_TEXT_2 + self.path_foder2.name)

    def compare_folders(self):
        """Compare the selected files. Raise an error if not both files are selected."""

        if not self._selecion_complete():
            messagebox.showerror("Error", "Se deben seleccionar ambas mallas para comparar")
            return

        msg = f"Se comparará:\nMalla 1: {self.path_foder1.name} \ncontra la Malla 2: {self.path_foder2.name}"
        return_option = messagebox.askyesno(title="Confirme accion", message=msg)
        if return_option is False:
            return

        diff_record = DiffRecorder()

        # Esto quizas es intuitivo que sea al reves, pero creeme que no. Invertido dan las diferencias de
        # forma intuitiva. Los nombres work y live son medio legacy que vienen arrastrados del contrastador
        # Habría que refactorizar los nombres con algo un toque mas intuitivo
        malla_live = ControlmFolder(str(self.path_foder1.absolute()))
        malla_work = ControlmFolder(str(self.path_foder2.absolute()))

        jobnames_nuevos = diferencia.jobnames(malla_work.jobnames(), malla_live.jobnames(), diff_record)

        for work_job in malla_work.jobs():
            if malla_live is not None and work_job.name in malla_live.jobnames():
                live_job = malla_live.obtener_job(work_job.name)
                try:
                    diferencia.atributos(work_job, live_job, diff_record)
                    diferencia.variables(work_job, live_job, diff_record)
                    diferencia.marcas(work_job, live_job, diff_record)
                    diferencia.acciones(work_job, live_job, diff_record)
                    diferencia.recursos_cuantitativos(work_job, live_job, diff_record)
                except Exception as diff_error:
                    msg = f"Ocurrió un error inesperado al analizar diferencias sobre el job {work_job.name} contactar a Tongas"
                    raise Exception(msg) from diff_error
            else:
                # Es job nuevo, informar
                try:
                    diferencia.job_nuevo(work_job, diff_record)
                except Exception as diff_nuevo_error:
                    msg = f"Ocurrió un error inesperado al informar el job nuevo {work_job.name} contactar a Tongas"
                    raise Exception(msg) from diff_nuevo_error

        informacion_extra_recorders = {
            'jobnames_nuevos': jobnames_nuevos,
            'jobnames_modificados': [],
            'jobnames_ruta_critica': []
        }

        diff_record.add_inicial(f"Fecha de generación [{datetime.now()}]", 'I')
        diff_record.add_inicial(f"Malla analizada [{malla_work.name}]", 'I')
        diff_record.add_inicial(f"UUAA: {malla_work.uuaa}", 'I')
        diff_record.add_inicial(f"Periodicidad: {malla_work.periodicidad}", 'I')
        diff_record.add_inicial(
            f"Cantidad jobs {malla_work.name}: {len(malla_work.jobs())}", 'I')
        diff_record.add_inicial(f"Cantidad jobs: {len(malla_live.jobs())}", 'I')
        diff_record.add_inicial('-' * 70, 'I')
        if jobnames_nuevos:
            diff_record.add_general(f"Jobnames nuevos: \n\t{jobnames_nuevos}", 'I')

        directory = filedialog.askdirectory(title="Seleccione un directorio para guardar el archivo .log")
        final_path = Path(directory) / f'DIFERENCIAS_{malla_work.name}.log'
        diff_record.write_log(str(final_path.absolute()), informacion_extra_recorders)
        tk.messagebox.showinfo(title="Archivo generado con exito", message=f"Se ha generado el archivo en {str(final_path.absolute())}")


if __name__ == '__main__':
    root = tk.Tk()
    app = FolderComparisonApp(root)
    root.mainloop()
