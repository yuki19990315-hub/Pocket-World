# サンニー Companion — Android専用アプリ（ソース v0.6）

Nothing Phone (4a) ProなどAndroid端末から、ESP32-S3「サンニー」のPocket Worldを観察し、画像・データ・ゲームロジックを無線アップロードするためのネイティブアプリです。

## できること

- **観察:** ESP32のローカルWi-Fiに接続し、6つの世界をWebViewで大きく表示。水の世界では川・海・深海を切り替え。ESP32側の実データを使用
- **更新:** Android標準のファイル選択画面からファイルを選び、認証キー付きでESP32へ送信
- **完成ワールドパック:** アプリに同梱した16枚のPNG・16枚の丸形画面用RGB565データ・`index.html`の計33ファイルをボタン一つで順次送信（通信中断時は再実行）
- **再起動:** `world_model.py` のアップロード後にサンニーの再起動を指示
- **設定:** Wi-Fi設定を開く、接続確認、更新キーの保存
- **v0.4 電源:** 朝の起床時刻・退勤時刻をサンニーに送信して保存、時刻をスマホから同期。土日祝日OFFの予定を管理（**実機スリープは安全ロック中**）
- **v0.4 モーション:** 6軸センサーの状態を取得し、「振るとキラキラ」演出を認証付きでON/OFF
- **v0.6 輝度:** 丸形画面の明るさを10〜100%のスライダーで調整・保存。夜間や土日祝日には本体がバックライトをOFFにする（Wi-Fiは稼働、深いスリープは安全ロックのまま）
- **v0.6 発見記録:** 6世界それぞれの最新24件の出来事を、日付の進行とともに閲覧

アプリはSANNY-ESP32のWi-Fi経由で、固定IP `192.168.4.1` と通信します。クラウドサーバー、広告、ユーザーアカウントはありません。

## APKビルド手順

Android StudioのソースプロジェクトとGitHub Actionsビルド設定があります。APKのビルドは自動処理で検証しますが、**AndroidとESP32の実機連携は未検証**です。

1. Android Studioを開き、`SannyCompanionAndroid` フォルダをプロジェクトとして選びます。
2. Android SDK Platform 35と対応するBuild Tools、JDK 17をセットアップします。
3. Gradle同期を完了します。Android Gradle Pluginは8.9.2を指定しています（Gradle 8.11.1対応）。
4. **Build → Build Bundle(s) / APK(s) → Build APK(s)** を実行します。
5. `app/build/outputs/apk/debug/app-debug.apk` が生成されたらAndroidスマホへインストールします。

Gradle Wrapperのjarは同梱していないため、Android Studioでの同期を前提とします。

**SDKをPCへ入れずにビルドしたい場合:** GitHubリポジトリのルートにある `.github/workflows/build-apk.yml` により、`main` ブランチ更新時または Actions の「Run workflow」からデバッグAPKを生成できます。成功した実行の Artifacts からダウンロードしてください。APKのビルド成功・実機動作は確認が必要です。

## ESP32側の準備

同じパッケージ内の `PocketWorld/README.md` に従って、まずMicroPythonと `main.py`、`world_model.py`、`safe_update.py`、`settings.py`、`round_screen.py`、`index.html`、`power_runtime.py`、`work_schedule.py`、`qmi8658.py`、`motion_effects.py`、`inmp441.py`、`/assets/jp_holidays.json` を転送します。初回はPNGと`.dat`の素材も転送し、以降の素材更新はアプリから行えます。

- `settings.py` の `AP_SSID`：`SANNY-ESP32`
- `AP_PASSWORD`：自分専用の長いWi-Fiパスワードに変更
- `ADMIN_KEY`：自分専用の長い更新キーに変更（初期値だと無線更新不可）

最初のMicroPython導入と失敗時の復旧にはUSB接続が必要です。

## 更新できるファイル

| アプリで選ぶ名前 | ESP32上の保存先 | 備考 |
| --- | --- | --- |
| `index.html` | `/index.html` | スマホ表示UIを更新 |
| `world_model.py` | `/world_model.py` | 世界のルールを更新。再起動後に反映 |
| `tree.png` | `/assets/tree.png` | 128KiBまで。利用にはゲームコード側の参照処理が必要 |
| `data.json` | `/assets/data.json` | 同上 |

`main.py`、`settings.py`、ファームウェア `.bin`、任意ZIP一括転送、フォルダ全体の差分同期は未対応です。同梱済み33ファイルの一括更新のみ対応しています。更新パックを作り直す場合はリポジトリ直下で`node PocketWorld/tools/build_display_assets.js`を実行します。

## セキュリティ・制限

- サンニー専用Wi-Fi内で、HTTPの平文通信を使用します。**職場など共有ネットワークで使わず、秘密のAPパスワードと更新キーを設定**してください。
- アプリはAndroidのプライベートな保存領域に更新キーを保持します。不要なら保存せず、使うときだけ入力する設計への変更も可能です。
- アプリの接続先は `http://192.168.4.1/` 固定です。別のWi-Fi内の任意のホストへ接続する機能はありません。
- 1ファイル最大128KiB。大きな写真やアニメーションには別の転送形式が必要です。
- Android 17のローカルネットワーク権限は、ターゲットSDK 37以降で必須になります。この試作アプリのターゲットはSDK 35です。今後更新時に権限対応が必要です。
- Android実機での接続、表示、更新、再起動は未検証です。

## ソースだけの簡易チェック

`tests/SannyApiSelfTest.java` は、ファイル名の許可リストや読み込みサイズを確認するJavaのテスト用ソースです。JDK開発キットの `javac` がある環境でコンパイルして実行できます。

Android仕様の公式参照:

- https://developer.android.com/privacy-and-security/local-network-permission
- https://developer.android.com/build/releases/agp-8-9-0-release-notes
- https://developer.android.com/training/data-storage/shared/documents-files
