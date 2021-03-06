import logging
import math
import threading
import time

MAX_K = 20  # specifies how many local and global clocks to remember
TAU = 2000  # specifies how often the clock synchronizes (in ms)

class Clock():
    def __init__(self, peer, sync=False):
        self.peer = peer
        self.current = 0
        self.next_sync = 0
        self.max_gps = 0
        self.localClock = [0 for _ in range(MAX_K)]
        self.globalClock = [0 for _ in range(MAX_K)]
        self.localClockSetTimestamp = 0
        self.globalClockSetTimestamp = 0

        if sync:
            sync_thread = threading.Thread(name="sync", target=self._sync)
            sync_thread.setDaemon(True)
            sync_thread.start()

    def _getCurrentLocal(self):
        return self.localClock[self.current] + math.floor(time.time() * 1000) - self.localClockSetTimestamp

    def _getCurrentGlobal(self):
        return self.globalClock[self.current] + math.floor(time.time() * 1000) - self.globalClockSetTimestamp

    def _getMlocal(self):
        result = self._getCurrentLocal()
        for t in self.localClock[:self.current] + self.localClock[self.current+1:]:
            if t > result:
                result = t
        return result

    def _getMglobal(self):
        result = self._getCurrentGlobal()
        for t in self.globalClock[:self.current] + self.globalClock[self.current+1:]:
            if t > result:
                result = t
        return result

    def _setGlobal(self, t):
        self.globalClockSetTimestamp = math.floor(time.time() * 1000)
        self.globalClock[self.current] = t

    def _setLocal(self, t):
        self.localClockSetTimestamp = math.floor(time.time() * 1000)
        self.localClock[self.current] = t

    def getLogical(self):
        logging.debug('GET LOGICAL ' + self.peer.name + ' local:' + str(self._getMlocal()) + ', global:' + str(self._getMglobal()) + ' - diff: ' + str(self._getMlocal()-self._getMglobal()))
        return max(self._getMlocal(), self._getMglobal())

    def recv(self, t, s, sender):
        logging.debug('SYNCING PEER ' + sender + ' -> ' + self.peer.name + ': ' + str(t) + '  ' + str(self._getCurrentGlobal()) + ' - diff: ' + str(t-self._getCurrentGlobal()))
        if s >= self.max_gps and t > self._getCurrentGlobal():
            self._setGlobal(t)
            self._send(t, s)
            if t/TAU >= self.next_sync:
                self.next_sync = math.floor(t/TAU) + 1

    def _sync(self):
        while True:
            while time.time() * 1000 > self.next_sync * TAU:
                self._send(self._getCurrentLocal(), self.max_gps)
                self.next_sync = math.floor(time.time() * 1000 / TAU) + 1
            time.sleep(TAU/1000)

    def _send(self, t, s):
        self.peer._send_msg("CLOCKSYNC", {'t': str(t), 's': str(s)})

    def gps(self, t):
        if t > self.max_gps:
            self.max_gps = t
            self._increaseCurrent()
            self._setLocal(t)
            self._setGlobal(t)
            self.next_sync = math.floor(t/TAU) + 1

    def _increaseCurrent(self):
        self.current = (self.current + 1) % MAX_K
