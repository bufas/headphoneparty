from xmlrpc.client import ServerProxy
import logging
import sys
import re
import threading
from threading import Lock
from threading import RLock
from datetime import datetime
import time
from RpcHelper import RequestHandler, ThreadedXMLRPCServer

from KeyDistributer import KeyDistributer

from clockSync import Clock

NR_PLAYLISTS_PREFERRED_ON_JOIN = 5
PLAYLIST_RECV_TIMEOUT_ON_JOIN = 3 #secs (for simulation, not real life)
OUT_OF_RANGE_CHECK_INTERVAL = 5 #secs
OUT_OF_RANGE_TIME_LIMIT = 60 #secs
LOCK_TOP = 3

class Peer(object):
    def __init__(self, name, host, port, driverHost, driverPort, manualOverride):
        self.name, self.host, self.port = name, host, port
        self.driverHost, self.driverPort = driverHost, driverPort
        self.manualOverride = manualOverride

        # [{'song': 'Britney Spears - Toxic', 'votes': [{'peer_name': 'P1', 'vote': 'signature_on_song', 'pk': ..., 'pksign': ...}, {'peer_name': 'P2', 'vote': '...', ...}]]
        self.playlist = []
        self.playlistLock = Lock()

        self.clock = Clock(self)

        keydist = KeyDistributer()
        self.sk, self.pk, self.pksign = keydist.createKeyPair()

        self.msg_count = 0
        self.MSG_IDS_SEEN_MAXSIZE = 1000
        self.msg_ids_seen = [-1] * self.MSG_IDS_SEEN_MAXSIZE
        self.msg_ids_seen_nextindex = 0
        self.msg_ids_seen_lock = RLock()

        self.playlist_request_id = None
        self.playlists_received = 0

        self.hasJoined = False

        self._time_since_last_msg = 0
        self._time_since_last_msg_lock = Lock()

        self._top = [None] * LOCK_TOP   # [('song', 42 votes), (...)]
        self._toplock = Lock()

    def start(self):
        # Create server
        self.rpc_server = ThreadedXMLRPCServer((self.host, self.port), requestHandler=RequestHandler)
        self.rpc_server.register_introspection_functions()

        # Register RPC functions.
        self.rpc_server.register_function(self.ReceiveMsg)

        server_thread = threading.Thread(name="server", target=self._server)
        server_thread.setDaemon(True)  # Don't wait for server thread to exit.
        server_thread.start()

        if not self.manualOverride:
            out_of_range_check_thread = threading.Thread(name="out_of_range_check_thread", target=self._check_out_of_range)
            out_of_range_check_thread.setDaemon(True)  # Don't wait for server thread to exit.
            out_of_range_check_thread.start()

        print("ready")

        self._main_loop()

    def _check_out_of_range(self):
        while True:
            time.sleep(OUT_OF_RANGE_CHECK_INTERVAL)
            if self.hasJoined:
                with self._time_since_last_msg_lock:
                    self._time_since_last_msg += OUT_OF_RANGE_CHECK_INTERVAL
                    if self._time_since_last_msg > OUT_OF_RANGE_TIME_LIMIT:
                        self.hasJoined = False
                        self._join()
                        self._time_since_last_msg = 0


    def _join(self):
        self.playlists_received = 0
        self.playlist_request_id = self._gen_msg_id()
        self._send_msg("GETLIST", {'request_id': self.playlist_request_id})
        if not self.manualOverride:
            # Start join timeout
            join_timeout_thread = threading.Thread(name="join", target=self._join_timeout)
            join_timeout_thread.setDaemon(True)  # Don't wait for thread to exit.
            join_timeout_thread.start()


    def _join_timeout(self):
        time.sleep(PLAYLIST_RECV_TIMEOUT_ON_JOIN)
        if not self.hasJoined:
            self._join() # Retry

    def ReceiveMsg(self, msg_id, sender_peer_name, msgtype, argdict):
        # For some reason argdict values has turned into lists
        txt = self.name + ": GOTMSG of type " + msgtype + " from peer " + sender_peer_name + ": " + str(argdict)
        logging.debug(txt)
        if self._shouldDropMsg(msg_id):
            logging.debug("DROPPEDMSG")
            print("DROPPED MSG")
        else:
            print(txt)
            if msgtype == "TXTMSG":
                self._handleTextMessage(sender_peer_name, str(argdict['msg']))
            elif msgtype == "VOTE":
                logging.debug("HANDLE VOTE")
                self._forward_msg(msg_id, sender_peer_name, msgtype, argdict) # Forward
                self._handleVote(sender_peer_name, str(argdict['song']), str(argdict['vote']), str(argdict['pk']), str(argdict['pksign']))
            elif msgtype == "VOTES":
                self._handleVotes(str(argdict['song']), argdict['votes'])
            elif msgtype == "GETLIST":
                logging.debug("GETLIST!")
                self._send_playlist(argdict['request_id'])
            elif msgtype == "PLAYLIST":
                logging.debug("PLAYLIST!")
                print("GOT PLAYLIST")
                self._handle_playlist(sender_peer_name, argdict['request_id'], argdict['playlist'], argdict['sign'], argdict['pk'], argdict['pksign'])
            elif msgtype == "CLOCKSYNC":
                (t, s) = argdict['message']
                self.clock.recv(t, s)
        return ''

    def _play_next(self):
        with self.playlistLock:
            with self._toplock:
                if self._top[0]:
                    (nextsong, _) = self._top[0]

                    # Clean up
                    for i in range(0, LOCK_TOP-1):
                        self._top[i] = self._top[i+1]
                    self._top[LOCK_TOP-1] = None

                    # Add new song to top
                    maxcnt = 0
                    maxsong = None
                    for playlistitem in self.playlist:
                        if self._compare_songs((playlistitem['song'], len(playlistitem['votes'])), (maxsong, maxcnt)):
                            maxcnt = len(playlistitem['votes'])
                            maxsong = playlistitem['song']
                    if maxsong:
                        self._flush_top(maxsong, maxcnt)

                    # Tell
                    playtxt = "PLAYING " + nextsong
                    logging.debug(playtxt)
                    print(playtxt)


    def _addMsgId(self, msg_id):
        with self.msg_ids_seen_lock:
            self.msg_ids_seen[self.msg_ids_seen_nextindex] = msg_id
            self.msg_ids_seen_nextindex += 1
            if self.msg_ids_seen_nextindex >= self.MSG_IDS_SEEN_MAXSIZE:
                self.msg_ids_seen_nextindex = 0

    def _shouldDropMsg(self, msg_id):
        with self.msg_ids_seen_lock:
            if msg_id in self.msg_ids_seen:
                return True
            self._addMsgId(msg_id)
            return False

    def _shout_votes(self, song):
        for playlistitem in self.playlist:
            if playlistitem['song'] == song:
                self._send_msg("VOTES", {'song': song, 'votes': playlistitem['votes']})
                break

    def _send_playlist(self, request_id):
        self._send_msg("PLAYLIST", {'request_id': request_id, 'playlist': self.playlist, 'sign': self._sign(self.playlist), 'pk': self.pk, 'pksign': self.pksign})

    def _handle_playlist(self, sender_peer_name, request_id, playlist, sign, pk, pksign):
        #TODO: Improve verification of playlist
        if self.playlist_request_id:
            if self._verifyPK(pk, pksign) and self._verifyPlaylist(playlist, sign, pk):
                if self.playlist_request_id == request_id:
                    logging.debug("A")
                    self._updatePlaylist(playlist)
                    logging.debug("B")
                    self.playlists_received += 1
                    if self.playlists_received > NR_PLAYLISTS_PREFERRED_ON_JOIN:
                        self.hasJoined = True
                        self.playlist_request_id = None



    def _handleTextMessage(self, sender_peer_name, msg):
        logging.debug("Handling Text Message")

    def _handleVote(self, sender_peer_name, song, vote, pk, pksign):
        #Where vote is a signature on the song name
        print("##################HANDLING VOTE###############")
        if self._verifyPK(pk, pksign) and self._verifyVote(song, vote, pk, pksign):
            self._addVote(song, sender_peer_name, vote, pk, pksign)

    def _handleVotes(self, song, votes):
        # Merge votes
        for vote in votes:
            self._addVote(song, vote['peer_name'], vote['vote'], vote['pk'], vote['pksign'])



    def _flush_top(self, updated_song, new_vote_cnt):
        with self._toplock:
            inTop = False

            for i in range(0, LOCK_TOP):
                if self._top[i]:
                    (songX, votecntX) = self._top[i]
                    if updated_song == songX:
                        inTop = True
                        self._top[i] = (songX, votecntX+1)
                        break
            if not inTop:

                if not self._top[LOCK_TOP-1]: # If not specified yet
                    #Find first empty position
                    for i in range(0,LOCK_TOP):
                        if not self._top[i]:
                            self._top[i] = (updated_song, new_vote_cnt)
                            break
                else:
                    lastTopSongDesc = self._top[LOCK_TOP]
                    if self._compare_songs((updated_song, new_vote_cnt), lastTopSongDesc):
                        self._top[LOCK_TOP] = (updated_song, new_vote_cnt)

            # Update internally
            for i in range(LOCK_TOP-1, 0, -1):
                songdescX = self._top[i]
                songdescY = self._top[i-1]
                if self._compare_songs(songdescY, songdescX):
                    self._top[i] = songdescY
                    self._top[i-1] = songdescX
            if not inTop: # => Must have been added
                # Flush votes for new song in top X (vote sync)
                self._shout_votes(updated_song)

    def _compare_songs(self, songdesc1, songdesc2):
        # Returns true if first song has higher rank
        if not songdesc2 or not songdesc1:
            return True
        (song1, votecnt1) = songdesc1
        (song2, votecnt2) = songdesc2
        if votecnt1 > votecnt2 or (votecnt1 == votecnt2 and song1 < song2):
            return True
        return False

    def _addVote(self, song, peer_name, vote, pk, pksign):
        #Verify vote
        if self._verifyPK(pk, pksign) and \
           self._verifyVote(song, vote, pk, pksign):
            # If exists
            added = False

            for playlistitem in self.playlist:
                if playlistitem['song'] == song:
                    if not peer_name in [vote['peer_name'] for vote in playlistitem['votes']]:
                        # The vote is not in the list, add it
                        playlistitem['votes'].append({'peer_name': peer_name, 'vote': vote, 'pk': pk, 'pksign': pksign})
                        self._flush_top(song, len(playlistitem['votes']))
                    added = True
                    break
            if not added:
                self.playlist.append({'song': song, 'votes': [{'peer_name': peer_name, 'vote': vote, 'pk': pk, 'pksign': pksign}]})
                self._flush_top(song, 1)

        print("VOTE ADDED")

    def _updatePlaylist(self, recievedPlaylist):
        for song in recievedPlaylist:
            # Authenticate votes
            for vote in song['votes']:
                if self._verifyPK(vote['pk'], vote['pksign']) and self._verifyVote(song['song'], vote['vote'], vote['pk'], vote['pksign']):
                    # Vote is authentic, add it
                    self._addVote(song['song'], vote['peer_name'], vote['vote'], vote['pk'], vote['pksign'])
                else:
                    # This guy is a cheater
                    # TODO sound the alarm
                    pass

    def _sign(self, obj):
        #TODO
        return ""

    def _verifyPK(self, pk, pksign):
        #TODO: verify signature on PK
        return True

    def _verifyVote(self, song, vote, pk, pksign):
        #TODO: verify signature
        return True

    def _verifyPlaylist(self, playlist, sign, pk):
        #TODO
        return True

    def _createVote(self, song):
        #TODO: sign
        return song


    def _forward_msg(self, msg_id, sender_peer_name, msgtype, argdict):
        thread = threading.Thread(name="forward", target=self._do_send_msg,
                                  args=[msg_id, sender_peer_name, msgtype, argdict])
        thread.start()
        return ''

    def _gen_msg_id(self):
        dt = datetime.now()
        self.msg_count += 1
        msg_id = self.name + "_" + str(dt.microsecond) + str(self.msg_count)
        self._addMsgId(msg_id)
        return msg_id

    def _send_msg(self, msgtype, argdict):
        thread = threading.Thread(name="forward", target=self._do_send_msg,
                                  args=[self._gen_msg_id(), self.name, msgtype, argdict])
        thread.start()
        return ''

    def _do_send_msg(self, msg_id, sender_peer_name, msgtype, argdict):
        s = ServerProxy('http://' + self.driverHost + ':' + str(self.driverPort))
        s.forwardMessage(self.name, msg_id, sender_peer_name, msgtype, argdict)



    def _main_loop(self):
        while True:
            cmd = sys.stdin.readline().strip()
            logging.debug(self.name + ": Read command: %s" % cmd)
            if "q" == cmd:
                break
            match = re.match(r'sendmsg (\S+)', cmd)
            if match:
                msg = match.group(1)
                self._send_msg("TXTMSG", {'msg': msg})
                continue
            match = re.match(r'vote (\S+)', cmd)
            if match:
                song = match.group(1)
                vote = self._createVote(song)
                self._addVote(song, self.name, vote, self.pk, self.pksign)
                self._send_msg("VOTE", {'song': song, 'vote': vote, 'pk': self.pk, 'pksign': self.pksign})
                continue
            if "join" == cmd:
                self._join()
                continue
            if "play_next" == cmd:
                self._play_next()
                continue
            if "say_quit" == cmd:
                print("QUITTING")
                continue
            if "get_playlist" == cmd:
                with self.playlistLock:
                    playlist_str = "PLAYLIST#####"
                    for playlistitem in self.playlist:
                        playlist_str += playlistitem['song'] + "###"
                        for vote in playlistitem['votes']:
                            first = True
                            for key in vote.keys():
                                if not first:
                                    playlist_str += "#"
                                else:
                                    first = False
                                playlist_str += key + "#" + vote[key]
                            playlist_str += "@@"
                        playlist_str += "####"
                    print(playlist_str)
                continue
            print("Unknown command:", cmd)

    def _server(self):
        logging.debug('Starting peer on: %s:%s' % (self.host, self.port))
        try:
            self.rpc_server.serve_forever()
        finally:
            self.rpc_server.close()

# If executed from cmd line.
if __name__ == '__main__':
    # Setup logging to stderr.
    logging.basicConfig(level=logging.DEBUG, format='(%(threadName)-10s) %(message)s')

    name = sys.argv[1]
    host = sys.argv[2]
    port = int(sys.argv[3])
    driverHost = sys.argv[4]
    driverPort = int(sys.argv[5])
    manualOverride = bool(sys.argv[6])

    peer = Peer(name, host, port, driverHost, driverPort, manualOverride)
    peer.start()
