"""MX Master wheel: hi-res (smooth) scrolling in free-spin, line-by-line in ratchet.

Talks HID++ 2.0 to the mouse through Windows' own hid.dll/setupapi.dll (ctypes,
no third-party packages). In free-spin it turns the wheel's hi-res events into
small WM_MOUSEWHEEL deltas and blocks Options+'s whole-notch ones; in ratchet it
leaves scrolling alone.

  python mx_scroll_mode.py probe                 show what the mouse reports, change nothing
  python mx_scroll_mode.py run [-v] [--speed=1]  smooth scrolling in free-spin until stopped
      -v       log every wheel event
      --speed  1 = same distance per wheel travel as ratchet; 2 = twice as far
"""
import ctypes
import ctypes.wintypes as wt
import sys
import time

# ---------------------------------------------------------------- Win32 / HID

hid = ctypes.WinDLL("hid")
setupapi = ctypes.WinDLL("setupapi")
k32 = ctypes.WinDLL("kernel32", use_last_error=True)


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD), ("Data4", ctypes.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("InterfaceClassGuid", GUID), ("Flags", wt.DWORD), ("Reserved", ctypes.c_void_p)]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Size", wt.ULONG), ("VendorID", wt.USHORT), ("ProductID", wt.USHORT), ("VersionNumber", wt.USHORT)]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [("Usage", wt.USHORT), ("UsagePage", wt.USHORT), ("InputReportByteLength", wt.USHORT),
                ("OutputReportByteLength", wt.USHORT), ("FeatureReportByteLength", wt.USHORT),
                ("Reserved", wt.USHORT * 17), ("Rest", wt.USHORT * 10)]


class OVERLAPPED(ctypes.Structure):
    _fields_ = [("Internal", ctypes.c_size_t), ("InternalHigh", ctypes.c_size_t),
                ("Offset", wt.DWORD), ("OffsetHigh", wt.DWORD), ("hEvent", wt.HANDLE)]


k32.CreateFileW.restype = wt.HANDLE
k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE]
k32.CreateEventW.restype = wt.HANDLE
k32.CreateEventW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.BOOL, wt.LPCWSTR]
k32.ReadFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p, ctypes.c_void_p]
k32.WriteFile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p, ctypes.c_void_p]
k32.GetOverlappedResult.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(wt.DWORD), wt.BOOL]
k32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
k32.CancelIoEx.argtypes = [wt.HANDLE, ctypes.c_void_p]
k32.CloseHandle.argtypes = [wt.HANDLE]
setupapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), ctypes.c_void_p, ctypes.c_void_p, wt.DWORD]
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID), wt.DWORD,
                                                 ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
                                                      ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
hid.HidD_GetAttributes.argtypes = [wt.HANDLE, ctypes.POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetPreparsedData.argtypes = [wt.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetCaps.restype = ctypes.c_long

INVALID_HANDLE = wt.HANDLE(-1).value
GENERIC_RW = 0x80000000 | 0x40000000
SHARE_RW = 0x1 | 0x2
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
ERROR_IO_PENDING = 997
WAIT_OBJECT_0 = 0
LOGITECH = 0x046D


def hid_collections():
    """Yield (path, vid, pid, usage_page, usage, out_len) for every present HID collection."""
    guid = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(guid))
    devs = setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None, 0x12)  # PRESENT | DEVICEINTERFACE
    try:
        i = 0
        while True:
            ifd = SP_DEVICE_INTERFACE_DATA(cbSize=ctypes.sizeof(SP_DEVICE_INTERFACE_DATA))
            if not setupapi.SetupDiEnumDeviceInterfaces(devs, None, ctypes.byref(guid), i, ctypes.byref(ifd)):
                break
            i += 1
            need = wt.DWORD()
            setupapi.SetupDiGetDeviceInterfaceDetailW(devs, ctypes.byref(ifd), None, 0, ctypes.byref(need), None)
            buf = ctypes.create_string_buffer(need.value)
            ctypes.c_uint32.from_buffer(buf).value = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
            if not setupapi.SetupDiGetDeviceInterfaceDetailW(devs, ctypes.byref(ifd), buf, need, None, None):
                continue
            path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
            h = k32.CreateFileW(path, 0, SHARE_RW, None, OPEN_EXISTING, 0, None)
            if h == INVALID_HANDLE:
                continue
            try:
                attr = HIDD_ATTRIBUTES(Size=ctypes.sizeof(HIDD_ATTRIBUTES))
                if not hid.HidD_GetAttributes(h, ctypes.byref(attr)):
                    continue
                pp = ctypes.c_void_p()
                if not hid.HidD_GetPreparsedData(h, ctypes.byref(pp)):
                    continue
                caps = HIDP_CAPS()
                hid.HidP_GetCaps(pp, ctypes.byref(caps))
                hid.HidD_FreePreparsedData(pp)
                yield path, attr.VendorID, attr.ProductID, caps.UsagePage, caps.Usage, caps.OutputReportByteLength
            finally:
                k32.CloseHandle(h)
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(devs)


