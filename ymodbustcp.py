#!/usr/bin/env python
"""
Pymodbus Server With Callbacks
--------------------------------------------------------------------------

This is an example of adding callbacks to a running modbus server
when a value is written to it. In order for this to work, it needs
a device-mapping.txt file.
"""
# --------------------------------------------------------------------------- #
# import the python libraries we need
# --------------------------------------------------------------------------- #
from multiprocessing import Queue, Process
# --------------------------------------------------------------------------- #
# configure the service logging
# --------------------------------------------------------------------------- #
import logging
# --------------------------------------------------------------------------- #
# import the modbus libraries we need
# --------------------------------------------------------------------------- #
import struct

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder, BinaryPayloadBuilder
from pymodbus.server.asynchronous import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSparseDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from yoctopuce.yocto_api import *

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)


class YocotpuceBinding(object):

    def __init__(self, reg_no, hwid, encoding):
        self.reg_no = reg_no
        self.hwid = hwid
        self.ysensor = YSensor.FindSensor(hwid)
        self.encoding = encoding

    def encode_value(self, val):
        builder = BinaryPayloadBuilder(byteorder=Endian.Big)
        if self.encoding == 'int8':
            builder.add_8bit_int(int(val))
        elif self.encoding == 'int16':
            builder.add_16bit_int(int(val))
        elif self.encoding == 'int32':
            builder.add_32bit_int(int(val))
        elif self.encoding == 'float16':
            builder.add_16bit_float(val)
        elif self.encoding == 'float32':
            builder.add_32bit_float(val)
        ba = builder.to_registers()
        return ba

    def get_encoded_measure(self):
        val = self.ysensor.get_currentValue()
        return self.encode_value(val)

    def get_hwid(self):
        return self.hwid

# --------------------------------------------------------------------------- #
# create your custom data block with callbacks
# --------------------------------------------------------------------------- #


class YoctopuceDataBlock(ModbusSparseDataBlock):
    """ A datablock that stores the new value in memory
    and performs a custom action after it has been stored.
    """

    def __init__(self, devices):
        """
        """
        self.devices = devices
        values = {}
        for reg in devices.keys():
            values[reg] = self.devices[reg].get_encoded_measure()

        values[0xbeef] = len(values)  # the number of devices
        super(YoctopuceDataBlock, self).__init__(values)

    def setValues(self, address, value):
        """ Sets the requested values of the datastore

        :param address: The starting address
        :param values: The new values to be set
        """
        super(YoctopuceDataBlock, self).setValues(address, value)

        # whatever you want to do with the written value is done here,
        # however make sure not to do too much work here or it will
        # block the server, espectially if the server is being written
        # to very quickly
        print("wrote {} ".format(value, address))

    def getValues(self, address, count=1):
        print("read %d count %d -> %s " % (address, count, self.devices[address].get_hwid()))
        val = self.devices[address].get_encoded_measure()
        print(val)
        return val

# --------------------------------------------------------------------------- #
# define your callback process
# --------------------------------------------------------------------------- #


def rescale_value(value):
    """ Rescale the input value from the range
    of 0..100 to -3200..3200.

    :param value: The input value to scale
    :returns: The rescaled value
    """
    s = 1 if value >= 50 else -1
    c = value if value < 50 else (value - 50)
    return s * (c * 64)


def device_writer(queue):
    """ A worker process that processes new messages
    from a queue to write to device outputs

    :param queue: The queue to get new messages from
    """
    while True:
        device, value = queue.get()
        scaled = rescale_value(value[0])
        log.debug("Write(%s) = %s" % (device, value))
        if not device: continue
        # do any logic here to update your devices


# --------------------------------------------------------------------------- #
# initialize your device map
# --------------------------------------------------------------------------- #


def read_device_map(path):
    """ A helper method to read the device
    path to address mapping from file::

       0x0001,/dev/device1
       0x0002,/dev/device2

    :param path: The path to the input file
    :returns: The input mapping file
    """
    devices = {}
    with open(path, 'r') as stream:
        for line in stream:
            piece = line.strip().split(',')
            hwid = piece[1]
            regno = int(piece[0], 16)
            devices[regno] = YocotpuceBinding(regno, hwid, piece[2])
    return devices


# ----------------------------------------------------------------------- #
# initialize your data store
# ----------------------------------------------------------------------- #
def run_callback_server():
    errmsg = YRefParam()

    # Setup the API to use local USB devices
    if YAPI.RegisterHub("usb", errmsg) != YAPI.SUCCESS:
        sys.exit("init error" + str(errmsg))

    # ----------------------------------------------------------------------- #
    # initialize your data store
    # ----------------------------------------------------------------------- #
    queue = Queue()
    devices = read_device_map("device-mapping.txt")

    block = YoctopuceDataBlock(devices)
    store = ModbusSlaveContext(di=block, co=block, hr=block, ir=block)
    context = ModbusServerContext(slaves=store, single=True)

    # ----------------------------------------------------------------------- #
    # initialize the server information
    # ----------------------------------------------------------------------- #
    identity = ModbusDeviceIdentification()
    identity.VendorName = 'pymodbus'
    identity.ProductCode = 'PM'
    identity.VendorUrl = 'http://github.com/bashwork/pymodbus/'
    identity.ProductName = 'pymodbus Server'
    identity.ModelName = 'pymodbus Server'
    identity.MajorMinorRevision = '2.3.0'

    # ----------------------------------------------------------------------- #
    # run the server you want
    # ----------------------------------------------------------------------- #
    p = Process(target=device_writer, args=(queue,))
    p.start()
    StartTcpServer(context, identity=identity, address=("localhost", 5020))


if __name__ == "__main__":
    run_callback_server()
