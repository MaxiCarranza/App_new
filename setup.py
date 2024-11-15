from cx_Freeze import setup, Executable


executables = [Executable("main.py", target_name="generador_aut.exe", base="Win32GUI", icon="src/img/bbva.ico")]

buildOptions = {
    'packages': ['tkcalendar', 'collections', 'requests', 'controlm.structures','controlm'],
    'excludes': [],
    'include_files': [
        ('src/img/bbva.ico', 'src/img/bbva.ico'),
        ('src/img/logo.png', 'src/img/logo.png'),
        ('src/img/logo_2.png', 'src/img/logo_2.png'),
        ('src/img/im_bbva.png', 'src/img/im_bbva.png'),
        ('src/fechas_nolaborables.json', 'src/fechas_nolaborables.json')
    ]
}

setup(
    name="Generador Automático",
    version="0.1",
    description="Generador de reliability",
    options={'build_exe': buildOptions},
    executables=executables
)
