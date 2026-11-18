# はじめてのサンニー実機テスト（Windows）

対象: Waveshare ESP32-S3-Touch-LCD-1.28。最初は**既存ファームウェアを消さない**。

## ステップ1 — PCでUSB接続を確認（書き込みなし）

1. サンニーにUSB-Cの**データ通信対応**ケーブルをつなぐ。マイクとバッテリーの外部配線はまだつながない。
2. Windowsで `Win + X` →「デバイス マネージャー」→「ポート (COM と LPT)」を展開。
3. USBを抜き差しして増えた `USB-SERIAL CH343 (COMx)` 等の名前とCOM番号を控える。
4. ポートが出なければ別の通信対応ケーブルを試し、Waveshare公式のCH343ドライバー情報を確認する。外装を閉じる前にBOOT/RESETへアクセスできるようにする。

この段階では書き込み・初期化・消去をしない。**購入時の丸形画面が表示しているか**も記録する。

## ステップ2 — 現在のファームウェア方式を確認

- **すでにMicroPythonのREPLが使える場合のみ**：WindowsにPythonがあるなら `py -m pip install mpremote` でツールを準備し、次の2コマンドを実行する（COM番号は実際の番号へ変更）。

  ```powershell
  py -m mpremote connect COM7 exec "import sys; print(sys.implementation)"
  py -m mpremote connect COM7 run PocketWorld/tools/hardware_probe.py
  ```

  Windowsターミナルをリポジトリのルートで開いて実行する。COM7は以前ユーザーが報告した番号なので、現在違っていれば読み替える。2つ目は**一時的なRAM上の実行**で、装置にファイルを追加しない。`mpremote`による接続は起動中の既存アプリを中断またはソフトリセットする場合がある。
- Arduino/メーカー工場デモが入っている場合、`mpremote` はMicroPython REPLを見つけられない。その場合はそのまま止め、接続時の画面とCOM番号とエラーを確認してからバックアップ手順を決める。**MicroPythonの新規書き込みを自動実行しない。**

## ステップ3 — 確認結果を共有

以下を共有する：

- Windowsデバイスマネージャーに表示されたCOM番号／機器名
- サンニーの丸形画面が起動しているか（写真でも可）
- `mpremote` が動く場合は `=== SANNY HARDWARE PROBE 1 ===` 以下のログ
- 裏面・コネクタの写真（INMP441を配線する前にGPIO15/16/17/3V3/GNDの位置を確認するため）

この結果を見てから**ファームウェア全体のバックアップ→丸形GC9A01テスト→タッチ→IMU→INMP441**の順で進める。自動休眠は実機での安全確認までOFFのまま維持する。

**v0.6の追加確認:** LCDの左右スワイプ、タップ、長押し（電池4本ゲージ）、水槽の上下スワイプを確認する。スマホで時刻同期→夜間時間設定にしてバックライトOFF→昼間の時刻に戻して復帰できるかも確認する。ディープスリープは引き続きONにせず、USBによる復旧手段を確保する。Android設定では輝度を10〜100%で試し、電池電圧は実測値と比較する。

## 参考（一次資料）

- [Waveshare本体・USB/UART・GPIO仕様](https://docs.waveshare.com/ESP32-S3-Touch-LCD-1.28)
- [Waveshare MicroPython導入方法](https://docs.waveshare.com/ESP32-MicroPython-Tutorials/Getting-Started)
- [MicroPython公式mpremoteマニュアル](https://docs.micropython.org/en/latest/reference/mpremote.html)
