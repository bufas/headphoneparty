from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler
from xmlrpc.client import ServerProxy
import socketserver
import logging
import sys
import re
import threading
import codecs

# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

# Threaded RPC for concurrency.
# Field 'allow_reuse_address' inserted to avoid tcp "address already in use".
# See http://www.dalkescientific.com/writings/diary/archive/2005/04/21/using_xmlrpc.html.
class ThreadedXMLRPCServer(socketserver.ThreadingMixIn, SimpleXMLRPCServer):
    allow_reuse_address = True

class Peer(object):
    def __init__(self, name, host, port, driverHost, driverPort):
        self.name, self.host, self.port = name, host, port
        self.driverHost, self.driverPort = driverHost, driverPort

    def ReceiveMsg(self, peer_name, msg):
        txt = self.name + ": GOTMSG from peer " + peer_name + ": " + msg
        logging.debug(txt)
        print(txt)
        return ''

    def _send_msg(self, msg):
        thread = threading.Thread(name="forward", target=self._do_send_msg, args=[msg])
        thread.start()
        return ''

    def _do_send_msg(self, msg):
        s = ServerProxy('http://' + self.driverHost + ':' + str(self.driverPort))
        s.ForwardMessage(self.name, msg)

    def _main_loop(self):
        while True:
            cmd = sys.stdin.readline().strip()
            logging.debug(self.name + ": Read command: %s" % cmd)
            if "q" == cmd:
                break
            match = re.match(r'sendmsg (\S+)', cmd)
            if match:
                msg = match.group(1),
                self._send_msg(msg)
                continue
            if "say_timeout" == cmd:
                print ("SAY_TIMEOUT") # Used for test readline timeout
                continue
            print ("Unknown command:", cmd)

    def _server(self):
        logging.debug('Starting peer on: %s:%s' % (self.host, self.port))
        try:
            self.rpc_server.serve_forever()
        finally:
            self.rpc_server.close()

    def start(self):

        # Create server
        self.rpc_server = ThreadedXMLRPCServer((self.host, self.port),
                                        requestHandler=RequestHandler)
        self.rpc_server.register_introspection_functions()

        # Register RPC functions.
        self.rpc_server.register_function(self.ReceiveMsg)

        server_thread = threading.Thread(name="server", target=self._server)
        server_thread.setDaemon(True) # Don't wait for server thread to exit.
        server_thread.start()

        print ("ready\n")

        self._main_loop()

# If executed from cmd line.
if __name__ == '__main__':

    # Setup logging to stderr.
    logging.basicConfig(
        level=logging.DEBUG,
        format='(%(threadName)-10s) %(message)s')

    name = sys.argv[1]
    host = sys.argv[2]
    port = int(sys.argv[3])
    driverHost = sys.argv[4]
    driverPort = int(sys.argv[5])

    peer = Peer(name, host, port, driverHost, driverPort)
    peer.start()
