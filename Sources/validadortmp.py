"""
Realiza validaciones sobre una malla temporal
"""

from __future__ import annotations

import datetime
import re

from pathlib import Path

from controlm import ControlmFolder


class Control:
    @staticmethod
    def parametros_correctos(malla_tmp: ControlmFolder, recorder: RecorderTmp):

        if malla_tmp.order_method != 'PRUEBAS':
            recorder.add_general(f"El 'ORDER METHOD' de la malla no es el correcto. Esperado [PRUEBAS], obtenido [{malla_tmp.order_method}]")

        if malla_tmp.datacenter != 'CTM_CTRLMCCR':
            recorder.add_general(f"El servidor no es el correcto. Valor esperado [CTM_CTRLMCCR], obtenido [{malla_tmp.datacenter}]")

    @staticmethod
    def marcas_out(malla_tmp: ControlmFolder, job_tmp: ControlmJob, recorder: RecorderTmp):

        d = Utils.encontrar_duplicados(job_tmp.get_acciones_marcas())
        if d:recorder.add_listado(job_tmp.name, f"Existen marcas OUT duplicadas", d)

        for marca in job_tmp.marcasout:

            # Si es una marca mal formada, continuar
            if marca.destino is None or marca.origen is None:
                recorder.add_item(job_tmp.name, f"La marca OUT [{str(marca)}] está mal formada")
                continue

            if marca.signo == '-':

                # El job de destino tiene que sel el propio que estamos eliminando
                if marca.destino != job_tmp.name:
                    recorder.add_item(job_tmp.name, f"El job de DESTINO [{marca.destino}] de la marca OUT [{str(marca)}] debería ser [{job_tmp.name}] ya que ELIMINA marca")

                # El job de origen tiene que existir en la malla
                if marca.origen not in malla_tmp.jobnames():
                    recorder.add_item(job_tmp.name, f"El job de ORIGEN [{marca.origen}] de la marca OUT [{str(marca)}] no se encuentra en la malla")

            elif marca.signo == '+':
                # El job de origen tiene que ser el que agregue marca a otro job
                if marca.origen != job_tmp.name:
                    recorder.add_item(job_tmp.name, f"El job de ORIGEN [{marca.origen}] de la marca OUT [{str(marca)}] debería ser [{job_tmp.name}] ya que AGREGA marca")

                # El job de destino tiene que existir en la malla
                if marca.destino not in malla_tmp.jobnames():
                    recorder.add_item(job_tmp.name, f"El job de DESTINO [{marca.destino}] de la marca OUT [{str(marca)}] no se encuentra en la malla")

            # De cada marca, analizamos si los jobs de partida o destino no corren peligro de ser marcas a jobs productivos
            info_marca_out_origen = Utils.obtener_info_jobname(marca.origen)
            info_marca_out_destino = Utils.obtener_info_jobname(marca.destino)

            if info_marca_out_origen is not None and info_marca_out_origen['periodicidad'] != '9':
                recorder.add_item(job_tmp.name,
                                  f"Para la marca in [{marca.name}], el job de ORIGEN [{marca.origen}] no tiene dígito de periodicidad de una temporal[9], corre peligro de ser una marca productiva")

            if info_marca_out_destino is not None and info_marca_out_destino['periodicidad'] != '9':
                recorder.add_item(job_tmp.name,
                                  f"Para la marca in [{marca.name}], el job de DESTINO [{marca.destino}] no tiene dígito de periodicidad de una temporal[9], corre peligro de ser una marca productiva")

        # Toda marcain debe eliminarse
        for marca_in in job_tmp.marcasin:
            se_elimina = False

            for marca_out in job_tmp.marcasout:
                if marca_out.origen == marca_in.origen and marca_out.destino == marca_in.destino and marca_out.signo == '-':
                    se_elimina = True

            if not se_elimina:
                recorder.add_item(job_tmp.name, f"La marca IN {marca_in.name} no se elimina")

    @staticmethod
    def jobname(malla_tmp: ControlmFolder, job_tmp: ControlmJob, recorder: RecorderTmp):

        info = Utils.obtener_info_jobname(job_tmp.name)

        if info is None:
            recorder.add_item(job_tmp.name, f"No se puede obtener información a partir del jobname, no cumple con el estándar")
            return

        if info['periodicidad'] != '9':
            recorder.add_item(job_tmp.name, f"El dígito de periodicidad no corresponde con uno de una malla temporal. Digito esperado [9], obtenido [{info['periodicidad']}]")

        if info['uuaa'] != malla_tmp.uuaa:
            recorder.add_item(job_tmp.name, f"No coincide la uuaa del jobname [{info['uuaa']}] con la uuaa de la malla [{malla_tmp.uuaa}]")

        if info['pais'] != 'A':
            recorder.add_item(job_tmp.name, f"El carácter de país dene ser de Argentina [A], obtenido [{info['pais']}]")

    @staticmethod
    def scheduling(malla_tmp: ControlmFolder, job_tmp: ControlmJob, recorder: RecorderTmp):

        if job_tmp.atributos['MAXWAIT'] != '0':
            recorder.add_item(job_tmp.name, f"El job al ser temporal debe tener su keepactive en 0, obtenido [{job_tmp.atributos['MAXWAIT']}]")

        if job_tmp.atributos.get('DAYSCAL') is None:
            pass  # FIXME: implementar

    @staticmethod
    def atributos(malla_tmp: ControlmFolder, job_tmp: ControlmJob, recorder: RecorderTmp):

        if job_tmp.subapp != 'DATIO-AR-P':
            recorder.add_item(job_tmp.name, f"La SUB APPLICATION del job no es la correcta para temporales. Valor esperado [DATIO-AR-P], obtenido [{job_tmp.subapp}]")

        if job_tmp.atributos['DESCRIPTION'].strip() == '':
            recorder.add_item(job_tmp.name, f"La descripción no puede estar vacía")

        info_app = re.search(REGEX_APPLICATION, job_tmp.app)
        if info_app is None:
            recorder.add_item(job_tmp.name, f"La APPLICATION [{job_tmp.app}] no cumple con el estandar")
        else:
            if info_app['uuaa'] != malla_tmp.uuaa:
                recorder.add_item(job_tmp.name, f"No coincide la uua de la APPLICATION [{info_app['uuaa']}], con la de la malla [{malla_tmp.uuaa}]")

            if info_app['pais'] != 'AR':
                recorder.add_item(job_tmp.name, f"El pais de la APPLICATION deberia ser [AR], valor obtenido [{info_app['pais']}]")

            if info_app['app'] != 'DATIO':
                recorder.add_item(job_tmp.name, f"La APPLICATION no tiene DATIO en su nombre [{job_tmp.app}]")

        if job_tmp.atributos['MULTY_AGENT'] == 'Y':
            recorder.add_item(job_tmp.name, f"La opción de MULTY AGENT está tildada, si se da order el job se subirá al activo varias veces")

    @staticmethod
    def recursos_cuantitativos(malla: ControlmFolder, job: ControlmJob, cr: RecorderTmp):

        generico_encontrado = False
        tmp_encontrado = False
        for recurso in job.recursos_cuantitativos:
            if recurso.name == 'ARD':
                generico_encontrado = True
            if recurso.name == 'ARD-TMP':
                tmp_encontrado = True
            if recurso.name != 'ARD-TMP' and recurso.name != 'ARD':
                cr.add_item(job.name, f"Se encontró un recurso cuantitativo no permitido en malla temporales [{recurso.name}]")


        if not generico_encontrado:
            cr.add_item(job.name, f"No se encuentra el recurso cuantitativo por defecto ARD")

        if not tmp_encontrado:
            cr.add_item(job.name, f"No se encuentra el recurso cuantitativo ARD-TMP")


