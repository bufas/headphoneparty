from test import P2PTestCase 
import random
import unittest
from Visualizer import Visualizer
from operator import itemgetter, attrgetter
import time


class RandomVoting(P2PTestCase):
    # Comment values says the value tested with seed 2080896176
    NO_OF_PEERS = 25 #25
    RADIO_RANGE = 600 #600
    USE_TICKS = False
    TOP_SPEED = 75 #75
    RAND_SEED = 2080896176 # 2080896176

    def test_randomVotes(self):

        self.peer_controller.visualize(block=False)
        

        peersKilled = 0
        peers_wasoutofrange = []

        songs = {"A":0,"B":0,"C":0,
                 "D":0,"E":0,"F":0} #A-F

        hasvotedfor = {}

        lastBiggestConnectedSet = None
        for j in range(100): # 100
            time.sleep(0.05) # 0.05

            peeridx = self.myRandom.randint(0,len(self.peers)-1)
            peer = self.peers[peeridx]

            if j > 0 and self.myRandom.randint(0,100) < 60: # 60, Not first time - need out of range check first
                self.peer_controller.movePeers()
            if self.myRandom.randint(0,100) < 15: #15
                if not peer.name in hasvotedfor.keys():
                    hasvotedfor[peer.name] = []
                songNo = self.myRandom.randint(0,5)
                if not songNo in hasvotedfor[peer.name]:
                    songOfChoice = list(songs.keys())[songNo]
                    peer.vote(songOfChoice)
                    songs[songOfChoice] += 1
                    hasvotedfor[peer.name].append(songNo)
            if self.myRandom.randint(0,100) < 5: #5
                peer.kill()
                peersKilled += 1
                newPeer = self.create_peer("P%d" % (self.NO_OF_PEERS + peersKilled), "127.0.0.1",
                                           8500 + self.NO_OF_PEERS + peersKilled)
                newPeer.expect_ready()
                self.peer_controller.replacePeer(peeridx, newPeer)
                self.peers[peeridx].write_to_stdin("join\n")
                    
            # Out of range check
            settosearch = lastBiggestConnectedSet
            if not settosearch:
                settosearch = self.peers
            biggestConnectedSet = []
            for p in settosearch:
                reachable = [p]
                cont = True
                while cont:
                    cont = False
                    for rp in reachable:
                        for pinrange in self.peer_controller.findPeersInRange(rp):
                            if not pinrange in reachable:
                                reachable.append(pinrange)
                                cont = True
                if len(reachable) > len(biggestConnectedSet):
                    biggestConnectedSet = reachable
            self.lastBiggestConnectedSet = biggestConnectedSet
            for p in self.peers:
                if (not p in biggestConnectedSet) and (not p in peers_wasoutofrange):
                    peers_wasoutofrange.append(p)
                    

        self.wait_nw_idle()
        for p in peers_wasoutofrange:
            if p in self.peers and len(self.peer_controller.findPeersInRange(p)) > 1:
                p.write_to_stdin("join\n")
                try:
                    p.expect_output("GOT PLAYLIST", 2)
                except Exception:
                    pass
        self.wait_nw_idle()
        #time.sleep(60)

        peersinrange = []
        peersoutofrange = []
        for p in self.peers:
            if not p in peers_wasoutofrange:
                peersinrange.append(p.name)
            else:
                peersoutofrange.append(p.name)
        print("PEERS IN RANGE " + str(peersinrange))
        print("PEERS OUT OF RANGE " + str(peersoutofrange))            
        #time.sleep(7)


        # Check playlists
        # Disabled: Since no out-of-range sync is done on the rest of the playlist, we cannot make sure it is in sync
        # However, we can say that peers that has always been in range of each other should have identical playlists
        syncedplaylist = None
        for x in self.peers:
            if not x in peers_wasoutofrange:
                playlist = [(song['song_name'], len(song['votes'])) for song in x.get_playlist()]
                playlist = sorted(playlist, key=itemgetter(1, 0))
                if not syncedplaylist:
                    syncedplaylist = playlist
                else:
                    self.assertEqual(syncedplaylist, playlist)

                # Check that playlist equal to votes given - as explained, this cannot be done since voting peers might be out of range
                #peersongs = [song['song_name'] for song in playlist]
                #for key,value in songs.items():
                #    if value != 0:
                #        self.assertTrue(key in peersongs, "Song " + key + " should be in playlist of " + x.name)
                #    for j in playlist:
                #        if j['song_name'] == key:
                #            self.assertEqual(len(j['votes']), value)

        # Play song
        for peer in self.peers:
            peer.write_to_stdin("play_next\n")
            peer.expect_output("PLAYING", 60, altmsgs=["NOTHING"]) # Long timeout, to allow for long queues


        def check_top_equal(peerlst):
            top = None
            for peer in peerlst:
                toplst = peer.get_top3songs()
                if not top:
                    top = toplst
                else:
                    self.assertEqual(top, toplst)

        peerstotest = [p for p in self.peers]
        connsets = []
        while len(peerstotest) > 0:
            centerpeer = peerstotest.pop(0)
            inrange = [centerpeer]
            changed = True
            while changed:
                changed = False
                for p in inrange:
                    r = self.peer_controller.findPeersInRange(p)
                    for rp in r:
                        if not rp in inrange:
                            changed = True
                            inrange.append(rp)
                        if rp in peerstotest:
                            peerstotest.remove(rp)
            connsets.append(inrange)
            check_top_equal(inrange)

        print("CONNECTED SETS")
        for connset in connsets:
            print(str([p.name for p in connset]))

        #time.sleep(7)

        #self.peer_controller.endVisualize()
