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
import subprocess
import sys
import io
import traceback
import logging
import random
import os
import xml.etree.ElementTree as ET
import requests
import json
import pandas as pd
import pickle
import shutil
import re
import tkinter as tk
from collections import defaultdict
from Sources.funciones_control_m import ControlmDigrafo
from tkinter import ttk, messagebox, filedialog, simpledialog, Listbox, Scrollbar
from PIL import Image, ImageTk
from PIL.ImageOps import contain
from tkcalendar import DateEntry, Calendar
from datetime import datetime, timedelta
from tkinter.ttk import Treeview

current_year = datetime.now().year
api_url = f'https://api.argentinadatos.com/v1/feriados/{current_year}'

fechas_seleccionadas = []
selected_jobs_global = set()

REGEX_MAILS = r'[^@ \t\r\n]+@[^@ \t\r\n]+\.[^@ \t\r\n]+'

class JobData:
    def __init__(self, name, marcasout=None, marcasin=None):
        self.name = name
        self.marcasout = marcasout if marcasout is not None else []
        self.marcasin = marcasin if marcasin is not None else []

    def __repr__(self):
        return f"JobData(name={self.name}, marcasout={self.marcasout}, marcasin={self.marcasin})"

def ruta_absoluta(rel_path):
    if hasattr(sys, 'frozen'):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, rel_path)

ruta_modelo = ruta_absoluta('model.h5')

class JobData:
    def __init__(self, name, marcasout=None, marcasin=None):
        self.name = name
        self.marcasout = marcasout if marcasout is not None else []
        self.marcasin = marcasin if marcasin is not None else []

    def __repr__(self):
        return f"JobData(name={self.name}, marcasout={self.marcasout}, marcasin={self.marcasin})"

    def get_prerequisitos(self):
        # Devuelve una lista con los nombres de los prerequisitos (marcasin)
        return [marca.name for marca in self.marcasin]

class MarcaOut:
    def __init__(self, name, signo):
        self.name = name
        self.signo = signo

def preparar_datos_para_digrafo(jobs):
    job_data = []
    for job in jobs:
        job_name = job.get('JOBNAME')

        marcasout = [MarcaOut(marca.get('NAME'), marca.get('SIGN')) for marca in job.findall('.//OUTCOND')]
        marcasin = [MarcaOut(marca.get('NAME'), marca.get('SIGN')) for marca in job.findall('.//INCOND')]

        if job_name:
            job_data.append(JobData(name=job_name, marcasout=marcasout, marcasin=marcasin))

    return job_data

def es_fecha_valida(fecha):
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        feriados_data = response.json()
        non_chamba_days = set()
        for feriado in feriados_data:
            fecha_feriado = datetime.strptime(feriado['fecha'], '%Y-%m-%d').date()
            non_chamba_days.add(fecha_feriado)
    except requests.exceptions.RequestException as e:
        print(f"Error al consultar la API de feriados: {e}")
        non_chamba_days = set()
    return fecha.weekday() < 5 and fecha not in non_chamba_days

def ordenar_jobs_creados_por_dependencias(dependencias, jobs_creados):
    # Agrupar jobs creados por ODATE
    jobs_por_odate = defaultdict(list)
    for job_nuevo, job_original, odate in jobs_creados:
        jobs_por_odate[odate].append((job_nuevo, job_original, odate))

    jobs_creados_ordenados = []
    usados = set()

    # Recorrer cada ODATE y ordenar por dependencias
    for odate, jobs_con_odate in sorted(jobs_por_odate.items()):
        # Ordenar por dependencias dentro del mismo ODATE
        for dep in dependencias:
            job_deja_marca, job_recibe_marca = dep

            # Buscar el job correspondiente en jobs_con_odate
            for job_nuevo, job_original, odate_actual in jobs_con_odate:
                if job_original == job_recibe_marca and job_nuevo not in usados and odate_actual == odate:
                    jobs_creados_ordenados.append((job_nuevo, job_original, odate_actual))
                    usados.add(job_nuevo)

                    # Buscar el job que deja la marca (predecesor en la dependencia)
                    for job_nuevo_predecesor, job_original_predecesor, odate_predecesor in jobs_con_odate:
                        if job_original_predecesor == job_deja_marca and job_nuevo_predecesor not in usados:
                            jobs_creados_ordenados.append(
                                (job_nuevo_predecesor, job_original_predecesor, odate_predecesor))
                            usados.add(job_nuevo_predecesor)
                            break

    # Agregar los jobs que no fueron procesados en las dependencias
    for job_nuevo, job_original, odate in jobs_creados:
        if job_nuevo not in usados:
            jobs_creados_ordenados.append((job_nuevo, job_original, odate))
            usados.add(job_nuevo)

    return jobs_creados_ordenados

