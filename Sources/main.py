"""
Project Name: Generador de Mallas - Reliabity
Version: 0.1
Description:
    Este proyecto es una herramienta diseñada para automatizar la creación y modificación
    de jobs en un entorno de generación de mallas. Permite a los usuarios seleccionar fechas,
    modificar jobs, y gestionar listas de trabajos a través de una interfaz gráfica desarrollada en Tkinter.

Author: Maxi Carranza
Date: 01/09/2024
Python Version: 3.12

Main Features:
    - Selección de fechas con un calendario desplegable.
    - Modificación de trabajos (jobs) usando las fechas seleccionadas.
    - Interfaz gráfica para interactuar con listas de trabajos.
    - Uso de Tkinter para la creación de la interfaz gráfica de usuario.
    - Soporte para la integración de múltiples fechas y trabajos seleccionados.

Usage:
    - Ejecuta el archivo principal para abrir la interfaz gráfica.
    - Selecciona una fecha a través del calendario.
    - Selecciona y modifica trabajos en la lista.
    - Confirma los trabajos para aplicar los cambios.

Version History:
    0.1 - Primera versión funcional con selección de fechas y jobs, y modificación básica de jobs.

Requirements:
    - tkinter
    - tkcalendar
    - xml.etree.ElementTree para manipular archivos XML (si es necesario).

Future Improvements:
    - Añadir validaciones y manejo de errores más robusto.
    - Soporte para carga y exportación de archivos en diferentes formatos.
    - Mejorar la visualización y gestión de trabajos.
"""

import sys
import traceback
import logging
import random
import os
import xml.etree.ElementTree as ET
from tkinter.ttk import Radiobutton

import requests
import pandas as pd
import re
import tkinter as tk

from controlm.structures import ControlmFolder
from tkinter import messagebox, filedialog, Checkbutton, BooleanVar
from PIL import Image, ImageTk
from tkcalendar import DateEntry, Calendar
from datetime import datetime

from controlm.structures import MallaMaxi


api_url = f'https://api.argentinadatos.com/v1/feriados/'

fechas_seleccionadas = []
selected_jobs_global = set()

REGEX_MAILS = r'[^@ \t\r\n]+@[^@ \t\r\n]+\.[^@ \t\r\n]+'
REGEX_LEGAJO = r'^[A-Za-z]\d+$'


def ruta_absoluta(rel_path):
    if hasattr(sys, 'frozen'):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, rel_path)


ruta_modelo = ruta_absoluta('model.h5')


def es_fecha_valida(fecha):
    """
    Obtener los días no laborables (feriados)
    """

    anios_seleccionados = list(set([str(anio.year) for anio in fecha]))

    non_chamba_days = []
    for anio in anios_seleccionados:
        try:
            response = requests.get(api_url + anio + '/', verify=False)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.error("No se pudo conectar con la API de feriados: %s", e)
        else:
            feriados_data = response.json()
            non_chamba_days.extend([feriado['fecha'] for feriado in feriados_data])
        finally:
            # Dia del bancario
            non_chamba_days.append(f'{anio}-11-06')

    fechas_a_generar_jobs = []
    for f in fecha:
        fecha_str = f.strftime('%Y-%m-%d')
        if f.weekday() < 5 and fecha_str not in non_chamba_days:
            fechas_a_generar_jobs.append(fecha_str)

    return fechas_a_generar_jobs


def obtener_fechas_optimizado(current_date, end_date, fechas_pross, fechas_manual=None):
    """
    Genera un rango optimizado de fechas basadas en la opción fechas_pross y fechas_manual.
    """
    if fechas_manual:
        # Si se proporciona fechas_manual, usarla en lugar de generar un rango
        return [datetime.strptime(fecha, "%Y-%m-%d").date() for fecha in fechas_manual]

    # Si fechas_pross es "dias_habiles", generar solo días hábiles
    if fechas_pross == "dias_habiles":
        fechas_a_work = pd.date_range(start=current_date, end=end_date).to_pydatetime().tolist()
        fecha_habil = es_fecha_valida(fechas_a_work)
        return fecha_habil

    # Por defecto, retornar todas las fechas en el rango
    return pd.date_range(start=current_date, end=end_date).to_pydatetime().tolist()

