import unittest
import simulations
import time
import math
import os

def createdir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

createdir("logs")
createdir("logs/NO_OF_PEERS")
createdir("logs/RADIO_RANGE")
createdir("logs/TOP_SPEED")
createdir("logs/MAX_SPEED_CHANGE")
createdir("logs/SIM_ROUNDS")
createdir("logs/SIM_SLEEP")
createdir("logs/SIM_VOTE_PROB")
createdir("logs/SIM_MOVE_PROB")
createdir("logs/SIM_KILL_PROB")

def write_logs(folder, fileprefix, timestamp, statusTxt):
    f = open('logs/'+folder+'/log-'+fileprefix+'-'+timestamp+".txt",'w')
    f.write(statusTxt)
    f.close()

def store_csv(folder, fileprefix, timestamp, data):
    f = open('logs/'+folder+'/csv-'+fileprefix+'-'+timestamp+".csv",'w')
    f.write(data)
    f.close()


def tracebackString(errs):
    try:
        errorsTxt = ""
        for (_, trace) in errs:
            errorsTxt += trace + "\n\n-----------\n"
        return errorsTxt
    except Exception:
        return "Error getting traceback"

DEFAULT_NO_OF_PEERS = 10
DEFAULT_RADIO_RANGE = 600
DEFAULT_TOP_SPEED = 75
DEFAULT_MAX_SPEED_CHANGE = 50
DEFAULT_SIM_ROUNDS = 10
DEFAULT_SIM_SLEEP = 0.05
DEFAULT_SIM_VOTE_PROB = 15
DEFAULT_SIM_MOVE_PROB = 60
DEFAULT_SIM_KILL_PROB = 5

msgtypes = sorted(["VOTE", "VOTES", "GETLIST", "PLAYLIST", "CLOCKSYNC"])
songs = sorted(["A", "B", "C", "D", "E", "F"])

tests = [('NO_OF_PEERS', 10, [1,2,3,5,10,20,25,30,40,50]),
         ('RADIO_RANGE', 10, [100,300,600,1000,1500,2000,999999]),
         ('TOP_SPEED', 10, [10,40,60,75,100,200]),
         ('MAX_SPEED_CHANGE', 10, [10,30,50,70,100]),
         ('SIM_ROUNDS', 10, [10, 50, 100, 300, 500]),
         ('SIM_SLEEP', 10, [0, 0.05, 0.5, 1, 3]),
         ('SIM_VOTE_PROB', 10, [1, 10, 20, 50, 80, 100]),
         ('SIM_MOVE_PROB', 10, [5, 10, 25, 50, 100]),
         ('SIM_KILL_PROB', 10, [0, 5, 10, 20, 50, 75])]

#tests = [('NO_OF_PEERS', 3, [2,3])]