def modificar_malla(filename, mail_personal, start_date, end_date, selected_jobs, caso_de_uso, fechas_pross, fechas_manual=None):
    global new_filename, xml_buffer
    """
    Función para modificar la malla.

    Esta función ahora acepta las fechas seleccionadas como parámetro opcional.

    :param filename: Es el archivo adjunto(Malla)
    :param mail_personal: toma el mail ingresado
    :param fechas_pross: toma el fechas de la opcion
    :param fechas: Lista de fechas seleccionadas. Si no se pasan, se usará la variable global fechas_seleccionadas.
    """
    random_number = str(random.randint(10, 99))
    current_date = start_date
    tree = ET.parse(filename)
    root = tree.getroot()
    jobs = root.findall('.//JOB')
    jobs_data = preparar_datos_para_digrafo(jobs)
    controlM_digrafo = ControlmDigrafo(jobs_data)
    application_value = root.find('.//JOB').get('APPLICATION')
    if application_value:
        app_prefix = application_value[:3]
    else:
        app_prefix = "None"  # Si no se encuentra APPLICATION

    folder_name = root.find('.//FOLDER').get('FOLDER_NAME')
    if folder_name:
        new_folder_name = f"CR-AR{app_prefix}TMP-T{random_number}"
        root.find('.//FOLDER').set('FOLDER_NAME', new_folder_name)
        root.find('.//FOLDER').set('FOLDER_ORDER_METHOD', "PRUEBAS")
    jobs_creados = []

    deja_marca = None
    recibe_marca = None

    primer_job = False
    segudo_resto = False

    dependencias = []
    depen = []
    for job_name in selected_jobs:
        cadena_descendente = controlM_digrafo.recorrer_cadena(job_name)
        cadena_ascendente = controlM_digrafo.recorrer_cadena_inversa(job_name)
        cadena_completa = list(set(cadena_descendente + cadena_ascendente))
        pares_xy = controlM_digrafo.obtener_paresxy()
        for parxy in pares_xy:
            if parxy[0] in cadena_completa and parxy[1] in cadena_completa:
                depen.append((parxy[0], parxy[1]))

    for job in root.findall('.//JOB'):
        job_name = job.get('JOBNAME')

        # Si el job contiene "TP" en su nombre, iniciamos el proceso de búsqueda de dependencias
        if "TP" in job_name:
            siguiente_job = job  # El siguiente job a procesar inicialmente es el que contiene "TP"

            while siguiente_job is not None:
                encontrado = False  # Bandera para verificar si se encontró un job con SIGN="+"

                for outcond in siguiente_job.findall('.//OUTCOND'):
                    outcond_name = outcond.get('NAME')  # Obtener el nombre de la marca
                    sign = outcond.get('SIGN')

                    # Si la marca tiene SIGN="+", es una marca de dependencia válida
                    if sign == "+" and '-TO-' in outcond_name:
                        partes = outcond_name.split('-TO-')
                        if len(partes) == 2:
                            quien_deja_marca = partes[0]  # Job que deja la marca
                            quien_recibe_marca = partes[1]  # Job que recibe la marca

                            # Añadir la dependencia a la lista
                            dependencias.append((quien_deja_marca, quien_recibe_marca))

                            # Buscar el siguiente job en la cadena de dependencias
                            for siguiente in root.findall('.//JOB'):
                                if siguiente.get('JOBNAME') == quien_recibe_marca:
                                    siguiente_job = siguiente
                                    encontrado = True
                                    break


                if not encontrado:
                    siguiente_job = None

    for job in root.findall('.//JOB'):
        job_name = job.get('JOBNAME')
        if job_name not in selected_jobs:
            root.find('.//FOLDER').remove(job)

    jobs_to_duplicate = [job for job in root.findall('.//JOB') if job.get('JOBNAME') in selected_jobs]

    random_job_suffix = f"9{random.randint(1, 100):03}"
    job_suffix_count = int(random_job_suffix)

    i = 0

    if fechas_manual is None:
        while current_date <= end_date:
            if es_fecha_valida(current_date) and fechas_pross == "dias_habiles":
                for job in jobs_to_duplicate:
                    original_job_name = job.get('JOBNAME')

                    new_job = ET.Element("JOB", job.attrib)
                    new_job.attrib = job.attrib.copy()

                    new_job_name = original_job_name[:-4] + f"{job_suffix_count:04}"
                    new_job.set('JOBNAME', new_job_name)
                    job_suffix_count += 1

                    for var in job.findall('.//VARIABLE'):
                        modified_var_attrib = var.attrib.copy()
                        if '%%$ODATE' in modified_var_attrib.get('VALUE', ''):
                            modified_var_attrib['VALUE'] = modified_var_attrib['VALUE'].replace('%%$ODATE',
                                                                                                current_date.strftime(
                                                                                                    '%Y%m%d'))
                        if '%%MAIL' in modified_var_attrib.get('NAME', ''):
                            modified_var_attrib['NAME'] = modified_var_attrib['NAME'].replace('%%MAIL', mail_personal)
                        new_var = ET.SubElement(new_job, "VARIABLE", modified_var_attrib)
                        new_var.text = var.text

                    for on_element in job.findall('.//ON'):
                        new_on = ET.SubElement(new_job, "ON", {k: (v if v is not None else '') for k, v in on_element.attrib.items()})
                        for sub_element in on_element:
                            new_sub_element = ET.SubElement(new_on, sub_element.tag, sub_element.attrib)
                            new_sub_element.text = sub_element.text
                            if sub_element.get('CC_DEST'):
                                new_sub_element.set('CC_DEST', mail_personal)
                            if 'Ok' in sub_element.get('SUBJECT', ''):
                                new_sub_element.set('SUBJECT', sub_element.get('SUBJECT').replace('Ok', caso_de_uso))
                            if 'Cancelo' in sub_element.get('SUBJECT', ''):
                                new_sub_element.set('SUBJECT', sub_element.get('SUBJECT').replace('Cancelo', caso_de_uso))

                    for qua in job.findall('.//QUANTITATIVE'):
                        modified_qua_attrib = {k: (v if v is not None else '') for k, v in qua.attrib.items()}
                        if modified_qua_attrib['NAME'] == "ARD":
                            pass
                        else:
                            modified_qua_attrib['NAME'] = "ARD"
                            ET.SubElement(new_job, "QUANTITATIVE", modified_qua_attrib)

                        modified_qua_attrib_tmp = qua.attrib.copy()
                        if modified_qua_attrib_tmp['NAME'] == "ARD-TMP":
                            pass
                        else:
                            modified_qua_attrib_tmp['NAME'] = "ARD-TMP"
                            ET.SubElement(new_job, "QUANTITATIVE", modified_qua_attrib_tmp)

                    sub_application = new_job.get('SUB_APPLICATION')
                    if sub_application == "DATIO-AR-CCR":
                        new_job.set('SUB_APPLICATION', "DATIO-AR-P")

                    parent_folder = new_job.get('PARENT_FOLDER')
                    if parent_folder:
                        new_parent_folder = f"CR-AR{app_prefix}TMP-T{random_number}"
                        new_job.set('PARENT_FOLDER', new_parent_folder)

                    max_wait = new_job.get('MAXWAIT')
                    if max_wait != "0":
                        new_job.set('MAXWAIT', "0")

                    scheduling = new_job.get('DAYSCAL')
                    if scheduling:
                        scheduling = new_job.attrib.pop('DAYSCAL', None)

                    scheduling_calen = new_job.get('DAYS')
                    if scheduling_calen:
                        scheduling_calen = new_job.attrib.pop('DAYS', None)

                    create_user_by = new_job.get('CREATED_BY')
                    if create_user_by:
                        create_user_by = new_job.attrib.pop('CREATED_BY', None)

                    jobs_creados.append((new_job_name,original_job_name,current_date.strftime('%Y%m%d')))
                    root.find('.//FOLDER').append(new_job)

            elif fechas_pross == "todos_los_dias":
                for job in jobs_to_duplicate:
                    original_job_name = job.get('JOBNAME')

                    new_job = ET.Element("JOB", job.attrib)
                    new_job.attrib = job.attrib.copy()

                    new_job_name = original_job_name[:-4] + f"{job_suffix_count:04}"
                    new_job.set('JOBNAME', new_job_name)
                    job_suffix_count += 1

                    for var in job.findall('.//VARIABLE'):
                        modified_var_attrib = var.attrib.copy()
                        if '%%$ODATE' in modified_var_attrib.get('VALUE', ''):
                            modified_var_attrib['VALUE'] = modified_var_attrib['VALUE'].replace('%%$ODATE',
                                                                                                current_date.strftime(
                                                                                                    '%Y%m%d'))
                        if '%%MAIL' in modified_var_attrib.get('NAME', ''):
                            modified_var_attrib['NAME'] = modified_var_attrib['NAME'].replace('%%MAIL', mail_personal)
                        new_var = ET.SubElement(new_job, "VARIABLE", modified_var_attrib)
                        new_var.text = var.text

                    for on_element in job.findall('.//ON'):
                        new_on = ET.SubElement(new_job, "ON", {k: (v if v is not None else '') for k, v in on_element.attrib.items()})
                        for sub_element in on_element:
                            new_sub_element = ET.SubElement(new_on, sub_element.tag, sub_element.attrib)
                            new_sub_element.text = sub_element.text
                            if sub_element.get('CC_DEST'):
                                new_sub_element.set('CC_DEST', mail_personal)
                            if 'Ok' in sub_element.get('SUBJECT', ''):
                                new_sub_element.set('SUBJECT', sub_element.get('SUBJECT').replace('Ok', caso_de_uso))
                            if 'Cancelo' in sub_element.get('SUBJECT', ''):
                                new_sub_element.set('SUBJECT', sub_element.get('SUBJECT').replace('Cancelo', caso_de_uso))

                    for qua in job.findall('.//QUANTITATIVE'):
                        modified_qua_attrib = {k: (v if v is not None else '') for k, v in qua.attrib.items()}
                        if modified_qua_attrib['NAME'] == "ARD":
                            pass
                        else:
                            modified_qua_attrib['NAME'] = "ARD"
                            ET.SubElement(new_job, "QUANTITATIVE", modified_qua_attrib)

                        modified_qua_attrib_tmp = qua.attrib.copy()
                        if modified_qua_attrib_tmp['NAME'] == "ARD-TMP":
                            pass
                        else:
                            modified_qua_attrib_tmp['NAME'] = "ARD-TMP"
                            ET.SubElement(new_job, "QUANTITATIVE", modified_qua_attrib_tmp)

                    sub_application = new_job.get('SUB_APPLICATION')
                    if sub_application == "DATIO-AR-CCR":
                        new_job.set('SUB_APPLICATION', "DATIO-AR-P")

                    parent_folder = new_job.get('PARENT_FOLDER')
                    if parent_folder:
                        new_parent_folder = f"CR-AR{app_prefix}TMP-T{random_number}"
                        new_job.set('PARENT_FOLDER', new_parent_folder)

                    max_wait = new_job.get('MAXWAIT')
                    if max_wait != "0":
                        new_job.set('MAXWAIT', "0")

                    scheduling = new_job.get('DAYSCAL')
                    if scheduling:
                        scheduling = new_job.attrib.pop('DAYSCAL', None)

                    scheduling_calen = new_job.get('DAYS')
                    if scheduling_calen:
                        scheduling_calen = new_job.attrib.pop('DAYS', None)

                    create_user_by = new_job.get('CREATED_BY')
                    if create_user_by:
                        create_user_by = new_job.attrib.pop('CREATED_BY', None)

                    jobs_creados.append((new_job_name,original_job_name,current_date.strftime('%Y%m%d')))
                    root.find('.//FOLDER').append(new_job)
            current_date += timedelta(days=1)

    elif fechas_manual:
        while i < len(fechas_manual):
            current_date = datetime.strptime(fechas_manual[i], "%Y-%m-%d").date()
            if fechas_pross == "carga_manual":
                for job in jobs_to_duplicate:
                    original_job_name = job.get('JOBNAME')

                    new_job = ET.Element("JOB", job.attrib)
                    new_job.attrib = job.attrib.copy()

                    new_job_name = original_job_name[:-4] + f"{job_suffix_count:04}"
                    new_job.set('JOBNAME', new_job_name)
                    job_suffix_count += 1

                    for var in job.findall('.//VARIABLE'):
                        modified_var_attrib = var.attrib.copy()
                        if '%%$ODATE' in modified_var_attrib.get('VALUE', ''):
                            modified_var_attrib['VALUE'] = modified_var_attrib['VALUE'].replace('%%$ODATE',
                                                                                                current_date.strftime(
                                                                                                    '%Y%m%d'))
                        if '%%MAIL' in modified_var_attrib.get('NAME', ''):
                            modified_var_attrib['NAME'] = modified_var_attrib['NAME'].replace('%%MAIL', mail_personal)
                        new_var = ET.SubElement(new_job, "VARIABLE", modified_var_attrib)
                        new_var.text = var.text

                    for on_element in job.findall('.//ON'):
                        new_on = ET.SubElement(new_job, "ON", {k: (v if v is not None else '') for k, v in on_element.attrib.items()})
                        for sub_element in on_element:
                            new_sub_element = ET.SubElement(new_on, sub_element.tag, sub_element.attrib)
                            new_sub_element.text = sub_element.text
                            if sub_element.get('CC_DEST'):
                                new_sub_element.set('CC_DEST', mail_personal)
                            if 'Ok' in sub_element.get('SUBJECT', ''):
                                new_sub_element.set('SUBJECT', sub_element.get('SUBJECT').replace('Ok', caso_de_uso))
                            if 'Cancelo' in sub_element.get('SUBJECT', ''):
                                new_sub_element.set('SUBJECT', sub_element.get('SUBJECT').replace('Cancelo', caso_de_uso))

                    for qua in job.findall('.//QUANTITATIVE'):
                        modified_qua_attrib = {k: (v if v is not None else '') for k, v in qua.attrib.items()}
                        if modified_qua_attrib['NAME'] == "ARD":
                            pass
                        else:
                            modified_qua_attrib['NAME'] = "ARD"
                            ET.SubElement(new_job, "QUANTITATIVE", modified_qua_attrib)

                        modified_qua_attrib_tmp = qua.attrib.copy()
                        if modified_qua_attrib_tmp['NAME'] == "ARD-TMP":
                            pass
                        else:
                            modified_qua_attrib_tmp['NAME'] = "ARD-TMP"
                            ET.SubElement(new_job, "QUANTITATIVE", modified_qua_attrib_tmp)

                    sub_application = new_job.get('SUB_APPLICATION')
                    if sub_application == "DATIO-AR-CCR":
                        new_job.set('SUB_APPLICATION', "DATIO-AR-P")

                    parent_folder = new_job.get('PARENT_FOLDER')
                    if parent_folder:
                        new_parent_folder = f"CR-AR{app_prefix}TMP-T{random_number}"
                        new_job.set('PARENT_FOLDER', new_parent_folder)

                    max_wait = new_job.get('MAXWAIT')
                    if max_wait != "0":
                        new_job.set('MAXWAIT', "0")

                    scheduling = new_job.get('DAYSCAL')
                    if scheduling:
                        scheduling = new_job.attrib.pop('DAYSCAL', None)

                    scheduling_calen = new_job.get('DAYS')
                    if scheduling_calen:
                        scheduling_calen = new_job.attrib.pop('DAYS', None)

                    create_user_by = new_job.get('CREATED_BY')
                    if create_user_by:
                        create_user_by = new_job.attrib.pop('CREATED_BY', None)

                    jobs_creados.append((new_job_name,original_job_name,current_date.strftime('%Y%m%d')))
                    root.find('.//FOLDER').append(new_job)
        i += 1


    for job in jobs_to_duplicate:
        root.find('.//FOLDER').remove(job)

    jobs_creados_ordenados = ordenar_jobs_creados_por_dependencias(dependencias, jobs_creados)
    job_agregar_marcas = []
    for x in jobs_creados_ordenados:
        job_agregar_marcas.append(x[0])

    for i in range(len(job_agregar_marcas) - 1):
        deja_marca = job_agregar_marcas[i]
        recibe_marca = job_agregar_marcas[i + 1]

        for job in root.findall('.//JOB'):
            if job.get('JOBNAME') == deja_marca:
                marca_mofied_attrib = {
                    'NAME': f"{deja_marca}-TO-{recibe_marca}",
                    'ODATE': "ODAT",
                    'SIGN': "+"
                }
                ET.SubElement(job, "OUTCOND", marca_mofied_attrib)

            elif job.get('JOBNAME') == recibe_marca:
                marca_mofied_attrib = {
                    'NAME': f"{deja_marca}-TO-{recibe_marca}",
                    'ODATE': "ODAT",
                    'SIGN': "-"
                }
                ET.SubElement(job, "OUTCOND", marca_mofied_attrib)
                prere__mofied_attrib = {
                    'NAME': f"{deja_marca}-TO-{recibe_marca}",
                    'ODATE': "ODAT",
                    'AND_OR': "A"
                }
                ET.SubElement(job, "INCOND", prere__mofied_attrib)



    new_filename = f"CR-AR{app_prefix}TMP-T{random_number}.xml"
    xml_buffer = io.BytesIO()
    tree.write(xml_buffer, encoding='utf-8', xml_declaration=True)
    return new_filename

