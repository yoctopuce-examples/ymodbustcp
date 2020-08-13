# ymodbustcp

Ymodbustcp is a simple Modbus server that use Yocopuce sensor as value for Modbus register

## Instalation

To install this small Modbus TCP server, you must clone the code from GitHub:
````
git clone https://github.com/yoctopuce-examples/ymodbustcp.git
cd ymodbustcp
````

And install with pip the libraries used by the server, that is pymodbus and yoctopuce.
````
pip install pymodbus
pip install yoctopuce
````

Then you must edit the device_mapping.txt file so that it corresponds to the Yoctopuce modules present on the machine.
Ex: 

````
0x0001,METEOMK2-114F07.temperature,float32
0x0002,METEOMK2-114F07.humidity,float32
0x0003,LIGHTMK3-C0905.lightSensor,int32
````

Then you only have to launch the server::

```
./ymodbustcp.py
```

## More Informations

For more information you can have a look at this article:

    https://www.yoctopuce.com/EN/article/using-yoctopuce-sensors-with-modbus-tcp 