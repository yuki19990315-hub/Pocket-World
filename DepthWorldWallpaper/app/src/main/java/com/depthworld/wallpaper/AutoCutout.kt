package com.depthworld.wallpaper

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.ImageDecoder
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.segmentation.subject.SubjectSegmentation
import com.google.mlkit.vision.segmentation.subject.SubjectSegmenterOptions
import java.io.File
import java.io.FileOutputStream
import java.nio.FloatBuffer
import kotlin.concurrent.thread
import kotlin.math.max

/**
 * Runs Google ML Kit subject separation on the phone. ML Kit isolates subjects;
 * the background hole is filled by deterministic nearest-neighbor diffusion,
 * NOT generative AI inpainting (hidden details cannot be recovered from 1 photo).
 */
object AutoCutout {
    fun create(context: Context, uri: Uri, onDone: (Result<Unit>) -> Unit) {
        val app = context.applicationContext
        val ui = Handler(Looper.getMainLooper())
        thread(name = "depthworld-image-decode") {
            val source = try {
                decodeSampled(app, uri)
            } catch (e: Exception) {
                ui.post { onDone(Result.failure(e)) }
                return@thread
            }
            ui.post {
                val options = SubjectSegmenterOptions.Builder()
                    .enableForegroundConfidenceMask()
                    .enableForegroundBitmap()
                    .build()
                val segmenter = SubjectSegmentation.getClient(options)
                val input = InputImage.fromBitmap(source, 0)
                segmenter.process(input)
                    .addOnSuccessListener { segmentation ->
                        val subject = segmentation.foregroundBitmap
                        val mask = segmentation.foregroundConfidenceMask
                        if (subject == null || mask == null) {
                            segmenter.close()
                            source.recycle()
                            onDone(Result.failure(IllegalStateException("前景の被写体を認識できませんでした")))
                        } else {
                            thread(name = "depthworld-background-repair") {
                                try {
                                    val background = fillHiddenArea(source, mask)
                                    writePng(app, background, "background")
                                    writePng(app, subject, "foreground")
                                    background.recycle()
                                    ui.post { onDone(Result.success(Unit)) }
                                } catch (e: Exception) {
                                    ui.post { onDone(Result.failure(e)) }
                                } finally {
                                    segmenter.close()
                                    source.recycle()
                                }
                            }
                        }
                    }
                    .addOnFailureListener { e ->
                        segmenter.close()
                        source.recycle()
                        onDone(Result.failure(IllegalStateException(
                            "初回はGoogle Play開発者サービスのAIモデル取得が必要です。時間を置いて再試行してください: ${e.message}", e
                        )))
                    }
            }
        }
    }

    private fun decodeSampled(context: Context, uri: Uri): Bitmap {
        if (Build.VERSION.SDK_INT >= 28) {
            val source = ImageDecoder.createSource(context.contentResolver, uri)
            return ImageDecoder.decodeBitmap(source) { decoder, info, _ ->
                decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
                var sample = 1
                while (max(info.size.width, info.size.height) / sample > 1600) sample *= 2
                decoder.setTargetSampleSize(sample)
            }
        }
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        val headerStream = context.contentResolver.openInputStream(uri) ?: error("画像を読み込めません")
        headerStream.use { BitmapFactory.decodeStream(it, null, bounds) }
        require(bounds.outWidth > 0 && bounds.outHeight > 0) { "画像形式が不正です" }
        var sample = 1
        while (max(bounds.outWidth, bounds.outHeight) / sample > 1600) sample *= 2
        val options = BitmapFactory.Options().apply { inSampleSize = sample }
        return context.contentResolver.openInputStream(uri)?.use {
            BitmapFactory.decodeStream(it, null, options)
        } ?: error("画像をデコードできません")
    }

