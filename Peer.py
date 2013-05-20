from xmlrpc.client import ServerProxy
import logging
import sys
import re
import threading
from threading import Lock
from threading import RLock
from datetime import datetime
import time
from Crypto.Hash import SHA256
from KeyHandler import KeyHandler
from RpcHelper import RequestHandler, ThreadedXMLRPCServer

from KeyDistributer import KeyDistributer

from clockSync import Clock

NR_PLAYLISTS_PREFERRED_ON_JOIN = 5
PLAYLIST_RECV_TIMEOUT_ON_JOIN = 3 #secs (for simulation, not real life)
OUT_OF_RANGE_CHECK_INTERVAL = 5 #secs
OUT_OF_RANGE_TIME_LIMIT = 60 #secs
LOCK_TOP = 3

class Peer(object):
    def __init__(self, register, name, host, port, routerHost, routerPort, manualOverride, clockSyncActive):
        self.name, self.host, self.port = name, host, port
        self.routerHost, self.routerPort = routerHost, routerPort
        self.manualOverride, self.clockSyncActive = manualOverride, clockSyncActive
        self.register = register

        # [{'song_name': 'Britney Spears - Toxic', 'votes': [{'peer_name': 'P1', 'sig': 'signature_on_song', 'pk': ..., 'pksign': ...}, {'peer_name': 'P2', 'sig': '...', ...}]]
        self.playlist = []
        self.playlistLock = Lock()

        keydist = KeyDistributer()
        self.key = keydist.getKeyPair()

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
        self._toplock = RLock()

        self.clock = Clock(self, sync=self.clockSyncActive)

        self.progressLock = Lock()
        self.quitting = False

    def start(self):
        if self.register:
            s = ServerProxy('http://' + self.routerHost + ':' + str(self.routerPort))
            s.registerNewPeer()

        # Create server
        self.rpc_server = ThreadedXMLRPCServer((self.host, self.port), requestHandler=RequestHandler, logRequests=False)
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
            print("JOIN RETRY")
            self._join() # Retry

    def ReceiveMsg(self, msg_id, sender_peer_name, msgtype, argdict):
        if not self.quitting:
            recv_handler_thread = threading.Thread(name="recvhandler", target=self._handle_recv_message,
                                                   args=[msg_id, sender_peer_name, msgtype, argdict])
            recv_handler_thread.start()            
        return ''

    def _handle_recv_message(self, msg_id, sender_peer_name, msgtype, argdict):
        # For some reason argdict values has turned into lists
        txt = self.name + ": GOTMSG of type " + msgtype + " from peer " + sender_peer_name + ": " + str(argdict)
        #logging.debug(txt)
        if self._shouldDropMsg(msg_id):
            print("DROPPED MSG")
        else:
            print(txt)
            if msgtype == "VOTE":
                #logging.debug(self.name + "HANDLE VOTE")
                self._forward_msg(msg_id, sender_peer_name, msgtype, argdict) # Forward
                self._handleVote(argdict['song_name'],
                                 argdict['vote'])
            elif msgtype == "VOTES":
                print("GOT VOTESLIST of " + str(argdict['song_name']))
                self._handleVotes(str(argdict['song_name']),
                                  argdict['votes'])
            elif msgtype == "GETLIST":
                self._send_playlist(argdict['request_id'])
            elif msgtype == "PLAYLIST":
                print("GOT PLAYLIST")
                self._handle_playlist(sender_peer_name,
                                      argdict['request_id'],
                                      argdict['playlist'],
                                      argdict['pk'],
                                      argdict['pksign'])
            elif msgtype == "CLOCKSYNC":
                (t, s) = argdict['message']
                self.clock.recv(t, s)
                
    def _play_next(self):
        with self.playlistLock:
            with self._toplock:
                if self._top[0]:
                    (nextsong, _) = self._top[0]

                    # Clean up
                    top3songs = []
                    for i in range(0, LOCK_TOP-1):
                        self._top[i] = self._top[i+1]
                        if self._top[i]:
                            (song, _) = self._top[i]
                            top3songs.append(song)
                    self._top[LOCK_TOP-1] = None

                    # Remove played song
                    for playlistitem in self.playlist:
                        if playlistitem['song_name'] == nextsong:
                            self.playlist.remove(playlistitem)
                            break

                    # Add new song to top
                    maxcnt = 0
                    maxsong = None
                    for playlistitem in self.playlist:
                        if not playlistitem['song_name'] in top3songs:
                            if self._compare_songs((playlistitem['song_name'], len(playlistitem['votes'])), (maxsong, maxcnt)):
                                maxcnt = len(playlistitem['votes'])
                                maxsong = playlistitem['song_name']
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

    def _shout_votes(self, songName):
        print("SHOUTING VOTES")
        for playlistitem in self.playlist:
            if playlistitem['song_name'] == songName:
                self._send_msg("VOTES", {'song_name': songName, 'votes': playlistitem['votes']})
                break

    def _send_playlist(self, request_id):
        params = {'request_id': request_id,
                  'playlist': self.playlist,
                  'pk': self.key.getPublicKey(),
                  'pksign': self.key.getPksign()}
        self._send_msg("PLAYLIST", params)

    def _handle_playlist(self, sender_peer_name, request_id, playlist, pk, pksign):
        #TODO: Improve verification of playlist
        if self.playlist_request_id:
            if self._verifyPK(pk, pksign) and self._verifyPlaylist(playlist, pk):
                if self.playlist_request_id == request_id:
                    #logging.debug("A")
                    self._updatePlaylist(playlist)
                    #logging.debug("B")
                    self.playlists_received += 1
                    if self.playlists_received > NR_PLAYLISTS_PREFERRED_ON_JOIN:
                        self.hasJoined = True
                        self.playlist_request_id = None

    def _handleVote(self, songName, vote):
        print("##################HANDLING VOTE###############")
        if self._verifyPK(vote['pk'], vote['pksign']) and self._verifyVote(songName, vote):
            self._addVote(songName, vote)
        else:
            print('VOTE REJECTED')

    def _handleVotes(self, songName, votes):
        # Merge votes
        for vote in votes:
            self._addVote(songName, vote)



    def _flush_top(self, updated_song, new_vote_cnt):
        with self._toplock:
            inTop = False

            for i in range(0, LOCK_TOP):
                if self._top[i]:
                    (songX, votecntX) = self._top[i]
                    if updated_song == songX:
                        inTop = True
                        self._top[i] = (songX, new_vote_cnt)
                        break
            if not inTop:

                if not self._top[LOCK_TOP-1]: # If not specified yet
                    #Find first empty position
                    for i in range(0,LOCK_TOP):
                        if not self._top[i]:
                            self._top[i] = (updated_song, new_vote_cnt)
                            break
                else:
                    lastTopSongDesc = self._top[LOCK_TOP-1]
                    if self._compare_songs((updated_song, new_vote_cnt), lastTopSongDesc):
                        self._top[LOCK_TOP -1] = (updated_song, new_vote_cnt)

            # Update internally
            for i in range(LOCK_TOP-1, 0, -1):
                songdescX = self._top[i]
                songdescY = self._top[i-1]
                if self._compare_songs(songdescX, songdescY):
                    self._top[i] = songdescY
                    self._top[i-1] = songdescX
            if not inTop: # => Must have been added
                # Flush votes for new song in top X (vote sync)
                self._shout_votes(updated_song)

    def _compare_songs(self, songdesc1, songdesc2):
        # Returns true if first song has higher rank
        if not songdesc2:
            return True
        if not songdesc1:
            return False
        (song1, votecnt1) = songdesc1
        (song2, votecnt2) = songdesc2
        if votecnt1 > votecnt2 or (votecnt1 == votecnt2 and song1 < song2):
            return True
        return False

    def _addVote(self, songName, vote):
        with self.playlistLock:
            # If exists
            added = False

            for playlistitem in self.playlist:
                if playlistitem['song_name'] == songName:
                    if not vote['peer_name'] in [existingVote['peer_name'] for existingVote in playlistitem['votes']]:
                        # The vote is not in the list, add it
                        playlistitem['votes'].append(vote)
                        self._flush_top(songName, len(playlistitem['votes']))
                    added = True
                    break
            if not added:
                self.playlist.append({'song_name': songName, 'votes': [vote]})
                self._flush_top(songName, 1)

            print("VOTE ADDED")

    def _updatePlaylist(self, recievedPlaylist):
        for song in recievedPlaylist:
            # Authenticate votes
            for vote in song['votes']:
                self._addVote(song['song_name'], vote)

    def _sign(self, obj):
        return self.key.signMessage(obj)

    def _hashOfPlaylist(self, playlist):
        result = SHA256.new()
        for songDescriptor in playlist:
            result.update(songDescriptor['song_name'].encode())
            for vote in songDescriptor['votes']:
                result.update(vote['peer_name'].encode())
                result.update(vote['sig'].encode())
                result.update(vote['pk'])
                result.update(vote['pksign'].encode())
        return result.digest()

    def _verifyPK(self, pk, pksign):
        return self.key.verifyPublicKey(pk, int(pksign))

    def _verifyVote(self, songName, vote):
        return self.key.verifyMessage(vote['pk'], songName, vote['sig']) and self._verifyPK(vote['pk'], vote['pksign'])

    def _verifyPlaylist(self, playlist, pk):
        # Run through all votes for all songs and verify them
        for songDescripter in playlist:
            for vote in songDescripter['votes']:
                if not self._verifyVote(songDescripter['song_name'], vote):
                    return False
        return True

    def _createVote(self, songName):
        """Creates a vote for a specific song"""
        return {'peer_name': self.name,
                'sig': str(self.key.signMessage(songName)),
                'pk': self.key.getPublicKey(),
                'pksign': self.key.getPksign()}


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
        if not self.quitting:
            thread = threading.Thread(name="forward", target=self._do_send_msg,
                                      args=[self._gen_msg_id(), self.name, msgtype, argdict])
            thread.start()
        return ''

    def _do_send_msg(self, msg_id, sender_peer_name, msgtype, argdict):
        s = ServerProxy('http://' + self.routerHost + ':' + str(self.routerPort))
        s.forwardMessage(self.name, msg_id, sender_peer_name, msgtype, argdict)

    def _sendVote(self, songName, vote):
        params = {'song_name': songName,
                  'vote': vote}
        self._send_msg("VOTE", params)

    def _print_songlist(self, prefix, songlist):
        songlist_str = prefix + "#####"
        for songlistitem in songlist:
            songlist_str += songlistitem['song_name'] + "###"
            for vote in songlistitem['votes']:
                first = True
                for key in vote.keys():
                    if not first:
                        songlist_str += "#"
                    else:
                        first = False
                    songlist_str += key + "#" + vote[key].replace("\n", "#LINEBREAK#")
                songlist_str += "@@"
            songlist_str += "####"
        print(songlist_str)

    def _main_loop(self):
        while True:
            cmd = sys.stdin.readline().strip()
            logging.debug(self.name + ": Read command: %s" % cmd)
            if "q" == cmd:
                with self.progressLock:
                    self.quitting = True
                    break
            match = re.match(r'sendmsg (\S+)', cmd)
            if match:
                msg = match.group(1)
                self._send_msg("TXTMSG", {'msg': msg})
                continue
            match = re.match(r'vote (\S+)', cmd)
            if match:
                songName = match.group(1)
                vote = self._createVote(songName)
                self._addVote(songName, vote)
                self._sendVote(songName, vote)
                print("VOTEOK")
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
                    self._print_songlist("PLAYLIST", self.playlist)
                continue
            if "get_top3songs" == cmd:
                with self._toplock:
                    top3str = "TOP3SONGS###"
                    for top3item in self._top:
                        if top3item:
                            (song, votecnt) = top3item
                            top3str += song + "#" + str(votecnt) + "##"
                    print(top3str)
                continue
            if "test_create_fake_vote" == cmd:
                songName = 'Justin Beaver'
                fakeVote = {'peer_name': self.name,
                            'sig': str(self.key.signMessage(songName)),
                            'pk': self.key.getPublicKey(),
                            'pksign': '0'}
                self._sendVote(songName, fakeVote)
                continue
            if "get_logical_clock" == cmd:
                print("LOGICALCLOCK#" + str(self.clock.getLogical()))
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

    register = (sys.argv[1] == "register")
    name = sys.argv[2]
    host = sys.argv[3]
    port = int(sys.argv[4])
    routerHost = sys.argv[5]
    routerPort = int(sys.argv[6])
    manualOverride = (sys.argv[7] == "True")
    clockSync = (sys.argv[8] == "True")

    peer = Peer(register, name, host, port, routerHost, routerPort, manualOverride, clockSync)
    peer.start()
