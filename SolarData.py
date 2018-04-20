import datetime
import math
import numpy as np
import urllib.request as request

#defaultStartYear = 1983
defaultStartYear = 1995
#defaultStartYear = 2003

def fetchDaily(lat,lon,startYear=defaultStartYear,endYear=2005,startMonth=1,endMonth=12,
    startDay=1,endDay=31):
    endpoint = ('https://eosweb.larc.nasa.gov/cgi-bin/sse/homer.cgi?ye={3}&'
        'lat={0}&submit=GetDailyDataasplaintext&me={5}&daily=swv_dwn&email='
        'skip@larc.nasa.gov&step=1&p=&ms={4}&ys={2}&de={7}&lon={1}&ds={6}'
        ).format(lat,lon,startYear,endYear,startMonth,endMonth,startDay,
        endDay)

    try:
        resource = request.urlopen(endpoint)
        stringData = resource.read().decode('utf-8')
        numData = [float(x) for x in stringData.split(' ')]
    except:
        raise ValueError('Could not fetch data at lat={0}, lon={1}',lat,lon)

    return numData

def calcIrradianceVectorOverDay(lat,lon,date,resolution,tOffset,flag='clearsky',flagVal=1):
    #date: A date object representing the day we are calculating the irradiance vector for
    #resolution: time period in hours of the vector to be returned
    #tOffset: timedelta object representing the difference between local time and solar time
    #flag:
    #   'clearsky': calculate clear sky irradiance
    #   'clearness': calculate clear sky irradiance and scale by provided clearness index through 'flagVal'
    #   'mean': calc clear sky and scale so that mean irradiance is equal to number (kW/m^2) provided through 'flagVal'
    #   'insolation': calc clear sky and scale so that total insolation over the day is equal to number (kWh/m^2) provided through 'flagVal'


    if (resolution > 12):
        raise ValueError('Cannot have a resolution greater than 12 hours')

    dayOfYear = (date - datetime.date(date.year,1,1)).days+1 #day of year in [1,365]
    coercedDate = datetime.datetime.combine(date,datetime.time.min)-tOffset

    acosd = lambda x : math.degrees(math.acos(x))
    tand = lambda x : math.tan(math.radians(x))
    cosd = lambda x : math.cos(math.radians(x))
    sind = lambda x : math.sin(math.radians(x))

    #Get the average insolation of a time period with midpoint 't_utc'
    #over 'resolution' number of hour.
    decl = 23.45*sind(360*(284+dayOfYear)/365) #declination
    Gon = 1.367*(1+0.033*cosd(360*dayOfYear/365)) #extraterrestrial normal radiation kW/m^2
    getClearSkyMeanIrradianceFromInterval = lambda w1,w2: Gon*(cosd(lat)*cosd(decl)*(sind(w2)-sind(w1))*180/math.pi/((w2-w1)%360)+sind(lat)*sind(decl)) # Average irradiance from integration kW/m^2.  Interval must be during light!
    getClearSkyInsolationFromInterval = lambda w1,w2: getClearSkyMeanIrradianceFromInterval(w1,w2)*((w2-w1)%360)/15 # Cumulative irradiance from integration kWh/m^2. Requires that sunrise < w1 < w2 < sunset

    sunset = acosd(-tand(lat)*tand(decl))
    sunrise = 360-sunset

    if flag == 'clearsky':
        clearnessIndex = 1
    elif flag == 'clearness':
        clearnessIndex = flagVal
    elif flag == 'mean':
        meanIrradiance = flagVal
        clearnessIndex = meanIrradiance/(getClearSkyInsolationFromInterval(sunrise,sunset)/24)
    elif flag == 'insolation':
        meanIrradiance = flagVal/24
        clearnessIndex = meanIrradiance/(getClearSkyInsolationFromInterval(sunrise,sunset)/24)
    else:
        raise ValueError('Invalid flag')

    #Parameters for calculating solar hour given obliquity of orbit
    B = 360*(dayOfYear-1)/365
    E = 3.82*(0.000075+0.001868*cosd(B)-0.032077*sind(B)-0.014615*cosd(2*B)-0.04089*sind(2*B)) #Equation of time for obliquity

    def getClearSkyIrradianceFromMidpoint(t_utc):

        solarHour = t_utc.hour+(t_utc).minute/60+lon/15 + E

        #Calculate the beginning and end of the integration period
        w1 = (solarHour-resolution/2-12)*15 % 360
        w2 = (solarHour+resolution/2-12)*15 % 360

        #Adjust the bounds of integration if period includes nighttime.
        w1dark = w1>=sunset and w1<=sunrise
        w2dark = w2>=sunset and w2<=sunrise
        if (w1dark and w2dark): # The entire period is dark, so irradiance = 0;
            return 0
        if (w1dark):
            w1 = 360-sunset
        if (w2dark):
            w2 = sunset

        return getClearSkyMeanIrradianceFromInterval(w1,w2)*((w2-w1)%360)/(resolution*15) #scaling term is to compensate for when w2-w1 is not the even interval and weight accordingly

    N = round(24/resolution)
    irradiance = []
    time = []

    for k in range(N):
        t_utc = coercedDate + datetime.timedelta(minutes=k*round(resolution*60))
        irradiance.append(getClearSkyIrradianceFromMidpoint(t_utc)*clearnessIndex)
        time.append(t_utc)

    return {
        'irradiance': irradiance,
        'time': time,
        'clearnessIndex': clearnessIndex
    }


