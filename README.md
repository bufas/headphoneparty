# headphoneparty

## Dependencies
The program depends on [PyCrypto][https://www.dlitz.net/software/pycrypto/] which is a cryptography toolkit for python.

## How to run unittests
The unittests are located in a module named test.py and are written in the python unittest framework and are run the standard way.

```python
python -m unittest test
```

## How to start the peers independently
Before you start any peer you need to start the router as it mediates all the message passing.

#### Starting the router
The router takes either 2 or 8 arguments depending on whether you want to use the visualizer or not.

* host
* port
* visualize (True | False)
* world width (integer)
* world height (integer)
* top speed (integer)
* max speed change (integer)
* radio range (integer)

Host and port are self explanatory. If visualize is set to True, the visualizer will be shown. World width and height are the size of the world peers move around in, in centimeters.Standard values for these are 2000, i.e. 20 meters. Top speed is how fast the peers can move in cm per 'tick'. Max speed change defines the allowed acceleration every 'tick' and is 50 by default.Finally radio range defines the broadcast range in cm, and is 500 per default.

Here is a few examples on how to start the router

```python
# Do not use the visualizer
python Router.py 127.0.0.1 8300
# Use the visualizer
python Router.py 127.0.0.1 8300 True 4000 1000 120 25 300
```

#### Starting a peer
Peers take 8 arguments.

* register (register)
* name (string)
* host
* port
* router host
* router port
* manual override (True | False)
* clock sync (True | False)

Register must be the string `register` or the peer will not register with the router, and consequently wouln't recieve any messages. Name, host, and port are pretty self explanatory. Router host and port are the address of the router. Manual override specifies whether the peer should automatically check for it being out of 'range', and automatically send join messages until a satisfying amount of responses has been received. This should be set to `False` under normal circumstances. Clock sync should be set to `True` to turn on clock synchronization.

Here is an example on how to start a peer

```python
python Peer.py register Peer1 127.0.0.1 8301 127.0.0.1 8300 False True
```
