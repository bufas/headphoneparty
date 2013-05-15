import subprocess
import threading
import unittest
from PeerHandler import PeerController
from PeerHandler import PeerHandler
from Router import Router
from Visualizer import Visualizer
import time

class P2PTestCase(unittest.TestCase):
    NO_OF_PEERS = 1
    VISUALIZE = False

    # Simulation params
    TOP_SPEED = 140
    MAX_SPEED_CHANGE = 50
    RADIO_RANGE = 500
    WORLD_SIZE = {'width': 2000, 'height': 2000}  # in centimeters
    USE_TICKS = False

    def setUp(self):
        self.peers = [self.create_peer("P%d" % i, "127.0.0.1", 8500 + i) for i in range(self.__class__.NO_OF_PEERS)]
        self.peer_controller = PeerController(self.peers,
                                              self.WORLD_SIZE,
                                              self.TOP_SPEED,
                                              self.MAX_SPEED_CHANGE,
                                              self.RADIO_RANGE)

        #Start router
        self.router = Router("127.0.0.1", 8300, self.peers, self.peer_controller, self.USE_TICKS)
        self.router.start()
        self.ensure_peers_ready(self.peers)

        if self.VISUALIZE:
            self.visualizer = Visualizer(self.peers, self.peer_controller)

    def tearDown(self):
        for peer in self.peers:
            peer.kill()
        self.router.shutdown()

    def tick(self, num_msgs=1):
        self.router.tick(num_msgs)

    def visualize(self, block=True):
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
        peer = PeerHandler(name, host, port)

        if peer.process.returncode is not None:
            raise Exception("Peer " + peer.name + " quit immediately ")
        return peer

    def ensure_peers_ready(self, peers):
        for peer in peers:
            peer.expect_ready()


class SimpleVisualTest(P2PTestCase):
    NO_OF_PEERS = 10
    VISUALIZE = False

    @unittest.skip("deactivated")
    def test_visual(self):
        self.peers[0].write_to_stdin("sendmsg testmessage\n")
        self.wait_nw_idle()
        self.visualize(False)
        for peer in self.peers:
            peer.communicate("q \n")


class TickTest(P2PTestCase):
    NO_OF_PEERS = 2
    USE_TICKS = True
    RADIO_RANGE = 999999999

    def test_no_tick_no_progress(self):
        self.peers[0].write_to_stdin("sendmsg testmessage\n")
        with self.assertRaises(subprocess.TimeoutExpired):
            self.peers[1].expect_output("GOTMSG", 1)
        for peer in self.peers:
            peer.communicate("q \n")

    def test_one_tick_onestep_progress(self):
        self.peers[0].write_to_stdin("sendmsg testmessage\n")
        self.peers[0].write_to_stdin("sendmsg testmessage\n")
        self.tick()
        self.peers[1].expect_output("GOTMSG", 1)
        with self.assertRaises(subprocess.TimeoutExpired):
            self.peers[1].expect_output("GOTMSG", 1)
        for peer in self.peers:
            peer.communicate("q \n")

    def test_tick_progress(self):
        self.peers[0].write_to_stdin("sendmsg testmessage\n")
        self.tick()
        self.peers[1].expect_output("GOTMSG", 1)
        for peer in self.peers:
            peer.communicate("q \n")

    def test_two_tick_progress(self):
        self.peers[0].write_to_stdin("sendmsg testmessage\n")
        self.peers[0].write_to_stdin("sendmsg testmessage\n")
        self.tick()
        self.peers[1].expect_output("GOTMSG", 1)
        self.tick()
        self.peers[1].expect_output("GOTMSG", 1)
        for peer in self.peers:
            peer.communicate("q \n")


class SimpleVisualPermanentTest(P2PTestCase):
    NO_OF_PEERS = 10
    VISUALIZE = True

    @unittest.skip("deactivated")
    def test_permanent_visual(self):
        for peer in self.peers:
            peer.communicate("q \n")


class JoinTests(P2PTestCase):
    NO_OF_PEERS = 2
    RADIO_RANGE = 999999999
    USE_TICKS = False

    def test_join(self):
        self.peers[0].write_to_stdin("join\n")
        self.peers[0].expect_output("GOT PLAYLIST", 2)
        for peer in self.peers:
            peer.communicate("q \n")

class JoinTestsMany(P2PTestCase):
    NO_OF_PEERS = 50
    RADIO_RANGE = 500
    USE_TICKS = False

    def test_join(self):
        for i in range(len(self.peers)):
            self.peers[i].write_to_stdin("join\n")
            self.peers[i].expect_output("GOT PLAYLIST", 2)
            self.wait_nw_idle()

        for peer in self.peers:
            peer.communicate("q \n")