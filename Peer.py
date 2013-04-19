from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler
import sys

# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/RPC2',)

class Peer(object):

    def __init__(self, port):
        # Create server
        server = SimpleXMLRPCServer(("127.0.0.1", port),
                                    requestHandler=RequestHandler)
        server.register_introspection_functions()

        server.register_function(self.iadd, 'add')

        print ("Peer running on port ", port)

        server.serve_forever()


    # Register a function under a different name
    def iadd(self, x,y):
        return x + y

# If executed from cmd line.
if __name__ == '__main__':

    port = int(sys.argv[1])
    peer = Peer(port)
