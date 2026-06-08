# AI 美甲虚拟试戴系统 - 完整集成指南

## 📋 项目概述

本项目实现了一个完整的AI美甲虚拟试戴系统的核心模块，包括：

1. **肤色自动适配模块** - 分析用户肤色并推荐最适合的美甲颜色
2. **手型识别与甲型推荐** - 基于手部形态推荐最适合的指甲形状
3. **甲型几何变形模块** - 支持多种指甲形状的视觉变形
4. **颜色数据库系统** - 管理美甲款式的颜色特征
5. **推荐引擎** - 生成个性化的美甲推荐
6. **完整的数据处理流程** - 从Excel导入数据到生成推荐

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd nail_virtual_try_on
pip install -r requirements.txt
```

### 2. 运行示例

```bash
# 运行完整示例（无需真实数据）
python examples.py

# 处理Excel数据并构建系统
python process_data.py --excel /path/to/DATA.xlsx --output ./output --build-db
```

### 3. 集成到现有系统

```python
from pipeline import NailRecommendationPipeline
import cv2

# 初始化管道
pipeline = NailRecommendationPipeline(
    color_db_path='./cache/style_color_db.json'
)

# 读取用户手部照片
hand_image = cv2.imread('user_hand.jpg')
hand_mask = cv2.imread('hand_mask.jpg', 0)

# 从MediaPipe获取21个手部关键点
# landmarks = mediapipe_hand_detector.get_landmarks(hand_image)

# 生成推荐
recommendations = pipeline.recommend_nails(
    hand_image=hand_image,
    hand_mask=hand_mask,
    landmarks=landmarks  # 可选
)

# 获取结果
print(recommendations['report'])  # 打印推荐报告
```

---

## 📦 模块说明

### 模块1：肤色分析 (skin_analysis.py)

#### 主要功能
- 从手部图像提取肤色特征
- 将肤色分类为：冷白皮、暖黄皮、偏黑皮、中性色
- 生成肤色推荐参数

#### API 接口

```python
from modules.skin_analysis import SkinAnalyzer

analyzer = SkinAnalyzer()

# 分析肤色
result = analyzer.analyze(hand_image, hand_mask)

# 结果结构
{
    'color_stats': {
        'avg_hsv': [h, s, v],
        'brightness': value,
        'saturation': value,
        'hue': value,
    },
    'tone_classification': {
        'skin_type': 'warm_yellow'|'cool_white'|'dark_skin'|'neutral',
        'is_warm': bool,
        'is_cool': bool,
        'is_dark': bool,
    }
}
```

#### 输入输出例子

```python
# 输入
image = cv2.imread('hand.jpg')  # RGB BGR format
mask = cv2.imread('hand_mask.jpg', 0)  # Binary mask

# 分析
analyzer = SkinAnalyzer()
color_stats = analyzer.extract_skin_color(image, mask)
tone = analyzer.classify_skin_tone(color_stats['avg_hsv'])

# 输出
print(tone['skin_type'])  # 'warm_yellow'
print(color_stats['avg_hsv'])  # [25.5, 120.3, 165.8]
```

---

### 模块2：手型识别 (hand_shape_analysis.py)

#### 主要功能
- 从MediaPipe的21个关键点分析手部形态
- 计算手指长宽比
- 分类为：短粗手、细长手、标准手
- 推荐最适合的指甲形状

#### 媒体管道手部关键点格式

```
0:  wrist          (腕部)
1-4:   thumb       (大拇指)
5-8:   index       (食指)
9-12:  middle      (中指)
13-16: ring        (无名指)
17-20: pinky       (小指)
```

#### API 接口

```python
from modules.hand_shape_analysis import HandShapeAnalyzer

analyzer = HandShapeAnalyzer()

# 分析手型 (landmarks: 21x2 array)
result = analyzer.analyze(landmarks)

