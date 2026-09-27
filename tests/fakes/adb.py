"""A fake adb, set in place of abgal.adb.

It answers the few commands abgal sends, the device list, the console's
name query and the console's kill, from a table the test fills. Every call
is recorded as (serial, args).
"""


class FakeAdb:

    def __init__(self, proc=None):
        self.proc = proc
        self.devices = {}
        self.calls = []
        self.devices_fails = False

    def attach(self, serial, name, state="device", pid=None, stubborn=False):
        """An emulator adb lists. A stubborn one ignores the console's kill."""
        self.devices[serial] = {"name": name, "state": state, "pid": pid,
                                "stubborn": stubborn}

    def __call__(self, *args, serial=None, timeout=30):
        args = tuple(str(a) for a in args)
        self.calls.append((serial, args))
        if args == ("devices",):
            return self.list_devices()
        if args == ("emu", "avd", "name"):
            return self.console_name(serial)
        if args == ("emu", "kill"):
            return self.console_kill(serial)
        return 0, "", ""

    def list_devices(self):
        if self.devices_fails:
            return 1, "", "cannot connect to daemon"
        lines = ["List of devices attached"]
        lines += ["%s\t%s" % (s, d["state"]) for s, d in self.devices.items()]
        return 0, "\n".join(lines), ""

    def console_name(self, serial):
        device = self.devices.get(serial)
        if device is None:
            return 1, "", "error: device '%s' not found" % serial
        if device["state"] == "unauthorized":
            return 1, "", "error: device unauthorized."
        return 0, "%s\nOK" % device["name"], ""

    def console_kill(self, serial):
        device = self.devices.get(serial)
        if device is None:
            return 1, "", "error: device '%s' not found" % serial
        if not device["stubborn"]:
            del self.devices[serial]
            if self.proc is not None and device["pid"] is not None:
                self.proc.remove(device["pid"])
        return 0, "OK: killing emulator, bye bye", ""

    def serials_called(self, *args):
        return [s for s, a in self.calls if a == args]
