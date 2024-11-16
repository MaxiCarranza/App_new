"""
Modulo de controles/validaciones (funciones... R E G L A S D E N E G O C I O) a realizar. Existen dos tipos:
    - Puntual: Sobre el job de control m (ej: Que el jobname comience con la letra 'A')
    - General: En toda la malla (ej: Que no haya jobnames duplicados)
    - Global: A nivel contenedor, es decir, controles que se deben realizar teniendo en cuenta datos de varias mallas a
        la vez (Ej: Que una marca que agrega un job sea eliminada por otro)

Aquellas que se deben realizar sobre una malla temporal, se prefijarán con "temp_" TODO: Hay una mejor forma ?
"""

import csv
import re
import src.controlm.utils as utils
import src.controlm.constantes as constantes

from difflib import SequenceMatcher
from src.controlm.structures import (
    ControlmJob,
    ControlmAction,
    ControlmMarcaOut,
    ControlmDigrafo,
    ControlmContainer,
    ControlmFolder
)
from src.controlm.record import ControlRecorder, RecorderTmp
from src.controlm.constantes import Regex


def jobname(job: ControlmJob, malla: ControlmFolder, cr: ControlRecorder):
    """
    Realiza controles puntuales sobre el jobname

    :param job: El job de control M cuyo jobname se va a analizar
    :param malla: La malla que contiene al job
    :param cr: Recorder encargado de logear los controles fallidos
    """

    if not job.jobname_valido():
        cr.add_item(job.name, f"El jobname {job.name} no cumple con el estandar. Corregir este error antes de pasar a producción.")
        return
    else:
        info_jobname = job.get_info_jobname()

    if info_jobname['uuaa'] != malla.uuaa:
        cr.add_item(job.name, f"No coincide la uuaa del jobname [{info_jobname['uuaa']}] con la de la malla [{malla.uuaa}]")

    if info_jobname['entorno'] != 'P':
        cr.add_item(job.name, f"El jobname no está ambientado a producción. Valor esperado [P], obtenido [{info_jobname['entorno']}]")

    if info_jobname['periodicidad'] == 9:
        cr.add_item(job.name, f"El jobname tiene periodicidad de una malla temporal [9].")

    if info_jobname['pais'] != 'A':
        cr.add_item(job.name, f"El país de jobname no es ARGENTINA. Valor obtenido [{info_jobname['pais']}], valor esperado [A]")

    if constantes.MAPEO_PERJOBNAME_PERMALLA[info_jobname['periodicidad']] != malla.periodicidad:
        cr.add_item(job.name, f"No coincide la periodicidad del job[{info_jobname['periodicidad']}({constantes.MAPEO_PERJOBNAME_PERMALLA[info_jobname['periodicidad']]})], con la de la malla a la que pertenece[{malla.periodicidad}]")


def application(job: ControlmJob, malla: ControlmFolder, cr: ControlRecorder):
    """
    Realiza controles puntuales sobre la application

    :param job: El job de control M a analizar
    :param malla: La malla que contiene al job
    :param cr: Recorder encargado de logear los controles fallidos
    """

    info_app = job.get_info_application()

    if info_app is None:
        cr.add_item(job.name, f"La application [{job.app}] no es la correcta. Corregir este conflicto antes de pasar a producción.")
        return

    if info_app['uuaa'] != malla.uuaa:
        cr.add_item(job.name, f"No coincide la uuaa de la application [{info_app['uuaa']}] con la de la malla [{malla.uuaa}]")

    if info_app['pais'] != 'AR':
        cr.add_item(job.name, f"Para la application [{job.app}], el pais [{info_app['pais']}] debería ser [AR]")


def subapp(job: ControlmJob, malla: ControlmFolder, cr: ControlRecorder):
    """
    Realiza controles puntuales sobre la subapplication

    :param job: El job de control M a analizar
    :param malla: La malla que contiene al job
    :param cr: Recorder encargado de logear los controles fallidos
    """

    if not job.subapp.startswith('DATIO-AR-'):
        cr.add_item(job.name, f"La subapplication no comienza con DATIO-AR, valor obtenido [{job.subapp}]")

    if 'CCR' not in job.subapp:
        cr.add_item(job.name, f"La subapplication no contiene la palabra clave [CCR], valor obtenido [{job.subapp}]")


def atributos(job: ControlmJob, malla: ControlmFolder, cr: ControlRecorder):
    """
    Realiza controles puntuales sobre los atributos del job. Los atributos incluyen muchas cosas, entre ellas la
    app, subapp, scheduling, nombre malla, commando, etc.

    :param job: El job de control M a analizar
    :param malla: La malla que contiene al job
    :param cr: Recorder encargado de logear los controles fallidos
    """

    if not job.jobname_valido():
        cr.add_item(job.name, f"No se puede analizar sus atributos debido a que el jobname {job.name} no cumple con el estandar. Corregir este error antes de pasar a producción.")
        return
    else:
        info_jobname = job.get_info_jobname()

    for key_atributo, val_atritubo in job.atributos.items():

        if key_atributo == 'DESCRIPTION' and val_atritubo.strip() == '':
            cr.add_item(job.name, f"La descripción no puede estar vacía")

        if key_atributo == 'MAXWAIT':
            # Mensuales tienen que tener keepActive en 7
            if info_jobname['periodicidad'] == '4' and info_jobname['tipo'] != 'W' and val_atritubo != '7':
                cr.add_item(job.name, f"Al ser mensual debe tener su Keep Active en 7, valor obtenido: [{val_atritubo}]")

            # Diarias keepActive en 3
            if info_jobname['periodicidad'] == '0' and info_jobname['tipo'] != 'W' and val_atritubo != '3':
                cr.add_item(job.name, f"Los jobs diarios deben tener su Keep Active en 3, valor obtenido: [{val_atritubo}]")

        if key_atributo == 'PARENT_FOLDER' and val_atritubo != malla.name:
            cr.add_item(job.name, f"No coincide la malla 'padre' del job {val_atritubo} con la malla que se encuentra en el xml {malla.name}. Indagar al desarrollador sobre esto debido a que implica una manipulación manual del xml exportado")


