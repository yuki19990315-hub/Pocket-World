package com.depthworld.wallpaper

import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RadialGradient
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.Typeface
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import kotlin.math.cos
import kotlin.math.sin

/**
 * Original cyber-glass artwork inspired by the layered look of neon home-screen themes.
 * The tiles are decorative artwork, not actual app shortcuts or a replacement launcher.
 * All coordinates are normalized to a 1080x2400 portrait canvas.
 */
class CyberCircuitRenderer {
    private val brush = Paint(Paint.ANTI_ALIAS_FLAG)
    private val displayFont = Typeface.create("sans-serif-medium", Typeface.BOLD)
    private val symbolFont = Typeface.create("sans-serif", Typeface.NORMAL)
    private var shownMinute = -1L
    private var clockText = "00:00"
    private var dateText = ""
    private var currentHour = 12
    private data class EnergyRipple(val x: Float, val y: Float, val started: Float)
    private val ripples = ArrayList<EnergyRipple>(6)

    private val neon = intArrayOf(
        Color.rgb(91, 239, 186), Color.rgb(255, 208, 67),
        Color.rgb(77, 206, 255), Color.rgb(255, 87, 172),
        Color.rgb(152, 124, 255), Color.rgb(255, 128, 76)
    )

    fun emitRipple(xRatio: Float, yRatio: Float, time: Float) {
        if (ripples.size >= 6) ripples.removeAt(0)
        ripples.add(EnergyRipple(xRatio.coerceIn(0f, 1f) * 1080f,
            yRatio.coerceIn(0f, 1f) * 2400f, time))
    }

    fun draw(canvas: Canvas, width: Float, height: Float, tx: Float, ty: Float,
             time: Float, style: Int, intensity: Float, glow: Float, tiles: Boolean,
             autoColors: Boolean = false, showBattery: Boolean = false,
             batteryPercent: Int? = null, showRipples: Boolean = true) {
        if (width <= 0 || height <= 0) return
        updateClock()
        val save = canvas.save()
        canvas.scale(width / 1080f, height / 2400f)
        val x = tx.coerceIn(-2f, 2f) * intensity
        val y = ty.coerceIn(-2f, 2f) * intensity
        val pulse = 0.83f + sin(time * 1.1f) * .17f
        val palette = if (autoColors) when (currentHour) {
            in 6..15 -> 1 // daylight: cool aurora
            in 16..19 -> 0 // sunset: orange-violet
            else -> 2 // night: emerald and cyan
        } else style
        val warm = when (palette) {
            1 -> Color.rgb(74, 188, 255)
            2 -> Color.rgb(116, 255, 183)
            else -> Color.rgb(255, 127, 63)
        }
        val cool = when (palette) {
            1 -> Color.rgb(189, 102, 255)
            2 -> Color.rgb(56, 230, 229)
            else -> Color.rgb(190, 89, 248)
        }

        drawBase(canvas, warm, cool, palette, time, glow)
        canvas.save()
        canvas.translate(x * 22f, y * 22f)
        drawCircuits(canvas, warm, cool, time, glow)
        canvas.restore()

        canvas.save()
        canvas.translate(x * 43f, y * 37f)
        drawPanel(canvas, warm, cool, time, pulse, glow)
        canvas.restore()

        canvas.save()
        canvas.translate(-x * 83f, -y * 68f)
        drawHeader(canvas, warm, cool, time, pulse, glow, showBattery, batteryPercent)
        if (tiles) drawGlassTiles(canvas, warm, cool, palette, time, pulse, glow)
        else drawOpenCircuit(canvas, warm, cool, time, glow)
        canvas.restore()

        drawDust(canvas, time, glow)
        if (showRipples) drawRipples(canvas, time, warm, cool, glow)
        canvas.restoreToCount(save)
    }

    private fun updateClock() {
        val minute = System.currentTimeMillis() / 60_000L
        if (shownMinute == minute) return
        shownMinute = minute
        val now = Date()
        currentHour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        clockText = SimpleDateFormat("HH:mm", Locale.getDefault()).format(now)
        dateText = SimpleDateFormat("EEE  dd  MMM", Locale.getDefault())
            .format(now).uppercase(Locale.getDefault())
    }

