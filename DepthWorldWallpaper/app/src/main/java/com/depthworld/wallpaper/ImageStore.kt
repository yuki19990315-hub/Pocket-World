package com.depthworld.wallpaper

import android.content.Context
import android.graphics.BitmapFactory
import android.net.Uri
import java.io.File
import java.io.FileOutputStream

/** Copies picker content privately; no storage permission or persistable URI is required. */
object ImageStore {
    private val layers = setOf("background", "glow", "foreground")
    fun file(context: Context, layer: String): File {
        require(layer in layers)
        return File(File(context.filesDir, "custom_layers"), "$layer.image")
    }

    fun importImage(context: Context, uri: Uri, layer: String) {
        val destination = file(context, layer)
        destination.parentFile?.mkdirs()
        val temporary = File(destination.parentFile, "${layer}.incoming")
        try {
            context.contentResolver.openInputStream(uri)?.use { input ->
                FileOutputStream(temporary).use { output ->
                    val buffer = ByteArray(32 * 1024)
                    var length = 0L
                    while (true) {
                        val read = input.read(buffer)
                        if (read < 0) break
                        length += read
                        require(length <= 24L * 1024 * 1024) { "24MB以下の画像を選んでください" }
                        output.write(buffer, 0, read)
                    }
                }
            } ?: error("画像を開けません")
            val options = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeFile(temporary.path, options)
            require(options.outWidth > 0 && options.outHeight > 0) { "画像形式が不正です" }
            require(temporary.renameTo(destination)) { "画像を保存できませんでした" }
        } finally {
            if (temporary.exists()) temporary.delete()
        }
    }
}
