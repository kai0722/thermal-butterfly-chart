# thermal-butterfly-chart

非定常熱解析結果から、各ノードの**経験温度範囲・許容温度範囲・マージン領域**を一覧できるバタフライチャートを生成するツールです。

## チャートの見方

各ノードの行は、以下の3ゾーンを背景色で表し、その上に経験温度範囲をカラーバーで重ね描きします。

```
|  薄いグレー  |  濃いグレー  |      白      |  濃いグレー  |  薄いグレー  |
  許容温度範囲外  マージン領域   設計温度範囲   マージン領域   許容温度範囲外
              ↑                              ↑
           許容下限                        許容上限
               ↑                          ↑
            設計下限                    設計上限
            (allow_low + margin)    (allow_high − margin)
```

| 表示 | 意味 |
|---|---|
| 薄いグレー | 許容温度範囲外 |
| 濃いグレー | マージン領域（許容範囲内だが設計温度範囲外） |
| 白 | 設計温度範囲（経験温度が収まるべき領域） |
| カラーバー | 経験温度範囲（全解析ケースにわたる最低〜最高温度） |
| 黒い縦線 | 許容温度限界 |

経験温度バーが白い領域（設計温度範囲）に収まっていれば、マージンを確保できています。濃いグレー（マージン領域）にかかっている場合はマージンが消費されており、薄いグレー（許容温度範囲外）まで出ている場合は許容温度逸脱です。

## ディレクトリ構成

```
thermal-butterfly-chart/
├── main.py                              # メインスクリプト
├── pyproject.toml
├── analysis_results/
│   ├── *.xlsx                           # 熱解析結果（複数可）
│   └── allowable_limits.json            # 許容温度限界・マージン設定
└── output/
    └── butterfly_chart.png              # 生成されたチャート
```

## セットアップ

Python パッケージの管理には [uv](https://github.com/astral-sh/uv) を使用します。

```bash
# 依存パッケージのインストール
uv sync
```

## 実行方法

```bash
# analysis_results/ 内のすべての xlsx を対象
uv run python3 main.py

# ファイルを指定（拡張子あり・なし、どちらでも可）
uv run python3 main.py sun_MY_A
uv run python3 main.py sun_MY_A hot_case_B cold_case_C
uv run python3 main.py sun_MY_A.xlsx hot_case_B.xlsx
```

生成されたチャートは `output/butterfly_chart.png` に保存されます。チャートのタイトルには、読み込んだ xlsx ファイル名が自動的に使用されます。

## 入力データ形式（xlsx）

各 xlsx ファイルは以下の形式を想定しています。

| Times | NODE_A | NODE_B | ... |
|---|---|---|---|
| 0 | 20.0 | 18.5 | ... |
| 288 | 20.7 | 19.1 | ... |
| ... | ... | ... | ... |

- 1行目: ヘッダ行。先頭列は時刻列（列名は任意）、以降の列がノード名
- 先頭列: 時刻（秒）
- 以降の列: 各時刻における各ノードの温度（°C）
- 複数のファイルを読み込んだ場合、同名ノードの温度範囲は全ファイルにわたってまとめられます

## 設定ファイル（allowable_limits.json）

`analysis_results/allowable_limits.json` で、マージン値と各ノードの許容温度限界を設定します。

```json
{
  "margin_deg_c": 15.0,
  "nodes": {
    "NODE_NAME_IN_XLSX": {
      "label": "表示名",
      "allow_low": -20.0,
      "allow_high": 70.0
    }
  }
}
```

| フィールド | 説明 |
|---|---|
| `margin_deg_c` | 温度マージン（°C）。許容温度範囲の上下それぞれから内側に縮まる量。デフォルト: `15.0` |
| `nodes` | ノードごとの設定。キーは xlsx のヘッダ行に記載されているノード名 |
| `label` | チャートのY軸に表示する名称。省略時はノード名をそのまま使用 |
| `allow_low` | 許容温度下限（°C） |
| `allow_high` | 許容温度上限（°C） |

`nodes` に記載のないノードは、経験温度範囲にマージン分を加えた値が許容限界として自動設定されます。

ノードごとに異なるマージン値を設定したい場合は、該当ノードの設定内に `margin_deg_c` を追加します。

```json
{
  "margin_deg_c": 15.0,
  "nodes": {
    "BATTERY_NODE": {
      "label": "Battery",
      "allow_low": 0.0,
      "allow_high": 40.0,
      "margin_deg_c": 10.0
    }
  }
}
```
