import unittest
import subprocess

from Driver import *


class SimpleMsgTest(P2PTestCase):

    NO_OF_PEERS = 10
    VISUALIZE = False

    def test_visual(self):
        self.peers[0].write_stdin("sendmsg testmessage\n")
        time.sleep(1)
        self.visualize(False)
        for peer in self.peers:
            peer.communicate("q \n")

class SimpleVisualTest(P2PTestCase):

    NO_OF_PEERS = 10
    VISUALIZE = True

    @unittest.skip("deactivated")
    def test_visual(self):
        for peer in self.peers:
            peer.communicate("q \n")
