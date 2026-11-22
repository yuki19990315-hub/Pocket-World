"""Dependency-free structural checks. Does NOT replace Android compile/device tests."""

from pathlib import Path
import struct
import hashlib
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app/src/main"

required = [
    ROOT / "gradlew",
    ROOT / "gradlew.bat",
    ROOT / "gradle/wrapper/gradle-wrapper.jar",
    ROOT / "gradle/wrapper/gradle-wrapper.properties",
    ROOT / "settings.gradle",
    ROOT / "build.gradle",
    ROOT / "app/build.gradle",
    APP / "AndroidManifest.xml",
    APP / "res/xml/wallpaper.xml",
    *(
        APP / "java/com/depthworld/wallpaper" / name
        for name in (
            "MainActivity.kt",
            "WallpaperConfig.kt",
            "ImageStore.kt",
            "ParallaxWallpaperService.kt",
            "AutoCutout.kt",
            "LightEffects.kt",
            "VideoStore.kt",
        )
    ),
]
for path in required:
    assert path.is_file(), f"missing {path}"

manifest = ET.parse(APP / "AndroidManifest.xml").getroot()
wallpaper = ET.parse(APP / "res/xml/wallpaper.xml").getroot()
assert manifest.tag == "manifest"
assert wallpaper.tag == "wallpaper"
android_ns = "{http://schemas.android.com/apk/res/android}"
service = manifest.find("application/service")
assert service is not None
assert service.attrib[android_ns + "permission"] == "android.permission.BIND_WALLPAPER"
assert service.attrib[android_ns + "exported"] == "true"
assert not manifest.findall("uses-permission"), "unexpected Android permission requested"
dependencies = (ROOT / "app/build.gradle").read_text()
assert "play-services-mlkit-subject-segmentation:16.0.0-beta1" in dependencies
assert "versionName '0.4.1'" in dependencies

wrapper_jar = ROOT / "gradle/wrapper/gradle-wrapper.jar"
wrapper_sha = hashlib.sha256(wrapper_jar.read_bytes()).hexdigest()
assert wrapper_sha == "7d3a4ac4de1c32b59bc6a4eb8ecb8e612ccd0cf1ae1e99f66902da64df296172", "Gradle wrapper JAR checksum mismatch"
wrapper_properties = (ROOT / "gradle/wrapper/gradle-wrapper.properties").read_text()
assert "gradle-8.11.1-bin.zip" in wrapper_properties
assert "distributionSha256Sum=f397b287023acdba1e9f6fc5ea72d22dd63669d59ed4a289a29b1a76eee151c6" in wrapper_properties
assert any(node.attrib.get(android_ns + "name") == "com.google.mlkit.vision.DEPENDENCIES"
           for node in manifest.findall("application/meta-data"))

drawables = APP / "res/drawable-nodpi"
for name in ("fantasy_bg.png", "fantasy_island.png", "pocket_island.png"):
    path = drawables / name
    with path.open("rb") as f:
        header = f.read(26)
    assert header[:8] == b"\x89PNG\r\n\x1a\n", f"not a PNG: {name}"
    width, height = struct.unpack(">II", header[16:24])
    assert width >= 800 and height >= 800, f"image is too small: {name}"
    if name != "fantasy_bg.png":
        assert header[25] == 6, f"foreground lacks RGBA alpha: {name}"

world = APP / "assets/pocketworld"
for name in ("hybrid", "nature", "fantasy", "forest", "river", "city", "aquarium", "deepsea"):
    for stage in ("young", "mature"):
        assert (world / f"{name}-{stage}.png").is_file(), f"missing {name}-{stage}"

code_dir = APP / "java/com/depthworld/wallpaper"
activity_code = (code_dir / "MainActivity.kt").read_text()
engine_code = (code_dir / "ParallaxWallpaperService.kt").read_text()
video_code = (code_dir / "VideoStore.kt").read_text()
assert 'type = if (layer == "video" || layer == "video_ai") "video/*"' in activity_code
assert "WallpaperConfig.VIDEO -> drawVideo" in engine_code
assert "LightEffects.behind" in engine_code and "LightEffects.inFront" in engine_code
assert "onVisibilityChanged(visible: Boolean)" in engine_code
assert "enableForegroundConfidenceMask()" in video_code
assert "stabilizeMask" in video_code and "createForeground" in video_code
assert "MediaMetadataRetriever" in video_code
assert "MAX_NORMAL_MS = 8_000L" in video_code and "MAX_AI_MS = 6_000L" in video_code
assert "NORMAL_FPS = 20" in video_code and "AI_FPS = 10" in video_code
assert "cancelled.get()" in video_code
assert 'setProperty("start_ms", startMs.toString())' in video_code
assert "WallpaperConfig.VIDEO_START" in activity_code
assert "WallpaperConfig.VIDEO_LENGTH" in activity_code
assert "WallpaperConfig.VIDEO_SPEED" in activity_code
assert "WallpaperConfig.VIDEO_PINGPONG" in activity_code
assert "WallpaperConfig.VIDEO_ZOOM" in activity_code
assert "WallpaperConfig.VIDEO_OFFSET_X" in activity_code
assert "WallpaperConfig.VIDEO_OFFSET_Y" in activity_code
assert "VideoStore.removeVideoIfInactive" in activity_code
assert "power.isPowerSaveMode" in engine_code
assert "WallpaperConfig.TILT_ENABLED" in engine_code

print("OK: XML, Gradle wrapper/checksums, video controls/AI mask smoothing, battery handling, source files, PNG assets, 16 PocketWorld scenes, no permissions")
print("NOTE: Android SDK compile, APK installation, orientation and battery testing remain unverified")
