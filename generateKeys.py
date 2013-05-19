from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
import time
from KeyHandler import KeyHandler


def genKeys():
    usedkeys = []
    f = open('keys/keys.pem','w')
    while usedkeys.__len__() < 200:
        key = RSA.generate(1024)
        pksign = masterKey.sign(SHA256.new(key.publickey().exportKey()).digest(), None)[0]
        if pksign in usedkeys:
            continue
        usedkeys.append(pksign)
        f.write(key.exportKey().decode() + '\n\n')
        f.write('-----BEGIN MASTER KEY SIGN-----\n' + str(pksign) + '\n-----END MASTER KEY SIGN-----\n\n')

    f.close()


def readKeys():
    f = open('keys/keys.pem','r')
    file = f.read()
    f.close()

    keylist = []
    pksignlist = []

    start = 0
    while '-----BEGIN RSA PRIVATE KEY-----' in file[start:]:
        s = file.find('-----BEGIN RSA PRIVATE KEY-----', start)
        e = file.find('-----END RSA PRIVATE KEY-----', start) + 29 + 1

        sk = file.find('-----BEGIN MASTER KEY SIGN-----', start) + 32
        ek = file.find('-----END MASTER KEY SIGN-----', start) - 1

        keylist.append(RSA.importKey(file[s:e]))
        pksignlist.append(int(file[sk:ek]))
        start = ek + 20

    kh = KeyHandler(keylist[0], pksignlist[0], masterKey.publickey())

    # This is the function
    publickey = KeyHandler.keyFromString(keylist[1])
    print(publickey.exportKey())
    publickeyHash = SHA256.new(publickey.exportKey()).digest()
    return masterKey.publickey().verify(publickeyHash, (pksignlist[1], None))


masterKey = RSA.importKey(open('keys/master_key.pem','r').read())

t1 = time.time()
readKeys()
#genKeys()
t2 = time.time()
print("Opreation took " + str(t2-t1) + " seconds")