def modificar_malla(filename, mail_personal, start_date, end_date, selected_jobs, caso_de_uso, fechas_pross,legajo,var_force,fechas_manual=None):
    """
    Función para modificar la malla.

    Esta función ahora acepta las fechas seleccionadas como parámetro opcional.

    :param filename: Es el archivo adjunto(Malla)
    :param mail_personal: toma el mail ingresado
    :param fechas_pross: toma el fechas de la opcion
    :param fechas: Lista de fechas seleccionadas. Si no se pasan, se usará la variable global fechas_seleccionadas.
    """
    global new_filename, xml_buffer, new_folder_name,m_max

    nro_malla = str(random.randint(10, 99))
    new_folder_name = f"CR-AR{malla.uuaa}TMP-T{nro_malla}"

    fechas_a_iterar = obtener_fechas_optimizado(start_date, end_date, fechas_pross, fechas_manual)
    jobs_to_duplicate = [job for job in malla.jobs() if job.name in selected_jobs]

    # Comienza la salsa
    m_max = MallaMaxi(jobs_to_duplicate, malla)
    m_max.ordenar()
    m_max.replicar_y_enlazar(fechas_a_iterar)
    m_max.ambientar(mail_personal, new_folder_name, caso_de_uso, legajo,var_force)

    return new_folder_name

def select_attached_file():
    global attached_file_path, jobs, malla
    attached_file_path = filedialog.askopenfilename(title="Selecciona una malla XML",
                                                    filetypes=[("XML files", "*.xml")])

    try:

        malla = ControlmFolder(attached_file_path)

        # Limpia las listas si ya estaban cargada previamentes
        job_listbox.delete(0, tk.END)
        selected_jobs_listbox.delete(0, tk.END)

        job_names_from_xml = malla.jobnames()

        for job_name in job_names_from_xml:
            job_listbox.insert(tk.END, job_name)

        messagebox.showinfo("Éxito", "Archivo adjunto cargado correctamente.")

    except:
        messagebox.showinfo("Fallo", "Archivo adjunto no se cargo.")

def confirmar_seleccion():

    global modified_file_path, selected_jobs_listbox, caso_uso_var, mail_entry, start_date_entry, end_date_entry, job_listbox

    email = mail_entry.get()
    legajo = legajo_var.get()
    if not validate_email(email):
        messagebox.showerror("Mail inválido", "Por favor, ingrese un Mail válido.")
        return
    if not validate_legajo(legajo):
        messagebox.showerror("Legajo inválido", "Por favor, ingrese un Legajo válido.")
        return

    selected_jobs = list(selected_jobs_global)
    # Llamar a la función modificar_malla con los jobs seleccionados
    if selected_jobs and attached_file_path and caso_uso_var.get() and mail_entry.get() and seleccion_var.get() != "carga_manual":
        modified_file_path = modificar_malla(attached_file_path, mail_entry.get(), start_date_entry.get_date(),
                                             end_date_entry.get_date(), selected_jobs, caso_uso_var.get(),
                                             seleccion_var.get(), legajo_var.get(),var_force.get(), None)
        messagebox.showinfo("Éxito", "La malla ha sido modificada y guardada temporalmente.")
        if not new_folder_name:
            messagebox.showwarning("Advertencia", "No hay malla modificada para descargar o el archivo no existe.")
            return

        save_path = filedialog.asksaveasfilename(defaultextension=".xml", filetypes=[("XML files", "*.xml")],
                                                 initialfile=os.path.basename(modified_file_path))

        m_max.exportar(save_path)
        messagebox.showinfo("Éxito", f"Malla descargada en: {save_path}")

    elif selected_jobs and attached_file_path and caso_uso_var.get() and mail_entry.get() and seleccion_var.get() == "carga_manual":
        modified_file_path = modificar_malla(attached_file_path, mail_entry.get(), None,
                                             None, selected_jobs, caso_uso_var.get(),
                                             seleccion_var.get(), legajo_var.get(),var_force.get(),fechas_seleccionadas)

    elif not caso_uso_var.get() or not mail_entry.get():
        messagebox.showwarning("Advertencia", "Por favor, completar todos los campos.")

    elif not selected_jobs:
        messagebox.showwarning("Advertencia", "Por favor, elija al menos un job.")

    elif not attached_file_path:
        messagebox.showwarning("Advertencia", "Por favor, adjunte un archivo.")

    else:
        messagebox.showwarning("Advertencia", "Por favor, adjunte un archivo y al menos un job.")

