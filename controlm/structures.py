"""
Modulo que contiene todas las clases correspondientes a elementos notables de control m.
"""

from __future__ import annotations

import re

import controlm.utils as utils

from controlm.constantes import TagXml
from controlm.constantes import Regex

from xml.etree.ElementTree import parse
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import ParseError
from typing import Literal

import itertools


class ControlmContainer:

    def __init__(self, workspace: Element):

        self.mallas = []
        self._jobs = dict()
        for malla_productiva in workspace.findall('FOLDER'):
            malla_obj = ControlmFolder(malla_productiva)
            self.mallas.append(malla_obj)

            for job in malla_obj.jobs():
                self._jobs[job.name] = job

    def get_malla(self, nombre_malla) -> ControlmFolder | None:
        for malla in self.mallas:
            if malla.name == nombre_malla:
                return malla
        return None

    def get_job(self, jobname: str) -> ControlmJob:
        return self._jobs[jobname]  # Para acceso O(1)

    def get_prerequisitos_globales(self) -> dict[str, str]:
        prerequisitos_globales = dict()
        for malla in self.mallas:
            for job in malla.jobs():
                for prereq in job.get_prerequisitos():
                    prerequisitos_globales[job.name] = prereq
        return prerequisitos_globales

    def get_acciones_marca_globales(self) -> dict[str, ControlmMarcaOut]:
        prerequisitos_globales = dict()
        for malla in self.mallas:
            for job in malla.jobs():
                for prereq in job.get_acciones_marcas():
                    prerequisitos_globales[job.name] = prereq
        return prerequisitos_globales


class ControlmFolder:
    """
    Representacion de una malla de control M que contiene jobs
    """

    def __init__(self, xml_input: str | Element):
        """
        Constructor

        :param xml_input: Path o elemento al archivo xml donde se encuentra la malla de control m exportada
        """
        # TODO: Migrar atributos a propiedades

        if isinstance(xml_input, str):

            self.filename = xml_input

            try:
                self._base = parse(xml_input).getroot().find(TagXml.FOLDER)
                self.name = self._base.get(TagXml.NOMBRE_MALLA)
            except (ParseError, AttributeError) as error_xml:
                mensaje = f"Archivo xml [{xml_input}] corrupto o mal formado. Revisar que posea el formato correcto de xml y respete la estructura de malla exportada de Control-m"
                raise Exception(mensaje) from error_xml

        elif isinstance(xml_input, Element):
            try:
                self._base = xml_input.find(TagXml.FOLDER)
                self.name = self._base.get(TagXml.NOMBRE_MALLA)
            except (ParseError, AttributeError) as error_xml:
                mensaje = f"Elemento [{xml_input}] corrupto o mal formado. Revisar que posea el formato correcto de xml y respete la estructura de malla exportada de Control-m"
                raise Exception(mensaje) from error_xml

        else:
            raise Exception("Proveer el tipo correcto de input para el xml, str o Element de xml")

        self._match = re.search(Regex.MALLA, self.name)
        if self._match is None:
            raise ValueError(f"No se puede obtener uuaa o periodicidad a partir del nombre malla [{self.name}] en el archivo [{xml_input}]. Para realizar el analisis es obligatorio que cumpla con el estandar definido por el regex [{Regex.MALLA}]")

        self._jobs: dict[str, ControlmJob] = dict()
        for job_element in self._base.findall(TagXml.JOB):
            try:
                job_ctrlm = ControlmJob(job_element, self.filename)
            except Exception as error_carga_job:
                mensaje = f"Ocurrió un error inesperado al cargar la informacion del xml sobre el job [{job_element.get(TagXml.JOB_NAME)}] en la malla [{self.filename}]"
                raise Exception(mensaje) from error_carga_job

            if job_ctrlm.name in self._jobs.keys():
                msg = f"No se puede cargar la informacion de una malla [{self.name}] con jobnames duplicados [{job_ctrlm.name}] en el archivo [{self.filename}]"
                raise ValueError(msg)
            else:
                self._jobs[job_ctrlm.name] = job_ctrlm

        setattr(ControlmJob, 'malla', self)

        # Armamos el digrafo de la malla
        self.digrafo = ControlmDigrafo(list(self._jobs.values()))

    def jobnames(self) -> list[str]:
        """
        Devuelve una lista de jobnames que se encuentran en la malla

        :return: Lista de jobnames
        """
        return list(self._jobs.keys())

    def jobs(self) -> list[ControlmJob]:
        return list(self._jobs.values())

    def obtener_job(self, jobname_a_buscar: str) -> [ControlmJob, None]:
        """
        Retorna, si existe, el job segun el jobname provista

        :param jobname_a_buscar: Jobname a buscar en la malla
        :return: Retorna el objeto si lo encuentra, None de lo contrario
        """
        return self._jobs.get(jobname_a_buscar, None)

    @property
    def uuaa(self) -> str:
        return self._match.group('uuaa')

    @property
    def periodicidad(self) -> str:
        return self._match.group('periodicidad')

    @property
    def order_method(self) -> str:
        return self._base.get('FOLDER_ORDER_METHOD')

    @property
    def datacenter(self) -> str:
        return self._base.get('DATACENTER')