def variables(job: ControlmJob, malla: ControlmFolder, cr: ControlRecorder):
    """
    Realiza controles puntuales sobre las variables del job

    :param job: El job de control M a analizar
    :param malla: La malla que contiene al job
    :param cr: Recorder encargado de logear los controles fallidos
    """

    # TODO: Estas son variables, que algunos jobs las dejan vacías. No es un error y no tengo idea del proceso
    #   que ejecutan, pero las voy a hardcodear hasta que se comprenda bien por qué pueden ir vacías.
    variables_vacias_validas = [
        'FORMATO_UNO',
        'FORMATO_DOS',
        'CARPETA_SIN_FECHA',
        'PRIMERA_PARTE_CARPETA_SIN_FECHA',
        'SEGUNDA_PARTE_CARPETA_SIN_FECHA'
    ]

    # Nombres reservados no permitidos por el estandar, ver https://ctm.bancolombia.com/help/CTMHelp/en-US/Documentation/Variables.htm
    variables_no_permitidas = [
        # Generales del sistema
        'APPLIC',
        'APPLGROUP',
        'CYCLIC',
        '$FOLDER_ID',
        'GROUP_ORDID',
        '$GROUP_ORDID',
        'JOBNAME',
        'MEMLIB',
        'ORDERID',
        'OWNER',
        'RUNCOUNT',
        'SCHEDTAB',
        'SMART_ORDERID',
        '$SMART_ORDERID',
        '$TABLE_ID',

        # Las resueltas en tiempo de ejecucion
        '$DATE',
        '$YEAR',
        'MONTH',
        'OWDAY',
        'RMONTH',
        'YEAR',
        '$ODATE',
        'CENT',
        'ODATE',
        'OYEAR',
        'RWDAY',
        'OMONNAM',
        '$OYEAR',
        'DATE',
        'ODAY',
        'RDATE',
        'RYEAR',
        'RMONNAM',
        '$RDATE',
        'DAY',
        'OJULDAY',
        'RDAY',
        'TIME',
        'MONNAM',
        '$RYEAR',
        'JULDAY',
        'OMONTH',
        'RJULDAY',
        'WDAY'
    ]

    existe_tabla = False
    tabla_keys_posibles = ['TABLENAME', 'TABLE_NAME', 'TABLE', 'TABLA']

    # realizamos controles puntuales sobre las variables
    for var_key, var_value in job.variables.items():
        var_key = var_key.replace('%%', '')

        if (var_key in tabla_keys_posibles and var_value.startswith(f't_')) or 't_' in job.atributos['DESCRIPTION']:
            existe_tabla = True

        match_dataproc_namespace = re.search(Regex.DATAPROC_NAMESPACE, utils.oofstr(var_value))
        if match_dataproc_namespace is not None and match_dataproc_namespace.group('ambiente') == 'dev':
            cr.add_item(job.name, f"Existe un namespace de DESARROLLO [{var_value}] en la variable [{var_key}]")

        if var_key in variables_no_permitidas:
            cr.add_item(job.name, f"La variable [{var_key}] valor [{var_value}] reemplaza la variable %%{variables_no_permitidas[variables_no_permitidas.index(var_key)]} definida y reservada por el sistema, esto no es permitido por el estandar")

        if utils.oofstr(var_value).strip() == '' and var_key not in variables_vacias_validas:
            cr.add_item(job.name, f"La variable [{var_key}] está vacía")

        # TODO: Comento porque da muchos falsos positivos, revisar si vale la pena realmente verificar esto
        # if not var_key.isupper():
        #     cr.add_item(job.name, f"La variable [{var_key}] tiene minusculas, no está permitido por el estandar")

    if not existe_tabla:
        cr.add_item_listado_general('tabla_identificadora', job.name)

    datapros_encontrados = []  # Un job no puede tener dos datapros
    for var_key, var_value in job.variables.items():
        match_dataproc = re.search(Regex.DATAPROC_JOB_ID, utils.oofstr(var_value))
        if match_dataproc is not None:
            datapros_encontrados.append(match_dataproc)

    if len(datapros_encontrados) > 1:
        cr.add_listado(job.name, f"Se encontraron [{len(datapros_encontrados)}] dataprocs para un mismo job, revisar si esto es correcto ya que debería estar definido una sola vez", [m.group(0) for m in datapros_encontrados])

    # Validamos que todas las variables declaradas estén en uso. Una variable se puede usar en el asunto de un
    # mail, en el command o en otras variables. Las volvermos a recorrer
    for var_key in job.variables.keys():

        variable_usada = False

        # buscamos el uso en otras variables
        for var_value in job.variables.values():
            if (var_value is not None and var_key in var_value) or not utils.oofstr(var_value).startswith('t_'):  # Las variables de table no se usan
                variable_usada = True

        # En el command
        try:
            if var_key in job.atributos['CMDLINE']:
                variable_usada = True
        except KeyError:
            pass  # Si no tiene command, no pasa nada

        # En la descripcion, aunque no se resuelven en tiempo de ejecucion, les damos un changüí
        if var_key in job.atributos['DESCRIPTION']:
            variable_usada = True

        # En los mails que se envían
        for oncondition in job.onconditions:
            for action in job.onconditions[oncondition]:
                if action.id == 'DOMAIL' and any([var_key in atr for atr in action.attrs.values()]):
                    variable_usada = True

        if not variable_usada:
            cr.add_item(job.name, f"La variable [{var_key}] valor [{job.variables[var_key]}] está declarada pero no está siendo usada")


