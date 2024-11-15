"""Clases que se encargan de logear... cosas"""

from abc import abstractmethod


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
        Ej: Si nos viene [A, B, C] con un mensaje 'Los siguientes id fallaron' con una key 'key_emjeplo', se formateara así:

        key_ejemplo
            Los siguientes id fallaron:
                A
                B
                C

        :param key: Key que agrupara todos los items
        :param mensaje: Item a ser agregado
        :param elementos: Lista de elementos que van a estar asociados a un mensaje
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

    @abstractmethod
    def write_log(self, filename: str, info_extra: dict):
        pass


class DiffRecorder(Recorder):
    """
    Registra todas las diferencias encontradas por el proceso en un .log
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

            # Escribimos los items iniciales
            items_iniciales = self.info.pop('INICIAL')
            for item in items_iniciales:
                file.write(item)

            # Escribimos los items generales, si los hay
            try:
                items_generales = self.info.pop('GENERAL')
            except KeyError:
                pass
            else:
                if len(items_generales) > 0:
                    file.write(f"\nGENERAL\n")
                    for item in items_generales:
                        file.write(item)

            value: str | list
            for key, value in self.info.items():
                nuevo_str = " (NUEVO)" if key in nuevos else ""
                modif_str = " (MODIFICADO)" if key in modificados else ""
                rc_str = " - (RUTA CRITICA)" if key in rc else ""
                file.write(f"\n{key}{nuevo_str}{modif_str}{rc_str}\n")
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

            if len(self.info) == 0:
                file.write("No se detectaron errores\n")

    def generate_log(self, info_extra: dict):
        """
        """

        nuevos = info_extra.get('jobnames_nuevos', '')
        modificados = info_extra.get('jobnames_modificados', '')
        rc = info_extra.get('jobnames_ruta_critica', '')

        final_str = ""

        # # Escribimos los items iniciales
        # items_iniciales = self.info.pop('INICIAL')
        # for item in items_iniciales:
        #     final_str += item

        # Escribimos los items generales, si los hay
        items_generales = self.info.pop('GENERAL')
        if len(items_generales) > 0:
            final_str += f"\nGENERAL\n"
            for item in items_generales:
                final_str += item

        value: str | list
        for key, value in self.info.items():
            nuevo_str = " (NUEVO)" if key in nuevos else ""
            modif_str = " (MODIFICADO)" if key in modificados else ""
            rc_str = " - (RUTA CRITICA)" if key in rc else ""
            final_str += f"\n{key}{nuevo_str}{modif_str}{rc_str}\n"
            if isinstance(value, list):
                for v in value:
                    final_str += v
            else:
                final_str += value

        # Los listados generales van al final
        for listado_general in self.listados_generales.values():
            if listado_general[1]:  # Si hay items en la lista
                final_str += f"\n{listado_general[0]}\n"
                for item in listado_general[1]:
                    final_str += f"\t\t{item}\n"
                final_str += '\n'

        if len(self.info) == 0:
            final_str += "No se detectaron errores\n"

        return final_str


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
