"""
Este módulo informa aquellos items de elementos de un job que difieren en ambas mallas. Ej: Cuáles son los las variables
nuevas, cuáles se eliminaron y cuáles se modificaron (ABM). Las diferencias las registra un DiffRecorder
"""

import utils
from constantes import ATRIBUTOS_NO_RELEVANTES

from controlm import ControlmJob
from controlm import ControlmAction

from record import DiffRecorder


def job_nuevo(job: ControlmJob, df: DiffRecorder):
    """
    Genera una 'tabla' que en realizad es una lista de renglones (strings), formateados para que al ser pasados
    al recorder se imprima una tabla fachera. No tengo idea de cómo se me ocurrió esto y realmente no es algo
    que me enorgullezca.

    :param job: El job a informar como nuevo
    :param df: El recorder encargado de conservar la tabla hasta ser escrita
    """

    # Forgive me father, for I have sinned
    sep = "-" * 97
    tabla = [sep, "{:^97}".format("JOB NUEVO: " + job.name), sep, "{:^97}".format("ATRIBUTOS"), sep]
    for keyattr, valueattr in job.atributos.items():
        tabla.append("{:^48}|{:^48}".format(keyattr, valueattr))
    tabla.append(sep)
    tabla.append("{:^97}".format("VARIABLES"))
    tabla.append(sep)
    for key, value in job.variables.items():
        tabla.append("{:^48}|{:^48}".format(key, utils.oofstr(value)))  # Si el value viene None rompe
    tabla.append(sep)
    tabla.append("{:^97}".format("MARCAS IN"))
    tabla.append(sep)
    for marcain in job.marcasin:
        tabla.append("{:^97}".format(marcain.name))
    tabla.append(sep)
    tabla.append("{:^97}".format("MARCAS OUT"))
    tabla.append(sep)
    for marcaout in job.marcasout:
        tabla.append("{:^48}|{:^48}".format(marcaout.name, marcaout.signo))
    tabla.append(sep)

    df.add_listado(job.name, "Job nuevo", tabla)


def jobnames(work_jobnames: list, live_jobnames: list, dr: DiffRecorder) -> list:
    """
    Informa ABM de jobnames.

    :param work_jobnames: Lista de jobs de la malla ambientada
    :param live_jobnames: Lista de jobs de la malla productiva
    :param dr: Recorder encargado de logear las diferencias
    :return: Una lista con todos aquellos jobs (jobnames) que son nuevos
    """
    jobs_nuevos = utils.encontrar_nuevos(work_jobnames, live_jobnames)
    if jobs_nuevos:
        dr.add_listado('GENERAL', f"Jobs nuevos:", jobs_nuevos)

    jobs_eliminados = utils.encontrar_eliminados(work_jobnames, live_jobnames)
    if jobs_eliminados:
        dr.add_listado('GENERAL', f"Jobs eliminados:", jobs_eliminados)

    return jobs_nuevos


def atributos(workjob: ControlmJob, livejob: ControlmJob, dr: DiffRecorder):
    """
    Informa ABM de toodos aquellos aritubos del job que no se encuentren en los no relevantes. Ademas hace una
    pequeña verificacion de si pasa o deja de ser RC

    :param workjob: Job de la malla ambientada
    :param livejob: Job de la malla productiva
    :param dr: Recorder encargado de logear las diferencias
    """

    for work_key, work_value in workjob.atributos.items():

        # Ver si se encuentra el atributo en live
        live_value = livejob.atributos.get(work_key)

        if work_key in ATRIBUTOS_NO_RELEVANTES:
            continue
        elif live_value is None:
            dr.add_item(workjob.name, f"Atributo nuevo [{work_key}] valor: [{work_value}]")
        elif work_value.rstrip() != live_value.rstrip():
            dr.add_diff(workjob.name, f"Se modificó el valor del atributo {work_key}", work_value, live_value)

        # Si el job pasa a ser o deja de ser de Ruta Crítica, informar nuevamente. Esto lo hago mas que nada
        # para que no se nos pase y explote toO
        if work_key == 'SUB_APPLICATION':

            pasa_a_rc = True if work_value.replace(live_value, '') == '-RC' and work_value.endswith('-RC') else False
            deja_de_ser_rc = True if live_value.replace(work_value, '') == '-RC' and not work_value.endswith('-RC') else False

            if pasa_a_rc:
                dr.add_item(workjob.name, f"WARNING: EL JOB PASA A PERTENECER A RUTA CRÍTICA, SUB-APPLICATION:[{work_value}]. VERIFICAR CON EL EQUIPO RESPONSABLE")
            if deja_de_ser_rc:
                dr.add_item(workjob.name, f"WARNING: EL JOB DEJA DE PERTENECER A RUTA CRÍTICA, SUB-APPLICATION:[{work_value}]. VERIFICAR CON EL EQUIPO RESPONSABLE")

    for live_key in livejob.atributos.keys():
        if live_key not in workjob.atributos.keys() and live_key not in ATRIBUTOS_NO_RELEVANTES:
            dr.add_item(workjob.name, f"Se eliminó el atributo [{live_key}] valor: [{livejob.atributos.get(live_key)}]")


