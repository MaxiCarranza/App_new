from cx_Freeze import setup, Executable


executables = [
    Executable("main_qt.py", target_name="validador.exe", base="Win32GUI", icon="src/resources/img/bbva.ico"),

]

buildOptions = {
    'packages': ['tkcalendar', 'requests', 'PySide6', 'src.controlm'],
    'excludes': [],
    'include_files': [
        ('src/resources/img/bbva.ico', 'src/resources/img/bbva.ico'),
        ('src/resources/img/logo.png', 'src/resources/img/logo.png'),
        ('src/resources/img/logo_2.png', 'src/resources/img/logo_2.png'),
        ('src/resources/img/im_bbva.png', 'src/resources/img/im_bbva.png'),
        ('src/resources/img/help.png', 'src/resources/img/help.png'),
        ('src/resources/fechas_nolaborables.json', 'src/fechas_nolaborables.json')
    ]
}

setup(
    name="Validador de mallas",
    version="0.1",
    description="Validador de mallas Reliability - DataHub",
    options={'build_exe': buildOptions},
    executables=executables
)
