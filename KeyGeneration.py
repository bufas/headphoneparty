from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA


class Generator():
    BIT_MASK = 0b0000001  # Write 1 on the positions you want to be 0 in the hash
    key = None

    def __init__(self):
        result = 1
        counter = 0

        # Run the loop until a valid key pair is found
        while result != 0:
            # Generate a new key pair
            keyObj = RSA.generate(2048)
            publicKey = keyObj.publickey()

            # Hash the public key
            h1 = SHA256.new()
            h1.update(str(publicKey.n).encode())
            h1.update(str(publicKey.e).encode())

            # Hash the hashed public key
            h2 = SHA256.new()
            h2.update(str(h1).encode('utf-8'))

            # AND the double hashed public key with a predefined bit mask.
            # The ANDed value must be zero for the key pair to be valid
            result = h2.digest()[0:self.BIT_MASK // 256 + 1]
            result = int.from_bytes(result, byteorder='little')
            result &= self.BIT_MASK

            # Count tries and print status messages (just for debugging)
            counter += 1
            print('Try ' + str(counter) + ', fist byte was ' + '{0:08b}'.format(result))

        # A valid key pair was found. The printed stuff is just for debugging
        self.key = keyObj

        print()
        print('YAY, we solved the crypto puzzle after ' + str(counter) + ' tries.')
        print('The resulting hash was: ' + h2.hexdigest())

    def verifyMessage(self, publicKey, message, signature):
        """Verifies a message signature"""
        messageHash = SHA256.new(message.encode()).digest()
        return publicKey.verify(messageHash, signature)

    def signMessage(self, message):
        """Signs a message with the private key"""
        messageHash = SHA256.new(message.encode()).digest()
        return self.key.sign(messageHash, None)

    def getPublicKey(self):
        return self.key.publickey()

# Test
# print('expected output: True, True, True, False, False, True')
# g = Generator()
# key1 = RSA.generate(2048)
# key1Public = key1.publickey()
#
# m1 = 'This is message 1'
# m2 = 'Message 2 is here'
# m3 = 'Yet another message'
#
# m1Hash = SHA256.new(m1.encode()).digest()
# m2Hash = SHA256.new(m2.encode()).digest()
#
# m1Sig = key1.sign(m1Hash, None)
# m2Sig = key1.sign(m2Hash, None)
#
# print(key1Public.verify(m1Hash, m1Sig))
# print(g.verifyMessage(key1Public, m1, m1Sig))
# print(g.verifyMessage(key1Public, m2, m2Sig))
#
# print(g.verifyMessage(key1Public, m1, m2Sig))
# print(g.verifyMessage(key1Public, m2, m1Sig))
#
#
# g1 = Generator()
# g2 = Generator()
# m3Sig = g1.signMessage(m3)
# g1PubKey = g1.getPublicKey()
# print(g2.verifyMessage(g1PubKey, m3, m3Sig))