class ControlmJob:
    """
    Clase que representa un job de control M
    """

    malla: ControlmFolder = None

    mapeo_jobtipo_descripcion = {
        'C': 'ingesta',
        'S': 'smart-cleaner',
        'V': 'hammurabi',
        'T': 'transmision',
        'P': 'transmisionTPT',
        'B': 'borradoHDFS',
        'G': 'sparkjob-custom',
        'D': 'dummy',
        'N': 'dummy',  # Cuál era el verdadero dummy? emosidoengañado?
        'W': 'filewatcher'
    }

    cant_max_iteraciones = 10  # Para la expansion de strings, que nadie se haga el vivo aca

    def __init__(self, xml_element: Element, filename: str):
        """
        Constructor

        :param xml_element: Elemento padre xml, es aquel que contiene el tag JOB
        :param filename: Nombre del archivo xml del cual se lee, se utiliza para informar en caso de error
        """

        self.name: str = xml_element.get(TagXml.JOB_NAME)
        self.atributos: dict = {i[0]: i[1] for i in xml_element.items()}

        self._match_jobname = re.search(Regex.JOBNAME, self.name)
        self._match_app = re.search(Regex.APPLICATION, self.atributos['APPLICATION'])
        self._match_dataproc_id = None
        self._match_dataproc_namespace = None

        # Variables
        self.variables = dict()
        for var in xml_element.iterfind('VARIABLE'):
            var_name = var_value = None
            for xml_name, xml_value in var.items():
                if xml_name == 'NAME':
                    var_name = xml_value
                elif xml_name == 'VALUE':
                    var_value = xml_value

                    # Aprovechamos que estamos recorriendo las variables para ver el match con los datapros
                    match_dp_id = re.search(Regex.DATAPROC_JOB_ID, xml_value)
                    if match_dp_id is not None:
                        self._match_dataproc_id = match_dp_id

                    match_dp_nm = re.search(Regex.DATAPROC_NAMESPACE, xml_value)
                    if match_dp_nm is not None:
                        self._match_dataproc_namespace = match_dp_nm

            if var_name in self.variables.keys():
                print(
                    f"WARNING: EXISTE UNA VARIABLE DUPLICADA [{var_name}], JOBNAME [{self.name}] EN LA MALLA[{filename}]. "
                    f"SE OMITIRÁ DE LOS CONTROLES Y DIFERENCIAS DE LAS VARIABLES. SOLUCIONARLO ANTES DE REALIZAR EL "
                    f"PASAJE A LIVE YA QUE VA A GENERAR COMPORTAMIENTO IMPREDECIBLE EN CONTROL-M Y EN EL CONTRASTADOR."
                )
            else:
                self.variables[var_name] = var_value

        # TODO: implementar la estructura de datos que guarde el scheduling, nota: Robar el código de Ailu :^)
        self.scheduling = None

        # Prerequisitos(Marcas-in)
        self.marcasin: list[ControlmMarcaIn] = []
        for incond in xml_element.iterfind(TagXml.MARCA_IN):
            aux_name = aux_odate = None
            for key, value in incond.items():
                if key == 'NAME':
                    aux_name = value
                elif key == 'ODATE':
                    aux_odate = value
            self.marcasin.append(ControlmMarcaIn(aux_name, aux_odate))

        # Marcasout(acciones de marca)
        self.marcasout: list[ControlmMarcaOut] = []
        for incond in xml_element.iterfind(TagXml.MARCA_OUT):
            aux_name = aux_odate = aux_sign = None
            for key, value in incond.items():
                if key == 'NAME':
                    aux_name = value
                elif key == 'ODATE':
                    aux_odate = value
                elif key == 'SIGN':
                    aux_sign = value
            self.marcasout.append(
                ControlmMarcaOut(
                    marca_nombre=aux_name,
                    odate_esperado=aux_odate,
                    signo=aux_sign,
                    mediante_accion=False
                )
            )

        # Marcasout(pero ahora con aquellas que son mediante una condicion, ej: retorno 7)
        for on_group in xml_element.iterfind(TagXml.ON_CONDITION):
            for on_action in on_group.iterfind(TagXml.ON_DOCOND):
                self.marcasout.append(
                    ControlmMarcaOut(
                        marca_nombre=on_action.get('NAME'),
                        odate_esperado=on_action.get('ODATE'),
                        signo=on_action.get('SIGN'),
                        mediante_accion=True
                    )
                )

        # Recursos cuantitativos
        self.recursos_cuantitativos: list[ControlmRecursoCuantitativo] = []
        for recurso in xml_element.iterfind(TagXml.RECURSO_CUANTITATIVO):
            self.recursos_cuantitativos.append(ControlmRecursoCuantitativo(recurso.get('NAME')))

        # On-conditions(las peores)
        self.onconditions: dict = {}
        for ongroup in xml_element.iterfind('ON'):

            for condition_key, condition_value in ongroup.items():
                if condition_key == 'CODE':
                    self.onconditions[condition_value]: list[ControlmAction] = []
                    break

            for action_element in ongroup.iter():
                if action_element.tag == 'ON':
                    continue

                if condition_value:
                    self.onconditions[condition_value].append(
                        ControlmAction(
                            action_id=action_element.tag,
                            attrs={action_key: action_value for action_key, action_value in action_element.items()}
                        )
                    )

        # Fase del job, si es staging|raw|master. Esta es una de las peores partes de la clase, la cantidad de
        # suposiciones que se tienen que hacer es exageradamente alta. Proceder con precaución
        self.fase: Literal['master', 'staging', 'raw', None] = None
        match self.tipo:

            case 'P' | 'T':  # Transmision
                self.fase = 'staging'

            case 'B' | 'S':  # Borrado
                info_match_dataproc = self.get_info_dataproc_id()
                if info_match_dataproc is not None:

                    if info_match_dataproc['tipo'] == 'dfs' or info_match_dataproc['subtipo'] == 'rmv':
                        # Tenemos que recorrer todas las variables y ver a qué path apuntan
                        for var_value in self.variables.values():
                            if var_value is None:
                                continue
                            if '/in/staging/' in var_value:
                                self.fase = 'staging'
                                break
                            if '/data/raw/' in var_value:
                                self.fase = 'raw'
                                break
                            if '/data/master/' in var_value:
                                self.fase = 'master'
                                break

            case 'C':  # 'ingesta', o bien, mover cosas de un lado a otro
                info_match_dataproc = self.get_info_dataproc_id()
                if info_match_dataproc is not None:

                    if info_match_dataproc['tipo'] in ['spk', 'biz', 'psp', 'sbx', 'hmm'] or info_match_dataproc['nombre'] == 'hdfsrename':
                        # Proceso spark o tablon, es de master (deberia...). Renombrado tambien va master
                        self.fase = 'master'

                    if info_match_dataproc['tipo'] == 'krb' and info_match_dataproc['subtipo'].startswith('in'):
                        if info_match_dataproc['subtipo'].endswith('m'):
                            self.fase = 'master'
                        if info_match_dataproc['subtipo'].endswith('r'):
                            self.fase = 'raw'
                        if info_match_dataproc['subtipo'].endswith('s'):
                            self.fase = 'staging'  # No creo que sea posible, pero uno siempre se sorprende

                    if info_match_dataproc['tipo'] == 'krb' and info_match_dataproc['subtipo'] == 'trn':
                        self.fase = 'master'

            case 'V':  # Hammurabi
                info_match_dataproc = self.get_info_dataproc_id()
                if info_match_dataproc is not None:

                    if info_match_dataproc['tipo'] in ['spk', 'hmm'] and info_match_dataproc['subtipo'] == 'qlt':
                        if info_match_dataproc['nombre'].endswith('m'):
                            self.fase = 'master'
                        if info_match_dataproc['nombre'].endswith('r'):
                            self.fase = 'raw'
                        if info_match_dataproc['nombre'].endswith('s'):
                            self.fase = 'staging'

                        if self.fase is None and (info_match_dataproc['pais'] == 'gl' or info_match_dataproc['uuaa'].startswith('k')):
                            self.fase = 'master'

                        if self.fase is None:
                            # Cuando tod0 falla, recurrimos a la descripcion del job
                            descripcion = self.atributos.get('DESCRIPTION').lower()
                            if 'raw' in descripcion:
                                self.fase = 'raw'
                            elif 'master' in descripcion:
                                self.fase = 'master'
                            elif 'staging' in descripcion:
                                self.fase = 'staging'

                    if info_match_dataproc['tipo'] == 'hmm' and info_match_dataproc['subtipo'] == 'trn':
                        self.fase = 'master'

    def __str__(self):
        return self.name

    @property
    def tipo(self) -> str:
        """
        El tipo de un job es un caracter que indica qué es lo que debería hacer. Definido por el REGEX_JOBNAME

        :return: Un caracter. Ej para AMOLCP0017 debería ser 'C'
        """
        return self.get_info_jobname()['tipo']

    @property
    def tipo_descripcion(self) -> str:
        """
        La descripcion es una forma verbosa de informar al usuario lo que hace un job. Ej: si es de tipo C, será de
        'ingesta'. Viene definido por el mapeo de la clase

        :return: String que representa la descripcion del job
        """
        return self.mapeo_jobtipo_descripcion[self.tipo]

    @property
    def app(self) -> str:
        return self.atributos['APPLICATION']

    @property
    def subapp(self) -> str:
        return self.atributos['SUB_APPLICATION']

    @property
    def dataproc_id(self) -> str | None:
        return self._match_dataproc_id.group(0) if self._match_dataproc_id is not None else None

    @property
    def dataproc_namespace(self) -> str | None:
        return self._match_dataproc_namespace.group(0) if self._match_dataproc_namespace is not None else None

    @property
    def command(self) -> str | None:
        return self.atributos.get('CMDLINE')

    def get_info_dataproc_id(self) -> dict:
        """
        Devuelve un diccionario con los grupos capturados del dataproc_job_id, recordar que este tiene esta forma (es
        un ejemplo): adco-ar-krb-inr-leasingfeeplannedagmtr-01

        :return: diccionario con la info del jobname
        """
        return self._match_dataproc_id.groupdict() if self.dataproc_id is not None else None

    def get_info_dataproc_namespace(self) -> dict:
        """
        Devuelve un diccionario con los grupos capturados del dataproc_namespace, recordar que este tiene esta forma (es
        un ejemplo): ar.amol.app-id-20247.pro

        :return: diccionario con la info del jobname
        """
        return self._match_dataproc_id.groupdict() if self.dataproc_id is not None else None

    def jobname_valido(self) -> bool:
        """
        Determina si un jobname es válido, para ello simplemente ve si matchea con la expresion regular REGEX_JOBNAME

        :return: True si es válido, False de lo contrario
        """
        return True if self._match_jobname is not None else False

    def get_info_jobname(self) -> dict:
        """
        Devuelve un diccionario con los grupos capturados del jobname, dado que el jobname en sí contiene bastante
        informacion

        :return: diccionario con la info del jobname
        """
        return self._match_jobname.groupdict()

    def application_valida(self) -> bool:
        """
        Determina si la application de un job es válida, para ello simplemente ve si matcheó con la expresion
        regular REGEX_APPLICATION

        :return: True si es válido, False de lo contrario
        """
        return True if self._match_app is not None else False

    def get_info_application(self) -> dict | None:
        """
        Devuelve un diccionario con los grupos capturados y sus respectivos matches

        :return: diccionario con la info del jobname
        """
        return self._match_app.groupdict() if self._match_app is not None else None

    def get_prerequisitos(self) -> list:
        """
        Devuelve una lista con nombres de prerequisitos del job. No incluye el ODATE esperado debido a que devuelve los
        identificadores, no referencias a los objetos

        :return: Lista con nombres de prerequisitos
        """
        return [m.name for m in self.marcasin]

    def get_recurso_cuantitativo(self, name: str) -> ControlmRecursoCuantitativo | None:
        """
        Devuelve un recurso cuantitativo dado un nombre

        :param name: Nombre deel RRCC a buscar en el job
        :return: El RRCC segun el nombre, None si no lo encuentra
        """
        for rec in self.recursos_cuantitativos:
            if rec.name == name:
                return rec
        return None

    def get_acciones_marcas(self) -> list:
        """
        Devuelve una lista de marcas out del job

        :return: Una lista de strings que representan las marcas out (acciones)
        """
        return [str(m) for m in self.marcasout]

    def es_ruta_critica(self) -> bool:
        return self.atributos['SUB_APPLICATION'].endswith('-RC')

    def es_filewatcher(self) -> bool:
        tipo = self._match_jobname.group('tipo')
        return tipo == 'W'

    def es_transmisiontp(self) -> bool:
        tipo = self._match_jobname.group('tipo')
        return tipo == 'T'

    def es_tpt(self) -> bool:
        tipo = self._match_jobname.group('tipo')
        return tipo == 'P'

    def expandir_string(self, template: str, iter_actual: int = 1) -> str:
        """
        Reemplaza todas las variables que se encuentran en un string e para ver cómo quedarían resueltas en tiempo de
        ejecución por control M. Ej: "OK JOB %%JOBNAME", reemplazado es "OK JOB AMOLCP0001"

        Si una variable no está definida y no se puede resolver, la reemplazara por CTMERR

        Esto se resuelve de forma recursiva, para evitar recursividad infinita si es que alguien es malo y reemplaza
        una variable con otra vamos a frenarlo en la cantidad maxima de iteraciones permitidas, que viene definida en
        la clase

        :param template: El string a ser expandido, es decir, a ser reemplazado con sus variables
        :param iter_actual: Iteracion actual, si se pasa salir para no entrar en un bucle infinito
        :return: El string sin variables
        """
        variables_por_defecto = {
            '%%JOBNAME': self.name,
            '%%SCHEDTABLE': 'CR-ARXXXXXX-X02',
            '%%$ODATE': '99999999',
            '%%$ORDERID': 'xxxx'
        }
        # TODO: Hacer el CTMERR :^), lo mencioné en el docstring pero no se hizo aún

        if iter_actual > self.cant_max_iteraciones:
            print(f"WARNING: CANTIDAD MÁXIMA DE ITERACIONES ({iter_actual}) AL EXPANDIR EL STRING [{template}] ALCANZADAS. REVISAR RECURSIVIDAD INFINITA EN LAS VARIABLES DE CONTROL M")

        # El sorted mitiga aquellas variables que pueden estar incluídas en ellas mismas
        # Ejemplo %%MAIL="hola", %%MAIL_2="hola_soyotro"
        # Si el asunto es "Enviando mail a %%MAIL_2", vamos a evitar que se reemplace de la siguiente forma:
        # "Enviando mail a hola_2", que es incorrecto, debería ser "Enviando mail a hola_soyotro"
        for key in sorted(self.variables, key=len, reverse=True):
            template = template.replace(key, utils.oofstr(self.variables[key]))

        for key in variables_por_defecto:
            template = template.replace(key, variables_por_defecto[key])

        iter_actual += 1
        if '%%' in template and iter_actual <= self.cant_max_iteraciones:
            self.expandir_string(template, iter_actual)

        return template


