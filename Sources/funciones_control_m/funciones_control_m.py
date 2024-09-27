"""
Contrastador de mallas.

Analiza diferencias entre dos mallas exportadas de control M  y logea en un archivo para posterior análisis.
Necesita 1 xml en cada carpeta LIVE_FOLDER y WORK_FOLDER.
"""
from __future__ import annotations

import csv
import shutil
import re
import abc
import os
import base64
import time


from xml.etree.ElementTree import parse
from xml.etree.ElementTree import Element
from pathlib import Path
from difflib import SequenceMatcher
from datetime import date

from typing import Literal

# Carpetas donde se encuentran los archivos a controlar
WORK_FOLDER = 'TODO_MALLA'

ATRIBUTOS_NO_RELEVANTES = [
    'CHANGE_DATE',
    'CHANGE_TIME',
    'VERSION_SERIAL',
    'VERSION_HOST',
    'JOBISN',
    'CREATION_TIME',
    'CREATION_DATE',
    'CREATION_USER',
    'CHANGE_USERID',
    'INSTREAM_JCL',
    'CHANGE_USERID',
    'CHANGE_DATE',
    'CHANGE_TIME',
    'VERSION_OPCODE',
    'IS_CURRENT_VERSION'
]

# La jerarquía es DEFTABLE -> FOLDER -> JOB -> todos los hijos correspondientes a un JOB
TAG_DEFTABLE = 'DEFTABLE'
TAG_FOLDER = 'FOLDER'
TAG_JOB = 'JOB'
TAG_JOB_NAME = 'JOBNAME'
TAG_NOMBRE_MALLA = 'FOLDER_NAME'
TAG_MARCA_IN = 'INCOND'
TAG_MARCA_OUT = 'OUTCOND'
TAG_ON_CONDITION = 'ON'
TAG_RECURSO_CUANTITATIVO = 'QUANTITATIVE'
TAG_ON_DOCOND = 'DOCOND'

# Este diccionario es una correspondencia entre el dígito de periodicidad de un jobname y la periodicidad de una malla
# se formó en base al manual de estandares de control m. Hay más pero por lo que veo solo se usan estos
MAPEO_PERJOBNAME_PERMALLA = {
    '0': 'DIA',
    '4': 'MEN',
    '9': 'EVE'
}

