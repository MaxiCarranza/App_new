from cx_Freeze import setup, Executable
from PySide6.QtCore import QLibraryInfo
import sys

qt_platforms_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)

executables = [
    Executable(
        "main_qt.py",
        target_name="validador.exe",
        base="Win32GUI" if sys.platform == "win32" else None,
        icon="src/resources/img/bbva.ico",
    ),
]

buildOptions = {
    "packages": ["os", "sys", "traceback", "logging", "PySide6"],
    "includes": ["src.view.reli_ui"],
    "excludes": ["tkinter"],
    "include_files": [
        ('src/resources/img/bbva.ico', 'src/resources/img/bbva.ico'),
        ('src/resources/img/logo.png', 'src/resources/img/logo.png'),
        ('src/resources/img/logo_2.png', 'src/resources/img/logo_2.png'),
        ('src/resources/img/im_bbva.png', 'src/resources/img/im_bbva.png'),
        ('src/resources/img/help.png', 'src/resources/img/help.png'),
        ('src/resources/fechas_nolaborables.json', 'src/fechas_nolaborables.json'),
        (qt_platforms_path, "platforms"),  # Include Qt platform plugins
    ],
}

setup(
    name="Validador de mallas",
    version="0.1",
    description="Validador de mallas Reliability - DataHub",
    options={'build_exe': buildOptions},
    executables=executables
)