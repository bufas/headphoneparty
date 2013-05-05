import threading
import time
from xmlrpc.client import ServerProxy
from threading import Condition
from threading import Lock
from rpc.RpcHelper import RequestHandler, ThreadedXMLRPCServer


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
        self.queue_was_empty = True

        # Init for ticks
        for peer in self.peers:
            self.peer_can_send[peer.name] = 0

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
                    self.msg_cond.wait()
                else:
                    if self.queue_was_empty:
                        break
                    else:
                        self.queue_was_empty = True
                        time.sleep(0.5)

    def start(self):
        # Create server
        self.rpc_server = ThreadedXMLRPCServer((self.host, self.port), requestHandler=RequestHandler)
        self.rpc_server.register_introspection_functions()

        # Register RPC functions.
        self.rpc_server.register_function(self.forwardMessage)

        server_thread = threading.Thread(name="server", target=self._server)
        server_thread.setDaemon(True)  # Don't wait for server thread to exit.
        server_thread.start()

        queue_thread = threading.Thread(name="queue", target=self._queue_handler)
        queue_thread.setDaemon(True)  # Don't wait for server thread to exit.
        queue_thread.start()

    def shutdown(self):
        self.rpc_server.server_close()

    def forwardMessage(self, msg_id, peer_name, msgtype, argdict):
        #Find peer
        #TODO: IMPROVE
        sender_peer = None
        for peer in self.peers:
            if peer.name == peer_name:
                sender_peer = peer
                break
        self.msg_lock.acquire()
        self.msg_queue.append((msg_id, sender_peer, msgtype, argdict))
        self.queue_was_empty = False
        self.msg_cond.notify()
        self.msg_lock.release()
        return ''

    def _server(self):
        print('Starting driver on: %s:%s' % (self.host, self.port))
        try:
            self.rpc_server.serve_forever()
        except ValueError:  # Thrown upon exit :(
            pass

    def _queue_handler(self):
        while True:
            with self.msg_lock:
                if len(self.msg_queue) == 0:
                    self.msg_cond.wait()
                for i in range(len(self.msg_queue)):
                    (msg_id, sender_peer, msgtype, argdict) = self.msg_queue[i]
                    if not self.useTicks or (self.peer_can_send[sender_peer.name]
                                             and self.peer_can_send[sender_peer.name] > 0):
                        self.msg_queue.pop(i)
                        if self.useTicks:
                            self.peer_can_send[sender_peer.name] -= 1
                        self._do_forward_msg(msg_id, sender_peer, msgtype, argdict)
                        break

    def _do_forward_msg(self, msg_id, sender_peer, msgtype, argdict):
        peersInRange = self.peer_controller.findPeersInRange(sender_peer)
        for peer in peersInRange:
            if peer != sender_peer:
                serverProxy = ServerProxy('http://' + peer.adr())
                serverProxy.ReceiveMsg(msg_id, sender_peer.name, str(msgtype), argdict)
