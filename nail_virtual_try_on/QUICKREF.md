# 🚀 快速参考卡片

## 最常用的3个命令

```bash
# 1. 运行示例（无需数据）
python examples.py

# 2. 处理Excel数据
python process_data.py --excel DATA.xlsx --build-db

# 3. 生成推荐
python -c "
from pipeline import NailRecommendationPipeline
import cv2
pipeline = NailRecommendationPipeline()
result = pipeline.recommend_nails(cv2.imread('hand.jpg'))
print(result['report'])
"
```

---

## 最常用的3个API

### API 1：完整推荐（推荐）

```python
from pipeline import NailRecommendationPipeline

pipeline = NailRecommendationPipeline()
result = pipeline.recommend_nails(hand_image)
print(result['report'])
```

### API 2：肤色分析

```python
from modules.skin_analysis import SkinAnalyzer

analyzer = SkinAnalyzer()
result = analyzer.analyze(hand_image, hand_mask)
print(result['tone_classification']['skin_type'])
```

### API 3：手型识别

```python
from modules.hand_shape_analysis import HandShapeAnalyzer

analyzer = HandShapeAnalyzer()
result = analyzer.analyze(landmarks)
print(result['classification']['hand_type'])
```

---

## 输出结构速查

```json
{
  "status": "success",
  "components": {
    "skin_analysis": {
      "skin_type": "warm_yellow|cool_white|dark_skin|neutral",
      "avg_hsv": [h, s, v]
    },
    "hand_analysis": {
      "hand_type": "short_wide|standard|long_thin",
      "average_ratio": 2.5
    }
  },
  "recommendations": {
    "combined_recommendations": [
      {
        "nail_shape": "oval|square|round|almond|coffin",
        "skin_compatibility": {
          "best_colors": ["color1", "color2"]
        }
      }
    ]
  },
  "style_recommendations": {
    "high_contrast": [
      {
        "style_id": 1,
        "url": "http://...",
        "score": 0.85
      }
    ]
  }
}
```

---

## 肤色与推荐对应

| 肤色类型 | HSV特征 | 推荐颜色 |
|---------|--------|--------|
| warm_yellow | H: 10-40, 暖色调 | 冷粉、深蓝、紫色 |
| cool_white | H: 270-360, 冷色调 | 酒红、深紫、高饱和 |
| dark_skin | V < 50, 暗色 | 亮红、金色、荧光 |
| neutral | 中性 | 百搭所有颜色 |

---

## 手型与指甲形状对应

| 手型 | 长宽比 | 推荐形状 | 理由 |
|-----|-------|--------|------|
| short_wide | < 2.0 | oval, round | 视觉拉长 |
| standard | 2.0-3.0 | oval, almond, coffin | 通用 |
| long_thin | > 3.0 | square, round | 视觉平衡 |

---

## 目录结构

```
nail_virtual_try_on/
├── modules/              # 核心模块
├── pipeline.py          # 主管道
├── config.py            # 配置
├── examples.py          # 示例
├── process_data.py      # 数据处理
├── README.md            # 说明
├── INTEGRATION_GUIDE.md # 详细文档
├── PROJECT_SUMMARY.md   # 完整总结
└── QUICKREF.md          # 本文件
```

---

## 问题速解

| 问题 | 解决方案 |
|-----|---------|
| ModuleNotFoundError | `pip install -r requirements.txt` |
| 空推荐结果 | `python process_data.py --build-db` |
| 低准确度 | 提供 mask + landmarks |
| 颜色库查询慢 | 减少数据库大小或优化查询参数 |

---

## 性能目标

- ⏱️ 单个推荐：< 200ms
- 💾 内存占用：< 100MB
- 📊 准确率：> 85%（主观评价）

---

## 下一步

1. 📥 **数据准备** - 从Excel导入数据
2. 🔨 **构建数据库** - `python process_data.py --build-db`
3. ✅ **测试系统** - `python examples.py`
4. 🔗 **集成系统** - 调用 `NailRecommendationPipeline`
5. 📊 **监控效果** - 检查推荐准确度

---

**提示**：更多详情请查看 `INTEGRATION_GUIDE.md`
