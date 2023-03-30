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
course = 0			# Eigener Kurs / Winkel zum Nordpol
deadtime1 = 10			# Zeit seit dem letzten Signal, ab wann markiert wird
deadtime2 = 30			# ... , ab wann nicht mehr anzeigen (Dump1090 intern ab 300s)
scale = 0.1			# Maßstab (km pro Pixel)

# Bildschirmmaße definieren
screen_width = 800
screen_height = 410
screen = (screen_width, screen_height)
Menuebreite = 100
Menuekante = int(screen_width - Menuebreite)
# Eigene Positon im Bildschirm
centerposx = (screen_width - Menuebreite) / 2 + 0
centerposy = screen_height / 2 + 0
centerpos = (int(centerposx), int(centerposy))


# Farben definieren
white = (255, 255, 255)
gray = (128, 128 ,128)
black = (0, 0, 0)
red = (255, 0, 0)
green = (0, 128, 0) 


###--FUNKTIONEN--------------------

# GPS initialisieren
gps = Serial('/dev/ttyS0', 9600)

def read_gps_data():
	global lat
	global lon
	global gps_signal
	global gps_thread_running
	while gps_thread_running:	
		line = gps.readline().decode('utf-8')
		if line.startswith('$GPGGA'):
			data = line.split(',')
			if data[2]:
				gps_signal = True
				lat = float(data[2][:2]) + float(data[2][2:]) / 60
				lon = float(data[4][:3]) + float(data[4][3:]) / 60
#				print("GPS")
			else:
#				print("Kein GPS-Signal")
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

# Pixelkoordinaten bestimmen
def getPixelx(planedist, planeangl):
	angl = planeangl - course
	dist = planedist / scale
	x = int(round(math.sin(math.radians(angl)) * dist))
#	print("AbsolutX:", abs(x))
	if x > (screen_width / 2):
		x = (screen_width / 2)
	if x < (screen_width / -2):
		x = (screen_width / -2)
	return x

def getPixely(planedist, planeangl):
	angl = planeangl - course
	dist = planedist / scale
	y = int(round(math.cos(math.radians(angl)) * dist))
#	print("AbsolutY:", abs(y))
	if y > (screen_height / 2):
		y = (screen_height / 2)
	if y < (screen_height / -2):
		y = (screen_height / -2)
	return y

# Flugzeugsymbol zeichnen
def drawPlane(coords, color, dir, size):
	Planefont  = pygame.font.Font('/home/adsbpi/ADS-B_Empfaenger/fa-solid-900.ttf', size)
	Planetext = Planefont.render(chr(0xE22D) , True, color)
	Planetext_rect = Planetext.get_rect()
	Planetext_rect.center = coords
	screen.blit(Planetext, Planetext_rect)
	return

# Fenster erstellen und Fenstertitel vergeben
screen = pygame.display.set_mode(screen , pygame.RESIZABLE)
pygame.display.set_caption('ADS-B Empfänger Version 1')

# Font definieren
font = pygame.font.Font(None, 27)
fontS = pygame.font.Font(None, 20)


# Quit-Button Eigenschaften
button_width = Menuebreite
button_height = 60
button_x = screen_width - button_width
button_y = screen_height - button_height

#time.sleep(1.5)

pygame.display.update()
#print("123")

#print("Testabstand: ",Abstand(lat,lon,(lat-1),(lon-1)))
#print("Testwinkel: ",Winkel(lat,lon,(lat-1),(lon-1)))
#print("X: ", getPixelx(20, 45), "Y: ",getPixely(20,45))

#print(fa.icons['thumbs-up'])

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
	
	pygame.draw.line(screen, gray, [Menuekante - 4, 0], [Menuekante - 4, screen_height], 2)

	# Variable anzeigen
	lattext = font.render(str(round(lat, 5)), True, black)
	lontext = font.render(str(round(lon, 5)), True, black)
	screen.blit(lattext, (Menuekante, 40))
	screen.blit(lontext, (Menuekante, 60))

	# GPS-Status anzeigen
	if gps_signal:
		screen.blit(font.render("GPS", True, green), (Menuekante, 10))
	else:
		screen.blit(font.render("Kein GPS", True, red), (Menuekante, 10))

	#Schaltfläche
	pygame.draw.rect(screen, gray, (button_x, button_y, button_width, button_height))
	text = font.render("Quit", True, black)
	text_rect = text.get_rect(center=(button_x + button_width // 2, button_y + button_height // 2))
	screen.blit(text, text_rect)

	# Eigene Position darstellen
	drawPlane(centerpos, green, 0 ,40)

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
#				print("Abstand: ",planedist, "Winkel: ", planeangl)
				planepixelpos = (int(centerposx + getPixelx(planedist, planeangl)), int(centerposy - getPixely(planedist, planeangl)))
				if aircraft.get('seen') > deadtime1:
					planecolor = gray
				else:
					planecolor = black
				pygame.draw.circle(screen, planecolor, (planepixelpos) , 10)
				screen.blit(fontS.render(aircraft.get('hex'), True, black), tuple(map(sum, zip(planepixelpos,(10,-10)))))

#	screen.blit(font.render(("Flugzeuge:", planedetec_raw), True, black, (19, (screen_height - 40))))
#	screen.blit(font.render(("Davon mit Loc:", planedetec_loc), True, black, (19, ))))

	rawtext = font.render(("R: " + str(planedetec_raw)), True, black)
	loctext = font.render(("L: " + str(planedetec_loc)), True, black)
	screen.blit(rawtext, (Menuekante, (screen_height - (button_height + 50))))
	screen.blit(loctext, (Menuekante, (screen_height - (button_height + 30))))


#	print("Anzahl: ",planedetec_raw," Davon Loc: ", planedetec_loc)
#	time.sleep(1)
	pygame.display.update()
	pygame.time.Clock().tick(60)

p.terminate()
gps_thread_running = False
gps_thread.join()
pygame.quit()
sys.exit()