REGEX_DATAPROC_NAMESPACE = r'(?P<pais>\w{2})\.(?P<uuaa>k?[a-z0-9]{3,4})\.app-id-(?P<id>\d+.)\.(?P<ambiente>(dev|pro))'
REGEX_DATAPROC_JOB_ID = r'(?P<uuaa>k?[a-z0-9]{3,4})-(?P<pais>\w{2})-(?P<tipo>\w{3,4})-(?P<subtipo>\w{3,4})-(?P<nombre>.*)-(?P<nro>\d+)'
REGEX_MALLA = r'^CR-AR(?P<uuaa>K?[A-Z0-9]{3,4})(?P<periodicidad>[A-Z]{3})-[TK]02$'
REGEX_APPLICATION = r'^(?P<uuaa>K?[A-Z0-9]{3,4})-(?P<pais>[A-Z]{2})-(?P<app>[A-Z0-9]+)$'
REGEX_JOBNAME = r'^(?P<pais>[A-Z])(?P<uuaa>K?[A-Z0-9]{3,4})(?P<tipo>[NEDRTCWAVMBPGSD])(?P<entorno>[PBDTCM])(?P<periodicidad>\d)[0-9A-Z]{3}$'
REGEX_MAILS = r'[^@ \t\r\n]+@[^@ \t\r\n]+\.[^@ \t\r\n]+'
REGEX_TABLA = r'^t_(?P<uuaa>k?[a-z0-9]{3,4})_.+$'


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
            self.destino = marca_nombre[index + 4:]

            self._match_origen = re.search(REGEX_JOBNAME, self.origen)
            self._match_destino = re.search(REGEX_JOBNAME, self.destino)

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

    Tienen esta forma: ARD-NC-UUAA (no es regla, pueden cambiar y no se exactamente cual es)
    """

    def __init__(self, name: str):
        """
        Constructor

        :param name: Nombre, identificador único del recurso. Hay un estandar pero no se va a definir aca
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

    Donde inicio indica cual es el nodo de partida y la lista a la cual apunta representa todas las aritas del nodo.
    Si un nodo es hoja, apunta a una lista vacia
    """

    def __init__(self, jobs: list[ControlmJob]):
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
        Genera un string de jobs pertenecientes a una cadena que puede ser filtrado en control m
        :param jobname: jobname a partir del cual se analizará hacia abajo en el digrafo
        """
        return '|'.join(self.recorrer_cadena(jobname))

    def str_controlm_inverso(self, jobname: str) -> str:
        """
        Genera un string de jobs pertenecientes a una cadena que puede ser filtrado en control m
        :param jobname: jobname a partir del cual se analizará hacia arriba en el arbol
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
        prerequisitos de un job, osea, 'hacia arriba'

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

    def obtener_arboles(self) -> list[set[str]]:
        cadenas = [set(self.recorrer_cadena(raiz)) for raiz in self.raices()]
        # En el arbol se guardan todas las cadenas
        arbol = []

        while cadenas:
            conjunto_actual = cadenas.pop(0)
            unidos = True

            # Keep merging with other sets as long as there are common elements
            while unidos:
                unidos = False
                for s in cadenas:
                    if not conjunto_actual.isdisjoint(s):
                        # Unimos los conjuntos con interseccion
                        conjunto_actual.update(s)
                        cadenas.remove(s)  # Lo sacamos de la cadena porque fue unido
                        unidos = True
                        break

            # Add the merged set to the list of merged sets
            arbol.append(conjunto_actual)

        return arbol


class ControlmJob:
    """
    Clase que representa un job de control M
    """

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

        self.name: str = xml_element.get(TAG_JOB_NAME)
        self.atributos: dict = {i[0]: i[1] for i in xml_element.items()}

        self._match_jobname = re.search(REGEX_JOBNAME, self.name)
        self._match_app = re.search(REGEX_APPLICATION, self.atributos['APPLICATION'])
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
                    match_dp_id = re.search(REGEX_DATAPROC_JOB_ID, xml_value)
                    if match_dp_id is not None:
                        self._match_dataproc_id = match_dp_id

                    match_dp_nm = re.search(REGEX_DATAPROC_NAMESPACE, xml_value)
                    if match_dp_nm is not None:
                        self._match_dataproc_namespace = match_dp_nm

            if var_name in self.variables.keys():
                print(
                    f"WARNING: EXISTE UNA VARIABLE DUPLICADA [{var_name}], JOBNAME [{self.name}] EN LA MALLA[{filename}]. "
                    f"SE OMITIRÁ DE LOS CONTROLES Y DIFERENCIAS DE LAS VARIABLES. SOLUCIONARLO ANTES DE REALIZAR EL PASAJE A LIVE YA VA A "
                    f"GENERAR COMPORTAMIENTO IMPREDECIBLE EN CONTROL-M Y EN EL CONTRASTADOR."
                )
            else:
                self.variables[var_name] = var_value

        # TODO: implementar la estructura de datos que guarde el scheduling, nota: Robar el código de Ailu :^)
        self.scheduling = None

        # Prerequisitos(Marcas-in)
        self.marcasin: list[ControlmMarcaIn] = []
        for incond in xml_element.iterfind(TAG_MARCA_IN):
            aux_name = aux_odate = None
            for key, value in incond.items():
                if key == 'NAME':
                    aux_name = value
                elif key == 'ODATE':
                    aux_odate = value
            self.marcasin.append(ControlmMarcaIn(aux_name, aux_odate))

        # Marcasout(acciones de marca)
        self.marcasout: list[ControlmMarcaOut] = []
        for incond in xml_element.iterfind(TAG_MARCA_OUT):
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
        for on_group in xml_element.iterfind(TAG_ON_CONDITION):
            for on_action in on_group.iterfind(TAG_ON_DOCOND):
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
        for recurso in xml_element.iterfind(TAG_RECURSO_CUANTITATIVO):
            rec_obj = ControlmRecursoCuantitativo(recurso.get('NAME'))
            self.recursos_cuantitativos.append(rec_obj)

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
                self.onconditions[condition_value].append(
                    ControlmAction(
                        action_id=action_element.tag,
                        attrs={action_key: action_value for action_key, action_value in action_element.items()}
                    )
                )

        # Fase del job, si es staging|raw|master. TODO: Los APX de qué fase son?
        self.fase: Literal['master', 'staging', 'raw', None] = None
        match self.tipo:

            case 'P' | 'T':
                self.fase = 'staging'

            case 'B' | 'S':
                info_match_dataproc = self.get_info_dataproc_id()
                if info_match_dataproc is not None:
                    if info_match_dataproc['tipo'] == 'dfs' and info_match_dataproc['subtipo'] == 'rmv':
                        # Tenemos que recorrer todas las variables y ver a qué path apuntan
                        for var_value in self.variables.values():
                            if var_value is not None:
                                if '/in/staging/' in var_value:
                                    self.fase = 'staging'
                                    break
                                if '/data/raw/' in var_value:
                                    self.fase = 'raw'
                                    break
                                if '/data/master/' in var_value:
                                    self.fase = 'master'
                                    break

            case 'C':
                info_match_dataproc = self.get_info_dataproc_id()
                if info_match_dataproc is not None:
                    if info_match_dataproc['tipo'] in ['spk', 'biz', 'psp', 'sbx', 'hmm']:
                        # Proceso spark o tablon, es de master (deberia...)
                        self.fase = 'master'
                    if info_match_dataproc['tipo'] == 'krb' and info_match_dataproc['subtipo'].startswith('in'):
                        if info_match_dataproc['subtipo'].endswith('m'):
                            self.fase = 'master'
                        if info_match_dataproc['subtipo'].endswith('r'):
                            self.fase = 'raw'
                        if info_match_dataproc['subtipo'].endswith('s'):
                            self.fase = 'staging'  # TODO: No creo que sea posible, relevar
                    if info_match_dataproc['tipo'] == 'krb' and info_match_dataproc['subtipo'] == 'trn':
                        self.fase = 'master'

            case 'V':
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
                            desc_aux = self.atributos.get('DESCRIPTION').lower()
                            if 'raw' in desc_aux:
                                self.fase = 'raw'
                            elif 'master' in desc_aux:
                                self.fase = 'master'
                            elif 'staging' in desc_aux:
                                self.fase = 'staging'
                    if info_match_dataproc['tipo'] == 'hmm' and info_match_dataproc['subtipo'] == 'trn':
                        self.fase = 'master'

    def __str__(self):
        return self.name

    @property
    def tipo(self) -> str:
        """
        El tipo de un job un caracter que indica qué es lo que debería hacer. Definido por el REGEX_JOBNAME

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

    def esta_desplanificado(self) -> bool:
        try:
            fecha_hasta = self.atributos['ACTIVE_TILL']
        except KeyError:
            return False

        fecha_hasta = date(int(fecha_hasta[:4]), int(fecha_hasta[4:6]), int(fecha_hasta[6:]))

        return fecha_hasta < date.today()

    def expandir_string(self, template: str, iter_actual: int = 1) -> str:
        """
        Reemplaza todas las variables que se encuentran en un string e para ver cómo quedarían resueltas en tiempo de
        ejecución por control M. Ej: "OK JOB %%JOBNAME", reemplazado es "OK JOB AMOLCP0001"

        Si una variable no está definida y no se puede resolver, la reemplazara por CTMERR

        Esto se resuelve de forma recursiva, para evitar recursividad infinita si es que alguien es malo y reemplaza
        una variable con otra vamos a frenarlo en la cantidad maxima de iteraciones permitidas, que viene definido en
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
            print(
                f"WARNING: CANTIDAD MÁXIMA DE ITERACIONES ({iter_actual}) AL EXPANDIR EL STRING [{template}] ALCANZADAS. REVISAR RECURSIVIDAD INFINITA EN LAS VARIABLES DE CONTROL M")

        # El sorted mitiga aquellas variables que pueden estar incluídas en ellas mismas
        # Ejemplo %%MAIL="hola", %%MAIL_2="hola_soyotro"
        # Si el asunto es "Enviando mail a %%MAIL_2", vamos a evitar que se reemplace de la siguiente forma:
        # "Enviando mail a hola_2", que es incorrecto, debería ser "Enviando mail a hola_soyotro"
        for key in sorted(self.variables, key=len, reverse=True):
            template = template.replace(key, Utils.oofstr(self.variables[key]))

        for key in variables_por_defecto:
            template = template.replace(key, variables_por_defecto[key])

        iter_actual += 1
        if '%%' in template and iter_actual <= self.cant_max_iteraciones:
            self.expandir_string(template, iter_actual)

        return template


class ControlmFolder:
    """
    Representacion de una malla de control M que contiene todos los jobs
    """

    def __init__(self, elemento_base: Element, xml_filename: str):
        """
        Constructor

        :param xml_filename: Path al archivo xml donde se encuentra la malla de control m exportada
        """

        self.filename = xml_filename  # TODO: Arreglame loco
        self.name = xml_filename

        match = re.search(REGEX_MALLA, self.name)
        if match is not None:
            self.uuaa = match.group('uuaa')
            self.periodicidad = match.group('periodicidad')
        else:
            raise ValueError(f"No se puede obtener uuaa o periodicidad a partir del nombre malla [{self.name}] en el archivo [{xml_filename}]. Para realizar el analisis es obligatorio que cumpla con el estandar")

        self.jobs: list[ControlmJob] = []
        for job_element in elemento_base.findall(TAG_JOB):
            self.jobs.append(ControlmJob(job_element, self.filename))

        dupes = Utils.encontrar_duplicados([job.name for job in self.jobs])
        if dupes:
            raise ValueError(f"No se puede cargar la informacion de una malla [{self.name}] con jobnames duplicados [{dupes}] en el archivo [{xml_filename}]")

        # Armamos el digrafo de la malla
        self.digrafo = ControlmDigrafo(self.jobs)

    def jobnames(self) -> list[str]:
        """
        Devuelve una lista de jobnames que se encuentran en la malla

        :return: Lista de jobnames
        """
        return [job.name for job in self.jobs]

    def obtener_job(self, jobname_a_buscar: str) -> [ControlmJob, None]:
        """
        Busca y, si encuentra, devuelve el job que se encuentran en la malla

        :param jobname_a_buscar: Jobname a buscar en la mallla
        :return: Retorna el objeto si lo encuentra, None de lo contrario
        """
        job_ret = None

        for job in self.jobs:
            if job.name == jobname_a_buscar:
                job_ret = job

        return job_ret


class ControlmContainer:

    def __init__(self, workspace: Element):

        self.mallas = []
        self._jobs = dict()
        for malla_productiva in workspace.findall('FOLDER'):
            malla_obj = ControlmFolder(malla_productiva, malla_productiva.get('FOLDER_NAME'))
            self.mallas.append(malla_obj)

            for job in malla_obj.jobs:
                self._jobs[job.name] = job

    def get_malla(self, nombre_malla) -> ControlmFolder | None:
        for malla in self.mallas:
            if malla.name == nombre_malla:
                return malla
        return None

    def get_job(self, jobname:str) -> ControlmJob:
        return self._jobs[jobname]  # Para acceso O(1)

    def get_prerequisitos_globales(self) -> dict[str, str]:
        prerequisitos_globales = dict()
        for malla in self.mallas:
            for job in malla.jobs:
                for prereq in job.get_prerequisitos():
                    prerequisitos_globales[job.name] = prereq
        return prerequisitos_globales

    def get_acciones_marca_globales(self) -> dict[str, ControlmMarcaOut]:
        prerequisitos_globales = dict()
        for malla in self.mallas:
            for job in malla.jobs:
                for prereq in job.get_acciones_marcas():
                    prerequisitos_globales[job.name] = prereq
        return prerequisitos_globales


class Recorder:
    """
    Clase que se encarga de logear todos los controles / diferencias que se encuentren entre los dos xml
    """

    def __init__(self) -> None:
        self.info = {
            'INICIAL': [],
            'GENERAL': []
        }

    def add_inicial(self, mensaje: str) -> None:
        """
        Agrega items iniciales al log, son los primeros que se muestran en el log

        :param mensaje: String que repesenta el item a ser agregado, no utilizar \n ya que se lo agrega aca
        """
        item = f"{mensaje}\n"
        self.info['INICIAL'].append(item)

    def add_general(self, mensaje: str) -> None:
        """
        Agrega item general al log, utilizarlos para items que no son puntuales a ningun job pero si a nivel malla.
        Va inmediatamente despues del INICIAL

        :param mensaje: String que repesenta el item a ser agregado, no utilizar \n ya que se lo agrega aca
        """
        item = f"\t{mensaje}\n"
        self.info['GENERAL'].append(item)

    def add_item(self, key: str, mensaje: str) -> None:
        """
        Agrega un ítem asociado a una key, que en este caso es un jobname

        :param key: Key que agrupara todos los items
        :param mensaje: Item a ser agregado
        """
        item = f"\t{mensaje}\n"
        try:
            self.info[key].append(item)
        except KeyError:
            self.info[key] = [item]

    def add_listado(self, key: str, mensaje: str, elementos: [set, list]) -> None:
        """
        Agrega un listado a una key y lo formatea acorde.
        Ej: Si nos viene [A, B, C] con un mensaje 'hola es un mensaje' con una key 'key_emjeplo', se formateara así:
        key_ejemplo
            hola es un mensaje:
                A
                B
                C

        :param key: Key que agrupara todos los items
        :param mensaje: Item a ser agregado
        :param elementos: Lista de elementos que van a estar asociados a una lista
        """

        if not mensaje.endswith(':'):
            mensaje += ':'

        elementos = list(elementos)  # Por si viene un set, que no se pueden acceder por indice
        if len(elementos) == 1:
            mensaje_final = f"\t{mensaje} [{elementos[0]}]"
        else:
            mensaje_final = f"\t{mensaje}"
            for item in elementos:
                mensaje_final += f"\n\t\t[{item}]"
        mensaje_final += '\n'

        try:
            self.info[key].append(mensaje_final)
        except KeyError:
            self.info[key] = [mensaje_final]

    @abc.abstractmethod
    def write_log(self, filename: str, info_extra: dict):
        pass


class ControlRecorder(Recorder):
    """
    Registra todos los eventos notables de un control. Generalmente si algo se registra, es porque está mal.
    """

    # El diccionario listados_generales es una forma de evitar la siguiente situacion: Si tenemos una malla con 400
    # jobs y en 300 de ellos no se encuentra, por ejemplo, un mail de responsable. En vez de que por cada job se informe
    # que no existe la variable con mail de resp, se informa mediante una lista general aquellos jobs que no cumplen con
    # este control, así evitamos 'ensuciar' el log con items innecesarios que por ahí nos hacen perder info más importante.
    #
    # La estructura es la siguiente: 'identificador_control': (mensaje_control, lista_de_jobs_que_no_cumplen_el_control)
    # Esto se usa generalmente para controles que sabemos que van a fallar varios. Idealmente en un futuro esto debería
    # desaparecer(ja).
    listados_generales = {
        'tabla_identificadora': [f"En los siguientes jobs no se encontró la tabla a la cual afectan:", []]
    }

    def add_item_listado_general(self, identificador: str, jobname: str) -> None:
        """
        Agrega un jobname a la lista de un error perteneciente al listado general

        :param identificador:
        :param jobname:
        :return:
        """
        self.listados_generales[identificador][1].append(jobname)

    def write_log(self, filename: str, info_extra: dict) -> None:
        """
        Escribe en un .log todas las controles fallidos. Cada key tiene sus items

        :param filename: Nombre del archivo a generar
        :param info_extra: Diccionario con info extra, en este caso necesitaremos los jobnames nuevos, los modificados y
        los de RC
        """

        rc = info_extra['jobnames_ruta_critica']

        with open(os.path.join("CONTROLES", filename), 'w', encoding='UTF-8') as file:

            # Escribimos los items iniciales
            items_iniciales = self.info.pop('INICIAL')
            for item in items_iniciales:
                file.write(item)

            # Escribimos los items generales, si los hay
            items_generales = self.info.pop('GENERAL')
            if len(items_generales) > 0:
                file.write(f"\nGENERAL\n")
                for item in items_generales:
                    file.write(item)

            value: str | list
            for key, value in self.info.items():
                rc_str = " - (RUTA CRITICA)" if key in rc else ""
                file.write(f"\n{key}{rc_str}\n")
                if isinstance(value, list):
                    for v in value:
                        file.write(v)
                else:
                    file.write(value)

            # Los listados generales van al final
            for listado_general in self.listados_generales.values():
                if listado_general[1]:  # Si hay items en la lista
                    file.write(f"\n{listado_general[0]}\n")
                    for item in listado_general[1]:
                        file.write(f"\t\t{item}\n")
                    file.write('\n')

        self.listados_generales['tabla_identificadora'][1] = []


class Utils:
    """
    Contiene todas las funciones 'utiles' que se usan a lo largo del proceso. Una función últil se considera como tal
    si se presenta algo como código repetido o si se necesita abstraer algo.
    """

    @staticmethod
    def encontrar_duplicados(lista_con_dupes: list[str]) -> list[str]:
        """
        Encuentra los elementos duplicados de una lista

        :param lista_con_dupes: Lista a analizar los duplicados
        :return: Lista con aquellos elementos que se repiten 1 o mas veces
        """

        if len(lista_con_dupes) != len(set(lista_con_dupes)):
            # Hay duplicados, encontrarlos
            dupes = set()
            vistos = set()
            for item in lista_con_dupes:
                if item in vistos:
                    dupes.add(item)
                else:
                    vistos.add(item)
            return list(dupes)
        else:
            return []

    @staticmethod
    def encontrar_nuevos(work: list, live: list[str]) -> list[str]:
        """
        Calcula quellos elementos de work que no estan en live, son considerados nuevos. Se utiliza para jobnames pero
        tambien se puede utilizar con cualquier lista de elementos semejantes.

        Ejemplo:
        work = [A, B, C]
        live = [A, B]
        retorno = [C]

        :param work: Elementos a izquierda a comparar
        :param live: Elementos a derecha a comparar
        :return: Elementos que son únicos en work, es decir, nuevos
        """
        return list(set(work).difference(set(live)))

    @staticmethod
    def encontrar_eliminados(work: list, live: list[str]) -> list[str]:
        """
        Calcula quellos elementos de live que no estan en work, son considerados eliminados. es la negación de la
        funcion encontrar_nuevos

        Ejemplo:
        work = [A, B]
        live = [A, B, C, D]
        retorno = [C, D]

        :param work: Elementos a izquierda a comparar
        :param live: Elementos a derecha a comparar
        :return: Elementos que son únicos en live, es decir, eliminados
        """
        return list(set(live).difference(set(work)))

    @staticmethod
    def remover_duplicados(lista_con_dupes: list[str]) -> list[str]:
        """
        Saca duplicados de una lista, se utiliza la particularidad de que los sets no aceptan duplicados

        :param lista_con_dupes: La lista a remover duplicados
        :return: Lista sin duplicados
        """
        return list(set(lista_con_dupes))

    @staticmethod
    def oofstr(s: str | None) -> str:
        """
        Retorna vacio si el parametro s es None, caso contrario la representación

        :param s: El string a analizar,
        :return str: '' Si es None, caso contrario el string
        """

        return '' if s is None else str(s)


class Control:
    """
    Contenedor de controles a realizar sobre la malla. Existen dos tipos:
        Puntual: Sobre el job de control m(ej: que una marca IN se elimine)
        General: En toda la malla(ej: Que no haya jobnames duplicados)
    """

    @staticmethod
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

        if MAPEO_PERJOBNAME_PERMALLA[info_jobname['periodicidad']] != malla.periodicidad:
            cr.add_item(job.name, f"No coincide la periodicidad del job[{info_jobname['periodicidad']}({MAPEO_PERJOBNAME_PERMALLA[info_jobname['periodicidad']]})], con la de la malla a la que pertenece[{malla.periodicidad}]")

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

            match_dataproc_namespace = re.search(REGEX_DATAPROC_NAMESPACE, Utils.oofstr(var_value))
            if match_dataproc_namespace is not None and match_dataproc_namespace.group('ambiente') == 'dev':
                cr.add_item(job.name, f"Existe un namespace de DESARROLLO [{var_value}] en la variable [{var_key}]")

            if var_key in variables_no_permitidas:
                cr.add_item(job.name, f"La variable [{var_key}] valor [{var_value}] reemplaza la variable %%{variables_no_permitidas[variables_no_permitidas.index(var_key)]} definida y reservada por el sistema, esto no es permitido por el estandar")

            if Utils.oofstr(var_value).strip() == '' and var_key not in variables_vacias_validas:
                cr.add_item(job.name, f"La variable [{var_key}] está vacía")

            #  TODO: Comento porque da muchos falsos positivos, revisar si vale la pena realmente verificar esto
            # if not var_key.isupper():
            #     cr.add_item(job.name, f"La variable [{var_key}] tiene minusculas, no está permitido por el estandar")

        if not existe_tabla:
            cr.add_item_listado_general('tabla_identificadora', job.name)

        # Ahora vamos a validar si el dataproc_job_id del job coincide con la letra que indica el tipo del job. Por
        # ejemplo: si el job es un CP, en su dataproc tiene que haber un -krb-; si el job es un WP, no tiene que tener
        # datapro_job_id, etc. Tenemos que volver a recorrer las variables (no será muy eficiente pero bueh)
        datapros_encontrados = []  # Un job no puede tener dos datapros
        for var_key, var_value in job.variables.items():
            match_dataproc = re.search(REGEX_DATAPROC_JOB_ID, Utils.oofstr(var_value))
            if match_dataproc is not None:
                datapros_encontrados.append(match_dataproc)

        if len(datapros_encontrados) > 1:
            cr.add_listado(job.name, f"Se encontraron [{len(datapros_encontrados)}] dataprocs para un mismo job, revisar si esto es correcto ya que debería estar definido una sola vez", [m.group(0) for m in datapros_encontrados])

        elif len(datapros_encontrados) == 1:

            match_dataproc = datapros_encontrados[0]  # Nos quedamos con el unico encontrado
            discrepancia_datapros = False
            match job.tipo:

                case 'C':
                    if match_dataproc.group('tipo') not in ('krb', 'sbx', 'biz', 'spk', 'psp'):
                        discrepancia_datapros = True

                case 'V':
                    if match_dataproc.group('tipo') == 'spk' and match_dataproc.group('subtipo') != 'qlt':
                        discrepancia_datapros = True
                    elif match_dataproc.group('tipo') != 'hmm' and match_dataproc.group('subtipo') == 'trn':
                        discrepancia_datapros = True

                case 'S' | 'B':
                    if match_dataproc.group('subtipo') != 'rmv':
                        discrepancia_datapros = True

                case 'W' | 'T' | 'P':
                    cr.add_item(job.name, f"El job es [{job.tipo_descripcion}] y se encontró un dataproc en el mismo [{match_dataproc.group(0)}], no debería tenerlo por su tipo")

                case _:
                    cr.add_item(job.name, f"No se pudo controlar el dataproc del Job [{match_dataproc.group(0)}] debido a que tiene un tipo desconocido [{job.tipo}]")

            if discrepancia_datapros:
                mensaje = f"Segun su tipo [{job.tipo}], el job es [{job.tipo_descripcion}] pero esto no se ve reflejado su dataproc job id [{match_dataproc.group(0)}]"
                cr.add_item(job.name, mensaje)

        # Validamos que todas las variables declaradas estén en uso. Una variable se puede usar en el asunto de un
        # mail, en el command o en otras variables. Las volvermos a recorrer
        for var_key in job.variables.keys():

            variable_usada = False

            # buscamos el uso en otras variables
            for var_value in job.variables.values():
                if (var_value is not None and var_key in var_value) or not Utils.oofstr(var_value).startswith('t_'):  # Las variables de table no se usan
                    variable_usada = True

            # En el command
            try:
                if var_key in job.atributos['CMDLINE']:
                    variable_usada = True
            except KeyError:
                pass  # Si no tiene command, no pasa nada

            # En la descripcion, aunque no se resuelten en tiempo de ejecucion, les damos un changüí
            if var_key in job.atributos['DESCRIPTION']:
                variable_usada = True

            # En los mails que se envían
            for oncondition in job.onconditions:
                for action in job.onconditions[oncondition]:
                    if action.id == 'DOMAIL' and any([var_key in atr for atr in action.attrs.values()]):
                        variable_usada = True

            if not variable_usada:
                cr.add_item(job.name, f"La variable [{var_key}] valor [{job.variables[var_key]}] está declarada pero no está siendo usada")

    @staticmethod
    def marcas_in(job: ControlmJob, malla: ControlmFolder, cr: ControlRecorder):

        info_jobname = job.get_info_jobname()

        duplis = Utils.encontrar_duplicados(job.get_prerequisitos())
        if duplis:
            cr.add_item(job.name, f"Existen marcas IN duplicadas: {duplis}")

        for marca in job.marcasin:

            if not marca.es_valida():
                cr.add_item(job.name, f"La marca IN [{str(marca)}] está mal formada")
                continue

            if marca.destino != job.name:
                cr.add_item(job.name, f"Para la marca IN [{str(marca)}] no coincide el job de DESTINO [{marca.destino}] con el que pertenece [{job.name}]")

            info_jobname_origen = marca.get_info_origen()
            if (
                    marca.origen not in malla.jobnames() and
                    info_jobname_origen['uuaa'] == malla.uuaa and
                    info_jobname_origen['periodicidad'] != info_jobname['periodicidad']
            ):
                cr.add_item(job.name, f"El job de ORIGEN [{marca.origen}] de la marca IN [{marca.name}] no se encuentra en la malla y no pertenece a otra malla")

    @staticmethod
    def marcas_out(job: ControlmJob, malla: ControlmFolder, cr: ControlRecorder):

        info_jobname = job.get_info_jobname()

        duplis = Utils.encontrar_duplicados(job.get_prerequisitos())
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
                cr.add_item(job.name, f"La marca IN [{str(marca_in)}] no se elimina")

    @staticmethod
    def _subcontrol_mail(job: ControlmJob, action: ControlmAction, code: str, malla: ControlmFolder, reglas: dict, cr: ControlRecorder):
        """
        Sub control para cuando llega una accion DOMAIL. es OBLIGATORIO cuando termina OK y cuando termina NOTOK

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

            if re.search(REGEX_MAILS, destinatario) is None:
                cr.add_item(job.name, f"El mail del receptor cuando termina [{code}] es [{destinatario}], no parece ser un mail válido")

        try:
            destinatario_cc = action.attrs['CC_DEST']
        except KeyError:
            # Realmente no tenemos que hacer nada si el mail viene sin CC, ya que no es un requisito obligatorio
            pass
        else:
            if '%%' in destinatario_cc:
                destinatario_cc = job.expandir_string(destinatario_cc)

            if destinatario_cc is None or re.search(REGEX_MAILS, destinatario_cc) is None:
                cr.add_item(job.name, f"El mail de CC cuando termina [{code}] es [{destinatario_cc}], no parece ser un mail válido")

        if action.attrs['ATTACH_SYSOUT'] != 'Y' and action.attrs['ATTACH_SYSOUT'] != 'D':
            cr.add_item(job.name, f"El mail de CC cuando termina [{code}] no adjunta su SYSOUT")

        try:
            asunto = action.attrs['SUBJECT']
        except KeyError:
            cr.add_item(job.name, f"El mail cuando termina [{code}] no tiene asunto")
        else:
            if '%%' in asunto:
                asunto = job.expandir_string(asunto)

                if len(asunto) > 99:
                    cr.add_item(job.name, f"El mail cuando termina [{code}] no se enviará debido a que supera los 100 caracteres. Valor obtenido: [{asunto}]")

            if '%%JOBNAME' not in asunto and job.name not in asunto:
                cr.add_item(job.name, f"El mail cuando termina [{code}] no informa el %%JOBNAME en el asunto, que es [{asunto}]")

                cuerpo = action.attrs.get('MESSAGE')
                if cuerpo is None:
                    cr.add_item(job.name, f"El mail cuando termina [{code}] no tiene un mensaje en su cuerpo.")
                elif '%%JOBNAME' not in cuerpo and job.name not in cuerpo:
                    cr.add_item(job.name, f"El mail cuando termina [{code}] TAMPOCO informa el %%JOBNAME en el cuerpo, que es [{cuerpo}]... media pila loco >:(")

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

    @staticmethod
    def _subcontrol_cond(job: ControlmJob, action: ControlmAction, code: str, malla: ControlmFolder, reglas: dict, cr: ControlRecorder):

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

    @staticmethod
    def _subcontrol_doaction(job: ControlmJob, action: ControlmAction, code: str, malla: ControlmFolder, reglas: dict, cr: ControlRecorder):

        if code == '*{"id":"SUCCESS","name":"SUCCESS"}*' and action.attrs['ACTION'] != 'OK':
            cr.add_item(job.name, f"El job no se setea OK cuando termina con código [{code}]")

        if job.es_filewatcher():

            if code == 'COMPSTAT EQ 0' and action.attrs['ACTION'] == 'SPCYC':
                reglas['fw_stop_cyclic_code0'][0] = True

            if code == 'NOTOK' and action.attrs['ACTION'] == 'SPCYC':
                reglas['fw_stop_cyclic_notok'][0] = True

    @staticmethod
    def _subcontrol_forcejob(job: ControlmJob, action: ControlmAction, code: str, malla: ControlmFolder, reglas: dict, cr: ControlRecorder):

        intro = f"Bajo la condicion [{code}]"

        if action.attrs['TABLE_NAME'] != malla.name:
            cr.add_item(job.name, f"{intro}, el job ordena con force a otro job de otra malla [{action.attrs['TABLE_NAME']}]")

        if action.attrs['NAME'] not in malla.jobnames():
            cr.add_item(job.name, f"{intro}, el job ordena con force a otro job [{action.attrs['NAME']}] que no existe en la malla [{malla.name}]")

        if action.attrs['ODATE'] != 'ODAT':
            cr.add_item(job.name, f"{intro}, el job ordena con force a otro [{action.attrs['NAME']}] con un ODATE distinto al permitido por el estandar [{action.attrs['ODATE']}]")

    @staticmethod
    def _subcontrol_doshout(job: ControlmJob, action: ControlmAction, code: str, malla: ControlmFolder, reglas: dict, cr: ControlRecorder):

        # Solo verificar el doshout si es de RC, los otros casos no se contemplan
        if job.es_ruta_critica():

            reglas['rc_doshout'][0] = True

            if code != 'NOTOK':
                cr.add_item(job.name, f"El job es de RC y está enviando un alertamiento cuando finaliza [{code}], el alertamiento corresponde cuando termina [NOT OK]")

            if action.attrs['URGENCY'] == 'U':
                reglas['rc_doshout_urgente'][0] = True

            if action.attrs['MESSAGE'] is not None:
                mensaje_correcto = "Ruta Critica, escalar a Aplicativo"
                coeficiente_diferencia = SequenceMatcher(a=mensaje_correcto, b=action.attrs['MESSAGE']).ratio()

                if coeficiente_diferencia < 0.85:
                    cr.add_item(job.name, f"El job es de RC y el mensaje de su alertamiento no es el correcto [{action.attrs['MESSAGE']}], debería ser [{mensaje_correcto}]")

    @staticmethod
    def acciones(job: ControlmJob, malla: ControlmFolder, cr: ControlRecorder):
        """
        Para controlar las acciones primero hay que ver bajo qué criterio están agrupadas. Este critero se conoce como
        código(o CODE) dentro del xml. A lo que me refiero es: Bajo el código NOTOK pueden haber varias acciones
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
            'DOMAIL': Control._subcontrol_mail,
            'DOCOND': Control._subcontrol_cond,
            'DOACTION': Control._subcontrol_doaction,
            'DOFORCEJOB': Control._subcontrol_forcejob,
            'DOSHOUT': Control._subcontrol_doshout
        }

        for condicion, acciones in job.onconditions.items():
            for accion in acciones:
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

    @staticmethod
    def recursos_cuantitativos(job: ControlmJob, malla: ControlmFolder, cr: ControlRecorder):

        generico_encontrado = False
        rrcc_stg_correcto = True

        if job.es_tpt() or job.es_transmisiontp() or job.es_filewatcher():
            rrcc_stg_correcto = False

        for recurso in job.recursos_cuantitativos:

            if recurso.name == 'ARD':
                generico_encontrado = True

            if (job.es_tpt() or job.es_transmisiontp() or job.es_filewatcher()) and recurso.name == 'ARD-STG':
                rrcc_stg_correcto = True

            r: str
            if not all([r.isupper() or r.isalnum() for r in recurso.seccionar()]):
                cr.add_item(job.name, f"El recurso [{recurso.name}] no parece seguir el estandar defindo (caracteres o 'forma' no permitidos)")

        if not generico_encontrado:
            cr.add_item(job.name, f"No se encuentra el recurso cuantitativo por defecto ARD")

        if not rrcc_stg_correcto:
            cr.add_item(job.name, f"El job es [{job.tipo}P] ({job.tipo_descripcion}) y no se encuentra el recurso cuantitativo ARD-STG")

    @staticmethod
    def cadenas(malla: ControlmFolder, cr: ControlRecorder):
        """
        Realiza controles sobre todas las cadenas de jobs que componen a la malla

        :param malla: Malla que contiene el job
        :param cr: Recorder que se encargará de guardar los controles fallidos
        """

        recorder_key = "ANALISIS DE CADENAS"

        for job_raiz in malla.digrafo.raices():
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
            cadena = malla.digrafo.recorrer_cadena(job_raiz)
            for jobname in cadena:
                job = malla.obtener_job(jobname)
                if job.tipo in ['T', 'P', 'C'] and job.fase is not None:
                    contador_instancias_ingesta[job.fase] += 1
                if job.tipo in ['S'] and job.fase is not None:
                    contador_instancias_borradosm[job.fase] += 1

            for fase in contador_instancias_ingesta.keys():
                if contador_instancias_ingesta[fase] > contador_instancias_borradosm[fase]:
                    diferencia = contador_instancias_ingesta[fase] - contador_instancias_borradosm[fase]
                    mensaje = f"Para la cadena {cadena}, existen más jobs de ingesta en {fase} [{contador_instancias_ingesta[fase]}] que smart cleaners de {fase} [{contador_instancias_borradosm[fase]}]. Faltarían [{diferencia}] SP's de {fase}"
                    cr.add_item(recorder_key, mensaje)

    @staticmethod
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

    @staticmethod
    def global_marcas(cont: ControlmContainer):
        pass


if __name__ == '__main__':

    path = Path()
    files = [file for file in path.iterdir() if file.name.endswith('.xml')]
    if len(files) > 1 or len(files) == 0:
        raise Exception(f"Asegurarse de que exista solamente 1 xml en el directorio de trabajo")
    else:
        xml_prod = str(files[0])
    base = parse(xml_prod).getroot()

    print("Cargando xml...")
    contenedor = ControlmContainer(base)
    print("...xml cargado")

    # Con global no me refuero a uuaas globales, sino que cosas a nivel xml entero y no puntualmente sobre cada malla
    print("Generando digrafo global")
    jobs_global = []
    for malla_global in contenedor.mallas:
        jobs_global.extend([job for job in malla_global.jobs])
    digrafo_global = ControlmDigrafo(jobs_global)
    print("Digrafo global generado")

    print("Escribiendo archivos cadenas globales")
    with (open(f"cadenas_global_nomina.csv", 'w', newline='', encoding='utf-8') as f_nomina,
          open(f"cadenas_global_indice.csv", 'w', newline='', encoding='utf-8') as f_indice):

        csv_writer_cadena_global_nomina = csv.writer(f_nomina)
        csv_writer_cadena_global_nomina.writerow(["ID_CADENA", "JOBNAME", "MALLA", "FASE", "DATAPROC"])

        csv_writer_cadena_global_indice = csv.writer(f_indice)
        csv_writer_cadena_global_indice.writerow(["ID_CADENA", "JOBS", "CANT_JOBS"])

        for index, cadena in enumerate(digrafo_global.obtener_arboles()):

            cadena_id = str(index).zfill(3)
            for jobname in cadena:
                job = contenedor.get_job(jobname)
                csv_writer_cadena_global_nomina.writerow([cadena_id, job.name, job.atributos['PARENT_FOLDER'], Utils.oofstr(job.fase), job.dataproc_id])

            csv_writer_cadena_global_indice.writerow([cadena_id, "|".join([jobname for jobname in cadena]), len(cadena)])
    print("Archivos cadenas globales escritas")