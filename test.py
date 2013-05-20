import subprocess
import threading
import unittest
from Crypto.PublicKey import RSA
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
    CLOCK_SYNC = False
    MANUAL_OVERRIDE = True

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
        self.router.activate_queue()

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
        peer = PeerHandler(name, host, port, self.MANUAL_OVERRIDE, self.CLOCK_SYNC)

        if peer.process.returncode is not None:
            raise Exception("Peer " + peer.name + " quit immediately ")
        return peer

    def ensure_peers_ready(self, peers):
        for peer in peers:
            peer.expect_ready()

    def has_song_with_votes_in_playlist(self, playlist, song):
        for playlistitem in playlist:
            if playlistitem['song_name'] == song:
                if len(playlistitem['votes']) > 0:
                    return True
                return False
        return False

    def assert_song_in_playlist(self, playlist, song):
        self.assertTrue(self.has_song_with_votes_in_playlist(playlist,song), "Song " + song + " was expected in playlist")


class ClockTest(P2PTestCase):
    NO_OF_PEERS = 25
    CLOCK_SYNC = True

    def test_clock(self):
        min = 2**64
        max = -9999

        time.sleep(60)

        for p in self.peers:
            logical = p.get_logicalClock()
            if logical < min:
                min = logical
            if logical > max:
                max = logical

        self.assertGreaterEqual(50, max-min, "The clocks drifted too far apart")


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

class JoinTimeoutTests(P2PTestCase):
    NO_OF_PEERS = 1
    USE_TICKS = False
    MANUAL_OVERRIDE = False

    def test_jointimeout_retry(self):
        self.peers[0].write_to_stdin("join\n")
        self.peers[0].expect_output("JOIN RETRY", 4)
        for peer in self.peers:
            peer.communicate("q \n")


class JoinTestsMany(P2PTestCase):
    NO_OF_PEERS = 50
    RADIO_RANGE = 500
    USE_TICKS = False

    def test_join(self):
        #Test correct setup - that peers are in range
        for peer in self.peers:
            if len(self.peer_controller.findPeersInRange(peer)) == 0:
                self.fail("IGNORE (RERUN TEST): Incorrect setup, a peer is out of range")

        for i in range(len(self.peers)):
            self.peers[i].write_to_stdin("join\n")
            self.peers[i].expect_output("GOT PLAYLIST", 60)
            self.wait_nw_idle()

        for peer in self.peers:
            peer.communicate("q \n")

class OutOfRange(P2PTestCase):
    NO_OF_PEERS = 10
    RADIO_RANGE = 500
    USE_TICKS = False

    @unittest.skip("not completed... TODO!")
    def test_outofrange(self):
        for i in range(self.NO_OF_PEERS):
            self.peers[i].setLocation(self,(1,1,1,1))
        for i in range(len(self.peers)):
            self.peers[i].write_to_stdin("join\n")
            self.peers[i].expect_output("GOT PLAYLIST", 1)
            self.wait_nw_idle()
        self.peers[2].setLocation(self, (10,10,1,1))        # Move peer 2 away
        self.peers[3].write_to_stdin("vote LimboSong2\n")
        self.peers[4].write_to_stdin("vote LimboSong2\n")
        self.peers[1].setLocation(self,(1,1,1,1))           # Move peer 2 back

class DropMsg(P2PTestCase):
    NO_OF_PEERS = 2
    RADIO_RANGE = 500000
    USE_TICKS = False

    def test_dropmsg(self):
        for i in range(self.NO_OF_PEERS):
            self.peers[i].write_to_stdin("join\n")
            self.peers[i].expect_output("GOT PLAYLIST", 2)
            self.wait_nw_idle()
        self.peers[1].write_to_stdin("vote LimboSang2\n")
        self.peers[1].expect_output("DROPPED MSG",2)

class SimpleVoteTests(P2PTestCase):
    NO_OF_PEERS = 2
    RADIO_RANGE = 999999999
    USE_TICKS = False

    def test_add_others_vote(self):
        song = "abc"
        self.peers[0].write_to_stdin("vote "+song+"\n")
        self.peers[1].expect_output("VOTE ADDED", 2)
        print(self.peers[0].get_playlist())
        self.assert_song_in_playlist(self.peers[1].get_playlist(), song)

        for peer in self.peers:
            peer.communicate("q \n")

    def test_add_own_vote(self):
        song = "abc"
        self.peers[0].write_to_stdin("vote "+song+"\n")
        self.peers[0].expect_output("VOTE ADDED", 2)
        print(self.peers[0].get_playlist())
        self.assert_song_in_playlist(self.peers[0].get_playlist(), song)

        for peer in self.peers:
            peer.communicate("q \n")

    def test_invalid_vote(self):
        self.peers[0].write_to_stdin("test_create_fake_vote\n")
        self.peers[1].expect_output("VOTE REJECTED", 2)
        self.assertEqual(self.peers[1].get_playlist(), [])

        for peer in self.peers:
            peer.communicate("q \n")

