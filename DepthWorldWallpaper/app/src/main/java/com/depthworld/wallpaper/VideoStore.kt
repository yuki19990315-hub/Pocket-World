package com.depthworld.wallpaper

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.LruCache
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.segmentation.subject.SubjectSegmentation
import com.google.mlkit.vision.segmentation.subject.SubjectSegmenterOptions
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.nio.FloatBuffer
import java.util.Properties
import java.util.UUID
import java.util.concurrent.CancellationException
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

/**
 * Converts a short, silent video to private on-device image sequences before playback.
 * This intentionally avoids trying to draw Canvas effects on MediaPlayer's Surface.
 * It is a CPU/space-limited prototype, NOT hardware-decoded full-frame-rate video.
 */
object VideoStore {
    private const val MAX_NORMAL_MS = 8_000L
    private const val MAX_AI_MS = 6_000L
    private const val NORMAL_FPS = 20
    private const val AI_FPS = 10

    data class VideoInfo(val fps: Int, val frames: Int, val ai: Boolean,
                         val startMs: Long, val durationMs: Long)

    fun directory(context: Context, id: String): File {
        require(id.matches(Regex("[A-Za-z0-9_-]{8,50}"))) { "動画IDが不正です" }
        return File(File(context.filesDir, "video_sequences"), id)
    }

    fun readInfo(directory: File): VideoInfo {
        val properties = Properties()
        FileInputStream(File(directory, "video.properties")).use { properties.load(it) }
        val frames = properties.getProperty("frames").toInt()
        val fps = properties.getProperty("fps").toInt()
        require(frames in 1..200 && fps in 1..30) { "動画の情報が不正です" }
        return VideoInfo(fps, frames, properties.getProperty("ai") == "true",
            properties.getProperty("start_ms")?.toLongOrNull() ?: 0L,
            properties.getProperty("duration_ms")?.toLongOrNull() ?: frames * 1000L / fps)
    }

    /** Progress and completion always run on the UI thread. */
    fun prepare(context: Context, uri: Uri, ai: Boolean, startSeconds: Int, lengthSeconds: Int,
                progress: (Int, String) -> Unit, onDone: (Result<String>) -> Unit): AtomicBoolean {
        val app = context.applicationContext
        val main = Handler(Looper.getMainLooper())
        val cancelled = AtomicBoolean(false)
        thread(name = "depthworld-video-import") {
            val id = UUID.randomUUID().toString().replace("-", "")
            val destination = directory(app, id)
            val staging = File(destination.parentFile, "$id.preparing")
            val retriever = MediaMetadataRetriever()
            var segmenter: com.google.mlkit.vision.segmentation.subject.SubjectSegmenter? = null
            try {
                check(staging.mkdirs()) { "動画用フォルダを作成できません" }
                retriever.setDataSource(app, uri)
                val durationMs = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)
                    ?.toLongOrNull() ?: error("動画の長さを取得できません")
                require(durationMs > 0L) { "動画が空です" }
                val startMs = min(startSeconds.coerceIn(0, 60) * 1000L,
                    (durationMs - 2000L).coerceAtLeast(0L))
                val limit = min(if (ai) MAX_AI_MS else MAX_NORMAL_MS,
                    lengthSeconds.coerceIn(2, 8) * 1000L)
                val totalMs = min(durationMs - startMs, limit)
                val fps = if (ai) AI_FPS else NORMAL_FPS
                val frameCount = ((totalMs * fps + 999L) / 1000L).toInt().coerceIn(1, 200)
                val sourceWidth = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)
                    ?.toIntOrNull() ?: 0
                val sourceHeight = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT)
                    ?.toIntOrNull() ?: 0
                val scale = if (sourceWidth > 0 && sourceHeight > 0) {
                    min(1f, min(720f / sourceWidth, 960f / sourceHeight))
                } else 1f
                val targetWidth = max(1, (sourceWidth * scale).toInt())
                val targetHeight = max(1, (sourceHeight * scale).toInt())

