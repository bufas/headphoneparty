import logging
import subprocess
import random
import math
import time
import threading
from io import BufferedReader
from collections import deque
from threading import Lock

VERBOSE = True  # Verbose true does not pipe stderr.
ROUTER_HOST = "127.0.0.1"
ROUTER_PORT = 8300

class PeerHandler(object):
    BUFFER_SIZE = 100

    def __init__(self, name, host, port, manualOverride):
        self.name, self.host, self.port = name, host, port
        self.x, self.y, self.vecX, self.vecY = None, None, None, None
        self.color = None
        self.guiID = None
        self.buffer = deque(maxlen=self.BUFFER_SIZE)
        self.bufferlock = Lock()

        cmd = "python -u Peer.py %s %s %s %s %s %s" % (name, host, port, ROUTER_HOST, ROUTER_PORT, MANUAL_OVERRIDE)
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

        # Start reader
        reader_thread = threading.Thread(name="reader", target=self._reader)
        reader_thread.setDaemon(True)  # Don't wait for thread to exit.
        reader_thread.start()

    def _reader(self):
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise Exception(self.name + " stdout closed while waiting for output")
            line = line.decode("utf-8")
            with self.bufferlock:
                self.buffer.append(line)

            #print("got output (" + self.name + "): " + line)

            if "QUITTING" in line:
                break




    def setLocation(self, peerLoc):
        (x, y, vecX, vecY) = peerLoc
        self.x, self.y, self.vecX, self.vecY = x, y, vecX, vecY

    def __str__(self):
        return self.name

    def adr(self):
        return "%s:%d" % (self.host, self.port)

    def expect_output(self, msg, timeout=0):
        sleep_time = 0.05
        acc_sleep_time = 0
        while True:
            line = None
            with self.bufferlock:
                if len(self.buffer) > 0:
                    line = self.buffer.popleft()
            if not line:
                time.sleep(sleep_time)
                acc_sleep_time += sleep_time
            else:
                if msg in line:
                    return line
            if 0 < timeout <= acc_sleep_time:
                raise subprocess.TimeoutExpired(msg, timeout)

    def expect_ready(self):
        self.expect_output("ready")

    def get_playlist(self):
        self.write_to_stdin("get_playlist\n")
        line = self.expect_output("PLAYLIST#####")
        line = line.strip("PLAYLIST#####").strip()
        playlist = []
        for playlistitem in line.split("####"):
            if not playlistitem == "":
                [song, votes] = playlistitem.split("###")
                voteslst = []
                for vote in votes.split("@@"):
                    if not vote == "":
                        voteparams = vote.split("#")
                        votedict = {}
                        for i in range(0,len(voteparams)-1,2):
                            votedict[voteparams[i]] = voteparams[i+1]
                        voteslst.append(votedict)
                playlist.append({'song': song, 'votes': voteslst})
        return playlist

    def get_top3songs(self):
        self.write_to_stdin("get_top3songs\n")
        line = self.expect_output("TOP3SONGS###")
        line = line.strip("TOP3SONGS###").strip()
        top3 = []
        for songlistitem in line.split("##"):
            if not songlistitem == "":
                [song, votecnt] = songlistitem.split("#")
                top3.append((song, votecnt))
        return top3

    def vote(self, song):
        self.write_to_stdin("vote "+song+"\n")
        self.expect_output("VOTE ADDED", 2)

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
        #Stop read loop - it seems we can't 'communicate' while doing readline
        self.write_to_stdin("say_quit\n")
        try:
            self.expect_output("QUITTING", 1)
        except subprocess.TimeoutExpired:
            raise subprocess.TimeoutExpired("Peer unresponsive, cannot 'communicate'", 1)
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
        # print()
        # if peer.color:
        #     print('Finding peers in range of ' + peer.name + '(' + peer.color + ')')
        # else:
        #     print('Finding peers in range of ' + peer.name)
        peersInRange = []
        meX = peer.x
        meY = peer.y
        for opeer in self.peers:
            if math.pow(meX - opeer.x, 2) + math.pow(meY - opeer.y, 2) < math.pow(self.RADIO_RANGE, 2):
                # if opeer.color:
                #     print(opeer.name + '(' + opeer.color + ') is in range')
                # else:
                #     print(opeer.name + ' is in range')
                peersInRange.append(opeer)

        return peersInRange
