# Pocket-World — サンニー

Waveshare ESP32-S3-Touch-LCD-1.28（愛称 **サンニー**）とAndroidスマホで育てる、6種類の小さな世界のテラリウム実験プロジェクトです。

## プロジェクト構成

- **[PocketWorld/](PocketWorld/README.md)** — ESP32-S3用のMicroPythonコード、6世界シミュレーション、スマホ用Web画面、無線更新API、祝日スケジューラ・6軸モーション・INMP441 I2Sマイクの音量反応（外付けマイクは実機接続前のため初期OFF）
- **[SannyCompanionAndroid/](SannyCompanionAndroid/README.md)** — Android専用アプリ「サンニー Companion」。大画面観察、33ファイル一括無線更新、生活時間・振る演出・画面輝度の設定
- **[生活時間・電池・外装の設計](PocketWorld/docs/LIFE_CYCLE_POWER_ENCLOSURE.md)** — 時刻・休日判定と画面の時間帯消灯を実装。ディープスリープ・充電中検出・外装は実機未検証の設計項目
- **[操作・表示・通信の統合設計](PocketWorld/docs/INTERACTION_SYSTEM_DESIGN.md)** — 本体タッチ操作、ジャイロ、モード変更、マイク音量・電源制御の構成と設計履歴
- **[.github/workflows/build-apk.yml](.github/workflows/build-apk.yml)** — `main` ブランチの更新時と手動実行時にAndroidのデバッグAPKをビルド

## APKの受け取り方

1. GitHubの **Actions** → **Build Sanny Android APK** を開く。
2. 最新の成功した実行を開き、ページ下部の **Artifacts** から `SannyCompanion-debug-apk` をダウンロードする。
3. ZIPを展開してAndroidスマホにAPKをインストールする。

これは開発用のデバッグAPKです。Android実機テストはまだ完了していません。v0.7の「起床から就寝までがサンニーの1日」演出にはESP32側へv0.7の`main.py`・`work_schedule.py`・`round_screen.py`等をUSBで導入する必要があります。

## はじめる前に

**実機を手元に用意できたら**、[Windowsでの初回USB診断手順](PocketWorld/docs/FIRST_REAL_DEVICE_TEST.md)に従って、まず既存ファームウェアを消さずにCOMポートと基板センサーを確認してください。RAM上だけで動く `PocketWorld/tools/hardware_probe.py` を同梱しています。書き込み作業はバックアップ手順を確定してから進めます。

- `PocketWorld/firmware/settings.py` のWi-Fiパスワードと更新キーは**公開用の初期値**です。サンニー実機に入れる前に、各自の秘密の値に変更してください。自分のパスワードやキーをGitHubに登録しないでください。
- 初回のMicroPython導入や新しい `main.py` の反映にはUSB接続が必要です。**丸形液晶描画・タッチ・バックライト制御のコードは実装済みですがCOM7実機未検証**です。深いスリープは `ENABLE_DEEP_SLEEP = False` でロックし、夜間はバックライトだけ消す安全な試験運用に対応します。
- ESP32実機とAndroid実機による動作確認は未完了です。

詳しい導入・制限・更新可能ファイルは各ディレクトリのREADMEを参照してください。
