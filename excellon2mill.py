#!/usr/bin/python
import sys
import math
import argparse
import itertools
import operator

parser = argparse.ArgumentParser(description='Convert Excellon drill files generated by Eagle to g-code for LinuxCNC for milling.')
parser.add_argument('--p1', metavar='num', type=float, nargs=2,
                   help='The position of the first drill hole')
parser.add_argument('--p2', metavar='num', type=float, nargs=2,
                   help='The position of the last drill hole')
parser.add_argument('--diameter', metavar='num', type=float, nargs=1, default=0.8,
                   help='The drill diameter (default 0.8)')
parser.add_argument('--thickness', metavar='num', type=float, nargs=1, default=[1.75],
                   help='The PCB thickness (default 1.75)')
parser.add_argument('--ae', metavar='num', type=float, nargs=1, default=30.0,
                   help='The maximum amount of material taken in one movement (in %% of the drill diameter, default 30)')
parser.add_argument('--calibrate', action='store_true',
                   help='Whether to just output the first and last drill hole index and position for calibration using --p1 and --p2')
parser.add_argument('--boardsize', metavar='num', type=float, nargs=4,
                   help='Two board edge coordinates (supply lower left and upper right in the form x1 y1 x2 y2, in the coordinate space of the PCB generator)')
parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin)
parser.add_argument('outfile', nargs='?', type=argparse.FileType('w'), default=sys.stdout)

args = parser.parse_args()

def dot(x, y):
	assert len(x) == len(y)
	return sum(itertools.starmap(operator.mul, itertools.izip(x, y)))

def matmult(m, v):
	return [dot(row, v) for row in m]

drill_diameter = args.diameter
tiefe_max = args.thickness[0]
a_e = (args.ae/100.0) * drill_diameter

tools = []
holes = []

for line in args.infile:
	line = line.strip()
	if line[0] == 'T':
		index = int(line[1:3])
		if line[3:4] == 'C':
			while len(tools) < index:
				tools.append(0)
			index -= 1
			tools[index] = float(line[4:]) * 25.4
		else:
			current_tool_size = tools[index-1]
	elif line[0] == 'X':
		y_idx = line.find('Y')
		x_pos = float(line[1:y_idx]) * 25.4 / 10000
		y_pos = float(line[y_idx+1:]) * 25.4 / 10000
		holes.append({
			'index': len(holes),
			'x': x_pos,
			'y': y_pos,
			'diameter': current_tool_size
		})

holes.sort(key=lambda h: h['y'])
holes.sort(key=lambda h: h['x'])

if args.calibrate:
	sys.stdout.write("First drill hole: index %d, position %.2f, %.2f\n" % (holes[0]['index']+1, holes[0]['x'], holes[0]['y']))
	sys.stdout.write(" Last drill hole: index %d, position %.2f, %.2f\n" % (holes[-1]['index']+1, holes[-1]['x'], holes[-1]['y']))
	exit(0)

transform = [[1.0,0.0,0.0],
             [0.0,1.0,0.0],
             [0.0,0.0,1.0]]

if args.p1 != None and args.p2 != None:
	p1 = [holes[0]['x'], holes[0]['y']]
	p2 = [holes[-1]['x'], holes[-1]['y']]
	a1 = args.p1
	a2 = args.p2
	origp1 = p1
	
	p1 = [a-b for a,b in zip(p1,origp1)]
	p2 = [a-b for a,b in zip(p2,origp1)]
	a1 = [a-b for a,b in zip(a1,origp1)]
	a2 = [a-b for a,b in zip(a2,origp1)]

	# rotation
	vlen = math.sqrt(math.pow(p2[0] - p1[0], 2) + math.pow(p2[1] - p1[1], 2))
	argslen = math.sqrt(math.pow(args.p2[0] - args.p1[0], 2) + math.pow(args.p2[1] - args.p1[1], 2))
	
	if abs(vlen - argslen) > 0.1:
		sys.stderr.write("The distance between the two points is not correct (should be %.2f, you measured %.2f)! Have you scaled the PCB?\n" % (vlen, argslen))
		sys.exit(1)
	
	cosalpha = ((p2[0] - p1[0]) / vlen) * (args.p2[0] - args.p1[0]) / argslen + \
	           ((p2[1] - p1[1]) / vlen) * (args.p2[1] - args.p1[1]) / argslen
	transform[0][0] = cosalpha
	transform[1][1] = cosalpha
	transform[1][0] = math.sqrt(1.0-cosalpha*cosalpha)
	transform[0][1] = -transform[1][0]
	
	# translation
	delta = matmult(transform, [origp1[0], origp1[1], 1])
	transform[0][2] = -delta[0] + args.p1[0]
	transform[1][2] = -delta[1] + args.p1[1]


