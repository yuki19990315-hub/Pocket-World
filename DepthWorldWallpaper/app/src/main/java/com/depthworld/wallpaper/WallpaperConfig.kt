package com.depthworld.wallpaper

import android.content.Context
import android.content.SharedPreferences

object WallpaperConfig {
    const val MODE = "mode"
    const val INTENSITY = "intensity"
    const val GLOW = "glow"
    const val FPS = "fps"
    const val WORLD = "world"
    const val STAGE = "stage"
    const val TOUCH = "touch"
    const val LIGHT_PRESET = "light_preset"
    const val RECENTER = "recenter"
    const val RELOAD_IMAGES = "reload_images"
    const val AUTO_ALIGNED = "auto_aligned"
    const val VIDEO_ID = "video_id"
    const val VIDEO_START = "video_start_seconds"
    const val VIDEO_LENGTH = "video_length_seconds"
    const val VIDEO_SPEED = "video_speed_percent"
    const val VIDEO_PINGPONG = "video_pingpong"
    const val VIDEO_ZOOM = "video_zoom_percent"
    const val VIDEO_OFFSET_X = "video_offset_x_percent"
    const val VIDEO_OFFSET_Y = "video_offset_y_percent"
    const val TILT_ENABLED = "tilt_enabled"
    const val CYBER_STYLE = "cyber_style"
    const val CYBER_TILES = "cyber_tiles"

    const val CYBER = "cyber"
    const val FANTASY = "fantasy"
    const val POCKET = "pocket"
    const val CUSTOM = "custom"
    const val VIDEO = "video"

    val worldIds = arrayOf("hybrid", "nature", "fantasy", "forest", "river", "city", "aquarium", "deepsea")
    val worldNames = arrayOf("自然＋文明（浮遊島）", "自然", "ファンタジー", "森", "川と水辺", "街", "水槽", "深海")
    val stageNames = arrayOf("成長前", "成熟")
    val lightNames = arrayOf("光なし", "柔らかな光", "きらめく星くず", "木漏れ日", "ネオン", "夕焼けの逆光", "水面の反射")
    val cyberStyleNames = arrayOf("サイバー回路／琥珀×紫", "オーロラガラス／青×紫", "ホログラム／緑×水色")

    fun preferences(context: Context): SharedPreferences = context.getSharedPreferences("depthworld", Context.MODE_PRIVATE)
    fun intensity(prefs: SharedPreferences) = (prefs.getInt(INTENSITY, 100) / 100f).coerceIn(0.5f, 2f)
    fun glow(prefs: SharedPreferences) = (prefs.getInt(GLOW, 85) / 100f).coerceIn(0f, 1f)
    fun fps(prefs: SharedPreferences) = if (prefs.getInt(FPS, 60) == 30) 30 else 60
    fun mode(prefs: SharedPreferences) = prefs.getString(MODE, CYBER) ?: CYBER
    fun cyberStyle(prefs: SharedPreferences) = prefs.getInt(CYBER_STYLE, 0).coerceIn(0, cyberStyleNames.lastIndex)
    fun cyberTiles(prefs: SharedPreferences) = prefs.getBoolean(CYBER_TILES, true)
    fun world(prefs: SharedPreferences) = prefs.getInt(WORLD, 0).coerceIn(0, worldIds.lastIndex)
    fun stage(prefs: SharedPreferences) = prefs.getInt(STAGE, 1).coerceIn(0, 1)
    fun lightPreset(prefs: SharedPreferences) = prefs.getInt(LIGHT_PRESET, 1).coerceIn(0, lightNames.lastIndex)
    fun videoStart(prefs: SharedPreferences) = prefs.getInt(VIDEO_START, 0).coerceIn(0, 60)
    fun videoLength(prefs: SharedPreferences) = prefs.getInt(VIDEO_LENGTH, 8).coerceIn(2, 8)
    fun videoSpeed(prefs: SharedPreferences) = prefs.getInt(VIDEO_SPEED, 100).coerceIn(50, 150) / 100f
    fun videoZoom(prefs: SharedPreferences) = prefs.getInt(VIDEO_ZOOM, 133).coerceIn(100, 160) / 100f
    fun videoOffsetX(prefs: SharedPreferences) = prefs.getInt(VIDEO_OFFSET_X, 0).coerceIn(-50, 50) / 100f
    fun videoOffsetY(prefs: SharedPreferences) = prefs.getInt(VIDEO_OFFSET_Y, 0).coerceIn(-50, 50) / 100f
}
