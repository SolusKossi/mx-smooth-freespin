# MX Master: smooth free-spin scrolling on Windows

The MX Master 3S has two wheel modes: ratchet (notched) and free-spin. On Windows,
both scroll the same way: three lines per notch, even with "Smooth scrolling"
turned on in Logi Options+.

This script makes free-spin scroll smoothly, in small steps that follow the
wheel, closer to a trackpad. Ratchet mode stays line by line.

## How it works

- The mouse already sends fine-grained ("hi-res") wheel data in free-spin, over
  Logitech's HID++ protocol (feature `0x2121`, HiResWheel).
- Logi Options+ takes that data and sends Windows whole notches (120 units).
  The Bolt receiver doesn't tell Windows the mouse supports fine steps
  (no Resolution Multiplier in its HID descriptor), so Windows can't read the
  fine data itself.
- In free-spin, this script reads the same HID++ wheel events and sends Windows
  small wheel deltas with `SendInput`. A low-level mouse hook blocks Options+'s
  whole-notch events while you're in free-spin.
- In ratchet, it touches nothing.

It's one Python file with no dependencies. It talks to the mouse through
Windows' own `hid.dll` and `setupapi.dll` via `ctypes`, and makes no network
access.

## Tested on

- MX Master 3S for Business, connected through a **Logi Bolt receiver**
- Windows 11, Python 3.14, Logi Options+ running with "Smooth scrolling" on

That is the only setup it has been tested on. Other HID++ mice with a MagSpeed
wheel (MX Master 3, MX Master 3S) will probably work. **Bluetooth probably will
not**: over Bluetooth on Windows the mouse showed whole notches only, and the
script has not been tested that way.

Programs that ignore fractional wheel deltas (some older Win32 programs) still
scroll in steps. Browsers, VS Code, Teams and most modern apps scroll smoothly.

## Install

Needs Python 3 from [python.org](https://www.python.org/) (it uses `pythonw.exe`).

```powershell
git clone https://github.com/SolusKossi/mx-smooth-freespin.git "$env:USERPROFILE\mx-smooth-freespin"
pwsh -File "$env:USERPROFILE\mx-smooth-freespin\install.ps1"
```

This copies the script to `%LOCALAPPDATA%\MXSmoothScroll`, adds a shortcut to
your Startup folder, and starts it. No admin rights, service or scheduled task.

Uninstall:

```powershell
pwsh -File "$env:USERPROFILE\mx-smooth-freespin\install.ps1" -Uninstall
```

## Use and tuning

```powershell
python mx_scroll_mode.py probe            # show what the mouse reports, change nothing
python mx_scroll_mode.py run -v           # run in a console, log every wheel event
python mx_scroll_mode.py run --speed=1.5  # free-spin 1.5x further per wheel turn
```

When started by the installer, it writes its log to
`%LOCALAPPDATA%\MXSmoothScroll\mx_scroll_mode.log`.

## Notes

- Only one copy runs at a time (named mutex), so two copies never send double steps.
- It survives the mouse sleeping, reconnecting and the receiver being re-plugged.
- On a managed machine: it is a plain script run by the signed `pythonw.exe`,
  and it hooks only the mouse, not the keyboard. Please don't repackage it as an
  `.exe`; that is the form endpoint protection is most likely to flag.

## License

MIT