class ControlmMarcaIn:
    """
    Una Marca-In, también conocida como pre-requisito, es una marca que el job espera con una cierta fecha de operacion
    ODATE para poder iniciar. Se considera como mal formada si no cumple con las iguiente estructura:

    JOBNAMEORIGEN-TO-JOBNAMEDESTINO

    Dicho esto, una marca no necesariamente tiene que cumplir con esta nomenclatura para funcionar, solamente es un
    estandar definido para que no sea un desastre y explote control m.
    """

    def __init__(self, marca_nombre: str, odate_esperado: str):
        """
        Constructor del prerequisito.

        :param marca_nombre: Identificador único de la marca, debe seguir el estandar definido en la clase
        :param odate_esperado: Fecha de operación esperada asociada a la marca
        """

        self.name = marca_nombre

        try:
            index = marca_nombre.index('-TO-')
        except ValueError:
            self.origen = None
            self.destino = None
        else:
            self.origen = marca_nombre[:index]
            self.destino = marca_nombre[index+4:]

            self._match_origen = re.search(Regex.JOBNAME, self.origen)
            self._match_destino = re.search(Regex.JOBNAME, self.destino)

        self.odate = odate_esperado

    def __str__(self):
        return self.name

    def es_valida(self) -> bool:
        """
        Devuelve True si la marca se considera como valida. Es considerada como tal si cumple con la nomenclatura y
        ambos jobnames que componen el nombre de la marca son validos

        :return: True si es valida, False si no es valida
        """

        origen_valido = self.origen is not None and self._match_origen is not None
        destino_valido = self.destino is not None and self._match_destino is not None

        return origen_valido and destino_valido

    def get_info_origen(self) -> [dict, None]:
        return self._match_origen.groupdict() if self._match_origen is not None else None

    def get_info_destino(self) -> [dict, None]:
        return self._match_destino.groupdict() if self._match_destino is not None else None


