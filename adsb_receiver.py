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

# FÜR PR0GRAMMIEREN IMMER FALSE
Vollbild = True

# Variablen
gps_thread_running = True	# Läuft der GPS-Thread
gps_signal = False		# GPS-Signalempfang
planedetec_raw = 0		# Anzahl an detektierter Flugzeuge
planedetec_loc = 0		# Anzahl an detek. Flug. mit Koordinaten
lat = 48.8			# Eigene Position Breitengrad
lon = 9.2			# Eigene Position Längengrad
sats = 0			# Anzahl GPS-Satelliten in Verwendung
alt = 100			# GPS-Antennenhöhe über NN in m
speed = 0			# GPS-Geschwindigkeit in kt
course = 0			# Eigener Kurs / Winkel zum Nordpol
maprotation = 0			# Verdrehung der Karte
deadtime1 = 10			# Zeit seit dem letzten Signal, ab wann markiert wird
deadtime2 = 30			# ... , ab wann nicht mehr anzeigen (Dump1090 intern ab 300s)
scale = 0.1			# Maßstab (km pro Pixel)
scale_alt = 100.0		# Zur Detektion, ob Kompass neu berechnet werden muss

Radio = True			# Ob Funkrufname angezeigt werden soll, sonst ICAO-Code
Info = True			# Ob Weitere Informationen (Höhe, Course, Speed) angezeigt werden
Hide = False			# Ob ab großer Höhendifferenz nur vermindert dargestellt wird
deltaH = 2000			# Höhendifferenzschwelle in ft für Hide

# Bildschirmmaße definieren
screen_width = 800
if Vollbild:
	screen_height = 480
else:
	screen_height = 420
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
darkgray = (40, 40, 40)
black = (0, 0, 0)
red = (255, 0, 0)
green = (0, 128, 0) 

# Maus ausblenden
mauszeit = 10
last_mouse_movement = time.time()
pygame.mouse.set_visible(True)

# Fenster erstellen und Fenstertitel vergeben
if Vollbild:
	screen = pygame.display.set_mode(screen , pygame.FULLSCREEN)
else:
	screen = pygame.display.set_mode(screen , pygame.RESIZABLE)
pygame.display.set_caption('ADS-B Empfänger Version 1')

# Schriftarten definieren
font = pygame.font.Font(None, 27)
fontS = pygame.font.Font(None, 20)
Iconfont = pygame.font.Font('/home/adsbpi/ADS-B_Empfaenger/fa-solid-900.ttf', 40)

# Zoom-Button Eigenschaften
zoomI_btn_width = Menuebreite
zoomO_btn_width = zoomI_btn_width
zoomI_btn_height = 70
zoomO_btn_height = zoomI_btn_height
zoomI_btn_x = screen_width - zoomI_btn_width
zoomO_btn_x = screen_width - zoomO_btn_width
zoomI_btn_y = screen_height - zoomI_btn_height
zoomO_btn_y = screen_height - zoomO_btn_height - zoomI_btn_height - 5

# Info-Button Eigenschaften
info_btn_width = Menuebreite
info_btn_height = zoomI_btn_height
info_btn_x = screen_width - info_btn_width
info_btn_y = zoomO_btn_y - info_btn_height - 5

# Hide-Button Eigenschaften
hide_btn_width = Menuebreite
hide_btn_height = zoomI_btn_height
hide_btn_x = screen_width - hide_btn_width
hide_btn_y = info_btn_y - hide_btn_height - 5


###--FUNKTIONEN--------------------

# GPS initialisieren und Starten des Threads
gps = Serial('/dev/ttyS0', 9600)

def read_gps_data():
	global lat
	global lon
	global alt
	global gps_signal
	global gps_thread_running
	global sats
	global speed
	global course
	while gps_thread_running:	
		line = gps.readline().decode('utf-8')
		if line.startswith('$GPGGA'):
			data = line.split(',')
			if data[2]:
				gps_signal = True
				lat = float(data[2][:2]) + float(data[2][2:]) / 60
				lon = float(data[4][:3]) + float(data[4][3:]) / 60
			else:
				gps_signal = False
			if data[7]:
				sats = int(data[7])
			else:
				sats = 99
			if data[9]:
				alt = int(float(data[9]))
		if line.startswith('$GPVTG'):
			data = line.split(',')
			if data[5]:
				speed = float(data[5])
			if data[1]:
				course = float(data[1])
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
	global overedge
	angl = planeangl - maprotation
	dist = planedist / scale
	x = int(round(math.sin(math.radians(angl)) * dist))
	if x > ((screen_width - Menuebreite) / 2 - Randbreite - 10):
		overedge = True
		x = ((screen_width - Menuebreite) / 2 - Randbreite - 10)
	if x < ((screen_width - Menuebreite) / -2 + Randbreite):
		overedge = True
		x = ((screen_width - Menuebreite) / -2 + Randbreite)
	return x

def getPixely(planedist, planeangl):
	global overedge
	angl = planeangl - maprotation
	dist = planedist / scale
	y = int(round(math.cos(math.radians(angl)) * dist))
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
	Planetext = pygame.transform.rotate(Planetext, -dir + maprotation)
	Planetext_rect = Planetext.get_rect()
	Planetext_rect.center = coords
	screen.blit(Planetext, Planetext_rect)
	return

# Kompass berechnen
def calcKompass():
	maxRad = centerposy - 10
	Teiler = [200, 150,  100, 75, 50, 40, 30, 20, 10, 7.5, 5, 3, 2, 1, 0.5, 0.2, 0.1]
	global Radiuskm
	global Radiuspx
	maxGef = False
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

