# TODO: USAR ENUM


class Carpetas:
    """
    Nombres de carpetas donde se encuentran los archivos a comparar
    """

    LIVE_FOLDERNAME = 'MALLA_PRODUCTIVA'
    WORK_FOLDERNAME = 'MALLA_AMBIENTADA'


class TagXml:
    DEFTABLE = 'DEFTABLE'
    FOLDER = 'FOLDER'
    JOB = 'JOB'
    JOB_NAME = 'JOBNAME'
    NOMBRE_MALLA = 'FOLDER_NAME'
    MARCA_IN = 'INCOND'
    MARCA_OUT = 'OUTCOND'
    ON_CONDITION = 'ON'
    RECURSO_CUANTITATIVO = 'QUANTITATIVE'
    ON_DOCOND = 'DOCOND'


class Regex:
    DATAPROC_NAMESPACE = r'(?P<pais>\w{2})\.(?P<uuaa>k?[a-z0-9]{3,4})\.app-id-(?P<id>\d+.)\.(?P<ambiente>(dev|pro))'
    DATAPROC_JOB_ID = r'(?P<uuaa>k?[a-z0-9]{3,4})-(?P<pais>\w{2})-(?P<tipo>\w{3,4})-(?P<subtipo>\w{3,4})-(?P<nombre>.*)-(?P<nro>\d+)'
    MALLA = r'^CR-AR(?P<uuaa>K?[A-Z0-9]{3,4})(?P<periodicidad>[A-Z]{3})-[TK]02$'
    MALLA_TMP = r'^CR-AR(?P<uuaa>K?[A-Z0-9]{3,4})(?P<periodicidad>TMP)-[TK](?!02)\d{2}$'
    APPLICATION = r'^(?P<uuaa>K?[A-Z0-9]{3,4})-(?P<pais>[A-Z]{2})-(?P<app>[A-Z0-9]+)$'
    JOBNAME = r'^(?P<pais>[A-Z])(?P<uuaa>K?[A-Z0-9]{3,4})(?P<tipo>[NERDTCWAVMBPGSDL])(?P<entorno>[PBDTCM])(?P<periodicidad>\d)[0-9A-Z]{3}$'
    MAILS = r'[^@ \t\r\n]+@[^@ \t\r\n]+\.[^@ \t\r\n]+'
    TABLA = r'^t_(?P<uuaa>k?[a-z0-9]{3,4})_.+$'


class Limits:
    MAX_JOBS_TMP = 30


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

# Este diccionario es una correspondencia entre el dígito de periodicidad de un jobname y la periodicidad de una malla
# se formó en base al manual de estandares de control m. Hay más pero por lo que veo solo se usan estos
MAPEO_PERJOBNAME_PERMALLA = {
    '0': 'DIA',
    '4': 'MEN',
    '9': 'EVE'
}

CONTACTO = 'ar-data-hub-solutions.group@bbva.com'

# TODO: Estas son variables, que algunos jobs las dejan vacías. No es un error y no tengo idea del proceso
#   que ejecutan, pero las voy a hardcodear hasta que se comprenda bien por qué pueden ir vacías.
VARIABLES_VACIAS_VALIDAS = [
    'FORMATO_UNO',
    'FORMATO_DOS',
    'CARPETA_SIN_FECHA',
    'PRIMERA_PARTE_CARPETA_SIN_FECHA',
    'SEGUNDA_PARTE_CARPETA_SIN_FECHA'
]

# Nombres reservados no permitidos por el estandar, ver https://ctm.bancolombia.com/help/CTMHelp/en-US/Documentation/Variables.htm
VARIABLES_NO_PERMITIDAS = [
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

DOCUMENTACION_VALIDADOR_URL = 'https://docs.google.com/document/d/1GDNQf1aOZrfZfQm70cF0abeJX4FGS70NVKDIayMB6g4/edit?usp=sharing'
