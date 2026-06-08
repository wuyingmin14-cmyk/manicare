# AI 美甲虚拟试戴 — Gradio Web App
# 运行: python app.py  → 浏览器自动打开 http://localhost:7860

import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import cv2
import numpy as np
import gradio as gr
from typing import Dict, List, Optional, Tuple

from modules.hand_detector        import HandDetector
from modules.skin_analysis        import SkinAnalyzer
from modules.hand_shape_analysis  import HandShapeAnalyzer
from modules.nail_shape_transform import NailShapeTransformer
from modules.recommendation_engine import RecommendationEngine

# ── 初始化核心模块 ────────────────────────────────────────────────────────────
detector      = HandDetector()
skin_analyzer = SkinAnalyzer()
hand_analyzer = HandShapeAnalyzer()
nail_xform    = NailShapeTransformer()
rec_engine    = RecommendationEngine()

# ── 加载真实款式库 ────────────────────────────────────────────────────────────
nail_art_renderer = None
_style_db_ready   = False

try:
    from modules.texture_warper import NailArtRenderer
    nail_art_renderer = NailArtRenderer()
    if nail_art_renderer.num_styles > 0:
        _style_db_ready = True
        print(f"[App] NailArtRenderer: {nail_art_renderer.num_styles} styles, "
              f"{len(nail_art_renderer.get_thumbnails())} thumbnails")
except Exception as e:
    print(f"[App] NailArtRenderer unavailable: {e}")

if not _style_db_ready:
    from modules.nail_renderer import NailRenderer
    _fallback_renderer = NailRenderer()
    print("[App] Using colour-swatch fallback renderer")
else:
    _fallback_renderer = None

# ── 标签翻译 ──────────────────────────────────────────────────────────────────
SKIN_CN = {
    "warm_yellow": "暖黄皮",
    "cool_white":  "冷白皮",
    "dark_skin":   "偏深肤色",
    "neutral":     "中性肤色",
}
HAND_CN = {
    "short_wide": "短圆手型",
    "long_thin":  "细长手型",
    "standard":   "标准手型",
}
SHAPE_CN = {
    "oval":   "椭圆形",
    "almond": "杏仁形",
    "square": "方形",
    "round":  "圆形",
    "coffin": "棺材形",
}
SKIN_TIPS = {
    "warm_yellow": "推荐冷色调（蓝、紫、冷粉），与暖黄皮高对比显白",
    "cool_white":  "推荐高饱和酒红、深紫、宝石红，衬托冷白皮",
    "dark_skin":   "推荐亮色系（经典红、玫瑰金、裸色），形成视觉焦点",
    "neutral":     "百搭款，经典红、裸色、珊瑚粉均适合",
}


# ── 工具函数 ──────────────────────────────────────────────────────────────────
def _bgr(img_rgb: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)

