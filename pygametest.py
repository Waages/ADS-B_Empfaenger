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
alt = 100			# GPS-Antennenhöhe über NN in m
speed = 0			# GPS-Geschwindigkeit in kt
course = 0			# Eigener Kurs / Winkel zum Nordpol
deadtime1 = 10			# Zeit seit dem letzten Signal, ab wann markiert wird
deadtime2 = 30			# ... , ab wann nicht mehr anzeigen (Dump1090 intern ab 300s)
scale = 0.1			# Maßstab (km pro Pixel)
scale_alt = 100.0		# Zur Detektion, ob Kompass neu berechnet werden muss


# Bildschirmmaße definieren
screen_width = 800
screen_height = 480
screen = (screen_width, screen_height)
Menuebreite = 100
Menuekante = int(screen_width - Menuebreite)
Randbreite = 10

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

# Maus ausblenden
mauszeit = .3
last_mouse_movement = time.time()
pygame.mouse.set_visible(True)



###--FUNKTIONEN--------------------

# GPS initialisieren
gps = Serial('/dev/ttyS0', 9600)

def read_gps_data():
	global lat
	global lon
	global alt
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
		if line.startswith('$GPVTG'):
			data = line.split(',')
			if data[7]:
				speed = float(data[7])
				course = float(data[1])
		time.sleep(0.1)

gps_thread = threading.Thread(target=read_gps_data)
#gps_thread.start()

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
	global overedge
	angl = planeangl - course
	dist = planedist / scale
	x = int(round(math.sin(math.radians(angl)) * dist))
#	print("AbsolutX:", abs(x))
	if x > ((screen_width - Menuebreite) / 2 - Randbreite - 10):
		overedge = True
		x = ((screen_width - Menuebreite) / 2 - Randbreite - 10)
	if x < ((screen_width - Menuebreite) / -2 + Randbreite):
		overedge = True
		x = ((screen_width - Menuebreite) / -2 + Randbreite)
	return x

def getPixely(planedist, planeangl):
	global overedge
	angl = planeangl - course
	dist = planedist / scale
	y = int(round(math.cos(math.radians(angl)) * dist))
#	print("AbsolutY:", abs(y))
	if y > (screen_height / 2 - Randbreite):
		overedge = True
		y = (screen_height / 2 - Randbreite)
	if y < (screen_height / -2 + Randbreite):
		overedge = True
		y = (screen_height / -2 + Randbreite)
	return y

# Flugzeugsymbol zeichnen
def drawPlane(coords, color, dir, size, type):
	if type == 0:
		symb = chr(0xE22D) # Flugzeug normal
	elif type == 1:
		symb = chr(0xE518) # Kampfjet
	elif type == 2:
		symb = chr(0xF533) # Helikopter
	elif type == 3:
		symb = chr(0xF188) # Bug
	elif type == 4:
		symb = chr(0xF535) # unflyable
	elif type == 5:
		symb = chr(0xF6E2) # Boo
	elif type == 6:
		symb = chr(0xF67B) # FSM
	Planefont  = pygame.font.Font('/home/adsbpi/ADS-B_Empfaenger/fa-solid-900.ttf', size)
	Planetext = Planefont.render(symb , True, color)
	Planetext = pygame.transform.rotate(Planetext, -dir + course)
	Planetext_rect = Planetext.get_rect()
	Planetext_rect.center = coords
	screen.blit(Planetext, Planetext_rect)
	return

# Kompass berechnen
def calcKompass():
	maxRad = centerposy - 10
	Teiler = [200, 150,  100, 75, 50, 40, 30, 20, 10, 5, 2, 1, 0.5, 0.1]
	global Radiuskm
	global Radiuspx
	maxGef = False
	print("Radius berechnet")
	for wert in Teiler:
		if (wert/scale) < maxRad and maxGef == False:
			Radiuskm = wert
			Radiuspx = int(Radiuskm / scale)
			maxGef = True
	return

