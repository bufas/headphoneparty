import sys
import threading
import time
from xmlrpc.client import ServerProxy
from PeerHandler import BasicPeerHandler
from PeerHandler import PeerController
from threading import Condition
from threading import Lock
from RpcHelper import RequestHandler, ThreadedXMLRPCServer


class Router:
    def __init__(self, host, port, peers, peer_controller, useTicks):
        self.host = host
        self.port = port
        self.peer_controller = peer_controller
        self.peers = peers
        self.msg_queue = []
        self.msg_lock = Lock()
        self.msg_cond = Condition(self.msg_lock)
        self.useTicks = useTicks
        self.peer_can_send = {}
        self.queue_was_empty = False
        self.queue_active = False

        # Init for ticks
        for peer in self.peers:
            self.peer_can_send[peer.name] = 0

    def activate_queue(self):
        with self.msg_lock:
            self.queue_active = True
            self.msg_cond.notify()

    def tick(self, num_msgs):
        """Each peer can only send a fixed number of messages each time interval"""
        with self.msg_lock:
            for peer in self.peers:
                self.peer_can_send[peer.name] = num_msgs
            self.msg_cond.notify()

    def wait_queue_empty(self):
        # Check twice with small interval
        while True:
            with self.msg_lock:
                if len(self.msg_queue) > 0:
                    self.queue_was_empty = True
                else:
                    if self.queue_was_empty:
                        self.queue_was_empty = False
                        break
                    else:
                        self.queue_was_empty = True
            time.sleep(0.1)

    def start(self):
        # Create server
        self.rpc_server = ThreadedXMLRPCServer((self.host, self.port), requestHandler=RequestHandler, logRequests=False)
        self.rpc_server.register_introspection_functions()

        # Register RPC functions.
        self.rpc_server.register_function(self.forwardMessage)
        self.rpc_server.register_function(self.registerNewPeer)

        server_thread = threading.Thread(name="server", target=self._server)
        server_thread.setDaemon(True)  # Don't wait for server thread to exit.
        server_thread.start()

        queue_thread = threading.Thread(name="queue", target=self._queue_handler)
        queue_thread.setDaemon(True)  # Don't wait for server thread to exit.
        queue_thread.start()

    def shutdown(self):
        self.rpc_server.server_close()

    def registerNewPeer(self):
        print("HURRAY")
        return ''

    # Peer name is the origin of the message
    def forwardMessage(self, immediate_sender, msg_id, peer_name, msgtype, argdict):
        #Find peer
        #TODO: IMPROVE
        immediate_sender_peer = None
        for peer in self.peers:
            if peer.name == immediate_sender:
                immediate_sender_peer = peer
                break
        self.msg_lock.acquire()
        self.msg_queue.append((immediate_sender_peer, msg_id, peer_name, msgtype, argdict))
        self.queue_was_empty = False
        self.msg_cond.notify()
        self.msg_lock.release()
        return ''

    def _server(self):
        print('Starting router on: %s:%s' % (self.host, self.port))
        try:
            self.rpc_server.serve_forever()
        except ValueError:  # Thrown upon exit :(
            pass


    def _queue_handler(self):
        while True:
            with self.msg_lock:
                if not self.queue_active:
                    self.msg_cond.wait()
                    continue
                if len(self.msg_queue) == 0:
                    self.msg_cond.wait()
                for i in range(len(self.msg_queue)):
                    (immediate_sender_peer, msg_id, peer_name, msgtype, argdict) = self.msg_queue[i]
                    if not self.useTicks or (self.peer_can_send[immediate_sender_peer.name]
                                             and self.peer_can_send[immediate_sender_peer.name] > 0):
                        self.msg_queue.pop(i)
                        if self.useTicks:
                            self.peer_can_send[immediate_sender_peer.name] -= 1
                        self._do_forward_msg(immediate_sender_peer, msg_id, peer_name, msgtype, argdict)
                        break

    def _do_forward_msg(self, immediate_sender_peer, msg_id, peer_name, msgtype, argdict):
        peersInRange = self.peer_controller.findPeersInRange(immediate_sender_peer)
        for peer in peersInRange:
            if peer != immediate_sender_peer:
                peer.sendMessage(immediate_sender_peer, msg_id, peer_name, str(msgtype), argdict)

            


    def _main_loop(self):
        while True:
            cmd = sys.stdin.readline().strip()
            if "q" == cmd:
                break
            match = re.match(r'sendmsg (\S+)', cmd)
            if match:
                msg = match.group(1)
                self._send_msg("TXTMSG", {'msg': msg})
                continue
            print("Unknown command:", cmd)        

if __name__ == '__main__':
    host = sys.argv[1]
    port = int(sys.argv[2])
    if len(sys.argv) > 3:
        visualize = (sys.argv[3] == "True")
        worldwidth = int(sys.argv[4])
        worldheight = int(sys.argv[5])
        topSpeed = int(sys.argv[6])
        maxSpeedChange = int(sys.argv[7])
        radioRange = int(sys.argv[8])
    else:
        visualize = False
        worldwidth, worldheight = 2000, 2000
        topSpeed = 140
        maxSpeedChange = 50
        radioRange = 500

    peers = []

    peer_controller = PeerController(peers, {'width': worldwidth, 'height': worldheight}, topSpeed, maxSpeedChange, radioRange)
    router = Router(host, port, peers, peer_controller, False)
    router.start()
    router.activate_queue()

    if visualize:
        peer_controller.visualize(block=False, refresh=True)

    router._main_loop()
