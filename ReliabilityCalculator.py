from collections import deque
import itertools
import math
import numpy as np
import numpy.matlib
from numpy import mean
from scipy.optimize import fsolve

import SolarData

#For debuggin and profiling
import time

def calculateReliabilityFrontier(reliability,insolation,load,
    stepSizeConst = 0.01,maxTolConst = 100, recursDepth = 0):

    tolX = min(stepSizeConst,(1-reliability))/maxTolConst;

    startSolar = 2*mean(load)/mean(insolation); #pick a starting point. Mostly arbitrary as we do a forward and backward sweep from this point

    try:
        f = lambda storCap: reliability - simulateReliability(insolation,load,startSolar,storCap)
        #s = time.time()
        startStorage = fsolve(f,0,xtol=tolX)
        #e = time.time()
        #print('fsolve took {0} seconds'.format(e-s))
        if (startStorage <= 0): #Storage has to be at least >= 0 physically. Also has to be >0 if reliability requires power at night
            startStorage = 0.001
            f = lambda solCap: reliability - simulateReliability(insolation,load,solCap,startStorage)
            startSolar = fsolve(f,startSolar,xtol=tolX)
    except:
        raise Exception('Could not calculate start storage')

    maxDer = -0.05 #Bounds of dSolCap/dStorCap for stopping.  The stopping criterion is to be negative and close to zero
    minDer = -2 #Lower bound for stopping.  Based on an upper bound of storage prices ($/kWh) being twice solar prices ($/kW).

    f = lambda storCap: reliability - simulateReliability(insolation,load,100*mean(load)/mean(insolation),storCap)
    minStorage = max(0,fsolve(f,0))
    r = stepSizeConst/startStorage #Step size for storage capacity iteration so that the step size is 0.01 around startStorage, storCap(i) = storCap(i-1)*(1+r) in forward sweep and storCap(i) = storCap(i-1)*(1-r) in backward sweep

    i = 0;
    storCap = deque([startStorage])
    solCap = deque([startSolar])
    solCapD = deque([maxDer])
    #Do forward sweep until reaching the max derivative.  We start somewhere in
    #the middle so as not to bother calculating values for solar capacity close
    #to the minStorage level (which will likely be cost prohibitive).
    while solCapD[i] <= maxDer:
        deltaStor = r*storCap[i];
        i = i+1;
        storCap.append(storCap[i-1]+deltaStor)
        f = lambda solCap: reliability - simulateReliability(insolation,load,solCap,storCap[i])
        solCapVal,_,exitFlag,mesg = fsolve(f,solCap[i-1]+deltaStor*solCapD[i-1],xtol=tolX,full_output=True) #use taylor estimate for guess of x0
        solCap.append(solCapVal)
        if exitFlag != 1:
            raise Exception('fsolve did not converge. Exit flag was {0}.'+
                ' Message: {1}'.format(exitFlag,mesg))
        solCapD.append((solCap[i]-solCap[i-1])/deltaStor)

    #Trim the first element where derivative was not defined
    solCap = deque(itertools.islice(solCap,1,len(solCap)))
    solCapD = deque(itertools.islice(solCapD,1,len(solCapD)))
    storCap = deque(itertools.islice(storCap,1,len(storCap)))

    #Do backward sweep until reaching the min derivative or min storage
    while solCapD[0] >= minDer and storCap[0] > minStorage:
        if storCap[0]-minStorage > 0.001:
            storCap.appendleft(max(storCap[0]*(1-r),minStorage)) #Going backwards, so add new point to front of array
        else:
            storCap.appendleft(minStorage)

        deltaStor = storCap[1]-storCap[0]
        f = lambda solCap: reliability - simulateReliability(insolation,load,solCap,storCap[0])
        solCapVal,_,exitFlag,mesg = fsolve(f,solCap[0]-deltaStor*solCapD[0],xtol=tolX,full_output=True)
        if exitFlag !=1:
            raise Exception('Fzero did not converge. Exit flag was ' + str(exitFlag))

        solCap.appendleft(solCapVal)
        solCapD.appendleft((solCap[1]-solCap[0])/deltaStor)

    #Only return elements within the derivative range (filters out cases where
    #the forward sweep started with a very negative derivative, or backward
    #sweep started with a very flat derivative.
    #Also transpose into column vectors
    solCap = np.array(solCap) #Convert to np array for logical indexing
    storCap = np.array(storCap)
    solCapD = np.array(solCapD)
    t = np.logical_and(solCapD >= minDer, solCapD <= maxDer)
    solCap =  solCap[t]
    storCap = storCap[t]
    solCapD = solCapD[t]

    if np.any(solCapD > 0):
        raise Exception('Calculated dSol/dStor > 0')
    solCapD2 = np.diff(solCapD)
    solCap = solCap.tolist()
    storCap = storCap.tolist()
    solCapD = solCapD.tolist()
    print('solCap')
    print(solCap)
    print('solCapD')
    print(solCapD)
    print('storCap')
    print(storCap)
    print(np.logical_and(np.divide(solCapD2,np.diff(storCap)) < -0.1, solCapD2 < -0.05))
    print(np.divide(solCapD2,np.diff(storCap)))
    print('---------------------------------')
    if any(np.logical_and(np.divide(solCapD2,np.diff(storCap)) < -0.1, solCapD2 < -0.05)):
        if recursDepth < 10:
            maxTolConst = maxTolConst*10
            solCap,storCap,solCapD = calculateReliabilityFrontier(reliability,insolation,load,stepSizeConst,maxTolConst,recursDepth+1); #Recurse with a tighter tolerance to smooth numerical oscillations
        else:
            raise Exception('Calculated d^2Sol/dStor^2 < 0; i.e. significantly non-convex and recurse limit of 10 exceeded')

    if len(solCap) < 10:
        if recursDepth < 10:
            solCap,storCap,solCapD = calculateReliabilityFrontier(reliability,insolation,load,stepSizeConst/2,maxTolConst,recursDepth+1);
        else:
            raise Exception('Too few (less than 10) points returned in frontier and recurse limit of 10 exceeded');

    return solCap,storCap,solCapD