# Kompass zeichen
def drawKompass():
	pygame.draw.circle(screen, black,  centerpos, Radiuspx , 1)
	text = str(Radiuskm) + " km"
	text_width, text_height = font.size(text)
	screen.blit(font.render(text, True, black), (centerposx - (text_width / 2), int(centerposy + Radiuspx - 25)))
	return

# Fenster erstellen und Fenstertitel vergeben
screen = pygame.display.set_mode(screen , pygame.FULLSCREEN)
pygame.display.set_caption('ADS-B Empfänger Version 1')

# Font definieren
font = pygame.font.Font(None, 27)
fontS = pygame.font.Font(None, 20)
Iconfont = pygame.font.Font('/home/adsbpi/ADS-B_Empfaenger/fa-solid-900.ttf', 40)

# Quit-Button Eigenschaften
quit_btn_width = Menuebreite
quit_btn_height = 60
quit_btn_x = screen_width - quit_btn_width
quit_btn_y = 0

# Zoom-Button Eigenschaften
zoomI_btn_width = Menuebreite
zoomO_btn_width = zoomI_btn_width
zoomI_btn_height = 70
zoomO_btn_height = zoomI_btn_height
zoomI_btn_x = screen_width - zoomI_btn_width
zoomO_btn_x = screen_width - zoomO_btn_width
zoomI_btn_y = screen_height - zoomI_btn_height
zoomO_btn_y = screen_height - zoomO_btn_height - zoomI_btn_height - 5

#time.sleep(1.5)

pygame.display.update()
#print("123")