class ControlmMarcaOut(ControlmMarcaIn):
    """
    Una marca out en realidad una accion. Dicha acción es agregar una amrca al servidor de control M. Esta accion se
    puede dar por dos eventos notables:

    - El job finaliza OK: en este caso el job va a agregar todas las marcas que tenga indicadas en su pestaña actions
    - Condicion: Dada una condicion, existe la posibilidad de que bajo esta accion un job agregue una marca al servidor.

    Con respecto al segundo caso:
    Esto no necesariamente significa que el job finalizó ok, sino que se cumplió dicha condición para que se agregue
    una marca. Ej: En la malla de KTNY, si el filewatcher no encuentra archivo a cabo de 12 horas va a retornar con
    código 7 y esto significa que tiene que agregar una marca a un job dummy para que este corra porque, si bien no
    encontró archivo, le está indicando que "ejecute con lo que estaba en el día de ayer ya que hoy no vamos a
    recibir archivo"
    """

    def __init__(self, marca_nombre: str, odate_esperado: str, signo: str, mediante_accion: bool = False):
        """
        Constructor

        :param marca_nombre: Identificador único de la marca, debe seguir el estandar definido en la clase
        :param odate_esperado: Odate el cual será asociado a la marca una vez agregada o eliminead del servidor
        :param signo: Puede ser + o - y nos indica qué se está haciendo con la marca: agregar o quitar
        :param mediante_accion: Booleano que nos indica si la marga fue agregada mediante finalizacion OK o condicion.
        """

        super().__init__(marca_nombre, odate_esperado)
        self.signo = signo
        self.mediante_accion = mediante_accion

    def __str__(self):
        return f"{self.name} ({self.signo})"


