from xmlrpc.client import ServerProxy
from rpc.RpcHelper import RequestHandler, ThreadedXMLRPCServer
import logging
import sys
import re
import threading
from KeyDistributer import KeyDistributer
from threading import Lock
from datetime import datetime
import time


NR_PLAYLISTS_PREFERRED_ON_JOIN = 5
PLAYLIST_RECV_TIMEOUT_ON_JOIN = 3 #secs (for simulation, not real life)
OUT_OF_RANGE_CHECK_INTERVAL = 5 #secs
OUT_OF_RANGE_TIME_LIMIT = 60 #secs
LOCK_TOP = 3

class Peer(object):
    def __init__(self, name, host, port, driverHost, driverPort):
        self.name, self.host, self.port = name, host, port
        self.driverHost, self.driverPort = driverHost, driverPort

        # [{'song': 'Britney Spears - Toxic', 'votes': [{'peer_name': 'P1', 'vote': 'signature_on_song'}, {'peer_name': 'P2', 'vote': '...'}]]
        self.playlist = []
        self.playlistLock = Lock()

        self.sk, self.pk, self.pksign = KeyDistributer.createKeyPair()

        self.msg_count = 0
        self.MSG_IDS_SEEN_MAXSIZE = 1000
        self.msg_ids_seen = [-1] * self.MSG_IDS_SEEN_MAXSIZE
        self.msg_ids_seen_nextindex = 0
        self.msg_ids_seen_lock = Lock()

        self.playlist_request_id = None
        self.playlists_received = 0

        self.hasJoined = False

        self._time_since_last_msg = 0
        self._time_since_last_msg_lock = Lock()


        self._top = {}   # {'1': ('song', 42 votes), '2': (...)}
        for topX in range(1,LOCK_TOP+1):
            self._top[topX] = None
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

        out_of_range_check_thread = threading.Thread(name="out_of_range_check_thread", target=self._check_out_of_range)
        out_of_range_check_thread.setDaemon(True)  # Don't wait for server thread to exit.
        out_of_range_check_thread.start()

        print("ready\n")

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
        print(txt)
        if self._shouldDropMsg(msg_id):
            logging.debug("DROPPEDMSG")
        else:
            if msgtype == "TXTMSG":
                self._handleTextMessage(sender_peer_name, str(argdict['msg']))
            elif msgtype == "VOTE":
                self._forward_msg(sender_peer_name, msgtype, argdict) # Forward
                self._handleVote(sender_peer_name, str(argdict['song']), str(argdict['vote']), str(argdict['pk']), str(argdict['pksign']))
            elif msgtype == "GETLIST":
                logging.debug("GETLIST!")
                self._send_playlist(argdict['request_id'])
            elif msgtype == "PLAYLIST":
                logging.debug("PLAYLIST!")
                print("GOT PLAYLIST")
                self._handle_playlist(sender_peer_name, argdict['request_id'], argdict['playlist'], argdict['sign'], argdict['pk'], argdict['pksign'])
        return ''


    def _shouldDropMsg(self, msg_id):
        with self.msg_ids_seen_lock:
            if msg_id in self.msg_ids_seen:
                return True
            self.msg_ids_seen[self.msg_ids_seen_nextindex] = msg_id
            self.msg_ids_seen_nextindex += 1
            if self.msg_ids_seen_nextindex >= self.MSG_IDS_SEEN_MAXSIZE:
                self.msg_ids_seen_nextindex = 0
            return False

    def _send_playlist(self, request_id):
        self._send_msg("PLAYLIST", {'request_id': request_id, 'playlist': self.playlist, 'sign': self._sign(self.playlist), 'pk': self.pk, 'pksign': self.pksign})

    def _handle_playlist(self, sender_peer_name, request_id, playlist, sign, pk, pksign):
        #TODO: Improve verification of playlist
        if self.playlist_request_id:
            if self._verifyPK(pk, pksign) and self._verifyPlaylist(playlist, sign, pk):
                if self.playlist_request_id == request_id:
                    self._updatePlaylist(playlist)
                    self.playlists_received += 1
                    if self.playlists_received > NR_PLAYLISTS_PREFERRED_ON_JOIN:
                        self.hasJoined = True
                        self.playlist_request_id = None



    def _handleTextMessage(self, sender_peer_name, msg):
        logging.debug("Handling Text Message")

    def _handleVote(self, sender_peer_name, song, vote, pk, pksign):
        #Where vote is a signature on the song name
        if self._verifyPK(pk, pksign) and self._verifyVote(song, vote, pk):
            self._addVote(song, sender_peer_name, vote)

    def _flush_top3(self, updated_song, new_vote_cnt):
        with self._toplock:
            inTop = False
            for (topX, (songX, votecntX)) in self._top.items():
                if updated_song == songX:
                    inTop = True
                    self._top[topX] = (songX, votecntX+1)
                    break
            if not inTop:
                if not self._top[LOCK_TOP]: # If not specified yet
                    self._top[LOCK_TOP] = (updated_song, new_vote_cnt)
                else:
                    lastTopSongDesc = self._top3[LOCK_TOP]
                    if self._compare_songs((updated_song, new_vote_cnt), lastTopSongDesc):
                        self._top[LOCK_TOP] = (updated_song, new_vote_cnt)

            # Update internally
            for topX in range(LOCK_TOP, 1, -1):
                songdescX = self._top[topX]
                songdescY = self._top3[topX-1]
                if self._compare_songs(songdescY, songdescX):
                    self._top[topX] = songdescY
                    self._top[topX-1] = songdescX

    def _compare_songs(self, songdesc1, songdesc2):
        # Returns true if first song has higher rank
        (song1, votecnt1) = songdesc1
        (song2, votecnt2) = songdesc2
        if votecnt1 > votecnt2 or (votecnt1 == votecnt2 and song1 < song2):
            return True
        return False

    def _addVote(self, song, peer_name, vote):
        # If exists
        added = False
        for playlistitem in self.playlist:
            if playlistitem['song'] == song:
                if not peer_name in [vote['peer_name'] for vote in playlistitem['votes']]:
                    # The vote is not in the list, add it
                    playlistitem['votes'].append({'peer_name': peer_name, 'vote': vote})
                    self._flush_top3()
                added = True
                break
        if not added:
            self.playlist.append({'song': song, 'votes': [{'peer_name': peer_name, 'vote': vote}]})
            self._flush_top3()

    def _udpatePlaylist(self, recievedPlaylist, peerName):
        for song in recievedPlaylist:
            # Authenticate votes
            for vote in song['votes']:
                if self._verifyPK(vote['pk'], vote['pksign']) and self._verifyVote(song['song'], vote['vote'], vote['pk']):
                    # Vote is authentic, add it
                    self._addVote(song['song'], peerName, vote)
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

    def _verifyVote(self, vote, pk):
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
        return self.name + "_" + str(dt.microsecond) + str(self.msg_count)

    def _send_msg(self, msgtype, argdict):
        thread = threading.Thread(name="forward", target=self._do_send_msg,
                                  args=[self._gen_msg_id(), self.name, msgtype, argdict])
        thread.start()
        return ''

    def _do_send_msg(self, msg_id, sender_peer_name, msgtype, argdict):
        s = ServerProxy('http://' + self.driverHost + ':' + str(self.driverPort))
        s.forwardMessage(msg_id, sender_peer_name, msgtype, argdict)



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
                self._send_msg("VOTE", {'song': song, 'vote': self._createVote(song), 'pk': self.pk, 'pksign': self.pksign})
                continue
            if "join" == cmd:
                self._join()
                continue
            if "say_timeout" == cmd:
                print("SAY_TIMEOUT")  # Used for test readline timeout
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

    peer = Peer(name, host, port, driverHost, driverPort)
    peer.start()
