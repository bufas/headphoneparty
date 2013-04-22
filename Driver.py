from xmlrpc.client import ServerProxy
import subprocess
import random
import logging
import math
import tkinter as tk
import unittest
import time
import threading
from threading import Condition
from threading import Lock
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler
import socketserver


# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

# Threaded RPC for concurrency.
# Field 'allow_reuse_address' inserted to avoid tcp "address already in use".
# See http://www.dalkescientific.com/writings/diary/archive/2005/04/21/using_xmlrpc.html.
class ThreadedXMLRPCServer(socketserver.ThreadingMixIn, SimpleXMLRPCServer):
    allow_reuse_address = True


# Verbose true does not pipe stderr.
VERBOSE = True
DRIVERHOST = "127.0.0.1"
DRIVERPORT = 8300

class Peer(object):
    def __init__(self, name, host, port):
        self.name, self.host, self.port = name, host, port
        self.x, self.y, self.vecX, self.vecY = None, None, None, None
        self.color = None
        self.guiID = None

        cmd = "python -u peer.py %s %s %s %s %s" \
            % (name, host, port, DRIVERHOST, DRIVERPORT)
        if VERBOSE: # Do not pipe stderr.
            self.process = subprocess.Popen(cmd,
                                       shell=True,
                                       stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE)
        else:
            self.process = subprocess.Popen(cmd,
                                       shell=True,
                                       stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)

    def setLocation(self, peerLoc):
        (x,y,vecX,vecY) = peerLoc
        self.x, self.y, self.vecX, self.vecY = x, y, vecX, vecY

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def adr(self):
        return "%s:%d" % (self.host, self.port)

    def expect_output(self, msg, timeout = 0):
        """Wait until stdout contains msg; returns line."""
        stopThread = False

        # Bad solution for timeout:
        # Make a thread that, if not stopped, will after timeout tell peer to shout "TIMEOUT", causing readline() to exit.
        # TODO: Find better approach
        def timeout_logic():
            timeSlept = 0
            while True:
                if stopThread:
                    break
                if timeSlept >= timeout:
                    self.write_stdin("say_timeout \n")
                    break
                time.sleep(0.1)
                timeSlept += 0.1

        if timeout != 0:
            timeout_thread = threading.Thread(name="timeout_thread", target=timeout_logic)
            timeout_thread.setDaemon(True) # Don't wait for thread to exit.
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
        # Returncode is None if process has not finished.
        if self.process.returncode is None:
            logging.warning("WARNING: " + self.name + " did not exit")
            try:
                self.communicate("q \n", 1);
            except subprocess.TimeoutExpired:
                logging.warning("WARNING: " + self.name + " could not exit (TIMEOUT) - FORCING!")
        if self.process.returncode is None: # If still not finished
            self.process.kill()
            self.process.wait()

    def communicate(self, msg, timeout = None):
        """Feeds msg to stdin, waits for peer to exit, and returns (stdout, stderr)."""
        return self.process.communicate(bytes(msg, "utf-8"), timeout)

    def write_stdin(self, msg):
        self.process.stdin.write(bytes(msg, "utf-8"))
        self.process.stdin.flush()