class ControlmAction:
    """
    Clase base para todas las acciones, los attrs son los atributos propios del tag xml. Una accion se 'detona' cuando
    se cumple cierto 'evento'. Por ejemplo: Cuando un job finaliza OK, NOT OK,  retorno x (donde x es el código de
    retorno), etc. Se pueden detonar n acciones bajo un evento. Ej: Si el job finaliza NOT OK pueden enviarse 3 mails
    a casillas distintas con distintos mensajes.
    """

    def __init__(self, action_id: str, attrs: dict):
        """
        Constructor

        :param action_id: Identificador que nos indica qué acción se va a realizar
        :param attrs: Atributos propios de la accion, ej: para la acción DOMAIL estos atributos pueden ser el remitente,
        el destinatario, el mensaje, etc. Estos atributos dependen de la acción a la cual están asociados
        """

        self.id = action_id
        self.attrs = attrs

    def __eq__(self, other: ControlmAction) -> bool:

        resultado = True

        if self.id != other.id or len(self.attrs) != len(other.attrs):
            resultado = False

        for key, value in self.attrs.items():
            try:
                other_value = other.attrs[key]
            except KeyError:
                resultado = False
            else:
                if value != other_value:
                    resultado = False

        return resultado


class ControlmRecursoCuantitativo:
    """
    Un recurso cuantitativo (RRCC) es simplemente un key con un valor, nada mas. Hay más logica dentro del mismo para
    validar si está 'ok' pero la base es eso. No se ecplicará qué representa o como funcionan ya que nuestro trabajo es
    solamente validarlos.

    Tienen esta forma: ARD-NC-UUAA (no es regla, pueden cambiar y no se exactamente cual es). Siempre tienen que estar
    separados opr guiones
    """

    def __init__(self, name: str):
        """
        Constructor

        :param name: Nombre, identificador único del recurso.
        """

        self.name = name

    def __eq__(self, other: ControlmRecursoCuantitativo):

        if not isinstance(other, ControlmRecursoCuantitativo):
            return False

        if self.name == other.name:
            return True
        else:
            return False

    def __str__(self):
        return self.name

    def seccionar(self) -> list:
        """
        Divide al RRCC, separandolo en base a los guiones
        :return: Una lista con todas las 'secciones' que lo componen
        """

        return self.name.split('-')


