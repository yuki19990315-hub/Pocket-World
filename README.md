# Pocket-World — サンニー

Waveshare ESP32-S3-Touch-LCD-1.28（愛称 **サンニー**）とAndroidスマホで育てる、6種類の小さな世界のテラリウム実験プロジェクトです。

## プロジェクト構成

- **[PocketWorld/](PocketWorld/README.md)** — ESP32-S3用のMicroPythonコード、6世界シミュレーション、スマホ用Web画面、無線更新API、祝日スケジューラ・6軸モーション・INMP441 I2Sマイクの音量反応（外付けマイクは実機接続前のため初期OFF）
- **[SannyCompanionAndroid/](SannyCompanionAndroid/README.md)** — Android専用アプリ「サンニー Companion」。大画面観察、無線更新、v0.4では生活時間と振る演出を本体に保存
- **[生活時間・電池・外装の設計](PocketWorld/docs/LIFE_CYCLE_POWER_ENCLOSURE.md)** — 日中常時点灯、土日祝日を含む夜間休眠、朝の自動起床、スマホ設定、充電演出、裏蓋からのBOOT/RESET復旧の設計（**時刻・休日判定は試作済み、ハードウェア連動は未実装**）
- **[操作・表示・通信の統合設計](PocketWorld/docs/INTERACTION_SYSTEM_DESIGN.md)** — 本体のタッチ操作、スマホと本体の別画面、6世界の切替、ジャイロ演出、API、マイク・電源機能の接続方針（**設計のみ**）
- **[.github/workflows/build-apk.yml](.github/workflows/build-apk.yml)** — `main` ブランチの更新時と手動実行時にAndroidのデバッグAPKをビルド

## APKの受け取り方

1. GitHubの **Actions** → **Build Sanny Android APK** を開く。
2. 最新の成功した実行を開き、ページ下部の **Artifacts** から `SannyCompanion-debug-apk` をダウンロードする。
3. ZIPを展開してAndroidスマホにAPKをインストールする。

これは開発用のデバッグAPKです。Android実機テストはまだ完了していません。v0.4のAndroid設定機能にはESP32側のv0.4ファイル導入が必要です。

## はじめる前に

- `PocketWorld/firmware/settings.py` のWi-Fiパスワードと更新キーは**公開用の初期値**です。サンニー実機に入れる前に、各自の秘密の値に変更してください。自分のパスワードやキーをGitHubに登録しないでください。
- 初回のMicroPython導入や新しい `main.py` の反映にはUSB接続が必要です。現在、ESP32-S3の**丸形液晶への表示は未実装**です。v0.4の夜間スリープは実機安全確認前のため `ENABLE_DEEP_SLEEP = False` でロックしています。
- ESP32実機とAndroid実機による動作確認は未完了です。

詳しい導入・制限・更新可能ファイルは各ディレクトリのREADMEを参照してください。