    private fun drawBase(c: Canvas, warm: Int, cool: Int, style: Int, time: Float, glow: Float) {
        val bottom = if (style == 2) Color.rgb(4, 35, 42) else Color.rgb(17, 12, 38)
        brush.shader = LinearGradient(0f, 0f, 1080f, 2400f,
            intArrayOf(Color.rgb(8, 13, 28), bottom, Color.rgb(4, 6, 22)),
            floatArrayOf(0f, .5f, 1f), Shader.TileMode.CLAMP)
        c.drawColor(Color.BLACK)
        c.drawRect(0f, 0f, 1080f, 2400f, brush)
        brush.shader = null
        halo(c, 830f + sin(time * .22f) * 42f, 490f, 790f, cool, .26f * glow)
        halo(c, 130f, 1480f, 880f, warm, .22f * glow)
        halo(c, 630f, 2150f, 680f, cool, .15f * glow)
        // Recessed diagonal rails create the glass-device outline.
        for (n in 0 until 9) {
            val xx = n * 142f - 70f
            line(c, xx, 0f, xx + 215f, 2400f, tone(warm, .05f), 4f)
        }
    }

    private fun drawCircuits(c: Canvas, warm: Int, cool: Int, time: Float, glow: Float) {
        // A multi-plane PCB: traces have faint shadows, junctions and flowing light pulses.
        for (i in 0 until 28) {
            val fromLeft = i % 2 == 0
            val yy = 210f + i * 75f
            val sx = if (fromLeft) -80f else 1160f
            val mx = if (fromLeft) 150f + i % 6 * 64f else 930f - i % 6 * 64f
            val endX = if (fromLeft) 465f + i % 3 * 90f else 615f - i % 3 * 90f
            val turnY = yy + if (i % 3 == 0) 65f else -45f
            val tint = if (i % 3 == 0) warm else cool
            val p = Path().apply {
                moveTo(sx, yy)
                lineTo(mx - if (fromLeft) 42f else -42f, yy)
                lineTo(mx, turnY)
                lineTo(endX, turnY)
            }
            brush.style = Paint.Style.STROKE
            brush.strokeWidth = if (i % 4 == 0) 6f else 3f
            brush.color = tone(tint, .23f * glow)
            c.drawPath(p, brush)
            brush.style = Paint.Style.FILL
            dot(c, endX, turnY, 6f, tint, .45f * glow)
            val phase = (time * (36f + i % 5 * 7f) + i * 41f) % 260f
            val currentX = if (fromLeft) sx + phase else sx - phase
            if (currentX in 0f..1080f) dot(c, currentX, yy, 3.4f, tint, .82f * glow)
        }
        for (i in 0 until 16) {
            val x = 102f + (i * 179 % 860)
            val y = 245f + (i * 347 % 1870)
            val rect = RectF(x, y, x + 41f, y + 22f)
            brush.color = Color.argb(105, 8, 20, 39)
            c.drawRoundRect(rect, 5f, 5f, brush)
            outline(c, rect, 4f, if (i % 2 == 0) warm else cool, .27f * glow)
        }
    }

    private fun drawPanel(c: Canvas, warm: Int, cool: Int, time: Float,
                          pulse: Float, glow: Float) {
        val back = RectF(52f, 190f, 1028f, 2227f)
        brush.color = Color.argb(160, 1, 3, 18)
        c.drawRoundRect(back, 57f, 57f, brush)
        brush.shader = LinearGradient(30f, 190f, 1020f, 2250f,
            intArrayOf(tone(warm, .20f), Color.argb(30, 5, 12, 28), tone(cool, .13f)),
            null, Shader.TileMode.CLAMP)
        c.drawRoundRect(back, 57f, 57f, brush)
        brush.shader = null
        outline(c, back, 50f, warm, .16f * glow, 23f)
        outline(c, back, 50f, warm, .74f * glow, 4f)
        outline(c, RectF(67f, 208f, 1012f, 2206f), 37f, cool, .50f * glow, 2.5f)

        // Structural rails and circuitry between the floating foreground glass cards.
        for (i in 0 until 5) {
            val xx = 170f + i * 177f
            line(c, xx, 256f, xx, 2138f,
                tone(if (i % 2 == 0) warm else cool, .11f * glow), 9f)
            for (row in 0 until 7) {
                val y = 705f + row * 208f
                line(c, xx, y, xx + 60f, y + 19f, tone(cool, .20f * glow), 3f)
            }
        }
        for (i in 0 until 17) {
            val yy = 294f + i * 108f
            line(c, 89f, yy, 991f, yy, tone(if (i % 2 == 0) warm else cool, .09f * glow), 3f)
        }
        // Optical scan line and a moving thin reflection.
        val scan = 300f + (time * 80f % 1850f)
        line(c, 75f, scan, 1005f, scan, tone(cool, .11f * glow * pulse), 15f)
    }

