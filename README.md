# Pocket-World — サンニー

Waveshare ESP32-S3-Touch-LCD-1.28（愛称 **サンニー**）とAndroidスマホで育てる、6種類の小さな世界のテラリウム実験プロジェクトです。

## プロジェクト構成

- **[PocketWorld/](PocketWorld/README.md)** — ESP32-S3用のMicroPythonコード、6世界シミュレーション、スマホ用Web画面、無線更新API、祝日スケジューラ・6軸モーション・INMP441 I2Sマイクの音量反応（外付けマイクは実機接続前のため初期OFF）
- **[SannyCompanionAndroid/](SannyCompanionAndroid/README.md)** — Android専用アプリ「サンニー Companion」。大画面観察、無線更新、v0.4では生活時間と振る演出を本体に保存
- **[生活時間・電池・外装の設計](PocketWorld/docs/LIFE_CYCLE_POWER_ENCLOSURE.md)** — 日中常時点灯、土日祝日の消灯、朝の再点灯、スマホ設定、充電演出、BOOT/RESET復旧の設計
- **[操作・表示・通信の統合設計](PocketWorld/docs/INTERACTION_SYSTEM_DESIGN.md)** — 本体のタッチ操作、スマホと本体の別画面、6世界の切替、ジャイロ演出、API、マイク・電源機能の接続方針（**設計のみ**）
- **[.github/workflows/build-apk.yml](.github/workflows/build-apk.yml)** — `main` ブランチの更新時と手動実行時にAndroidのデバッグAPKをビルド

## APKの受け取り方

1. GitHubの **Actions** → **Build Sanny Android APK** を開く。
2. 最新の成功した実行を開き、ページ下部の **Artifacts** から `SannyCompanion-debug-apk` をダウンロードする。
3. ZIPを展開してAndroidスマホにAPKをインストールする。

これは開発用のデバッグAPKです。Android実機テストはまだ完了していません。v0.4のAndroid設定機能にはESP32側のv0.4ファイル導入が必要です。

## はじめる前に

**実機を手元に用意できたら**、[Windowsでの初回USB診断手順](PocketWorld/docs/FIRST_REAL_DEVICE_TEST.md)に従って、まず既存ファームウェアを消さずにCOMポートと基板センサーを確認してください。RAM上だけで動く `PocketWorld/tools/hardware_probe.py` を同梱しています。書き込み作業はバックアップ手順を確定してから進めます。

- `PocketWorld/firmware/settings.py` のWi-Fiパスワードと更新キーは**公開用の初期値**です。サンニー実機に入れる前に、各自の秘密の値に変更してください。自分のパスワードやキーをGitHubに登録しないでください。
- 初回のMicroPython導入や新しい `main.py` の反映にはUSB接続が必要です。[丸形画面の操作と導入方法](PocketWorld/README.md#サンニーの丸形画面)を参照してください。ディープスリープは復帰・復旧の検証まで無効です。
- ESP32実機とAndroid実機による動作確認は未完了です。

詳しい導入・制限・更新可能ファイルは各ディレクトリのREADMEを参照してください。
