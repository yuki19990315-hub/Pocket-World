package com.depthworld.wallpaper

import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RadialGradient
import android.graphics.Shader
import kotlin.math.cos
import kotlin.math.sin

/** Procedural, selectable light styles; no pre-rendered glow image necessary. */
object LightEffects {
    fun behind(canvas: Canvas, w: Float, h: Float, tx: Float, ty: Float,
               preset: Int, amount: Float, time: Float) {
        if (preset == 0 || amount <= 0f) return
        val p = Paint(Paint.ANTI_ALIAS_FLAG)
        val x = tx * w * .12f
        val y = ty * h * .12f
        val breath = .83f + .17f * sin(time * 1.5707963f)
        when (preset) {
            1 -> {
                halo(canvas, w * .70f + x, h * .38f + y, w * .72f, Color.rgb(255, 244, 212), amount * breath)
                halo(canvas, w * .29f - x * .3f, h * .72f, w * .40f, Color.rgb(166, 205, 255), amount * .32f)
            }
            2 -> {
                halo(canvas, w * .55f + x, h * .45f + y, w * .56f, Color.rgb(155, 196, 255), amount * .6f)
            }
            3 -> {
                halo(canvas, w * .16f + x, h * .05f + y, w * 1.10f, Color.rgb(255, 245, 189), amount * .9f)
                for (i in 0 until 5) {
                    val baseX = w * (-.3f + i * .26f) + x
                    val ray = Path().apply {
                        moveTo(w * .04f + x, h * -.03f + y)
                        lineTo(w * .19f + x, h * -.03f + y)
                        lineTo(baseX + w * .54f, h)
                        lineTo(baseX, h)
                        close()
                    }
                    p.color = Color.argb((amount * (10 + i * 3)).toInt().coerceIn(0, 65), 255, 247, 205)
                    canvas.drawPath(ray, p)
                }
            }
            4 -> {
                halo(canvas, w * .15f + x, h * .42f + y, w * .59f, Color.rgb(25, 240, 246), amount)
                halo(canvas, w * .90f - x, h * .56f - y, w * .66f, Color.rgb(235, 39, 233), amount)
            }
            5 -> {
                halo(canvas, w * .80f + x, h * .26f + y, w * .83f, Color.rgb(255, 145, 66), amount)
                halo(canvas, w * .44f + x * .4f, h * .64f, w * .58f, Color.rgb(255, 79, 113), amount * .5f)
            }
            6 -> {
                halo(canvas, w * .52f + x, h * .72f + y, w * .76f, Color.rgb(77, 222, 255), amount * .75f)
            }
            7 -> {
                halo(canvas, w * .4f + x, h * .3f + y, w * .85f, Color.rgb(65, 245, 194), amount * .72f)
                halo(canvas, w * .7f - x, h * .2f + y, w * .75f, Color.rgb(146, 108, 252), amount * .65f)
            }
            8 -> halo(canvas, w * .50f + x, h * .63f + y, w * .58f, Color.rgb(130, 245, 122), amount * .5f)
            9 -> halo(canvas, w * .55f + x, h * .40f + y, w * .75f, Color.rgb(170, 222, 255), amount * .4f)
            10 -> {
                halo(canvas, w * .78f + x, h * .22f + y, w * .7f, Color.rgb(255, 231, 160), amount * .90f)
                halo(canvas, w * .4f + x, h * .6f, w * .32f, Color.rgb(255, 161, 128), amount * .3f)
            }
            11 -> halo(canvas, w * .52f + x, h * .53f + y, w * .72f, Color.rgb(66, 225, 255), amount * .55f)
            12 -> halo(canvas, w * .48f + x, h * .42f + y, w * .7f, Color.rgb(215, 215, 255), amount * .45f)
            13 -> halo(canvas, w * .5f + x, h * .7f + y, w * .70f, Color.rgb(255, 135, 55), amount * .65f)
        }
    }

