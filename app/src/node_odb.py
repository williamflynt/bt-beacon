import time

import obd

"""
obd.OBD            # main OBD connection class
obd.Async          # asynchronous OBD connection class
obd.commands       # command tables
obd.Unit           # unit tables (a Pint UnitRegistry)
obd.OBDStatus      # enum for connection status
obd.scan_serial    # util function for manually scanning for OBD adapters
obd.OBDCommand     # class for making your own OBD Commands
obd.ECU            # enum for marking which ECU a command should listen to
obd.logger         # the OBD module's root logger (for debug)
"""

connection = obd.OBD()  # auto-connects to USB or RF port

cmd = obd.commands.SPEED  # select an OBD command (sensor)
# cmd = obd.commands.OIL_TEMP  # select an OBD command (sensor)

response = connection.query(cmd)  # send the command, and parse the response

while True:
    print(response.value)  # returns unit-bearing values thanks to Pint
    time.sleep(1)
# print(response.value.to("mph"))  # user-friendly unit conversions
