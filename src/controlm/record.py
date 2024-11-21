"""Clases que se encargan de logear... cosas"""

from abc import abstractmethod
from copy import deepcopy


class Recorder:
    """
    Clase que se encarga de logear todos los controles / diferencias que se encuentren entre los dos xml
    """

    INI_KEY = 'INICIAL'
    GEN_KEY = 'GENERAL'

    def __init__(self):
        self.info = dict()

    def _add_or_append_dict_item(self, key: str, item: tuple[str, list[str] | None]):
        try:
            self.info[key].append(item)
        except KeyError:
            self.info[key] = [item]

    def add_inicial(self, mensaje: str) -> None:
        """
        Agrega items iniciales al log, son los primeros que se muestran

        :param mensaje: String que repesenta el item a ser agregado, no utilizar \n ya que se lo agrega aca
        """
        self._add_or_append_dict_item(self.INI_KEY, (mensaje, None))

    def add_general(self, mensaje: str) -> None:
        """
        Agrega item general al log, utilizarlos para items que no son puntuales a ningun job pero si a nivel malla.
        Va inmediatamente despues del INICIAL

        :param mensaje: String que repesenta el item a ser agregado
        """
        self._add_or_append_dict_item(self.GEN_KEY, (mensaje, None))

    def add_item(self, key: str, mensaje: str) -> None:
        """
        Agrega un ítem asociado a una key, que en este caso es un jobname

        :param key: Key que agrupara todos los items
        :param mensaje: Item a ser agregado
        """
        if key in [Recorder.INI_KEY, Recorder.GEN_KEY]:
            raise KeyError(f"No se puede agregar un item cuya key está dentro de las no permitidas {[Recorder.INI_KEY, Recorder.GEN_KEY]}")
        else:
            self._add_or_append_dict_item(key, (mensaje, None))

    def add_listado(self, key: str, mensaje: str, elementos: [set, list]) -> None:
        """
        Agrega un listado a una key y lo formatea acorde.
        Ej: Si nos viene [A, B, C] con un mensaje 'Los siguientes id fallaron' con una key 'key_emjeplo', se formateara
        así:

        key_ejemplo
            Los siguientes id fallaron:
                A
                B
                C

        :param key: Key que agrupara todos los items
        :param mensaje: Item a ser agregado
        :param elementos: Lista de elementos que van a estar asociados a un mensaje
        """
        if isinstance(elementos, set):
            elementos = list(elementos)  # Por si viene un set, que no se pueden acceder por indice
        self._add_or_append_dict_item(key, (mensaje, elementos))

    @abstractmethod
    def write_log(self, filename: str, info_extra: dict):
        pass


