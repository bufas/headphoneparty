import sys
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from KeyHandler import KeyHandler


class KeyDistributer:
    def __init__(self):
        # Initialize the master key with a keyhandler
        self.masterkey = RSA.importKey(open('keys/master_key.pem','r').read())

        # Read all the other keys from the key file
        self.keylist = self.getKeysFromFile()  # Contains (key, pksign) 2-tuples

    def getKeyPair(self):
        if self.keylist.__len__() == 0:
            sys.exit('All 200 keys are in use. Create more keys with generateKeys.py')
        (key, pksign) = self.keylist.pop()
        return KeyHandler(key, pksign, self.masterkey.publickey())

    def getKeysFromFile(self):
        # Read the file containing keys into a variable
        f = open('keys/keys.pem','r')
        fileContents = f.read()
        f.close()

        # Parse the file into a list of (key, pksign) 2-tuples
        startIndex = 0
        keylist = []
        while '-----BEGIN RSA PRIVATE KEY-----' in fileContents[startIndex:]:
            startOfkey = fileContents.find('-----BEGIN RSA PRIVATE KEY-----', startIndex)
            endOfKey = fileContents.find('-----END RSA PRIVATE KEY-----', startIndex) + 29 + 1
            startOfPksign = fileContents.find('-----BEGIN MASTER KEY SIGN-----', startIndex) + 32
            endOfPksign = fileContents.find('-----END MASTER KEY SIGN-----', startIndex) - 1

            key = RSA.importKey(fileContents[startOfkey:endOfKey])
            pksign = int(fileContents[startOfPksign:endOfPksign])

            keylist.append((key, pksign))
            startIndex = endOfPksign + 20

        return keylist