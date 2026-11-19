"""Cinematic grade applied to every web frame (orbit, explode, fly-in, stills) so they all share one look.
Warm highlights, cool shadows, gentle S-curve, a soft bloom and a light vignette."""
import numpy as np
from PIL import Image, ImageFilter

def grade(im, strength=1.0):
    a = np.asarray(im.convert("RGB")).astype(np.float32) / 255.0
    h, w, _ = a.shape
    lum = (a * [0.2126, 0.7152, 0.0722]).sum(2, keepdims=True)
    # split tone
    warm = np.array([1.06, 1.00, 0.90]); cool = np.array([0.94, 0.99, 1.06])
    t = np.clip((lum - 0.25) / 0.6, 0, 1)
    a = a * (cool * (1 - t) + warm * t) ** strength
    # S-curve (contrast) around mid grey
    a = np.clip(a, 0, 1); a = a + 0.18 * strength * (a - a * a) * (2 * a - 1) * -1 * -1
    a = 0.5 + (a - 0.5) * (1 + 0.10 * strength)
    # saturation
    lum = (a * [0.2126, 0.7152, 0.0722]).sum(2, keepdims=True)
    a = lum + (a - lum) * (1 + 0.12 * strength)
    a = np.clip(a, 0, 1)
    # bloom from highlights
    hi = np.clip((a - 0.78) / 0.22, 0, 1)
    b = Image.fromarray((hi * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(max(w, h) / 90))
    a = a + np.asarray(b).astype(np.float32) / 255.0 * 0.22 * strength * np.array([1.0, 0.92, 0.80])
    # vignette
    yy, xx = np.mgrid[0:h, 0:w]; r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / 1.4142
    a = a * (1 - 0.22 * strength * np.clip(r - 0.35, 0, 1) ** 1.6)[..., None]
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))

if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        grade(Image.open(p)).save(p.rsplit(".", 1)[0] + "_graded.jpg", quality=90)
