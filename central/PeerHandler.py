import logging
import subprocess
import random
import math
import time
import threading

VERBOSE = True  # Verbose true does not pipe stderr.
ROUTER_HOST = "127.0.0.1"
ROUTER_PORT = 8300


class PeerHandler(object):
    def __init__(self, name, host, port):
        self.name, self.host, self.port = name, host, port
        self.x, self.y, self.vecX, self.vecY = None, None, None, None
        self.color = None
        self.guiID = None

        cmd = "python -u Peer.py %s %s %s %s %s" % (name, host, port, ROUTER_HOST, ROUTER_PORT)
        if VERBOSE:
            # Do not pipe stderr
            self.process = subprocess.Popen(cmd,
                                            shell=True,
                                            stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE)
        else:
            # Pipe to stderr
            self.process = subprocess.Popen(cmd,
                                            shell=True,
                                            stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE)

    def setLocation(self, peerLoc):
        (x, y, vecX, vecY) = peerLoc
        self.x, self.y, self.vecX, self.vecY = x, y, vecX, vecY

    def __str__(self):
        return self.name

    def adr(self):
        return "%s:%d" % (self.host, self.port)

    def expect_output(self, msg, timeout=0):
        """Wait until stdout contains msg; returns line."""
        stopThread = False

        # Bad solution for timeout:
        # Make a thread that, if not stopped, will after timeout tell peer to shout
        # "TIMEOUT", causing readline() to exit.
        def timeout_logic():
            timeSlept = 0
            while not stopThread:
                if timeSlept >= timeout:
                    self.write_to_stdin("say_timeout \n")
                    break
                time.sleep(0.1)
                timeSlept += 0.1

        if timeout != 0:
            timeout_thread = threading.Thread(name="timeout_thread", target=timeout_logic)
            timeout_thread.setDaemon(True)  # Don't wait for thread to exit.
            timeout_thread.start()

        while True:
            line = self.process.stdout.readline()
            if not line:
                raise Exception(self.name + " stdout closed while waiting for output")
            line = str(line)
            logging.debug("got output (" + self.name + "): " + line)
            if msg in line:
                stopThread = True
                return line
            if "SAY_TIMEOUT" in line:
                raise subprocess.TimeoutExpired(msg, timeout)

    def expect_ready(self):
        self.expect_output("ready")

    def kill(self):
        # Return code is None if process has not finished.
        if self.process.returncode is None:
            logging.warning("WARNING: " + self.name + " did not exit")
            try:
                self.communicate("q \n", 1)
            except subprocess.TimeoutExpired:
                logging.warning("WARNING: " + self.name + " could not exit (TIMEOUT) - FORCING!")
        if self.process.returncode is None:  # If still not finished
            self.process.kill()
            self.process.wait()

    def communicate(self, msg, timeout=None):
        """Feeds msg to stdin, waits for peer to exit, and returns (stdout, stderr)."""
        return self.process.communicate(bytes(msg, "utf-8"), timeout)

    def write_to_stdin(self, msg):
        self.process.stdin.write(bytes(msg, "utf-8"))
        self.process.stdin.flush()


class PeerController():
    """The purpose of the class is to emulate a physical space to test range and effect of wireless communication.
    Average walking speed will be 1.4, which corresponds to 5 km/h. Maximal speed in this configuration is 7.12km/h"""

    def __init__(self, peers, worldSize, topSpeed, maxSpeedChange, radioRange):
        self.peers = peers
        self.worldSize = worldSize
        self.TOP_SPEED, self.MAX_SPEED_CHANGE, self.RADIO_RANGE = topSpeed, maxSpeedChange, radioRange

        for peer in self.peers:
            peer.setLocation(self.generateNewPeerLocation())

    def generateNewPeerLocation(self):
        x = random.uniform(0, self.worldSize['width'])          # x coord of peer spawn
        y = random.uniform(0, self.worldSize['height'])         # y coord of peer spawn
        vecX = random.uniform(-self.TOP_SPEED, self.TOP_SPEED)  # x coord of peer speed vector
        vecY = random.uniform(-self.TOP_SPEED, self.TOP_SPEED)  # y coord of peer speed vector
        return x, y, vecX, vecY

    def movePeers(self):
        for peer in self.peers:
            # Check the world bounds and flip the vector to avoid collision
            if peer.x + peer.vecX > self.worldSize['width'] or peer.x + peer.vecX < 0:
                peer.vecX = -peer.vecX
            if peer.y + peer.vecY > self.worldSize['height'] or peer.y + peer.vecY < 0:
                peer.vecY = -peer.vecY

            # Move
            peer.x += peer.vecX
            peer.y += peer.vecY

            # Change the vector to change speed and direction of peer
            peer.vecX = random.uniform(
                -self.TOP_SPEED if peer.vecX < -self.TOP_SPEED + self.MAX_SPEED_CHANGE else peer.vecX - self.MAX_SPEED_CHANGE,
                self.TOP_SPEED if peer.vecX > self.TOP_SPEED - self.MAX_SPEED_CHANGE else peer.vecX + self.MAX_SPEED_CHANGE)
            peer.vecY = random.uniform(
                -self.TOP_SPEED if peer.vecY < -self.TOP_SPEED + self.MAX_SPEED_CHANGE else peer.vecY - self.MAX_SPEED_CHANGE,
                self.TOP_SPEED if peer.vecY > self.TOP_SPEED - self.MAX_SPEED_CHANGE else peer.vecY + self.MAX_SPEED_CHANGE)

    def findPeersInRange(self, peer):
        print()
        if peer.color:
            print('Finding peers in range of ' + peer.name + '(' + peer.color + ')')
        else:
            print('Finding peers in range of ' + peer.name)
        peersInRange = []
        meX = peer.x
        meY = peer.y
        for opeer in self.peers:
            if math.pow(meX - opeer.x, 2) + math.pow(meY - opeer.y, 2) < math.pow(self.RADIO_RANGE, 2) and opeer != peer:
                if opeer.color:
                    print(opeer.name + '(' + opeer.color + ') is in range')
                else:
                    print(opeer.name + ' is in range')
                peersInRange.append(opeer)

        return peersInRange