def update_selected_jobs_listbox():
    global selected_jobs_global, selected_jobs_listbox
    selected_jobs_listbox.delete(0, tk.END)
    for job in selected_jobs_global:
        selected_jobs_listbox.insert(tk.END, job)

def filtrar_jobs(event):
    global jobs, attached_file_path, selected_jobs_global
    """Función que filtra jobs basados en lo que el usuario escribe en el Entry"""
    search_term = entry_buscar.get().lower()

    # Obtener los trabajos seleccionados antes de filtrar
    current_selection = [job_listbox.get(i) for i in job_listbox.curselection()]

    # Añadir los trabajos actualmente seleccionados a la lista global (evitando duplicados)
    selected_jobs_global.update(current_selection)

    # Limpiar el listbox antes de actualizarlo con los resultados filtrados
    job_listbox.delete(0, tk.END)

    try:
        tree = ET.parse(attached_file_path)
        root = tree.getroot()
    except Exception as e:
        messagebox.showerror("Error", f"Error al leer el archivo XML: {e}")
        return

    jobs = root.findall('.//JOB')
    job_names_from_xml = [job.get('JOBNAME') for job in jobs]

    if not search_term:
        for job_name in job_names_from_xml:
            job_listbox.insert(tk.END, job_name)
    else:
        for job_name in job_names_from_xml:
            if search_term in job_name.lower():
                job_listbox.insert(tk.END, job_name)

    for i, job_name in enumerate(job_listbox.get(0, tk.END)):
        if job_name in selected_jobs_global:
            job_listbox.selection_set(i)

    update_selected_jobs_listbox()

def on_job_click(event):
    global selected_jobs_global

    clicked_index = job_listbox.nearest(event.y)
    clicked_job = job_listbox.get(clicked_index)

    if clicked_job in selected_jobs_global:
        selected_jobs_global.remove(clicked_job)
        job_listbox.selection_clear(clicked_index)
    else:
        selected_jobs_global.add(clicked_job)
        job_listbox.selection_set(clicked_index)

    update_selected_jobs_listbox()


def on_entry_click(event):
    if entry_buscar.get() == "Buscar job por nombre":
        entry_buscar.delete(0, tk.END)  # Eliminar el texto
        entry_buscar.config(fg='black')

def color_seleccion(event):
    if var_force.get() == True:
        check_force.config(fg="white")
    elif var_force.get() == False:
        check_force.config(fg="#00b89f")

def color_seleccion_2(event):
    if var_seleccion.get() == True:
        check_button.config(fg="white")
    elif var_seleccion.get() == False:
        check_button.config(fg="#00b89f")



def on_focusout(event):
    if entry_buscar.get() == "":
        entry_buscar.insert(0, "Buscar job por nombre")
        entry_buscar.config(fg='grey')

def validate_email(email):
    if re.fullmatch(REGEX_MAILS, email):
        return True
    else:
        return False

def validate_legajo(legajo):
    if re.fullmatch(REGEX_LEGAJO, legajo):
        return True
    else:
        return False

def seleccionar_todos():
    clicked_job = job_listbox.get(0,tk.END)
    if var_seleccion.get():
        job_listbox.select_set(0, tk.END)
        for i in clicked_job:
            selected_jobs_global.add(i)
    else:
        job_listbox.select_clear(0, tk.END)
        for i in clicked_job:
            selected_jobs_global.remove(i)

    update_selected_jobs_listbox()

