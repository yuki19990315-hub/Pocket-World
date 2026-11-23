package com.depthworld.wallpaper

import android.app.Activity
import android.app.AlertDialog
import android.app.WallpaperManager
import android.content.ComponentName
import android.content.Intent
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.View
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.SeekBar
import android.widget.Spinner
import android.widget.Switch
import android.widget.TextView
import android.widget.Toast
import java.io.File
import java.util.concurrent.atomic.AtomicBoolean

/** No third-party UI or image-picker libraries are needed. */
class MainActivity : Activity() {
    private val prefs by lazy { WallpaperConfig.preferences(this) }
    private var pendingLayer: String? = null
    private var activeVideoImport: AtomicBoolean? = null
    private val navy = Color.rgb(8, 15, 37)
    private val cardColor = Color.rgb(20, 33, 60)
    private val accent = Color.rgb(118, 226, 221)
    private val muted = Color.rgb(162, 178, 205)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        pendingLayer = savedInstanceState?.getString("pending")
        render()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putString("pending", pendingLayer)
        super.onSaveInstanceState(outState)
    }

    override fun onDestroy() {
        // Prevent an import callback from writing to a destroyed Activity after rotation.
        activeVideoImport?.set(true)
        super.onDestroy()
    }

    private fun dp(value: Int) = (resources.displayMetrics.density * value + .5f).toInt()

    private fun rounded(color: Int, stroke: Int? = null): GradientDrawable {
        return GradientDrawable().apply {
            setColor(color)
            cornerRadius = dp(16).toFloat()
            stroke?.let { setStroke(dp(1), it) }
        }
    }

    private fun title(text: String, size: Float, color: Int = Color.WHITE): TextView {
        return TextView(this).apply {
            this.text = text
            textSize = size
            setTextColor(color)
            includeFontPadding = true
        }
    }

    private fun button(label: String, selected: Boolean = false, action: () -> Unit): Button {
        return Button(this).apply {
            text = label
            isAllCaps = false
            textSize = 14f
            setTextColor(if (selected) navy else Color.WHITE)
            background = rounded(if (selected) accent else Color.rgb(40, 57, 90))
            setPadding(dp(8), dp(7), dp(8), dp(7))
            setOnClickListener { action() }
        }
    }

    private fun section(root: LinearLayout, name: String): LinearLayout {
        val column = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(17), dp(16), dp(18))
            background = rounded(cardColor, Color.rgb(45, 64, 100))
        }
        column.addView(title(name, 18f))
        val margin = LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(14) }
        root.addView(column, margin)
        return column
    }

    private fun info(parent: LinearLayout, content: String) {
        parent.addView(title(content, 13f, muted), LinearLayout.LayoutParams(-1, -2).apply {
            topMargin = dp(8)
        })
    }

    private fun render() {
        val scroll = ScrollView(this).apply {
            setBackgroundColor(navy)
            isFillViewport = true
            clipToPadding = false
        }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(18), dp(28), dp(18), dp(30))
        }
        scroll.addView(root)
        setContentView(scroll)

        root.addView(title("DEPTHWORLD", 29f, accent))
        root.addView(title("ネオン・写真・動画から立体壁紙を作ろう", 15f, muted))

        val picker = section(root, "壁紙の世界")
        val mode = WallpaperConfig.mode(prefs)
        val names = listOf("ネオン3D" to WallpaperConfig.CYBER,
            "写真・イラスト" to WallpaperConfig.CUSTOM,
            "幻想世界" to WallpaperConfig.FANTASY,
            "PocketWorld" to WallpaperConfig.POCKET,
            "動画・AI動画" to WallpaperConfig.VIDEO)
        names.chunked(2).forEach { pair ->
            val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
            pair.forEach { (label, id) ->
                row.addView(button(label, mode == id) {
                    prefs.edit().putString(WallpaperConfig.MODE, id).apply()
                    render()
                }, LinearLayout.LayoutParams(0, dp(49), 1f).apply { marginEnd = dp(4) })
            }
            picker.addView(row, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(7) })
        }

        when (mode) {
            WallpaperConfig.CYBER -> cyberSection(root)
            WallpaperConfig.CUSTOM -> customSection(root)
            WallpaperConfig.VIDEO -> videoSection(root)
            WallpaperConfig.POCKET -> pocketSection(root)
            else -> fantasySection(root)
        }

        val settings = section(root, "動きと光")
        addSlider(settings, "奥行きの強さ", WallpaperConfig.INTENSITY, 50, 200, 100) { "${it / 100f}倍" }
        addSlider(settings, "光の強さ", WallpaperConfig.GLOW, 0, 100, 85) { "$it%" }
        val switch = Switch(this).apply {
            text = "60fps（OFFで省電力の30fps）"
            setTextColor(Color.WHITE)
            textSize = 14f
            isChecked = WallpaperConfig.fps(prefs) == 60
            setOnCheckedChangeListener { _, checked ->
                prefs.edit().putInt(WallpaperConfig.FPS, if (checked) 60 else 30).apply()
            }
        }
        settings.addView(switch, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12) })

        val touch = Switch(this).apply {
            text = "タッチ操作でも奥行きを動かす"
            setTextColor(Color.WHITE)
            textSize = 14f
            isChecked = prefs.getBoolean(WallpaperConfig.TOUCH, true)
            setOnCheckedChangeListener { _, checked ->
                prefs.edit().putBoolean(WallpaperConfig.TOUCH, checked).apply()
            }
        }
        settings.addView(touch)
        val tilt = Switch(this).apply {
            text = "傾きセンサーを使う（OFFでセンサー省電力）"
            setTextColor(Color.WHITE)
            textSize = 14f
            isChecked = prefs.getBoolean(WallpaperConfig.TILT_ENABLED, true)
            setOnCheckedChangeListener { _, checked ->
                prefs.edit().putBoolean(WallpaperConfig.TILT_ENABLED, checked).apply()
            }
        }
        settings.addView(tilt)
        val reverseHorizontal = Switch(this).apply {
            text = "左右の傾きを反転する（標準でON）"
            setTextColor(Color.WHITE)
            textSize = 14f
            isChecked = WallpaperConfig.invertTiltX(prefs)
            setOnCheckedChangeListener { _, checked ->
                prefs.edit().putBoolean(WallpaperConfig.INVERT_TILT_X, checked).apply()
            }
        }
        settings.addView(reverseHorizontal)
        settings.addView(button("傾きの中心をリセット") {
            prefs.edit().putInt(WallpaperConfig.RECENTER, prefs.getInt(WallpaperConfig.RECENTER, 0) + 1).apply()
            Toast.makeText(this, "次のセンサー入力を中心位置にします", Toast.LENGTH_SHORT).show()
        }, LinearLayout.LayoutParams(-1, dp(44)).apply { topMargin = dp(10) })

        root.addView(button("壁紙をプレビューして設定", selected = true) { previewWallpaper() },
            LinearLayout.LayoutParams(-1, dp(56)).apply { topMargin = dp(20) })
        info(root, "写真・動画は端末内で処理。アカウント・広告なし。画面外ではセンサーと描画を停止します。")
        info(root, "※ AI切り抜きは端末内処理。初回のみGoogle Play開発者サービスからAIモデルの取得が必要です。")
    }

    private fun fantasySection(root: LinearLayout) {
        val box = section(root, "星空の浮遊島")
        info(box, "オリジナルの夜空と魔法の浮遊島。発光・影・傾きによる視差を重ねて表示します。")
        val preview = ImageView(this).apply {
            setImageResource(R.drawable.fantasy_bg)
            scaleType = ImageView.ScaleType.CENTER_CROP
            background = rounded(Color.BLACK)
        }
        box.addView(preview, LinearLayout.LayoutParams(-1, dp(145)).apply { topMargin = dp(12) })
    }

    private fun cyberSection(root: LinearLayout) {
        val box = section(root, "3Dネオン・サーキット")
        info(box, "動画の透明な電子回路とガラス風の奥行きを参考にした、オリジナルのライブ壁紙。回路・フレーム・タイルが傾きで別々に動きます。")
        box.addView(title("デザインを選ぶ", 14f, accent),
            LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(14) })
        val styles = Spinner(this)
        styles.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item,
            WallpaperConfig.cyberStyleNames)
        styles.setSelection(WallpaperConfig.cyberStyle(prefs))
        styles.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                prefs.edit().putInt(WallpaperConfig.CYBER_STYLE, position).apply()
            }
        }
        box.addView(styles)
        box.addView(Switch(this).apply {
            text = "ガラス風のネオンタイルを表示"
            setTextColor(Color.WHITE)
            textSize = 14f
            isChecked = WallpaperConfig.cyberTiles(prefs)
            setOnCheckedChangeListener { _, checked ->
                prefs.edit().putBoolean(WallpaperConfig.CYBER_TILES, checked).apply()
            }
        }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(14) })
        info(box, "タイルは壁紙の装飾です。実際のアプリアイコンは別に表示されます。通常のアイコンと重なる場合はタイルをOFFにしてください。")
        box.addView(Switch(this).apply {
            text = "時刻で配色を変える（昼・夕方・夜）"
            setTextColor(Color.WHITE)
            textSize = 14f
            isChecked = WallpaperConfig.cyberTimeColors(prefs)
            setOnCheckedChangeListener { _, checked ->
                prefs.edit().putBoolean(WallpaperConfig.CYBER_TIME_COLORS, checked).apply()
            }
        }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12) })
        info(box, "ONのときはスマホの現在時刻に応じて配色が決まります。手動のデザイン選択はOFF時に使われます。")
        box.addView(Switch(this).apply {
            text = "実際のバッテリー残量をHUDに表示"
            setTextColor(Color.WHITE)
            textSize = 14f
            isChecked = WallpaperConfig.cyberBattery(prefs)
            setOnCheckedChangeListener { _, checked ->
                prefs.edit().putBoolean(WallpaperConfig.CYBER_BATTERY, checked).apply()
            }
        }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12) })
        box.addView(Switch(this).apply {
            text = "タップでネオンの波紋を出す"
            setTextColor(Color.WHITE)
            textSize = 14f
            isChecked = WallpaperConfig.cyberRipples(prefs)
            setOnCheckedChangeListener { _, checked ->
                prefs.edit().putBoolean(WallpaperConfig.CYBER_RIPPLES, checked).apply()
            }
        }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(12) })
        info(box, "プレビューではタップ操作を試せます。壁紙にした後のタッチ反応はホームアプリが壁紙へタッチを渡す場合に限ります。")
        val preview = CyberPreviewView(this)
        box.addView(preview, LinearLayout.LayoutParams(dp(204), dp(453)).apply {
            gravity = Gravity.CENTER_HORIZONTAL
            topMargin = dp(17)
        })
        info(box, "上のプレビューを指で動かすと、3Dパララックスを試せます。")
        info(box, "今後のホーム画面テーマ機能では、アイコンをタップして実際にアプリを開く機能も追加予定です。この壁紙版だけではアプリアイコンを置き換えません。")
    }

    private fun pocketSection(root: LinearLayout) {
        val box = section(root, "PocketWorldを壁紙に")
        info(box, "既存のPocket-World画像を同梱。自然＋文明では浮遊島、ほかの世界ではオリジナルのドット絵を表示します。")
        box.addView(title("世界", 14f, accent), LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(14) })
        val worldPicker = Spinner(this)
        worldPicker.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, WallpaperConfig.worldNames)
        worldPicker.setSelection(WallpaperConfig.world(prefs))
        worldPicker.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                prefs.edit().putInt(WallpaperConfig.WORLD, position).apply()
            }
        }
        box.addView(worldPicker)
        box.addView(title("成長段階", 14f, accent), LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(8) })
        val stagePicker = Spinner(this)
        stagePicker.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, WallpaperConfig.stageNames)
        stagePicker.setSelection(WallpaperConfig.stage(prefs))
        stagePicker.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                prefs.edit().putInt(WallpaperConfig.STAGE, position).apply()
            }
        }
        box.addView(stagePicker)
        info(box, "壁紙版の成長段階は手動切替です。ESP32本体の進行日数との同期はまだ行いません。")
    }

    private fun customSection(root: LinearLayout) {
        val box = section(root, "自分の画像で立体化")
        info(box, "写真1枚からAIが主役を切り抜いて、背景と前景の2層を自動作成します。背景の隠れた部分は簡易補完です。")
        box.addView(button("✦ 写真1枚をAIで3D化する", selected = true) { pickLayer("auto") },
            LinearLayout.LayoutParams(-1, dp(56)).apply { topMargin = dp(15) })
        addSlider(box, "切り抜き輪郭の滑らかさ", WallpaperConfig.CUTOUT_SMOOTHNESS,
            0, 100, 85) { "$it%" }
        info(box, "数値を上げるほど輪郭のギザギザを滑らかにします。変更は次にAIで切り抜く写真・動画から適用されます。")
        info(box, "人物・ペット・物が対象。輪郭は色の境界を見ながらなめらかに補正します。以前に加工した写真は、同じ写真をもう一度選ぶと改善処理が適用されます。")
        addLightPicker(box)
        info(box, "光の強さは下のスライダーで変更できます。")
        box.addView(title("手動で3枚の画像を調整", 14f, accent),
            LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(16) })
        listOf(
            Triple("background", "① 背景画像を選ぶ", "画面全体の写真やイラスト"),
            Triple("glow", "② 光の画像を選ぶ（任意）", "透過PNGの発光・粒子・光芒"),
            Triple("foreground", "③ 前景画像を選ぶ（任意）", "被写体を切り抜いた透過PNG")
        ).forEach { (key, label, help) ->
            val file = ImageStore.file(this, key)
            box.addView(button("$label ${if (file.exists()) "✓" else ""}") { pickLayer(key) },
                LinearLayout.LayoutParams(-1, dp(48)).apply { topMargin = dp(12) })
            info(box, help)
        }
        box.addView(button("画像を変更したら壁紙へ反映") { previewWallpaper() },
            LinearLayout.LayoutParams(-1, dp(46)).apply { topMargin = dp(14) })
    }

    private fun videoSection(root: LinearLayout) {
        val box = section(root, "動画からライブ壁紙を作る")
        info(box, "動画を選ぶと端末内でフレームに変換し、無音ループ＋傾き＋光エフェクトで再生します。")
        box.addView(title("動画の取り込み範囲", 14f, accent), LinearLayout.LayoutParams(-1, -2).apply {
            topMargin = dp(14)
        })
        addSlider(box, "開始位置", WallpaperConfig.VIDEO_START, 0, 60, 0) { "${it}秒" }
        addSlider(box, "使用する長さ", WallpaperConfig.VIDEO_LENGTH, 2, 8, 8) { "${it}秒" }
        info(box, "開始位置が動画より後なら、末尾付近に調整します。AIモードの最大長は6秒。上の設定は次に取り込む動画から適用されます。")
        box.addView(button("▶ 動画＋光でライブ壁紙にする", selected = true) { pickLayer("video") },
            LinearLayout.LayoutParams(-1, dp(56)).apply { topMargin = dp(14) })
        info(box, "標準モード：指定位置から最大8秒・20fps。背景がわずかに傾きで動きます。")
        box.addView(button("✦ 動画をAIで前景・背景に分ける") { pickLayer("video_ai") },
            LinearLayout.LayoutParams(-1, dp(56)).apply { topMargin = dp(14) })
        info(box, "AIモード：最大6秒・10fps。輪郭を色に合わせて補正し、動きの大きい部分では残像を抑えながら前景を逆方向に動かします。以前の加工動画は再度取り込んでください。")
        addSlider(box, "切り抜き輪郭の滑らかさ", WallpaperConfig.CUTOUT_SMOOTHNESS,
            0, 100, 85) { "$it%" }
        val id = prefs.getString(WallpaperConfig.VIDEO_ID, null)
        if (id != null) {
            try {
                val dir = VideoStore.directory(this, id)
                val details = VideoStore.readInfo(dir)
                info(box, "設定済み：${if (details.ai) "AI 3D動画" else "通常動画"}／${details.frames}フレーム／${details.fps}fps／開始${details.startMs / 1000f}秒")
                val storageBytes = dir.listFiles()?.sumOf { it.length() } ?: 0L
                info(box, "内部保存容量：約${(storageBytes + 524_287L) / 1_048_576L}MB（元動画はそのまま）")
                val thumb = File(dir, "bg_0000.jpg")
                if (thumb.isFile) {
                    val bitmap = BitmapFactory.decodeFile(thumb.path,
                        BitmapFactory.Options().apply { inSampleSize = 2 })
                    if (bitmap != null) {
                        val preview = FrameLayout(this).apply { background = rounded(Color.BLACK) }
                        preview.addView(ImageView(this).apply {
                            setImageBitmap(bitmap)
                            scaleType = ImageView.ScaleType.CENTER_CROP
                            contentDescription = "取り込み済み動画の最初のフレーム"
                        }, FrameLayout.LayoutParams(-1, -1))
                        if (details.ai) {
                            val fg = File(dir, "fg_0000.png")
                            if (fg.isFile) {
                                BitmapFactory.decodeFile(fg.path,
                                    BitmapFactory.Options().apply { inSampleSize = 2 })?.let { foreground ->
                                    preview.addView(ImageView(this).apply {
                                        setImageBitmap(foreground)
                                        scaleType = ImageView.ScaleType.CENTER_CROP
                                        contentDescription = "AIで切り抜いた前景"
                                    }, FrameLayout.LayoutParams(-1, -1))
                                }
                            }
                        }
                        box.addView(preview, LinearLayout.LayoutParams(-1, dp(145)).apply { topMargin = dp(12) })
                    }
                }
                box.addView(button("保存した加工動画を削除") {
                    AlertDialog.Builder(this)
                        .setTitle("加工動画を削除しますか？")
                        .setMessage("DepthWorld内で作成したフレームのみを削除します。元のスマホ内動画は削除されません。")
                        .setNegativeButton("キャンセル", null)
                        .setPositiveButton("削除") { _, _ ->
                            prefs.edit().remove(WallpaperConfig.VIDEO_ID)
                                .putString(WallpaperConfig.MODE, WallpaperConfig.FANTASY).apply()
                            render()
                            Handler(Looper.getMainLooper()).postDelayed({
                                Thread { VideoStore.removeVideoIfInactive(applicationContext, id) }.start()
                            }, 10_000L)
                        }.show()
                }, LinearLayout.LayoutParams(-1, dp(44)).apply { topMargin = dp(12) })
            } catch (_: Exception) {
                info(box, "保存動画を読み込めません。もう一度選択してください。")
            }
        }
        box.addView(title("再生の調整", 14f, accent), LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(14) })
        addSlider(box, "再生速度", WallpaperConfig.VIDEO_SPEED, 50, 150, 100) { "${it / 100f}倍" }
        addSlider(box, "動画の拡大率", WallpaperConfig.VIDEO_ZOOM, 100, 160, 133) { "$it%" }
        addSlider(box, "横方向の位置", WallpaperConfig.VIDEO_OFFSET_X, -50, 50, 0) { "$it%" }
        addSlider(box, "縦方向の位置", WallpaperConfig.VIDEO_OFFSET_Y, -50, 50, 0) { "$it%" }
        box.addView(Switch(this).apply {
            text = "往復ループ（最後まで再生したら逆再生）"
            setTextColor(Color.WHITE)
            textSize = 14f
            isChecked = prefs.getBoolean(WallpaperConfig.VIDEO_PINGPONG, false)
            setOnCheckedChangeListener { _, checked ->
                prefs.edit().putBoolean(WallpaperConfig.VIDEO_PINGPONG, checked).apply()
            }
        }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(10) })
        addLightPicker(box)
        info(box, "光は動画と独立して動きます。画面外で描画は停止します。")
        info(box, "※ この版は短いクリップを事前変換する試作です。元動画そのものの30/60fps再生ではありません。AI切り抜き輪郭・背景補完にはちらつきや残像が出る場合があります。")
    }

    private fun addLightPicker(box: LinearLayout) {
        box.addView(title("光のパターン", 14f, accent), LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(16) })
        val lights = Spinner(this)
        lights.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, WallpaperConfig.lightNames)
        lights.setSelection(WallpaperConfig.lightPreset(prefs))
        lights.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                prefs.edit().putInt(WallpaperConfig.LIGHT_PRESET, position).apply()
            }
        }
        box.addView(lights)
    }

    private fun addSlider(parent: LinearLayout, label: String, key: String,
                          min: Int, max: Int, initial: Int, valueLabel: (Int) -> String) {
        val current = prefs.getInt(key, initial).coerceIn(min, max)
        val header = title("$label　${valueLabel(current)}", 14f)
        parent.addView(header, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(14) })
        parent.addView(SeekBar(this).apply {
            this.max = max - min
            progress = current - min
            setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
                override fun onStartTrackingTouch(seekBar: SeekBar?) = Unit
                override fun onStopTrackingTouch(seekBar: SeekBar?) = Unit
                override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                    val value = min + progress
                    header.text = "$label　${valueLabel(value)}"
                    if (fromUser) prefs.edit().putInt(key, value).apply()
                }
            })
        })
    }

    private fun pickLayer(layer: String) {
        pendingLayer = layer
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = if (layer == "video" || layer == "video_ai") "video/*" else "image/*"
        }
        @Suppress("DEPRECATION")
        startActivityForResult(intent, 410)
    }

    @Deprecated("Uses the platform document picker without a third-party activity library")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != 410 || resultCode != RESULT_OK) return
        val layer = pendingLayer ?: return
        val uri: Uri = data?.data ?: return
        pendingLayer = null
        if (layer == "video" || layer == "video_ai") {
            val ai = layer == "video_ai"
            var cancelImport: AtomicBoolean? = null
            val dialog = AlertDialog.Builder(this)
                .setTitle(if (ai) "AIで動画を立体化中" else "動画を準備中")
                .setMessage("0% — 他の画面へ移らずお待ちください")
                .setNegativeButton("中止") { _, _ -> cancelImport?.set(true) }
                .setCancelable(false)
                .create()
            dialog.show()
            cancelImport = VideoStore.prepare(this, uri, ai,
                WallpaperConfig.videoStart(prefs), WallpaperConfig.videoLength(prefs),
                { percent, message ->
                if (!isDestroyed && dialog.isShowing) {
                    dialog.setMessage("$message $percent% — 端末内で処理中です")
                }
            }) { result ->
                activeVideoImport = null
                if (isDestroyed) {
                    result.getOrNull()?.let { id ->
                        Thread { VideoStore.removeVideoIfInactive(applicationContext, id) }.start()
                    }
                    return@prepare
                }
                dialog.dismiss()
                result.onSuccess { id ->
                    prefs.edit().putString(WallpaperConfig.VIDEO_ID, id)
                        .putString(WallpaperConfig.MODE, WallpaperConfig.VIDEO).apply()
                    Toast.makeText(this, "動画の準備が完了しました。光を選んで壁紙に設定してください", Toast.LENGTH_LONG).show()
                    render()
                    Handler(Looper.getMainLooper()).postDelayed({
                        Thread { VideoStore.removeOldVideos(applicationContext, id) }.start()
                    }, 30_000L)
                }.onFailure { error ->
                    Toast.makeText(this, if (error is java.util.concurrent.CancellationException)
                        "動画の変換を中止しました" else "動画変換に失敗: ${error.message}", Toast.LENGTH_LONG).show()
                }
            }
            activeVideoImport = cancelImport
        } else if (layer == "auto") {
            val dialog = AlertDialog.Builder(this)
                .setTitle("AIで画像を分離中")
                .setMessage("被写体を検出して背景を補完しています。初回はモデルの準備で時間がかかる場合があります。")
                .setCancelable(false)
                .create()
            dialog.show()
            AutoCutout.create(this, uri) { result ->
                dialog.dismiss()
                result.onSuccess {
                    prefs.edit().putString(WallpaperConfig.MODE, WallpaperConfig.CUSTOM)
                        .putBoolean(WallpaperConfig.AUTO_ALIGNED, true)
                        .putInt(WallpaperConfig.RELOAD_IMAGES,
                            prefs.getInt(WallpaperConfig.RELOAD_IMAGES, 0) + 1).apply()
                    Toast.makeText(this, "AI切り抜きが完了しました。光を選んで壁紙に設定できます", Toast.LENGTH_LONG).show()
                    render()
                }.onFailure { e ->
                    Toast.makeText(this, "AI切り抜きに失敗: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        } else {
            try {
                ImageStore.importImage(this, uri, layer)
                val editor = prefs.edit().putInt(WallpaperConfig.RELOAD_IMAGES,
                    prefs.getInt(WallpaperConfig.RELOAD_IMAGES, 0) + 1)
                if (layer == "background" || layer == "foreground") {
                    editor.putBoolean(WallpaperConfig.AUTO_ALIGNED, false)
                }
                editor.apply()
                Toast.makeText(this, "画像を保存しました", Toast.LENGTH_SHORT).show()
                render()
            } catch (e: Exception) {
                Toast.makeText(this, "画像を読み込めません: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun previewWallpaper() {
        val component = ComponentName(this, ParallaxWallpaperService::class.java)
        val request = Intent(WallpaperManager.ACTION_CHANGE_LIVE_WALLPAPER).apply {
            putExtra(WallpaperManager.EXTRA_LIVE_WALLPAPER_COMPONENT, component)
        }
        try {
            startActivity(request)
        } catch (_: Exception) {
            try {
                startActivity(Intent(WallpaperManager.ACTION_LIVE_WALLPAPER_CHOOSER))
            } catch (_: Exception) {
                Toast.makeText(this, "端末の壁紙設定からDepthWorldを選んでください", Toast.LENGTH_LONG).show()
            }
        }
    }
}
