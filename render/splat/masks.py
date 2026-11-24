import sys, glob, os, numpy as np
from PIL import Image
from concurrent.futures import ProcessPoolExecutor
def f(p):
    a=np.array(Image.open(p).convert('RGB'))[...,0].astype(np.int32)
    L=np.where(a<8,0,np.clip(np.rint(a/16.0),1,15)).astype(np.uint8)   # 0 = none, k = level k-1
    h,w=L.shape; W,H=w//2,h//2
    blk=L[:H*2,:W*2].reshape(H,2,W,2).transpose(0,2,1,3).reshape(H,W,4)
    # majority per 2x2 (keeps edges crisp, no blending)
    out=np.zeros((H,W),np.uint8); best=np.zeros((H,W),np.int32)
    for v in np.unique(blk):
        c=(blk==v).sum(2); m=c>best; out[m]=v; best[m]=c[m]
    Image.fromarray((out.astype(np.uint16)*16).clip(0,255).astype(np.uint8),'L').save(p,optimize=True)
    return os.path.getsize(p)
if __name__=='__main__':
    files=[p for d in sys.argv[1:] for p in glob.glob(d+'/*.png')]
    with ProcessPoolExecutor(8) as ex: s=sum(ex.map(f,files,chunksize=16))
    print(len(files),'files',s/1e6,'MB')
