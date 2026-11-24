"""Warp the user-approved photographic moon-jelly asset, keeping one animal."""
import math


ARM_WAVE = bytes(round(16*math.sin(i*math.pi/32))+16 for i in range(64))


def swim_state(tick):
    """Quick squeeze, passive reopening and decaying momentum on one clock."""
    t = tick/4
    cycle = int(t//5)
    u = t%5
    if u < .65:
        contraction = .5-.5*math.cos(math.pi*u/.65)
    else:
        contraction = math.exp(-(u-.65)/.8)*(.5+.5*math.cos(math.pi*(u-.65)/4.35))
    impulse = 1-(1+u/.6)*math.exp(-u/.6)
    normalization = 1-(1+5/.6)*math.exp(-5/.6)
    progress = .3*u/5+.7*impulse/normalization
    travel = (cycle+progress)*5
    lag = (t-.4)%5
    drag = math.exp(-lag/1.05)*math.sin(lag*3.8)
    velocity_x = 4.55*math.cos(travel*.13)+2.48*math.cos(travel*.31)
    return contraction,travel,int(max(-8,min(8,velocity_x*drag)))


def motion_parameters(tick, tilt_x=0, tilt_y=0):
    contraction, travel, wake = swim_state(tick)
    return ((int(math.sin(travel*.13)*35 + math.sin(travel*.31)*8)+tilt_x)*1840//1024,
            (int(math.sin(travel*.11)*24 + math.sin(travel*.27)*7)+tilt_y)*1840//1024,
            1840+int(contraction*96),1840-int(contraction*64),int(tick*2.5),wake,
            int(max(-3,min(3,(4.55*math.cos(travel*.13)+2.48*math.cos(travel*.31))*.35))))


def warp_reference(destination, source, settings):
    dx, dy, xs, ys, tick, wake, lean = settings
    for y in range(240):
        base_y = (((y-96)*1840)>>10)+96-dy
        sy = (((y-96)*ys)>>10)+96-dy if base_y <= 145 else base_y+-((49*(1840-ys)+1839)//1840)
        row_xs = 1840+(xs-1840)*max(0,min(49,145-sy))//49
        wave = 0
        if sy > 145:
            wave = ((ARM_WAVE[(sy+tick*4//5)%64]-16)*(sy-145))>>9
            wave += (wake*(sy-145)) >> 6
        wave += ((sy-120)*lean)>>6
        for x in range(240):
            sx = (((x-120)*row_xs)>>10)+120-dx+wave
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
        lean = int(settings[6])
        curve = ptr8(ARM_WAVE)
        for y in range(240):
            base_y = (((y-96)*1840)>>10)+96-dy
            sy = (((y-96)*ys)>>10)+96-dy
            if base_y > 145:
                sy = base_y+-((49*(1840-ys)+1839)//1840)
            factor = 145-sy
            if factor < 0:
                factor = 0
            if factor > 49:
                factor = 49
            row_xs = 1840+(xs-1840)*factor//49
            wave = 0
            if sy > 145:
                wave = ((curve[(sy+tick*4//5)%64]-16)*(sy-145))>>9
                wave += (wake*(sy-145))>>6
            wave += ((sy-120)*lean)>>6
            for x in range(240):
                sx = (((x-120)*row_xs)>>10)+120-dx+wave
                b = (y*240+x)*2
                color = 0
                if sx >= 0 and sx < 240 and sy >= 0 and sy < 240:
                    a = (sy*240+sx)*2
                    color = (image[a]<<8)|image[a+1]
                    if (color&0x07e0)==0 and (color>>11)<=2 and (color&31)<=1:
                        color = 0
                output[b] = color>>8
                output[b+1] = color&255
