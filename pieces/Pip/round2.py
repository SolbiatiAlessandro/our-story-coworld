from PIL import Image,ImageDraw
im=Image.new('L',(32,32),ord('.'));d=ImageDraw.Draw(im)
def el(b,c):d.ellipse(b,fill=ord(c))
def rect(b,c):d.rectangle(b,fill=ord(c))
def line(p,c,w=1):d.line(p,fill=ord(c),width=w)
def poly(p,c):d.polygon(p,fill=ord(c))
# moss and winding path
el((0,26,31,31),'d');el((3,26,28,29),'l');poly([(14,25),(18,25),(22,31),(10,31)],'t');line([(15,27),(18,27)],'s');line([(14,30),(19,30)],'s')
rect((8,13,24,26),'t');rect((9,14,23,25),'s');rect((10,14,12,25),'w')
el((14,18,20,28),'t');rect((14,22,20,27),'t');el((15,19,19,26),'p');rect((15,23,19,26),'p');d.point((18,23),fill=ord('y'))
for x in [10,21]:
 rect((x,17,x+2,20),'o');rect((x,17,x+1,19),'y')
# cap
poly([(2,14),(4,9),(8,5),(13,3),(20,3),(26,7),(29,13),(29,15),(2,15)],'p')
poly([(3,13),(6,8),(11,5),(19,4),(25,8),(28,13)],'r');line([(3,14),(28,14)],'m')
for b in [(10,6,14,9),(19,6,22,8),(5,11,8,12),(22,11,25,12)]:el(b,'w')
# tiny mushroom and sparkles
rect((2,25,3,28),'w');el((0,23,5,25),'m');d.point((2,23),fill=ord('w'))
for x,y in [(2,5),(27,3),(29,20)]:
 line([(x-1,y),(x+1,y)],'y');line([(x,y-1),(x,y+1)],'y')
for x,y in [(6,28),(25,27),(28,29)]:el((x,y,x+1,y+1),'c')
open('pieces/Pip/round2.txt','w').write('\n'.join(''.join(chr(im.getpixel((x,y))) for x in range(32)) for y in range(32))+'\n')
