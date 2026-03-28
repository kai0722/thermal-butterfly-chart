"""
Thermal Butterfly Chart Generator
非定常熱解析結果から各ノードの経験温度範囲・許容温度範囲・設計温度範囲を示す
バタフライチャートを生成する。

背景ゾーン（各ノード行）:
    薄いグレー | 濃いグレー | 白 | 濃いグレー | 薄いグレー
    許容範囲外   マージン領域  設計温度範囲  マージン領域   許容範囲外
その上にカラーバーで経験温度範囲を描画する。

Usage
-----
# すべての xlsx を対象
uv run python3 main.py

# ファイルを指定（拡張子あり・なし、複数指定可）
uv run python3 main.py example_data
uv run python3 main.py sun_MY_A hot_case_B
"""

import argparse
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd


# ── フォント設定 ────────────────────────────────────────────────────────────
def _setup_japanese_font() -> None:
    """macOS で利用可能な日本語フォントを matplotlib に設定する。"""
    candidates = [
        "Hiragino Kaku Gothic ProN",
        "Hiragino Sans",
        "Hiragino Kaku Gothic Pro",
        "Yu Gothic",
        "Noto Sans CJK JP",
        "DejaVu Sans",
    ]
    available = {f.name for f in matplotlib.font_manager.fontManager.ttflist}
    for font in candidates:
        if font in available:
            matplotlib.rcParams["font.family"] = font
            return
    matplotlib.rcParams["font.family"] = "DejaVu Sans"


_setup_japanese_font()

# ── パス設定 ────────────────────────────────────────────────────────────────
ANALYSIS_DIR = Path("analysis_results")
OUTPUT_DIR = Path("output")
LIMITS_FILE = ANALYSIS_DIR / "allowable_limits.json"

# ── ゾーン色定義 ─────────────────────────────────────────────────────────────
COLOR_OUTSIDE = "#C0C0C0"   # 許容温度範囲外（薄いグレー）
COLOR_MARGIN = "#808080"    # マージン領域（濃いグレー）
COLOR_DESIGN = "#FFFFFF"    # 設計温度範囲（白）

# ── レイアウト定数 ───────────────────────────────────────────────────────────
BG_HEIGHT = 0.85     # 背景ゾーンバーの高さ
EXP_HEIGHT = 0.55    # 経験温度バーの高さ
FIG_WIDTH = 14
X_PADDING = 10.0     # 許容限界の外側に追加する余白 (°C)


def load_analysis_data(
    analysis_dir: Path,
    targets: list[str] | None = None,
) -> tuple[dict, list[str]]:
    """
    analysis_dir 内のすべての .xlsx を読み込み、各ノードの
    全ケースにわたる最高・最低温度を返す。

    Parameters
    ----------
    analysis_dir : Path
    targets : list of str, optional
        xlsx ファイル名（拡張子あり・なし）のリスト。
        None または空リストの場合は analysis_dir 内の全 xlsx を対象とする。

    Returns
    -------
    (node_data, case_names)
        node_data  : {node_name: {"t_min": float, "t_max": float, "cases": list[str]}}
        case_names : list of xlsx file stems, in reading order
    """
    node_data: dict[str, dict] = {}
    case_names: list[str] = []

    if targets:
        excel_files = []
        for t in targets:
            stem = Path(t).stem          # 拡張子があっても stem だけ取り出す
            path = analysis_dir / f"{stem}.xlsx"
            if not path.exists():
                raise FileNotFoundError(f"File not found: {path}")
            excel_files.append(path)
    else:
        excel_files = sorted(analysis_dir.glob("*.xlsx"))

    if not excel_files:
        raise FileNotFoundError(f"No .xlsx files found in {analysis_dir}")

    for xlsx in excel_files:
        case_name = xlsx.stem
        case_names.append(case_name)
        df = pd.read_excel(xlsx, index_col=0)

        for col in df.columns:
            temps = df[col].dropna()
            if temps.empty:
                continue

            if col not in node_data:
                node_data[col] = {"t_min": float("inf"), "t_max": float("-inf"), "cases": []}

            node_data[col]["t_min"] = min(node_data[col]["t_min"], float(temps.min()))
            node_data[col]["t_max"] = max(node_data[col]["t_max"], float(temps.max()))
            node_data[col]["cases"].append(case_name)

    return node_data, case_names


def load_config(limits_file: Path) -> tuple[dict, float]:
    """
    設定ファイルを読み込み、ノード設定とグローバルマージン値を返す。

    Returns
    -------
    (nodes_dict, margin_deg_c)
    """
    if not limits_file.exists():
        return {}, 15.0

    with open(limits_file, encoding="utf-8") as f:
        cfg = json.load(f)

    # 新フォーマット: {"margin_deg_c": ..., "nodes": {...}}
    if "nodes" in cfg:
        margin = float(cfg.get("margin_deg_c", 15.0))
        return cfg["nodes"], margin

    # 旧フォーマット互換: {node_name: {...}, ...}
    return cfg, 15.0


