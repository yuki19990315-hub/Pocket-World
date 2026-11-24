"""Warp the user-approved photographic moon-jelly asset, keeping one animal."""
import math


def swim_state(tick):
    """One clock drives bell squeeze, propulsion and delayed oral-arm drag."""
    t = tick / 4
    cycle = int(t // 5)
    phase = (t % 5) / 5
    contraction = math.sin(math.pi * phase / .28) if phase < .28 else 0
    progress = (.55*(1-math.cos(math.pi*phase/.28))/2 if phase < .28
                else .55+.45*(phase-.28)/.72)
    travel = (cycle+progress)*5
    delayed = ((t-.5)%5)/5
    drag = math.sin(math.pi*delayed/.28) if delayed < .28 else 0
    velocity_x = 4.55*math.cos(travel*.13)+2.48*math.cos(travel*.31)
    return contraction, travel, int(max(-8,min(8,velocity_x*drag)))


def motion_parameters(tick, tilt_x=0, tilt_y=0):
    contraction, travel, wake = swim_state(tick)
    return ((int(math.sin(travel*.13)*35 + math.sin(travel*.31)*8)+tilt_x)*1840//1024,
            (int(math.sin(travel*.11)*24 + math.sin(travel*.27)*7)+tilt_y)*1840//1024,
            1840+int(contraction*96),1840-int(contraction*64),int(tick*2.5),wake)


def warp_reference(destination, source, settings):
    dx, dy, xs, ys, tick, wake = settings
    for y in range(240):
        sy = (((y-96)*ys)>>10)+96-dy
        wave = 0
        if sy > 145:
            triangle = (sy + tick*4//5) % 64
            triangle = triangle if triangle < 32 else 64-triangle
            wave = ((triangle-16)*(sy-145)) >> 9
            wave += (wake*(sy-145)) >> 6
        for x in range(240):
            sx = (((x-120)*xs)>>10)+120-dx+wave
            b = (y*240+x)*2
            color = 0
            if 0 <= sx < 240 and 0 <= sy < 240:
                a = (sy*240+sx)*2
                color = source[a]*256+source[a+1]
                if (color&0x07e0)==0 and color>>11<=2 and (color&31)<=1:
                    color = 0
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
        wake = int(settings[5])
        for y in range(240):
            sy = (((y-96)*ys)>>10)+96-dy
            wave = 0
            if sy > 145:
                triangle = (sy+tick*4//5)%64
                if triangle > 31:
                    triangle = 64-triangle
                wave = ((triangle-16)*(sy-145))>>9
                wave += (wake*(sy-145))>>6
            for x in range(240):
                sx = (((x-120)*xs)>>10)+120-dx+wave
                b = (y*240+x)*2
                color = 0
                if sx >= 0 and sx < 240 and sy >= 0 and sy < 240:
                    a = (sy*240+sx)*2
                    color = (image[a]<<8)|image[a+1]
                    if (color&0x07e0)==0 and (color>>11)<=2 and (color&31)<=1:
                        color = 0
                output[b] = color>>8
                output[b+1] = color&255
