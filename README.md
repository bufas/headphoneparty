# headphoneparty

### Dependencies
The program depends on [PyCrypto](https://www.dlitz.net/software/pycrypto/) which is a cryptography toolkit for python.

### How to run unittests
The unittests are located in a module named test.py and are written in the python unittest framework and are run the standard way.

```
python -m unittest test
```

**Note** To run the tests, python 3 must be linked to `python` in your system path. On most unix systems, python 3 is linked to by `python3`. To run the tests, you need to relink python or change line 71 in `PeerHandler.py` the following way

```diff
-        cmd = "python -u Peer.py nonregister %s %s %s %s %s %s %s" % (name, host, port, ROUTER_HOST, ROUTER_PORT, manualOverride, clockSync)
+        cmd = "python3 -u Peer.py nonregister %s %s %s %s %s %s %s" % (name, host, port, ROUTER_HOST, ROUTER_PORT, manualOverride, clockSync)
```

### How to start the peers independently
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

```
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

```
python -u Peer.py register Peer1 127.0.0.1 8301 127.0.0.1 8300 False True
```

## How to run simulations
In simulations.py a number of configuration values is defined which can be changed to simulate different behaviour. The simulations is written using the standard python unittesting framework and are run the following way
```
python -m unittest simulations.py
```
At the very top of the class, one can change the parameters for the simulation. Note that to repreduce possible errors, we have fixed the random seed in this single-simulation run. Set `RAND_SEED` to `None` to use clear the random seed.

We have also implemented a benchmark script which can be configured to run a series of test and log the results hereof. In the autosim.py file the `DEFAULT_` variables specify the default parameter values used during the simulations. A list variable called `tests` is used to vary the parameters used for the different simulations. The benchmark is run the following way
```
python autosim.py
```
The log files are stored in a folder called `logs`. Note that the automatically gathered statistics include non-protocol errors in the success rates.