#print("Testabstand: ",Abstand(lat,lon,(lat-1),(lon-1)))
#print("Testwinkel: ",Winkel(lat,lon,(lat-1),(lon-1)))
#print("X: ", getPixelx(20, 45), "Y: ",getPixely(20,45))
touchsize = 40
OwnPlanetype = 0
running = True
while running:
	# Events überprüfen
	for event in pygame.event.get():
		if event.type == pygame.QUIT:
			pygame.quit()
			quit()
		elif event.type == pygame.MOUSEMOTION:
			last_mouse_movement = time.time()
		elif event.type == pygame.MOUSEBUTTONDOWN:
			mouse_pos = pygame.mouse.get_pos()
			if quit_btn_x <= mouse_pos[0] <= quit_btn_x + quit_btn_width and quit_btn_y <= mouse_pos[1] <= quit_btn_y + quit_btn_height:
				running = False
			if zoomI_btn_x <= mouse_pos[0] <= zoomI_btn_x + zoomI_btn_width and zoomI_btn_y <= mouse_pos[1] <= zoomI_btn_y + zoomI_btn_height:
				scale *= 0.9
				if scale < 0.0005:
					scale = 0.0005
			if zoomO_btn_x <= mouse_pos[0] <= zoomO_btn_x + zoomO_btn_width and zoomO_btn_y <= mouse_pos[1] <= zoomO_btn_y + zoomO_btn_height:
				scale *= 1.1
			if centerposx - touchsize <= mouse_pos[0] <= centerposx + touchsize and centerposy - touchsize <= mouse_pos[1] <= centerposy + touchsize:
				OwnPlanetype += 1
				if OwnPlanetype > 6:
					OwnPlanetype = 0
	# Maus ausblenden
	if time.time() - last_mouse_movement > mauszeit:
		pygame.mouse.set_visible(False)
	else:
		pygame.mouse.set_visible(True)

	# Hintergrund einfärben
	screen.fill(white)
	pygame.draw.line(screen, gray, [Menuekante - 4, 0], [Menuekante - 4, screen_height], 2)

	# Kompass zeichen
	if scale != scale_alt:
		calcKompass()
	drawKompass()
	scale_alt = scale

	# Variable anzeigen
	lattext = font.render(str(round(lat, 5)), True, black)
	lontext = font.render(str(round(lon, 5)), True, black)
	coursetext = font.render((str(round(course))+ " °"), True, black)
	speedtext = font.render((str(round(speed))+ " kt"), True, black)
	screen.blit(lattext, (Menuekante, quit_btn_height + 40))
	screen.blit(lontext, (Menuekante, quit_btn_height + 60))
	screen.blit(coursetext, (Menuekante, (quit_btn_height + (90))))
	screen.blit(speedtext, (Menuekante, (quit_btn_height + (110))))
	

	# GPS-Status anzeigen
	if gps_signal:
		screen.blit(font.render("GPS", True, green), (Menuekante, quit_btn_height + 10))
	else:
		screen.blit(font.render("Kein GPS", True, red), (Menuekante, quit_btn_height + 10))

	#Quit-Button Schaltfläche
	pygame.draw.rect(screen, gray, (quit_btn_x, quit_btn_y, quit_btn_width, quit_btn_height))
	quittext = Iconfont.render(chr(0x23FB), True, red)
	quittext_rect = quittext.get_rect(center=(quit_btn_x + quit_btn_width // 2, quit_btn_y + quit_btn_height // 2))
	screen.blit(quittext, quittext_rect)

	#Zoom-In-Button Schaltfläche
	pygame.draw.rect(screen, gray, (zoomI_btn_x, zoomI_btn_y, zoomI_btn_width, zoomI_btn_height))
	zoomItext = Iconfont.render(chr(0xF00E), True, white)
	zoomItext_rect = zoomItext.get_rect(center=(zoomI_btn_x + zoomI_btn_width // 2, zoomI_btn_y + zoomI_btn_height // 2))
	screen.blit(zoomItext, zoomItext_rect)

	#Zoom-Out-Button Schaltfläche
	pygame.draw.rect(screen, gray, (zoomO_btn_x, zoomO_btn_y, zoomO_btn_width, zoomO_btn_height))
	zoomOtext = Iconfont.render(chr(0xF010), True, white)
	zoomOtext_rect = zoomOtext.get_rect(center=(zoomO_btn_x + zoomO_btn_width // 2, zoomO_btn_y + zoomO_btn_height // 2))
	screen.blit(zoomOtext, zoomOtext_rect)

	# Eigene Position darstellen
	drawPlane(centerpos, green, course ,40, OwnPlanetype)

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
				overedge = False
				planelat = aircraft.get('lat')
				planelon = aircraft.get('lon')
				planedist = Abstand(lat, lon, planelat, planelon)
				planeangl = Winkel(lat, lon, planelat, planelon)
#				print("Abstand: ",planedist, "Winkel: ", planeangl)
				planepixelpos = (int(centerposx + getPixelx(planedist, planeangl)), int(centerposy - getPixely(planedist, planeangl)))
				if aircraft.get('seen_pos') > deadtime1:
					planecolor = gray
				else:
					planecolor = black
				if overedge:
					planesize = 20
				else:
					planesize = 30
					screen.blit(fontS.render(aircraft.get('hex'), True, black), tuple(map(sum, zip(planepixelpos,(-20,20)))))
				drawPlane((planepixelpos), planecolor, aircraft.get('track',0), planesize, 0)
#				screen.blit(fontS.render(str(round(planedist)), True, black), tuple(map(sum, zip(planepixelpos,(10,-30)))))

#	screen.blit(font.render(("Flugzeuge:", planedetec_raw), True, black, (19, (screen_height - 40))))
#	screen.blit(font.render(("Davon mit Loc:", planedetec_loc), True, black, (19, ))))

	rawtext = fontS.render(("Rohdaten: " + str(planedetec_raw)), True, black)
	loctext = fontS.render(("mit Pos.: " + str(planedetec_loc)), True, black)
	screen.blit(rawtext, (Menuekante, (zoomO_btn_y - 35)))
	screen.blit(loctext, (Menuekante, (zoomO_btn_y - 20)))

#	course += .5

#	print("Anzahl: ",planedetec_raw," Davon Loc: ", planedetec_loc)
#	time.sleep(1)
	pygame.display.update()
	pygame.time.Clock().tick(60)

p.terminate()
gps_thread_running = False
#gps_thread.join()
pygame.quit()
sys.exit()