if __name__ == '__main__':

    p = Path('./')
    files = [f for f in p.iterdir() if f.name.endswith('.xml')]

    rec = RecorderTmp()
    for file in files:
        print(f"Validando {file.name}")
        mallatmp = ControlmFolder(xml_filename=file.name)

        # Controles generales, aquellos que se hacen a nivel malla
        Control.jobnames_duplicados(mallatmp, rec)
        Control.parametros_correctos(mallatmp, rec)

        # Controles particulares, aquellos que se hacen a nivel job
        for jobtmp in mallatmp.jobs:
            Control.marcas_in(mallatmp, jobtmp, rec)
            Control.marcas_out(mallatmp, jobtmp, rec)
            Control.variables(mallatmp, jobtmp, rec)
            Control.jobname(mallatmp, jobtmp, rec)
            Control.scheduling(mallatmp, jobtmp, rec)
            Control.atributos(mallatmp, jobtmp, rec)
            Control.recursos_cuantitativos(mallatmp, jobtmp, rec)

        rec.add_inicial(f"Fecha de generación [{datetime.datetime.now()}]")
        rec.add_inicial(f"Malla analizada [{mallatmp.name}]")
        rec.add_inicial(f"UUAA: {mallatmp.uuaa}")
        rec.add_inicial(f"Cantidad jobs: {len(mallatmp.jobs)}")

        rec.write_log(f"VALIDACION_{mallatmp.name}.log")

