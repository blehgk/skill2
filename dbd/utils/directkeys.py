# directkeys.py
# http://stackoverflow.com/questions/13564851/generate-keyboard-events
# msdn.microsoft.com/en-us/library/dd375731

import ctypes
from ctypes import wintypes
import time

user32 = ctypes.WinDLL('user32', use_last_error=True)

INPUT_MOUSE    = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP       = 0x0002
KEYEVENTF_UNICODE     = 0x0004
KEYEVENTF_SCANCODE    = 0x0008

MAPVK_VK_TO_VSC = 0

# List of all codes for keys:
# # msdn.microsoft.com/en-us/library/dd375731
UP = 0x26
DOWN = 0x28
A = 0x41
SPACE = 0x20

# Mouse side buttons (virtual key codes)
VK_XBUTTON1 = 0x05  # rear side button ("back")
VK_XBUTTON2 = 0x06  # front side button ("forward")

# C struct definitions

wintypes.ULONG_PTR = wintypes.WPARAM

class MOUSEINPUT(ctypes.Structure):
    _fields_ = (("dx",          wintypes.LONG),
                ("dy",          wintypes.LONG),
                ("mouseData",   wintypes.DWORD),
                ("dwFlags",     wintypes.DWORD),
                ("time",        wintypes.DWORD),
                ("dwExtraInfo", wintypes.ULONG_PTR))

class KEYBDINPUT(ctypes.Structure):
    _fields_ = (("wVk",         wintypes.WORD),
                ("wScan",       wintypes.WORD),
                ("dwFlags",     wintypes.DWORD),
                ("time",        wintypes.DWORD),
                ("dwExtraInfo", wintypes.ULONG_PTR))

    def __init__(self, *args, **kwds):
        super(KEYBDINPUT, self).__init__(*args, **kwds)
        # some programs use the scan code even if KEYEVENTF_SCANCODE
        # isn't set in dwFflags, so attempt to map the correct code.
        if not self.dwFlags & KEYEVENTF_UNICODE:
            self.wScan = user32.MapVirtualKeyExW(self.wVk,
                                                 MAPVK_VK_TO_VSC, 0)

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = (("uMsg",    wintypes.DWORD),
                ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD))

class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = (("ki", KEYBDINPUT),
                    ("mi", MOUSEINPUT),
                    ("hi", HARDWAREINPUT))
    _anonymous_ = ("_input",)
    _fields_ = (("type",   wintypes.DWORD),
                ("_input", _INPUT))

LPINPUT = ctypes.POINTER(INPUT)

def _check_count(result, func, args):
    if result == 0:
        raise ctypes.WinError(ctypes.get_last_error())
    return args

user32.SendInput.errcheck = _check_count
user32.SendInput.argtypes = (wintypes.UINT, # nInputs
                             LPINPUT,       # pInputs
                             ctypes.c_int)  # cbSize

user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)  # vKey

# Functions

# Virtual keys that must carry the extended-key flag when injected as scancodes.
_EXTENDED_KEYS = {
    0x25, 0x26, 0x27, 0x28,   # arrow keys (left, up, right, down)
    0x21, 0x22, 0x23, 0x24,   # PageUp, PageDown, End, Home
    0x2D, 0x2E,               # Insert, Delete
    0xA3, 0xA5,               # right Ctrl, right Alt
}

def _key_flags(hexKeyCode, key_up):
    # Games built on DirectInput / raw input (like Dead by Daylight) read the
    # hardware scancode, not the virtual key. Sending scancodes is what makes
    # the key actually register in-game.
    flags = KEYEVENTF_SCANCODE
    if hexKeyCode in _EXTENDED_KEYS:
        flags |= KEYEVENTF_EXTENDEDKEY
    if key_up:
        flags |= KEYEVENTF_KEYUP
    return flags

def PressKey(hexKeyCode):
    # KEYBDINPUT.__init__ fills wScan from wVk via MapVirtualKeyExW; with the
    # KEYEVENTF_SCANCODE flag set, Windows delivers that scancode to the game.
    x = INPUT(type=INPUT_KEYBOARD,
              ki=KEYBDINPUT(wVk=hexKeyCode,
                            dwFlags=_key_flags(hexKeyCode, key_up=False)))
    user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))

def ReleaseKey(hexKeyCode):
    x = INPUT(type=INPUT_KEYBOARD,
              ki=KEYBDINPUT(wVk=hexKeyCode,
                            dwFlags=_key_flags(hexKeyCode, key_up=True)))
    user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))

def is_pressed(vk_code):
    # High-order bit set means the key/button is currently held down.
    # Works system-wide, so it detects the mouse button even while DBD has focus.
    return bool(user32.GetAsyncKeyState(vk_code) & 0x8000)

if __name__ == "__main__":
    PressKey(A)
    time.sleep(0.5)
    ReleaseKey(A)
    print("Pressed")