def select_attached_file():
    global attached_file_path, jobs

    attached_file_path = filedialog.askopenfilename(title="Selecciona una malla XML",
                                                    filetypes=[("XML files", "*.xml")])

    if attached_file_path:

        tree = ET.parse(attached_file_path)
        root = tree.getroot()


        jobs = root.findall('.//JOB')

        job_listbox.delete(0, tk.END)
        selected_jobs_listbox.delete(0, tk.END)

        job_names_from_xml = [job.get('JOBNAME') for job in jobs]

        for job_name in job_names_from_xml:
            job_listbox.insert(tk.END, job_name)

        messagebox.showinfo("Éxito", "Archivo adjunto cargado correctamente.")

def save_job():
    global new_filename,xml_buffer
    if not new_filename or not xml_buffer:
        messagebox.showwarning("Advertencia", "No hay malla modificada para descargar o el archivo no existe.")
        return

    save_path = filedialog.asksaveasfilename(defaultextension=".xml", filetypes=[("XML files", "*.xml")],
                                             initialfile=os.path.basename(modified_file_path))

    if save_path:
        with open(save_path, 'wb') as f:
            f.write(xml_buffer.getvalue())
        messagebox.showinfo("Éxito", f"Malla descargada en: {save_path}")

def confirmar_seleccion():
    global modified_file_path
    global caso_uso_var
    global mail_entry
    global start_date_entry
    global end_date_entry

    email = mail_entry.get()
    if not validate_email(email):
        messagebox.showerror("Mail inválido", "Por favor, ingrese un Mail válido.")
        return
    # Obtener los jobs seleccionados
    selected_indices = job_listbox.curselection()
    selected_jobs = [job_listbox.get(i) for i in selected_indices]

    # Llamar a la función modificar_malla con los jobs seleccionados
    if selected_jobs and attached_file_path and caso_uso_var.get() and mail_entry.get() and seleccion_var.get() != "carga_manual":
        modified_file_path = modificar_malla(attached_file_path, mail_entry.get(), start_date_entry.get_date(),
                                             end_date_entry.get_date(), selected_jobs, caso_uso_var.get(),seleccion_var.get(), None)
        messagebox.showinfo("Éxito", "La malla ha sido modificada y guardada temporalmente.")
    elif selected_jobs  and attached_file_path and caso_uso_var.get() and mail_entry.get() and seleccion_var.get() == "carga_manual":
        modified_file_path = modificar_malla(attached_file_path, mail_entry.get(), None,
                                             None, selected_jobs, caso_uso_var.get(),
                                             seleccion_var.get(), fechas_seleccionadas)
    elif not caso_uso_var.get() or not mail_entry.get():
        messagebox.showwarning("Advertencia", "Por favor, completar todos los campos.")
    else:
        messagebox.showwarning("Advertencia", "Por favor, adjunte un archivo y al menos un job.")

