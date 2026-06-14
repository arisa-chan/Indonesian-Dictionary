from pathlib import Path
import subprocess
import time
import ctypes

p = Path('dist') / 'IndonesianDictionary.exe'
print('exe path:', p)
print('exists:', p.exists())
proc = subprocess.Popen([str(p)])
time.sleep(4)
hwnd = ctypes.windll.user32.FindWindowW(None, 'Indonesian Dictionary')
print('hwnd:', hwnd)
if hwnd:
    WM_GETICON = 0x007F
    ICON_BIG = 1
    ICON_SMALL = 0
    ICON_SMALL2 = 2
    icon_big = ctypes.windll.user32.SendMessageW(hwnd, WM_GETICON, ICON_BIG, 0)
    icon_small = ctypes.windll.user32.SendMessageW(hwnd, WM_GETICON, ICON_SMALL, 0)
    icon_small2 = ctypes.windll.user32.SendMessageW(hwnd, WM_GETICON, ICON_SMALL2, 0)
    print('icon big:', icon_big)
    print('icon small:', icon_small)
    print('icon small2:', icon_small2)
    if icon_big == 0 and icon_small == 0 and icon_small2 == 0:
        # try class icon
        icon_class = ctypes.windll.user32.GetClassLongPtrW(hwnd, -14)
        print('icon class:', icon_class)
proc.terminate()
ret = proc.wait(timeout=5)
print('terminated with', ret)
