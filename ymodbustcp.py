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
from multiprocessing import Queue
# --------------------------------------------------------------------------- #
# configure the service logging
# --------------------------------------------------------------------------- #
import logging

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder
from pymodbus.server.asynchronous import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from yoctopuce.yocto_api import *

# --------------------------------------------------------------------------- #
# import the modbus libraries we need
# --------------------------------------------------------------------------- #

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)


class YocotpuceBinding(object):

    def __init__(self, reg_no, hwid, encoding):
        self.reg_addr = reg_no
        self.hwid = hwid
        self.ysensor = YSensor.FindSensor(hwid)
        self.encoding = encoding
        self.reg_len = 2
        if self.encoding == 'int8':
            self.reg_len = 1
        elif self.encoding == 'int32' or self.encoding == 'float32':
            self.reg_len = 2

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

    def validate(self, address, count):
        end_addr = address + count
        if end_addr < self.reg_addr:
            return False
        if address > (self.reg_addr + self.reg_len):
            return False
        return True

    def get_encoded_measure(self, address, count):
        offset = address - self.reg_addr
        val = self.ysensor.get_currentValue()
        full_register = self.encode_value(val)
        return full_register[offset: offset + count]

    def set_encoded_measure(self, org_val, address, count):
        end_addr = address + count
        # skip device that are outside the range
        if end_addr <= self.reg_addr:
            return
        if address > (self.reg_addr + self.reg_len):
            return
        # get sensor values
        val = self.ysensor.get_currentValue()
        full_register = self.encode_value(val)
        # and update the corresponding register
        offset = self.reg_addr
        for word in full_register:
            org_val[offset] = word
            offset += 1

    def get_hwid(self):
        return self.hwid

    def get_reglen(self):
        return self.reg_len


# --------------------------------------------------------------------------- #
# create your custom data block with callbacks
# --------------------------------------------------------------------------- #


class YoctopuceDataBlock(ModbusSequentialDataBlock):
    """ A datablock that stores the new value in memory
    and performs a custom action after it has been stored.
    """

    def __init__(self, devices):
        self.devices = devices
        start = 0xffff
        end = 0
        for reg in devices.keys():
            reglen = devices[reg].get_reglen()
            if reg < start:
                start = reg
            if reg + reglen > end:
                end = reg + reglen
        values = [0] * (end - start)
        super(YoctopuceDataBlock, self).__init__(start, values)

    def getValues(self, address, count=1):
        for reg in self.devices.keys():
            self.devices[reg].set_encoded_measure(self.values, address, count)
        values = super(YoctopuceDataBlock, self).getValues(address, count)
        return values


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
    store = ModbusSlaveContext(di=block, co=block, hr=block, ir=block, zero_mode=True)
    context = ModbusServerContext(slaves=store, single=True)

    # ----------------------------------------------------------------------- #
    # initialize the server information
    # ----------------------------------------------------------------------- #
    identity = ModbusDeviceIdentification()
    identity.VendorName = 'Yoctopuce'
    identity.ProductCode = 'YMT'
    identity.VendorUrl = 'https://github.com/yoctopuce-examples/ymodbustcp'
    identity.ProductName = 'ymodbustcp Server'
    identity.ModelName = 'ypymodbus Server'
    identity.MajorMinorRevision = '0.0.1'

    StartTcpServer(context, identity=identity, address=("localhost", 5020))


if __name__ == "__main__":
    run_callback_server()