# 结果结构
{
    'classification': {
        'hand_type': 'short_wide'|'long_thin'|'standard',
        'average_ratio': 2.5,
    },
    'nail_shape_recommendations': {
        'primary_recommendation': 'oval',
        'secondary_options': ['almond', 'coffin'],
        'reasoning': 'Oval shapes visually elongate short fingers',
    }
}
```

#### 手型分类规则

| 长宽比 | 手型 | 推荐指甲形状 |
|-------|------|-----------|
| < 2.0 | 短粗手 | oval, round |
| 2.0-3.0 | 标准手 | oval, almond, coffin |
| > 3.0 | 细长手 | square, round |

---

### 模块3：指甲形状变形 (nail_shape_transform.py)

#### 主要功能
- 将指甲mask转换为不同的形状
- 支持：square, round, oval, almond, coffin
- 自动平滑边缘

#### API 接口

```python
from modules.nail_shape_transform import NailShapeTransformer

transformer = NailShapeTransformer()

# 单个指甲变形
nail_mask = cv2.imread('nail_mask.jpg', 0)
almond_shape = transformer.transform_to_shape(nail_mask, 'almond', smooth=True)

# 一组指甲变形
nail_masks = {
    'thumb': mask1,
    'index': mask2,
    'middle': mask3,
    'ring': mask4,
    'pinky': mask5,
}
transformed = transformer.transform_nail_set(nail_masks, 'oval')

# 预览所有形状
previews = transformer.preview_shapes(nail_mask)
for shape_name, mask in previews.items():
    print(f"{shape_name}: {np.sum(mask > 0)} pixels")
```

---

### 模块4：颜色数据库 (color_database.py)

#### 主要功能
- 从美甲图像提取主色调
- 构建美甲款式的颜色数据库
- 根据肤色查找兼容的美甲款式

#### API 接口

```python
from modules.color_database import ColorDatabase

db = ColorDatabase(cache_dir='./cache')

# 添加单个款式
db.add_style(
    style_id=1,
    image_path='style_1.jpg',
    style_url='http://example.com/style1'
)

# 批量添加
styles = [
    {'id': 1, 'path': 'style1.jpg', 'url': 'http://...'},
    {'id': 2, 'path': 'style2.jpg', 'url': 'http://...'},
]
db.batch_add_styles(styles)

# 保存数据库
db.save_database('./cache/style_color_db.json')

# 加载数据库
db.load_database('./cache/style_color_db.json')

# 查找兼容款式
skin_hsv = [25, 100, 150]
high_contrast = db.find_compatible_styles(skin_hsv, 'high_contrast', top_n=5)
harmonious = db.find_compatible_styles(skin_hsv, 'harmonious', top_n=5)

# 结果格式
[
    {
        'style_id': 1,
        'score': 0.85,
        'url': 'http://example.com/style1',
        'dominant_colors': [[25, 100, 200], ...],
    },
    ...
]
```

#### 颜色兼容性策略

**高对比（显白）**
- 选择与肤色明度相差大的颜色
- 倾向于高饱和度的颜色

**协调（和谐）**
- 选择与肤色相似色调的颜色
- 形成统一的色系搭配

---

### 模块5：推荐引擎 (recommendation_engine.py)

#### 主要功能
- 结合肤色和手型数据
- 生成个性化的美甲推荐
- 输出可读的推荐报告

#### API 接口

```python
from modules.recommendation_engine import RecommendationEngine

engine = RecommendationEngine(color_database)

# 生成综合推荐
recommendations = engine.generate_recommendations(
    skin_analysis=skin_result,
    hand_analysis=hand_result,
    style_preferences=None
)

# 结果结构
{
    'user_profile': {
        'skin_type': 'warm_yellow',
        'hand_type': 'short_wide',
    },
    'combined_recommendations': [
        {
            'priority': 'primary',
            'nail_shape': 'oval',
            'skin_compatibility': {
                'best_colors': ['cool_pink', 'deep_blue'],
            },
            'overall_score': 0.9,
        },
        ...
    ]
}

# 生成可读报告
report = engine.generate_report(recommendations)
print(report)
```

---

### 模块6：完整管道 (pipeline.py)

#### 主要功能
- 集成所有模块
- 端到端处理用户请求
- 缓存和性能优化

#### API 接口

```python
from pipeline import NailRecommendationPipeline

# 初始化
pipeline = NailRecommendationPipeline(
    color_db_path='./cache/style_color_db.json',
    cache_dir='./cache'
)

