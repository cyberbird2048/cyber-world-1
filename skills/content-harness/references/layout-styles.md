# 排版风格参考库

> 从参考作者的高质量文章中提炼的视觉排版规律。
> Stage 6.7 自动匹配时读取此文件。每次作者动态分析后由 /author-update 更新。
>
> **数据来源说明：**
> - 标注 `[初始值]` 的条目：基于训练知识的初始估计，**未经真实扫描验证**
> - 标注 `[实测 YYYY-MM-DD N篇]` 的条目：由 `analyze_layout.py` 从真实抓取的文章 HTML 中提取
>
> 更新方式：运行 `/author-update` → 对每篇抓取的文章执行 `analyze_layout.py --update-layout-styles`

---

## 排版模板索引

| 模板名 | 适合文章类型 | 核心特征 | 参考作者 |
|--------|------------|---------|---------|
| `dense-prose` | opinion, news-reaction | 纯文字为主，段落紧凑，情绪递进 | 卡兹克, 刘小排 |
| `breathing-space` | life-reflection, creator-share | 段落短，白空间多，有呼吸感 | 赛博禅心, 花叔 |
| `structured-scan` | how-to, creator-share | 有序号/分节，内嵌截图，强可读性 | 花叔, 刘小排 |
| `image-anchored` | opinion, news-reaction | 关键论点处插图，图起到视觉锚点作用 | 卡兹克 |

---

## 模板详细规格

### dense-prose（紧凑叙述型）

**适用场景：** opinion 观点文、news-reaction 时效文

**段落规范：**
- 段落长度：4-8 句话，信息密度高
- 段落间距：标准行距，不加额外空行
- 分节方式：用 `---` 横线（而非 emoji 或加粗副标题）分隔大节
- 单句成段：每 3-4 段出现一次，作为情绪刹车

**图片使用：**
- 封面图必选（900×500，无文字）
- 正文插图：0-1 张，仅在论点需要视觉支撑时才插
- 插图位置：放在"文章中段最强论点"之后，居中显示

**字体/样式（微信公众号）：**
```css
p { font-size: 16px; line-height: 1.75; color: #333; margin-bottom: 1.5em; }
hr { border: none; border-top: 1px solid #eee; margin: 2em 0; }
```

**卡兹克特征（2026-04 观察）：**
- 开头第一段极短（1-2 句），直接抛核心
- 每个 `---` 分节后，第一句往往是反问或短判断
- 结尾段有意拉长，制造收束感

---

### breathing-space（呼吸留白型）

**适用场景：** life-reflection 反思文、creator-share 分享文

**段落规范：**
- 段落长度：2-4 句话，短而克制
- 段落间距：每段后加一空行（比默认更松）
- 分节方式：纯空白行分节，不用横线或符号
- 单句成段：频繁使用，每 2-3 段一次

**图片使用：**
- 封面图必选（900×500）
- 正文插图：1-2 张，放在情绪高点或低点处
- 插图风格：温暖、柔和，有生活感（非数据图/截图）

**字体/样式（微信公众号）：**
```css
p { font-size: 16px; line-height: 2.0; color: #444; margin-bottom: 2em; }
```

**赛博禅心特征（初始观察，待丰富）：**
- 大量使用短段和单句段落，制造呼吸感
- 情绪词语密度高，但不用夸张词
- 结尾常是一个开放性问句或邀请

---

### structured-scan（结构扫描型）

**适用场景：** how-to 教程文、creator-share 工具分享

**段落规范：**
- 主体用 1/2/3 编号或「」引用块区分
- 每个步骤/要点独立成段
- 段内可用加粗标记关键词

**图片使用：**
- 截图/实操图：每个关键步骤后 1 张（优先）
- 封面图 + 2-4 张步骤图为标准配置
- 图片全宽居中，有边框/圆角

**字体/样式（微信公众号）：**
```css
p { font-size: 16px; line-height: 1.75; color: #333; margin-bottom: 1.2em; }
strong { color: #111; }
```

**花叔特征（2026-04 观察）：**
- 标题用「工具名 + 动作词」格式
- 正文有清晰的 Before/After 对比结构
- 结尾有明确的"你可以现在就…"行动号召

---

### image-anchored（图片锚点型）

**适用场景：** opinion 深度观点、news-reaction 分析

**段落规范：**
- 与 dense-prose 相近，但每隔 3-4 段插一张图
- 图起到视觉分节作用，替代横线 `---`

**图片使用：**
- 插图 2-3 张（较多）
- 每张图必须对应一个明确的论点，不是纯装饰
- 图说（caption）可选，如有则简短（1 句话）

**字体/样式（微信公众号）：**
```css
p { font-size: 16px; line-height: 1.75; color: #333; margin-bottom: 1.5em; }
img { max-width: 100%; border-radius: 6px; margin: 1.5em auto; display: block; }
```

---

## 作者排版特征速查

