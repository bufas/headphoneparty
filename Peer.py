from xmlrpc.client import ServerProxy
from rpc.RpcHelper import RequestHandler, ThreadedXMLRPCServer
import logging
import sys
import re
import threading


class Peer(object):
    def __init__(self, name, host, port, driverHost, driverPort):
        self.name, self.host, self.port = name, host, port
        self.driverHost, self.driverPort = driverHost, driverPort

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

    def ReceiveMsg(self, sender_peer_name, msgtype, argdict):
        # For some reason argdict values has turned into lists
        txt = self.name + ": GOTMSG of type " + msgtype + " from peer " + sender_peer_name + ": " + str(argdict['msg'])
        logging.debug(txt)
        print(txt)
        if msgtype == "TXTMSG":
            self._handleTextMessage(sender_peer_name, str(argdict['msg']))
        return ''

    def _handleTextMessage(self, sender_peer_name, msg):
        logging.debug("Handling Text Message")

    def _send_msg(self, msgtype, argdict):
        thread = threading.Thread(name="forward", target=self._do_send_msg, args=[msgtype, argdict])
        thread.start()
        return ''

    def _do_send_msg(self, msgtype, argdict):
        s = ServerProxy('http://' + self.driverHost + ':' + str(self.driverPort))
        s.ForwardMessage(self.name, msgtype, argdict)

    def _main_loop(self):
        while True:
            cmd = sys.stdin.readline().strip()
            logging.debug(self.name + ": Read command: %s" % cmd)
            if "q" == cmd:
                break
            match = re.match(r'sendmsg (\S+)', cmd)
            if match:
                msg = match.group(1),
                self._send_msg("TXTMSG", {'msg': msg})
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
# TODO merge this with Driver.py
if __name__ == '__main__':
    # Setup logging to stderr.
    logging.basicConfig(level=logging.DEBUG, format='(%(threadName)-10s) %(message)s')

    name = 'abe'
    host = '127.0.0.1'
    port = 61000
    driverHost = '127.0.0.1'
    driverPort = 6300

    # name = sys.argv[1]
    # host = sys.argv[2]
    # port = int(sys.argv[3])
    # driverHost = sys.argv[4]
    # driverPort = int(sys.argv[5])
    #
    peer = Peer(name, host, port, driverHost, driverPort)
    peer.start()