class ControlmDigrafo:
    """
    Clase para abstraer una cadena de jobs de control M, se comporta como una lista de "relaciones" o "aristas" entre
    nodos, dichos nodos son jobs de control M. La estructura de un elemento de la lista es:
    inicio -> [final1, final2, final3, ... finaln]

    Donde inicio indica cual es el nodo de partida y la lista a la cual apunta representa todas las aristas del nodo.
    Si un nodo es hoja, apunta a una lista vacia.

    Un conjunto de nodos con todas sus aristas se denomina Digrafo
    """

    def __init__(self, jobs: list[ControlmJob]):
        """
        Constructor

        :param jobs: Lista de jobs a ser agregados al Digrafo
        """
        self._grafo: dict[str, list[str]] = {}
        self._grafo_inverso: dict[str, list[str]] = {}

        for job in jobs:
            self._grafo[job.name] = []
            self._grafo_inverso[job.name] = []

            for marca_out in job.marcasout:
                if marca_out.signo == '+':
                    for job_aux in jobs:
                        if marca_out.name in [marcain.name for marcain in job_aux.marcasin]:
                            self._grafo[job.name].append(job_aux.name)

            for prerequisito in job.get_prerequisitos():
                for job_aux in jobs:
                    if prerequisito in [marcaout.name for marcaout in job_aux.marcasout if marcaout.signo == '+']:
                        self._grafo_inverso[job.name].append(job_aux.name)

    def __str__(self):
        s = ""
        for nodo, hijos in self._grafo.items():
            if hijos:
                s += f"{nodo}: {str([hijo for hijo in hijos])}\n"
            else:
                s += f"{nodo}: []\n"
        return s

    def str_controlm(self, jobname: str) -> str:
        """
        Genera un string de jobs pertenecientes a una cadena que puede ser filtrado en control m.
        :param jobname: jobname a partir del cual se analizará hacia abajo en el digrafo
        """
        return '|'.join(self.recorrer_cadena(jobname))

    def str_controlm_inverso(self, jobname: str) -> str:
        """
        Genera un string de jobs pertenecientes a una cadena que puede ser filtrado en control m
        :param jobname: jobname a partir del cual se analizará hacia arriba en el digrafo
        """
        return '|'.join(self.recorrer_cadena_inversa(jobname))

    def obtener_paresxy(self) -> tuple:
        """
        Retorna una tupla de tuplas que son pares (x,y) que representa una arista entre dos nodos del digrafo. Es
        unilateral y se lee "X da marca a Y (e Y la espera)"

        :return: tupla de tuplas (x,y) con las relaciones entre jobnames
        """
        pares = []
        for nodo, hijos in self._grafo.items():
            for hijo in hijos:
                if hijo is None:
                    pares.append((nodo, hijo))
                else:
                    pares.append((nodo, hijo))
        return tuple(pares)

    def raices(self) -> list[str]:
        """
        Devuelve aquellos nodos del digrafo que no tienen predecesores. Se considera como raíz si el nodo no se
        encuentra en ninguna arista

        :return: Lista de jobnames que no tienen prerequisitos
        """
        raices = []
        for nodo in self._grafo.keys():
            es_raiz = True

            for hijos in self._grafo.values():
                if nodo in [hijo for hijo in hijos if hijo is not None]:
                    es_raiz = False
                    break

            if es_raiz:
                raices.append(nodo)

        return raices

    def es_raiz(self, jobname: str) -> bool:
        """
        Verifica si un jobname es raiz de una cadena

        :param jobname: Jobname a verificar
        :return: True si lo es, Falso caso contrario
        """
        return True if jobname in self.raices() else False

    def es_hoja(self, jobname: str) -> bool:
        """
        Verifica si un jobname es hoja de una cadena

        :param jobname: Jobname a verificar
        :return: True si lo es, Falso caso contrario
        """
        return True if jobname in self.hojas() else False

    def hojas(self) -> list[str]:
        """
        Devuelve aquellos nodos del digrafo que no tienen sucesores. Se considera como hoja si el nodo no tiene ninguna
        arista, es decir, apunta a una lista vacía

        :return: Lista de jobnames que no tienen prerequisitos
        """
        return [job for job, hijos in self._grafo.items() if not hijos]

    def recorrer_cadena(self, inicio: str, visitados=None) -> list[str]:
        """
        Recorre una cadena dado un inicio, utiliza el algoritmo Depth First Search y 10 gramos de recursividad. La
        ventaja de este algoritmo es que no va a explotar con digrafos circulares o nodos que tengan aristas para sí
        mismos

        :param inicio: Jobname inicial a partir del cual se inicia el recorrido
        :param visitados: conjunto de jobnames que ya fueron visitados por el algoritmo
        :return: Lista de nodos (no ordenada) que contiene los jobnames que pertenecen a la cadena. El primer elemento
            siempre es el inicio de la cadena
        """
        if visitados is None:
            visitados = set()
        visitados.add(inicio)
        cadena = [inicio]
        for hijo in self._grafo.get(inicio, []):
            if hijo not in visitados:
                cadena.extend(self.recorrer_cadena(hijo, visitados))

        return cadena

    def recorrer_cadena_inversa(self, inicio: str, visitados=None) -> list[str]:
        """
        Identico a recorrer_cadena, pero en vez de recorrer el grafo 'hacia abajo' lo recorre en base a los
        prerequisitos de un job, osea, 'hacia arriba'.

        :param inicio: Jobname inicial a partir del cual se inicia el recorrido
        :param visitados: conjunto de jobnames que ya fueron visitados por el algoritmo
        :return: Lista de nodos (no ordenada) que contiene los jobnames que pertenecen a la cadena. El primer elemento
            siempre es el inicio de la cadena
        """
        if visitados is None:
            visitados = set()
        visitados.add(inicio)
        cadena = [inicio]
        for hijo in self._grafo_inverso.get(inicio, []):
            if hijo not in visitados:
                cadena.extend(self.recorrer_cadena_inversa(hijo, visitados))

        return cadena

    def recorrer_cadena_completa(self, inicio: str) -> list[str]:
        """
        Obtiene la cadena completa que 'nace' a partir del inicio. TODO: completar

        :param inicio: Jobname inicial a partir del cual se inicia el recorrido
        """
        return list(set(self.recorrer_cadena(inicio) + self.recorrer_cadena_inversa(inicio)))

    def obtener_arboles(self) -> list[set[str]]:
        """
        Se denomina arbol al conjunto de subconjuntos de nodos que forman parte del Digrafo, es decir que este método
        retornará una lista de cadenas que forman parte del digrafo. Las cadenas entre sí no están conectadas.

        :return: Lista de cadenas "aisladas"
        """
        cadenas = [set(self.recorrer_cadena(raiz)) for raiz in self.raices()]
        # En el arbol se guardan todas las cadenas
        arbol = []

        while cadenas:
            conjunto_actual = cadenas.pop(0)
            unidos = True

            while unidos:
                unidos = False
                for s in cadenas:
                    if not conjunto_actual.isdisjoint(s):
                        # Unimos los conjuntos con interseccion
                        conjunto_actual.update(s)
                        cadenas.remove(s)  # Lo sacamos de la cadena porque fue unido
                        unidos = True
                        break

            arbol.append(conjunto_actual)

        return arbol

    def find_shortest_path(self, start, end, path=None) -> list[str] | None:
        """
        Adaptado de alguna publicación oficial de Python que hasta hoy en día no pude volver a encontrar el
        link a la misma. Encuentra el camino (que, en teoría es el mas corto) de un job a otro

        :param start: Inicio de la cadena
        :param end: Target, osea job al cual se debe buscar el camino
        :param path: Lista de jobnames en la cual se va armando el camino
        :return: Lista de jobnames ***en orden*** que representa el camino desde un job a otro
        """
        if path is None:
            path = []
        path = path + [start]
        if start == end:
            return path
        if start not in self._grafo.keys():
            return None
        shortest = None
        for node in self._grafo[start]:
            if node not in path:
                newpath = self.find_shortest_path(node, end, path)
                if newpath:
                    if not shortest or len(newpath) < len(shortest):
                        shortest = newpath
        return shortest

    def obtener_pares_xy_cadena(self, cadena_jobnames: list[str]) -> list[tuple[str, str]]:
        lista_pares_retorno = []
        pares_xy = self.obtener_paresxy()

        for parxy in pares_xy:
            if parxy[0] in cadena_jobnames and parxy[1] in cadena_jobnames:
                lista_pares_retorno.append(parxy)

        return lista_pares_retorno


