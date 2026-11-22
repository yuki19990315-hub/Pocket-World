package com.depthworld.wallpaper

import android.content.Context
import android.graphics.Canvas
import android.os.BatteryManager
import android.view.MotionEvent
import android.view.View
import android.os.SystemClock

/** Live settings preview: drag to see the layers separate before setting wallpaper. */
class CyberPreviewView(context: Context) : View(context) {
    private val renderer = CyberCircuitRenderer()
    private val prefs = WallpaperConfig.preferences(context)
    private val battery = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
    private var dragX = 0f
    private var dragY = 0f
    private var batteryCheckedAt = -60_000L
    private var batteryPercent: Int? = null

    init {
        contentDescription = "サイバー壁紙のプレビュー。指でドラッグすると奥行きが動きます"
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val now = SystemClock.uptimeMillis()
        if (now - batteryCheckedAt >= 60_000L) {
            batteryCheckedAt = now
            batteryPercent = battery.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
                .takeIf { it in 1..100 }
        }
        renderer.draw(canvas, width.toFloat(), height.toFloat(), dragX, dragY,
            now / 1000f,
            WallpaperConfig.cyberStyle(prefs), WallpaperConfig.intensity(prefs),
            WallpaperConfig.glow(prefs), WallpaperConfig.cyberTiles(prefs),
            WallpaperConfig.cyberTimeColors(prefs), WallpaperConfig.cyberBattery(prefs),
            if (WallpaperConfig.cyberBattery(prefs)) batteryPercent else null,
            WallpaperConfig.cyberRipples(prefs))
        if (isShown) postInvalidateDelayed(50L)
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN, MotionEvent.ACTION_MOVE -> {
                if (event.actionMasked == MotionEvent.ACTION_DOWN && WallpaperConfig.cyberRipples(prefs)) {
                    renderer.emitRipple(event.x / width.coerceAtLeast(1),
                        event.y / height.coerceAtLeast(1), SystemClock.uptimeMillis() / 1000f)
                }
                dragX = ((event.x / width.coerceAtLeast(1)) * 2f - 1f).coerceIn(-1f, 1f)
                dragY = ((event.y / height.coerceAtLeast(1)) * 2f - 1f).coerceIn(-1f, 1f)
                invalidate()
                return true
            }
            MotionEvent.ACTION_UP -> {
                performClick()
                return true
            }
            MotionEvent.ACTION_CANCEL -> return true
        }
        return true
    }

    override fun performClick(): Boolean {
        super.performClick()
        return true
    }
}
