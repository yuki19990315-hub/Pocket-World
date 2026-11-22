package com.depthworld.wallpaper

import android.content.SharedPreferences
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RadialGradient
import android.graphics.RectF
import android.graphics.Shader
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.BatteryManager
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.os.SystemClock
import android.service.wallpaper.WallpaperService
import android.view.MotionEvent
import android.view.SurfaceHolder
import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin

/** Canvas parallax live wallpaper; uses ML Kit only during import, never while rendering. */
class ParallaxWallpaperService : WallpaperService() {
    override fun onCreateEngine(): Engine = DepthEngine()

    private inner class DepthEngine : Engine(), SensorEventListener,
        SharedPreferences.OnSharedPreferenceChangeListener {

        private val prefs = WallpaperConfig.preferences(this@ParallaxWallpaperService)
        private val sensors = getSystemService(SENSOR_SERVICE) as SensorManager
        private val power = getSystemService(POWER_SERVICE) as PowerManager
        private val battery = getSystemService(BATTERY_SERVICE) as BatteryManager
        private val sensor: Sensor? = sensors.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR)
            ?: sensors.getDefaultSensor(Sensor.TYPE_GAME_ROTATION_VECTOR)
            ?: sensors.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
        private val handler = Handler(Looper.getMainLooper())
        private val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
        private val cyberRenderer = CyberCircuitRenderer()

        private var visible = false
        private var surfaceReady = false
        private var listening = false
        private var powerSaveAtRegistration = power.isPowerSaveMode
        private var background: Bitmap? = null
        private var glowBitmap: Bitmap? = null
        private var foreground: Bitmap? = null
        private var videoFrames: VideoFrames? = null
        private var videoStartUptime = 0L
        private var batteryCheckedAt = -60_000L
        private var batteryPercent: Int? = null

        private var tiltX = 0f
        private var tiltY = 0f
        private var touchX = 0f
        private var touchY = 0f
        private var touching = false
        private var calibrated = false
        private var baseX = 0f
        private var baseY = 0f

        private val frame = object : Runnable {
            override fun run() {
                if (!visible || !surfaceReady) return
                if (powerSaveAtRegistration != power.isPowerSaveMode) {
                    if (listening) {
                        sensors.unregisterListener(this@DepthEngine)
                        listening = false
                    }
                    powerSaveAtRegistration = power.isPowerSaveMode
                    updateSensorListening()
                }
                drawFrame()
                val interval = when {
                    power.isPowerSaveMode -> 50L
                    WallpaperConfig.fps(prefs) == 60 -> 16L
                    else -> 33L
                }
                handler.postDelayed(this, interval)
            }
        }

        override fun onCreate(surfaceHolder: SurfaceHolder) {
            super.onCreate(surfaceHolder)
            setTouchEventsEnabled(true)
            prefs.registerOnSharedPreferenceChangeListener(this)
            reloadImages()
        }

        override fun onSurfaceCreated(holder: SurfaceHolder) {
            super.onSurfaceCreated(holder)
            surfaceReady = true
            if (background == null) reloadImages()
            if (visible) start()
        }

