"""Warp the user-approved photographic moon-jelly asset, keeping one animal."""
import math


SOURCE_BOUNDS = (23,35,211,201)  # Non-black bounds of the approved RGB565 master.

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
    return contraction,travel,max(-8,min(8,velocity_x*drag))


def motion_parameters(tick, tilt_x=0, tilt_y=0):
    contraction, travel, wake = swim_state(tick)
    return (int((math.sin(travel*.13)*35 + math.sin(travel*.31)*8+tilt_x)*1840*256/1024),
            int((math.sin(travel*.11)*24 + math.sin(travel*.27)*7+tilt_y)*1840*256/1024),
            1840+int(contraction*96),1840-int(contraction*64),int(tick*2.5*256)%81920,int(wake*256),
            int(max(-3,min(3,(4.55*math.cos(travel*.13)+2.48*math.cos(travel*.31))*.35))*256))


def frame_bounds(settings):
    cx = 120+settings[0]/256*1024/1840
    cy = 96+settings[1]/256*1024/1840
    left,top = max(0,int(cx)-67),max(0,int(cy)-41)
    right,bottom = min(240,int(cx)+68),min(240,int(cy)+68)
    return left,top,right-left,bottom-top


def warp_reference(destination, source, settings):
    destination[:] = bytes(115200)
    output,image,curve = destination,source,ARM_WAVE
    dx,dy = int(settings[0]),int(settings[1])
    xs,ys = int(settings[2]),int(settings[3])
    tick,wake,lean = int(settings[4]),int(settings[5]),int(settings[6])
    xmin,xmax = SOURCE_BOUNDS[0]-1,SOURCE_BOUNDS[2]
    ymin,ymax = SOURCE_BOUNDS[1]-1,SOURCE_BOUNDS[3]
    for y in range(240):
        base_y = (((y-96)*1840)>>2)+24576-dy
        sy = (((y-96)*ys)>>2)+24576-dy
        if base_y > 37120:
            sy = base_y-((49*(1840-ys)*256+1839)//1840)
        iy = sy>>8
        if iy < ymin or iy >= ymax:
            continue
        fy = (sy>>3)&31
        factor = 37120-sy
        if factor < 0:
            factor = 0
        if factor > 12544:
            factor = 12544
        row_xs = 1840+(xs-1840)*factor//12544
        wave = 0
        if sy > 37120:
            phase = (sy+tick*4//5)%16384
            index = phase>>8
            frac = phase&255
            value = curve[index]*(256-frac)+curve[(index+1)%64]*frac-4096
            wave = (value*(sy-37120))>>17
            wave += (wake*(sy-37120))>>14
        wave += ((sy-30720)*lean)>>14
        left = 120+((dx-wave+(xmin-120)*256)*4)//row_xs-2
        right = 120+((dx-wave+(xmax-120)*256)*4)//row_xs+3
        if left < 0:
            left = 0
        if right > 240:
            right = 240
        for x in range(left,right):
            sx = (((x-120)*row_xs)>>2)+30720-dx+wave
            ix = sx>>8
            if ix < xmin or ix >= xmax:
                continue
            fx = (sx>>3)&31
            a = (iy*240+ix)*2
            c0 = (image[a]<<8)|image[a+1]
            c1 = (image[a+2]<<8)|image[a+3]
            c2 = (image[a+480]<<8)|image[a+481]
            c3 = (image[a+482]<<8)|image[a+483]
            combined = c0|c1|c2|c3
            if combined in (0,1,0x0800,0x1000):
                continue
            h0 = ((((c0&0xf81f)*(32-fx)+(c1&0xf81f)*fx)>>5)&0xf81f)|((((c0&0x07e0)*(32-fx)+(c1&0x07e0)*fx)>>5)&0x07e0)
            h1 = ((((c2&0xf81f)*(32-fx)+(c3&0xf81f)*fx)>>5)&0xf81f)|((((c2&0x07e0)*(32-fx)+(c3&0x07e0)*fx)>>5)&0x07e0)
            color = ((((h0&0xf81f)*(32-fy)+(h1&0xf81f)*fy)>>5)&0xf81f)|((((h0&0x07e0)*(32-fy)+(h1&0x07e0)*fy)>>5)&0x07e0)
            red,green,blue = color>>11,(color>>5)&63,color&31
            if green == 0 and red <= 2 and blue <= 1:
                color = 0
            out = (y*240+x)*2
            output[out] = color>>8
            output[out+1] = color&255

try:
    import micropython
except ImportError:
    micropython = None

warp_pixels = warp_reference
if micropython is not None:
    @micropython.viper
    def warp_pixels(destination,source,settings):
        output = ptr16(destination)
        image = ptr16(source)
        curve = ptr8(ARM_WAVE)
        clear = ptr32(destination)
        for i in range(28800):
            clear[i] = 0
        dx,dy = int(settings[0]),int(settings[1])
        xs,ys = int(settings[2]),int(settings[3])
        tick,wake,lean = int(settings[4]),int(settings[5]),int(settings[6])
        xmin = int(SOURCE_BOUNDS[0])-1
        xmax = int(SOURCE_BOUNDS[2])
        ymin = int(SOURCE_BOUNDS[1])-1
        ymax = int(SOURCE_BOUNDS[3])
        for y in range(240):
            base_y = (((y-96)*1840)>>2)+24576-dy
            sy = (((y-96)*ys)>>2)+24576-dy
            if base_y > 37120:
                sy = base_y-((49*(1840-ys)*256+1839)//1840)
            iy = sy>>8
            if iy < ymin or iy >= ymax:
                continue
            fy = (sy>>3)&31
            factor = 37120-sy
            if factor < 0:
                factor = 0
            if factor > 12544:
                factor = 12544
            row_xs = 1840+(xs-1840)*factor//12544
            wave = 0
            if sy > 37120:
                phase = (sy+tick*4//5)%16384
                index = phase>>8
                frac = phase&255
                value = curve[index]*(256-frac)+curve[(index+1)%64]*frac-4096
                wave = (value*(sy-37120))>>17
                wave += (wake*(sy-37120))>>14
            wave += ((sy-30720)*lean)>>14
            left = 120+((dx-wave+(xmin-120)*256)*4)//row_xs-2
            right = 120+((dx-wave+(xmax-120)*256)*4)//row_xs+3
            if left < 0:
                left = 0
            if right > 240:
                right = 240
            for x in range(left,right):
                sx = (((x-120)*row_xs)>>2)+30720-dx+wave
                ix = sx>>8
                if ix < xmin or ix >= xmax:
                    continue
                fx = (sx>>3)&31
                a = iy*240+ix
                c0 = image[a]
                c1 = image[a+1]
                c2 = image[a+240]
                c3 = image[a+241]
                combined = c0|c1|c2|c3
                if combined == 0 or combined == 256 or combined == 8 or combined == 16:
                    continue
                c0 = ((c0&255)<<8)|(c0>>8)
                c1 = ((c1&255)<<8)|(c1>>8)
                c2 = ((c2&255)<<8)|(c2>>8)
                c3 = ((c3&255)<<8)|(c3>>8)
                h0 = ((((c0&0xf81f)*(32-fx)+(c1&0xf81f)*fx)>>5)&0xf81f)|((((c0&0x07e0)*(32-fx)+(c1&0x07e0)*fx)>>5)&0x07e0)
                h1 = ((((c2&0xf81f)*(32-fx)+(c3&0xf81f)*fx)>>5)&0xf81f)|((((c2&0x07e0)*(32-fx)+(c3&0x07e0)*fx)>>5)&0x07e0)
                color = ((((h0&0xf81f)*(32-fy)+(h1&0xf81f)*fy)>>5)&0xf81f)|((((h0&0x07e0)*(32-fy)+(h1&0x07e0)*fy)>>5)&0x07e0)
                red = color>>11
                green = (color>>5)&63
                blue = color&31
                if green == 0 and red <= 2 and blue <= 1:
                    color = 0
                out = y*240+x
                output[out] = ((color&255)<<8)|(color>>8)
