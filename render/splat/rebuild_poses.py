import numpy as np, json, math, sys
CX,CY=-158.0,-5.5; W,H=1920,1080
cams=[]
def ring(tag,r,h,tz,n,lens,a0=-180.0,a1=180.0,full=True):
    m=n if full else n-1
    for k in range(n):
        az=math.radians(a0+(a1-a0)*k/m)
        cams.append((f"{tag}{k:03d}",np.array([CX+math.sin(az)*r,CY-math.cos(az)*r,h]),np.array([CX,CY,tz]),lens))
ring("A",95.0,6.0,25.0,72,24); ring("B",130.0,35.0,35.0,72,28); ring("C",120.0,90.0,40.0,60,28)
ring("D",90.0,150.0,30.0,48,28); ring("E",40.0,230.0,20.0,24,30)
ring("F",45.0,3.0,8.0,29,22,-70.0,70.0,False); ring("G",70.0,15.0,18.0,33,24,-80.0,80.0,False)
ring("H",35.0,100.0,79.0,36,24)
ring("I",55.0,12.0,18.0,72,24); ring("J",60.0,40.0,42.0,72,24); ring("K",60.0,70.0,66.0,60,24)
ring("L",65.0,105.0,82.0,48,24); ring("M",32.0,4.0,7.0,41,20,-75.0,75.0,False); ring("N",85.0,55.0,45.0,48,35)
ring("O",42.0,20.0,22.0,96,24); ring("P",42.0,55.0,55.0,72,24); ring("Q",26.0,100.0,86.0,36,20)
ring("R",30.0,36.0,25.0,60,20); ring("S",70.0,2.5,4.0,72,22); ring("T",50.0,26.0,0.0,48,22)
OFF=np.array([CX,CY,0.0])
def c2w(P,T):
    f=T-P; f/=np.linalg.norm(f); x=np.cross(f,[0,0,1.0]); x/=np.linalg.norm(x); y=np.cross(x,f); z=-f
    M=np.eye(4); M[:3,0]=x; M[:3,1]=y; M[:3,2]=z; M[:3,3]=P-OFF; return M
def rot2q(R):
    t=np.trace(R)
    if t>0: s=math.sqrt(t+1)*2; return np.array([0.25*s,(R[2,1]-R[1,2])/s,(R[0,2]-R[2,0])/s,(R[1,0]-R[0,1])/s])
    i=np.argmax(np.diag(R))
    if i==0: s=math.sqrt(1+R[0,0]-R[1,1]-R[2,2])*2; return np.array([(R[2,1]-R[1,2])/s,0.25*s,(R[0,1]+R[1,0])/s,(R[0,2]+R[2,0])/s])
    if i==1: s=math.sqrt(1+R[1,1]-R[0,0]-R[2,2])*2; return np.array([(R[0,2]-R[2,0])/s,(R[0,1]+R[1,0])/s,0.25*s,(R[1,2]+R[2,1])/s])
    s=math.sqrt(1+R[2,2]-R[0,0]-R[1,1])*2; return np.array([(R[1,0]-R[0,1])/s,(R[0,2]+R[2,0])/s,(R[1,2]+R[2,1])/s,0.25*s])
flip=np.diag([1,-1,-1,1.0])
tj={"camera_model":"OPENCV","w":W,"h":H,"cx":W/2,"cy":H/2,"ply_file_path":"sparse_pc.ply","frames":[]}
ctx,itx=[],[]
for k,(nm,P,T,lens) in enumerate(cams):
    M=c2w(P,T); f=W*lens/36.0
    tj["frames"].append({"file_path":f"images/{nm}.png","fl_x":f,"fl_y":f,"transform_matrix":M.tolist()})
    ctx.append(f"{k+1} PINHOLE {W} {H} {f:.6f} {f:.6f} {W/2:.3f} {H/2:.3f}")
    w2c=np.linalg.inv(M@flip); q=rot2q(w2c[:3,:3]); t=w2c[:3,3]
    itx.append(f"{k+1} {q[0]:.9f} {q[1]:.9f} {q[2]:.9f} {q[3]:.9f} {t[0]:.6f} {t[1]:.6f} {t[2]:.6f} {k+1} {nm}.png\n\n")
import os; os.makedirs("out/sparse/0",exist_ok=True)
json.dump(tj,open("out/transforms.json","w"),indent=1)
open("out/sparse/0/cameras.txt","w").write("# Camera list\n"+"\n".join(ctx)+"\n")
open("out/sparse/0/images.txt","w").write("# Image list\n"+"".join(itx))
print(len(cams))