    /** Simplified fill: spreads surrounding background colors inward, then smooths. */
    internal fun fillHiddenArea(source: Bitmap, confidence: FloatBuffer,
                                blurRadius: Int = 3, edgeExpansion: Int = 2): Bitmap {
        val width = source.width
        val height = source.height
        val count = width * height
        require(confidence.capacity() >= count) { "AIマスクの画像サイズが一致しません" }
        val original = IntArray(count)
        source.getPixels(original, 0, width, 0, 0, width, height)
        val blocked = BooleanArray(count)
        var subjectPixels = 0
        for (index in 0 until count) {
            if (confidence.get(index) > 0.53f) {
                blocked[index] = true
                subjectPixels++
            }
        }
        require(subjectPixels > count / 300) { "切り抜く被写体が見つかりませんでした" }

        // Expand the hole slightly to remove colored outlines along the cutout.
        val expanded = blocked.copyOf()
        if (edgeExpansion > 0) {
            for (y in 1 until height - 1) {
                for (x in 1 until width - 1) {
                    val index = y * width + x
                    if (!blocked[index]) continue
                    for (dy in -edgeExpansion..edgeExpansion) {
                        for (dx in -edgeExpansion..edgeExpansion) {
                            val nx = x + dx
                            val ny = y + dy
                            if (nx in 0 until width && ny in 0 until height) expanded[ny * width + nx] = true
                        }
                    }
                }
            }
        }

        val filled = original.copyOf()
        val seen = BooleanArray(count)
        val queue = IntArray(count)
        var head = 0
        var tail = 0
        for (i in 0 until count) {
            if (!expanded[i]) {
                seen[i] = true
                queue[tail++] = i
            }
        }
        require(tail > 0) { "背景領域が足りません" }
        while (head < tail) {
            val pos = queue[head++]
            val x = pos % width
            val y = pos / width
            if (x > 0 && !seen[pos - 1]) {
                seen[pos - 1] = true
                filled[pos - 1] = filled[pos]
                queue[tail++] = pos - 1
            }
            if (x < width - 1 && !seen[pos + 1]) {
                seen[pos + 1] = true
                filled[pos + 1] = filled[pos]
                queue[tail++] = pos + 1
            }
            if (y > 0 && !seen[pos - width]) {
                seen[pos - width] = true
                filled[pos - width] = filled[pos]
                queue[tail++] = pos - width
            }
            if (y < height - 1 && !seen[pos + width]) {
                seen[pos + width] = true
                filled[pos + width] = filled[pos]
                queue[tail++] = pos + width
            }
        }

        // Blur the reconstructed region only; preserve the untouched real image.
        val smooth = filled.copyOf()
        for (y in 0 until height) {
            for (x in 0 until width) {
                val index = y * width + x
                if (!expanded[index]) continue
                var red = 0L
                var green = 0L
                var blue = 0L
                var amount = 0
                for (dy in -blurRadius..blurRadius) {
                    val ny = y + dy
                    if (ny !in 0 until height) continue
                    for (dx in -blurRadius..blurRadius) {
                        val nx = x + dx
                        if (nx !in 0 until width) continue
                        val color = filled[ny * width + nx]
                        red += Color.red(color)
                        green += Color.green(color)
                        blue += Color.blue(color)
                        amount++
                    }
                }
                smooth[index] = Color.rgb((red / amount).toInt(), (green / amount).toInt(),
                    (blue / amount).toInt())
            }
        }
        return Bitmap.createBitmap(smooth, width, height, Bitmap.Config.ARGB_8888)
    }

    private fun writePng(context: Context, bitmap: Bitmap, layer: String) {
        val destination = ImageStore.file(context, layer)
        destination.parentFile?.mkdirs()
        val temporary = File(destination.parentFile, "$layer.generated")
        try {
            FileOutputStream(temporary).use { output ->
                check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, output)) { "PNG保存に失敗" }
            }
            if (destination.exists()) check(destination.delete()) { "古い画像を置き換えられません" }
            check(temporary.renameTo(destination)) { "画像を保存できません" }
        } finally {
            if (temporary.exists()) temporary.delete()
        }
    }
}
