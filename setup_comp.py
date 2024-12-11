from cx_Freeze import setup, Executable
from PySide6.QtCore import QLibraryInfo
import sys

qt_platforms_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)

executables = [
    Executable(
        "main_comp.py",
        target_name="comparador.exe",
        base="Win32GUI" if sys.platform == "win32" else None,
        icon="src/resources/img/bbva.ico",
    ),
]

buildOptions = {
    "include_files": [
        ('src/resources/img/bbva.ico', 'src/resources/img/bbva.ico')
    ]
}

setup(
    name="Validador de mallas",
    version="0.1",
    description="Validador de mallas Reliability - DataHub",
    options={'build_exe': buildOptions},
    executables=executables
)
