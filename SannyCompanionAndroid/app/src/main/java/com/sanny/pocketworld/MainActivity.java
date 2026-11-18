package com.sanny.pocketworld;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.InputStream;

/** Native companion: observe 4 worlds and update Sanny safely over local Wi-Fi. */
public class MainActivity extends Activity {
    private static final int PICK_FILE = 701;
    private static final int BG = Color.rgb(14, 29, 32);
    private static final int PANEL = Color.rgb(27, 48, 50);
    private static final int ACCENT = Color.rgb(188, 241, 184);
    private static final int MUTED = Color.rgb(160, 181, 174);

    private final String[] tabNames = {"🌍 観察", "⬆ 更新", "⚙ 設定"};
    private TextView[] tabs;
    private FrameLayout pageHost;
    private TextView statusTag;
    private TextView fileLabel;
    private TextView uploadStatus;
    private EditText uploadKey;
    private ProgressBar uploadProgress;
    private WebView viewer;
    private Uri selectedFile;
    private String selectedName;
    private SharedPreferences preferences;
    private int page = 0;

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        preferences = getSharedPreferences("sanny_prefs", MODE_PRIVATE);
        buildChrome();
        showPage(0);
    }

    private int dp(float x) { return Math.round(getResources().getDisplayMetrics().density * x); }

    private GradientDrawable panel(int color, int radius, int stroke) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color); d.setCornerRadius(dp(radius));
        if (stroke != 0) d.setStroke(dp(1), stroke);
        return d;
    }

    private TextView label(String text, int sp, int color, boolean bold) {
        TextView v = new TextView(this);
        v.setText(text); v.setTextSize(sp); v.setTextColor(color);
        if (bold) v.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        v.setGravity(Gravity.CENTER_VERTICAL);
        return v;
    }

    private LinearLayout vertical(int space) {
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL); col.setPadding(dp(space), dp(space), dp(space), dp(space));
        return col;
    }

    private void add(LinearLayout parent, View child, int height, int bottomMargin) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, height < 0 ? height : dp(height));
        params.bottomMargin = dp(bottomMargin);
        parent.addView(child, params);
    }

    private Button action(String text) {
        Button b = new Button(this);
        b.setText(text); b.setTextColor(BG); b.setTextSize(13);
        b.setAllCaps(false); b.setBackground(panel(ACCENT, 13, 0));
        return b;
    }

    private Button secondary(String text) {
        Button b = new Button(this);
        b.setText(text); b.setTextColor(Color.WHITE); b.setTextSize(13);
        b.setAllCaps(false); b.setBackground(panel(Color.rgb(56, 85, 77), 13, Color.rgb(88, 121, 105)));
        return b;
    }

    private void buildChrome() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL); root.setBackgroundColor(BG);
        root.setPadding(dp(16), dp(12), dp(16), dp(10));
        setContentView(root);

        LinearLayout head = new LinearLayout(this);
        head.setOrientation(LinearLayout.HORIZONTAL); head.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout titleCol = new LinearLayout(this);
        titleCol.setOrientation(LinearLayout.VERTICAL);
        TextView title = label("☀ サンニー", 25, ACCENT, true);
        TextView sub = label("SANNY COMPANION  •  POCKET WORLD", 10, MUTED, true);
        titleCol.addView(title); titleCol.addView(sub);
        head.addView(titleCol, new LinearLayout.LayoutParams(0, -2, 1));
        statusTag = label("● 未接続", 11, Color.rgb(244, 210, 148), true);
        statusTag.setPadding(dp(10), dp(7), dp(10), dp(7));
        statusTag.setBackground(panel(Color.rgb(60, 49, 33), 15, 0));
        head.addView(statusTag);
        add(root, head, -2, 18);

        LinearLayout tabRow = new LinearLayout(this);
        tabRow.setOrientation(LinearLayout.HORIZONTAL);
        tabs = new TextView[3];
        for (int i = 0; i < tabs.length; i++) {
            final int index = i;
            TextView t = label(tabNames[i], 13, MUTED, true);
            t.setGravity(Gravity.CENTER);
            t.setPadding(dp(4), dp(12), dp(4), dp(12));
            t.setOnClickListener(v -> showPage(index));
            LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, -2, 1);
            p.setMargins(dp(3), 0, dp(3), 0);
            tabRow.addView(t, p); tabs[i] = t;
        }
        add(root, tabRow, -2, 12);
        pageHost = new FrameLayout(this);
        root.addView(pageHost, new LinearLayout.LayoutParams(-1, 0, 1));
    }

    private void setConnected(boolean connected) {
        statusTag.setText(connected ? "● 接続中" : "● 未接続");
        statusTag.setTextColor(connected ? ACCENT : Color.rgb(244, 210, 148));
        statusTag.setBackground(panel(connected ? Color.rgb(38, 68, 50) : Color.rgb(60, 49, 33), 15, 0));
    }

    private void showPage(int next) {
        page = next;
        WebView previousViewer = viewer;
        viewer = null;
        pageHost.removeAllViews();
        if (previousViewer != null) {
            previousViewer.stopLoading();
            previousViewer.destroy();
        }
        for (int i = 0; i < tabs.length; i++) {
            tabs[i].setTextColor(i == next ? ACCENT : MUTED);
            tabs[i].setBackground(panel(i == next ? Color.rgb(40, 73, 57) : PANEL, 12, i == next ? Color.rgb(106, 155, 107) : 0));
        }
        if (next == 0) showViewer();
        else if (next == 1) showUpdater();
        else showSettings();
    }

    private void preferWifiRoute() {
        ConnectivityManager manager = (ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
        if (manager == null) return;
        for (Network network : manager.getAllNetworks()) {
            NetworkCapabilities capabilities = manager.getNetworkCapabilities(network);
            if (capabilities != null && capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
                manager.bindProcessToNetwork(network);
                return;
            }
        }
        manager.bindProcessToNetwork(null);
    }

    private void showViewer() {
        LinearLayout col = vertical(0);
        pageHost.addView(col, new FrameLayout.LayoutParams(-1, -1));
        TextView description = label("4つの世界を大きな画面で観察。サンニーと同じデータを表示します。", 12, MUTED, false);
        description.setPadding(dp(4), 0, dp(4), dp(10)); add(col, description, -2, 5);

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        Button wifi = secondary("Wi-Fi設定");
        wifi.setOnClickListener(v -> openWifiSettings());
        Button refresh = action("再接続 ↻");
        refresh.setOnClickListener(v -> { preferWifiRoute(); if (viewer != null) viewer.loadUrl(SannyApi.BASE + "/"); });
        actions.addView(wifi, new LinearLayout.LayoutParams(0, dp(42), 1));
        LinearLayout.LayoutParams rp = new LinearLayout.LayoutParams(0, dp(42), 1);
        rp.leftMargin = dp(8); actions.addView(refresh, rp);
        add(col, actions, -2, 10);

        viewer = new WebView(this);
        viewer.setBackgroundColor(PANEL);
        viewer.getSettings().setJavaScriptEnabled(true);
        viewer.getSettings().setDomStorageEnabled(false);
        viewer.getSettings().setAllowFileAccess(false);
        viewer.getSettings().setAllowContentAccess(false);
        viewer.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return !request.getUrl().toString().startsWith(SannyApi.BASE + "/");
            }
            @Override public void onPageFinished(WebView view, String url) {
                if (url.startsWith(SannyApi.BASE)) setConnected(true);
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError error) {
                if (req.isForMainFrame()) {
                    setConnected(false);
                    view.loadDataWithBaseURL(null,
                        "<html><meta name='viewport' content='width=device-width,initial-scale=1'><body style='background:#1b3032;color:#e6f3df;text-align:center;font:16px sans-serif;padding:55px 18px'><h2>☀ サンニーを探しています</h2><p>SANNY-ESP32 のWi-Fiに接続してから『再接続』を押してね。</p></body></html>",
                        "text/html", "UTF-8", null);
                }
            }
        });
        col.addView(viewer, new LinearLayout.LayoutParams(-1, 0, 1));
        preferWifiRoute();
        viewer.loadUrl(SannyApi.BASE + "/");
    }

    private ScrollView scrollingPage() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true); scroll.setClipToPadding(false);
        pageHost.addView(scroll, new FrameLayout.LayoutParams(-1, -1));
        return scroll;
    }

    private void showUpdater() {
        ScrollView scroll = scrollingPage();
        LinearLayout col = vertical(8);scroll.addView(col);
        TextView heading = label("サンニーに無線アップロード", 22, Color.WHITE, true);add(col, heading, -2, 8);
        TextView intro = label("スマホに保存した新しい画像やゲームの更新ファイルを選んで送信します。サンニーのWi-Fiに接続して使ってね。", 13, MUTED, false);
        add(col, intro, -2, 16);

        LinearLayout box = vertical(17);box.setBackground(panel(PANEL, 18, Color.rgb(65, 93, 83)));
        add(col, box, -2, 15);
        add(box, label("① 更新ファイルを選ぶ", 15, Color.WHITE, true), -2, 12);
        fileLabel = label(selectedName == null ? "未選択（128KBまで）" : selectedName, 12, MUTED, false);
        add(box, fileLabel, -2, 12);
        Button picker = secondary("ファイルを選択");picker.setOnClickListener(v -> pickFile());add(box, picker, 46, 16);

        add(box, label("② 管理用キー", 15, Color.WHITE, true), -2, 8);
        uploadKey = new EditText(this);
        uploadKey.setSingleLine(true);
        uploadKey.setText(preferences.getString("admin_key", ""));
        uploadKey.setHint("サンニーの settings.py に設定したキー");
        uploadKey.setHintTextColor(MUTED);uploadKey.setTextColor(Color.WHITE);
        uploadKey.setTextSize(13);
        uploadKey.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        uploadKey.setPadding(dp(13),dp(10),dp(13),dp(10));
        uploadKey.setBackground(panel(Color.rgb(18, 38, 39), 10, Color.rgb(69, 96, 90)));
        add(box, uploadKey, 48, 15);

        Button send = action("③ サンニーへ送信する");send.setOnClickListener(v -> uploadSelected());add(box, send, 48, 12);
        uploadProgress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        uploadProgress.setMax(100);uploadProgress.setProgress(0);add(box, uploadProgress, 9, 10);
        uploadStatus = label("接続待ち", 12, MUTED, false);add(box, uploadStatus, -2, 8);

        TextView note = label("更新できるのは index.html、world_model.py、画像・データ（png / jpg / json / dat）です。main.py・settings.py・ファームウェア全体は安全のため無線上書きできません。", 12, MUTED, false);
        add(col, note, -2, 16);
        Button restart = secondary("サンニーを再起動");
        restart.setOnClickListener(v -> new AlertDialog.Builder(this).setTitle("サンニーを再起動？")
            .setMessage("Pythonプログラムを更新した後は再起動が必要です。")
            .setNegativeButton("戻る", null).setPositiveButton("再起動", (d,w) -> restartBoard()).show());
        add(col, restart, 46, 10);
    }

    private void showSettings() {
        ScrollView scroll = scrollingPage();LinearLayout col = vertical(8);scroll.addView(col);
        add(col, label("接続設定", 23, Color.WHITE, true), -2, 10);
        add(col, label("サンニー本体のアクセスポイントへ接続して使います。インターネットは必要ありません。", 13, MUTED, false), -2, 18);

        LinearLayout box = vertical(17);box.setBackground(panel(PANEL, 18, Color.rgb(65,93,83)));add(col,box,-2,18);
        add(box,label("Wi-Fi名：SANNY-ESP32", 16, ACCENT, true),-2,8);
        add(box,label("本体アドレス：192.168.4.1", 13, Color.WHITE, false),-2,13);
        Button wifi=action("スマホのWi-Fi設定を開く");wifi.setOnClickListener(v->openWifiSettings());add(box,wifi,46,10);
        Button test=secondary("サンニーとの接続を確認");
        test.setOnClickListener(v->checkConnection());add(box,test,46,10);

        LinearLayout safety=vertical(17);safety.setBackground(panel(PANEL,18,Color.rgb(65,93,83)));add(col,safety,-2,16);
        add(safety,label("管理用キーの保存", 16, Color.WHITE, true),-2,9);
        EditText key=new EditText(this);key.setSingleLine(true);
        key.setText(preferences.getString("admin_key", ""));
        key.setTextSize(13);key.setTextColor(Color.WHITE);key.setHintTextColor(MUTED);
        key.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        key.setHint("更新時に使うキー");
        key.setBackground(panel(Color.rgb(18,38,39),10,Color.rgb(69,96,90)));
        key.setPadding(dp(13),dp(10),dp(13),dp(10));add(safety,key,48,10);
        Button save=secondary("この端末に保存");
        save.setOnClickListener(v->{preferences.edit().putString("admin_key",key.getText().toString()).apply();Toast.makeText(this,"保存したよ",Toast.LENGTH_SHORT).show();});
        add(safety,save,46,8);
        add(col,label("通信はサンニーのローカルWi-Fi内で行います。更新キーとWi-Fiパスワードは他人に見せないでね。",12,MUTED,false),-2,6);
    }

    private void openWifiSettings() {
        try {startActivity(new Intent(Settings.ACTION_WIFI_SETTINGS));}
        catch (Exception e) {Toast.makeText(this,"Wi-Fi設定を開けませんでした",Toast.LENGTH_SHORT).show();}
    }

    private void pickFile() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.setType("*/*");intent.addCategory(Intent.CATEGORY_OPENABLE);
        startActivityForResult(intent, PICK_FILE);
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != PICK_FILE || result != RESULT_OK || data == null || data.getData() == null) return;
        Uri uri = data.getData();String displayName = null;
        try (Cursor c = getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)) {
            if (c != null && c.moveToFirst()) displayName = c.getString(0);
        } catch (Exception ignored) { }
        if (SannyApi.uploadName(displayName) == null) {
            Toast.makeText(this,"対応外のファイルです。更新可能な種類を確認してね。",Toast.LENGTH_LONG).show();return;
        }
        selectedFile=uri;selectedName=displayName;
        if (fileLabel != null) fileLabel.setText("選択中："+selectedName);
    }

    private void checkConnection() {
        preferWifiRoute();setConnected(false);
        new Thread(() -> {
            try {
                JSONObject data = new JSONObject(SannyApi.info());
                runOnUiThread(() -> {setConnected(true);new AlertDialog.Builder(this).setTitle("サンニーと接続できた！")
                    .setMessage("本体："+data.optString("name")+"\nバージョン："+data.optString("version")+
                        "\n無線更新："+(data.optBoolean("updater_enabled")?"有効":"管理用キー未設定"))
                    .setPositiveButton("OK",null).show();});
            } catch (Exception err) {
                runOnUiThread(() -> {setConnected(false);Toast.makeText(this,"接続できません："+err.getMessage(),Toast.LENGTH_LONG).show();});
            }
        }).start();
    }

    private void uploadSelected() {
        if (selectedFile == null || selectedName == null) {uploadStatus.setText("まず更新ファイルを選んでね");return;}
        final String secret=uploadKey.getText().toString().trim();
        if(secret.isEmpty()){uploadStatus.setText("管理用キーを入力してね");return;}
        preferences.edit().putString("admin_key",secret).apply();
        final Uri uri=selectedFile;final String name=selectedName;
        uploadStatus.setText("ファイルを確認しています…");uploadProgress.setProgress(0);
        preferWifiRoute();
        new Thread(() -> {
            try {
                byte[] data;
                try(InputStream input=getContentResolver().openInputStream(uri)){data=SannyApi.readLimited(input);}
                runOnUiThread(()->uploadStatus.setText("サンニーへ送信中…"));
                SannyApi.upload(name,data,secret,(sent,total)->runOnUiThread(()->uploadProgress.setProgress(sent*100/total)));
                runOnUiThread(()->{uploadStatus.setText("✓ 更新ファイルを送信・保存できたよ"+
                        (name.endsWith(".py")?"。再起動で反映されます。":"。"));setConnected(true);});
            } catch(Exception err){runOnUiThread(()->uploadStatus.setText("送信失敗："+err.getMessage()));}
        }).start();
    }

    private void restartBoard() {
        final String secret=preferences.getString("admin_key","");preferWifiRoute();
        new Thread(()->{
            try{SannyApi.restart(secret);runOnUiThread(()->Toast.makeText(this,"再起動を指示しました。少し待ってね。",Toast.LENGTH_LONG).show());}
            catch(Exception err){runOnUiThread(()->Toast.makeText(this,"再起動できません："+err.getMessage(),Toast.LENGTH_LONG).show());}
        }).start();
    }

    @Override protected void onDestroy() {
        if(viewer!=null){viewer.destroy();viewer=null;}
        ConnectivityManager manager=(ConnectivityManager)getSystemService(CONNECTIVITY_SERVICE);
        if(manager!=null)manager.bindProcessToNetwork(null);
        super.onDestroy();
    }
}
