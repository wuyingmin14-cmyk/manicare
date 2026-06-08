# AI 美甲虚拟试戴系统

<div align="center">

![Nail Try-On](https://img.shields.io/badge/AI-Nail%20Virtual%20Try%20On-brightgreen)
![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)

一个完整的AI美甲虚拟试戴系统实现，包括肤色识别、手型分析、指甲形状推荐和颜色匹配。

[快速开始](#-快速开始) • [功能特性](#-功能特性) • [文档](#-文档) • [示例](#-示例)

</div>

---

## ✨ 功能特性

### 🎨 肤色自动适配
- 自动检测用户肤色 (冷白皮/暖黄皮/偏黑/中性)
- 分析色调、饱和度、明度
- 基于肤色推荐显白或协调色系

### 🖐️ 手型智能识别
- 从21个关键点分析手部形态
- 分类为短粗手、标准手、细长手
- 为不同手型推荐最适合的指甲形状

### 💅 指甲形状变形
- 支持5种指甲形状：方形、圆形、椭圆、杏仁形、棺材形
- 自动调整指甲轮廓
- 保持自然外观

### 🎯 智能推荐引擎
- 结合肤色 + 手型 + 流行趋势
- 生成个性化推荐
- 输出可读的推荐报告

### 📊 颜色数据库
- 从美甲样图提取主色调
- 使用KMeans聚类提取特征
- 快速查询兼容的美甲款式

---

## 🚀 快速开始

### 环境要求
- Python 3.8+
- pip 或 conda

### 安装

```bash
# 克隆项目
cd nail_virtual_try_on

# 安装依赖
pip install -r requirements.txt
```

### 最小示例

```python
from pipeline import NailRecommendationPipeline
import cv2

# 初始化管道
pipeline = NailRecommendationPipeline()

# 读取手部照片
hand_image = cv2.imread('your_hand.jpg')

# 生成推荐
recommendation = pipeline.recommend_nails(hand_image)

# 查看推荐报告
print(recommendation['report'])
```

### 完整示例

```bash
# 运行所有示例（包括肤色分析、手型识别等）
python examples.py

# 处理Excel数据并构建颜色数据库
python process_data.py --excel DATA.xlsx --output ./output --build-db
```

---

## 📦 项目结构

```
nail_virtual_try_on/
├── modules/                          # 核心模块
│   ├── __init__.py
│   ├── skin_analysis.py             # 肤色分析
│   ├── hand_shape_analysis.py       # 手型识别
│   ├── nail_shape_transform.py      # 指甲形状变形
│   ├── color_database.py            # 颜色数据库
│   ├── recommendation_engine.py     # 推荐引擎
│   └── data_loader.py               # 数据加载
├── pipeline.py                       # 完整集成管道
├── config.py                         # 配置文件
├── process_data.py                  # 数据处理脚本
├── examples.py                       # 完整示例
├── INTEGRATION_GUIDE.md             # 详细集成指南
├── requirements.txt                 # 依赖列表
├── cache/                           # 缓存目录
├── data/                            # 数据目录
└── output/                          # 输出目录
```

---

## 📖 核心模块说明

### 1️⃣ 肤色分析 (SkinAnalyzer)

```python
from modules.skin_analysis import SkinAnalyzer

analyzer = SkinAnalyzer()

# 分析肤色
result = analyzer.analyze(hand_image, hand_mask)

print(result['tone_classification']['skin_type'])  # 'warm_yellow'
print(result['color_stats']['avg_hsv'])             # [25.5, 120.3, 165.8]
```

**输出肤色类型**：
- `warm_yellow` - 暖黄皮 → 推荐冷色系
- `cool_white` - 冷白皮 → 推荐酒红/深紫
- `dark_skin` - 深肤色 → 推荐亮色/对比色
- `neutral` - 中性 → 百搭色

### 2️⃣ 手型识别 (HandShapeAnalyzer)

```python
from modules.hand_shape_analysis import HandShapeAnalyzer

analyzer = HandShapeAnalyzer()

# 分析手型 (21个关键点)
result = analyzer.analyze(landmarks)

print(result['classification']['hand_type'])         # 'short_wide'
print(result['nail_shape_recommendations']['primary']) # 'oval'
```

**手型分类**：
- `short_wide` - 短粗手 → 推荐椭圆形（视觉拉长）
- `standard` - 标准手 → 推荐通用形状
- `long_thin` - 细长手 → 推荐方形（平衡）

### 3️⃣ 指甲形状变形 (NailShapeTransformer)

```python
from modules.nail_shape_transform import NailShapeTransformer

transformer = NailShapeTransformer()

# 转换单个指甲
almond_mask = transformer.transform_to_shape(nail_mask, 'almond')

# 一组指甲变形
transformed = transformer.transform_nail_set(nail_masks, 'oval')

# 预览所有形状
previews = transformer.preview_shapes(nail_mask)
```

**支持形状**：square, round, oval, almond, coffin

### 4️⃣ 颜色数据库 (ColorDatabase)

```python
from modules.color_database import ColorDatabase

db = ColorDatabase()

# 添加款式
db.add_style(1, 'style1.jpg', 'http://example.com/style1')

# 查找兼容款式
skin_hsv = [25, 100, 150]
recommendations = db.find_compatible_styles(
    skin_hsv, 
    search_type='high_contrast',
    top_n=5
)

# 保存数据库
db.save_database()
```

### 5️⃣ 推荐引擎 (RecommendationEngine)

```python
from modules.recommendation_engine import RecommendationEngine

engine = RecommendationEngine(color_database)

# 生成推荐
recommendations = engine.generate_recommendations(
    skin_analysis,
    hand_analysis
)

# 生成报告
report = engine.generate_report(recommendations)
print(report)
```

---

## 🔌 与现有系统集成

### 与美甲渲染模块集成

```python
# 1. 检测手部 (用MediaPipe/HRNet)
landmarks = hand_detector.get_landmarks(user_image)
hand_mask = hand_detector.get_mask(user_image)

# 2. 分割指甲 (已有模块)
nail_masks = nail_segmentor.segment(user_image)

# 3. 生成推荐 (新模块)
pipeline = NailRecommendationPipeline()
recommendation = pipeline.recommend_nails(
    hand_image=user_image,
    landmarks=landmarks,
    hand_mask=hand_mask,
    nail_masks=nail_masks
)

# 4. 传递给渲染器
renderer = NailRenderer()
result = renderer.render(
    hand_image=user_image,
    nail_shape=recommendation['nail_shape'],
    style_id=recommendation['style_id']
)
```

---

## 📊 完整流程

```
用户上传照片
    ↓
[手部检测] (已有)
    ↓
[指甲分割] (已有)
    ↓
肤色分析 → 肤色类型 → 颜色推荐
    ↓
手型识别 → 手型分类 → 甲型推荐
    ↓
颜色数据库查询 → 兼容款式
    ↓
推荐引擎综合
    ↓
输出推荐结果
    ├─ 推荐指甲形状
    ├─ 推荐颜色
    ├─ 推荐款式URL
    └─ 推荐报告
    ↓
渲染模块 → 试戴效果图
```

---

## 🎯 使用场景

### 📱 Web应用

```python
from flask import Flask, request
pipeline = NailRecommendationPipeline()

@app.route('/recommend', methods=['POST'])
def get_recommendation():
    image = request.files['image']
    # ... 处理 ...
    return pipeline.recommend_nails(image)
```

### 📹 实时视频处理

```python
import mediapipe as mp

cap = cv2.VideoCapture(0)
detector = mp.solutions.hands.Hands()

while True:
    ret, frame = cap.read()
    results = detector.process(frame)
    
    if results.multi_hand_landmarks:
        recommendation = pipeline.recommend_nails(
            hand_image=frame,
            landmarks=results.multi_hand_landmarks[0]
        )
```

### 📊 批量数据处理

```python
loader = DataLoader('DATA.xlsx')
hand_dataset, style_dataset = loader.get_all_data()

results = pipeline.batch_recommend([
    {'image': h['hand_img']} for h in hand_dataset
])
```

---

## 📈 性能指标

| 操作 | 耗时 | 备注 |
|-----|-----|------|
| 肤色分析 | 50-100ms | 颜色空间转换 |
| 手型分析 | 10-20ms | 关键点计算 |
| 颜色查询 | 5-10ms | 数据库查询 |
| **总耗时** | **100-200ms** | 单个请求 |

---

## 🛠️ 配置

编辑 `config.py` 自定义参数：

```python
# 肤色分类阈值
SKIN_TONE_THRESHOLDS = {
    'brightness_dark': 50,
    'brightness_light': 180,
    'hue_warm_min': 10,
    'hue_warm_max': 40,
}

# 手型分类参数
HAND_SHAPE_PARAMS = {
    'short_wide_threshold': 2.0,
    'long_thin_threshold': 3.0,
}

# 推荐参数
TOP_N_RECOMMENDATIONS = 5
SIMILARITY_THRESHOLD = 0.3
```

---

## 📚 详细文档

完整的集成指南、API文档和示例代码，请查看：

📖 **[INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md)** - 包含：
- 详细的模块API说明
- 输入输出格式规范
- 集成步骤和示例代码
- 常见问题解答
- 性能优化建议

---

## 💡 示例代码

### 示例1：基础肤色分析

```python
from modules.skin_analysis import SkinAnalyzer
import cv2

analyzer = SkinAnalyzer()
img = cv2.imread('hand.jpg')
result = analyzer.analyze(img)

print(f"Skin Type: {result['tone_classification']['skin_type']}")
```

### 示例2：完整推荐

```python
from pipeline import NailRecommendationPipeline
import cv2

pipeline = NailRecommendationPipeline(
    color_db_path='./cache/style_color_db.json'
)

recommendation = pipeline.recommend_nails(
    hand_image=cv2.imread('hand.jpg')
)

print(recommendation['report'])
```

### 示例3：处理Excel数据

```bash
python process_data.py \
    --excel ./DATA.xlsx \
    --cache ./cache \
    --output ./output \
    --build-db
```

更多示例详见 `examples.py`

---

## 🔧 故障排除

### 问题：ImageNotFoundError

**原因**：图片URL无法访问或网络问题

**解决**：
```python
# 使用本地图片替代
loader = DataLoader('DATA.xlsx', cache_dir='./cache')
# 数据会缓存在 ./cache 目录
```

### 问题：空的推荐结果

**原因**：颜色数据库为空或未加载

**解决**：
```python
# 构建颜色数据库
python process_data.py --excel DATA.xlsx --build-db

# 或手动加载
pipeline = NailRecommendationPipeline(
    color_db_path='./cache/style_color_db.json'
)
```

### 问题：低准确度

**原因**：输入数据质量不足

**改进**：
```python
# 提供完整的输入数据
recommendation = pipeline.recommend_nails(
    hand_image=img,
    hand_mask=mask,        # 提供mask
    landmarks=landmarks,   # 提供关键点
    nail_masks=nail_masks  # 提供指甲mask
)
```

---

## 📝 数据格式

### 输入

| 参数 | 类型 | 格式 | 备注 |
|-----|------|------|------|
| hand_image | ndarray | (H,W,3) BGR | uint8 |
| hand_mask | ndarray | (H,W) 二值图 | uint8 |
| landmarks | ndarray | (21,2) 坐标 | float32 |
| nail_masks | Dict | {'thumb': mask, ...} | uint8 |

### 输出

返回JSON格式字典，包含：
```json
{
  "status": "success",
  "components": {...},
  "recommendations": {...},
  "style_recommendations": {...},
  "report": "..."
}
```

详见 [INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md#输入输出格式规范)

---

## 🤝 贡献

欢迎提交Issue和Pull Request！

---

## 📄 许可证

MIT License - 详见 [LICENSE](./LICENSE)

---

## 📞 联系方式

- 📧 Email: support@example.com
- 🐛 Issues: [GitHub Issues](https://github.com/example/issues)
- 📖 Wiki: [Documentation](./INTEGRATION_GUIDE.md)

---

## 🙏 致谢

感谢以下开源项目的支持：
- [MediaPipe](https://github.com/google/mediapipe) - 手部检测
- [OpenCV](https://opencv.org/) - 图像处理
- [scikit-learn](https://scikit-learn.org/) - 机器学习

---

<div align="center">

**Made with ❤️ by AI Nail Team**

⭐ 如果对你有帮助，请给个Star！

</div>