class Visualizer(tk.Frame):
    colors = ['black', 'magenta', 'red', 'blue', 'green', 'gray', 'orange', 'DeepPink', 'Tan', 'Navy']
    GUI_SCALE = 5

    def __init__(self, peers, peer_controller):
        self.peers = peers
        self.peer_controller = peer_controller
        self.lastColorAssigned = 0

        tk.Frame.__init__(self, None)

        canvasWidth = self.peer_controller.worldSize['width'] / self.GUI_SCALE
        canvasHeight = self.peer_controller.worldSize['height'] / self.GUI_SCALE

        tk.Button(self, text='Move', command=self.buttonAction).pack()
        tk.Button(self, text='Who can first peer reach?', command=lambda: self.peer_controller.findPeersInRange(self.peers[0])).pack()
        self.canvas = tk.Canvas(self, width=canvasWidth, height=canvasHeight)

        self.pack()

        self.drawWorld()
        self.mainloop()

    def buttonAction(self):
        self.peer_controller.movePeers()
        self.drawWorld()


    def drawPeer(self, peer):
        peer.color = self.colors[self.lastColorAssigned % len(self.colors)]
        self.lastColorAssigned += 1

        scaledRadioRange = self.peer_controller.RADIO_RANGE / self.GUI_SCALE
        squareID = self.canvas.create_rectangle(peer.x, peer.y, peer.x + 5, peer.y + 5, outline=peer.color, fill=peer.color)
        circleID = self.canvas.create_oval(peer.x - scaledRadioRange + 3, peer.y - scaledRadioRange + 3,
                                           peer.x + scaledRadioRange + 3, peer.y + scaledRadioRange + 3,
                                           outline=peer.color)

        peer.guiID = (squareID, circleID)

    def drawWorld(self):
        # Move all peers
        for peer in self.peers:
            if peer.guiID is None:
                self.drawPeer(peer)

            x = peer.x
            y = peer.y
            x /= self.GUI_SCALE
            y /= self.GUI_SCALE
            scaledRadioRange = self.peer_controller.RADIO_RANGE / self.GUI_SCALE

            (squareID, circleID) = peer.guiID

            self.canvas.coords(squareID, x, y, x + 5, y + 5)
            self.canvas.coords(circleID, x - scaledRadioRange + 3, y - scaledRadioRange + 3,
                               x + scaledRadioRange + 3, y + scaledRadioRange + 3)

        # Redraw the canvas
        self.canvas.pack()

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
        return x,y,vecX,vecY

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
            # Todo this could be more sophisticated...
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

class Router:
    def __init__(self, host, port, peers, peer_controller, useTicks):
        self.host, self.port = host, port
        self.peer_controller = peer_controller
        self.peers = peers
        self.msg_queue = []
        self.msg_lock = Lock()
        self.msg_cond = Condition(self.msg_lock)
        self.useTicks = useTicks
        self.peer_can_send = {}
        self.queue_was_empty = True

        # Init for ticks
        for peer in self.peers:
            self.peer_can_send[peer.name] = 0

    def _server(self):
        print('Starting driver on: %s:%s' % (self.host, self.port))
        try:
            self.rpc_server.serve_forever()
        except ValueError: # Thrown upon exit :(
            pass

    def tick(self, num_msgs):
        with self.msg_lock:
            for peer in self.peers:
                self.peer_can_send[peer.name] = num_msgs
            self.msg_cond.notify()

    def wait_queue_empty(self):
        # Check twice with small interval
        while True:
            with self.msg_lock:
                if len(self.msg_queue) > 0:
                    self.msg_cond.wait()
                else:
                    if self.queue_was_empty:
                        break
                    else:
                        self.queue_was_empty = True
                        time.sleep(0.5)

    def start(self):

        # Create server
        self.rpc_server = ThreadedXMLRPCServer((self.host, self.port),
                                        requestHandler=RequestHandler)
        self.rpc_server.register_introspection_functions()

        # Register RPC functions.
        self.rpc_server.register_function(self.ForwardMessage)

        server_thread = threading.Thread(name="server", target=self._server)
        server_thread.setDaemon(True) # Don't wait for server thread to exit.
        server_thread.start()

        queue_thread = threading.Thread(name="queue", target=self._queue_handler)
        queue_thread.setDaemon(True) # Don't wait for server thread to exit.
        queue_thread.start()

    def shutdown(self):
        self.rpc_server.server_close()

    def ForwardMessage(self, peer_name, msg):
        #Find peer
        #TODO: IMPROVE
        sender_peer = None
        for peer in self.peers:
            if peer.name == peer_name:
                sender_peer = peer
                break
        self.msg_lock.acquire()
        self.msg_queue.append((sender_peer,msg))
        self.queue_was_empty = False
        self.msg_cond.notify()
        self.msg_lock.release()
        return ''

    def _queue_handler(self):
        while True:
            with self.msg_lock:
                if len(self.msg_queue) == 0:
                    self.msg_cond.wait()
                for i in range(len(self.msg_queue)):
                    (sender_peer, msg) = self.msg_queue[i]
                    if self.useTicks == False or (self.peer_can_send[sender_peer.name] and self.peer_can_send[sender_peer.name] > 0):
                        self.msg_queue.pop(i)
                        if self.useTicks:
                              self.peer_can_send[sender_peer.name] -= 1
                        self._do_forward_msg(sender_peer, msg)
                        break

    def _do_forward_msg(self, sender_peer, msg):
        peersInRange = self.peer_controller.findPeersInRange(sender_peer)
        for peer in peersInRange:
            if peer != sender_peer:
                s = ServerProxy('http://' + peer.adr())
                s.ReceiveMsg(sender_peer.name, str(msg))


