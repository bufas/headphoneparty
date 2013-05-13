import math

MAX_K = 20  # specifies how many local and global clocks to remember
TAU = 1000  # specifies how often the clock synchronizes (in ms)

class Clock():
    def __init__(self, peer):
        self.peer = peer
        self.current = 0
        self.next_sync = 0
        self.max_gps = 0
        self.localClock = [0 in range(MAX_K)]
        self.globalClock = [0 in range(MAX_K)]

    def getMlocal(self):
        return max(self.localClock)

    def getMglobal(self):
        return max(self.globalClock)

    def getLogical(self):
        return max(self.getMlocal(), self.getMglobal())

    def recv(self, t, s):
        if s >= self.max_gps and t > self.globalClock[self.current]:
            self.globalClock[self.current] = t
            self.send((t, s))
            if t/TAU >= self.next_sync:
                self.next_sync = math.floor(t/TAU) + 1

    def send(self, msg):
        self.peer._send_msg("CLOCKSYNC", {'message': msg})

    def gps(self, t):
        if t > self.max_gps:
            self.max_gps = t
            self._increaseCurrent()
            self.localClock[self.current] = t
            self.globalClock[self.current] = t
            self.next_sync = math.floor(t/TAU) + 1

    def _increaseCurrent(self):
        self.current = (self.current + 1) % self.MAX_K
