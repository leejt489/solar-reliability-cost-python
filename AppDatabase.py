import pymongo
#import numpy as np

host = 'localhost'
database = 'solar-reliability-cost'
solarCollection = 'solar'
reliabilityCollection = 'reliabilityFrontiers'

def install():
    db = Database()
    db.connect()
    db.db[solarCollection].create_index([
        ('lat', pymongo.ASCENDING),
        ('lon', pymongo.ASCENDING),
        ('startYear', pymongo.ASCENDING),
        ('endYear', pymongo.ASCENDING),
        ('startMonth', pymongo.ASCENDING),
        ('endMonth', pymongo.ASCENDING),
        ('startDay', pymongo.ASCENDING),
        ('endDay', pymongo.ASCENDING)
    ],unique=True)
    db.db[reliabilityCollection].create_index([
        ('lat', pymongo.ASCENDING),
        ('lon', pymongo.ASCENDING),
        ('loadTypeId', pymongo.ASCENDING),
        ('solarId', pymongo.ASCENDING)
    ],unique=True)
    db.disconnect()

def uninstall():
    db = Database()
    db.connect()
    db.client.drop_database(database)

class Database:

    def connect(self):
        self.client = pymongo.MongoClient(host)
        self.db = pymongo.database.Database(self.client, database)

    def disconnect(self):
        self.client.close()

    def loadDailySolar(self,lat,lon,startYear,endYear,startMonth,endMonth,
        startDay,endDay):
        solarData = self.db[solarCollection].find_one({
            'lat': lat,
            'lon': lon,
            'startYear': startYear,
            'endYear': endYear,
            'startMonth': startMonth,
            'endMonth': endMonth,
            'startDay': startDay,
            'endDay': endDay
        })
        return solarData.dailyInsolation,solarData._id

    def loadHourlySolar(self,lat,lon,startYear,endYear,startMonth,endMonth,
        startDay,endDay):
        solarData = self.db[solarCollection].find_one({
            'lat': lat,
            'lon': lon,
            'startYear': startYear,
            'endYear': endYear,
            'startMonth': startMonth,
            'endMonth': endMonth,
            'startDay': startDay,
            'endDay': endDay
        })
        return solarData['hourlyInsolation'],solarData['_id']

    def loadReliabilityFrontiers(self,lat,lon,loadTypeId,solarId):
        c = self.db[reliabilityCollection].find_one({
            'lat': lat,
            'lon': lon,
            'loadTypeId': loadTypeId,
            'solarId': solarId
        })
#        toRtn = {}
#        for r,f in c['reliabilityFrontiers']:
#            toRtn[r] = {}
#            for k,v in f:
#                toRtn[r][k] = np.array(v)
#        return toRtn
        return c['reliabilityFrontiers']

    def saveDailySolar(self,data,lat,lon,startYear,endYear,startMonth,endMonth,
        startDay,endDay):
        x = self.db[solarCollection].find_one_and_update({
            'lat': lat,
            'lon': lon,
            'startYear': startYear,
            'endYear': endYear,
            'startMonth': startMonth,
            'endMonth': endMonth,
            'startDay': startDay,
            'endDay': endDay
        },
        {
            '$set': {
                'dailyInsolation': data
            }
        },
        upsert=True,
        return_document = pymongo.ReturnDocument.AFTER
        )
        return x['_id']

    def saveHourlySolar(self,data,lat,lon,startYear,endYear,startMonth,endMonth,
        startDay,endDay):
        x = self.db[solarCollection].find_one_and_update({
            'lat': lat,
            'lon': lon,
            'startYear': startYear,
            'endYear': endYear,
            'startMonth': startMonth,
            'endMonth': endMonth,
            'startDay': startDay,
            'endDay': endDay
        },
        {
            '$set': {
                'hourlyInsolation': data
            }
        },
        upsert=True,
        return_document = pymongo.ReturnDocument.AFTER
        )
        return x['_id']

    def saveReliabilityFrontiers(self,reliabilityFrontiers,lat,lon,loadTypeId,solarId):


        self.db[reliabilityCollection].update({
            'lat': lat,
            'lon': lon,
            'loadTypeId': loadTypeId,
            'solarId': solarId
        },
        {
            '$set': {
                'reliabilityFrontiers.'+r: reliabilityFrontiers[r] for r in reliabilityFrontiers
            }
        },
        upsert=True)