                var previousMask: FloatArray? = null
                val smoothness = WallpaperConfig.cutoutSmoothness(WallpaperConfig.preferences(app))
                if (ai) {
                    segmenter = SubjectSegmentation.getClient(
                        SubjectSegmenterOptions.Builder()
                            .enableForegroundConfidenceMask()
                            .build()
                    )
                }

                for (i in 0 until frameCount) {
                    if (cancelled.get()) throw CancellationException("ユーザーが動画の変換を中止しました")
                    val timestampUs = (startMs * 1000L + i.toLong() * 1_000_000L / fps)
                        .coerceAtMost(durationMs * 1000L - 1L)
                    val decoded = if (Build.VERSION.SDK_INT >= 27 && sourceWidth > 0 && sourceHeight > 0) {
                        retriever.getScaledFrameAtTime(timestampUs, MediaMetadataRetriever.OPTION_CLOSEST,
                            targetWidth, targetHeight)
                    } else null
                    val extracted = decoded ?: retriever.getFrameAtTime(
                        timestampUs, MediaMetadataRetriever.OPTION_CLOSEST
                    ) ?: error("${i + 1}枚目の動画フレームを読み込めません")
                    val frame = scaleFrame(extracted)
                    try {
                        val background: Bitmap
                        if (ai) {
                            val result = Tasks.await(
                                segmenter!!.process(InputImage.fromBitmap(frame, 0)),
                                60, TimeUnit.SECONDS
                            )
                            val mask = result.foregroundConfidenceMask
                                ?: error("${i + 1}枚目でAIマスクを取得できません")
                            val stabilized = stabilizeMask(mask, frame.width * frame.height, previousMask)
                            previousMask = stabilized
                            val refined = MatteRefiner.refineMask(frame, stabilized, smoothness)
                            background = AutoCutout.fillHiddenArea(frame, FloatBuffer.wrap(refined), 1, 1)
                            try {
                                val subject = MatteRefiner.createForeground(frame, background, refined)
                                try {
                                    writeBitmap(subject, File(staging, "fg_${i.toString().padStart(4, '0')}.png"),
                                        Bitmap.CompressFormat.PNG, 100)
                                } finally {
                                    subject.recycle()
                                }
                            } catch (error: Exception) {
                                background.recycle()
                                throw error
                            }
                        } else {
                            background = frame
                        }
                        try {
                            writeBitmap(background, File(staging, "bg_${i.toString().padStart(4, '0')}.jpg"),
                                Bitmap.CompressFormat.JPEG, 86)
                        } finally {
                            if (background !== frame && !background.isRecycled) background.recycle()
                        }
                    } finally {
                        if (!frame.isRecycled) frame.recycle()
                    }
                    // Avoid flooding the UI thread with a callback for every frame.
                    if (i == 0 || (i + 1) % 3 == 0 || i == frameCount - 1) {
                        val percent = ((i + 1) * 100 / frameCount).coerceIn(0, 100)
                        main.post { progress(percent, if (ai) "AIで動画を分離中" else "動画を準備中") }
                    }
                }
                if (cancelled.get()) throw CancellationException("ユーザーが動画の変換を中止しました")
                val metadata = Properties().apply {
                    setProperty("fps", fps.toString())
                    setProperty("frames", frameCount.toString())
                    setProperty("ai", ai.toString())
                    setProperty("start_ms", startMs.toString())
                    setProperty("duration_ms", totalMs.toString())
                }
                FileOutputStream(File(staging, "video.properties")).use { metadata.store(it, "DepthWorld video") }
                check(staging.renameTo(destination)) { "動画の保存に失敗しました" }
                main.post { onDone(Result.success(id)) }
            } catch (error: Exception) {
                if (staging.exists()) staging.deleteRecursively()
                main.post { onDone(Result.failure(error)) }
            } finally {
                segmenter?.close()
                retriever.release()
            }
        }
        return cancelled
    }

    private fun scaleFrame(bitmap: Bitmap): Bitmap {
        val scale = min(1f, min(720f / bitmap.width, 960f / bitmap.height))
        if (scale >= 1f) return bitmap
        val result = Bitmap.createScaledBitmap(bitmap,
            max(1, (bitmap.width * scale).toInt()),
            max(1, (bitmap.height * scale).toInt()), true)
        if (result !== bitmap) bitmap.recycle()
        return result
    }

    private fun writeBitmap(bitmap: Bitmap, destination: File,
                            format: Bitmap.CompressFormat, quality: Int) {
        FileOutputStream(destination).use { output ->
            check(bitmap.compress(format, quality, output)) { "フレームを保存できません" }
        }
    }

    /** Keep stable edges quiet while letting genuinely moving edges change promptly. */
    private fun stabilizeMask(mask: FloatBuffer, count: Int, previous: FloatArray?): FloatArray {
        require(mask.capacity() >= count) { "AIマスクのサイズが一致しません" }
        val output = FloatArray(count)
        for (i in 0 until count) {
            val sampled = mask.get(i)
            val current = if (sampled.isFinite()) sampled.coerceIn(0f, 1f) else 0f
            output[i] = if (previous != null && previous.size == count) {
                val prior = previous[i]
                val persistence = 0.22f * (1f - abs(current - prior) * 3f).coerceIn(0f, 1f)
                current * (1f - persistence) + prior * persistence
            } else current
        }
        return output
    }

    fun removeOldVideos(context: Context, keepId: String) {
        // An earlier delayed cleanup must never erase a newly selected video.
        if (WallpaperConfig.preferences(context).getString(WallpaperConfig.VIDEO_ID, null) != keepId) return
        val base = File(context.filesDir, "video_sequences")
        base.listFiles()?.filter {
            it.isDirectory && it.name != keepId &&
                !it.name.endsWith(".preparing") && File(it, "video.properties").isFile
        }
            ?.forEach { it.deleteRecursively() }
    }

    fun removeVideoIfInactive(context: Context, id: String) {
        if (WallpaperConfig.preferences(context).getString(WallpaperConfig.VIDEO_ID, null) == id) return
        directory(context, id).deleteRecursively()
    }
}