# 单个推荐
result = pipeline.recommend_nails(
    hand_image=hand_img,           # numpy array BGR
    hand_mask=hand_mask,           # optional binary mask
    landmarks=landmarks,           # optional 21x2 array
    nail_masks=nail_masks          # optional dict of masks
)

# 批量推荐
results = pipeline.batch_recommend(
    hand_images=[
        {'image': img1, 'mask': mask1, 'landmarks': lm1},
        {'image': img2, 'mask': mask2, 'landmarks': lm2},
    ]
)

# 导出结果
pipeline.export_results(result, './output')
```

---

### 模块7：数据加载器 (data_loader.py)

#### 主要功能
- 从Excel读取数据
- 下载在线图片
- 处理数据集

#### API 接口

```python
from modules.data_loader import DataLoader

loader = DataLoader('./DATA.xlsx', cache_dir='./cache')

# 加载所有数据
hand_dataset, style_dataset = loader.get_all_data()

# 手部数据集结构
hand_dataset = [
    {
        'hand_id': 0,
        'hand_url': 'http://...',
        'style_url': 'http://...',
        'hand_img': numpy_array,
        'style_img': numpy_array,
    },
    ...
]

# 款式数据集结构
style_dataset = [
    {
        'style_id': 0,
        'raw_url': 'http://...',
        'enhanced_url': 'http://...',
        'raw_img': numpy_array,
        'enhanced_img': numpy_array,
    },
    ...
]
```

---

## 🔧 数据处理流程

### 完整流程

```
1. Excel数据 (DATA.xlsx)
   ↓
2. DataLoader (下载图片，缓存)
   ↓
3. ColorDatabase (提取颜色，建立索引)
   ↓
4. 用户输入
   ├─ 手部图像
   ├─ 手部mask
   └─ 手部关键点
   ↓
5. SkinAnalyzer (肤色分析)
   ↓
6. HandShapeAnalyzer (手型分析)
   ↓
7. NailShapeTransformer (形状推荐)
   ↓
8. RecommendationEngine (综合推荐)
   ↓
9. 输出
   ├─ 推荐报告
   ├─ 推荐款式URL
   ├─ 推荐指甲形状
   └─ 推荐颜色
```

### 执行脚本

```bash
# 完整数据处理
python process_data.py \
    --excel /path/to/DATA.xlsx \
    --cache ./cache \
    --output ./output \
    --build-db

# 输出文件
./output/
├── color_db_statistics.json          # 颜色库统计
├── hand_analysis_results.json        # 手部分析结果
├── recommendations.json              # 推荐结果
├── test_interface.json              # 测试接口数据
└── hand_dataset_meta.json           # 数据集元数据
```

---

## 💻 与现有系统集成

### 集成到美甲渲染模块

```python
# 1. 用户上传手部照片
user_image = upload_hand_photo()

# 2. 获取手部检测结果 (来自MediaPipe或HRNet)
detector = MediaPipeHandDetector()
landmarks = detector.get_landmarks(user_image)
hand_mask = detector.get_hand_mask(user_image)

# 3. 获取指甲分割结果
segmentor = NailSegmentor()
nail_masks = segmentor.segment_nails(user_image, hand_mask)

# 4. 使用推荐系统
pipeline = NailRecommendationPipeline()
recommendations = pipeline.recommend_nails(
    hand_image=user_image,
    hand_mask=hand_mask,
    landmarks=landmarks,
    nail_masks=nail_masks
)

# 5. 传递给渲染模块
render_engine = NailRenderEngine()

# 自动渲染推荐配置
recommended_nail_shape = recommendations['recommendations'][
    'nail_shape_recommendations'
]['primary_recommendation']

recommended_color = recommendations['style_recommendations'][
    'high_contrast'
][0]['style_id']

# 渲染
result = render_engine.render(
    hand_image=user_image,
    nail_masks=nail_masks,
    nail_shape=recommended_nail_shape,
    style_id=recommended_color
)