def variables(workjob: ControlmJob, livejob: ControlmJob, dr: DiffRecorder):
    """
    Informa ABM de todas las variables

    :param workjob: Job de la malla ambientada
    :param livejob: Job de la malla productiva
    :param dr: Recorder encargado de logear las diferencias
    """

    for work_key, work_value in workjob.variables.items():
        # Ver si se encuentra la variable en live
        live_value = livejob.variables.get(work_key)
        if live_value is None and work_value is not None:
            dr.add_item(workjob.name, f"Variable nueva [{work_key}] valor: [{work_value}]")
        elif work_value != live_value:
            dr.add_diff(workjob.name, f"Se modificó el valor de la variable [{work_key}]", work_value, live_value)

    for live_key, live_value in livejob.variables.items():
        if live_key not in workjob.variables.keys():
            dr.add_item(workjob.name, f"Se eliminó la variable [{live_key}] valor: [{live_value}]")


def marcas(workjob: ControlmJob, livejob: ControlmJob, dr: DiffRecorder):
    """
    Informa ABM de las marcas In y las OUT

    :param workjob: Job de la malla ambientada
    :param livejob: Job de la malla productiva
    :param dr: Recorder encargado de logear las diferencias
    """

    conj_marcasin_work = set(workjob.get_prerequisitos())
    conj_marcasin_live = set(livejob.get_prerequisitos())

    operacion = conj_marcasin_work.difference(conj_marcasin_live)
    if operacion:
        dr.add_listado(workjob.name, f"Se AGREGARON los siguientes pre-requisitos", operacion)

    operacion = conj_marcasin_live.difference(conj_marcasin_work)
    if operacion:
        dr.add_listado(workjob.name, f"Se ELIMINARON los siguientes pre-requisitos", operacion)

    conj_marcasout_work = set(workjob.get_acciones_marcas())
    conj_marcasout_live = set(livejob.get_acciones_marcas())

    operacion = conj_marcasout_work.difference(conj_marcasout_live)
    if operacion:
        dr.add_listado(workjob.name, f"Se AGREGARON las siguientes marcas-out", operacion)

    operacion = conj_marcasout_live.difference(conj_marcasout_work)
    if operacion:
        dr.add_listado(workjob.name, f"Se ELIMINARON las siguientes marcas-out", operacion)


