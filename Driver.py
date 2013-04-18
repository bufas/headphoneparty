import random
import math
import tkinter as tk


class SimpleTest(tk.Frame):
    """The purpose of the class is to emulate a physical space to test range and effect of wireless communication.
    Average walking speed will be 1.4, which corresponds to 5 km/h. Maximal speed in this configuration is 7.12km/h"""

    GUI_SCALE = 5
    TOP_SPEED = 140
    MAX_SPEED_CHANGE = 50
    RADIO_RANGE = 500

    def __init__(self, master=None):
        tk.Frame.__init__(self, master)
        self.peers = {}
        self.worldSize = {'width': 2000, 'height': 2000}  # in centimeters

        # GUI specific
        canvasWidth = self.worldSize['width'] / self.GUI_SCALE
        canvasHeight = self.worldSize['height'] / self.GUI_SCALE

        tk.Button(self, text='Move', command=self.buttonAction).pack()
        tk.Button(self, text='Who can Black reach?', command=lambda: self.findPeersInRange('black')).pack()
        self.canvas = tk.Canvas(self, width=canvasWidth, height=canvasHeight)

        self.pack()

    def buttonAction(self):
        self.movePeers()
        self.drawWorld()

    def addPeer(self, name):
        # Add the peer to the peer dictionary
        x = random.uniform(0, self.worldSize['width'])          # x coord of peer spawn
        y = random.uniform(0, self.worldSize['height'])         # y coord of peer spawn
        vecX = random.uniform(-self.TOP_SPEED, self.TOP_SPEED)  # x coord of peer speed vector
        vecY = random.uniform(-self.TOP_SPEED, self.TOP_SPEED)  # y coord of peer speed vector
        guiID = self.drawPeer(name, x, y)                       # Draw the peer
        self.peers[name] = (x, y, vecX, vecY, guiID)

    def drawPeer(self, color, x, y):
        scaledRadioRange = self.RADIO_RANGE / self.GUI_SCALE
        squareID = self.canvas.create_rectangle(x, y, x + 5, y + 5, outline=color, fill=color)
        circleID = self.canvas.create_oval(x - scaledRadioRange + 3, y - scaledRadioRange + 3,
                                           x + scaledRadioRange + 3, y + scaledRadioRange + 3,
                                           outline=color)
        return squareID, circleID

    def removePeer(self, name):
        del self.peers[name]

    def movePeers(self):
        for name, (x, y, vecX, vecY, itemID) in self.peers.items():
            # Check the world bounds and flip the vector to avoid collision
            if x + vecX > self.worldSize['width'] or x + vecX < 0:
                vecX = -vecX
            if y + vecY > self.worldSize['height'] or y + vecY < 0:
                vecY = -vecY

            # Move
            x += vecX
            y += vecY

            # Change the vector to change speed and direction of peer
            # Todo this could be more sophisticated...
            vecX = random.uniform(
                -self.TOP_SPEED if vecX < -self.TOP_SPEED + self.MAX_SPEED_CHANGE else vecX - self.MAX_SPEED_CHANGE,
                self.TOP_SPEED if vecX > self.TOP_SPEED - self.MAX_SPEED_CHANGE else vecX + self.MAX_SPEED_CHANGE)
            vecY = random.uniform(
                -self.TOP_SPEED if vecY < -self.TOP_SPEED + self.MAX_SPEED_CHANGE else vecY - self.MAX_SPEED_CHANGE,
                self.TOP_SPEED if vecY > self.TOP_SPEED - self.MAX_SPEED_CHANGE else vecY + self.MAX_SPEED_CHANGE)

            # Update the peer position and vector
            self.peers[name] = (x, y, vecX, vecY, itemID)

    def findPeersInRange(self, name):
        print()
        print('Finding peers in range of ' + name)

        peersInRange = []
        (meX, meY, _, _, _) = self.peers[name]
        for checkName, (x, y, _, _, _) in self.peers.items():
            if math.pow(meX - x, 2) + math.pow(meY - y, 2) < math.pow(self.RADIO_RANGE, 2) and name != checkName:
                print(checkName + ' is in range')
                peersInRange.append(checkName)

        return peersInRange

    def drawWorld(self):
        # Move all peers
        for name, (x, y, _, _, (squareID, circleID)) in self.peers.items():
            x /= self.GUI_SCALE
            y /= self.GUI_SCALE
            scaledRadioRange = self.RADIO_RANGE / self.GUI_SCALE

            self.canvas.coords(squareID, x, y, x + 5, y + 5)
            self.canvas.coords(circleID, x - scaledRadioRange + 3, y - scaledRadioRange + 3,
                               x + scaledRadioRange + 3, y + scaledRadioRange + 3)

        # Redraw the canvas
        self.canvas.pack()

# Run the test
colors = ['black', 'magenta', 'red', 'blue', 'green', 'gray', 'orange', 'DeepPink', 'Lime', 'Teal', 'Tan', 'Navy']

st = SimpleTest()
for color in colors:
    st.addPeer(color)
st.drawWorld()
st.mainloop()