class HidDev:
    """One HID collection, opened shared (Options+ keeps it open too) with overlapped I/O."""

    def __init__(self, path, out_len):
        self.h = k32.CreateFileW(path, GENERIC_RW, SHARE_RW, None, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None)
        if self.h == INVALID_HANDLE:
            raise OSError(ctypes.get_last_error(), "CreateFile failed")
        self.out_len = out_len
        self.rbuf = ctypes.create_string_buffer(64)
        self.rov = OVERLAPPED(hEvent=k32.CreateEventW(None, True, False, None))
        self.wov = OVERLAPPED(hEvent=k32.CreateEventW(None, True, False, None))
        self.pending = False

    def write(self, data):
        buf = ctypes.create_string_buffer(bytes(data).ljust(self.out_len, b"\0"), self.out_len)
        if not k32.WriteFile(self.h, buf, self.out_len, None, ctypes.byref(self.wov)):
            if ctypes.get_last_error() != ERROR_IO_PENDING:
                raise OSError(ctypes.get_last_error(), "WriteFile failed")
            if k32.WaitForSingleObject(self.wov.hEvent, 2000) != WAIT_OBJECT_0:
                k32.CancelIoEx(self.h, ctypes.byref(self.wov))
                raise TimeoutError("write timed out")
        n = wt.DWORD()
        k32.GetOverlappedResult(self.h, ctypes.byref(self.wov), ctypes.byref(n), False)

    def read(self, timeout_ms):
        """Return one input report as bytes, or None on timeout. A timed-out read stays pending."""
        if not self.pending:
            if k32.ReadFile(self.h, self.rbuf, len(self.rbuf), None, ctypes.byref(self.rov)):
                return self._finish()
            err = ctypes.get_last_error()
            if err != ERROR_IO_PENDING:
                raise OSError(err, "ReadFile failed")
            self.pending = True
        if k32.WaitForSingleObject(self.rov.hEvent, timeout_ms) != WAIT_OBJECT_0:
            return None
        return self._finish()

    def _finish(self):
        self.pending = False
        n = wt.DWORD()
        if not k32.GetOverlappedResult(self.h, ctypes.byref(self.rov), ctypes.byref(n), False):
            raise OSError(ctypes.get_last_error(), "device gone")
        return self.rbuf.raw[:n.value]

    def close(self):
        if self.pending:
            k32.CancelIoEx(self.h, ctypes.byref(self.rov))
        k32.CloseHandle(self.h)


# ---------------------------------------------------------------- HID++ 2.0

SWID = 0x0B
F_HIRES = 0x2121
F_SMARTSHIFT = 0x2110
F_SMARTSHIFT_ENH = 0x2111
MODE_HIRES = 0x02     # 0x2121 wheel mode bit: 1 = high resolution reports
MODE_DIVERT = 0x01    # 0x2121 wheel mode bit: 1 = wheel goes to HID++ (software) instead of HID


class HidppError(Exception):
    pass


class Mouse:
    def __init__(self, dev, index, name):
        self.dev, self.index, self.name = dev, index, name
        self.features = {}
        self.on_event = None

    def request(self, feat_idx, func, params=b"", timeout=1.0):
        msg = bytes([0x11, self.index, feat_idx, (func << 4) | SWID]) + bytes(params)
        self.dev.write(msg)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            r = self.dev.read(int(max(1, (deadline - time.monotonic()) * 1000)))
            if not r or r[0] not in (0x10, 0x11) or r[1] != self.index:
                continue
            if r[2] == 0xFF and r[3] == feat_idx and r[4] == msg[3]:
                raise HidppError(f"HID++ error {r[5]:#04x} on feature {feat_idx} func {func}")
            if r[0] == 0x10 and r[2] == 0x8F:
                raise HidppError(f"HID++ 1.0 error {r[5]:#04x}")
            if r[2] == feat_idx and r[3] == msg[3]:
                return r[4:]
            self._maybe_event(r)
        raise TimeoutError(f"no reply from feature {feat_idx} func {func}")

    def _maybe_event(self, r):
        if self.on_event and r[0] == 0x11 and r[1] == self.index and (r[3] & 0x0F) == 0:
            self.on_event(r[2], r[3] >> 4, r[4:])

    def feature(self, fid):
        if fid not in self.features:
            idx = self.request(0, 0, bytes([fid >> 8, fid & 0xFF]))[0]
            self.features[fid] = idx or None
        return self.features[fid]

    # HiResWheel 0x2121
    def wheel_mode(self):
        return self.request(self.feature(F_HIRES), 1)[0]

    def set_wheel_mode(self, mode):
        return self.request(self.feature(F_HIRES), 2, bytes([mode]))[0]

    def ratchet(self):
        """True = ratchet (notched), False = free-spin."""
        return bool(self.request(self.feature(F_HIRES), 3)[0] & 0x01)

    # SmartShift, only used by `test` to flip the wheel without touching it
    def set_freespin(self, free):
        mode = 1 if free else 2
        if self.feature(F_SMARTSHIFT_ENH):
            self.request(self.feature(F_SMARTSHIFT_ENH), 2, bytes([mode, 0, 0]))
        elif self.feature(F_SMARTSHIFT):
            self.request(self.feature(F_SMARTSHIFT), 1, bytes([mode, 0, 0]))
        else:
            raise HidppError("no SmartShift feature")


