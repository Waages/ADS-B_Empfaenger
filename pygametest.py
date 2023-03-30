import pygame
import sys
import time
import threading
from serial import Serial
import subprocess
import json
import urllib.request
import math

# Dump1090 starten
p = subprocess.Popen(['sudo', './dump1090', '--quiet', '--net'], cwd="/home/adsbpi/dump1090")
url = "http://localhost:8080/data/aircraft.json"

# Pygame initialisiern
pygame.init()


# Variablen
gps_thread_running = True	# Läuft der GPS-Thread
gps_signal = False		# GPS-Signalempfang
planedetec_raw = 0		# Anzahl an detektierter Flugzeuge
planedetec_loc = 0		# Anzahl an detek. Flug. mit Koordinaten
lat = 48.55			# Eigene Position Breitengrad
lon = 8.84			# Eigene Position Längengrad
deadtime1 = 10			# Zeit seit dem letzten Signal, ab wann markiert wird
deadtime2 = 30			# ... , ab wann nicht mehr anzeigen (Dump1090 intern ab 300s)
scale = 0.05			# Maßstab (km pro Pixel)


# GPS initialisieren
gps = Serial('/dev/ttyS0', 9600)

def read_gps_data():
	global lat
	global lon
	global gps_thread_running
	while gps_thread_running:	
		line = gps.readline().decode('utf-8')
		if line.startswith('$GPGGA'):
			data = line.split(',')
			if data[2]:
				gps_signal = True
				lat = float(data[2][:2]) + float(data[2][2:]) / 60
				lon = float(data[4][:3]) + float(data[4][3:]) / 60
			else:
				print("Kein GPS-Signal")
				gps_signal = False
		time.sleep(0.1)

gps_thread = threading.Thread(target=read_gps_data)
gps_thread.start()

# Abstandsbestimmungsfunktion anhand der Haversine Formel

def Abstand(lat, lon, planelat, planelon):
	R = 6371	# Erdradius in Kilometern
	phi1 = math.radians(lat)
	phi2 = math.radians(planelat)
	d_phi = math.radians(planelat - lat)
	d_lambda = math.radians(planelon - lon)
	a = math.sin(d_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2)**2
	c = 2* math.atan2(math.sqrt(a), math.sqrt(1-a))
	d = R * c
	return d


# Winkelbestimmung 
def Winkel(lat, lon, planelat, planelon):
	phi1 = math.radians(lat)
	phi2 = math.radians(planelat)
	d_lambda = math.radians(planelon - lon)
	x = math.cos(phi2) * math.sin(d_lambda)
	y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
	theta = math.atan2(x,y)
	alpha = math.degrees(theta)
	return alpha

# Bildschirmmaße definieren
screen_width = 800
screen_height = 400
screen = (screen_width, screen_height)
# Eigene Positon im Bildschirm
centerposx = screen_width / 2 + 0
centerposy = screen_height / 2 + 0
centerpos = (centerposx, centerposy)

# Fenster erstellen und Fenstertitel vergeben
screen = pygame.display.set_mode(screen , pygame.RESIZABLE)
pygame.display.set_caption('Hier steht Text')

# Farben definieren
white = (255, 255, 255)
gray = (128, 128 ,128)
black = (0, 0, 0)

# Font definieren
font = pygame.font.Font(None, 20)

# Kreis Eigenschaften
circle_radius = 100
circle_x = screen_width // 2
circle_y = screen_height // 2

# Quit-Button Eigenschaften
button_width = 120
button_height = 60
button_x = screen_width - button_width
button_y = screen_height - button_height

time.sleep(0.5)


pygame.display.update()
print("123")

print("Testabstand: ",Abstand(lat,lon,(lat-1),(lon-1)))
print("Testwinkel: ",Winkel(lat,lon,(lat-1),(lon-1)))


running = True
while running:
	# Events überprüfen
	for event in pygame.event.get():
		if event.type == pygame.QUIT:
			pygame.quit()
			quit()
		elif event.type == pygame.MOUSEBUTTONDOWN:
			mouse_pos = pygame.mouse.get_pos()
			if button_x <= mouse_pos[0] <= button_x + button_width and button_y <= mouse_pos[1] <= button_y + button_height:
				running = False
	# Hintergrund einfärben
	screen.fill(white)
	
	# Variable anzeigen
	lattext = font.render(str(lat), True, black)
	lontext = font.render(str(lon), True, black)
	screen.blit(lattext, (19, 10))
	screen.blit(lontext, (19, 30))

	# GPS-Status anzeigen
	if gps_signal == True:
		screen.blit(font.render("GPS-Empfang", True, black), (19, 50))
	else:
		screen.blit(font.render("Kein GPS", True, black), (19, 50))

	#Schaltfläche
	pygame.draw.rect(screen, gray, (button_x, button_y, button_width, button_height))
	text = font.render("Quit", True, black)
	text_rect = text.get_rect(center=(button_x + button_width // 2, button_y + button_height // 2))
	screen.blit(text, text_rect)


	# Dump1090 auslesen
	response = urllib.request.urlopen(url)
	data = json.loads(response.read())
	planedetec_raw = 0
	planedetec_loc = 0
	for aircraft in data['aircraft']:
		if aircraft.get('seen')  < deadtime2:
			planedetec_raw += 1
			if 'lat' in aircraft:
				planedetec_loc += 1
				planelat = aircraft.get('lat')
				planelon = aircraft.get('lon')
				planedist = Abstand(lat, lon, planelat, planelon)
				planeangl = Winkel(lat, lon, planelat, planelon)
				print("Abstand: ",planedist, "Winkel: ", planeangl)
#	print("Anzahl: ",planedetec_raw," Davon Loc: ", planedetec_loc)
#	time.sleep(1)
	pygame.display.update()
	pygame.time.Clock().tick(60)

p.terminate()
gps_thread_running = False
gps_thread.join()
pygame.quit()
sys.exit()

