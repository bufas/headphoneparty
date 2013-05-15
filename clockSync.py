import math
import threading
import time

MAX_K = 20  # specifies how many local and global clocks to remember
TAU = 15000  # specifies how often the clock synchronizes (in ms)

class Clock():
    def __init__(self, peer):
        self.peer = peer
        self.current = 0
        self.next_sync = 0
        self.max_gps = 0
        self.localClock = [0 in range(MAX_K)]
        self.globalClock = [0 in range(MAX_K)]
        self.localClockSetTimestamp = 0
        self.globalClockSetTimestamp = 0

        sync_thread = threading.Thread(name="sync", target=self.sync)
        sync_thread.setDaemon(True)
        sync_thread.start()

    def _getMlocal(self):
        max = self.localClock[self.current] + math.floor(time.time() * 1000) - self.localClockSetTimestamp
        for t in self.localClock[:self.current] + self.localClock[self.current+1:]:
            if t > max:
                max = t

        return max

    def _getMglobal(self):
        max = self.globalClock[self.current] + math.floor(time.time() * 1000) - self.globalClockSetTimestamp
        for t in self.globalClock[:self.current] + self.globalClock[self.current+1:]:
            if t > max:
                max = t

        return max

    def _setGlobal(self, t):
        self.globalClockSetTimestamp = math.floor(time.time() * 1000)
        self.globalClock[self.current] = t

    def _setLocal(self, t):
        self.localClockSetTimestamp = math.floor(time.time() * 1000)
        self.localClock[self.current] = t

    def getLogical(self):
        return max(self.getMlocal(), self.getMglobal())

    def recv(self, t, s):
        if s >= self.max_gps and t > self.globalClock[self.current]:
            self.setGlobal(t)
            self.send((t, s))
            if t/TAU >= self.next_sync:
                self.next_sync = math.floor(t/TAU) + 1

    def _sync(self):
        while time.time() * 1000 > self.next_sync * TAU:
            self.send((self.local[self.current], self.max_gps))
            self.next_sync = math.floor(time.time() * 1000 / TAU) + 1

    def _send(self, msg):
        self.peer._send_msg("CLOCKSYNC", {'message': msg})

    def gps(self, t):
        if t > self.max_gps:
            self.max_gps = t
            self._increaseCurrent()
            self.setLocal(t)
            self.setGlobal(t)
            self.next_sync = math.floor(t/TAU) + 1

    def _increaseCurrent(self):
        self.current = (self.current + 1) % self.MAX_K
