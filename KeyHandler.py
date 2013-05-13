from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA


class KeyHandler():

    def __init__(self, key, pksign):
        """Initialization"""
        self.key = key
        self.pksign = pksign

    def verifyMessage(self, publicKey, message, signature):
        """Verifies a message signature"""
        messageHash = SHA256.new(message.encode()).digest()
        return publicKey.verify(messageHash, signature)

    def signMessage(self, message):
        """Signs a message with the private key"""
        messageHash = SHA256.new(message.encode()).digest()
        return self.key.sign(messageHash, None)

    def getPublicKey(self):
        """Returns the public key"""
        return self.key.publickey()


    @staticmethod
    def generateKey():
        return RSA.generate(2048)
