import pynmea2

from pyubx import Manager


class CoordinateService(Manager):
    def __init__(self, ser, debug=False):
        if isinstance(ser, bytes) or isinstance(ser, str):
            import serial
            ser = serial.Serial(ser)
        Manager.__init__(self, ser, debug)
        self._dumpNMEA = False
        self.latest_fix = None

    # Override onNMEA from parent class to do work
    def onNMEA(self, buffer):
        msg = pynmea2.parse(buffer)
        if msg.__class__ is pynmea2.GGA:
            if msg.gps_qual > 0:
                self.latest_fix = msg
        else:
            # Potential to expand to more message types here
            pass

    def get_latest_fix(self):
        if self.latest_fix is not None:
            return (
                self.latest_fix.latitude,
                self.latest_fix.longitude,
                self.latest_fix.altitude,
                self.latest_fix.timestamp
            )
        else:
            return 0
