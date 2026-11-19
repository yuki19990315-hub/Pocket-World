# Pocket-World 開発引き継ぎ（2026-11-19）

チャットが長くなったときは、このファイルと最新コミットを読めば作業を再開できる。
進捗は「リポジトリで確認できる状態」を優先し、チャット上だけの完成報告と区別する。

## 今回の制作対象

- 自然ワールド（`nature`）：草原と若木の浮島から、大樹・花・滝の浮島へ育つ。地面を広く見せるため高めの俯瞰角度と薄い岩盤に統一した。
- 240×240の円形LCD。自然の背景画像は80×80の仮想ドットを3倍に最近傍拡大。
- 更新対象は `PocketWorld/design/assets/nature-{young,mature}.png` と、生成するESP32用 `.dat`、Android同梱の `.png` / `.dat`。
- Androidの成長プレビューでは自然の生き物が段階的に増え、成熟後は滝に小さな光の動きが現れる。

## 再生成・検証

```sh
node PocketWorld/tools/build_display_assets.js
python3 -m unittest discover -s PocketWorld/tests -q
node PocketWorld/tests/check_asset_pack.js
node PocketWorld/tests/check_web_ui.js
node PocketWorld/design/preview.test.js
```

`build_display_assets.js` と `check_asset_pack.js` にはNode.jsの `sharp` が必要。
AndroidデバッグAPKは `main` への更新後、GitHub Actions の `Build Sanny Android APK` で生成する。

## 実機未確認・次回の確認項目

- ESP32-S3-Touch-LCD-1.28実機での色、向き、描画速度、タッチとジャイロ。
- Android実機での新しい自然背景の表示と無線更新。画面上のプレビュー合格は実機動作の証明ではない。
- ディープスリープ・バッテリー・充電検出は安全性を優先して実機確認後に有効化する。
- 次の世界の改修順やビジュアルはユーザーと確認する。
