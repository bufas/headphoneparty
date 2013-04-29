from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA


class Generator():
    BIT_MASK = 0b0000111  # Write 1 on the positions you want to be 0 in the hash

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
            h1.update(str(publicKey.n).encode('utf-8'))
            h1.update(str(publicKey.e).encode('utf-8'))

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
        print()
        print('YAY, we solved the crypto puzzle after ' + str(counter) + ' tries.')
        print('The resulting hash was: ' + h2.hexdigest())

g = Generator()