/** Async 6-frame cache. Never decodes a video frame on the wallpaper/main thread. */
class VideoFrames(private val directory: File) {
    val info: VideoStore.VideoInfo = VideoStore.readInfo(directory)
    data class Layers(val background: Bitmap, val foreground: Bitmap?)

    private val executor = Executors.newSingleThreadExecutor()
    private val cache = LruCache<Int, Layers>(6)
    private val pending = mutableSetOf<Int>()
    @Volatile private var closed = false
    private var lastFrame: Layers? = null

    fun frame(index: Int, reverse: Boolean = false): Layers? {
        if (closed) return null
        val frameIndex = ((index % info.frames) + info.frames) % info.frames
        val ready = cache.get(frameIndex)
        if (ready != null) lastFrame = ready
        loadAsync(frameIndex)
        val step = if (reverse) -1 else 1
        loadAsync((frameIndex + step + info.frames) % info.frames)
        loadAsync((frameIndex + 2 * step + 2 * info.frames) % info.frames)
        return ready ?: lastFrame
    }

    private fun loadAsync(index: Int) {
        if (closed || cache.get(index) != null) return
        synchronized(pending) { if (!pending.add(index)) return }
        executor.execute {
            try {
                if (closed) return@execute
                val prefix = index.toString().padStart(4, '0')
                val bg = BitmapFactory.decodeFile(File(directory, "bg_$prefix.jpg").path,
                    BitmapFactory.Options().apply { inPreferredConfig = Bitmap.Config.RGB_565 })
                    ?: return@execute
                val fg = if (info.ai) BitmapFactory.decodeFile(File(directory, "fg_$prefix.png").path)
                    else null
                if (closed) {
                    bg.recycle()
                    fg?.recycle()
                } else {
                    cache.put(index, Layers(bg, fg))
                }
            } finally {
                synchronized(pending) { pending.remove(index) }
            }
        }
    }

    fun close() {
        closed = true
        executor.shutdownNow()
        cache.evictAll()
        lastFrame = null
    }
}