def interfaz_seleccion_job():
    global job_listbox, selected_jobs_global, entry_buscar, caso_uso_var,\
        mail_entry, original_jobs, selected_jobs_listbox,legajo_var,var_seleccion,\
        var_force,check_force,check_button

    tk.Label(dias_jobs_frame, text="Mail:", font=("Arial", 12,"bold"),  bg="#131c46", fg ="white").grid(row=5, column=2, sticky="e", pady=5,
                                                                                 padx=5)
    mail_entry = tk.Entry(dias_jobs_frame, font=("Arial", 12))
    mail_entry.grid(row=5, column=3, pady=5, padx=(0,120))

    tk.Label(dias_jobs_frame, text="Legajo:", font=("Arial", 12,"bold"), bg="#131c46", fg ="white").grid(row=6, column=2, sticky="e",
                                                                                        pady=5, padx=5)
    legajo_var = tk.Entry(dias_jobs_frame, font=("Arial", 12))
    legajo_var.grid(row=6, column=3, pady=5, padx=(0,120))

    tk.Label(dias_jobs_frame, text="Caso de uso:", font=("Arial", 12, "bold"), bg="#131c46", fg="white").grid(row=7,
                                                                                                         column=2,
                                                                                                         sticky="e",
                                                                                                         pady=5, padx=5)

    caso_uso_var = tk.Entry(dias_jobs_frame, font=("Arial", 12))
    caso_uso_var.grid(row=7, column=3, pady=5, padx=(0,120))

    attachment_button = tk.Button(dias_jobs_frame, text="ADJUNTAR MALLA", command=select_attached_file,
                                  font=("Arial", 12,"bold"), bg="#3c4c8f",fg ="white")
    attachment_button.grid(row=0, column=3, pady=(0,45),padx=(50,0))

    var_seleccion = BooleanVar()
    var_force = BooleanVar()

    check_force = Checkbutton(dias_jobs_frame, text="FORCE ORDER JOB", variable=var_force,
                             font=("Arial", 10), bg="#131c46", fg="white")
    check_force.grid(row=0, column=2, columnspan=1, pady=(0, 100), padx=(46, 0))

    check_button = Checkbutton(dias_jobs_frame, text="SELECIONAR TODOS", variable=var_seleccion, command=seleccionar_todos,font=("Arial", 10),bg="#131c46", fg="white")
    check_button.grid(row=0, column=2, columnspan=1, pady=(0,50),padx=(56,0))


    entry_buscar = tk.Entry(dias_jobs_frame, font=("Arial", 14), fg='grey',width=42)
    entry_buscar.grid(row=0, column=2, columnspan=2, pady=(25,0), padx=(40,0))
    entry_buscar.insert(0, "Buscar job por nombre")

    entry_buscar.bind('<FocusIn>', on_entry_click)
    entry_buscar.bind('<FocusOut>', on_focusout)

    listbox_frame = tk.Frame(dias_jobs_frame)
    listbox_frame.grid(row=0, column=2, pady=(200, 0), padx=(40,0), columnspan=2)

    # Configurar el Listbox dentro del contenedor
    job_listbox = tk.Listbox(listbox_frame, selectmode="multiple", font=("Arial", 12), width=50, height=7,
                             # Ajusta height según necesites
                             yscrollcommand=lambda *args: scrollbar.set(*args))
    job_listbox.grid(row=0, column=0)

    # Configurar la Scrollbar dentro del mismo contenedor
    scrollbar = tk.Scrollbar(listbox_frame, orient="vertical", command=job_listbox.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")  # Solo el Listbox ocupa toda la altura

    # Enlazar la Scrollbar con el Listbox
    job_listbox.config(yscrollcommand=scrollbar.set)

    selected_jobs_label = tk.Label(dias_jobs_frame, text="JOBS SELECCIONADOS", font=("Arial", 16,"bold"), bg="#131c46", fg ="white")
    selected_jobs_label.grid(row=0, column=1, padx=5, pady=(0,10))
    selected_jobs_frame = tk.Frame(dias_jobs_frame)
    selected_jobs_frame.grid(row=0, column=1, padx=(20,0), pady=(200, 0))

    # Configurar el Listbox dentro del contenedor
    selected_jobs_listbox = tk.Listbox(selected_jobs_frame, selectmode="multiple", font=("Arial", 12), width=40,
                                       height=7,  # Ajusta el height según necesites
                                       yscrollcommand=lambda *args: scrollbar_selec.set(*args))
    selected_jobs_listbox.grid(row=0, column=0)

    # Configurar la Scrollbar dentro del mismo contenedor
    scrollbar_selec = tk.Scrollbar(selected_jobs_frame, orient="vertical", command=selected_jobs_listbox.yview)
    scrollbar_selec.grid(row=0, column=1, sticky="ns")  # La barra ocupa solo la altura del Listbox

    # Enlazar la Scrollbar con el Listbox
    selected_jobs_listbox.config(yscrollcommand=scrollbar_selec.set)

    # Vincular eventos a los Listbox
    entry_buscar.bind('<KeyRelease>', filtrar_jobs)
    job_listbox.bind('<ButtonRelease-1>', on_job_click)
    check_force.bind('<ButtonRelease-1>', color_seleccion)
    check_button.bind('<ButtonRelease-1>', color_seleccion_2)
    fecha_op1.bind('<Button-1>', color_fechas_op)
    fecha_op2.bind('<Button-1>', color_fechas_op)
    fecha_op3.bind('<Button-1>', color_fechas_op)



    # Botón para descargar la malla temporal modificada
    save_button = tk.Button(dias_jobs_frame, text="GENERAR MALLA TEMPORAL", command=confirmar_seleccion, font=("Arial", 12,"bold"), bg="#00b89f", fg ="white", width=28, height=3)
    save_button.grid(row=9, column=1, columnspan=2, padx=(200, 0), pady=8)

def guardar_fecha(fecha):
    global fechas_seleccionadas
    fecha_obj = datetime.strptime(fecha, "%m/%d/%y").date()
    fechas_seleccionadas.append(fecha_obj)

def abrir_calendario():
    global fechas_seleccionadas
    ventana_calendario = tk.Toplevel(dias_jobs_frame)
    ventana_calendario.title("Seleccionar Fechas")
    icon_path = "Sources/imagen/bbva.ico"
    ventana_calendario.iconbitmap(icon_path)

    calendario = Calendar(ventana_calendario, selectmode='day', year=2024, month=9, day=1)
    calendario.grid(row=0, column=0, padx=20, pady=20)

    calendario.tag_config('seleccion', background='lightblue', foreground='black')

    # Al cerrar el calendario, guarda la fecha seleccionada y cierra la ventana
    tk.Button(ventana_calendario, text="Cerrar y Guardar Fecha",
              command=lambda: [guardar_fecha(calendario.get_date()), ventana_calendario.destroy()]).grid(row=1,
                                                                                                         column=0,
                                                                                                         pady=10)
    # Asignar acción al hacer clic en una fecha
    calendario.bind("<<CalendarSelected>>", lambda event: seleccionar_fecha(calendario))

def actualizar_estado_entradas():
    # Verifica el valor de seleccion_var y deshabilita o habilita los DateEntry según corresponda
    if seleccion_var.get() == "carga_manual":
        start_date_entry.config(state='disabled')
        end_date_entry.config(state='disabled')
    else:
        start_date_entry.config(state="readonly")
        end_date_entry.config(state="readonly")
        calendario_button.config(state='disabled')

def color_fechas_op(event):
    event.widget.config(fg="#00b89f")

def actualizar_interfaz():
    global dias_jobs_frame, seleccion_var, fechas_seleccionadas, start_date_entry, end_date_entry,\
        calendario_button,fecha_op1,fecha_op2,fecha_op3

    titulo_label = tk.Label(dias_jobs_frame, text="GENERADOR MALLAS TEMPORALES", font=("Arial", 20, "bold"),
                            bg="#131c46",fg="#00b89f",width=55)

    titulo_label.grid(row=0, column=1, columnspan=3, pady=(0,280),padx=(0,1))

    fecha_op1 = tk.Radiobutton(dias_jobs_frame, text="  Días corridos  ", variable=seleccion_var, value="todos_los_dias",
                   font=("Arial", 12,"bold"), bg="#131c46", fg ="white", width=25,anchor="w", justify="left",
                   command=actualizar_estado_entradas)
    fecha_op1.grid(row=5, column=1, sticky="w", padx=10, pady=2)

    fecha_op2 = tk.Radiobutton(dias_jobs_frame, text="  Días hábiles  ", variable=seleccion_var, value="dias_habiles",
                   font=("Arial", 12,"bold"), bg="#131c46", fg ="white", width=25,anchor="w", justify="left",
                   command=actualizar_estado_entradas)
    fecha_op2.grid(row=6, column=1, sticky="w", padx=10, pady=2)

    fecha_op3 = tk.Radiobutton(dias_jobs_frame, text="  Carga manual    ", variable=seleccion_var, value="carga_manual",
                   font=("Arial", 12,"bold"), bg="#131c46", fg ="white", width=25,anchor="w", justify="left",
                   command=actualizar_estado_entradas)
    fecha_op3.grid(row=7, column=1, sticky="w", padx=10, pady=2)



    calendario_button = tk.Button(dias_jobs_frame, text="CALENDARIO MANUAL", font=("Arial", 12,"bold"), bg="#3c4c8f",fg ="white",
              command=abrir_calendario)
    calendario_button.grid(row=4, column=1, sticky="w", padx=10, pady=5)

    tk.Label(dias_jobs_frame, text="Desde:", font=("Arial", 12,"bold"),  bg="#131c46", fg ="white").grid(row=3, column=2, sticky="e",
                                                                                  pady=5, padx=5)
    start_date_entry = DateEntry(dias_jobs_frame, width=18, background='darkblue', foreground='white',
                                 borderwidth=2, font=("Arial", 12), date_pattern='dd/MM/yyyy',state="readonly")
    start_date_entry.grid(row=3, column=3, pady=5, padx=(0,120))

    tk.Label(dias_jobs_frame, text="Hasta:", font=("Arial", 12,"bold"),  bg="#131c46", fg ="white").grid(row=4, column=2, sticky="e",
                                                                                  pady=5, padx=5)
    end_date_entry = DateEntry(dias_jobs_frame, width=18, background='darkblue', foreground='white', borderwidth=2,
                               font=("Arial", 12), date_pattern='dd/MM/yyyy',state="readonly")
    end_date_entry.grid(row=4, column=3, pady=5, padx=(0,120))

    interfaz_seleccion_job()

def seleccionar_fecha(calendario):
    fecha_str = calendario.get_date()
    fecha_obj = datetime.strptime(fecha_str, "%m/%d/%y").date()
    global fechas_seleccionadas
    if fecha_obj not in fechas_seleccionadas:
        fechas_seleccionadas.append(fecha_obj)
        calendario.calevent_create(fecha_obj, "Seleccionada", "seleccion")
    else:
        fechas_seleccionadas.remove(fecha_obj)
        for event in calendario.get_calevents(fecha_obj):
            calendario.calevent_remove(event)

def mostrar_fechas(listbox):
    listbox.delete(0, tk.END)
    for fecha in fechas_seleccionadas:
        listbox.insert(tk.END, fecha)

def main():
    global original_jobs, selected_jobs_global,dias_jobs_frame,seleccion_var

    root = tk.Tk()
    root.title("Generador de Mallas Temporales - BBVA")
    icon_path = "Sources/imagen/bbva.ico"
    root.iconbitmap(icon_path)
    root.geometry("1000x700")
    root.resizable(True, True)
    # Cargar la imagen de fondo
    #bg_image = Image.open(os.path.join("Sources", "imagen", "logo_2.png"))
    #bg_image = bg_image.resize((1000, 700), Image.LANCZOS)
    #bg_photo = ImageTk.PhotoImage(bg_image)
    original_jobs = []

    dias_jobs_frame = tk.Frame(root, padx=4, pady=8, bg="#131c46", highlightthickness=0, relief="flat")
    dias_jobs_frame.pack(expand=True, fill="both")

    # Añadir la imagen de fondo al frame
    #bg_label1 = tk.Label(dias_jobs_frame, image=bg_photo, borderwidth=0, highlightthickness=0)
    #bg_label1.place(x=0, y=0, relwidth=1, relheight=1)

    # Configurar el grid para centrar el contenido
    dias_jobs_frame.grid_rowconfigure(0, weight=1)
    dias_jobs_frame.grid_rowconfigure(9, weight=1)
    dias_jobs_frame.grid_columnconfigure(0, weight=1)
    dias_jobs_frame.grid_columnconfigure(5, weight=1)

    fechas_seleccionadas = []

    seleccion_var = tk.StringVar(value="dias_habiles")

    actualizar_interfaz()
    start_date_entry.config(state="readonly")
    end_date_entry.config(state="readonly")
    calendario_button.config(state='disabled')
    seleccion_var.trace("w", lambda *args: actualizar_interfaz())

    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        messagebox.showerror(title="Error", message=str(e))
        logging.basicConfig(filename='error.log', level=logging.ERROR, filemode='w')
        logging.error("Se produjo un error: %s", e)
        logging.error(traceback.format_exc())
        exit(-1)
