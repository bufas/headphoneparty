import tkinter as tk
import threading
import time
from threading import Lock

class Visualizer(tk.Frame):
    colors = ['black', 'magenta', 'red', 'blue', 'green', 'gray', 'orange', 'DeepPink', 'Tan', 'Navy']
    GUI_SCALE = 5

    def __init__(self, peers, peer_controller):
        self.peers = peers
        self.peer_controller = peer_controller
        self.lastColorAssigned = 0
        self.redraw = False
        self.close = False
        self.removedPeers = []

    def visualize(self):
        tk.Frame.__init__(self, None)

        canvasWidth = self.peer_controller.worldSize['width'] / self.GUI_SCALE
        canvasHeight = self.peer_controller.worldSize['height'] / self.GUI_SCALE

        tk.Button(self, text='Move', command=self.buttonAction).pack()
        tk.Button(self, text='Who can first peer reach?',
                  command=lambda: self.peer_controller.findPeersInRange(self.peers[0])).pack()
        self.canvas = tk.Canvas(self, width=canvasWidth, height=canvasHeight)

        self.pack()

        self.drawWorld()

        thread = threading.Thread(name="redrawcheck", target=self.redrawcheck, args=[])
        thread.setDaemon(True) 
        thread.start()


        self.mainloop()


    def _closeWin(self):
        self.quit()

    def redrawcheck(self):
        # Needed, since not allowed to call tk-methods from a different thread
        while(True):
            try:
                if self.close:
                    self._closeWin()
                    break
                while len(self.removedPeers) > 0:
                    peer = self.removedPeers.pop(0)
                    (squareID, circleID) = peer.guiID
                    self.canvas.delete(squareID)
                    self.canvas.delete(circleID)
                if self.redraw:
                    self.redraw = False
                    self.drawWorld()
            except Exception:
                break
            time.sleep(0.01)

    def removePeer(self, peer):
        self.removedPeers.append(peer)


    def buttonAction(self):
        self.peer_controller.movePeers()
        self.drawWorld()

    def drawPeer(self, peer):
        peer.color = self.colors[self.lastColorAssigned % len(self.colors)]
        self.lastColorAssigned += 1

        scaledRadioRange = self.peer_controller.RADIO_RANGE / self.GUI_SCALE
        #squareID = self.canvas.create_rectangle(peer.x, peer.y, peer.x + 5, peer.y + 5, outline=peer.color,
        #                                        fill=peer.color)
        squareID = self.canvas.create_text(peer.x, peer.y, font=("Arial", 10, "bold"),
                                           text=peer.name, fill=peer.color)
        circleID = self.canvas.create_oval(peer.x - scaledRadioRange + 3, peer.y - scaledRadioRange + 3,
                                           peer.x + scaledRadioRange + 3, peer.y + scaledRadioRange + 3,
                                           outline=peer.color)

        peer.guiID = (squareID, circleID)

    def drawWorld(self):
        # Move all peers to current locations
        for peer in self.peers:
            if peer.guiID is None:
                self.drawPeer(peer)

            x = peer.x
            y = peer.y
            x /= self.GUI_SCALE
            y /= self.GUI_SCALE
            scaledRadioRange = self.peer_controller.RADIO_RANGE / self.GUI_SCALE

            (squareID, circleID) = peer.guiID

            self.canvas.coords(squareID, x, y)
            self.canvas.coords(circleID,
                               x - scaledRadioRange + 3, y - scaledRadioRange + 3,
                               x + scaledRadioRange + 3, y + scaledRadioRange + 3)

        # Redraw the canvas
        self.canvas.pack()
