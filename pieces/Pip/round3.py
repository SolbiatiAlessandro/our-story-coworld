from PIL import Image,ImageDraw
im=Image.new('L',(32,32),ord('.'));d=ImageDraw.Draw(im)
def el(b,c):d.ellipse(b,fill=ord(c))
def re(b,c):d.rectangle(b,fill=ord(c))
def li(p,c,w=1):d.line(p,fill=ord(c),width=w)
def po(p,c):d.polygon(p,fill=ord(c))
po([(12,12),(20,12),(29,31),(3,31)],'e');li([(12,15),(5,30)],'c');li([(20,15),(27,30)],'c')
# glass dome and alien pilot
el((8,1,23,15),'n');el((9,2,22,14),'c');el((11,3,20,11),'e');el((13,5,19,11),'l');el((13,6,15,8),'n');el((17,6,19,8),'n');li([(16,5),(16,2)],'d');d.point((16,2),fill=ord('y'))
# saucer rim
el((1,10,30,17),'n');el((2,10,29,15),'p');el((4,9,27,13),'g');li([(7,10),(23,10)],'w');li([(10,17),(21,17)],'p')
for x in [5,11,18,24]:re((x,13,x+2,14),'y')
# cow suspended in beam
li([(10,24),(7,22),(7,20)],'n');re((10,21,21,26),'n');re((10,21,19,25),'w');re((11,26,12,28),'n');re((18,26,19,28),'n');re((12,21,14,23),'k');re((16,24,18,25),'k')
li([(20,21),(19,19)],'t');li([(23,21),(24,19)],'t');re((19,21,24,24),'w');d.point((20,22),fill=ord('k'));d.point((23,22),fill=ord('k'));re((20,24,24,25),'s');d.point((21,24),fill=ord('t'));d.point((23,24),fill=ord('t'))
for x,y in [(3,3),(28,5)]:li([(x-1,y),(x+1,y)],'y');li([(x,y-1),(x,y+1)],'y')
open('pieces/Pip/round3.txt','w').write('\n'.join(''.join(chr(im.getpixel((x,y))) for x in range(32)) for y in range(32))+'\n')
