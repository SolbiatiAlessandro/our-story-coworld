from PIL import Image,ImageDraw
im=Image.new('L',(32,32),ord('.'));d=ImageDraw.Draw(im)
def el(b,c):d.ellipse(b,fill=ord(c))
def re(b,c):d.rectangle(b,fill=ord(c))
def li(p,c,w=1):d.line(p,fill=ord(c),width=w)
def po(p,c):d.polygon(p,fill=ord(c))
re((0,0,31,31),'n')
el((23,2,29,8),'y');el((25,1,30,6),'n')
for x,y in [(3,4),(10,2),(29,13),(2,13),(20,5)]:d.point((x,y),fill=ord('w'))
li([(6,8),(6,12)],'y');li([(4,10),(8,10)],'y')
# flag
li([(16,5),(16,12)],'y');po([(17,5),(23,7),(17,8)],'m')
# roof in sharply alternating stripes
po([(2,20),(16,10),(29,20)],'p')
po([(16,10),(4,19),(10,19)],'m');po([(16,10),(13,19),(18,19)],'r');po([(16,10),(22,19),(28,19)],'m')
# tent walls
re((4,20,27,29),'r')
for x in [5,11,17,23]:re((x,20,x+2,29),'s')
# open sweeping curtains
po([(16,20),(12,29),(20,29)],'k');li([(15,22),(12,29)],'p');li([(17,22),(20,29)],'p')
d.point((15,26),fill=ord('y'));d.point((17,26),fill=ord('y'))
li([(2,20),(29,20)],'y');li([(2,30),(29,30)],'p')
for x in range(3,30,4):el((x,19,x+1,20),'w')
li([(4,22),(1,29)],'g');li([(27,22),(30,29)],'g');re((0,29,2,30),'y');re((29,29,31,30),'y')
open('pieces/Pip/round4.txt','w').write('\n'.join(''.join(chr(im.getpixel((x,y))) for x in range(32)) for y in range(32))+'\n')
