import unittest

from Driver import *


class SimpleVisualTest(P2PTestCase):

    NO_OF_PEERS = 10
    VISUALIZE = False

    @unittest.skip("deactivated")
    def test_visual(self):
        self.peers[0].write_stdin("sendmsg testmessage\n")
        time.sleep(1)
        self.visualize(False)
        for peer in self.peers:
            peer.communicate("q \n")

class TickTest(P2PTestCase):
    NO_OF_PEERS = 2
    USETICKS = True
    RADIO_RANGE = 999999999

    def test_no_tick_no_progress(self):
        self.peers[0].write_stdin("sendmsg testmessage\n")
        with self.assertRaises(subprocess.TimeoutExpired):
            self.peers[1].expect_output("GOTMSG", 1)
        for peer in self.peers:
            peer.communicate("q \n")

    def test_one_tick_onestep_progress(self):
        self.peers[0].write_stdin("sendmsg testmessage\n")
        self.peers[0].write_stdin("sendmsg testmessage\n")
        self.tick()
        self.peers[1].expect_output("GOTMSG", 1)
        with self.assertRaises(subprocess.TimeoutExpired):
            self.peers[1].expect_output("GOTMSG", 1)
        for peer in self.peers:
            peer.communicate("q \n")

    def test_tick_progress(self):
        self.peers[0].write_stdin("sendmsg testmessage\n")
        self.tick()
        self.peers[1].expect_output("GOTMSG", 1)
        for peer in self.peers:
            peer.communicate("q \n")

    def test_two_tick_progress(self):
        self.peers[0].write_stdin("sendmsg testmessage\n")
        self.peers[0].write_stdin("sendmsg testmessage\n")
        self.tick()
        self.peers[1].expect_output("GOTMSG", 1)
        self.tick()
        self.peers[1].expect_output("GOTMSG", 1)
        for peer in self.peers:
            peer.communicate("q \n")

class SimpleVisualTest(P2PTestCase):

    NO_OF_PEERS = 10
    VISUALIZE = True

    @unittest.skip("deactivated")
    def test_visual(self):
        for peer in self.peers:
            peer.communicate("q \n")
