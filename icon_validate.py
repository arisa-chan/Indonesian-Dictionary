from pathlib import Path
from PySide6.QtGui import QGuiApplication, QIcon
import sys

app = QGuiApplication(sys.argv)
icon_path = Path('icon.ico')
print('icon path exists:', icon_path.exists())
if icon_path.exists():
    print('icon size:', icon_path.stat().st_size)
    icon = QIcon(str(icon_path))
    print('icon isNull:', icon.isNull())
    print('available sizes:', icon.availableSizes())
else:
    print('icon missing')