    private fun drawHeader(c: Canvas, warm: Int, cool: Int,
                           time: Float, pulse: Float, glow: Float,
                           showBattery: Boolean, batteryPercent: Int?) {
        val board = RectF(126f, 295f, 948f, 746f)
        glass(c, board, warm, cool, .72f * glow)
        brush.typeface = displayFont
        text(c, "DEPTHWORLD  /  SYSTEM", 173f, 366f, 30f, cool, .94f)
        text(c, clockText, 171f, 517f, 119f, Color.WHITE, .94f)
        text(c, dateText, 176f, 584f, 38f, warm, .95f)
        text(c, "PARALLAX     LIVE", 178f, 660f, 27f, Color.rgb(201, 210, 250), .70f)
        // Oscilloscope strip occupies the right half of the top status display.
        val waveform = Path()
        for (i in 0..44) {
            val xx = 560f + i * 7.7f
            val yy = 524f + sin(i * .65f + time * 2f) * (22f + sin(i * .13f) * 14f)
            if (i == 0) waveform.moveTo(xx, yy) else waveform.lineTo(xx, yy)
        }
        brush.style = Paint.Style.STROKE
        brush.strokeWidth = 12f
        brush.color = tone(cool, .16f * glow)
        c.drawPath(waveform, brush)
        brush.strokeWidth = 3f
        brush.color = tone(cool, glow * pulse)
        c.drawPath(waveform, brush)
        brush.style = Paint.Style.FILL
        for (i in 0 until 19) {
            val x = 566f + i * 17f
            val height = 28f + (sin(i * .75f + time * 1.2f) + 1f) * 21f
            line(c, x, 645f - height, x, 645f, tone(warm, (.27f + height / 120f) * glow), 6f)
        }
        if (showBattery) {
            val capacity = batteryPercent?.takeIf { it in 0..100 }
            val tint = if (capacity != null && capacity <= 20) Color.rgb(255, 106, 96) else cool
            text(c, "POWER  ${capacity?.let { "$it%" } ?: "--"}",
                564f, 697f, 27f, tint, .88f)
            val track = RectF(737f, 671f, 891f, 690f)
            brush.color = tone(tint, .18f)
            c.drawRoundRect(track, 8f, 8f, brush)
            if (capacity != null && capacity > 0) {
                brush.color = tone(tint, .90f)
                c.drawRoundRect(RectF(track.left, track.top,
                    track.left + track.width() * capacity / 100f, track.bottom), 8f, 8f, brush)
            }
        }
    }

    private fun drawRipples(c: Canvas, time: Float, warm: Int, cool: Int, glow: Float) {
        val iterator = ripples.iterator()
        while (iterator.hasNext()) {
            val ring = iterator.next()
            val age = time - ring.started
            if (age < 0f || age > 1.15f) {
                iterator.remove()
                continue
            }
            val life = (1f - age / 1.15f).coerceIn(0f, 1f)
            val color = if (ring.x < 540f) cool else warm
            val radius = 18f + age * 560f
            brush.style = Paint.Style.STROKE
            brush.strokeWidth = 19f * life + 3f
            brush.color = tone(color, .16f * life * glow)
            c.drawCircle(ring.x, ring.y, radius, brush)
            brush.strokeWidth = 3.5f
            brush.color = tone(color, .91f * life * glow)
            c.drawCircle(ring.x, ring.y, radius, brush)
            brush.color = tone(Color.WHITE, .53f * life * glow)
            c.drawCircle(ring.x, ring.y, radius * .53f, brush)
            brush.style = Paint.Style.FILL
            dot(c, ring.x, ring.y, 9f * life + 1f, color, .72f * life * glow)
        }
    }