class CompareSongs1PeerTests(P2PTestCase):
    NO_OF_PEERS = 1
    USE_TICKS = False

    def test_alphabetical_order(self):
        song1 = "A"
        song2 = "B"
        song3 = "C"

        self.peers[0].vote(song1)
        self.peers[0].vote(song3)
        self.peers[0].vote(song2)

        top3songs = self.peers[0].get_top3songs()
        (top1song, _) = top3songs[0]
        (top2song, _) = top3songs[1]
        (top3song, _) = top3songs[2]
        self.assertEqual(top1song, song1)
        self.assertEqual(top2song, song2)
        self.assertEqual(top3song, song3)

    def test_move_song_to_top3(self):
        song1 = "A"
        song2 = "B"
        song3 = "C"
        song4 = "D"

        self.peers[0].vote(song2)
        self.peers[0].vote(song3)
        self.peers[0].vote(song4)
        self.peers[0].vote(song1)

        top3songs = self.peers[0].get_top3songs()
        (top1song, _) = top3songs[0]
        (top2song, _) = top3songs[1]
        (top3song, _) = top3songs[2]
        self.assertEqual(top1song, song1)
        self.assertEqual(top2song, song2)
        self.assertEqual(top3song, song3)


    def test_drop_identical_votes(self):
        song = "A"
        self.peers[0].vote(song)
        self.peers[0].vote(song)

        playlst = self.peers[0].get_playlist()
        self.assertEqual(len(playlst[0]['votes']), 1)

class CompareSongs3PeersTests(P2PTestCase):
    NO_OF_PEERS = 3
    RADIO_RANGE = 99999999
    USE_TICKS = False

    def test_votecnt_order(self):
        song3votes = "C"
        song2votes = "A"
        song1votes = "B"

        self.peers[0].vote(song3votes)
        self.peers[1].vote(song3votes)
        self.peers[2].vote(song3votes)

        self.peers[0].vote(song1votes)

        self.peers[0].vote(song2votes)
        self.peers[1].vote(song2votes)

        self.wait_nw_idle()

        top3songs = self.peers[0].get_top3songs()
        (top1song, _) = top3songs[0]
        (top2song, _) = top3songs[1]
        (top3song, _) = top3songs[2]
        self.assertEqual(top1song, song3votes)
        self.assertEqual(top2song, song2votes)
        self.assertEqual(top3song, song1votes)

class PlaySongTests(P2PTestCase):
    NO_OF_PEERS = 1
    USE_TICKS = False

    def test_play_right_song(self):
        song1 = "A"
        song2 = "B"

        self.peers[0].vote(song1)
        self.peers[0].vote(song2)

        self.peers[0].write_to_stdin("play_next\n")
        self.peers[0].expect_output("PLAYING " + song1, 2)

    def test_remove_played_song(self):
        song1 = "A"
        song2 = "B"
        initial_nr_of_songs = 2

        self.peers[0].vote(song1)
        self.peers[0].vote(song2)

        self.peers[0].write_to_stdin("play_next\n")
        self.peers[0].expect_output("PLAYING " + song1, 2)

        # TOP 3
        top3songs = self.peers[0].get_top3songs()
        self.assertEqual(len(top3songs), initial_nr_of_songs - 1)

        (nextsong, _) = top3songs[0]
        self.assertEqual(nextsong, song2)

        # Playlist
        playlist = self.peers[0].get_playlist()
        self.assertEqual(len(playlist), initial_nr_of_songs - 1)
        self.assertEqual(playlist[0]['song_name'], song2)
        

    def test_add_new_song_top3_on_play(self):
        song1 = "A"
        song2 = "B"
        song3 = "C"
        song4 = "D"

        self.peers[0].vote(song1)
        self.peers[0].vote(song2)
        self.peers[0].vote(song3)
        self.peers[0].vote(song4)

        self.peers[0].write_to_stdin("play_next\n")
        self.peers[0].expect_output("PLAYING " + song1, 2)

        top3songs = self.peers[0].get_top3songs()
        (top1song, _) = top3songs[0]
        (top2song, _) = top3songs[1]
        (top3song, _) = top3songs[2]
        self.assertEqual(top1song, song2)
        self.assertEqual(top2song, song3)
        self.assertEqual(top3song, song4)

class TopSyncTests(P2PTestCase):
    NO_OF_PEERS = 2
    RADIO_RANGE = 5
    USE_TICKS = False

    def test_send_top_votes(self):
        # Assumes TOP _3_
        song1 = "A"
        song2 = "B"
        song3 = "C"
        song4 = "D"

        # Ensure in range
        self.peers[0].setLocation((1,1,1,1))
        self.peers[1].setLocation((1,1,1,1))

        self.peers[0].vote(song1)
        self.peers[0].vote(song2)
        self.peers[0].vote(song3)
        self.peers[0].vote(song4)

        self.wait_nw_idle()
        # Ensure votes is not older than this point
        self.peers[0].clearBuffer()
        self.peers[1].clearBuffer()

        # Play, and see if votes for next song (D) is sent to other peer
        self.peers[0].write_to_stdin("play_next\n")
        self.peers[0].expect_output("SHOUTING VOTES", 2)
        self.peers[1].expect_output("GOT VOTESLIST of " + song4, 2)

    def test_received_top_songs_merged(self):
        # Assumes TOP _3_
        song1 = "A"
        song2 = "B"
        song3 = "C"
        song4 = "D"
        
        # Ensure P1 does not see votes
        self.peers[0].setLocation((1,1,1,1))
        self.peers[1].setLocation((10,10,1,1))

        self.peers[0].vote(song1)
        self.peers[0].vote(song2)
        self.peers[0].vote(song3)
        self.peers[0].vote(song4)

        self.wait_nw_idle()
        # Ensure votes is not older than this point
        self.peers[0].clearBuffer()
        self.peers[1].clearBuffer()

        # Move closer
        self.peers[1].setLocation((1,1,1,1))

        # Play, wait until votes received
        self.peers[0].write_to_stdin("play_next\n")
        self.peers[1].expect_output("GOT VOTESLIST", 2)

        # Check songs merged (since was out of range, these are the only ones)
        playlist = self.peers[1].get_playlist()
        self.assertEqual(len(playlist), 1)
        self.assertEqual(playlist[0]['song_name'], song4)