# 保存结果
save_visualization(result)
```

---

## 📊 输入输出格式规范

### 输入格式

#### 手部图像
- 格式：numpy array (H, W, 3) or (H, W, 4)
- 颜色空间：BGR（OpenCV默认）
- 类型：uint8
- 分辨率：无特殊要求，建议 ≥ 320x240

#### 手部mask
- 格式：numpy array (H, W)
- 值：0 或 255（二值图）
- 类型：uint8
- 大小：与手部图像相同

#### 手部关键点
- 格式：numpy array (21, 2) 或 (21, 3)
- 坐标系：图像坐标 (x, y) 或 (x, y, z)
- 类型：float32
- 范围：图像尺寸内

#### 指甲mask
- 格式：Dict[str, numpy array]
- 键：'thumb', 'index', 'middle', 'ring', 'pinky'
- 值：二值图 (H, W)

### 输出格式

#### 推荐结果 JSON

```json
{
  "status": "success",
  "components": {
    "skin_analysis": {
      "skin_type": "warm_yellow",
      "avg_hsv": [25.5, 120.3, 165.8]
    },
    "hand_analysis": {
      "hand_type": "short_wide",
      "average_ratio": 1.8
    },
    "nail_transform": {
      "recommended_shape": "oval",
      "transformed_masks": {"thumb": [100, 50], ...}
    }
  },
  "recommendations": {
    "user_profile": {
      "skin_type": "warm_yellow",
      "hand_type": "short_wide"
    },
    "combined_recommendations": [
      {
        "priority": "primary",
        "nail_shape": "oval",
        "skin_compatibility": {
          "best_colors": ["cool_pink", "deep_blue"],
          "avoid_colors": ["warm_brown"],
          "reasoning": "..."
        },
        "overall_score": 0.9
      }
    ]
  },
  "style_recommendations": {
    "high_contrast": [
      {
        "style_id": 1,
        "score": 0.85,
        "url": "http://example.com/style1",
        "properties": {"brightness": 180, "contrast": 100}
      }
    ],
    "harmonious": [...]
  },
  "report": "===== PERSONALIZED NAIL RECOMMENDATION ====="
}
```

---

## 🎯 使用场景

### 场景1：Web应用集成

```python
# Flask应用示例
from flask import Flask, request, jsonify
from pipeline import NailRecommendationPipeline
import cv2
import numpy as np

app = Flask(__name__)
pipeline = NailRecommendationPipeline()

@app.route('/api/recommend', methods=['POST'])
def get_recommendation():
    # 接收图片
    image_file = request.files['image']
    image = cv2.imdecode(
        np.frombuffer(image_file.read(), np.uint8), 
        cv2.IMREAD_COLOR
    )
    
    # 生成推荐
    result = pipeline.recommend_nails(hand_image=image)
    
    return jsonify(result)
```

### 场景2：批量处理

```python
# 批量处理数据集
hand_dataset = loader.process_hand_dataset(sheets)

results = pipeline.batch_recommend([
    {
        'image': hand['hand_img'],
        'landmarks': get_landmarks(hand['hand_img'])
    }
    for hand in hand_dataset
])

# 统计分析
skin_types = [r['components']['skin_analysis']['skin_type'] 
              for r in results if r['status'] == 'success']
print(f"Warm skin: {skin_types.count('warm_yellow')}")
print(f"Cool skin: {skin_types.count('cool_white')}")
```

### 场景3：实时推荐

```python
# 实时视频处理
import mediapipe as mp

