import random
import spur
import time

NUMBER_OF_PEERS = 2

username = raw_input('Enter your glorious NFIT username Sir.: ')
password = raw_input('And please accompany it with your fine password Mr. '+username+': ')

# Always start the router on
routerHost = 'llama01'
routerPort = '8300'

# Create list of shells
hosts = ['llama02', 'llama03', 'llama04', 'llama05', 'llama06', 'llama07', 'llama08', 'llama09', 'llama10',
         'llama11', 'llama12', 'llama13', 'llama14', 'llama15', 'llama16', 'llama17', 'birc01', 'birc02', 'coda']

# Run the driver
routerShell = spur.SshShell(hostname=routerHost, username=username, password=password)
with routerShell:
    router = routerShell.spawn(['python3', 'Router.py', routerHost, routerPort], store_pid=True)

# Run the peers
peers = []
for i in range(NUMBER_OF_PEERS):
    rand = random.randint(0, len(hosts)-1)
    host = hosts.pop(rand)
    peerShell = spur.SshShell(hostname=host, username=username, password=password)
    with peerShell:
        peer = peerShell.spawn(['python3', '-u', 'Peer.py', 'register', 'P'+str(i), host,
                                '8500', routerHost, routerPort, 'False', 'False'], store_pid=True)
        peer.stdin_write('join\n')
        peers.append(peer)

# Do something with the peers. (You don't have to do it, only if you want to...)
# Write to a peer using something like
#     peers[0].stdin_write('join\n')

print('Wait some')
time.sleep(2)
print('Finished waiting')

# Wait for all peers to finish
counter = 0
for p in peers:
    result = p.wait_for_result()
    print('P'+str(counter))
    print(result.output())
    counter += 1


#
# python3 Router.py llama01 8300
# python3 -u Peer.py register P0 llama02 8500 llama01 8300 False False
# python3 -u Peer.py register P1 llama03 8500 llama01 8300 False False
# python3 -u Peer.py register P2 llama04 8500 llama01 8300 False False
#