class DiffRecorder(Recorder):
    """
    Registra todas las diferencias encontradas por el proceso en un .log
    TODO: Con el ultimo refactor de la clase padre se va a romper, arreglar
    """

    def add_diff(self, key: str, mensaje: str, work_val: str, live_val: str) -> None:
        """
        Agrega al listado de diferencias un valor que se modificó asociado a una key

        :param key: Key a la cual estará asociado el item
        :param mensaje: Mensaje asociado a la key
        :param work_val: Valor productivo
        :param live_val: Valor de work, diferente al productivo
        """
        item = f"\t{mensaje}\n\t\tACTUAL:[{live_val}]\n\t\tNUEVO: [{work_val}]\n"
        try:
            self.info[key].append(item)
        except KeyError:
            self.info[key] = [item]

    def write_log(self, filename: str, info_extra: dict) -> None:
        """
        Escribe en un .log todas las diferencias encontradas. Por cada key tiene sus items

        :param filename: Nombre del archivo a generar
        :param info_extra: Argumentos extra, en este caso necesitaremos aquellos jobnames que son de Ruta Crítica
        """

        jobnames_rc = info_extra['jobnames_ruta_critica']

        with open(filename, 'w', encoding='UTF-8') as file:

            items_iniciales = self.info.pop('INICIAL')
            for item in items_iniciales:
                file.write(item)

            items_generales = self.info.pop('GENERAL')
            if len(items_generales) > 0:
                file.write(f"\nGENERAL\n")
                for item in items_generales:
                    file.write(item)

            value: list | str
            for key, value in self.info.items():
                rc_str = " - (RUTA CRITICA)" if key in jobnames_rc else ""
                file.write(f"\n{key}{rc_str}\n")
                if isinstance(value, list):
                    for v in value:
                        file.write(v)
                else:
                    file.write(value)

            if len(self.info) == 0:
                file.write("\nNo se detectaron diferencias puntuales en los jobs\n")


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
        'tabla_identificadora': (f"En los siguientes jobs no se encontró la tabla a la cual afectan:", [])
    }

    def add_item_listado_general(self, identificador: str, jobname: str):
        """
        Agrega un jobname a la lista de un error perteneciente al listado general

        :param identificador:
        :param jobname:
        :return:
        """
        self.listados_generales[identificador][1].append(jobname)

    def _hay_errores(self):
        return len(self.info.keys()) > 1

    def write_log(self, filename: str, info_extra: dict):
        """
        Escribe en un .log todas las controles fallidos. Cada key tiene sus items.

        :param filename: Nombre del archivo a generar
        :param info_extra: Diccionario con info extra, en este caso necesitaremos los jobnames nuevos, los modificados y
        los de RC
        """

        nuevos = info_extra.get('jobnames_nuevos', '')
        modificados = info_extra.get('jobnames_modificados', '')
        rc = info_extra.get('jobnames_ruta_critica', '')

        with open(filename, 'w', encoding='UTF-8') as file:
            file.write(self._generate_log({'jobnames_ruta_critica': rc}))  # FIXME: Enserio ?

    def _generate_log(self, info_extra: dict) -> str:
        """
        Genera un string para que luego sea escrito en un archivo txt
        """

        info = deepcopy(self.info)

        jobnames_rc = info_extra.get('jobnames_ruta_critica', '')

        final_str = ""

        item_ini_list: list | None = info.pop(self.INI_KEY, None)
        if item_ini_list is not None:
            for item in item_ini_list:
                final_str += f'{item[0]}\n'
        final_str += '\n'

        if not self._hay_errores():
            final_str += f'No se encontraron errores en la malla.\n'
            return final_str
        else:
            final_str += f'La malla contiene los siguientes errores:\n\n'

        item_gen_list: list | None = info.pop(self.GEN_KEY, None)
        if item_gen_list is not None:
            final_str += f'{self.GEN_KEY}\n'
            for item in item_gen_list:
                final_str += f'\t{item[0]}\n'
        final_str += '\n'

        for jobname, item_list in info.items():
            rc_str = " - (RUTA CRITICA)" if jobname in jobnames_rc else ""
            final_str += f'{jobname}{rc_str}\n'
            for item in item_list:
                if item[1] is None:
                    final_str += f'\t{item[0]}\n'
                else:
                    final_str += f'\t{item[0]}\n'
                    for sub_item in item[1]:
                        final_str += f'\t\t{sub_item}\n'
            final_str += '\n'

        return final_str

    def generate_html(self, info_extra: dict) -> str:
        """
        Genera un string html que representan los logs pero formateados lindo, se verá reflejado en el front del
        validador
        """

        info = deepcopy(self.info)

        control_html = '<META http-equiv="Content-Type" content="text/html; charset=UTF-8">'

        jobnames_rc = info_extra.get('jobnames_ruta_critica', '')
        malla_nombre = info_extra.get('malla_nombre', '')

        info.pop(self.INI_KEY, None)

        if not self._hay_errores():
            control_html += f'<p><span style="background-color:#8FD14F; font-size: 15px;"><strong>No se encontraron errores en la malla {malla_nombre}.</strong></span></p>'
            return control_html
        else:
            control_html += f'<p><span style="background-color:#F24726; color: white; font-size: 15px;"><strong>La malla {malla_nombre} contiene los siguientes errores:</strong></span></p>'

        item_gen_list: list | None = info.pop(self.GEN_KEY, None)
        if item_gen_list is not None:
            control_html += f'<p>{self.GEN_KEY}</p>'
            control_html += f'<ul>'
            for item in item_gen_list:
                control_html += f'<li>{item[0]}</li>'
            control_html += f'</ul>'
            control_html += f'<br>'

        for jobname, item_list in info.items():
            rc_str = " - (RUTA CRITICA)" if jobname in jobnames_rc else ""
            control_html += f'<p>{jobname}{rc_str}</p>'
            control_html += f'<ul>'
            for item in item_list:
                if item[1] is None:
                    control_html += f'<li><span style="color: #E1AD01;"><strong>WARNING: </strong></span>{item[0]}</li>'
                    # control_html += f'<li><span style="color: RED;"><strong>ERROR: </strong></span>{item[0]}</li>'
                else:
                    control_html += f'<li>{item[0]}</li>'
                    control_html += f'<ul>'
                    for sub_item in item[1]:
                        control_html += f'<li>{sub_item}</li>'
                    control_html += f'</ul>'
            control_html += f'</ul>'
            control_html += f'<br>'

        return control_html


class RecorderTmp:
    """
    Clase que engloba y registra las validaciones sobre una malla temporal, escribe dichas validaciones en un archivo .log
    """

    def __init__(self) -> None:
        self.info = {
            'INICIAL': [],
            'GENERAL': []
        }

    def add_inicial(self, mensaje: str) -> None:
        mensaje += '\n'
        self.info['INICIAL'].append(mensaje)

    def add_general(self, mensaje: str) -> None:
        mensaje += '\n'
        self.info['GENERAL'].append('\t' + mensaje)

    def add_item(self, key: str, mensaje: str) -> None:
        mensaje = f"\t{mensaje}\n"
        try:
            self.info[key].append(mensaje)
        except KeyError:
            self.info[key] = [mensaje]

    def add_listado(self, key: str, mensaje: str, items: set | list) -> None:
        items = list(items)  # Por si viene un set, que no se pueden acceder por indice
        if len(items) == 1:
            mensaje_final = f"\t{mensaje}: [{items[0]}]"
        else:
            mensaje_final = f"\t{mensaje}"
            for item in items:
                mensaje_final += f"\n\t\t[{item}]"
        try:
            self.info[key].append(mensaje_final + '\n')
        except KeyError:
            self.info[key] = [mensaje_final + '\n']

    def write_log(self, filename: str) -> None:
        """Escribe en un .log todos los controles"""

        with open(filename, 'w', encoding='UTF-8') as file:

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
                file.write(f"\n{key}\n")
                if isinstance(value, list):
                    for v in value:
                        file.write(v)
                else:
                    file.write(value)

            if len(self.info) == 0:
                file.write("No se detectaron errores\n")