def get_next_valid_date(fecha):
    while not es_fecha_valida(fecha):
        fecha += timedelta(days=1)
    return fecha

def update_selected_jobs_listbox():
    global selected_jobs_global,selected_jobs_listbox
    selected_jobs_listbox.delete(0, tk.END)
    for job in selected_jobs_global:
        selected_jobs_listbox.insert(tk.END, job)

def filtrar_jobs(event):
    global jobs, attached_file_path,selected_jobs_global
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
    if entry_buscar.get() == "Seleccione jobs":
        entry_buscar.delete(0, tk.END)  # Eliminar el texto
        entry_buscar.config(fg='black')

def on_focusout(event):
    if entry_buscar.get() == "":
        entry_buscar.insert(0, "Seleccione jobs")
        entry_buscar.config(fg='grey')

def validate_email(email):
    if re.fullmatch(REGEX_MAILS, email):
        return True
    else:
        return False

def interfaz_seleccion_job():
    global job_listbox, selected_jobs_global, entry_buscar, caso_uso_var, mail_entry, original_jobs,selected_jobs_listbox

    tk.Label(dias_jobs_frame, text="Mail:", font=("Arial", 12), bg="white").grid(row=3, column=2, sticky="e", pady=5,
                                                                                 padx=5)
    mail_entry = tk.Entry(dias_jobs_frame, font=("Arial", 12))
    mail_entry.grid(row=3, column=3, pady=5, padx=5)

    tk.Label(dias_jobs_frame, text="Caso de Uso:", font=("Arial", 12), bg="white").grid(row=4, column=2, sticky="e",
                                                                                        pady=5, padx=5)
    caso_uso_var = tk.StringVar(value="Reliability")
    caso_uso_menu = tk.OptionMenu(dias_jobs_frame, caso_uso_var, "CDD/BAU", "HORIZON A", "HORIZON B", "HORIZON C",
                                  "DATIO EVO", "ADA", "Digital work place", "Reliability", "ALPHA", "Reclamos",
                                  "BCBS239")
    caso_uso_menu.config(font=("Arial", 12))
    caso_uso_menu.grid(row=4, column=3, pady=5, padx=5)

    attachment_button = tk.Button(dias_jobs_frame, text="Adjuntar malla", command=select_attached_file,
                                  font=("Arial", 12))
    attachment_button.grid(row=5, column=2, columnspan=2, pady=10)

    entry_buscar = tk.Entry(dias_jobs_frame, font=("Arial", 12), fg='grey')
    entry_buscar.grid(row=6, column=2, columnspan=2, pady=5, padx=2, sticky="ew")
    entry_buscar.insert(0, "Seleccione jobs")

    entry_buscar.bind('<FocusIn>', on_entry_click)
    entry_buscar.bind('<FocusOut>', on_focusout)

    scrollbar = tk.Scrollbar(dias_jobs_frame, orient="vertical")
    job_listbox = tk.Listbox(dias_jobs_frame, selectmode="multiple", font=("Arial", 12), width=50, height=7,
                             yscrollcommand=scrollbar.set)
    job_listbox.grid(row=7, column=2, columnspan=2, pady=5, padx=2)
    scrollbar.config(command=job_listbox.yview)
    scrollbar.grid(row=7, column=4, sticky="ns", padx=(0, 30) ,pady=5)

    selected_jobs_label = tk.Label(dias_jobs_frame, text="Jobs Seleccionados", font=("Arial", 12), bg="white")
    selected_jobs_label.grid(row=6, column=1, padx=5, pady=5)
    scrollbar_selec = tk.Scrollbar(dias_jobs_frame, orient="vertical")
    selected_jobs_listbox = tk.Listbox(dias_jobs_frame, selectmode="multiple", font=("Arial", 12), width=40, height=7,yscrollcommand=scrollbar_selec.set)
    selected_jobs_listbox.grid(row=7, column=1, padx=(0, 40), pady=2)
    scrollbar_selec.config(command=selected_jobs_listbox.yview)
    scrollbar_selec.grid(row=7, column=0, sticky="ns", padx=(60, 0), pady=5)

    # Vincular eventos a los Listbox
    entry_buscar.bind('<KeyRelease>', filtrar_jobs)
    job_listbox.bind('<ButtonRelease-1>', on_job_click)

    confirm_button = tk.Button(dias_jobs_frame, text="Confirmar Selección", command=confirmar_seleccion,
                               font=("Arial", 12),width=20)
    confirm_button.grid(row=8, column=1, columnspan=2,padx=(200, 0), pady=8)

    # Botón para descargar la malla temporal modificada
    save_button = tk.Button(dias_jobs_frame, text="Descargar Temporal", command=save_job, font=("Arial", 12),width=20)
    save_button.grid(row=9, column=1, columnspan=2, padx=(200, 0),pady=8)

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
    tk.Button(ventana_calendario, text="Cerrar y Guardar Fecha", command=lambda: [guardar_fecha(calendario.get_date()), ventana_calendario.destroy()]).grid(row=1, column=0, pady=10)

    # Asignar acción al hacer clic en una fecha
    calendario.bind("<<CalendarSelected>>", lambda event: seleccionar_fecha(calendario))