args.outfile.write('''(Drill File)

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

for hole in holes:
	hole['orig_x'] = hole['x']
	hole['orig_y'] = hole['y']
	pos = matmult(transform, [hole['x'], hole['y'], 1])
	hole['x'] = pos[0]
	hole['y'] = pos[1]

# the arrangement might have changed due to the rotation, sort again
holes.sort(key=lambda h: h['y'])
holes.sort(key=lambda h: h['x'])

for hole in holes:
	args.outfile.write('\n(Hole %d: Pos = %.2f, %.2f; Diameter = %.2f)\n' % (hole['index']+1, hole['orig_x'], hole['orig_y'], hole['diameter']))
	
	args.outfile.write('''G0 X%.4f Y%.4f
G0 Z1
G1 Z0 F60
G83 R0.5 Q0.25 Z%.4f (%.2f ist maximale Eintauchtiefe)
G1 Z0
''' % (hole['x'], hole['y'], -tiefe_max, tiefe_max))
	# can we even start helix drilling?
	if hole['diameter'] - drill_diameter >= a_e/3:
		args.outfile.write('G91\n')
		delta = (hole['diameter'] - drill_diameter)/2
		alpha_prime = int(math.ceil(delta/a_e))
		a_e_prime = delta/alpha_prime
		for i in range(0,alpha_prime):
			args.outfile.write('''G1 Y%.4f
G2 Z%.4f I0 J%.4f P%d
''' % (a_e_prime, -tiefe_max, -(i+1)*a_e_prime, math.ceil(tiefe_max/drill_diameter)*2))
			if i != alpha_prime-1:
				args.outfile.write('G1 Y%.4f\nG0 Z%.4f\nG1 Y%.4f\n' % (-a_e_prime, tiefe_max, a_e_prime))
		args.outfile.write('G90\nG1 X%.4f Y%.4f\n' % (hole['x'], hole['y']))

	args.outfile.write('G0 Z5\nF1000\n')

if args.boardsize != None:
	args.outfile.write('\n(Milling Board Dimensions)\n')
	p1 = matmult(transform, [args.boardsize[0], args.boardsize[1], 1])
	p2 = matmult(transform, [args.boardsize[2], args.boardsize[1], 1])
	p3 = matmult(transform, [args.boardsize[2], args.boardsize[3], 1])
	p4 = matmult(transform, [args.boardsize[0], args.boardsize[3], 1])
	
	args.outfile.write('G0 X%.4f Y%.4f Z5\n' % (p1[0], p1[1]))
	args.outfile.write('G0 Z1\nF60\n')
	count = int(math.ceil(tiefe_max / a_e))
	a_e_prime = tiefe_max / count
	for i in range(0,count):
		args.outfile.write('G1 Z%.4f F60\nF1000\n' % (-i*a_e_prime,))
		args.outfile.write('G1 X%.4f Y%.4f\n' % (p2[0], p2[1]))
		args.outfile.write('G1 X%.4f Y%.4f\n' % (p3[0], p3[1],))
		args.outfile.write('G1 X%.4f Y%.4f\n' % (p4[0], p4[1],))
		args.outfile.write('G1 X%.4f Y%.4f\n' % (p1[0], p1[1],))
	args.outfile.write('G1 Z0\n') # don't move along the board with G0

args.outfile.write('''
G0 Z20 (Z-Wert soll Fraeser deutlich ueber das Werkstueck bringen)
G40
M30 (Spindel aus, Kuehlung aus, alles aus, Programmende)
''')