def marcas_in(job: ControlmJob, malla: ControlmFolder, cr: ControlRecorder):
    """
    Realiza controles puntuales sobre los prerequisitos, el metodo se llama marcas_in mas que nada porque así se
    llama el tag en el xml y bueno.

    :param job: El job de control M a analizar
    :param malla: La malla que contiene al job
    :param cr: Recorder encargado de logear los controles fallidos
    """

    if not job.jobname_valido():
        cr.add_item(job.name, f"No se puede controlar los prerequisitos debido a que el jobname {job.name} no cumple con el estandar. Corregir este error antes de pasar a producción.")
        return
    else:
        info_jobname = job.get_info_jobname()

    duplis = utils.encontrar_duplicados(job.get_prerequisitos())
    if duplis:
        cr.add_item(job.name, f"Existen prerequisitos duplicados: {duplis}")

    for marca in job.marcasin:

        if not marca.es_valida():
            cr.add_item(job.name, f"El prerequisito [{str(marca)}] está mal formado")
            continue

        if marca.destino != job.name:
            cr.add_item(job.name, f"Para El prerequisito [{str(marca)}] no coincide el job de DESTINO [{marca.destino}] con el que pertenece [{job.name}]")

        info_jobname_origen = marca.get_info_origen()
        if (
                marca.origen not in malla.jobnames() and
                info_jobname_origen['uuaa'] == malla.uuaa and
                info_jobname_origen['periodicidad'] != info_jobname['periodicidad']
        ):
            cr.add_item(job.name, f"El job de ORIGEN [{marca.origen}] de el prerequisito [{marca.name}] no se encuentra en la malla y no pertenece a otra malla")


def marcas_out(job: ControlmJob, malla: ControlmFolder, cr: ControlRecorder):
    """
    Realiza controles puntuales sobre las acciones de un job sobre marcas, el metodo se llama marcas_out mas que
    nada porque así se llama el tag en el xml.

    :param job: El job de control M a analizar
    :param malla: La malla que contiene al job
    :param cr: Recorder encargado de logear los controles fallidos
    """

    if not job.jobname_valido():
        cr.add_item(job.name, f"No se puede controlar las marcas out debido a que el jobname {job.name} no cumple con el estandar. Corregir este error antes de pasar a producción.")
        return
    else:
        info_jobname = job.get_info_jobname()

    duplis = utils.encontrar_duplicados(job.get_prerequisitos())
    if duplis:
        cr.add_item(job.name, f"Existen marcas OUT duplicadas: {duplis}")

    for marca in job.marcasout:

        if not marca.es_valida():
            cr.add_item(job.name, f"La marca OUT [{str(marca)}] está mal formada")
            continue

        info_jobname_origen = marca.get_info_origen()
        info_jobname_destino = marca.get_info_destino()

        if info_jobname_origen is None or info_jobname_destino is None:
            cr.add_item(job.name, f"La marca OUT [{str(marca)}], tiene jobnames que no cumplen con el estandar. RESOLVER EL CONFLICTO Y NO DEJAR PASAR ESTO")
            continue

        if marca.signo == '-':

            if marca.destino != job.name:
                cr.add_item(job.name, f"El job de DESTINO [{marca.destino}] de la marca OUT [{str(marca)}] debería ser [{job.name}] ya que ELIMINA marca")

            # El job de origen tiene que existir en la malla si pertenece a la misma uuaa
            if (marca.origen not in malla.jobnames()
                    and info_jobname_origen['uuaa'] == malla.uuaa
                    and info_jobname_origen['periodicidad'] != info_jobname['periodicidad']):
                cr.add_item(job.name, f"El job de ORIGEN [{marca.origen}] de la marca OUT [{str(marca)}] no se encuentra en la malla y no pertenece a otra malla")

        elif marca.signo == '+':

            if marca.origen != job.name:
                cr.add_item(job.name, f"El job de ORIGEN [{marca.origen}] de la marca OUT [{str(marca)}] debería ser [{job.name}] ya que AGREGA marca")

            if (marca.destino not in malla.jobnames()
                    and info_jobname_destino['uuaa'] == malla.uuaa
                    and info_jobname_destino['periodicidad'] != info_jobname['periodicidad']):
                cr.add_item(job.name, f"El job de DESTINO [{marca.destino}] de la marca OUT [{str(marca)}] no se encuentra en la malla y no pertenece a otra malla")

    for marca_in in job.marcasin:
        se_elimina = False

        for marca_out in job.marcasout:
            if marca_out.signo == '-' and marca_out.name == marca_in.name:
                se_elimina = True

        if not se_elimina:
            cr.add_item(job.name, f"El prerequisito [{str(marca_in)}] no se elimina")