def actualizar_interfaz():
    global dias_jobs_frame
    global seleccion_var
    global fechas_seleccionadas
    global start_date_entry
    global end_date_entry

    # Limpiar widgets previos
    for widget in dias_jobs_frame.winfo_children():
        widget.grid_forget()

    titulo_label = tk.Label(dias_jobs_frame, text="Generador Mallas Reliability", font=("Arial", 16, "bold"),
                            bg="white")

    titulo_label.grid(row=0, column=1, columnspan=3, pady=10)

    tk.Radiobutton(dias_jobs_frame, text="Seleccionar todos los días", variable=seleccion_var, value="todos_los_dias",
                   font=("Arial", 12), bg="white").grid(row=2, column=1, sticky="w", padx=10, pady=5)
    tk.Radiobutton(dias_jobs_frame, text="Seleccionar días hábiles", variable=seleccion_var, value="dias_habiles",
                   font=("Arial", 12), bg="white").grid(row=3, column=1, sticky="w", padx=10, pady=5)
    tk.Radiobutton(dias_jobs_frame, text="Carga manual (sin rango)", variable=seleccion_var, value="carga_manual",
                   font=("Arial", 12), bg="white").grid(row=4, column=1, sticky="w", padx=10, pady=5)

    if seleccion_var.get() == "carga_manual":
        tk.Button(dias_jobs_frame, text="Calendario manual", font=("Arial", 12), bg="white", command=abrir_calendario).grid(row=1, column=3, padx=10, pady=10)

        interfaz_seleccion_job()

    else:
        # Mostrar las opciones "Desde" y "Hasta"
        tk.Label(dias_jobs_frame, text="Desde:", font=("Arial", 12), bg="white").grid(row=1, column=2, sticky="e", pady=5, padx=5)
        start_date_entry = DateEntry(dias_jobs_frame, width=15, background='darkblue', foreground='white', borderwidth=2, font=("Arial", 12), date_pattern='dd/MM/yyyy')
        start_date_entry.grid(row=1, column=3, pady=5, padx=5)

        tk.Label(dias_jobs_frame, text="Hasta:", font=("Arial", 12), bg="white").grid(row=2, column=2, sticky="e", pady=5, padx=5)
        end_date_entry = DateEntry(dias_jobs_frame, width=15, background='darkblue', foreground='white', borderwidth=2, font=("Arial", 12), date_pattern='dd/MM/yyyy')
        end_date_entry.grid(row=2, column=3, pady=5, padx=5)

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
    listbox.delete(0, tk.END)  # Limpiar el ListBox antes de agregar las fechas
    for fecha in fechas_seleccionadas:
        listbox.insert(tk.END, fecha)
    print(f"Fechas seleccionadas: {fechas_seleccionadas}")