def find_mice(verbose=False):
    """Every Logitech HID++ long-report collection with a device that has feature 0x2121."""
    found = []
    for path, vid, pid, page, usage, out_len in hid_collections():
        if vid != LOGITECH:
            continue
        if verbose:
            print(f"  {pid:04X} page {page:04X} usage {usage:04X} out {out_len:2}  {path}")
        is_ble = page == 0xFF43 and usage == 0x0202
        is_rcv = page == 0xFF00 and usage == 0x0002
        if not (is_ble or is_rcv) or out_len < 20:
            continue
        try:
            dev = HidDev(path, out_len)
        except OSError as e:
            print(f"  cannot open {pid:04X}: {e}")
            continue
        keep = False
        for index in ([0xFF] if is_ble else [1, 2, 3, 4, 5, 6]):
            m = Mouse(dev, index, f"{'BLE' if is_ble else 'receiver'} {pid:04X} dev {index:#04x}")
            try:
                if m.feature(F_HIRES):
                    found.append(m)
                    keep = True
            except (TimeoutError, HidppError):
                pass
        if not keep:
            dev.close()
    return found


def describe(m):
    caps = m.request(m.feature(F_HIRES), 0)
    mode = m.wheel_mode()
    print(f"{m.name}: 0x2121 at index {m.feature(F_HIRES)}, multiplier {caps[0]}, flags {caps[1]:#04x}")
    print(f"  wheel mode {mode:#04x}: hi-res={'on' if mode & MODE_HIRES else 'off'}, "
          f"diverted to software={'yes' if mode & MODE_DIVERT else 'no'}, invert={'yes' if mode & 0x04 else 'no'}")
    print(f"  wheel is now: {'ratchet' if m.ratchet() else 'free-spin'}")
    print(f"  SmartShift: 0x2110={m.feature(F_SMARTSHIFT)} 0x2111={m.feature(F_SMARTSHIFT_ENH)}")


# ---------------------------------------------------------------- scroll injection
#
# Options+ diverts the wheel to HID++ and turns it into WM_MOUSEWHEEL itself, but
# always in whole 120-unit notches. The Bolt receiver's HID descriptor has no
# Resolution Multiplier, so Windows cannot take hi-res data from the mouse
# directly. So in free-spin we read the hi-res wheel events ourselves, send small
# wheel deltas with SendInput, and block the coarse events Options+ sends.
# In ratchet nothing is touched.

user32 = ctypes.WinDLL("user32", use_last_error=True)
LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)
user32.SetWindowsHookExW.restype = wt.HHOOK
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD]
user32.CallNextHookEx.restype = LRESULT
user32.CallNextHookEx.argtypes = [wt.HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM]
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
user32.SendInput.argtypes = [wt.UINT, ctypes.c_void_p, ctypes.c_int]
k32.GetModuleHandleW.restype = wt.HMODULE
k32.GetModuleHandleW.argtypes = [wt.LPCWSTR]

WH_MOUSE_LL = 14
WM_MOUSEWHEEL = 0x020A
MOUSEEVENTF_WHEEL = 0x0800
OUR_TAG = 0x4D585343  # dwExtraInfo on our own events, so the hook lets them through
NOTCH = 120           # WHEEL_DELTA


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wt.POINT), ("mouseData", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("mi", MOUSEINPUT)]