class MallaMaxi:
    """
    Abstracción de lo que se va a transformar en una malla temporal. Toma como base la lista de jobs que se deben
    'transformar' y la malla de referencia de la cual obtiene informacion que usa durante tod0 el proceso
    """

    def __init__(self, cadena_jobnames: list[ControlmJob], malla_origen: ControlmFolder):
        """
        Constructor

        :param cadena_jobnames: Lista de jobs que se deben transformar a temporales
        :param malla_origen: Malla que contiene los jobs
        """
        self.cadena_primordial = None
        self._trabajos_seleccionados = cadena_jobnames
        self._malla_origen = malla_origen

    def ordenar(self):
        """
        Genera una lista de jobnames que representa la cadena 'base', o 'primordial' de la malla temporal. A partir de
        esta cadena se van a generar tantas como odates se hayan seleccionado en tkinter.
        """

        # TODO: Contemplar el caso en el cual una cadena tiene 2 o mas raices (hay que generar el arbol)
        cadenas_relevantes = [self._malla_origen.digrafo.recorrer_cadena_completa(job.name) for job in self._trabajos_seleccionados]
        cadenas_relevantes = list(k for k, _ in itertools.groupby(cadenas_relevantes))

        # cadena_final_tmp es una Lista de tuplas que tiene la siguiente estructura:
        #   (jobname, orden_en_cadena)
        #
        # Dicha lista ya viene con los jobs ordenados, es decir, que ya 'se sabe' qué jobname le debe dejar marca a cual
        #
        # Por ej: [('AMOLCP0010', 4), ('AMOLCP0011', 5)]
        # Cuando se exporte la temporal AMOLCP0010 le va a dejar marca a AMOLCP0011
        #
        # Nota: cadena_final_tmp ya está filtrada (ver el filter que se realiza sobre cadena_con_orden de mas abajo),
        # pues no va a poseer los jobs que no fueron seleccionados en tequinter
        cadena_final_tmp = []

        for cadena in cadenas_relevantes:
            cadena_con_orden = []
            for jobname in cadena:
                if self._malla_origen.digrafo.es_raiz(jobname):
                    cadena_descendiente = self._malla_origen.digrafo.recorrer_cadena(jobname)
                    for jobname_des in cadena_descendiente:
                        cadena_con_orden.append(
                            (jobname_des, len(self._malla_origen.digrafo.find_shortest_path(start=jobname, end=jobname_des)))
                        )
                    break

            cadena_final_tmp.append(
                list(
                    filter(
                        lambda x: x[0] in [trabajo.name for trabajo in self._trabajos_seleccionados],  # Sacamos aquellos que no fueron seleccionados
                        cadena_con_orden)
                )
            )

        cadena_primordial = [e[0] for lista in cadena_final_tmp for e in lista]



        self.cadena_primordial = cadena_primordial

    def ambientar(self):
        pass

    def replicar(self):
        pass

    def enlazar(self):
        pass

    def exportar(self) -> Element:  # TODO: ETREE
        pass