def loadHourlyReliabilityFrontiers(db,latLonArray,reliabilities,loadTypeId='constant'):
    #Loads the frontiers from memory if they exist, and calculates and saves if they don't
    #latLonArray is an array of (lat,lon) tuples

    electricLoad = []

    for (lat,lon) in latLonArray:
        lat = math.floor(lat) #Round reflects NASA data, round to ones
        lon = math.floor(lon)

        insolation,solarId = SolarData.loadHourly(db,lat,lon)
        toSave = {}
        toRtn = {}

        try:
            rf = db.loadReliabilityFrontiers(lat,lon,loadTypeId,solarId)
        except:
            rf = {}

        for r in reliabilities:
            if r <= 0 or r > 1:
                raise ValueError('reliability must be 0 < r <=1')
            rKey = ('%.6f' % r).replace('.','_')
            if rKey in rf:
                toRtn[r] = rf[rKey]
                continue
            try:
                if len(electricLoad) < 1:
                    createLoad = lambda x: np.matlib.repmat(x,round(len(insolation)/24),1)
                    if(loadTypeId == 'constant'):
                        electricLoad = createLoad(np.ones((24,1))/24)
                    else:
                        raise NotImplementedError('Custom load lookup not implemented')
                        #electricLoad = lookUpTheOtherLoadProfile()
                toRtn[r] = {}
                toRtn[r]['solCap'],toRtn[r]['storCap'],toRtn[r]['solCapD'] = calculateReliabilityFrontier(r,insolation,electricLoad)
            except Exception as e:
                print(e)
                print('-----------------')
                raise e
                raise Exception(('Could not calculate reliability for lat={},lon={}'
                    ',reliability={}. Inner Exception: {}').format(lat,lon,r,e))
            db.saveReliabilityFrontiers({rKey: toRtn[r]},lat,lon,loadTypeId,solarId)

    return toRtn

def simulateReliability(insolation,load,solarCapacity,storageCapacity):
    r,_ = simulateReliabilityAndUnmetLoad(insolation,load,solarCapacity,storageCapacity)
    return r

def simulateReliabilityAndUnmetLoad(insolation,load,solarCapacity,storageCapacity):
    #Calculates the fraction of demand served given arguments
    #Insolation and load are vectors over time with the same period and have
    #units of power (average power over period). Storage capacity has units
    #P*(period length). solarCapacity has units P.

    N = len(insolation)
    endPeriodSOC = np.zeros(N+1)
    endPeriodSOC[0] = storageCapacity
    prevSOC = storageCapacity
    unmetLoad = np.zeros(N)
    #s = time.time()
    for i in range(N):
        excessPower = solarCapacity*insolation[i]-load[i]
        nextSOC = max(0,min(storageCapacity,prevSOC+excessPower))
        endPeriodSOC[i+1] = nextSOC
        #endPeriodSOC.append(max(0,min(storageCapacity,endPeriodSOC[i]+excessPower)))
        unmetLoad[i] = max(nextSOC-prevSOC-excessPower,0)
        prevSOC = nextSOC
        #unmetLoad.append(max(endPeriodSOC[i+1]-endPeriodSOC[i]-excessPower,0))


    #e = time.time()
    #print('Loop took {0} seconds'.format(e-s))
    reliability = 1-mean(unmetLoad)/mean(load)

    return reliability,unmetLoad
