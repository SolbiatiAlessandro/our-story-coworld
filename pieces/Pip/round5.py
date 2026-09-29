from PIL import Image,ImageDraw
im=Image.new('L',(32,32),ord('.'));d=ImageDraw.Draw(im)
def el(b,c):d.ellipse(b,fill=ord(c))
def re(b,c):d.rectangle(b,fill=ord(c))
def li(p,c,w=1):d.line(p,fill=ord(c),width=w)
def po(p,c):d.polygon(p,fill=ord(c))
# glass sphere, twilight interior
el((1,0,30,28),'n');el((2,1,29,27),'c');el((3,2,28,26),'b');el((5,3,26,25),'n');el((4,18,27,26),'e');el((5,20,26,25),'w')
# snowy fir
re((21,15,22,22),'t')
for y,w in [(6,3),(10,4),(14,5)]:
 po([(21,y),(21-w,y+7),(21+w,y+7)],'d');po([(21,y),(21-w+1,y+4),(21+w-1,y+4)],'w')
# snowman and twig arms
li([(10,17),(6,14),(5,12)],'t');li([(6,14),(4,14)],'t');li([(15,17),(18,14)],'t')
el((7,14,17,24),'e');el((8,14,16,23),'w');el((8,8,16,16),'e');el((8,8,15,15),'w')
re((9,5,14,8),'k');re((9,7,14,8),'p');re((7,9,16,9),'k')
for x in [10,13]:d.point((x,11),fill=ord('k'))
po([(12,12),(16,13),(12,13)],'o');li([(10,14),(12,15),(14,14)],'n')
re((8,15,16,16),'r');re((14,16,15,20),'r');d.point((11,19),fill=ord('n'));d.point((11,22),fill=ord('n'))
# floating snow and glass glints
for x,y in [(7,6),(18,4),(25,8),(5,17),(18,11),(24,19),(17,22)]:d.point((x,y),fill=ord('w'))
li([(5,9),(4,12),(4,16)],'w');li([(7,5),(9,4)],'w')
# ornate warm base
po([(7,26),(24,26),(28,30),(3,30)],'t');re((5,27,26,29),'o');re((4,30,27,31),'n');re((11,28,20,29),'y');d.point((15,28),fill=ord('w'))
open('pieces/Pip/round5.txt','w').write('\n'.join(''.join(chr(im.getpixel((x,y))) for x in range(32)) for y in range(32))+'\n')
