#!/usr/bin/python
import fileinput
import sys
import math

drill_diameter = 0.8
tiefe_max = 1.75
a_e = 0.3 * drill_diameter

sys.stdout.write('''(Drill File)

(Anfang Praeambel; folgendes immer an den Anfang des Programmes schreiben)
G21 (use millimeters for length units)
G90 (absolute distance mode)
G17 (Auswahl XY-Arbeitsebene)
G40 (turn cutter compensation off)
G49 (Ausschalten der Werkzeuglaengenkompensation)
G54 (Werkstuecknullpunkt in G54 gespeichert)
G80 (Cancel Motion Modes)
G94 (Vorschubart ist mm/min)
(Ende Praeambel)

S10000 (Drehzahl 10000 min-1)
M3 (Spindel dreht im Uhrzeigersinn; entlang der Spindel ins Werkstueck schauend)
F1000 (Fraesvorschub in mm/min gilt fuer G1, G2, G3)
G4 P2.0 (wait for 2.0 seconds before proceeding)

G0 Z20

''')

tools = []

state = 0
holes = []

for line in fileinput.input():
	line = line.strip()
	if line[0] == '%':
		state += 1
	if state == 1:
		if line[0] == 'T':
			index = int(line[1:3])
			while len(tools) < index:
				tools.append(0)
			index -= 1
			tools[index] = float(line[4:]) * 25.4
	elif state == 2:
		if line[0] == 'T':
			current_tool_size = tools[int(line[1:3])-1]
		elif line[0] == 'X':
			y_idx = line.find('Y')
			x_pos = float(line[1:y_idx]) * 25.4 / 10000
			y_pos = float(line[y_idx+1:]) * 25.4 / 10000
			holes.append({
				'x': x_pos,
				'y': y_pos,
				'diameter': current_tool_size
			})

holes.sort(key=lambda h: h['y'])
holes.sort(key=lambda h: h['x'])

for hole in holes:
	sys.stdout.write('\n(Hole: Pos = %.2f, %.2f; Diameter = %.2f)\n' % (hole['x'], hole['y'], hole['diameter']))
	sys.stdout.write('''G0 X%.4f Y%.4f
G0 Z1
G1 Z0 F60
G83 R0.5 Q0.25 Z%.4f (%.2f ist maximale Eintauchtiefe)
G1 Z0
''' % (hole['x'], hole['y'], -tiefe_max, tiefe_max))
	# can we even start helix drilling?
	if hole['diameter'] - drill_diameter >= a_e/3:
		sys.stdout.write('G91\n')
		delta = (hole['diameter'] - drill_diameter)/2
		alpha_prime = int(math.ceil(delta/a_e))
		a_e_prime = delta/alpha_prime
		for i in range(0,alpha_prime):
			sys.stdout.write('''G1 Y%.4f
G2 Z%.4f I0 J%.4f P%d
''' % (a_e_prime, -tiefe_max, -(i+1)*a_e_prime, math.ceil(tiefe_max/drill_diameter)*2))
			if i != alpha_prime-1:
				sys.stdout.write('G1 Y%.4f\nG0 Z%.4f\nG1 Y%.4f\n' % (-a_e_prime, tiefe_max, a_e_prime))
		sys.stdout.write('G90\nG1 X%.4f Y%.4f\n' % (hole['x'], hole['y']))

	sys.stdout.write('G0 Z5\nF1000\n')

sys.stdout.write('''
G0 Z20 (Z-Wert soll Fraeser deutlich ueber das Werkstueck bringen)
G40
M30 (Spindel aus, Kuehlung aus, alles aus, Programmende)
''')
