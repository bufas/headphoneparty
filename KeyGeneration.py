from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA


class Generator():
    BIT_MASK = 0b0000111  # Write 1 on the positions you want to be 0 in the hash

    def __init__(self):
        result = 1
        counter = 0

        while result != 0:
            keyObj = RSA.generate(2048)
            publicKey = keyObj.publickey()

            h1 = SHA256.new()
            h1.update(str(publicKey.n).encode('utf-8'))
            h1.update(str(publicKey.e).encode('utf-8'))

            h2 = SHA256.new()
            h2.update(str(h1).encode('utf-8'))

            result = h2.digest()[0:self.BIT_MASK // 256 + 1]
            result = int.from_bytes(result, byteorder='little')
            result &= self.BIT_MASK

            counter += 1
            print('Try ' + str(counter) + ', fist byte was ' + '{0:08b}'.format(result))

        print()
        print('YAY, we solved the crypto puzzle after ' + str(counter) + ' tries.')
        print('The resulting hash was: ' + h2.hexdigest())

g = Generator()