def _subcontrol_mail(job: ControlmJob, action: ControlmAction, code: str, malla: ControlmFolder, reglas: dict, cr: ControlRecorder):
    """
    Sub control para cuando llega una accion DOMAIL. es OBLIGATORIO cuando termina OK y cuando termina NOTOK. Esta
    accion se refiere al envío de mail desde control m.

    :param job: El jobname que contiene la accion
    :param action: La accion a controlar
    :param code: El código que representa la condicion bajo la cual se va a realizar la accion
    :param malla: La malla que contiene el job
    :param reglas: Diccionario que realiza el seguimiento del cumplimiento de las reglas
    :param cr: Recorder que guardará los controles fallidos
    """

    dest: str = action.attrs['DEST']
    if '%%' in dest:
        dest = job.expandir_string(dest)

    # Es probable que nos llegue una lista, no muchos lo implementan pero ya vi unos jobs de dudosa procedencia que lo hacen
    if ';' in dest:
        lista_mails = [m.strip() for m in dest.split(';')]
    else:
        lista_mails = [dest]

    for destinatario in lista_mails:

        if destinatario != 'datio-procesos-live.group@bbva.com':
            cr.add_item(job.name, f"El mail cuando termina [{code}] es [{destinatario}], debería enviarse a [datio-procesos-live.group@bbva.com]")

        if re.search(Regex.MAILS, destinatario) is None:
            cr.add_item(job.name, f"El mail del receptor cuando termina [{code}] es [{destinatario}], no parece ser un mail válido")

    try:
        destinatario_cc = action.attrs['CC_DEST']
    except KeyError:
        # Realmente no tenemos que hacer nada si el mail viene sin CC, ya que no es un requisito obligatorio
        pass
    else:
        if '%%' in destinatario_cc:
            destinatario_cc = job.expandir_string(destinatario_cc)

        if destinatario_cc is None or re.search(Regex.MAILS, destinatario_cc) is None:
            cr.add_item(job.name, f"El mail de CC cuando termina [{code}] es [{destinatario_cc}], no parece ser un mail válido")

    if action.attrs['ATTACH_SYSOUT'] != 'Y' and action.attrs['ATTACH_SYSOUT'] != 'D':
        cr.add_item(job.name, f"El mail de CC cuando termina [{code}] no adjunta su SYSOUT (output)")

    try:
        asunto = action.attrs['SUBJECT']
    except KeyError:
        cr.add_item(job.name, f"El mail cuando termina [{code}] no tiene asunto")
    else:
        if '%%' in asunto:
            asunto = job.expandir_string(asunto)

            if len(asunto) > 99:
                cr.add_item(job.name, f"El mail cuando termina [{code}] no se enviará debido a que su asunto tiene [{len(asunto)}] caracteres, supera los 99 caracteres. Valor obtenido: [{asunto}]")

        if job.name not in asunto:
            cr.add_item(job.name, f"El mail cuando termina [{code}] no informa el JOBNAME en el asunto, que es [{asunto}]")

            cuerpo = action.attrs.get('MESSAGE')
            if '%%' in cuerpo:
                cuerpo = job.expandir_string(cuerpo)
            if cuerpo is None:
                cr.add_item(job.name, f"El mail cuando termina [{code}] no tiene un mensaje en su cuerpo.")
            elif job.name not in cuerpo:
                cr.add_item(job.name, f"El mail cuando termina [{code}] TAMPOCO informa el JOBNAME en el cuerpo, que es [{cuerpo}]... media pila loco >:(")

    # OK y retorno 0 es lo mismo, el job ejecutó exitosamente sin error
    if code == 'OK' or 'COMPSTAT EQ 0':
        reglas['mail_ok'][0] = True

    # Lo mismo para retorno 1
    if code == 'NOTOK' or 'COMPSTAT EQ 1':
        reglas['mail_notok'][0] = True

    # Si el job es FW, tenemos que anotar si manda mail bajo sus respectivos códigos de retorno
    if job.es_filewatcher():
        if code == 'COMPSTAT EQ 0':
            reglas['fw_mail_code0'][0] = True
        elif code == 'COMPSTAT EQ 7':
            reglas['fw_mail_code7'][0] = True


def _subcontrol_cond(job: ControlmJob, action: ControlmAction, code: str, malla: ControlmFolder, reglas: dict, cr: ControlRecorder):
    """
    Sub control para cuando llega una accion COND. COND se refiere al agregado de una marca al servidor como si
    fuese mediante accion pero esta es mas particular, pues no es cuando el job finaliza ok si no que va a estar
    definido por code, o código mediante el cual se agrupa la accion

    :param job: El jobname que contiene la accion
    :param action: La accion a controlar
    :param code: El código que representa la condicion bajo la cual se va a realizar la accion
    :param malla: La malla que contiene el job
    :param reglas: Diccionario que realiza el seguimiento del cumplimiento de las reglas
    :param cr: Recorder que guardará los controles fallidos
    """

    marca = ControlmMarcaOut(marca_nombre=action.attrs['NAME'], odate_esperado=action.attrs['ODATE'], signo=action.attrs['SIGN'])
    intro = f"La marca [{str(marca)}] mediante accion [{action.id}] con código [{code}]"

    # Acá va a haber codigo repetido de las marcas out, así son las cosas che
    if not marca.es_valida():
        cr.add_item(job.name, f"{intro}, no es una marca válida")

    if marca.signo == '+':
        if marca.destino not in malla.jobnames():
            cr.add_item(job.name, f"{intro}, el jobname de DESTINO [{marca.destino}] no existe en la malla")

        if marca.origen != job.name:
            cr.add_item(job.name, f"{intro}, el jobname de PARTIDA [{marca.origen}] debería ser [{job.name}] ya que AGREGA marca")

    if marca.signo == '-':
        if marca.origen not in malla.jobnames():
            cr.add_item(job.name, f"{intro}, el jobname de PARTIDA [{marca.origen}] no existe en la malla")

        if marca.destino != job.name:
            cr.add_item(job.name, f"{intro}, el jobname de DESTINO [{marca.destino}] debería ser [{job.name}] ya que QUITA marca")

    # Si un FW retorna 0, quiere decir que encontró archivo, ver si el job al que le deja marca está ok
    if code == 'COMPSTAT EQ 0' and job.es_filewatcher():
        reglas['fw_deja_marca_ok'][0] = True


