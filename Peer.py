from xmlrpc.client import ServerProxy
from rpc.RpcHelper import RequestHandler, ThreadedXMLRPCServer
import logging
import sys
import re
import threading
from KeyDistributer import KeyDistributer
from threading import Lock
from datetime import datetime


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

    def start(self):
        # Create server
        self.rpc_server = ThreadedXMLRPCServer((self.host, self.port), requestHandler=RequestHandler)
        self.rpc_server.register_introspection_functions()

        # Register RPC functions.
        self.rpc_server.register_function(self.ReceiveMsg)

        server_thread = threading.Thread(name="server", target=self._server)
        server_thread.setDaemon(True)  # Don't wait for server thread to exit.
        server_thread.start()

        print("ready\n")

        self._main_loop()

    def _join(self):
        self._send_msg("GETLIST", {})

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
                self._send_playlist(msg_id)
            elif msgtype == "PLAYLIST":
                logging.debug("PLAYLIST!")
                print("GOT PLAYLIST")
                #self._handlePlaylist()
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

    def _send_playlist(self, msg_id):
        self._send_msg("PLAYLIST", {'playlist': self.playlist, 'sign': self._sign(self.playlist)})

    def _handleTextMessage(self, sender_peer_name, msg):
        logging.debug("Handling Text Message")

    def _handleVote(self, sender_peer_name, song, vote, pk, pksign):
        #Where vote is a signature on the song name
        if self._verifyPK(pk, pksign) and self._verifyVote(song, vote, pk):
            self._addVote(song, sender_peer_name, vote)

    def _addVote(self, song, peer_name, vote):
        # If exists
        added = False
        for playlistitem in self.playlist:
            if playlistitem['song'] == song:
                if not peer_name in [vote['peer_name'] for vote in playlistitem['votes']]:
                    # The vote is not in the list, add it
                    playlistitem['votes'].push_back({'peer_name': peer_name, 'vote': vote})
                added = True
                break
        if not added:
            self.playlist.push_back({'song': song, 'votes': [{'peer_name': peer_name, 'vote': vote}]})

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
