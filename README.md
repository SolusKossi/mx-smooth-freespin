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

### Let an AI assistant do it

If you use an AI assistant that can run commands on your PC (Claude Code, Codex,
Cursor, GitHub Copilot in agent mode, or similar), paste this prompt into it.
A chat-only assistant can't run anything; with one of those, follow the steps
above yourself.

```text
Install the open-source tool https://github.com/SolusKossi/mx-smooth-freespin on
this Windows PC for me. It makes the free-spin mode of a Logitech MX Master
mouse scroll smoothly while ratchet mode stays line by line. Do the work
yourself; only ask me when you need me to touch the mouse or make a choice.

1. Check prerequisites: Windows 10/11, Python 3 (`python --version`, and that
   `pythonw.exe` is on PATH), and git. If Python is missing, tell me to install
   it from python.org (with "Add to PATH" ticked) and stop. If git is missing,
   download the repo as a ZIP from GitHub instead, extract it to
   %USERPROFILE%\mx-smooth-freespin and run Unblock-File on the extracted files.
2. Clone it: git clone https://github.com/SolusKossi/mx-smooth-freespin.git
   "%USERPROFILE%\mx-smooth-freespin"
3. Read mx_scroll_mode.py and install.ps1 before running them, and tell me in
   two sentences what they do. They should use only Python's standard library
   and Windows' own DLLs, make no network calls, and need no admin rights.
   If you see anything else, stop and tell me.
4. Run: python "%USERPROFILE%\mx-smooth-freespin\mx_scroll_mode.py" probe
   - A line like "receiver C548 dev 0x03: 0x2121 at index ..." means it works
     with my mouse. Note whether "diverted to software" is yes or no.
   - "No HID++ device with HiResWheel (0x2121) found" means the mouse isn't
     reachable. Tell me to wake it by moving it and run probe again. If it is
     still not found, the mouse is probably on Bluetooth. This tool is only
     tested with a Logi Bolt receiver (a Unifying receiver may work); tell me
     that and stop.
5. Ask me to confirm Logi Options+ is running and that "Smooth scrolling" is on
   (Options+ > the mouse > Point & Scroll > Scroll wheel).
6. Install: pwsh -File "%USERPROFILE%\mx-smooth-freespin\install.ps1"
   (use `powershell -ExecutionPolicy Bypass -File ...` if pwsh is not installed).
   This copies the script to %LOCALAPPDATA%\MXSmoothScroll, adds a shortcut to
   my Startup folder and starts it in the background.
7. Wait a few seconds, then show me %LOCALAPPDATA%\MXSmoothScroll\mx_scroll_mode.log.
   It should say "using receiver ..." and then "ratchet" or "free-spin".
8. Ask me to press the button below the wheel to switch to free-spin and
   scroll a long web page, then switch back. Free-spin should glide; ratchet
   should step. Check the log shows the switches.
9. If it feels too slow or fast, edit the Startup shortcut "MX Smooth Scroll"
   to add --speed=1.5 (or another value) after "run", stop the running
   pythonw.exe that has mx_scroll_mode.py on its command line (by its PID only,
   never all python processes) and start it again from the shortcut.

To uninstall later: pwsh -File "%USERPROFILE%\mx-smooth-freespin\install.ps1" -Uninstall
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
