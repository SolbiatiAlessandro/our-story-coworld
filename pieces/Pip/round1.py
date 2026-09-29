from PIL import Image, ImageDraw
im=Image.new('L',(32,32),ord('.')); d=ImageDraw.Draw(im)
def ellipse(box,c): d.ellipse(box,fill=ord(c))
def line(points,c,w=1): d.line(points,fill=ord(c),width=w)
# waving arms with dark silhouettes and orange centers
for pts in [[(11,18),(8,24),(3,24),(2,20)],[(13,20),(11,28),(6,29),(4,27)],[(16,20),(16,29),(13,31)],[(19,20),(22,28),(26,28),(28,25)],[(21,18),(26,23),(30,20),(30,17)]]:
 line(pts,'p',4);line(pts,'o',2)
ellipse((7,6,24,23),'p');ellipse((8,6,23,21),'r');ellipse((9,7,22,19),'o');ellipse((11,8,15,10),'y')
for x in (11,18):
 ellipse((x,13,x+3,17),'w');ellipse((x+1,14,x+2,16),'n')
line([(14,19),(15,20),(17,20),(18,19)],'p')
ellipse((8,18,10,19),'r');ellipse((21,18,23,19),'r')
for box in [(2,6,5,9),(25,2,29,6),(24,10,26,12)]:
 d.ellipse(box,outline=ord('c'));d.point((box[0]+1,box[1]),fill=ord('w'))
line([(0,31),(2,27),(1,25)],'d');line([(2,30),(4,28)],'l')
for x,y in [(7,31),(24,31),(29,30)]:ellipse((x,y,x+1,y),'y')
open('pieces/Pip/round1.txt','w').write('\n'.join(''.join(chr(im.getpixel((x,y))) for x in range(32)) for y in range(32))+'\n')