def send_wheel(delta):
    inp = INPUT(type=0, mi=MOUSEINPUT(mouseData=delta & 0xFFFFFFFF, dwFlags=MOUSEEVENTF_WHEEL, dwExtraInfo=OUR_TAG))
    return user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


class State:
    free = False      # wheel is in free-spin: we own scrolling
    speed = 1.0       # 1.0 = same distance per notch-worth of wheel travel as ratchet
    verbose = False


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


@HOOKPROC
def hook_proc(code, wparam, lparam):
    if code == 0 and wparam == WM_MOUSEWHEEL and State.free:
        info = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        if info.dwExtraInfo != OUR_TAG:
            return 1  # Options+'s whole-notch event: swallow it
    return user32.CallNextHookEx(None, code, wparam, lparam)


def set_free(m, free, why):
    if free == State.free:
        return
    State.free = free
    log(f"{'free-spin -> smooth' if free else 'ratchet   -> line by line'} ({why})")
    # Options+ already does this; set it ourselves too so we don't depend on it.
    try:
        mode = m.wheel_mode()
        want = (mode | MODE_HIRES) if free else (mode & ~MODE_HIRES)
        if want != mode:
            m.set_wheel_mode(want)
    except (TimeoutError, HidppError):
        pass  # mouse asleep; the wheel data flag still tells us the mode


def wheel_handler(m, hires_idx, mult):
    per_unit = NOTCH * State.speed / mult
    carry = 0.0

    def on_event(feat_idx, event, data):
        nonlocal carry
        if feat_idx != hires_idx:
            return
        if event == 1:                       # ratchet switch
            set_free(m, not (data[0] & 0x01), "wheel button")
        elif event == 0:                     # wheel movement while diverted
            hires = bool(data[0] & 0x10)
            delta = int.from_bytes(data[1:3], "big", signed=True)
            if hires != State.free:          # SmartShift or a missed switch event
                set_free(m, hires, "wheel data")
            if State.free and hires:
                carry += delta * per_unit
                out = int(carry)
                if out:
                    carry -= out
                    send_wheel(out)
                    if State.verbose:
                        log(f"  wheel {delta:+d} -> {out:+d}")

    return on_event


def device_loop(m):
    hires_idx = m.feature(F_HIRES)
    mult = m.request(hires_idx, 0)[0] or 15
    m.on_event = wheel_handler(m, hires_idx, mult)
    State.free = None
    set_free(m, not m.ratchet(), "start")
    last = time.monotonic()
    while True:
        r = m.dev.read(1000)  # OSError here = receiver unplugged; worker() starts over
        if r:
            m._maybe_event(r)
        if time.monotonic() - last > 10:     # catch switches we never got an event for
            last = time.monotonic()
            try:
                set_free(m, not m.ratchet(), "poll")
            except TimeoutError:
                pass  # mouse asleep: no reply until it wakes, then its events resume


def worker():
    while True:  # survive sleep, reconnects and receiver swaps
        try:
            mice = find_mice()
            if not mice:
                State.free = False
                log("mouse not found, retrying in 10 s")
                time.sleep(10)
                continue
            log(f"using {mice[0].name}")
            device_loop(mice[0])
        except (OSError, TimeoutError, HidppError) as e:
            State.free = False
            log(f"lost the mouse ({e}), retrying in 5 s")
            time.sleep(5)


def run():
    import threading
    # Two copies would each send their own small steps: let only one run.
    k32.CreateMutexW.restype = wt.HANDLE
    k32.CreateMutexW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR]
    run.mutex = k32.CreateMutexW(None, False, "Local\\mx_scroll_mode")
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        log("already running, exiting")
        return
    threading.Thread(target=worker, daemon=True).start()
    hook = user32.SetWindowsHookExW(WH_MOUSE_LL, hook_proc, k32.GetModuleHandleW(None), 0)
    if not hook:
        raise OSError(ctypes.get_last_error(), "SetWindowsHookEx failed")
    msg = wt.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        pass


def main():
    if sys.stdout is None:  # pythonw: no console, log next to the script instead
        import os
        sys.stdout = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mx_scroll_mode.log"),
                          "w", encoding="utf-8", buffering=1)
    args = sys.argv[1:]
    cmd = args[0] if args and not args[0].startswith("-") else "run"
    State.verbose = "-v" in args
    for a in args:
        if a.startswith("--speed="):
            State.speed = float(a.split("=", 1)[1])
    if cmd == "probe":
        print("Logitech HID collections:")
        mice = find_mice(verbose=True)
        print()
        for m in mice:
            describe(m)
        if not mice:
            print("No HID++ device with HiResWheel (0x2121) found.")
    elif cmd == "run":
        run()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