    private fun drawGlassTiles(c: Canvas, warm: Int, cool: Int, style: Int,
                               time: Float, pulse: Float, glow: Float) {
        val icons = arrayOf("◉", "✦", "◎", "▣", "♫", "↗", "◈", "▶",
            "✉", "◇", "⌘", "☼", "♡", "◌", "∿", "✳")
        for (row in 0 until 4) for (col in 0 until 4) {
            if (row >= 2 && col <= 1) continue
            val idx = row * 4 + col
            val x = 114f + col * 225f
            val y = 829f + row * 278f
            val tile = RectF(x, y, x + 183f, y + 197f)
            val color = neon[(idx + style) % neon.size]
            val sway = sin(time * .7f + idx * .41f) * 3f
            val moved = RectF(tile.left, tile.top + sway, tile.right, tile.bottom + sway)
            // Extrusion and a moving cast shadow under each floating glass plate.
            brush.color = Color.argb(145, 0, 2, 12)
            c.drawRoundRect(RectF(moved.left + 15f, moved.top + 23f,
                moved.right + 15f, moved.bottom + 23f), 25f, 25f, brush)
            brush.color = tone(color, .19f * glow)
            c.drawRoundRect(RectF(moved.left + 7f, moved.bottom - 10f,
                moved.right + 9f, moved.bottom + 18f), 14f, 14f, brush)
            glass(c, moved, color, if (idx % 2 == 0) warm else cool, glow)
            val brightness = (pulse + sin(time * 1.6f + idx) * .08f).coerceIn(.55f, 1f)
            halo(c, moved.centerX(), moved.centerY(), 111f, color, .19f * glow * brightness)
            brush.typeface = symbolFont
            brush.textAlign = Paint.Align.CENTER
            text(c, icons[idx], moved.centerX(), moved.centerY() + 30f, 88f,
                color, glow * brightness)
            brush.textAlign = Paint.Align.LEFT
            // Fine highlight to suggest glass thickness above the screen.
            line(c, moved.left + 22f, moved.top + 16f,
                moved.right - 30f, moved.top + 16f, tone(Color.WHITE, .37f), 3.2f)
        }
        drawRadar(c, warm, cool, time, pulse, glow)
        text(c, "HOLOGRAPHIC DISPLAY   ·   3D DEPTH", 146f, 2060f,
            29f, cool, .73f * glow)
    }

    private fun drawRadar(c: Canvas, warm: Int, cool: Int,
                          time: Float, pulse: Float, glow: Float) {
        val pane = RectF(116f, 1387f, 519f, 1861f)
        glass(c, pane, cool, warm, glow)
        val cx = pane.centerX()
        val cy = pane.centerY() - 16f
        for (i in 0 until 4) {
            val radius = 72f + i * 36f
            brush.color = tone(if (i % 2 == 0) cool else warm, (.12f + .11f * pulse) * glow)
            brush.style = Paint.Style.STROKE
            brush.strokeWidth = if (i == 2) 8f else 3f
            c.drawCircle(cx, cy, radius, brush)
        }
        brush.style = Paint.Style.FILL
        halo(c, cx, cy, 171f, cool, .25f * glow)
        val theta = time * .64f
        line(c, cx, cy, cx + cos(theta) * 179f, cy + sin(theta) * 179f,
            tone(cool, .82f * glow), 5f)
        dot(c, cx, cy, 20f, warm, .98f * glow)
        text(c, "CORE  /  ONLINE", pane.left + 26f, pane.bottom - 31f,
            25f, warm, .92f * glow)
    }