def _rgb(img_bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

def _shaped_masks(state: Dict) -> Dict[str, np.ndarray]:
    masks = state["nail_masks"]
    shape = state.get("current_shape", "oval")
    if shape == "oval":
        return masks
    try:
        return nail_xform.transform_nail_set(masks, shape)
    except Exception:
        return masks


# ── 分析 & 推荐 ───────────────────────────────────────────────────────────────
def analyze_and_recommend(image_rgb: Optional[np.ndarray]):
    empty = ("", "", "", "", [], {})
    if image_rgb is None:
        return ("请先上传单手照片。",) + empty

    bgr = _bgr(image_rgb)

    # 1. 手部检测
    det = detector.detect(bgr)
    if not det["detected"]:
        return (
            "未检测到手部。建议：单手入镜、五指展开、光线充足、背景简洁。",
        ) + empty

    hand       = det["hands"][0]
    landmarks  = hand["landmarks"]
    nail_masks = hand["nail_masks"]
    nail_info  = hand["nail_info"]
    hand_mask  = hand["hand_mask"]

    # 2. 肤色分析
    try:
        skin_res  = skin_analyzer.analyze(bgr, hand_mask)
        skin_type = skin_res["tone_classification"]["skin_type"]
    except Exception:
        skin_type = "neutral"

    # 3. 手型分析
    try:
        hand_res      = hand_analyzer.analyze(landmarks)
        hand_type     = hand_res["classification"]["hand_type"]
        avg_ratio     = hand_res["classification"]["average_ratio"]
        primary_shape = hand_res["nail_shape_recommendations"]["primary_recommendation"]
        alt_shapes    = hand_res["nail_shape_recommendations"]["secondary_options"]
    except Exception:
        hand_type, avg_ratio = "standard", 2.5
        primary_shape, alt_shapes = "oval", ["almond"]

    # 4. 余弦相似度推荐 Top-5
    if _style_db_ready and nail_art_renderer is not None:
        top5_idx = nail_art_renderer.recommend(skin_type, hand_type, nail_info, k=5)
    else:
        top5_idx = list(range(5))

    state = {
        "bgr":           bgr,
        "nail_masks":    nail_masks,
        "nail_info":     nail_info,
        "hand_mask":     hand_mask,
        "landmarks":     landmarks,
        "skin_type":     skin_type,
        "hand_type":     hand_type,
        "primary_shape": primary_shape,
        "current_shape": primary_shape,
        "current_style_idx": top5_idx[0] if top5_idx else 0,
        "top5_idx":      top5_idx,
        "opacity":       1.0,
        "disliked_idx":  set(),
        "feedback_log":  [],
    }

    # 5. 构建推荐 Gallery
    gallery = _build_gallery(top5_idx)

    # 6. 文字摘要
    skin_cn   = SKIN_CN.get(skin_type, skin_type)
    hand_cn   = HAND_CN.get(hand_type, hand_type)
    shape_cn  = SHAPE_CN.get(primary_shape, primary_shape)
    alt_cn    = "、".join(SHAPE_CN.get(s, s) for s in alt_shapes[:2])
    shape_txt = f"主推：{shape_cn}  备选：{alt_cn}"
    tip_txt   = SKIN_TIPS.get(skin_type, "")
    status    = (
        f"检测成功！{len(nail_masks)} 个指甲  "
        f"肤色：{skin_cn}  手型：{hand_cn}"
    )

    return status, skin_cn, f"{hand_cn}（比 {avg_ratio:.1f}）", shape_txt, tip_txt, gallery, state


# ── Gallery 构建 ──────────────────────────────────────────────────────────────
def _build_gallery(top5_idx: List[int]) -> List[Tuple[np.ndarray, str]]:
    if _style_db_ready and nail_art_renderer is not None:
        all_thumbs = nail_art_renderer.get_thumbnails()
        items = []
        for i in top5_idx:
            if i < len(all_thumbs):
                items.append(all_thumbs[i])
        return items if items else all_thumbs[:5]

    # Fallback placeholder
    return [
        (np.full((100, 80, 3), [120 + i * 20, 80, 180], dtype=np.uint8),
         f"款式 {i+1}")
        for i in range(5)
    ]


# ── 渲染 dispatch ─────────────────────────────────────────────────────────────
def _render(
    bgr: np.ndarray,
    nail_masks: Dict,
    nail_info: Dict,
    style_idx: int,
    opacity: float,
    hand_mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    if _style_db_ready and nail_art_renderer is not None:
        return nail_art_renderer.render(bgr, nail_masks, nail_info,
                                        style_idx, opacity, hand_mask)
    from modules.nail_renderer import NAIL_STYLES
    style_names = list(NAIL_STYLES.keys())
    sname = style_names[style_idx % len(style_names)]
    return _fallback_renderer.render(bgr, nail_masks, sname, opacity)


def _rerender(state: Dict) -> Optional[np.ndarray]:
    if not state:
        return None
    result = _render(
        state["bgr"], _shaped_masks(state), state.get("nail_info", {}),
        state.get("current_style_idx", 0), state.get("opacity", 1.0),
        state.get("hand_mask"),
    )
    return _rgb(result)


# ── Event handlers ────────────────────────────────────────────────────────────
def on_gallery_select(evt: gr.SelectData, state: Dict):
    if not state:
        return None, "请先上传图片并点击「AI 分析 & 推荐」"
    top5 = state.get("top5_idx", list(range(5)))
    slot = evt.index
    idx  = top5[slot] if slot < len(top5) else slot
    state["current_style_idx"] = idx
    return _rerender(state), _style_label(idx)


def on_shape_change(shape: str, state: Dict):
    if not state:
        return None
    state["current_shape"] = shape
    return _rerender(state)


def on_opacity_change(opacity: float, state: Dict):
    if not state:
        return None
    state["opacity"] = opacity
    return _rerender(state)


def on_style_dropdown(value, state: Dict):
    if not state or value is None:
        return None, ""
    try:
        idx = int(value)
    except (ValueError, TypeError):
        idx = 0
    state["current_style_idx"] = idx
    return _rerender(state), _style_label(idx)




# ── 用户反馈入口 ──────────────────────────────────────────────────────────────
# "不喜欢" / "太假" / "颜色不合适" — 反馈被记录并立即用于调整后续推荐与渲染：
#   · 不喜欢 / 颜色不合适 → 当前款式加入排除列表，重新计算 Top-5 推荐
#   · 太假              → 自动调低融合强度（不透明度），让效果更柔和自然
FEEDBACK_LABELS = {"dislike": "不喜欢", "fake": "太假", "color": "颜色不合适"}


def on_feedback(fb_type: str, state: Dict):
    if not state or "current_style_idx" not in state:
        return None, gr.update(), "请先完成分析并选择一款试戴效果，再进行反馈。"

    cur_idx = state["current_style_idx"]
    label   = FEEDBACK_LABELS.get(fb_type, fb_type)
    state.setdefault("feedback_log", []).append({"style_idx": cur_idx, "type": fb_type})

    msg = [f"已收到反馈「{label}」。"]
    gallery_update = gr.update()

    # "太假" → 渲染参数调整：降低融合强度，让美甲与手部贴合得更自然
    if fb_type == "fake":
        new_opacity = max(0.55, float(state.get("opacity", 1.0)) - 0.12)
        state["opacity"] = new_opacity
        msg.append(f"已自动将融合强度调低至 {new_opacity:.2f}，让效果更贴合真实质感。")

    # "不喜欢" / "颜色不合适" → 推荐逻辑调整：排除该款式，重新匹配 Top-5
    if fb_type in ("dislike", "color"):
        disliked = state.setdefault("disliked_idx", set())
        disliked.add(cur_idx)
        if _style_db_ready and nail_art_renderer is not None:
            new_top5 = nail_art_renderer.recommend(
                state.get("skin_type", "neutral"),
                state.get("hand_type", "standard"),
                state.get("nail_info", {}),
                k=5, exclude=disliked,
            )
            if new_top5:
                state["top5_idx"] = new_top5
                state["current_style_idx"] = new_top5[0]
                gallery_update = _build_gallery(new_top5)
                msg.append("已根据反馈重新匹配推荐款式，避开类似的不合适效果。")

    return _rerender(state), gallery_update, "".join(msg)


def on_feedback_dislike(state: Dict):
    return on_feedback("dislike", state)


def on_feedback_fake(state: Dict):
    return on_feedback("fake", state)


def on_feedback_color(state: Dict):
    return on_feedback("color", state)


def _style_label(idx: int) -> str:
    if _style_db_ready and nail_art_renderer is not None:
        styles = nail_art_renderer.styles
        if idx < len(styles):
            det = "指甲检测" if styles[idx].get("has_detection") else "中心裁切"
            return f"款式 {styles[idx]['id']}  [{det}]"
    return f"款式 {idx + 1}"


def _dropdown_choices() -> List[Tuple[str, str]]:
    if _style_db_ready and nail_art_renderer is not None:
        return [(f"款式 {s['id']}", str(i))
                for i, s in enumerate(nail_art_renderer.styles)]
    from modules.nail_renderer import NAIL_STYLES
    return [(f"{v['name_cn']} ({v['category']})", str(i))
            for i, v in enumerate(NAIL_STYLES.values())]


# ── UI ────────────────────────────────────────────────────────────────────────
def build_ui() -> gr.Blocks:
    db_note = (
        f"共 {nail_art_renderer.num_styles} 款真实美甲（AI 余弦相似度推荐 Top-5）"
        if _style_db_ready else
        "（未检测到数据库，显示色样预览。请先运行 build_style_db.py）"
    )

    with gr.Blocks(title="AI美甲虚拟试戴") as demo:
        gr.Markdown(
            "# AI 美甲虚拟试戴\n"
            "上传**单手正面照片**（五指展开 · 掌心向下 · 光线充足 · 背景简洁），"
            "AI 自动分析肤色手型，从数据库余弦相似度匹配最适合的 5 款真实美甲，"
            "通过透视变换将完整甲片纹理贴合到您的真实指甲上。"
        )

        state = gr.State({})

        # ── Row 1: Upload + Analysis ──────────────────────────────────────
        with gr.Row(equal_height=False):
            with gr.Column(scale=1, min_width=300):
                input_img   = gr.Image(label="上传单手照片", type="numpy",
                                       height=380, sources=["upload", "clipboard"])
                analyze_btn = gr.Button("AI 分析 & 推荐", variant="primary", size="lg")
                status_box  = gr.Textbox(label="状态", interactive=False, lines=2)

            with gr.Column(scale=1, min_width=280):
                gr.Markdown("### 分析结果")
                skin_box  = gr.Textbox(label="肤色类型",  interactive=False)
                hand_box  = gr.Textbox(label="手型类型",  interactive=False)
                shape_box = gr.Textbox(label="甲型推荐",  interactive=False, lines=2)
                tip_box   = gr.Textbox(label="配色建议",  interactive=False, lines=2)

        # ── Row 2: Recommended Gallery ────────────────────────────────────
        gr.Markdown(f"---\n### 推荐款式\n{db_note}\n点击任意款式即可试戴")
        gallery = gr.Gallery(
            label="推荐款式（Top-5 余弦相似度）",
            columns=5, rows=1, height=260,
            allow_preview=False, show_label=False,
        )

        # ── Row 3: Result + Controls ──────────────────────────────────────
        gr.Markdown("---\n### 试戴效果")
        with gr.Row():
            with gr.Column(scale=2):
                result_img   = gr.Image(
                    label="美甲试戴效果（透视变换 + 光泽渲染）",
                    height=520, interactive=False,
                )
                selected_lbl = gr.Textbox(
                    label="当前款式", interactive=False,
                    value="请从上方点击款式",
                )
                gr.Markdown("**对当前效果不满意？告诉我们，AI 会自动调整推荐与渲染**")
                with gr.Row():
                    fb_dislike_btn = gr.Button("不喜欢", size="sm")
                    fb_fake_btn    = gr.Button("太假",   size="sm")
                    fb_color_btn   = gr.Button("颜色不合适", size="sm")
                feedback_status = gr.Textbox(
                    label="反馈状态", interactive=False, lines=2,
                )

            with gr.Column(scale=1, min_width=220):
                gr.Markdown("**甲型调整**")
                shape_radio = gr.Radio(
                    choices=[(cn, key) for key, cn in SHAPE_CN.items()],
                    value="oval", label="甲型",
                )
                gr.Markdown("**浏览全部款式**")
                style_dd = gr.Dropdown(
                    choices=_dropdown_choices(),
                    label="全部款式（手动选择）", value=None,
                )
                gr.Markdown("**融合强度**")
                opacity_sl = gr.Slider(
                    minimum=0.5, maximum=1.0, value=1.0, step=0.05,
                    label="不透明度",
                )

        with gr.Accordion("使用说明 & 渲染原理", open=False):
            gr.Markdown("""
| 步骤 | 操作 |
|---|---|
| 1 | 上传**单手**照片（五指展开、掌心向下） |
| 2 | 点击「AI 分析 & 推荐」，检测指甲、分析肤色手型 |
| 3 | 系统用余弦相似度从数据库匹配 Top-5 款式 |
| 4 | 点击缩略图，系统提取真实甲片 BGRA 纹理（含透明通道） |
| 5 | 透视变换将甲片贴合指甲轮廓（保留颜色/花纹/渐变/光泽） |
| 6 | 自动添加高光、边缘阴影，模拟真实甲片厚度感 |
| 7 | 大拇指自动检测侧视角，进行透视压缩处理 |

**渲染核心**：Homography 透视变换（非简单缩放），完整保留款式图中的图案、渐变、猫眼、闪粉效果。
BGRA 提取确保甲片背景完全透明，不污染用户皮肤区域。
            """)

        # ── Event bindings ────────────────────────────────────────────────
        analyze_btn.click(
            fn=analyze_and_recommend,
            inputs=[input_img],
            outputs=[status_box, skin_box, hand_box, shape_box,
                     tip_box, gallery, state],
        )
        gallery.select(
            fn=on_gallery_select,
            inputs=[state],
            outputs=[result_img, selected_lbl],
        )
        shape_radio.change(
            fn=on_shape_change,
            inputs=[shape_radio, state],
            outputs=[result_img],
        )
        opacity_sl.change(
            fn=on_opacity_change,
            inputs=[opacity_sl, state],
            outputs=[result_img],
        )
        style_dd.change(
            fn=on_style_dropdown,
            inputs=[style_dd, state],
            outputs=[result_img, selected_lbl],
        )
        fb_dislike_btn.click(
            fn=on_feedback_dislike,
            inputs=[state],
            outputs=[result_img, gallery, feedback_status],
        )
        fb_fake_btn.click(
            fn=on_feedback_fake,
            inputs=[state],
            outputs=[result_img, gallery, feedback_status],
        )
        fb_color_btn.click(
            fn=on_feedback_color,
            inputs=[state],
            outputs=[result_img, gallery, feedback_status],
        )

    return demo


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 62)
    print("  AI 美甲虚拟试戴系统")
    print(f"  MediaPipe:  {detector._mp_available}")
    print(f"  Style DB:   {nail_art_renderer.num_styles if nail_art_renderer else 0} styles")
    print("  Starting server...")
    print("=" * 62)

    demo = build_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        inbrowser=True,
        theme=gr.themes.Soft(primary_hue="pink", neutral_hue="slate"),
    )