class P2PTestCase(unittest.TestCase):

    NO_OF_PEERS = 1
    VISUALIZE = False

    # Simulation params
    TOP_SPEED = 140
    MAX_SPEED_CHANGE = 50
    RADIO_RANGE = 500
    WORLD_SIZE = {'width': 2000, 'height': 2000}  # in centimeters
    USETICKS = False

    def setUp(self):
        self.peers = [self.create_peer("P%d" % i, "127.0.0.1", 8400 + i)
                     for i in range(self.__class__.NO_OF_PEERS)]
        self.peer_controller = PeerController(self.peers, self.WORLD_SIZE, self.TOP_SPEED, self.MAX_SPEED_CHANGE, self.RADIO_RANGE)
        #Start router
        self.router = Router(DRIVERHOST, DRIVERPORT, self.peers, self.peer_controller, self.USETICKS)
        self.router.start()
        self.ensure_peers_ready(self.peers)

        if self.VISUALIZE:
            self.visualizer = Visualizer(self.peers, self.peer_controller)

    def tearDown(self):
        for peer in self.peers:
            peer.kill()
        self.router.shutdown()

    def tick(self, num_msgs = 1):
        self.router.tick(num_msgs)

    def visualize(self, block = True):
        if block:
            self._do_visualize()
        else:
            thread = threading.Thread(name="visualize", target=self._do_visualize, args=[])
            thread.start()

    def _do_visualize(self):
        self.visualizer = Visualizer(self.peers, self.peer_controller)

    def wait_nw_idle(self):
        self.router.wait_queue_empty()

    def assertContains(self, msg, msg_part):
        try:
            self.assertTrue(msg_part in msg)
        except AssertionError:
            raise AssertionError("Msg: %s does not contain %s"
                                 % (msg, msg_part))

    def assertNotContains(self, msg, msg_part):
        try:
            self.assertFalse(msg_part in msg)
        except AssertionError:
            raise AssertionError("Msg: %s does  contain %s"
                                 % (msg, msg_part))

    def create_peer(self, name, host, port):
        peer = Peer(name, host, port)

        if peer.process.returncode is not None:
            raise Exception("Peer " + peer.name + " quit immediately ")
        return peer


    def ensure_peers_ready(self, peers):
        for peer in peers:
            peer.expect_ready()






if __name__ == '__main__':

    # Setup logging to stderr.
    # Use either WARN, DEBUG, ALL, ...
    logging.basicConfig(
        level=logging.WARN,
        format='(%(threadName)-10s) %(message)s')

    # Run tests with cmd line interface.
    # All tests: "python -m unittest -v test"
    # Class of tests: "python -m unittest -v test.MoreTests"
    # Specific test:
    #   "python -m unittest test.MoreTests.test_helloes_carry_plist_on"
    unittest.main()