def main():
    global original_jobs,selected_jobs_global

    try:
        root = tk.Tk()
        root.title("Generador de Mallas Temporales - BBVA")
        icon_path = "Sources/imagen/bbva.ico"
        root.iconbitmap(icon_path)
        root.geometry("1000x700")
        root.resizable(False, False)
        global dias_jobs_frame
        # Cargar la imagen de fondo
        bg_image = Image.open(os.path.join("Sources", "imagen", "logo_2.png"))
        bg_image = bg_image.resize((1000, 700), Image.LANCZOS)
        bg_photo = ImageTk.PhotoImage(bg_image)
        original_jobs = []

        dias_jobs_frame = tk.Frame(root, padx=4, pady=8, bg="white", highlightthickness=0, relief="flat")
        dias_jobs_frame.pack(expand=True, fill="both")


        # Añadir la imagen de fondo al frame
        bg_label1 = tk.Label(dias_jobs_frame, image=bg_photo, borderwidth=0, highlightthickness=0)
        bg_label1.place(x=0, y=0, relwidth=1, relheight=1)

        # Configurar el grid para centrar el contenido
        dias_jobs_frame.grid_rowconfigure(0, weight=1)
        dias_jobs_frame.grid_rowconfigure(9, weight=1)
        dias_jobs_frame.grid_columnconfigure(0, weight=1)
        dias_jobs_frame.grid_columnconfigure(5, weight=1)

        fechas_seleccionadas = []

        global seleccion_var
        seleccion_var = tk.StringVar(value="dias_habiles")

        actualizar_interfaz()  # Llamar a la función de actualización

        seleccion_var.trace("w", lambda *args: actualizar_interfaz())

        root.mainloop()

    except Exception as e:
        # Manejo de errores y logging
        logging.basicConfig(filename='error_log.txt', level=logging.ERROR)
        logging.error("Se produjo un error: %s", e)
        logging.error(traceback.format_exc())
        print(f"Se produjo un error: {e}")
        input("Presiona Enter para salir...")  # Evitar que la aplicación se cierre inmediatamente

if __name__ == "__main__":
    main()