    fun inFront(canvas: Canvas, w: Float, h: Float, tx: Float, ty: Float,
                preset: Int, amount: Float, time: Float) {
        if (amount <= 0f || preset == 0) return
        val p = Paint(Paint.ANTI_ALIAS_FLAG)
        val shift = tx * w * .08f
        when (preset) {
            2, 4, 5 -> {
                for (i in 0 until (if (preset == 2) 33 else 14)) {
                    val x = ((i * 137 + 39) % 311) / 311f * w + shift
                    val y = ((i * 97 + 15) % 277) / 277f * h + ty * h * .05f
                    val twinkle = .45f + .55f * sin(time * (1f + i % 3 * .22f) + i * .75f)
                    val alpha = (amount * twinkle * 155f).toInt().coerceIn(0, 255)
                    p.color = when (preset) {
                        4 -> Color.argb(alpha, 148, 245, 255)
                        5 -> Color.argb(alpha, 255, 210, 146)
                        else -> Color.argb(alpha, 237, 242, 255)
                    }
                    val r = w * (if (i % 5 == 0) .006f else .002f)
                    canvas.drawCircle(x, y, r, p)
                    if (i % 5 == 0) {
                        p.strokeWidth = w * .0015f
                        canvas.drawLine(x - r * 2f, y, x + r * 2f, y, p)
                        canvas.drawLine(x, y - r * 2f, x, y + r * 2f, p)
                    }
                }
            }
            7, 8, 9, 10, 11, 12, 13 -> {
                for (i in 0 until (if (preset == 11) 24 else 36)) {
                    val x = ((i * 91 + 29) % 307) / 307f * w + shift
                    val seedY = ((i * 137 + 19) % 293) / 293f
                    val phase = time * (.18f + (i % 4) * .05f)
                    val y = (((seedY + (if (preset == 9) phase * .11f else -phase * .09f)) % 1f + 1f) % 1f) * h
                    val pulse = .5f + .5f * sin(time * 1.3f + i.toFloat())
                    val alpha = (amount * pulse * 185f).toInt().coerceIn(0,255)
                    val rgb = when(preset) {
                        7 -> Color.rgb(115, 255, 190)
                        8 -> Color.rgb(175, 255, 135)
                        9 -> Color.rgb(218, 245, 255)
                        10 -> Color.rgb(255, 234, 178)
                        11 -> Color.rgb(97, 233, 255)
                        12 -> Color.rgb(231, 221, 255)
                        else -> Color.rgb(255, 157, 64)
                    }
                    p.color = Color.argb(alpha, Color.red(rgb), Color.green(rgb), Color.blue(rgb))
                    if(preset == 11) {
                        p.strokeWidth = w * .0015f
                        canvas.drawLine(0f,y,w,y+h*.006f,p)
                    } else {
                        val radius = w * (if(preset == 12) .006f else .003f)
                        canvas.drawCircle(x,y,radius,p)
                    }
                }
            }
            6 -> {
                p.strokeWidth = w * .004f
                for (i in 0 until 19) {
                    val x = ((i * 101 + 71) % 299) / 299f * w
                    val y = h * (.63f + ((i * 19) % 29) / 100f) +
                        sin(time * 1.7f + i * .9f) * h * .013f
                    val sparkle = .5f + .5f * cos(time * 1.9f + i)
                    p.color = Color.argb((150f * amount * sparkle).toInt().coerceIn(0, 255), 184, 250, 255)
                    canvas.drawLine(x - w * .015f, y, x + w * .015f, y, p)
                }
            }
        }
    }

    private fun halo(canvas: Canvas, x: Float, y: Float, radius: Float, color: Int, strength: Float) {
        val p = Paint(Paint.ANTI_ALIAS_FLAG)
        val alpha = (strength * 115f).toInt().coerceIn(0, 180)
        p.shader = RadialGradient(x, y, radius,
            intArrayOf(Color.argb(alpha, Color.red(color), Color.green(color), Color.blue(color)), Color.TRANSPARENT),
            floatArrayOf(0f, 1f), Shader.TileMode.CLAMP)
        canvas.drawCircle(x, y, radius, p)
    }
}