def _subcontrol_doaction(job: ControlmJob, action: ControlmAction, code: str, malla: ControlmFolder, reglas: dict, cr: ControlRecorder):
    """
    Sub control para cuando llega una accion DOACTION. DOACTION se refiere a una accion a tomar sobre el job que
    implica modificar su estado. Por ej: Si un job finaliza con retorno 7, una acción sobre el mismo
    puede ser que se setee ok (SET OK) o not ok (NOTOK)

    :param job: El jobname que contiene la accion
    :param action: La accion a controlar
    :param code: El código que representa la condicion bajo la cual se va a realizar la accion
    :param malla: La malla que contiene el job
    :param reglas: Diccionario que realiza el seguimiento del cumplimiento de las reglas
    :param cr: Recorder que guardará los controles fallidos
    """

    if code == '*{"id":"SUCCESS","name":"SUCCESS"}*' and action.attrs['ACTION'] != 'OK':
        cr.add_item(job.name, f"El job no se setea OK cuando termina con código [{code}]")

    if job.es_filewatcher():

        if code == 'COMPSTAT EQ 0' and action.attrs['ACTION'] == 'SPCYC':
            reglas['fw_stop_cyclic_code0'][0] = True

        if code == 'NOTOK' and action.attrs['ACTION'] == 'SPCYC':
            reglas['fw_stop_cyclic_notok'][0] = True


def _subcontrol_forcejob(job: ControlmJob, action: ControlmAction, code: str, malla: ControlmFolder, reglas: dict, cr: ControlRecorder):
    """
    Sub control para cuando llega una accion DOFORCE. DOFORCE se refiere a subir al activo a otro job ignorando su
    scheduling. Esto se utiliza para las clásicas cadenas que "se levantan con force". esta acción es generalmente
    realizada por un filewatcher que planifica todos los días y levanta la cadena predecesora cuando encuentra
    archivo. Esto aplica generalmente para las cadenas mensuales, en aquellas que no saben con exactitud cuándo
    van a recibir archivo a lo largo del mes.

    :param job: El jobname que contiene la accion
    :param action: La accion a controlar
    :param code: El código que representa la condicion bajo la cual se va a realizar la accion
    :param malla: La malla que contiene el job
    :param reglas: Diccionario que realiza el seguimiento del cumplimiento de las reglas
    :param cr: Recorder que guardará los controles fallidos
    """

    intro = f"Bajo la condicion [{code}]"

    if action.attrs['TABLE_NAME'] != malla.name:
        cr.add_item(job.name, f"{intro}, el job ordena con force a otro job de otra malla [{action.attrs['TABLE_NAME']}]")

    if action.attrs['NAME'] not in malla.jobnames():
        cr.add_item(job.name, f"{intro}, el job ordena con force a otro job [{action.attrs['NAME']}] que no existe en la malla [{malla.name}]")

    if action.attrs['ODATE'] != 'ODAT':
        cr.add_item(job.name, f"{intro}, el job ordena con force a otro [{action.attrs['NAME']}] con un ODATE distinto al permitido por el estandar [{action.attrs['ODATE']}]")

    if action.attrs['REMOTE'] != 'N':
        cr.add_item(job.name, f"{intro}, el job ordena con force a otro [{action.attrs['NAME']}] con un REMOTE distinto al permitido por el estandar [{action.attrs['REMOTE']}] Valor esperado [N] (Esto no va a planificar los jobs con force)")

    if action.attrs.get('DATACENTER') is not None:
        cr.add_item(job.name, f"{intro}, el job ordena con force a otro [{action.attrs['NAME']}] con un DATACENTER, NO debería tenerlo (Esto no va a planificar los jobs con force)")


def _subcontrol_doshout(job: ControlmJob, action: ControlmAction, code: str, malla: ControlmFolder, reglas: dict, cr: ControlRecorder):
    """
    Sub control para cuando llega una accion DOSHOUT. DOSHOUT se refiere a un alertamiento que llega a la pestaña de
    monitorin que utiliza el GEM para derivar y priorizar las cancelaciones que son RC. Solo se verifica y es
    obligatorio si el job es de Ruta Crítica.

    :param job: El jobname que contiene la accion
    :param action: La accion a controlar
    :param code: El código que representa la condicion bajo la cual se va a realizar la accion
    :param malla: La malla que contiene el job
    :param reglas: Diccionario que realiza el seguimiento del cumplimiento de las reglas
    :param cr: Recorder que guardará los controles fallidos
    """

    if job.es_ruta_critica():

        reglas['rc_doshout'][0] = True

        if code != 'NOTOK':
            cr.add_item(job.name, f"El job es de RC y está enviando un alertamiento cuando finaliza [{code}], el alertamiento corresponde cuando termina [NOT OK]")

        if action.attrs['URGENCY'] == 'U':
            reglas['rc_doshout_urgente'][0] = True

        if action.attrs['MESSAGE'] is not None:
            mensaje_correcto = "Ruta Critica, escalar a Aplicativo"
            coeficiente_diferencia = SequenceMatcher(a=mensaje_correcto, b=action.attrs['MESSAGE']).ratio()
            if coeficiente_diferencia < 0.85:  # Falopa, lo se. Pero funciona
                cr.add_item(job.name, f"El job es de RC y el mensaje de su alertamiento no es el correcto [{action.attrs['MESSAGE']}], debería ser [{mensaje_correcto}]")


