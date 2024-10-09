"""
Contrastador de mallas.

Analiza diferencias entre dos mallas exportadas de control M y logea en un archivo para posterior análisis. También
realiza controles en una de ellas (la ambientada)

Requiere Python >= 3.10
Motivo: Uso de Structural Pattern Matching y nueva sintaxis de type hints
"""

from __future__ import annotations

import time
import datetime
import os

from pathlib import Path

from controlm import ControlRecorder, validaciones, diferencia
from controlm import DiffRecorder
from controlm import utils
from controlm import ControlmFolder
from controlm.constantes import Carpetas


if __name__ == '__main__':

    path_work = Path(os.path.join(os.getcwd(), Carpetas.WORK_FOLDERNAME))
    if not path_work.exists():
        os.mkdir(Carpetas.WORK_FOLDERNAME)
        msg = f"Colocar los xml correspondientes en las carpetas {Carpetas.WORK_FOLDERNAME} y {Carpetas.LIVE_FOLDERNAME}\n"
        msg += f"Si solo se quieren realizar controles colocar el xml en la carpeta {Carpetas.WORK_FOLDERNAME}"
        print(msg)

    path_live = Path(os.path.join(os.getcwd(), Carpetas.LIVE_FOLDERNAME))
    if not path_live.exists():
        os.mkdir(Carpetas.LIVE_FOLDERNAME)

    crono_start = time.perf_counter()

    control_record = ControlRecorder()
    diff_record = DiffRecorder()

    work_xml_filename = utils.obtener_xmlpath(Carpetas.WORK_FOLDERNAME)
    live_xml_filename = utils.obtener_xmlpath(Carpetas.LIVE_FOLDERNAME)

    if work_xml_filename is None:
        msg = f"No se encontró un archivo xml en la carpeta {Carpetas.WORK_FOLDERNAME}. asegurarse de que esté colocado en el directorio y volver a ejecutar el script"
        raise FileNotFoundError(msg)
    else:
        malla_work = ControlmFolder(xml_input=work_xml_filename)

    comparar_con_live = True
    if live_xml_filename is None:
        comparar_con_live = False
        malla_live = None
        jobnames_nuevos = None
        print(f"INFO: No se encontró un archivo xml en la carpeta {Carpetas.LIVE_FOLDERNAME}. No se analizarán diferencias, solo se realizarán controles")
    else:
        malla_live = ControlmFolder(xml_input=live_xml_filename)
        jobnames_nuevos = diferencia.jobnames(malla_work.jobnames(), malla_live.jobnames(), diff_record)
        if malla_work.name != malla_live.name:
            raise Exception(f"No se pueden analizar mallas distintas: {Carpetas.WORK_FOLDERNAME}[{malla_work.name}] != {Carpetas.LIVE_FOLDERNAME}[{malla_live.name}]")

    for work_job in malla_work.jobs():
        try:
            validaciones.jobname(work_job, malla_work, control_record)
            validaciones.application(work_job, malla_work, control_record)
            validaciones.subapp(work_job, malla_work, control_record)
            validaciones.atributos(work_job, malla_work, control_record)
            validaciones.variables(work_job, malla_work, control_record)
            validaciones.marcas_in(work_job, malla_work, control_record)
            validaciones.marcas_out(work_job, malla_work, control_record)
            validaciones.acciones(work_job, malla_work, control_record)
            validaciones.tipo(work_job, malla_work, control_record)
            validaciones.recursos_cuantitativos(work_job, malla_work, control_record)
        except Exception as control_error:
            msg = f"Ocurrió un error inesperado al realizar controles sobre el job [{work_job.name}] contactar a Tongas"
            raise Exception(msg) from control_error

        # Si no hay malla de live para comparar, continuamos
        if not comparar_con_live:
            continue

        # Ya hechos los controles, vemos las diferencias
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

    # La validación de cadenas es un control a nivel malla, no es puntual con los jobs, lo podemos dejar acá
    try:
        validaciones.cadenas_malla(malla_work, control_record)
    except Exception as error_cadenas:
        msg = f"Ocurrió un error inesperado al analizar las cadenas de la malla, dónde está tu Dios ahora?"
        raise Exception(msg) from error_cadenas

    informacion_extra_recorders = {
        'jobnames_nuevos': jobnames_nuevos if comparar_con_live else [],
        'jobnames_modificados': [key for key in diff_record.info.keys() if key not in ('INICIAL', 'GENERAL') and key not in jobnames_nuevos] if comparar_con_live else [],
        'jobnames_ruta_critica': [job.name for job in malla_work.jobs() if job.es_ruta_critica()]
    }

    sec, millisec = divmod((time.perf_counter() - crono_start), 1000)

    control_record.add_inicial(f"Fecha de generación [{datetime.datetime.now()}]")
    control_record.add_inicial(f"Malla analizada [{malla_work.name}]")
    control_record.add_inicial(f"UUAA: {malla_work.uuaa}")
    control_record.add_inicial(f"Periodicidad: {malla_work.periodicidad}")
    control_record.add_inicial(f"Cantidad jobs {malla_work.filename[malla_work.filename.index(os.sep) + 1:]}: {len(malla_work.jobs())}")
    control_record.add_inicial(f"Tiempo empleado: {sec}s:{round(millisec, 3)}ms")
    control_record.add_inicial('-' * 70)
    control_record.write_log(f'CONTROLES_{malla_work.name}.log', informacion_extra_recorders)

    if comparar_con_live:
        diff_record.add_inicial(f"Fecha de generación [{datetime.datetime.now()}]")
        diff_record.add_inicial(f"Malla analizada [{malla_work.name}]")
        diff_record.add_inicial(f"UUAA: {malla_work.uuaa}")
        diff_record.add_inicial(f"Periodicidad: {malla_work.periodicidad}")
        diff_record.add_inicial(f"Cantidad jobs {malla_work.filename[malla_work.filename.index(os.sep) + 1:]}: {len(malla_work.jobs())}")
        diff_record.add_inicial(f"Cantidad jobs {malla_live.filename[malla_live.filename.index(os.sep) + 1:]}: {len(malla_live.jobs())}")
        diff_record.add_inicial(f"Tiempo empleado: {sec}s:{round(millisec, 3)}ms")
        diff_record.add_inicial('-' * 70)
        diff_record.write_log(f'DIFERENCIAS_{malla_work.name}.log', informacion_extra_recorders)

        modificados_rc = set(informacion_extra_recorders['jobnames_modificados']).intersection(set(informacion_extra_recorders['jobnames_ruta_critica']))
        if modificados_rc:
            print(f"WARNING: SE MODIFICARON JOBS DE RUTA CRÍTICA: {modificados_rc}, CORROBORARLO CON EL EQUIPO")

    print("Análisis finalizado, revise los archivos .log")
