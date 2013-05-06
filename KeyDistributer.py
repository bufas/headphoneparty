from KeyGeneration import KeyHandler


class KeyDistributer:
    def __init__(self):
        self.key = KeyHandler(KeyHandler.generateKey(), None)

    def createKeyPair(self):
        newKey = KeyHandler.generateKey()
        pksign = self.key.signMessage(newKey.publickey())
        key = KeyHandler(newKey, pksign)
        return key, pksign, self.key.getPublicKey()

