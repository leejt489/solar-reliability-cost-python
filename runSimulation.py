import matplotlib.pyplot as plt

import AppDatabase
import SolarData
import ReliabilityCalculator

#AppDatabase.uninstall()
#AppDatabase.install()

db = AppDatabase.Database()
db.connect()

lat = 10
lon = 10
r1 = 0.9
r2 = 0.95
r3 = 0.98
r4 = 0.99
latLonArray = [(lat,lon)]

rf = ReliabilityCalculator.loadHourlyReliabilityFrontiers(db,latLonArray,[r1,r2,r3,r4])

db.disconnect()

solCap1 = rf[r1]['solCap']
storCap1 = rf[r1]['storCap']
solCap2 = rf[r2]['solCap']
storCap2 = rf[r2]['storCap']
solCap3 = rf[r3]['solCap']
storCap3 = rf[r3]['storCap']
solCap4 = rf[r4]['solCap']
storCap4 = rf[r4]['storCap']

#Test plot
plt.figure()
plt.plot(storCap1,solCap1,storCap2,solCap2,storCap3,solCap3,storCap4,solCap4)
plt.xlabel('Storage capacity')
plt.ylabel('Solar capacity')
plt.savefig('Figures/tesplot.png')
plt.close()