def acciones(job: ControlmJob, malla: ControlmFolder, cr: ControlRecorder):
    """
    Para controlar las acciones primero hay que ver bajo qué criterio están agrupadas. Este critero se conoce como
    código (o CODE) dentro del xml. A lo que me refiero es: Bajo el código NOTOK pueden haber varias acciones
    agrupadas, como el envío de mail o alertamiento por control m o hasta incluso dejar marca a otro job.

    Las reglas fijas son aquellas que se tienen que cumplir si o si para un job y van a estar contenidas en
    un diccionario. Se pasa por referencia en todos los sub-controles. Dicho diccionario tiene la siguiente forma

    reglas_generales = {
        'identificador': [False, "Mensaje de control fallido"]
    }

    identificador: Es simplementa una key que identifica el subcontrol
    False: Booleano que nos indica si pasó el control o no
    "Mensaje de ...": Mensaje que se logueara en el Recorder si falla (Si el booleano sigue siendo falso)

    Todos los controles que se realizan sobre acciones se llamarán subcontroles debido a que no siempre se
    ejecutan, pues si un job no envía mail no se ejecutará el subcontrol para los mails

    :param job: Job a analizar las acciones
    :param malla: Malla que contiene el job
    :param cr: Recorder que se encargará de guardar los controles fallidos
    """
    if not job.jobname_valido():
        cr.add_item(job.name, f"No se pueden analizar las acciones porque el jobname {job.name} no cumple con el estandar. Corregir este error antes de pasar a producción.")
        return

    reglas_generales = {
        'mail_ok': [False, "Cuando termina OK no envía mail"],
        'mail_notok': [False, "Cuando termina NOTOK no envía mail"],
    }

    # Agregamos controles extras si el job cumple ciertas condiciones con respecto a su tipo
    if job.es_filewatcher():
        reglas_generales['fw_mail_code0'] = [False, "El FW no envia mail cuando se encuentra el archivo(retorno 0)"]
        reglas_generales['fw_mail_code7'] = [False, "El FW no envia mail cuando no se encuentra el archivo(retorno 7)"]
        reglas_generales['fw_deja_marca_ok'] = [False, "El FW no deja marca mediante acción cuando se encuentra el archivo(retorno 0)"]
        reglas_generales['fw_stop_cyclic_notok'] = [False, "El FW no frena su cyclic run cuando finaliza NOTOK"]
        reglas_generales['fw_stop_cyclic_code0'] = [False, "El FW no frena su cyclic run cuando finaliza con retorno 0"]

    # Si es de RC, tiene que tener sus marcas BIM bien colocadas.
    if job.es_ruta_critica():
        reglas_generales['rc_doshout'] = [False, "El job es de RC y NO PROPORCIONA un alertamiento cuando finaliza [NOTOK]"]
        reglas_generales['rc_doshout_urgente'] = [False, "El job es de RC y su mensaje de alertamiento no tiene la prioridad máxima (URGENT)"]

    # En vez de hacer if's para saber qué métodos ejecutar, que se haga de forma polimórfica
    # Se ejecutará en base al id de la accion
    mapeo_acciones_subcontroles = {
        'DOMAIL': _subcontrol_mail,
        'DOCOND': _subcontrol_cond,
        'DOACTION': _subcontrol_doaction,
        'DOFORCEJOB': _subcontrol_forcejob,
        'DOSHOUT': _subcontrol_doshout
    }

    for condicion, acciones_job in job.onconditions.items():
        for accion in acciones_job:
            control = mapeo_acciones_subcontroles.get(accion.id)
            if control is not None:
                # Ejecutamos el control sobre la accion
                control(job, accion, condicion, malla, reglas_generales, cr)
            else:
                cr.add_item(job.name, f"Accion no contemplada [{accion.id}]. Contactar con Tongas para implementar.")

    # Cada regla fallida es informada
    for value in reglas_generales.values():
        if not value[0]:
            cr.add_item(job.name, value[1])


def recursos_cuantitativos(job: ControlmJob, malla: ControlmFolder, cr: ControlRecorder):
    """
    Los RRCC son identificadores que tienen un valor en el servidor que indican cuántos jobs pueden correr en
    paralelo que posean el mismo recurso. El nombre viene definido por el desarrollador, mientras que la cantidad
    viene definida por el servidor (se despliega mediante CRQ). Solamente podemos controlar el nombre.

    :param job: Job a analizar los RRCC
    :param malla: Malla que contiene el job
    :param cr: Recorder que se encargará de guardar los controles fallidos
    """

    generico_encontrado = False
    rrcc_stg_correcto = True

    if job.es_tpt() or job.es_transmisiontp() or job.es_filewatcher():
        rrcc_stg_correcto = False

    for recurso in job.recursos_cuantitativos:

        if recurso.name == 'ARD':
            generico_encontrado = True

        if (job.es_tpt() or job.es_transmisiontp() or job.es_filewatcher()) and recurso.name == 'ARD-STG':
            rrcc_stg_correcto = True

        seccion: str
        if not all([seccion.isupper() or seccion.isalnum() for seccion in recurso.seccionar()]):
            cr.add_item(job.name, f"El recurso [{recurso.name}] no parece seguir el estandar defindo (caracteres o 'forma' no permitidos)")

    if not generico_encontrado:
        cr.add_item(job.name, f"No se encuentra el recurso cuantitativo por defecto ARD")

    if not rrcc_stg_correcto:
        cr.add_item(job.name, f"El job es [{job.tipo}P] ({job.tipo_descripcion}) y no se encuentra el recurso cuantitativo ARD-STG")


