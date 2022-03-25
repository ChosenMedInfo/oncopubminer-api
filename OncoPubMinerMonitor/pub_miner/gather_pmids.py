# -*- coding: utf-8 -*-
# @Time : 2021/8/2 13:37
# @File : gather_pmids.py
# @Project : OncoPubMinerMonitor

import os
import json
from collections import defaultdict

from sys import getsizeof, stderr
from itertools import chain
from collections import deque

try:
    from reprlib import repr
except ImportError:
    pass

import pub_miner


def total_size(o, handlers=None, verbose=False):
    """
    Returns the approximate memory footprint an object and all of its contents.
    Automatically finds the contents of the following builtin containers and their subclasses:
    tuple, list, deque, dict, set and frozenset.
    To search other containers, add handlers to iterate over their contents:
    handlers = {SomeContainerClass: iter, OtherContainerClass: OtherContainerClass.get_elements}
    """
    if handlers is None:
        handlers = {}
    dict_handler = lambda d: chain.from_iterable(d.items())
    all_handlers = {tuple: iter,
                    list: iter,
                    deque: iter,
                    dict: dict_handler,
                    set: iter,
                    frozenset: iter,
                    }
    all_handlers.update(handlers)
    seen = set()
    default_size = getsizeof(0)

    def sizeof(o):
        if id(o) in seen:
            return 0
        seen.add(id(o))
        s = getsizeof(o, default_size)

        if verbose:
            print(s, type(o), repr(o), file=stderr)

        for typ, handler in all_handlers.items():
            if isinstance(o, typ):
                s += sum(map(sizeof, handler(o)))
                break
        return s

    return sizeof(o)


def memReport(variables):
    print('-' * 30)
    for var, obj in variables.items():
        if not var.startswith('_'):
            print("%s\t%.1fMB" % (var, total_size(obj) / (1024.0 * 1024.0)))
    print('-' * 30)


def gatherPMIDs(inHashDir, outPMDir, whichHashes=None, pmidExclusions=None):
    if os.path.isdir(outPMDir):
        inHashDir_modified = [os.path.getmtime(os.path.join(root, f)) for root, _, files in os.walk(inHashDir) for f
                              in files]
        outPMIDDir_modified = [os.path.getmtime(os.path.join(root, f)) for root, _, files in os.walk(outPMDir) for f
                               in files]
        if max(inHashDir_modified) < max(outPMIDDir_modified):
            print("No PMID update necessary")
            return

    files = sorted([os.path.join(inHashDir, f) for f in os.listdir(inHashDir)])

    pubMedXMLFiles = ['/datami/yueyueliu/ChosenLitReviewer/resources/PUBMED/pubmed21n0001xml']

    if True:
        maxPmidInt = -1
        for filename in files:
            # continue
            with open(filename) as f:
                hashes = json.load(f)
                keys = list(hashes.keys())
                assert len(keys) == 1
                pubMedXMLFile = keys[0]
                pubMedXMLFiles.append(pubMedXMLFile)

            tempMaxPmid = max(map(int, hashes[pubMedXMLFile].keys()))
            maxPmidInt = max(maxPmidInt, tempMaxPmid)

        pubMedXMLFiles = []
        firstFile = [None for _ in range(maxPmidInt + 1)]
        versionCounts = [0 for _ in range(maxPmidInt + 1)]

        for filename in files:
            with open(filename) as f:
                hashes = json.load(f)
                keys = list(hashes.keys())
                assert len(keys) == 1
                pubMedXMLFile = keys[0]
                pubMedXMLFiles.append(pubMedXMLFile)

            for pid in hashes[pubMedXMLFile].keys():
                pidInt = int(pid)
                if firstFile[pidInt] is None:
                    firstFile[pidInt] = pubMedXMLFile
                versionCounts[pidInt] += 1
        pidToFilename = list(firstFile)

        if True:
            runningHashes = {}
            for filename in reversed(files):
                with open(filename) as f:
                    hashes = json.load(f)
                    keys = list(hashes.keys())
                    assert len(keys) == 1
                    pubMedXMLFile = keys[0]

                for pmid in hashes[pubMedXMLFile].keys():
                    pmidInt = int(pmid)
                    if versionCounts[pmidInt] == 1:
                        continue

                    if whichHashes is None:
                        hashVal = hashes[pubMedXMLFile][pmid]
                    else:
                        try:
                            hashVal = [hashes[pubMedXMLFile][pmid][h] for h in whichHashes]
                        except KeyError as e:
                            raise RuntimeError(
                                f"The selected hash ({str(e)}) from the 'usePubMedHashes' option has not been found "
                                f"in the hash files.")

                    if pmidInt in runningHashes and runningHashes[pmidInt] != hashVal:
                        versionCounts[pmidInt] = 1
                        del runningHashes[pmidInt]
                    else:
                        runningHashes[pmidInt] = hashVal
                        pidToFilename[pmidInt] = pubMedXMLFile

                    if firstFile[pmidInt] == pubMedXMLFile and pmidInt in runningHashes:
                        del runningHashes[pmidInt]

    filenameToPMIDs = defaultdict(list)
    for pid, filename in enumerate(pidToFilename):
        if filename is not None:
            filenameToPMIDs[filename].append(pid)

    if not os.path.isdir(outPMDir):
        os.makedirs(outPMDir)

    for filename in pubMedXMLFiles:
        basename = os.path.basename(filename)
        outName = os.path.join(outPMDir, basename + '.pids')

        pids = filenameToPMIDs[filename]

        if pmidExclusions is not None:
            pids = [pid for pid in pids if pid not in pmidExclusions]

        fileAlreadyExists = os.path.isfile(outName)
        if fileAlreadyExists:
            timestamp = os.path.getmtime(outName)
            beforeHash = pub_miner.calcSHA256(outName)
            with open(outName, 'w') as f:
                for pid in pids:
                    f.write(f"{pid}\n")
            afterHash = pub_miner.calcSHA256(outName)
            if beforeHash == afterHash:  # File hasn't changed so move the modified date back
                os.utime(outName, (timestamp, timestamp))