def create_butterfly_chart(
    node_data: dict,
    node_limits: dict,
    margin_deg_c: float,
    output_path: Path,
    case_names: list[str] | None = None,
) -> None:
    """
    バタフライチャートを生成して output_path に保存する。

    各行のバックグラウンド:
        [薄グレー: 許容範囲外] [濃グレー: マージン] [白: 設計範囲] [濃グレー: マージン] [薄グレー: 許容範囲外]
    その上にカラーバーで経験温度範囲を重ね描画する。
    """
    nodes = list(node_data.keys())
    n = len(nodes)

    # ── チャート x 軸範囲を全ノードの許容限界から決定 ────────────────────────
    all_allow = []
    for node in nodes:
        lim = node_limits.get(node, {})
        t_min = node_data[node]["t_min"]
        t_max = node_data[node]["t_max"]
        all_allow.append(lim.get("allow_low", t_min - margin_deg_c))
        all_allow.append(lim.get("allow_high", t_max + margin_deg_c))

    chart_left = min(all_allow) - X_PADDING
    chart_right = max(all_allow) + X_PADDING

    # ── カラーパレット（経験温度バー用）────────────────────────────────────
    cmap = plt.get_cmap("tab10")

    fig_height = max(4.0, n * 0.6 + 1.8)
    _, ax = plt.subplots(figsize=(FIG_WIDTH, fig_height))
    ax.set_facecolor("white")

    y_labels = []

    for i, node in enumerate(nodes):
        t_min = node_data[node]["t_min"]
        t_max = node_data[node]["t_max"]
        lim = node_limits.get(node, {})
        allow_low = lim.get("allow_low", t_min - margin_deg_c)
        allow_high = lim.get("allow_high", t_max + margin_deg_c)
        node_margin = float(lim.get("margin_deg_c", margin_deg_c))
        design_low = allow_low + node_margin
        design_high = allow_high - node_margin
        label = lim.get("label", node)
        y_labels.append(label)

        # y=0 が最上行になるよう反転（invert_yaxis は後で設定）
        y = i
        exp_color = cmap(i % 10)

        # ── Layer 1: 薄いグレー（チャート全幅 = 許容範囲外の色）────────────
        ax.barh(
            y, chart_right - chart_left, left=chart_left,
            height=BG_HEIGHT, color=COLOR_OUTSIDE, linewidth=0, zorder=1,
        )

        # ── Layer 2: 白（許容温度範囲 → 設計温度範囲の背景）────────────────
        ax.barh(
            y, allow_high - allow_low, left=allow_low,
            height=BG_HEIGHT, color=COLOR_DESIGN, linewidth=0, zorder=2,
        )

        # ── Layer 3: 濃いグレー（マージン領域）──────────────────────────────
        # 低温側マージン
        if design_low > allow_low:
            ax.barh(
                y, design_low - allow_low, left=allow_low,
                height=BG_HEIGHT, color=COLOR_MARGIN, linewidth=0, zorder=3,
            )
        # 高温側マージン
        if allow_high > design_high:
            ax.barh(
                y, allow_high - design_high, left=design_high,
                height=BG_HEIGHT, color=COLOR_MARGIN, linewidth=0, zorder=3,
            )

        # ── Layer 4: 経験温度範囲バー（カラー）──────────────────────────────
        ax.barh(
            y, t_max - t_min, left=t_min,
            height=EXP_HEIGHT, color=exp_color, linewidth=0, zorder=4,
        )

        # ── 許容温度限界の境界線 ──────────────────────────────────────────
        for x_lim in (allow_low, allow_high):
            ax.plot(
                [x_lim, x_lim],
                [y - BG_HEIGHT / 2, y + BG_HEIGHT / 2],
                color="black", linewidth=1.0, zorder=5,
            )

    # ── 軸設定 ────────────────────────────────────────────────────────────
    ax.set_yticks(range(n))
    ax.set_yticklabels(y_labels, fontsize=10)
    ax.set_ylim(-0.6, n - 0.4)
    ax.invert_yaxis()
    ax.set_xlim(chart_left, chart_right)
    ax.set_xlabel("Temperature (°C)", fontsize=11)
    title_name = ", ".join(case_names) if case_names else "Thermal Butterfly Chart"
    ax.set_title(
        f"{title_name}  [margin: ±{margin_deg_c:.0f}°C]",
        fontsize=13, pad=10,
    )
    ax.grid(True, axis="x", linestyle="--", alpha=0.35, zorder=0)

    # ── Legend ───────────────────────────────────────────────────────────
    legend_handles = [
        mpatches.Patch(facecolor=COLOR_OUTSIDE, edgecolor="gray",
                       label="Outside Allowable"),
        mpatches.Patch(facecolor=COLOR_MARGIN, edgecolor="gray",
                       label=f"Margin Zone (±{margin_deg_c:.0f}°C)"),
    ]
    ax.legend(
        handles=legend_handles,
        loc="lower right",
        fontsize=9,
        framealpha=0.95,
    )

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate a thermal butterfly chart from transient analysis xlsx files.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        metavar="FILE",
        help=(
            "xlsx file name(s) to include (with or without .xlsx extension). "
            "If omitted, all xlsx files in analysis_results/ are used."
        ),
    )
    args = parser.parse_args()

    print("Loading analysis data ...")
    node_data, case_names = load_analysis_data(ANALYSIS_DIR, args.files or None)
    print(f"  Found {len(node_data)} node(s): {list(node_data.keys())}")
    print(f"  Cases: {case_names}")

    node_limits, margin_deg_c = load_config(LIMITS_FILE)
    print(f"  Loaded limits for {len(node_limits)} node(s), margin = {margin_deg_c}°C")

    output_path = OUTPUT_DIR / "butterfly_chart.png"
    print("Creating butterfly chart ...")
    create_butterfly_chart(node_data, node_limits, margin_deg_c, output_path, case_names)
    print("Done.")


if __name__ == "__main__":
    main()