def tipo(job: ControlmJob, malla: ControlmFolder, cr: ControlRecorder):
    """
    Control sobre la correspondencia del tipo de un job según su jobname y lo que realmente hace

    :param job: Job a analizar los RRCC
    :param malla: Malla que contiene el job
    :param cr: Recorder que se encargará de guardar los controles fallidos
    """
    # Controlamos correspondencia entre command y tipo de job
    tipo_verbose = f"[{job.tipo}] - {job.tipo_descripcion}"
    match job.tipo:

        case 'C' | 'V' | 'S' | 'B':
            if job.command is None or job.command == '' or not job.command.startswith('/opt/datio/sentry-ar/dataproc_sentry.py'):
                cr.add_item(job.name, f"El job es {tipo_verbose} y no ejecuta el comando de dataproc_sentry.py correspondiente. Valor obtenido [{job.command}]")
            if job.fase is None:
                cr.add_item(job.name, f"El job es {tipo_verbose}, pero esto no se ve reflejado en su dataproc id, no se pudo inferir sobre qué fase actúa [{job.dataproc_id}]")

        case 'W':
            if job.command is None or job.command == '' or not (job.command.startswith('ctmfw') or job.command.startswith('epsilon-watch')):
                cr.add_item(job.name, f"El job es {tipo_verbose} y no ejecuta el comando de correspondiente a los filewatchers (ctmfw o epsilon-watch). Valor obtenido [{job.command}]")

        case 'T':
            nombre_script = job.atributos.get('MEMNAME')
            if nombre_script is not None and not nombre_script.endswith('.sh'):
                cr.add_item(job.name, f"El job es {tipo_verbose} y no ejecuta un script sh. Valor obtenido [{job.command}]")

        case 'P':
            if job.es_spark_compactor():
                if job.command is None or job.command == '' or not job.command.startswith('/opt/datio/sentry-ar/dataproc_sentry.py'):
                    cr.add_item(job.name, f"El job es {tipo_verbose} y no ejecuta el comando de dataproc_sentry.py correspondiente. Valor obtenido [{job.command}]")

            elif not job.es_tpt():
                cr.add_item(job.name, f"El job es {tipo_verbose} y no ejecuta un script multi_tpt.sh. Valor obtenido [{job.command}]")

        case _:
            pass  # TODO: Ver los casos no contemplados

    # Controlamos correspondencia entre dataproc id y tipo de job
    if job.dataproc_id is None:
        return

    info_dataproc = job.get_info_dataproc_id()
    discrepancia_datapros = False
    match job.tipo:

        case 'C' | 'G':
            if info_dataproc['tipo'] not in ('krb', 'sbx', 'biz', 'spk', 'psp', 'dfs'):
                discrepancia_datapros = True

        case 'V':
            if info_dataproc['tipo'] == 'spk' and info_dataproc['subtipo'] != 'qlt':
                discrepancia_datapros = True
            elif info_dataproc['tipo'] != 'hmm' and info_dataproc['subtipo'] == 'trn':
                discrepancia_datapros = True

        case 'S' | 'B':
            if info_dataproc['subtipo'] != 'rmv':
                discrepancia_datapros = True

        case 'W' | 'T':
            cr.add_item(job.name, f"El job es [{tipo_verbose}] y se encontró un dataproc en el mismo [{job.dataproc_id}], no debería tenerlo por su tipo")

        case 'P':
            if not job.es_spark_compactor():
                cr.add_item(job.name, f"El job es [{tipo_verbose}] y se encontró un dataproc en el mismo [{job.dataproc_id}], no debería tenerlo por su tipo")

        case _:
            cr.add_item(job.name, f"No se pudo controlar el dataproc del Job [{job.dataproc_id}] debido a que tiene un tipo desconocido [{job.tipo}]")

    if discrepancia_datapros:
        mensaje = f"Segun su tipo [{job.tipo}], el job es [{tipo_verbose}] pero esto no se ve reflejado su dataproc job id [{job.dataproc_id}]"
        cr.add_item(job.name, mensaje)


def cadena_smart_cleaner(malla: ControlmFolder, cr: ControlRecorder):
    """
    Valida que haya tantos jobs de smart cleaner como de ingesta en una cadena, puede fallar

    :param malla: Malla que contiene el job
    :param cr: Recorder que se encargará de guardar los controles fallidos
    """

    recorder_key = "ANALISIS DE CADENAS"

    cadenas = malla.digrafo.obtener_arboles()
    for cadena in cadenas:

        contador_instancias_ingesta = {
            'staging': 0,
            'raw': 0,
            'master': 0
        }
        contador_instancias_borradosm = {
            'staging': 0,
            'raw': 0,
            'master': 0
        }

        for jobname_cadena in cadena:
            job: ControlmJob = malla.obtener_job(jobname_cadena)
            if job.es_job_de_ingesta() and job.fase is not None:
                contador_instancias_ingesta[job.fase] += 1
            if job.es_smart_cleaner() and job.fase is not None:
                contador_instancias_borradosm[job.fase] += 1

        for fase in contador_instancias_ingesta.keys():
            if contador_instancias_ingesta[fase] > contador_instancias_borradosm[fase]:
                diferencia = contador_instancias_ingesta[fase] - contador_instancias_borradosm[fase]
                mensaje = f"Para la cadena {cadena}, existen más jobs de ingesta en {fase} [{contador_instancias_ingesta[fase]}] que smart cleaners de {fase} [{contador_instancias_borradosm[fase]}]. Faltarían [{diferencia}] SP's de {fase}"
                cr.add_item(recorder_key, mensaje)