for test in tests:
    (param, rounds, paramvals) = test

    allroundsCsvrows = ""

    for paramval in paramvals:
        roundcsvrows = ""

        acc_roundsOK = 0
        avg_exectime = 0
        avg_msgs = 0
        avg_datasize = 0
        avg_msgtypes = {}
        avg_peerskilled = 0
        avg_peersinrange = 0
        avg_peersoutofrange = 0
        avg_connectedsets = 0
        avg_songVotes = {}

        for song in songs:
            avg_songVotes[song] = 0
        
        for round in range(rounds):

            suite = unittest.TestSuite()
            sim = simulations.RandomVoting('test_randomVotes')
            suite.addTest(sim)
            testresult = sim.defaultTestResult()

            sim.force_visualize = False
            sim.RAND_SEED = None
            sim.NO_OF_PEERS = DEFAULT_NO_OF_PEERS
            sim.RADIO_RANGE = DEFAULT_RADIO_RANGE
            sim.TOP_SPEED = DEFAULT_TOP_SPEED
            sim.MAX_SPEED_CHANGE = DEFAULT_MAX_SPEED_CHANGE
            sim.SIM_ROUNDS = DEFAULT_SIM_ROUNDS
            sim.SIM_SLEEP = DEFAULT_SIM_SLEEP
            sim.SIM_VOTE_PROB = DEFAULT_SIM_VOTE_PROB
            sim.SIM_MOVE_PROB = DEFAULT_SIM_MOVE_PROB
            sim.SIM_KILL_PROB = DEFAULT_SIM_KILL_PROB

            if param == 'NO_OF_PEERS':
                sim.NO_OF_PEERS = paramval
            elif param == 'RADIO_RANGE':
                sim.RADIO_RANGE = paramval
            elif param =='TOP_SPEED':
                sim.TOP_SPEED = paramval
            elif param == 'MAX_SPEED_CHANGE':
                sim.MAX_SPEED_CHANGE = paramval
            elif param == 'SIM_ROUNDS':
                sim.SIM_ROUNDS = paramval
            elif param == 'SIM_SLEEP':
                sim.SIM_SLEEP = paramval
            elif param == 'SIM_VOTE_PROB':
                sim.SIM_VOTE_PROB = paramval
            elif param == 'SIM_MOVE_PROB':
                sim.SIM_MOVE_PROB = paramval
            elif param == 'SIM_KILL_PROB':
                sim.SIM_KILL_PROB = paramval

            starttime = time.time()
            suite.run(testresult)
            endtime = time.time()

            ok = testresult.wasSuccessful()
            errors = testresult.errors
            failures = testresult.failures
            unexpectSucc = testresult.unexpectedSuccesses

            if ok:
                pureexectime = (sim.endtime - sim.starttime)
            else:
                pureexectime = endtime - starttime
            exectime = math.ceil(pureexectime * 10) / 10 #secs



            router = sim.router
            stats = router.stats()
            details = sim.details
            stat_peersKilledCnt = sim.stat_peersKilledCnt
            stat_peersInRangeCnt = sim.stat_peersInRangeCnt
            stat_peersOutOfRangeCnt = sim.stat_peersOutOfRangeCnt
            stat_songVotes = sim.stat_songVotes
            stat_connSetsCnt = sim.stat_connSetsCnt
            timeoutocc = ("Timeout" in (tracebackString(errors)) or ("Timeout" in tracebackString(failures)))

            timestamp = str(time.strftime("%b%d%Y-%H%M%S"))

            paramsstr = "NO_OF_PEERS: " + str(sim.NO_OF_PEERS) + "\n" + \
                        "RADIO_RANGE: " + str(sim.RADIO_RANGE) + "\n" + \
                        "TOP_SPEED: " + str(sim.TOP_SPEED) + "\n" + \
                        "MAX_SPEED_CHANGE: " + str(sim.MAX_SPEED_CHANGE) + "\n" + \
                        "SIM_ROUNDS: " + str(sim.SIM_ROUNDS) + "\n" + \
                        "SIM_SLEEP: " + str(sim.SIM_SLEEP) + "\n" + \
                        "SIM_VOTE_PROB: " + str(sim.SIM_VOTE_PROB) + "\n" + \
                        "SIM_MOVE_PROB: " + str(sim.SIM_MOVE_PROB) + "\n" + \
                        "SIM_KILL_PROB: " + str(sim.SIM_KILL_PROB) + "\n"

            msgcnt = router.get_msgcnt()
            msgsize = router.get_msgsize()
            msgtypecnt = router.get_msgtypecnt()


            # Accumulate
            if ok:
                acc_roundsOK += 1
                avg_exectime += pureexectime
                avg_msgs += msgcnt
                avg_datasize += msgsize
                for msgtype in msgtypecnt:
                    if not msgtype in avg_msgtypes:
                        avg_msgtypes[msgtype] = 0
                    avg_msgtypes[msgtype] += msgtypecnt[msgtype]
                avg_peerskilled += stat_peersKilledCnt
                avg_peersinrange += stat_peersInRangeCnt
                avg_peersoutofrange += stat_peersOutOfRangeCnt
                avg_connectedsets += stat_connSetsCnt
                if stat_songVotes:
                    for song in stat_songVotes:
                        avg_songVotes[song] += stat_songVotes[song]

            # Round stats
            roundcsvrow = str(round) + ";"
            if timeoutocc:
                roundcsvrow += "TIMEOUT;"
            else:
                roundcsvrow += str(ok) + ";"
            roundcsvrow += str(exectime).replace(".", ",") + ";" + \
                           str(msgcnt) + ";" + \
                           str(msgsize) + ";"
            for msgtype in msgtypes:
                if not msgtype in msgtypecnt:
                    roundcsvrow += "0;"
                else:
                    roundcsvrow += str(msgtypecnt[msgtype]) + ";"
            roundcsvrow += str(stat_peersKilledCnt) + ";" + \
                           str(stat_peersInRangeCnt) + ";" + \
                           str(stat_peersOutOfRangeCnt) + ";" + \
                           str(stat_connSetsCnt) + ";"
            for song in songs:
                if stat_songVotes and (song in stat_songVotes):
                    roundcsvrow += str(stat_songVotes[song]) + ";"
                else:
                    roundcsvrow += "?;"
            logfilename = str(paramval)
            if ok:
                logfilename += "-OK"
            else:
                if timeoutocc:
                    logfilename += "-TIMEOUT"
                else:
                    logfilename += "-FAIL"
            logfilename += "-" + timestamp
            roundcsvrow += logfilename

            if ok:
                write_logs(param, str(paramval) + "-OK", timestamp, "OK\n\n" + \
                               "EXECTIME: " + str(exectime) + " secs\n" + \
                               "--------- PARAMS ----------\n" + paramsstr + \
                               "--------- STATS ----------\n" + stats + \
                               "\n\n-------- RUN DETAILS ----------\n" + details)
            else:
                failMsg = "FAIL"
                if timeoutocc:
                    failMsg = "TIMEOUT"
                write_logs(param, str(paramval) + "-" + failMsg, timestamp, failMsg + "\n\n" + \
                               "EXECTIME: " + str(exectime) + " secs\n" + \
                               "--------- STATS ----------\n" + stats + \
                               "\n\n--------- ERRORS ---------\n" + tracebackString(errors) + \
                               "\n\n--------- FAILURES ---------\n" + tracebackString(failures) + \
                               "\n\n--------- UNEXPECTED SUCCESSES ---------\n" + tracebackString(unexpectSucc))
                

            roundcsvrows += roundcsvrow + "\n"

        # Accumulate statistics
        if acc_roundsOK == 0:
            avg_exectime = "?"
            avg_msgs = "?"
            avg_datasize = "?"
            for msgtype in avg_msgtypes:
                avg_msgtypes[msgtype] = "?"
            avg_peerskilled = "?"
            avg_peersinrange = "?"
            avg_peersoutofrange = "?"
            avg_connectedsets = "?"
            for song in avg_songVotes:
                avg_songVotes[song] = "?"
        else:
            avg_exectime = math.ceil((avg_exectime / acc_roundsOK) * 10) / 10 #secs
            avg_msgs = math.ceil(avg_msgs / acc_roundsOK)
            avg_datasize = math.ceil(avg_datasize / acc_roundsOK)
            for msgtype in avg_msgtypes:
                avg_msgtypes[msgtype] = math.ceil(avg_msgtypes[msgtype] / acc_roundsOK)
            avg_peerskilled = math.ceil(avg_peerskilled / acc_roundsOK)
            avg_peersinrange = math.ceil(avg_peersinrange / acc_roundsOK)
            avg_peersoutofrange = math.ceil(avg_peersoutofrange / acc_roundsOK)
            avg_connectedsets = math.ceil(avg_connectedsets / acc_roundsOK)
            for song in avg_songVotes:
                avg_songVotes[song] = math.ceil(avg_songVotes[song] / acc_roundsOK)
        
        allroundCsvrow = str(paramval) + ";" + str(rounds) + ";" + str(avg_exectime).replace(".", ",") + ";"
        percentageOK = math.ceil(((acc_roundsOK / rounds) * 100) * 100) / 100
        allroundCsvrow += str(percentageOK).replace(".", ",") + ";" + \
                          str(avg_msgs) + ";" + \
                          str(avg_datasize) + ";"

        for msgtype in msgtypes:
            if acc_roundsOK == 0:
                allroundCsvrow += "?;"
            else:
                if not msgtype in avg_msgtypes:
                    allroundCsvrow += "0;"
                else:
                    allroundCsvrow += str(avg_msgtypes[msgtype]) + ";"
        allroundCsvrow += str(avg_peerskilled) + ";" + \
                          str(avg_peersinrange) + ";" + \
                          str(avg_peersoutofrange) + ";" + \
                          str(avg_connectedsets) + ";"
        for song in songs:
            if song in avg_songVotes:
                allroundCsvrow += str(avg_songVotes[song]) + ";"
            else:
                allroundCsvrow += "?;"

        allroundsCsvrows += allroundCsvrow + "\n"

        # Rounds statistics combined
        roundcsv = "Round;OK;Time;Messages;Data Size;"
        for msgtype in msgtypes:
            roundcsv += msgtype + ";"
        roundcsv += "Peers Killed;Peers In Range;Peers Out Of Range;Connected Sets;"
        for song in songs:
            roundcsv += song + ";"
        roundcsv += "Log\n"

        roundcsv += roundcsvrows

        

        store_csv(param, str(paramval), str(time.strftime("%b%d%Y-%H%M%S")), roundcsv)

    # All rounds statistics
    allroundcsv = param + " Value;Rounds;Avg Time (OK);OK Percentage;Avg Messages;Avg Data Size;"
    for msgtype in msgtypes:
        allroundcsv += "Avg " + msgtype + ";"
    allroundcsv += "Avg Peers Killed;Avg Peers In Range;Avg Peers Out Of Range;Avg Connected Sets;"
    for song in songs:
        allroundcsv += "Avg " + song + ";"
    allroundcsv += "\n"
    
    allroundcsv += allroundsCsvrows
    
    store_csv(param, "RESULT", str(time.strftime("%b%d%Y-%H%M%S")), allroundcsv)