# Infos an Symbol anzeigen
def drawInfo(planepos,info1,info2,info3,info4):
	screen.blit(fontS.render(str(info1), True, black), tuple(map(sum, zip(planepos,(-20,20)))))
	if info2:
		screen.blit(fontS.render(str(info2), True, black), tuple(map(sum, zip(planepos,(-20,33)))))
		screen.blit(fontS.render(str(info3), True, black), tuple(map(sum, zip(planepos,(-20,46)))))
		screen.blit(fontS.render(str(info4), True, black), tuple(map(sum, zip(planepos,(-20,59)))))
	return

pygame.display.update()
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
		elif event.type == pygame.KEYDOWN:
			if event.key == pygame.K_ESCAPE:
				running = False
		elif event.type == pygame.MOUSEBUTTONDOWN:
			mouse_pos = pygame.mouse.get_pos()
			if zoomI_btn_x <= mouse_pos[0] <= zoomI_btn_x + zoomI_btn_width and zoomI_btn_y <= mouse_pos[1] <= zoomI_btn_y + zoomI_btn_height:
				scale *= 0.9
				if scale < 0.0005:
					scale = 0.0005
			if zoomO_btn_x <= mouse_pos[0] <= zoomO_btn_x + zoomO_btn_width and zoomO_btn_y <= mouse_pos[1] <= zoomO_btn_y + zoomO_btn_height:
				scale *= 1.1
				if scale > 2:
					scale = 2
			if info_btn_x <= mouse_pos[0] <= info_btn_x + info_btn_width and info_btn_y <= mouse_pos[1] <= info_btn_y + info_btn_height:
				if Info:
					Info = False
				else:
					Info = True
			if hide_btn_x <= mouse_pos[0] <= hide_btn_x + hide_btn_width and hide_btn_y <= mouse_pos[1] <= hide_btn_y + hide_btn_height:
				if Hide:
					Hide = False
				else:
					Hide = True
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
	coursetext = font.render((str(int(course))+ " °"), True, black)
	speedtext = font.render((str(int(speed))+ " kt"), True, black)
	alttext = font.render((str(alt)+ " m"), True, black)
	screen.blit(lattext, (Menuekante, 30))
	screen.blit(lontext, (Menuekante, 50))
	screen.blit(coursetext, (Menuekante, 80))
	screen.blit(speedtext, (Menuekante, 100))
	screen.blit(alttext, (Menuekante, 120))

	# GPS-Status anzeigen
	if gps_signal:
		screen.blit(font.render("GPS", True, green), (Menuekante, 6))
	else:
		screen.blit(font.render("Kein GPS", True, red), (Menuekante, 6))

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

	#Info-Button Schaltfläche
	if Info:
		infocolor = darkgray
	else:
		infocolor = gray
	pygame.draw.rect(screen, infocolor, (info_btn_x, info_btn_y, info_btn_width, info_btn_height))
	infotext = Iconfont.render(chr(0xF05A), True, white)
	infotext_rect = infotext.get_rect(center=(info_btn_x + info_btn_width // 2, info_btn_y + info_btn_height // 2))
	screen.blit(infotext, infotext_rect)

	#Hide-Button Schaltfläche
	if Hide:
		hidecolor = darkgray
		hidechr = chr(0xF070)
	else:
		hidecolor = gray
		hidechr = chr(0xF06E)
	pygame.draw.rect(screen, hidecolor, (hide_btn_x, hide_btn_y, hide_btn_width, hide_btn_height))
	hidetext = Iconfont.render(hidechr, True, white)
	hidetext_rect = hidetext.get_rect(center=(hide_btn_x + hide_btn_width // 2, hide_btn_y + hide_btn_height // 2))
	screen.blit(hidetext, hidetext_rect)

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
				isGround = False
				planelat = aircraft.get('lat')
				planelon = aircraft.get('lon')
				planealt = aircraft.get('altitude')
				if isinstance(planealt,(int)) == False:
					if planealt == "ground":
						isGround = True
					planealt = 0
				planedist = Abstand(lat, lon, planelat, planelon)
				planeangl = Winkel(lat, lon, planelat, planelon)
				planepixelpos = (int(centerposx + getPixelx(planedist, planeangl)), int(centerposy - getPixely(planedist, planeangl)))
				if aircraft.get('seen_pos') > deadtime1:
					planecolor = gray
				else:
					planecolor = black
				if overedge or (Hide and planealt > (alt*3.28 + deltaH )):
					planesize = 20
				else:
					planesize = 30
					info2 = ""
					info3 = ""
					info4 = ""
					if 'flight' in aircraft and Radio:
						info1 = aircraft.get('flight')
					else:
						info1 = aircraft.get('hex')
					if Info:
						if isGround:
							info2 = "GROUND"
						else:
							info2 = str(planealt) + " ft"
						info3 = str(aircraft.get('track')) + " °"
						info4 = str(aircraft.get('speed')) + " kt"
					drawInfo(planepixelpos, info1, info2, info3, info4)
				drawPlane((planepixelpos), planecolor, aircraft.get('track',0), planesize, 0)

	# Debug-Anzeige in Menueleiste
	debugtext = fontS.render(("R" + str(planedetec_raw) + " / L" + str(planedetec_loc) + " / S" + str(sats)), True, black)
	screen.blit(debugtext, (Menuekante, hide_btn_y-15))

	pygame.display.update()
	pygame.time.Clock().tick(60)

# Abbruchroutine
p.terminate()
gps_thread_running = False
gps_thread.join()
pygame.quit()
sys.exit()
