"""Warp the user-approved photographic moon-jelly asset, keeping one animal."""
import math


def motion_parameters(tick, tilt_x=0, tilt_y=0):
    t = tick / 4
    phase = (t % 4.8) / 4.8
    contraction = math.sin(math.pi * phase / .28) if phase < .28 else 0
    return (int(math.sin(t*.17)*3)+tilt_x,
            int(math.sin(t*.29)*2-contraction*2)+tilt_y,
            1024+int(contraction*64),1024-int(contraction*40),int(tick))


def warp_reference(destination, source, settings):
    dx, dy, xs, ys, tick = settings
    for y in range(240):
        sy = max(0,min(239,(((y-96)*ys)>>10)+96-dy))
        wave = 0
        if y > 145:
            triangle = (y + tick*2) % 64
            triangle = triangle if triangle < 32 else 64-triangle
            wave = ((triangle-16)*(y-145)) >> 9
        for x in range(240):
            sx = max(0,min(239,(((x-120)*xs)>>10)+120-dx+wave))
            a = (sy*240+sx)*2
            b = (y*240+x)*2
            destination[b] = source[a]
            destination[b+1] = source[a+1]


try:
    import micropython
except ImportError:
    micropython = None

warp_pixels = warp_reference
if micropython is not None:
    @micropython.viper
    def warp_pixels(destination, source, settings):
        output = ptr8(destination)
        image = ptr8(source)
        dx, dy = int(settings[0]), int(settings[1])
        xs, ys = int(settings[2]), int(settings[3])
        tick = int(settings[4])
        for y in range(240):
            sy = (((y-96)*ys)>>10)+96-dy
            if sy < 0:
                sy = 0
            if sy > 239:
                sy = 239
            wave = 0
            if y > 145:
                triangle = (y+tick*2)%64
                if triangle > 31:
                    triangle = 64-triangle
                wave = ((triangle-16)*(y-145))>>9
            for x in range(240):
                sx = (((x-120)*xs)>>10)+120-dx+wave
                if sx < 0:
                    sx = 0
                if sx > 239:
                    sx = 239
                a = (sy*240+sx)*2
                b = (y*240+x)*2
                output[b] = image[a]
                output[b+1] = image[a+1]
