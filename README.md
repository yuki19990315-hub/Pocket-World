# Pocket-World — サンニー

Waveshare ESP32-S3-Touch-LCD-1.28（愛称 **サンニー**）とAndroidスマホで育てる、6種類の小さな世界のテラリウム実験プロジェクトです。

## プロジェクト構成

- **[PocketWorld/](PocketWorld/README.md)** — ESP32-S3用のMicroPythonコード、6世界シミュレーション（自然・街・共生・魔法・森・水槽）、音量に反応する世界ロジック（マイク接続は未実装）、スマホ用Web画面、無線更新API
- **[SannyCompanionAndroid/](SannyCompanionAndroid/README.md)** — Android専用アプリ「サンニー Companion」。大画面での観察、無線での画像・世界データ更新
- **[.github/workflows/build-apk.yml](.github/workflows/build-apk.yml)** — `main` ブランチの更新時と手動実行時にAndroidのデバッグAPKをビルド

## APKの受け取り方

1. GitHubの **Actions** → **Build Sanny Android APK** を開く。
2. 最新の成功した実行を開き、ページ下部の **Artifacts** から `SannyCompanion-debug-apk` をダウンロードする。
3. ZIPを展開してAndroidスマホにAPKをインストールする。

これは開発用のデバッグAPKです。Android実機テストはまだ完了していません。

## はじめる前に

- `PocketWorld/firmware/settings.py` のWi-Fiパスワードと更新キーは**公開用の初期値**です。サンニー実機に入れる前に、各自の秘密の値に変更してください。自分のパスワードやキーをGitHubに登録しないでください。
- 初回のMicroPython導入にはUSB接続が必要です。現在、ESP32-S3の**丸形液晶への表示は未実装**です。大画面でのスマホ観察と、6世界のデータ管理が試作範囲です。
- ESP32実機とAndroid実機による動作確認は未完了です。

詳しい導入・制限・更新可能ファイルは各ディレクトリのREADMEを参照してください。
