from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler
import socketserver


# Restrict to a particular path.
class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = '/RPC2'


# Threaded RPC for concurrency.
# Field 'allow_reuse_address' inserted to avoid tcp "address already in use".
# See http://www.dalkescientific.com/writings/diary/archive/2005/04/21/using_xmlrpc.html.
class ThreadedXMLRPCServer(socketserver.ThreadingMixIn, SimpleXMLRPCServer):
    allow_reuse_address = True