        override fun onSurfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) {
            super.onSurfaceChanged(holder, format, width, height)
            if (visible) drawFrame()
        }

        override fun onVisibilityChanged(visible: Boolean) {
            super.onVisibilityChanged(visible)
            this.visible = visible
            if (visible && surfaceReady) start() else stop()
        }

        private fun start() {
            handler.removeCallbacks(frame)
            videoStartUptime = SystemClock.uptimeMillis()
            powerSaveAtRegistration = power.isPowerSaveMode
            updateSensorListening()
            handler.post(frame)
        }

        private fun updateSensorListening() {
            val enabled = visible && surfaceReady && sensor != null &&
                prefs.getBoolean(WallpaperConfig.TILT_ENABLED, true)
            if (enabled && !listening) {
                listening = sensors.registerListener(this, sensor,
                    if (power.isPowerSaveMode) SensorManager.SENSOR_DELAY_UI else SensorManager.SENSOR_DELAY_GAME)
            } else if (!enabled && listening) {
                sensors.unregisterListener(this)
                listening = false
            }
        }

        private fun stop() {
            handler.removeCallbacks(frame)
            if (listening) {
                sensors.unregisterListener(this)
                listening = false
            }
        }

        override fun onSurfaceDestroyed(holder: SurfaceHolder) {
            surfaceReady = false
            stop()
            super.onSurfaceDestroyed(holder)
        }

        override fun onDestroy() {
            stop()
            prefs.unregisterOnSharedPreferenceChangeListener(this)
            releaseImages()
            releaseVideo()
            super.onDestroy()
        }

        override fun onSharedPreferenceChanged(sharedPreferences: SharedPreferences?, key: String?) {
            when (key) {
                WallpaperConfig.MODE, WallpaperConfig.WORLD, WallpaperConfig.STAGE,
                WallpaperConfig.RELOAD_IMAGES, WallpaperConfig.VIDEO_ID -> reloadImages()
                WallpaperConfig.RECENTER -> {
                    calibrated = false
                    tiltX = 0f
                    tiltY = 0f
                }
                WallpaperConfig.TILT_ENABLED -> {
                    calibrated = false
                    tiltX = 0f
                    tiltY = 0f
                    updateSensorListening()
                }
                WallpaperConfig.INVERT_TILT_X -> tiltX = 0f
            }
        }

        override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit

        override fun onSensorChanged(event: SensorEvent) {
            val x: Float
            val y: Float
            if (event.sensor.type == Sensor.TYPE_ACCELEROMETER) {
                x = event.values[0] / 9.81f
                y = event.values[1] / 9.81f
            } else {
                val matrix = FloatArray(9)
                SensorManager.getRotationMatrixFromVector(matrix, event.values)
                val angles = FloatArray(3)
                SensorManager.getOrientation(matrix, angles)
                x = angles[2]
                y = angles[1]
            }
            if (!calibrated) {
                baseX = x
                baseY = y
                calibrated = true
            }
            val dx = normalizedDelta(x, baseX)
            val dy = normalizedDelta(y, baseY)
            val horizontal = if (WallpaperConfig.invertTiltX(prefs)) -dx else dx
            tiltX = tiltX * 0.90f + horizontal * 0.10f
            tiltY = tiltY * 0.90f + dy * 0.10f
        }

        private fun normalizedDelta(current: Float, initial: Float): Float {
            val delta = atan2(sin(current - initial), cos(current - initial))
            return (delta / 0.35f).coerceIn(-1f, 1f)
        }

        override fun onTouchEvent(event: MotionEvent) {
            val moving = prefs.getBoolean(WallpaperConfig.TOUCH, true)
            val rippling = WallpaperConfig.mode(prefs) == WallpaperConfig.CYBER &&
                WallpaperConfig.cyberRipples(prefs)
            if (!moving && !rippling) return
            val width = max(1, surfaceHolder.surfaceFrame.width()).toFloat()
            val height = max(1, surfaceHolder.surfaceFrame.height()).toFloat()
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    if (rippling) cyberRenderer.emitRipple(event.x / width, event.y / height,
                        SystemClock.uptimeMillis() / 1000f)
                    if (moving) {
                        touching = true
                        touchX = ((event.x / width) * 2f - 1f).coerceIn(-1f, 1f)
                        touchY = ((event.y / height) * 2f - 1f).coerceIn(-1f, 1f)
                    }
                }
                MotionEvent.ACTION_MOVE -> {
                    if (moving) {
                        touching = true
                        touchX = ((event.x / width) * 2f - 1f).coerceIn(-1f, 1f)
                        touchY = ((event.y / height) * 2f - 1f).coerceIn(-1f, 1f)
                    }
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> touching = false
            }
        }

        private fun loadDrawable(id: Int): Bitmap? = try {
            BitmapFactory.decodeResource(resources, id, BitmapFactory.Options().apply { inScaled = false })
        } catch (_: Exception) { null }

        private fun loadAsset(path: String): Bitmap? = try {
            assets.open(path).use { BitmapFactory.decodeStream(it) }
        } catch (_: Exception) { null }

        private fun loadCustom(layer: String): Bitmap? {
            return try {
                val file = ImageStore.file(this@ParallaxWallpaperService, layer)
                if (!file.exists()) null else {
                    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                    BitmapFactory.decodeFile(file.path, bounds)
                    var sample = 1
                    while (max(bounds.outWidth, bounds.outHeight) / sample > 2600) sample *= 2
                    BitmapFactory.decodeFile(file.path, BitmapFactory.Options().apply { inSampleSize = sample })
                }
            } catch (_: Exception) { null }
        }

        private fun releaseImages() {
            listOf(background, glowBitmap, foreground).filterNotNull().distinct().forEach {
                if (!it.isRecycled) it.recycle()
            }
            background = null
            glowBitmap = null
            foreground = null
        }

        private fun releaseVideo() {
            videoFrames?.close()
            videoFrames = null
        }

        private fun reloadImages() {
            releaseImages()
            releaseVideo()
            when (WallpaperConfig.mode(prefs)) {
                WallpaperConfig.CYBER -> Unit
                WallpaperConfig.VIDEO -> {
                    val id = prefs.getString(WallpaperConfig.VIDEO_ID, null)
                    if (id != null) {
                        try {
                            videoFrames = VideoFrames(VideoStore.directory(this@ParallaxWallpaperService, id))
                            videoStartUptime = SystemClock.uptimeMillis()
                        } catch (_: Exception) {
                            // Missing/incomplete video: retain the fallback gradient.
                        }
                    }
                }
                WallpaperConfig.CUSTOM -> {
                    background = loadCustom("background") ?: loadDrawable(R.drawable.fantasy_bg)
                    glowBitmap = loadCustom("glow")
                    foreground = loadCustom("foreground")
                }
                WallpaperConfig.POCKET -> {
                    val id = WallpaperConfig.worldIds[WallpaperConfig.world(prefs)]
                    val stage = if (WallpaperConfig.stage(prefs) == 0) "young" else "mature"
                    foreground = if (id == "hybrid" && stage == "mature") {
                        loadDrawable(R.drawable.pocket_island)
                    } else {
                        loadAsset("pocketworld/$id-$stage.png")
                    }
                }
                else -> {
                    background = loadDrawable(R.drawable.fantasy_bg)
                    foreground = loadDrawable(R.drawable.fantasy_island)
                }
            }
        }

        private fun drawFrame() {
            if (!visible || !surfaceReady) return
            var canvas: Canvas? = null
            try {
                canvas = surfaceHolder.lockCanvas() ?: return
                val w = canvas.width.toFloat()
                val h = canvas.height.toFloat()
                val time = SystemClock.uptimeMillis() / 1000f
                val breathing = (0.85f + 0.15f * sin(time * (2f * Math.PI.toFloat() / 4f))).coerceIn(0.7f, 1f)
                val strength = WallpaperConfig.intensity(prefs)
                val tx = (tiltX + touchX * 0.45f).coerceIn(-1f, 1f) * strength
                val ty = (tiltY + touchY * 0.45f).coerceIn(-1f, 1f) * strength
                when (WallpaperConfig.mode(prefs)) {
                    WallpaperConfig.CYBER -> cyberRenderer.draw(canvas, w, h, tx, ty, time,
                        WallpaperConfig.cyberStyle(prefs), 1f, WallpaperConfig.glow(prefs),
                        WallpaperConfig.cyberTiles(prefs),
                        WallpaperConfig.cyberTimeColors(prefs), WallpaperConfig.cyberBattery(prefs),
                        if (WallpaperConfig.cyberBattery(prefs)) currentBatteryPercent() else null,
                        WallpaperConfig.cyberRipples(prefs))
                    WallpaperConfig.VIDEO -> drawVideo(canvas, w, h, tx, ty, time, breathing)
                    WallpaperConfig.CUSTOM -> drawCustom(canvas, w, h, tx, ty, time, breathing)
                    WallpaperConfig.POCKET -> drawPocket(canvas, w, h, tx, ty, time, breathing)
                    else -> drawFantasy(canvas, w, h, tx, ty, time, breathing)
                }
                if (!touching) {
                    touchX *= 0.93f
                    touchY *= 0.93f
                }
            } catch (_: Exception) {
                // Ignore drawing during surface teardown; next visible frame retries.
            } finally {
                if (canvas != null) {
                    try { surfaceHolder.unlockCanvasAndPost(canvas) } catch (_: Exception) { }
                }
            }
        }

        private fun currentBatteryPercent(): Int? {
            val now = SystemClock.uptimeMillis()
            if (now - batteryCheckedAt >= 60_000L) {
                batteryCheckedAt = now
                val percent = battery.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
                batteryPercent = percent.takeIf { it in 1..100 }
            }
            return batteryPercent
        }

        private fun drawFantasy(canvas: Canvas, w: Float, h: Float, tx: Float, ty: Float,
                                time: Float, breath: Float) {
            drawGradient(canvas, w, h, Color.rgb(10, 10, 42), Color.rgb(57, 44, 116))
            background?.let { drawCover(canvas, it, w, h, tx * w * .05f, ty * h * .05f, 1.45f) }
            drawStars(canvas, w, h, time, .30f)
            val cx = w * .50f - tx * w * .25f
            val cy = h * .55f - ty * h * .16f + sin(time * .65f) * h * .008f
            drawHalo(canvas, cx, cy + h * .02f, w * .60f, breath * WallpaperConfig.glow(prefs), Color.CYAN)
            foreground?.let { drawFloating(canvas, it, cx, cy, w * 1.13f, h * .64f, true, false) }
        }

        private fun drawPocket(canvas: Canvas, w: Float, h: Float, tx: Float, ty: Float,
                               time: Float, breath: Float) {
            drawGradient(canvas, w, h, Color.rgb(11, 35, 77), Color.rgb(122, 165, 199))
            drawStars(canvas, w, h, time, .22f)
            drawCloud(canvas, w * .23f + tx * w * .03f, h * .29f, w * .36f)
            drawCloud(canvas, w * .80f + tx * w * .03f, h * .66f, w * .30f)
            val cx = w * .50f - tx * w * .23f
            val cy = h * .54f - ty * h * .14f + sin(time * .7f) * h * .009f
            drawHalo(canvas, cx, cy + h * .08f, w * .55f, breath * WallpaperConfig.glow(prefs) * .65f,
                Color.rgb(106, 223, 215))
            foreground?.let {
                val isIsland = WallpaperConfig.world(prefs) == 0 && WallpaperConfig.stage(prefs) == 1
                if (isIsland) drawFloating(canvas, it, cx, cy, w * 1.2f, h * .59f, true, true)
                else drawSceneWindow(canvas, it, cx, cy, w * .89f)
            }
        }

        private fun drawCustom(canvas: Canvas, w: Float, h: Float, tx: Float, ty: Float,
                               time: Float, breath: Float) {
            drawGradient(canvas, w, h, Color.rgb(12, 14, 42), Color.rgb(66, 59, 99))
            background?.let { drawCover(canvas, it, w, h, tx * w * .05f, ty * h * .05f, 1.45f) }
            glowBitmap?.let {
                paint.alpha = (255f * breath * WallpaperConfig.glow(prefs)).toInt().coerceIn(0, 255)
                drawCover(canvas, it, w, h, tx * w * .12f, ty * h * .12f, 1.28f)
                paint.alpha = 255
            }
            val preset = WallpaperConfig.lightPreset(prefs)
            val strength = WallpaperConfig.glow(prefs) * breath
            LightEffects.behind(canvas, w, h, tx, ty, preset, strength, time)
            foreground?.let {
                val cx = w * .5f - tx * w * .25f
                val cy = h * .59f - ty * h * .18f
                if (prefs.getBoolean(WallpaperConfig.AUTO_ALIGNED, false)) {
                    // AI cutout retains the source image dimensions; using the exact
                    // background crop avoids a jump at the neutral tilt position.
                    drawCover(canvas, it, w, h, -tx * w * .25f, -ty * h * .25f, 1.45f)
                } else {
                    drawHalo(canvas, cx, cy + h * .09f, w * .35f,
                        breath * WallpaperConfig.glow(prefs) * .35f, Color.WHITE)
                    drawFloating(canvas, it, cx, cy, w * 1.02f, h * .70f, true, false)
                }
            }
            LightEffects.inFront(canvas, w, h, tx, ty, preset, strength, time)
        }

        private fun drawVideo(canvas: Canvas, w: Float, h: Float, tx: Float, ty: Float,
                              time: Float, breath: Float) {
            drawGradient(canvas, w, h, Color.rgb(9, 12, 29), Color.rgb(42, 32, 72))
            val sequence = videoFrames ?: return
            val elapsedMs = (SystemClock.uptimeMillis() - videoStartUptime).coerceAtLeast(0L)
            val step = (elapsedMs * sequence.info.fps * WallpaperConfig.videoSpeed(prefs) / 1000f)
                .toLong()
            val count = sequence.info.frames
            val pingpong = prefs.getBoolean(WallpaperConfig.VIDEO_PINGPONG, false)
            var reverse = false
            val index = if (pingpong && count > 1) {
                val period = (count - 1) * 2
                val phase = (step % period).toInt()
                reverse = phase >= count
                if (phase < count) phase else period - phase
            } else (step % count).toInt()
            val layers = sequence.frame(index, reverse) ?: return
            // Both layers preserve the original crop, then separate during tilt.
            val zoom = WallpaperConfig.videoZoom(prefs)
            val offsetX = WallpaperConfig.videoOffsetX(prefs) * w
            val offsetY = WallpaperConfig.videoOffsetY(prefs) * h
            drawCover(canvas, layers.background, w, h,
                offsetX + tx * w * .05f, offsetY + ty * h * .05f, zoom)
            val preset = WallpaperConfig.lightPreset(prefs)
            val light = WallpaperConfig.glow(prefs) * breath
            LightEffects.behind(canvas, w, h, tx, ty, preset, light, time)
            layers.foreground?.let {
                paint.shader = RadialGradient(w * .5f + tx * w * .10f,
                    h * .62f + ty * h * .07f, w * .43f,
                    intArrayOf(Color.argb(74, 2, 5, 15), Color.TRANSPARENT),
                    null, Shader.TileMode.CLAMP)
                canvas.drawOval(RectF(w * .12f, h * .40f, w * .88f, h * .84f), paint)
                paint.shader = null
                drawCover(canvas, it, w, h,
                    offsetX - tx * w * .25f, offsetY - ty * h * .25f, zoom)
            }
            LightEffects.inFront(canvas, w, h, tx, ty, preset, light, time)
        }

        private fun drawGradient(canvas: Canvas, w: Float, h: Float, top: Int, bottom: Int) {
            paint.shader = LinearGradient(0f, 0f, 0f, h, top, bottom, Shader.TileMode.CLAMP)
            paint.alpha = 255
            canvas.drawRect(0f, 0f, w, h, paint)
            paint.shader = null
        }

        private fun drawCover(canvas: Canvas, bitmap: Bitmap, w: Float, h: Float,
                              dx: Float, dy: Float, overscan: Float) {
            val scale = max(w / bitmap.width, h / bitmap.height) * overscan
            val width = bitmap.width * scale
            val height = bitmap.height * scale
            val destination = RectF((w - width) / 2f + dx, (h - height) / 2f + dy,
                (w + width) / 2f + dx, (h + height) / 2f + dy)
            val previousAlpha = paint.alpha
            paint.isFilterBitmap = true
            canvas.drawBitmap(bitmap, null, destination, paint)
            paint.alpha = previousAlpha
        }

        private fun drawFloating(canvas: Canvas, bitmap: Bitmap, cx: Float, cy: Float,
                                 maxWidth: Float, maxHeight: Float, shadow: Boolean, pixelArt: Boolean) {
            val scale = min(maxWidth / bitmap.width, maxHeight / bitmap.height)
            val width = bitmap.width * scale
            val height = bitmap.height * scale
            val area = RectF(cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2)
            if (shadow) {
                paint.shader = RadialGradient(cx, cy + height * .21f, width * .55f,
                    intArrayOf(Color.argb(92, 1, 12, 29), Color.argb(0, 1, 12, 29)),
                    floatArrayOf(0f, 1f), Shader.TileMode.CLAMP)
                canvas.drawOval(RectF(cx - width * .56f, cy - height * .10f,
                    cx + width * .56f, cy + height * .48f), paint)
                paint.shader = null
            }
            paint.alpha = 255
            paint.isFilterBitmap = !pixelArt
            canvas.drawBitmap(bitmap, null, area, paint)
            paint.isFilterBitmap = true
        }

        private fun drawSceneWindow(canvas: Canvas, bitmap: Bitmap, cx: Float, cy: Float, size: Float) {
            val shadow = RectF(cx - size * .52f, cy - size * .52f, cx + size * .52f, cy + size * .54f)
            paint.color = Color.argb(115, 2, 12, 31)
            paint.shader = null
            canvas.drawRoundRect(shadow, size * .12f, size * .12f, paint)
            val box = RectF(cx - size * .5f, cy - size * .5f, cx + size * .5f, cy + size * .5f)
            val path = Path().apply { addRoundRect(box, size * .10f, size * .10f, Path.Direction.CW) }
            canvas.save()
            canvas.clipPath(path)
            paint.color = Color.WHITE
            paint.alpha = 255
            paint.isFilterBitmap = false
            canvas.drawBitmap(bitmap, null, box, paint)
            canvas.restore()
            paint.isFilterBitmap = true
            paint.style = Paint.Style.STROKE
            paint.strokeWidth = size * .012f
            paint.color = Color.argb(180, 228, 244, 250)
            canvas.drawRoundRect(box, size * .10f, size * .10f, paint)
            paint.style = Paint.Style.FILL
            paint.color = Color.WHITE
        }

        private fun drawHalo(canvas: Canvas, x: Float, y: Float, radius: Float, strength: Float, tint: Int) {
            val alpha = (90f * strength).toInt().coerceIn(0, 120)
            paint.shader = RadialGradient(x, y, radius,
                intArrayOf(Color.argb(alpha, Color.red(tint), Color.green(tint), Color.blue(tint)),
                    Color.TRANSPARENT), floatArrayOf(0f, 1f), Shader.TileMode.CLAMP)
            paint.alpha = 255
            canvas.drawCircle(x, y, radius, paint)
            paint.shader = null
        }

        private fun drawStars(canvas: Canvas, w: Float, h: Float, time: Float, opacity: Float) {
            paint.shader = null
            for (index in 0 until 46) {
                val x = ((index * 157 + 53) % 997) / 997f * w
                val y = ((index * 229 + 91) % 947) / 947f * h
                val pulse = 0.66f + 0.34f * sin(time * (0.5f + index % 5 * .17f) + index)
                paint.color = Color.argb((255f * opacity * pulse).toInt().coerceIn(0, 255), 226, 255, 255)
                canvas.drawCircle(x, y, if (index % 8 == 0) w * .0042f else w * .002f, paint)
            }
            paint.color = Color.WHITE
        }

        private fun drawCloud(canvas: Canvas, cx: Float, cy: Float, radius: Float) {
            paint.shader = RadialGradient(cx, cy, radius,
                intArrayOf(Color.argb(80, 230, 248, 255), Color.TRANSPARENT),
                floatArrayOf(0f, 1f), Shader.TileMode.CLAMP)
            canvas.drawOval(RectF(cx - radius * 1.6f, cy - radius * .27f,
                cx + radius * 1.6f, cy + radius * .27f), paint)
            paint.shader = null
        }
    }
}