cap = cv2.VideoCapture(0)
detector = mp.solutions.hands.Hands()
pipeline = NailRecommendationPipeline()

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # 检测手部
    results = detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    
    if results.multi_hand_landmarks:
        landmarks = results.multi_hand_landmarks[0].landmark
        landmarks = np.array([(lm.x, lm.y) for lm in landmarks])
        
        # 生成推荐
        recommendation = pipeline.recommend_nails(
            hand_image=frame,
            landmarks=landmarks
        )
        
        # 显示结果
        skin_type = recommendation['components']['skin_analysis']['skin_type']
        cv2.putText(frame, f"Skin: {skin_type}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow('Nail Recommendation', frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
```

---

## ⚙️ 配置参数

### config.py 关键参数

```python
# 肤色分类阈值
SKIN_TONE_THRESHOLDS = {
    'hue_warm_min': 10,      # 暖色最小色调
    'hue_warm_max': 40,      # 暖色最大色调
    'hue_cool_min': 270,     # 冷色最小色调
    'hue_cool_max': 360,     # 冷色最大色调
    'brightness_dark': 50,   # 暗肤色明度阈值
    'brightness_light': 180, # 亮肤色明度阈值
}

# 手型分类参数
HAND_SHAPE_PARAMS = {
    'short_wide_threshold': 2.0,   # 短粗手长宽比阈值
    'long_thin_threshold': 3.0,    # 细长手长宽比阈值
}

# 推荐参数
TOP_N_RECOMMENDATIONS = 5          # 返回前N条推荐
SIMILARITY_THRESHOLD = 0.3         # 颜色相似度阈值
KMEANS_CLUSTERS = 5                # 颜色聚类数
```

---

## 📈 性能优化

### 缓存策略

```python
# 自动缓存已处理的图片
pipeline = NailRecommendationPipeline(cache_dir='./cache')

# 使用缓存的颜色数据库
pipeline.color_database.load_database('./cache/style_color_db.json')

# 缓存手部关键点
with open('./cache/hand_landmarks.json', 'w') as f:
    json.dump(landmarks.tolist(), f)
```

### 性能指标

| 操作 | 耗时 (ms) | 备注 |
|-----|----------|------|
| 肤色分析 | 50-100 | 包括颜色空间转换 |
| 手型分析 | 10-20 | 仅计算，不涉及图像处理 |
| 颜色数据库查询 | 5-10 | 取决于数据库大小 |
| 推荐生成 | 20-30 | 综合计算 |
| **总耗时** | **100-200** | 单个请求 |

---

## 🐛 常见问题

### Q1: 如何处理没有手部mask的情况？

```python
# mask为可选参数，如果不提供会使用整个图像
result = pipeline.recommend_nails(hand_image=img)  # 有效
```

### Q2: 如何处理没有关键点的情况？

```python
# landmarks为可选参数，如果不提供会使用默认手型
result = pipeline.recommend_nails(
    hand_image=img,
    hand_mask=mask
    # 不提供landmarks，将使用默认值
)
```

### Q3: 如何自定义颜色推荐规则？

```python
# 修改 COLOR_RECOMMENDATION_RULES 在 config.py
COLOR_RECOMMENDATION_RULES = {
    'warm_yellow': {
        'high_contrast': ['custom_color1', 'custom_color2'],
        'harmonious': ['custom_color3'],
    },
    ...
}
```

### Q4: 如何提高推荐准确度？

```python
# 1. 提供完整的输入（mask + landmarks）
# 2. 使用高质量的手部图像
# 3. 确保颜色数据库足够大
# 4. 定期更新颜色数据库

# 构建更大的数据库
loader = DataLoader('./DATA.xlsx')
hand_dataset, style_dataset = loader.get_all_data()

pipeline.build_color_database_from_styles(style_dataset)
```

---

## 📚 API 快速参考

### 快速调用表

```python
# 1. 初始化
from pipeline import NailRecommendationPipeline
pipeline = NailRecommendationPipeline()

# 2. 准备输入
hand_image = cv2.imread('hand.jpg')
hand_mask = cv2.imread('mask.jpg', 0)
landmarks = np.array([...])  # 21x2

# 3. 生成推荐
result = pipeline.recommend_nails(
    hand_image=hand_image,
    hand_mask=hand_mask,
    landmarks=landmarks
)

# 4. 提取结果
skin_type = result['components']['skin_analysis']['skin_type']
nail_shape = result['recommendations']['combined_recommendations'][0]['nail_shape']
style_urls = [s['url'] for s in result['style_recommendations']['high_contrast']]

# 5. 导出
pipeline.export_results(result, './output')
```

---

## 🔗 相关资源

- MediaPipe Hands: https://github.com/google/mediapipe/blob/master/docs/solutions/hands.md
- OpenCV 文档: https://docs.opencv.org/
- scikit-learn 文档: https://scikit-learn.org/

---

## 📝 版本历史

- v1.0 (2024-06) - 初始发布，包含所有5个核心模块

---

## 📄 许可证

MIT License

---

## 💬 支持

有问题？提交Issue或联系技术支持。

**更新时间**: 2024年6月
**维护者**: AI美甲团队
