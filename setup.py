from cx_Freeze import setup, Executable


executables = [Executable("Sources/main.py", target_name="generador_aut.exe", base="Win32GUI", icon="Sources/imagen/bbva.ico")]

buildOptions = {
    'packages': ['pandas', 'tkcalendar', 'collections', 'requests', 'pickle', 'controlm.structures','controlm'],
    'excludes': [],
    'include_files': [
        ('Sources/imagen/bbva.ico', 'Sources/imagen/bbva.ico'),
        ('Sources/imagen/logo.png', 'Sources/imagen/logo.png'),
        ('Sources/imagen/logo_2.png', 'Sources/imagen/logo_2.png'),
    ]
}

setup(
    name="Generador Automático",
    version="0.1",
    description="Generador de reliability",
    options={'build_exe': buildOptions},
    executables=executables
)