def loadDaily(db,lat,lon,startYear=defaultStartYear,endYear=2005,startMonth=1,endMonth=12,
    startDay=1,endDay=31):

    try:
        data,id = db.loadDailySolar(lat,lon,startYear,endYear,startMonth,endMonth,
            startDay,endDay) #Try to load it
        if (len(data) < 1): #If it's not there, fetch it then save it
            data = saveDaily(db,lat,lon,startYear,endYear,startMonth,endMonth,
            startDay,endDay)
    except:
        data,id = saveDaily(db,lat,lon,startYear,endYear,startMonth,endMonth,
        startDay,endDay)

    return data,id

def loadHourly(db,lat,lon,startYear=defaultStartYear,endYear=2005,startMonth=1,endMonth=12,
    startDay=1,endDay=31):

    try:
        data,id = db.loadHourlySolar(lat,lon,startYear,endYear,startMonth,endMonth,
            startDay,endDay) #Try to load it
        if (len(data) < 1): #If it's not there, fetch it then save it
            data = saveHourly(db,lat,lon,startYear,endYear,startMonth,endMonth,
            startDay,endDay)
    except:
        data,id = saveHourly(db,lat,lon,startYear,endYear,startMonth,endMonth,
        startDay,endDay)

    return np.array(data),id

def saveDaily(db,lat,lon,startYear=defaultStartYear,endYear=2005,startMonth=1,endMonth=12,
    startDay=1,endDay=31):
    dailyInsolation = fetchDaily(lat,lon,startYear,endYear,startMonth,endMonth,
        startDay,endDay)

    #Save the data
    id = db.saveDailySolar(dailyInsolation,lat,lon,startYear,endYear,startMonth,
        endMonth,startDay,endDay)

    return dailyInsolation,id

def saveHourly(db,lat,lon,startYear=defaultStartYear,endYear=2005,startMonth=1,endMonth=12,
    startDay=1,endDay=31):
    dailyInsolation,_ = loadDaily(db,lat,lon,startYear,endYear,startMonth,endMonth,startDay,
        endDay)
    startDate = datetime.date(startYear,startMonth,endMonth)
    Ndays = len(dailyInsolation)
    Nhours = Ndays*24
    hourlyInsolation = []
    for i in range(Ndays):
        d = startDate + datetime.timedelta(days=i)
        x = calcIrradianceVectorOverDay(lat,lon,d,1,
            datetime.timedelta(hours=lon/15),'insolation',dailyInsolation[i])
        hourlyInsolation = hourlyInsolation + x['irradiance']

    #Save the data
    id = db.saveHourlySolar(hourlyInsolation,lat,lon,startYear,endYear,startMonth,endMonth,
        startDay,endDay)

    return hourlyInsolation,id
