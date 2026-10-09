"""Create an isolated environment; never pip-install into the QGIS interpreter."""
import sys
import subprocess
import os
import venv
from pathlib import Path
if __name__=='__main__':
    if not (3,10)<=sys.version_info[:2]<=(3,12):
        raise SystemExit('Python 3.10–3.12 gerekli.')
    folder=Path(sys.argv[1])
    if folder.exists(): raise SystemExit('Ortam klasörü mevcut. Mevcut Python yolunu seçin veya farklı kurulum klasörü kullanın.')
    venv.create(folder,with_pip=True)
    python=folder/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    # Replace this process so cancellation also stops pip, without a detached child.
    os.execv(str(python),[str(python),'-m','pip','install','--timeout','180','--retries','3','-r',str(Path(__file__).parent/'requirements.txt')])
