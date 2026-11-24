"""Warp the user-approved photographic moon-jelly asset, keeping one animal."""
import math


def motion_parameters(tick, tilt_x=0, tilt_y=0):
    t = tick / 4
    phase = (t % 4.8) / 4.8
    contraction = math.sin(math.pi * phase / .28) if phase < .28 else 0
    return ((int(math.sin(t*.13)*35 + math.sin(t*.31)*8)+tilt_x)*1840//1024,
            (int(math.sin(t*.11)*24 + math.sin(t*.27)*7-contraction*2)+tilt_y)*1840//1024,
            1840+int(contraction*96),1840-int(contraction*64),int(tick))


def warp_reference(destination, source, settings):
    dx, dy, xs, ys, tick = settings
    for y in range(240):
        sy = (((y-96)*ys)>>10)+96-dy
        wave = 0
        if sy > 145:
            triangle = (sy + tick*2) % 64
            triangle = triangle if triangle < 32 else 64-triangle
            wave = ((triangle-16)*(sy-145)) >> 9
        for x in range(240):
            sx = (((x-120)*xs)>>10)+120-dx+wave
            b = (y*240+x)*2
            color = 0x0045
            if 0 <= sx < 240 and 0 <= sy < 240:
                a = (sy*240+sx)*2
                color = source[a]*256+source[a+1]
                weight = min(16,sx,239-sx,sy,239-sy)
                weight = min(weight,max(0,(color>>11)*2+((color>>5)&63)-8))
                if weight < 16:
                    red = ((color>>11)*weight)//16
                    green = (((color>>5)&63)*weight+2*(16-weight))//16
                    blue = ((color&31)*weight+5*(16-weight))//16
                    color = red<<11 | green<<5 | blue
            destination[b] = color>>8
            destination[b+1] = color&255


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
            wave = 0
            if sy > 145:
                triangle = (sy+tick*2)%64
                if triangle > 31:
                    triangle = 64-triangle
                wave = ((triangle-16)*(sy-145))>>9
            for x in range(240):
                sx = (((x-120)*xs)>>10)+120-dx+wave
                b = (y*240+x)*2
                color = 0x0045
                if sx >= 0 and sx < 240 and sy >= 0 and sy < 240:
                    a = (sy*240+sx)*2
                    color = (image[a]<<8)|image[a+1]
                    weight = 16
                    if sx < weight:
                        weight = sx
                    if 239-sx < weight:
                        weight = 239-sx
                    if sy < weight:
                        weight = sy
                    if 239-sy < weight:
                        weight = 239-sy
                    matte = (color>>11)*2+((color>>5)&63)-8
                    if matte < 0:
                        matte = 0
                    if matte < weight:
                        weight = matte
                    if weight < 16:
                        red = ((color>>11)*weight)//16
                        green = (((color>>5)&63)*weight+2*(16-weight))//16
                        blue = ((color&31)*weight+5*(16-weight))//16
                        color = (red<<11)|(green<<5)|blue
                output[b] = color>>8
                output[b+1] = color&255
