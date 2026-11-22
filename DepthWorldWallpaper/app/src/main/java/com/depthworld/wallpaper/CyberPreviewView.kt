package com.depthworld.wallpaper

import android.content.Context
import android.graphics.Canvas
import android.view.MotionEvent
import android.view.View
import android.os.SystemClock

/** Live settings preview: drag to see the layers separate before setting wallpaper. */
class CyberPreviewView(context: Context) : View(context) {
    private val renderer = CyberCircuitRenderer()
    private val prefs = WallpaperConfig.preferences(context)
    private var dragX = 0f
    private var dragY = 0f

    init {
        contentDescription = "サイバー壁紙のプレビュー。指でドラッグすると奥行きが動きます"
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        renderer.draw(canvas, width.toFloat(), height.toFloat(), dragX, dragY,
            SystemClock.uptimeMillis() / 1000f,
            WallpaperConfig.cyberStyle(prefs), WallpaperConfig.intensity(prefs),
            WallpaperConfig.glow(prefs), WallpaperConfig.cyberTiles(prefs))
        if (isShown) postInvalidateDelayed(50L)
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN, MotionEvent.ACTION_MOVE -> {
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
