from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA


class KeyHandler():

    def __init__(self, key, pksign, masterpk):
        """Initialization"""
        self.key = key
        self.pksign = str(pksign)
        self.masterpk = masterpk

    def verifyMessage(self, publicKey, message, signature):
        """Verifies a message signature"""
        # Convert publickey to a key object if it is a string
        publicKey = self.keyFromString(publicKey)
        # Verify the message
        messageHash = SHA256.new(message.encode()).digest()
        return publicKey.verify(messageHash, (int(signature), None))

    def verifyPublicKey(self, publickey, pksign):
        """Verifies a publickey by checking that pksign is the signature from keyDistributer on the hashed publickey"""
        publickeyHash = SHA256.new(publickey.encode()).digest()
        return self.masterpk.verify(publickeyHash, (pksign, None))

    def signMessage(self, message):
        """Signs a message with the private key, and returns a string"""
        messageHash = SHA256.new(message.encode()).digest()
        return str(self.key.sign(messageHash, None)[0])

    def getPublicKey(self):
        """Returns the public key"""
        return str(self.key.publickey().exportKey().decode())

    def getPksign(self):
        return self.pksign

    def getKey(self):
        """Returns the actual key"""
        return self.key

    @staticmethod
    def keyFromString(key):
        """Creates a key object from a string representation"""
        if isinstance(key, str):
            return RSA.importKey(key)
        elif isinstance(key, bytes):
            return RSA.importKey(key.decode())
        return key