    private fun drawOpenCircuit(c: Canvas, warm: Int, cool: Int, time: Float, glow: Float) {
        for (i in 0 until 6) {
            val cx = 540f
            val cy = 1275f
            val radius = 110f + i * 97f
            brush.style = Paint.Style.STROKE
            brush.strokeWidth = if (i % 2 == 0) 8f else 3f
            brush.color = tone(if (i % 2 == 0) warm else cool, (.23f - i * .024f) * glow)
            c.drawCircle(cx, cy, radius, brush)
        }
        brush.style = Paint.Style.FILL
        halo(c, 540f, 1275f, 470f, cool, .48f * glow)
        val a = time * .8f
        line(c, 540f, 1275f, 540f + cos(a) * 365f, 1275f + sin(a) * 365f,
            tone(cool, glow), 7f)
        text(c, "DEPTH  /  ENGINE", 275f, 1923f, 43f, warm, .93f * glow)
        text(c, "NEON CIRCUIT SYSTEM", 278f, 1992f, 29f, cool, .82f * glow)
    }

    private fun drawDust(c: Canvas, time: Float, glow: Float) {
        for (i in 0 until 46) {
            val xx = (i * 193 + 67) % 1080f
            val yy = ((i * 443 + 127) % 2260f + sin(time * .42f + i) * 14f)
            dot(c, xx, yy, if (i % 5 == 0) 3.9f else 1.7f,
                if (i % 2 == 0) Color.CYAN else Color.MAGENTA,
                (.15f + .14f * sin(time + i).let { it * it }) * glow)
        }
    }

    private fun glass(c: Canvas, rect: RectF, primary: Int, secondary: Int, glow: Float) {
        brush.shader = LinearGradient(rect.left, rect.top, rect.right, rect.bottom,
            intArrayOf(Color.argb(181, 7, 15, 33), tone(primary, .27f), Color.argb(190, 7, 10, 28)),
            null, Shader.TileMode.CLAMP)
        c.drawRoundRect(rect, 23f, 23f, brush)
        brush.shader = null
        outline(c, rect, 22f, primary, .16f * glow, 19f)
        outline(c, rect, 22f, primary, .74f * glow, 4f)
        outline(c, RectF(rect.left + 6f, rect.top + 6f,
            rect.right - 6f, rect.bottom - 6f), 18f, secondary, .37f * glow, 2f)
    }

    private fun outline(c: Canvas, rect: RectF, radius: Float, tint: Int,
                        alpha: Float, width: Float = 3f) {
        brush.shader = null
        brush.style = Paint.Style.STROKE
        brush.strokeWidth = width
        brush.color = tone(tint, alpha)
        c.drawRoundRect(rect, radius, radius, brush)
        brush.style = Paint.Style.FILL
    }

    private fun line(c: Canvas, x1: Float, y1: Float, x2: Float, y2: Float,
                     tint: Int, width: Float) {
        brush.shader = null
        brush.style = Paint.Style.STROKE
        brush.strokeCap = Paint.Cap.ROUND
        brush.color = tint
        brush.strokeWidth = width
        c.drawLine(x1, y1, x2, y2, brush)
        brush.style = Paint.Style.FILL
    }

    private fun dot(c: Canvas, x: Float, y: Float, radius: Float, tint: Int, alpha: Float) {
        brush.color = tone(tint, alpha)
        brush.shader = null
        brush.style = Paint.Style.FILL
        c.drawCircle(x, y, radius, brush)
    }

    private fun halo(c: Canvas, x: Float, y: Float, radius: Float, tint: Int, alpha: Float) {
        if (alpha <= 0f) return
        brush.shader = RadialGradient(x, y, radius,
            tone(tint, alpha), Color.TRANSPARENT, Shader.TileMode.CLAMP)
        brush.style = Paint.Style.FILL
        c.drawCircle(x, y, radius, brush)
        brush.shader = null
    }

    private fun text(c: Canvas, value: String, x: Float, y: Float,
                     size: Float, tint: Int, opacity: Float) {
        brush.shader = null
        brush.style = Paint.Style.FILL
        brush.color = tone(tint, opacity)
        brush.textSize = size
        c.drawText(value, x, y, brush)
    }

    private fun tone(color: Int, opacity: Float): Int = Color.argb(
        (255f * opacity).toInt().coerceIn(0, 255),
        Color.red(color), Color.green(color), Color.blue(color))
}