### 数字生命卡兹克
- **首选模板：** `dense-prose` / `image-anchored`（opinion 用前者，news-reaction 用后者）
- **封面：** 抽象隐喻型（B方向），高对比度，有张力
- **插图：** 平均每 400-500 字 1 张，多为概念示意图或截图
- **特殊标记：** 重要判断句加粗，结尾段不分节

#### 数据采样 2026-04-14 — https://mp.weixin.qq.com/s?src=11&timestamp=1776154548&ver=6 [实测 1篇]
- 段落数: 137，均长 45 字
- 短段（≤30字）: 66 段（占比 48%）
- 图片: 26 张，分布 前/8 中/12 后/6
- 分节方式: whitespace（hr=0, 横线段=0）
- 强调: bold×19 blockquote×0
- CSS: font-size=None line-height=None color=rgb(255, 255, 255)
- **推断模板: `image-anchored`**

### AI进化论-花生（花叔）
- **首选模板：** `structured-scan` / `breathing-space`（how-to 用前者，creator-share 用后者）
- **封面：** 具象型（A方向），有人物或工具图标
- **插图：** 实操截图为主，每步骤 1 张
- **特殊标记：** 工具名用「」引用，功能描述用「→」连接

#### 数据采样 2026-04-14 — https://mp.weixin.qq.com/s?src=11&timestamp=1776145190&ver=6 [实测 2篇]
- 段落数: 89，均长 37 字
- 短段（≤30字）: 54 段（占比 61%）
- 图片: 25 张，分布 前/5 中/14 后/6
- 分节方式: whitespace（hr=0, 横线段=0）
- 强调: bold×27 blockquote×0
- CSS: font-size=14px line-height=1.3 color=rgb(29, 29, 27)
- **推断模板: `structured-scan`**

#### 数据采样 2026-04-14 — https://mp.weixin.qq.com/s?src=11&timestamp=1776155494 [实测 2篇]
- 段落数: 70，均长 61 字
- 短段（≤30字）: 19 段（占比 27%）
- 图片: 39 张，分布 前/6 中/27 后/6
- 分节方式: whitespace（hr=0, 横线段=0）
- 强调: bold×32 blockquote×0
- CSS: font-size=None line-height=1.75em color=var(--weui-FG-2)
- **推断模板: `structured-scan`**

### 刘小排
- **首选模板：** `structured-scan`（实测：hr分节+大量bold，比初始估计的dense-prose密度更高）
- **封面：** 情绪型（C方向），留白多，文字感强
- **插图：** 每节配图，中段集中
- **特殊标记：** 大量关键词加粗（bold/段落比约0.66），用 `<hr>` 分节

#### 数据采样 2026-04-14 — https://mp.weixin.qq.com/s?src=11&timestamp=1776155727 [实测 1篇]
- 段落数: 119，均长 32 字
- 短段（≤30字）: 63 段（占比 53%）
- 图片: 33 张，分布 前/1 中/26 后/6
- 分节方式: hr（hr=10, 横线段=0）
- 强调: bold×79 blockquote×0
- CSS: font-size=16px line-height=1.75em !important color=#2c2c2c !important
- **推断模板: `structured-scan`**

### 赛博禅心
- **首选模板：** `breathing-space`
- **封面：** 情绪型（C方向），温暖色调
- **插图：** 生活感插图，1-2 张，放在情绪转折处
- **特殊标记：** 极短段落（均长16字），单句成段为主，短段比91%

#### 数据采样 2026-04-14 [实测 1篇]
- 段落数: 34，均长 16 字
- 短段（≤30字）: 31 段（占比 91%）
- 图片: 33 张，分布 前/20 中/7 后/6
- 分节方式: whitespace（hr=0, 横线段=0）
- 强调: bold×14 blockquote×0
- CSS: font-size=14px line-height=2em color=rgb(55, 53, 47)
- **推断模板: `breathing-space`**

---

## 排版匹配规则（Stage 6.7 自动决策依据）

```
文章类型 × 受众 → 推荐模板

opinion × practitioner     → dense-prose（默认）/ image-anchored（论点多时）
opinion × friends-circle   → breathing-space / dense-prose
opinion × general-public   → image-anchored（降低门槛）

creator-share × any        → breathing-space（体验分享）/ structured-scan（工具教程）
                             判断依据：是否有操作步骤？有→structured-scan，无→breathing-space

life-reflection × any      → breathing-space（首选）

news-reaction × practitioner → dense-prose（快节奏）/ image-anchored
news-reaction × general-pub  → image-anchored（帮助理解）

how-to × any               → structured-scan（首选）
```

**受众优先级：** 受众比文章类型对模板选择影响更大（practitioner 容忍高密度，general-public 需要视觉辅助）。

---

_最后更新：2026-04-14_
_下次更新：运行 /author-update 后由 analyze_article.py 自动追加新观察_