def verificar_variables_nuevas(job: ControlmJob, cr: ControlRecorder):

    """
    Verifica que, si hay jobs nuevos en la malla, estos contengan estas 6 nuevas variables: ORIGEN, TABLA_ORIGEN, TABLA, TRANSFER_ID, XCOM, FORMATEADOR. Las 3 ultimas, solo si son FW o TP.
    Solo verifica que estas variables existan, no se fija en su contenido

    :param job: Job a analizar los RRCC
    :param cr: Recorder que se encargará de guardar los controles fallidos

    """

    def validar_variables_nuevas(job_obj: ControlmJob, dict_variables: dict):
        """
        Subcontrol blablabla, TODO: Completar docstring
        """

        for var_key in job_obj.variables.keys():

            var_key = var_key.replace('%%', '')

            if var_key in dict_variables.keys():
                dict_variables[var_key] = True

        variables_no_encontradas = [variable for variable, valor in dict_variables.items() if valor is False]
        variables_encontradas = [variable for variable, valor in dict_variables.items() if valor is True]
        return variables_no_encontradas, variables_encontradas

    variables_nuevas_obligatorias = {
        'ORIGEN': False,
        'TABLA_ORIGEN': False,
        'TABLA_DATIO': False,
    }

    variables_nuevas_obligatorias_fw_tp = {
        'FORMATEADOR': False,
        'XCOM': False,
        'TRANSFER_ID': False
    }

    variables_generales_no_encontradas, _ = validar_variables_nuevas(job, variables_nuevas_obligatorias)
    variables_fw_tp_no_encontradas, _ = validar_variables_nuevas(job, variables_nuevas_obligatorias_fw_tp)

    if len(variables_generales_no_encontradas) > 0:
        cr.add_listado(job.name, f"Las siguientes variables obligatorias nuevas no se encuentran en el job ",
                       variables_generales_no_encontradas)

    if len(variables_fw_tp_no_encontradas) > 0:

        if job.es_transmisiontp():

            cr.add_listado(job.name, f"Al tratarse de un TP, las siguientes variables no estan creadas ",
                           variables_fw_tp_no_encontradas)

        elif job.es_filewatcher():

            cr.add_listado(job.name, f"Al tratarse de un FW, las siguientes variables no estan creadas ",
                           variables_fw_tp_no_encontradas)


def cadenas_global(digrafo_global: ControlmDigrafo, contenedor_global: ControlmContainer):
    """
    Realiza controles sobre todas las cadenas de jobs del global control m prod

    :param digrafo_global: Digrafo con todos los jobs
    :param contenedor_global: Digrafo con todos los jobs
    """

    with open("analisis_cadenas.csv", 'w', newline='', encoding='utf-8') as f_cadena:
        csv_writer_cadena = csv.writer(f_cadena)
        csv_writer_cadena.writerow(["ID_CADENA", "FASE", "CANT_INGESTAS", "CANT_SMART_CLEANERS", "CANT_SM_FALTANTES"])
        cadenas = digrafo_global.obtener_arboles()
        for i, cadena_g in enumerate(cadenas):
            id_cadena = str(i).zfill(3)
            contador_instancias_ingesta = {
                'staging': 0,
                'raw': 0,
                'master': 0
            }
            contador_instancias_borradosm = {
                'staging': 0,
                'raw': 0,
                'master': 0
            }
            for jobname_g in cadena_g:
                job = contenedor_global.get_job(jobname_g)
                if job.tipo in ['T', 'P', 'C'] and job.fase is not None:
                    contador_instancias_ingesta[job.fase] += 1
                if job.tipo in ['S'] and job.fase is not None:
                    contador_instancias_borradosm[job.fase] += 1

            for fase in contador_instancias_ingesta.keys():
                if contador_instancias_ingesta[fase] > contador_instancias_borradosm[fase]:
                    diferencia = contador_instancias_ingesta[fase] - contador_instancias_borradosm[fase]
                    csv_writer_cadena.writerow([id_cadena, fase, contador_instancias_ingesta[fase], contador_instancias_borradosm[fase], diferencia])


def global_marcas(cont: ControlmContainer):
    """
    Analiza la validez de todas las marcas de los jobs. Por ej: si una marca es agregada por un job, se valida que esta
    misma sea esperada y borrada por otro. TODO: implementar

    :param cont:
    :return:
    """
    pass


def tmp_parametros(malla_tmp: ControlmFolder, recorder: RecorderTmp):
    """


    :param malla_tmp:
    :param recorder:
    :return:
    """

    if malla_tmp.order_method != 'PRUEBAS':
        recorder.add_general(
            f"El 'ORDER METHOD' de la malla no es el correcto. Esperado [PRUEBAS], obtenido [{malla_tmp.order_method}]")

    if malla_tmp.datacenter != 'CTM_CTRLMCCR':
        recorder.add_general(
            f"El servidor no es el correcto. Valor esperado [CTM_CTRLMCCR], obtenido [{malla_tmp.datacenter}]")

