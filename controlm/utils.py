"""
Contiene todas las funciones 'utiles' que se usan a lo largo del proceso. Una función últil se considera como tal
si se presenta algo como código repetido o si se necesita abstraer algo.
"""

from controlm.constantes import Carpetas

from pathlib import Path


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


def remover_duplicados(lista_con_dupes: list[str]) -> list[str]:
    """
    Saca duplicados de una lista, se utiliza la particularidad de que los sets no aceptan duplicados

    :param lista_con_dupes: La lista a remover duplicados
    :return: Lista sin duplicados
    """
    return list(set(lista_con_dupes))


def obtener_xmlpath(carpeta: str) -> str | None:
    """
    Dada una carpeta, obtiene el path del archivo xml para leer, controla que haya uno solo. El path no es absoluto,
    es relativo al path de donde se ejecute el script. Si hay xml, debe ser único

    :param carpeta: String que representa la carpeta donde se buscara el archivo xml
    :return: Un string que representa el path al archivo xml, None en caso de no encontrarlo
    """

    p = Path(carpeta)
    files = [x for x in p.rglob('*.xml')]
    if len(files) > 1:
        raise Exception(f"Asegurarse de que exista solamente 1 xml en la carpeta de {Carpetas.WORK_FOLDERNAME}")
    elif len(files) == 0:
        xml_filename = None
    else:
        xml_filename = str(files[0])

    return xml_filename


def oofstr(s: str | None) -> str:
    """
    Retorna un string vacio si el parametro s es None, caso contrario la representación

    :param s: El string a analizar,
    :return str: '' Si es None, caso contrario el string
    """

    return '' if s is None else str(s)


class Secuencia:
    """
    Clase generadora de identificador único de jobname, genera caracteres del 000 al 999 y luego de A00 a Z99
    """

    def __init__(self):
        self.current = 0
        self.letter = 0
        self.number = 1

    def obtener_nmnemoc(self):
        nmne = self._generar_mnemoc()
        if nmne == 'Z99':
            return 'noo'
        return nmne

    def _generar_mnemoc(self):
        # Generate numbers from 000 to 999
        if self.current < 1000:
            ret_str = f"{self.current:03}"
            self.current += 1
            return ret_str
        else:
            # Generate letters A to Z followed by 01 to 99
            ret_str = f"{chr(65 + self.letter)}{self.number:02}"
            self.number += 1

            if self.number > 99:
                self.number = 1
                self.letter += 1

            return ret_str
