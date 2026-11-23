package com.depthworld.wallpaper

import android.graphics.Bitmap
import android.graphics.Color
import kotlin.math.max
import kotlin.math.min

/**
 * Refines ML Kit's soft foreground confidence mask during import, never per drawn frame.
 *
 * A small color-guided spatial filter smooths blocky/noisy mask edges without freely
 * blurring them across visually distinct colors. Fine detail that the model never
 * detected (individual hairs, transparent glass, etc.) cannot be reconstructed here.
 */
object MatteRefiner {
    fun refineMask(source: Bitmap, confidence: FloatArray, smoothness: Float = 0.85f): FloatArray {
        val width = source.width
        val height = source.height
        val count = width * height
        require(confidence.size == count) { "AIマスクの画像サイズが一致しません" }
        val strength = smoothness.coerceIn(0f, 1f)
        if (strength == 0f) return FloatArray(count) { sanitize(confidence[it]) }
        val colors = IntArray(count)
        source.getPixels(colors, 0, width, 0, 0, width, height)
        val output = FloatArray(count)

        // 3x3 guided convolution: spatial kernel [1,2,1] x [1,2,1].
        // Color contrast lowers cross-edge weights, preserving visible object borders.
        for (y in 0 until height) {
            for (x in 0 until width) {
                val index = y * width + x
                val center = colors[index]
                val red = Color.red(center)
                val green = Color.green(center)
                val blue = Color.blue(center)
                var weighted = 0f
                var total = 0f
                for (dy in -1..1) {
                    val ny = y + dy
                    if (ny !in 0 until height) continue
                    for (dx in -1..1) {
                        val nx = x + dx
                        if (nx !in 0 until width) continue
                        val neighbor = ny * width + nx
                        val pixel = colors[neighbor]
                        val dr = red - Color.red(pixel)
                        val dg = green - Color.green(pixel)
                        val db = blue - Color.blue(pixel)
                        val colorDistance = dr * dr + dg * dg + db * db
                        val spatial = (if (dx == 0) 2f else 1f) *
                            (if (dy == 0) 2f else 1f)
                        val weight = spatial / (1f + colorDistance / 6075f)
                        val value = sanitize(confidence[neighbor])
                        weighted += value * weight
                        total += weight
                    }
                }
                val original = sanitize(confidence[index])
                output[index] = (weighted / total * strength + original * (1f - strength))
                    .coerceIn(0f, 1f)
            }
        }
        return output
    }

    /**
     * Builds a PNG-ready foreground with continuous alpha and modest background
     * color removal on partially transparent pixels. Uses the repaired background
     * as an estimate only: it is not a physically exact alpha matte.
     */
    fun createForeground(source: Bitmap, repairedBackground: Bitmap, confidence: FloatArray): Bitmap {
        val width = source.width
        val height = source.height
        val count = width * height
        require(repairedBackground.width == width && repairedBackground.height == height)
        require(confidence.size == count)
        val pixels = IntArray(count)
        val behind = IntArray(count)
        source.getPixels(pixels, 0, width, 0, 0, width, height)
        repairedBackground.getPixels(behind, 0, width, 0, 0, width, height)

        var detected = 0
        for (i in 0 until count) {
            val value = sanitize(confidence[i])
            if (value > 0.53f) detected++
            val t = ((value - 0.09f) / 0.82f).coerceIn(0f, 1f)
            val alpha = t * t * (3f - 2f * t)
            val original = pixels[i]
            val a = (alpha * Color.alpha(original) + 0.5f).toInt().coerceIn(0, 255)
            if (a == 0) {
                pixels[i] = Color.TRANSPARENT
                continue
            }

            if (a == 255) {
                pixels[i] = Color.rgb(Color.red(original), Color.green(original), Color.blue(original))
                continue
            }
            val background = behind[i]
            val correction = min(0.75f, (1f - alpha) / max(alpha, 0.30f) * 0.65f)
            pixels[i] = Color.argb(a,
                correctChannel(Color.red(original), Color.red(background), correction),
                correctChannel(Color.green(original), Color.green(background), correction),
                correctChannel(Color.blue(original), Color.blue(background), correction))
        }
        require(detected >= max(1, count / 500)) { "切り抜く被写体が見つかりませんでした" }
        return Bitmap.createBitmap(pixels, width, height, Bitmap.Config.ARGB_8888)
    }

    private fun sanitize(value: Float): Float =
        if (value.isFinite()) value.coerceIn(0f, 1f) else 0f

    private fun correctChannel(channel: Int, background: Int, correction: Float): Int {
        val color = (channel + (channel - background) * correction).toInt()
        return color.coerceIn(max(0, channel - 70), min(255, channel + 70))
    }
}