def acciones(workjob: ControlmJob, livejob: ControlmJob, dr: DiffRecorder):
    """
    Analiza las diferencias entre las condiciones y las acciones agrupadas bajo la misma condicion. Se incluyeron
    dos funciones en este método porque son exclusivas de esta lógica y no pertenecen a utils

    El algoritmo que realiza esto no está del tod0 bien hecho pero esto es porque revisar un ABM entre diccionarios
    agrupados bajo una key que no te garantiza unicidad y es mas complicado que la mier**.

    Y paso a explicar por qué: Hay que meterse condicion por condicion y de cada condicion hay que evaluar
    caso por caso:

    - Si encontras accion de un lado y no del otro: Se elimino (o se agregó), sos Gardel, a mimir.
    - Si encontraste la misma accion en ambos lados y es única (en ambos lados): Sos Gardel, tenes unicidad, mirar diferencias
    - Si encontraste n acciones iguales (con mismo id) de un lado y del otro lado: Cagaste...

    Para este último caso hay que tener en cuenta que dos acciones distintas pero que realizan lo mismo tienen mismo
    id, ejemplo facil: Para la accion DOMAIL (enviar mail) podes tener varias acciones que corresponden con envios
    de mail

    DOMAIL| dest:'destinatario1@mail.com', asunto:'Ayudame loco', cuerpo:'cuerpo bien hecho'
    DOMAIL| dest:'destinatario2@mail.com', asunto:'Ayudame loco pero otro equipo', cuerpo:'asdasdasdasd'

    Como se puede ver, dos acciones distintas con mismo id pero con atributos que difieren.

    Entonces si encontraste una accion en ambos lados no te garantiza que sea un match 100%. Entonces tenes que
    meterte atributo por atributo por cada accion y ver si hay diferencias. Pero ojo porque si hay diferencias no
    quiere decir que realmente sea una diferencia. Si comparten id y no coinciden en alguno de sus atributos no te
    garantiza que sea una diferencia(esto ya lo dije lo se) es un 'candidato' a diferencia. Por lo tanto se
    guarda esto y se sigue con el siguiente ya que el siguiente puede ser el identico a esta acción
    entonces tu candidato se descarta y así indefinidamente...

    Incrementar este contador en 1 cada vez que se intente encarar este método y se falle espectacularmente en
    dejarlo funcionando al 100% sin bugs ni cosas raras
    contador_frustaciones = 14
    """

    sep = "-" * 97  # Separador

    def informar_condicion_nueva(jname: str, cond: str, lista_acciones: list[ControlmAction], direc: DiffRecorder):
        """
        Informa una condicion nueva con estructura de tabla junto con todas sus acciones al recorder

        :param jname: Jobname que posee la condicion nueva
        :param cond: Id de la condicion (ej: Retorno 0, ENDED NOT OK, etc.)
        :param lista_acciones: Lista de acciones correspondientes a la condicion
        :param direc: Recorder encargado de contener la info nueva para luego logearla
        """
        tabla = [sep, "{:^97}".format(f"CONDICION NUEVA: [{cond}]"), sep]

        for act in lista_acciones:
            tabla.append("{:^97}".format(f"ACCION [{act.id}]"))
            tabla.append(sep)
            for a_key, a_value in act.attrs.items():
                if a_key == 'ID':
                    continue
                else:
                    tabla.append("{:^48}|{:^48}".format(a_key, utils.oofstr(a_value)))
            tabla.append(sep)

        direc.add_listado(jname, "Condicion(es) nueva(s)", tabla)

    def informar_accion_nueva(jname: str, cond: str, accion_nueva: ControlmAction, direc: DiffRecorder):
        """
        Informa una accion nueva bajo una condicion al recorder

        :param jname: Jobname que posee la accion nueva
        :param cond: Id de la condicion (ej: Retorno 0, ENDED NOT OK, etc.)
        :param accion_nueva: Objeto con la info de la accion nueva
        :param direc:
        :return: Recorder encargado de contener la info nueva para luego logearla
        """
        tabla = [sep, "{:^97}".format(f"ACCION NUEVA: [{accion_nueva.id}]"), sep]

        for key, value in accion_nueva.attrs.items():
            tabla.append("{:^48}|{:^48}".format(key, utils.oofstr(value)))
        tabla.append(sep)

        direc.add_listado(jname, f"Acción nueva bajo condicion [{cond}]", tabla)

    work_conditions = workjob.onconditions
    live_conditions = livejob.onconditions

    # Comienza el baile
    for work_condition, work_actions in work_conditions.items():

        # Buscar si existe esa condicion en LIVE
        if work_condition in live_conditions.keys():
            # Existe, obtenerla para comparar
            live_actions = live_conditions.get(work_condition)
        else:
            # De no existir, deducimos que es nueva. informarla al recorder
            informar_condicion_nueva(workjob.name, work_condition, work_actions, dr)
            # Al ser condicion nueva, no requiere más analisis. Pasar a la siguiente condicion
            continue

        # Ahora iteramos accion por accion, para ver las diferencias(si las hay)
        for w_action in work_actions:

            # Opa y esto ?
            acciones_live_mismo_id = [a for a in live_actions if a.id == w_action.id]
            acciones_work_mismo_id = [a for a in work_actions if a.id == w_action.id]

            if len(acciones_live_mismo_id) == 1 and len(acciones_work_mismo_id) == 1:
                # Somos Gardel, ver las diferencias(si las hay) e informar
                l_action = acciones_live_mismo_id[0]
                for wkey, wvalue in w_action.attrs.items():
                    try:
                        lvalue = l_action.attrs[wkey]
                    except KeyError:
                        mensaje = f"Se agregó el atributo [{wkey}], VALOR: [{wvalue}] para la accion [{w_action.id}] bajo la condicion [{work_condition}]"
                        dr.add_item(workjob.name, mensaje)
                    else:
                        if lvalue != wvalue:
                            mensaje = f"Se modificó el atributo [{wkey}] para la accion [{w_action.id}] bajo la condicion [{work_condition}]"
                            dr.add_diff(workjob.name, mensaje, wvalue, lvalue)
                # Al haber informado(o no) las diferencias con la accion de work y su contraparte de live, no hay
                # que hacer más análisis. Pasar a la siguiente accion
                continue

            elif len(acciones_live_mismo_id) == 0:
                # Somos Gardel, es una accion nueva, informar
                informar_accion_nueva(workjob.name, work_condition, w_action, dr)
                # Al ser una accion nueva, no requiere más análisis. Continuar con la siguiente iteracion
                continue

            else:
                # No somos Gardel, estamos en SERIOS problemas
                # Tenemos varios caminos posibles acá
                # Recorremos accion por accion en live para ver qué caso corresponde
                accion_encontrada = False
                for accion_live_mismo_id in acciones_live_mismo_id:
                    # Vemos si son acciones equivalentes, es valido ya que se implementó el dunder __eq__
                    if accion_live_mismo_id == w_action:
                        # Si son iguales, no requiere más analisis. Salimos del loop indicando que encontramos una
                        # acción idéntica
                        accion_encontrada = True
                        break

                # De no haberse encontrado una accion que sea igual a la que estabamos analizando en la lista de
                # candidatos posibles con el mismo id, es POSIBLE que sea accion nueva.
                #
                # Acá es donde salen las canas, pues es el absolutamente peor de los casos al no haber encontrado
                # una accion similar sigue habiendo varios "candidatos"(comparten el mismo id) estamos ante la
                # chance de que haya una modificación sobre uno de los que ya estaban...
                if not accion_encontrada:
                    informar_accion_nueva(workjob.name, work_condition, w_action, dr)

                # TODO: Falta informar cuando una acción o condición está en LIVE pero no en WORK... pucha


def recursos_cuantitativos(workjob: ControlmJob, livejob: ControlmJob, dr: DiffRecorder):

    # Si no tiene recursos cuantitativos, salir
    if len(workjob.recursos_cuantitativos) == 0 and len(livejob.recursos_cuantitativos) == 0:
        return

    live_reccuantitativo = None
    for work_reccuantitativo in workjob.recursos_cuantitativos:
        live_reccuantitativo = livejob.get_recurso_cuantitativo(work_reccuantitativo.name)
        if live_reccuantitativo is None:
            dr.add_item(workjob.name, f"Nuevo recurso cuantitativo [{str(work_reccuantitativo)}]")

    else:
        if live_reccuantitativo is not None:
            del live_reccuantitativo  # Dereferenciamos para el siguiente for, paja de usar otro nombre

    # Vemos si se eliminaron
    for live_reccuantitativo in livejob.recursos_cuantitativos:
        if workjob.get_recurso_cuantitativo(live_reccuantitativo.name) is None:
            dr.add_item(workjob.name, f"Recurso cuantitativo ELIMINADO [{str(live_reccuantitativo)}]")
