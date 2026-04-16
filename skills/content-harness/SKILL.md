---
name: content-harness
description: >-
  AI 内容生产 Harness。输入一句灵感，自动完成「选题研判→结构生成→分段写作→评估打分→优化重写→多平台改写」全流程管线。
  评估基于真实标杆文章校准，不是 AI 自嗨打分。每次运行结束强制沉淀写作经验到知识库，下一次自动加载。
  用户只负责：提供灵感 + 最终发布确认。
  触发：/content-harness、/write、写文章、写一篇、帮我写、发公众号、content harness、写作助手
---

# Content Harness — 内容生产管线

## 核心原则

1. **你的灵感是灵魂** — 文章必须围绕用户的原始洞察展开，不是泛泛写一个话题
2. **一键跑通** — 灵感进去，成稿出来。中间不暂停，只在最终审核等用户
3. **规则化质检，不是自嗨打分** — 用硬规则扫描，用对抗式 sub-agent 评估
4. **每次运行都让系统更强** — 强制沉淀，知识库主动注入下一次写作
5. **像人不像 AI** — 禁止套话、空话、emoji 堆砌、"值得注意的是"类 AI 语气词

## 运行模式

**默认：自动模式** — 灵感 → 自动跑完 Stage 1-6.5 + Stage 8.2 归档 → 在 Stage 7 展示成稿等用户审核

**可选：协作模式** — 用户说"我想参与每一步"或"一步一步来"时，每个 Stage 暂停等确认

除非用户明确要求协作模式，否则**一律用自动模式**。

## 运行前：初始化 Orchestrator + 加载知识库

每次触发时，**第一步必须初始化 orchestrator**：

```bash
python3 "$SKILL_DIR/scripts/orchestrator.py" init --inspiration "用户的灵感原文"
```

orchestrator 会记录本次运行的起点状态（包括知识库 hash），后续每个关键 Stage 完成后都要调用 `verify` 验证。如果 verify 返回非零退出码，**必须修复后重新验证，不能跳过**。

### Step 1: 读取知识库

读取 `references/knowledge-base.md`。

### Step 2: 编译写作约束（用脚本，不靠记忆）

**必须执行以下命令**，获取编译后的约束列表：

```bash
python3 "$SKILL_DIR/scripts/compile_knowledge.py"
```

脚本会自动从 knowledge-base.md 提取高效模式、避免模式、用户修改信号，输出可直接使用的约束列表。

将脚本输出**原样拼接**到写作指令的开头，格式：

```
## 本次写作约束（从知识库自动编译）
[脚本输出]
```

### Step 3: 读取参考资料

按需读取（不需要每次全读）：
- `references/user-style-dna.md` — **用户的写作风格 DNA + 写作模式矩阵**（写作阶段必读）
- `references/author-methods.md` — 参考作者写作方法论（写作阶段参考）
- `references/evaluation-rubric.md` — 评估标准和标杆特征（评估阶段参考）

### Step 4: 检查作者动态（轻量预检）

读取 `references/author-feed.md`：
- 检查 `last_updated`：如果超过 14 天，提示用户考虑运行 `/author-update`（不阻断流程）
- 检查"模式变化信号"区域：如有未处理的信号，将其注入到本次写作约束（标注为"最新观察，权重低于已验证规则"）
- 检查"近期高质量文章表"：如有与本次文章类型相同的高质量文章，在 Stage 3 写作时参考其开头/结尾模式

### Step 5: 读取排版数据（Stage 6.7 所需）

读取 `references/layout-styles.md`：
- 注意区分 `[初始值]`（训练知识估计）和 `[实测 YYYY-MM-DD N篇]`（真实扫描数据）
- Stage 6.7 排版推荐时，**优先使用实测数据**；如果某作者尚无实测数据，以初始值为参考但降低置信度，并在推荐方案中注明"未经验证"

---

## Pipeline 执行流程

### Stage 0: 灵感接收（含断点续跑 + 选题推荐）

**Step 0.1: 检测未完成的 pipeline**

在接收新灵感之前，先运行：

```bash
python3 "$SKILL_DIR/scripts/orchestrator.py" resume 2>/dev/null
```

- 如果存在活跃的未完成 pipeline → 告知用户上次运行的灵感、进度、中断位置，询问：
  > 检测到上次未完成的管线：「{灵感}」，已完成到 Stage {X}。
  > 1. **继续上次** — 从 Stage {X+1} 接着写
  > 2. **放弃上次，开始新的** — 旧 pipeline 自动归档
- 用户选择继续 → 跳到对应 Stage 继续执行（不重新 init）
- 用户选择新开 → 正常走 init（orchestrator 会自动归档旧 run）
- 没有活跃 pipeline → 正常接收灵感

**Step 0.2: 接收灵感（或选题推荐）**

如果用户没有明确灵感，或说了"帮我选题"/"今天写什么好"，执行选题池刷新：

```bash
python3 "$SKILL_DIR/scripts/refresh_topic_pool.py"
```

然后读取 `references/topic-pool.md`，结合以下维度推荐 3-5 个选题：
- **时效性** — 48h 内热点优先
- **独特角度** — 能产生原创洞察，不是复述新闻
- **历史去重** — 参考 knowledge-base.md 历史文章表，避免重复话题
- **作者差异化** — 避开关注作者已覆盖的相同角度

用户选定后，将选题作为灵感锚点。

如果用户已有明确灵感，**跳过此步**。

**Step 0.3: 灵感锚点确认**

原文保留，这是整篇文章的锚点。然后**直接进入 Stage 1，不暂停**。

---

### Stage 1: 选题研判（自动）

目标：判断灵感的最佳切入角度。

**自动决策，不等用户：**
1. 评估灵感的传播潜力和独特性
2. 选定最佳切入角度（基于知识库中的历史表现和参考作者的选题模式）
3. 确定目标读者画像
4. **直接进入 Stage 1.5**

仅在判断"建议放弃"时暂停告知用户。

---

### Stage 1.5: 文章类型分类（必须执行，决定后续所有容器）

**这一步决定写什么形状的文章，错了后面全错。**

完成三个判断，输出分类结果：

**① 文章类型**（对应 user-style-dna.md 模式矩阵）

| 类型标签 | 触发特征 |
|---------|---------|
| `opinion` | 你有一个判断想让读者接受——AI趋势/时代变局/方法论推广 |
| `creator-share` | 你做了某个东西/发现了某个工具，想把它送给读者 |
| `life-reflection` | 以个人经历为核心，情感密度高——年终/里程碑/旅行感悟 |
| `news-reaction` | 对刚发生的行业事件做第一判断，时效性是核心 |
| `how-to` | 要让读者掌握一个具体技能，可操作性是核心 |

**② 主要受众**
- `practitioner` — 同行，习惯高密度内容
- `friends-circle` — 关心你这个人的读者，情感连接优先
- `general-public` — 对话题感兴趣的大众，需降低门槛

**③ 写作意图**
- `persuade` / `share-gift` / `document` / `teach` / `react`

分类完成后，**查阅 user-style-dna.md 的对应模式，提取该类型的容器规则**，这是 Stage 2 的唯一输入。

**严禁用 `opinion` 的容器（V型弧 + 哲学金句）写 `creator-share` 类文章。**

**Orchestrator 检查点：**
```bash
python3 "$SKILL_DIR/scripts/orchestrator.py" verify --stage 1.5 --article-type [类型]
```

---

### Stage 2: 结构生成（自动）

目标：按 Stage 1.5 确定的文章类型，生成对应容器的文章骨架。

**根据文章类型路由，使用对应规则：**

- `opinion` → 小切口进入 + V型弧 + 哲学升维收束，结尾金句能独立传播
- `creator-share` → 展示作品 + 过程窗口 + 一个洞察 + 温暖邀请，无V型弧
- `life-reflection` → 场景切入 + 下沉 + 顿悟 + 上扬 + 祝福共勉
- `news-reaction` → 事件+判断（前3句）+ 逻辑展开 + 立场/展望
- `how-to` → 数字冲击开头 + 清单铁律 + 行动号召

**所有类型共用的约束：**
- 每个部分必须有独立论点，不是同一观点的不同说法
- 必须包含至少一个真实案例/个人经历
- 不用副标题（段落自身的情绪转折分节）

输出结构包括：
- 推荐标题（3 备选，选定 1 个）
- 开头切入方式（由文章类型决定）
- 各部分核心论点和支撑
- 结尾方向（由文章类型决定，NOT 永远是哲学金句）

**直接进入 Stage 3，不暂停。**

---

### Stage 3: 全文写作（自动）

**这是最核心的环节。**

#### 写作前

读取 `references/author-methods.md`，注入参考作者手法。将编译后的知识库约束拼接到写作指令开头。

#### 写作铁律

1. **信息密度**：每段必须有新信息。删除所有不增加信息量的句子
2. **具象化**：每个抽象概念必须配一个具体类比或案例
3. **语言自然**：使用口语化表达，允许短句、碎句、甚至偶尔粗口
4. **反 AI 感**：禁止——"随着…的发展"、"值得注意的是"、"总的来说"、"不可否认"、"在当今…时代"、"毋庸置疑"
5. **不重复**：后文不得重复前文已说过的观点，哪怕换了说法
6. **"不是X而是Y"** 全文不超过 2 次（首次运行验证的 AI 高频特征）
7. **用户灵感贯穿**：用户的原始洞察必须是文章的灵魂主线
8. **节奏感**：段落长短参差不齐，使用单句成段制造节奏，使用"刹车式转折"制造起伏
9. **一个类比贯穿全文**比每段换一个类比更有凝聚力

#### 执行方式

**一次性输出完整文章**，但内部按以下顺序构思：

1. **开头**：按 Stage 1.5 文章类型决定开头方式，不是所有文章都从"具体场景制造悬念"开始
2. **正文**：逐部分推进，每部分有独立的信息增量
3. **结尾**：按文章类型决定结尾方式——`opinion` 用金句，`creator-share` 用邀请，`life-reflection` 用祝福，`news-reaction` 用立场，`how-to` 用行动号召

**写完后用 Write 工具将全文写入 `/tmp/article_draft.txt`（不用 echo），然后验证：**

```bash
python3 "$SKILL_DIR/scripts/orchestrator.py" verify --stage 3 --article /tmp/article_draft.txt
```

验证通过后进入 Stage 4。

---

### Stage 4: 规则化质检 + 对抗式评估（自动）

这是 harness 的核心。分两层：**规则扫描**（确定性）+ **对抗评估**（判断性）。

#### 第一层：规则扫描（脚本强制执行，不靠自检）

**必须执行以下命令**，将文章正文保存到临时文件后扫描：

```bash
# 文章已在 Stage 3 通过 Write 工具写入 /tmp/article_draft.txt
# 运行规则扫描器（输出 JSON 供 orchestrator 验证）
python3 "$SKILL_DIR/scripts/rule_scan.py" -f /tmp/article_draft.txt --json > /tmp/scan_result.json
python3 "$SKILL_DIR/scripts/rule_scan.py" -f /tmp/article_draft.txt
# 验证
python3 "$SKILL_DIR/scripts/orchestrator.py" verify --stage 4 --scan-result /tmp/scan_result.json
```

脚本会自动检查 8 项硬规则（AI 感词频、"不是A而是B"计数、段落长度方差、单句成段、段落长度上限、句子长度、模糊词频率、数据支撑），输出 PASS/FAIL 报告。

**脚本的判定不可覆盖。** FAIL 就是 FAIL，不能解释为"虽然 FAIL 但其实还行"。

在脚本扫描之外，Claude 需要**额外判断**以下 3 项（脚本无法检测的语义级问题）：
- **信息密度**：逐段检查，有没有删掉不影响全文的段？
- **反直觉点**：全文是否有至少一个让读者意外的判断？
- **灵感还原**：用户原始灵感是否是文章灵魂？

#### 第二层：对抗式评估（spawn 独立 sub-agent）

**必须 spawn 一个独立的 Agent** 来做评估，不能自己评自己。

spawn Agent 时的 prompt 要求：
1. 提供完整文章 + 用户原始灵感 + 评估标准（从 evaluation-rubric.md 中提取关键特征）
2. 要求 sub-agent 做以下判断：
   - 和标杆文章的差距在哪（具体到段落级别）
   - 活人感终审：读起来像"一个有见识的普通人在认真跟你聊天"吗？还是像"AI在输出信息"？
   - 最致命的 3 个问题
   - 综合判定：可发布 / 需优化 / 需重写

sub-agent 返回结果后，综合两层检查决定下一步：
- **规则扫描全 PASS + 对抗评估"可发布"** → 进入 Stage 6
- **有 FAIL 或 "需优化"** → 进入 Stage 5
- **"需重写"** → 回到 Stage 2 重新生成结构

---

### Stage 5: 自动修复（如需）

根据 Stage 4 的具体问题，**只修复有问题的部分**：

- 规则 FAIL → 针对性修复（删禁止词、打散重复句式、拆均匀段落、补案例）
- 对抗评估的致命问题 → 重写对应段落

修复后**再跑一轮 Stage 4**（但只跑规则扫描，不再 spawn sub-agent，避免无限循环）。

最多循环 **2 轮**。超过 2 轮说明结构有问题，通知用户并给出具体建议。

---

### Stage 6: 多平台改写（自动）

评分达标后，自动生成多平台版本：

**公众号版：** 即 Stage 3 的产出（长文，2000-3000 字）

**小红书版：** （读取 `references/platform-styles/xiaohongshu.md` 生成）
- 标题改写为小红书钩子格式（参考 Step XHS-1 规范）
- 正文压缩为 200-800 字，分点呈现（3-7 点）
- 末尾添加互动邀请句
- 话题标签生成

**知乎版：** （读取 `references/platform-styles/zhihu.md` 生成）
- 确定发布形式：专栏文章 / 问题作答（参考 Step ZH-1 路由规则）
- 标题/首句改为结论先行格式
- 正文调整为理性分析语气，1000-2500 字
- 语气去情绪化，可添加副标题

**即刻/Twitter 版：**
- 3-5 条独立短内容，每条 < 140 字
- 每条可独立传播，不依赖上下文

---

### Stage 6.5: 视觉生产（自动 + 中立评审）

这是完整的视觉生产环节，包含封面备选、文中插图、排版方案、中立评审四个步骤。**全部自动执行，评审结果才展示给用户。**

**图片后端自动选择**（generate_cover.py 自动检测）：
- CDP Proxy 可用 → **即梦/豆包**（cdp操作，画质最高）
- 有 MINIMAX_API_KEY → MiniMax API（画质中等）
- 兜底 → Pollinations.ai（免费，画质中等）

#### 步骤一：生成 3 个封面方向

基于文章核心类比，构造 **3 个视觉方向**，每个方向对应不同的视觉语言：

| 方向 | 设计思路 | 适合文章类型 |
|------|---------|------------|
| A: 具象型 | 直接呈现文章的核心场景或物件，写实感强 | creator-share, how-to |
| B: 隐喻型 | 将核心类比视觉化，抽象几何，有张力 | opinion, news-reaction |
| C: 情绪型 | 捕捉文章的情绪基调，氛围优先，不强调信息 | life-reflection, opinion |

每个方向生成一张，共 3 张，命名为 `/tmp/cover_A_[日期].png`、`cover_B_`、`cover_C_`：

```bash
D=$(date +%Y%m%d)
python3 "$SKILL_DIR/scripts/generate_cover.py" --prompt "PROMPT_A" --out /tmp/cover_A_$D.png
python3 "$SKILL_DIR/scripts/generate_cover.py" --prompt "PROMPT_B" --out /tmp/cover_B_$D.png
python3 "$SKILL_DIR/scripts/generate_cover.py" --prompt "PROMPT_C" --out /tmp/cover_C_$D.png
```

所有 prompt 必须包含固定风格约束：`no text, no words, 900x500, cinematic lighting, editorial style, photorealistic, natural grain, human presence`

> 即梦后端：prompt 支持中文，风格更自然真实，建议 prompt 中加"电影感"、"真实人物"等描述。

#### 步骤二：生成文中插图（1 张固定必选 + 选做第 2 张）

**第 1 张插图：强制生成，不可跳过。**

锚点位置：情绪转折处（V弧底部 / 正文 30%-40% 处）。所有文章类型均需生成 1 张，放在读者情绪进入最深之前，起"视觉呼吸"作用。

**第 2 张插图（选做）：** 满足以下任一条件时额外生成：
- 文章有数据/反差对比段（creator-share / news-reaction 类型）
- 文章结构有多个情绪转折点（life-reflection 类型）

命名规则：`/tmp/illus_1_[日期].png`（固定）、`/tmp/illus_2_[日期].png`（选做）：

```bash
# 第 1 张：固定生成
python3 "$SKILL_DIR/scripts/generate_cover.py" --prompt "ILLUS_PROMPT_1" --out /tmp/illus_1_$(date +%Y%m%d).png

# 第 2 张：满足条件时生成
python3 "$SKILL_DIR/scripts/generate_cover.py" --prompt "ILLUS_PROMPT_2" --out /tmp/illus_2_$(date +%Y%m%d).png
```

插图 prompt 规则：
- 比封面更具体，可以有场景感，但仍然无文字
- 风格必须与封面同向（A/B/C 中选一个，保持统一）
- 建议尺寸 900×400（文章内嵌图）

#### 步骤三：生成排版方案

输出一份文字版排版方案：

```
封面图：[推荐方向] — [理由]
插图1位置：第[N]段后，[左对齐/居中/全宽]，作用：[强化哪个论点]
插图2位置：（如有）第[M]段后，[对齐方式]
整体视觉节奏：[文字比例高/图文交替/图片收束]
```

#### 步骤四：spawn 中立设计评审 agent

**必须 spawn 一个独立 Agent**，提供以下内容让它评审：
- 3 张封面图（路径）+ 文章标题 + 核心类比
- 1-2 张插图（路径）+ 对应的文章段落
- 排版方案文字稿

要求 agent 给出：
1. **封面图推荐**：哪个方向与文章调性最匹配，理由（需具体指出视觉元素与文章内容的对应关系）
2. **风格一致性**：封面与插图是否在同一视觉语言体系内
3. **排版可行性**：插图位置是否会打断阅读节奏
4. **一句话总结**：用一句话描述这套视觉方案给读者带来的整体感受

评审结果连同所有图片一起，进入 Stage 6.7。

---

### Stage 6.7: 排版风格匹配（自动 + 用户确认）

这一步决定文章的视觉容器——同样的内容，匹配错排版等于换了一张脸。**自动完成推荐，在 Stage 7 等用户确认后才生效。**

#### 步骤一：读取排版库

```bash
# 读取排版模板库
cat "$SKILL_DIR/references/layout-styles.md"
```

#### 步骤二：自动匹配

根据 Stage 1.5 的分类结果（文章类型 + 受众），从 `layout-styles.md` 的匹配规则中选出推荐模板：

```
文章类型 × 受众 → 推荐模板（见 layout-styles.md 排版匹配规则章节）
```

同时检查：有没有参考作者的同类型文章对应特定模板偏好？（见 layout-styles.md 作者排版特征速查）

#### 步骤三：生成排版预案（2 个选项）

输出两个可选方案，供用户在 Stage 7 确认：

**方案 A（推荐）：** 基于文章类型的自动匹配模板
- 模板名：`[dense-prose / breathing-space / structured-scan / image-anchored]`
- 推荐理由：文章类型/受众的匹配依据
- CSS 样式预览：关键样式参数（字号、行高、段间距）
- 插图位置方案：哪些位置插图

**方案 B（参考作者同款）：** 如有参考作者的同类文章，展示其排版特征
- 作者名：[谁的风格]
- 模板名：[对应模板]
- 与方案 A 的差异：[具体差异]

结果暂存，**在 Stage 7 由用户选择方案，不在此暂停**。

---

### Stage 7 前置门禁（硬性检查，不可跳过）

**进入 Stage 7 之前，必须逐项确认以下 5 项全部完成：**

- [ ] Stage 6.5 视觉生产：3 张封面 + 插图已生成，设计评审 agent 已返回结果
- [ ] Stage 6.7 排版匹配：已生成 2 个排版方案（推荐 + 参考作者版）
- [ ] Stage 8.2 文章归档：公众号正文已写入三个目录（项目目录 + skill 目录 + Obsidian）
- [ ] Stage 8.3 知识库更新：knowledge-base.md 已追加本次运行记录和 insights
- [ ] INDEX.md 已更新文章列表和视觉方案

**任一未完成，禁止进入 Stage 7。** 先补完再展示。

这个门禁的设计理由：归档和视觉生产不依赖用户反馈，没有理由等到用户确认后才做。把它们前置，确保不因为"等用户"而遗漏。

---

### Stage 7: 用户审核（唯一的人工暂停点）

展示给用户：
1. 完整的公众号版文章
2. 规则扫描结果（简要）
3. 对抗评估的关键结论
4. 多平台版本（小红书、知乎、即刻版各一份）
5. 封面图 3 张 + 插图 + 设计评审推荐

**排版方案选择（必选项，直接影响 Stage 9 发布样式）：**
- 方案 A（推荐）：[模板名] — [理由]
- 方案 B（参考作者版）：[作者] 同款 — [差异描述]
- 请选择 A 或 B，或说"自定义"

等待用户确认：
- **确认发布** + 排版方案选择 → 进入 Stage 8.1（提取 insights）→ 进入 Stage 9
- **只推草稿，不群发** → 进入 Stage 9，完成草稿箱上传后停止
- **要求修改** → 执行修改，**记录修改的 diff 作为风格信号**，修改后更新已归档的文件
- **放弃** → 仍然进入 Stage 8.1（提取 insights），跳过 Stage 9

**发布平台确认（如用户确认发布，同步询问）：**
- 公众号草稿（默认）
- 小红书（附带内容包）
- 知乎（附带内容包）
- 全部（分批输出各平台内容包）

---

### Stage 8: 沉淀学习（强制执行，不可跳过）

每次运行结束，不管文章是否发布，都必须执行：

#### 8.1 提取 Insights

- 这次运行中什么有效、什么无效
- 如果用户改了稿 → 提取 diff，分析用户的风格偏好信号
- 如果评估失败重写了 → 记录失败原因和修复策略

#### 8.2 保存文章正文（原子写入协议）

将最终版公众号正文保存到以下三个位置。**必须使用 staging → move 两阶段写入，防止部分写入导致不一致。**

**Step 1: 写入暂存区**

将所有文件先写入 `/tmp/content_harness_staging/`：

```
/tmp/content_harness_staging/projects/YYYY-MM-DD_标题简短版.md
/tmp/content_harness_staging/skill/YYYY-MM-DD_标题简短版.md
/tmp/content_harness_staging/vault/YYYY-MM-DD_标题简短版.md
```

文件格式（带 frontmatter）：
```markdown
---
title: [文章标题]
date: [日期]
inspiration: [原始灵感]
score: [评分]
published: [公众号版/草稿/未发布]
cover_image: [images/covers/YYYY-MM-DD_cover_X.png，用户选定的那张]
---

[文章正文]
```

**Step 2: 确认暂存区完整后，移动到最终路径**

三个最终位置（与暂存文件一一对应）：

| 暂存路径 | 最终路径 |
|---------|---------|
| `/tmp/.../projects/` | `~/Documents/Claude/Projects/AI工具/content-harness/articles/` |
| `/tmp/.../skill/` | `~/.claude/skills/content-harness/articles/` |
| `/tmp/.../vault/` | `~/Documents/Obsidian Vault/05_thought/写作/` |

用 `mv` 逐个移动。每次 mv 后立即检查目标文件存在。

**Step 3: 失败处理**

- 任何一个 mv 失败 → 立即停止，输出已成功/失败的路径清单，提示用户手动从 `/tmp/content_harness_staging/` 复制
- 全部成功 → 删除暂存目录，执行 `python3 scripts/orchestrator.py verify --stage 8`

**Step 4: 更新索引**

写入文章后，同步更新 `~/Documents/Claude/Projects/AI工具/content-harness/INDEX.md`：在文章列表中追加一行，填入日期、标题、类型、评分、发布状态、封面图和插图的相对路径。

#### 8.3 更新知识库

将以下内容追加到 `references/knowledge-base.md`：

**高效模式区：** 新发现的有效写作策略
**避免模式区：** 新发现的应避免模式
**历史文章表：** 本次文章基本信息
**运行记录区：** 详细记录

沉淀格式：

```markdown
### Run [日期] — [文章标题]
- **灵感：** [原始灵感]
- **文章类型：** [opinion / creator-share / life-reflection / news-reaction / how-to]
- **受众：** [practitioner / friends-circle / general-public]
- **最终评分：** [规则扫描 N/8 PASS + 对抗评估结论]
- **发布：** [是/否]
- **写作 insights：**（必须标注类型，格式：[类型] insight内容）
  - [opinion] insight 1
  - [creator-share] insight 2
- **用户修改信号：** [如果有]
- **失败与修复：** [如果有]
```

**Orchestrator 验证（Stage 8 最关键的检查点）：**

```bash
python3 "$SKILL_DIR/scripts/orchestrator.py" verify --stage 8
```

此命令会检查：
1. knowledge-base.md 的 hash 是否与 pipeline 开始时不同（如果相同 = 没更新 = FAIL）
2. 是否包含今日的运行记录
3. 文章是否已保存到项目目录
4. 封面图是否已保存到项目目录

**验证不通过，pipeline 不能 complete。** 没有例外。

完成所有写入后，标记 pipeline 完成：
```bash
python3 "$SKILL_DIR/scripts/orchestrator.py" complete
```

complete 会检查 Stage 3 + Stage 4 + Stage 8 是否全部通过验证。任一缺失，拒绝完成。

#### 8.4 知识库蒸馏（每 5 篇触发一次）

当历史文章表中累积到 5 的倍数时，执行一次知识库蒸馏：
- 把零散的 insights 合并去重，**保留类型标签**
- 把反复出现的用户修改信号升级为稳定的风格规则
- 把反复出现的避免模式升级为写作铁律
- **严禁**：将某一类型的有效模式升级为通用规则——除非它在 3 种以上不同类型都得到验证
- 清理过时或矛盾的记录

---

### Stage 9: 多平台发布（按用户 Stage 7 选择执行）

**前置条件**：用户在 Stage 7 确认发布意图 + 平台选择 + 排版方案。

根据用户选择的平台，各自执行对应发布流程。完整技术手册见 `scripts/wechat_publish.md`（微信）和 `references/platform-styles/` 目录（小红书/知乎）。

---

#### 9-WeChat: 微信公众号（CDP 自动化，2 次授权）

完整手册：`scripts/wechat_publish.md`

**作者固定：`cyber brid`（阿泽账号），所有发布中 author0 字段不可修改。**

**总体原则：**
- 全程用同一个已登录 tab（不要 `/new` 开新 tab，session 不跟随）
- 内容注入全部用 base64 → `decodeURIComponent(escape(atob(b64)))` 解码
- 所有图片（封面 + 插图）在 Block A 一次性全部上传，Block B 只负责写内容

**Block A（1次授权）— CDP health + Token + 上传所有图片**

一次性完成：环境检查、找 MP 标签页、提取 token、上传封面图、上传插图（如有），将所有变量保存到 `/tmp/wechat_vars.sh`。

详见 `scripts/wechat_publish.md` Block A 完整代码。

**Block B（1次授权）— 编辑器注入 + 保存草稿 + 绑封面 + 截图**

接续 Block A 变量，完成：
1. `source /tmp/wechat_vars.sh`
2. 导航到新建编辑器
3. 注入标题 + 作者（`cyber brid`）+ 正文 HTML（base64 编码）
4. 点击"保存为草稿"（`.send_wording[2].click()`）
5. 从 URL 提取草稿 ID
6. `operate_appmsg` 绑封面 + 写完整 HTML（`content0` 必须包含完整内容）
7. 导航到草稿预览 + 截图验证

详见 `scripts/wechat_publish.md` Block B 完整代码。

**operate_appmsg 关键字段：**
- `author0: 'cyber brid'` — 固定，不可变
- `content0: FULL_HTML` — 必须包含完整 HTML，缺失则正文被清空
- `fileid0 / cdn_url0 / cdn_235_1_url0 / cdn_1_1_url0 / cdn_3_4_url0` — 均填封面 CDN URL
- `originality_type0: '1'` — 原创

**草稿完成后的群发审批（技术层门禁，不可绕过）**

使用 AskUserQuestion 工具弹出确认：
- 问题："即将向订阅者群发《[文章标题]》，此操作发出后不可撤回。确认发布？"
- 选项：`["确认群发", "取消，先留草稿"]`
- 取消 → 立即终止，草稿保留
- 确认群发 → 点击编辑器"发表"按钮，截图确认

**⚠️ 注意：** 订阅号群发最后一步需要手机扫码二次确认，CDP 流程止步于草稿完成。如 session 在群发时失效，草稿已安全保存在草稿箱，用户手动点"发表"即可。

---

#### 9-XHS: 小红书（CDP 半自动发布）

完整规范见 `references/platform-styles/xiaohongshu.md`

**前置条件：**
- CDP Proxy 运行中（`curl -s http://localhost:3456/health`）
- 用户已在 Chrome 中登录 creator.xiaohongshu.com

**自动执行：**
1. 读取 Stage 6 生成的小红书版草稿，执行 Step XHS-1（标题/正文/话题改写）
2. 准备封面图：如需竖版裁切，用 Pillow crop 中心区域
3. 生成话题标签（Step XHS-3）
4. **调用 xhs_publish.py 自动填写** — 图片上传、标题、正文、第一个话题

```bash
python3 "$SKILL_DIR/scripts/xhs_publish.py" \
  --title "标题（≤20字）" \
  --body "正文内容" \
  --tags "标签1,标签2,标签3" \
  --images "/path/cover.png,/path/illus.png"
```

5. 截图确认内容正确后，**暂停等用户手动点击发布**

**用户手动操作（最后一步）：**
- 检查图片顺序
- 确认话题标签已从下拉中选中
- 点击右上角「发布」

**⚠️ 安全门禁（脚本不自动点发布）：**
小红书对自动化有风控检测，最后一步由用户手动确认，降低账号风险。

---

#### 9-ZH: 知乎（手动发布，输出内容包）

完整规范见 `references/platform-styles/zhihu.md`

**自动执行：**
1. 执行 Step ZH-1（确定专栏 vs 问题作答）
2. 执行 Step ZH-2（内容转化：结论先行 + 理性语气 + 可选副标题）

**输出内容包（用户手动在知乎创作中心发布）：**

```
--- 知乎发布内容包 ---
【发布类型】专栏文章 / 问题作答

【如果问题作答，建议搜索的问题关键词】
[关键词]

【标题（专栏）/ 首句（回答）】
[内容]

【正文（知乎 Markdown 格式）】
[正文内容，1000-2500字]
```

---

#### 9.6 效果回收（异步，24-72 小时后）

发布完成后，提醒用户：

> 草稿已上传。24-72 小时后可运行效果回收：
> `python3 $SKILL_DIR/scripts/fetch_article_stats.py --cdp`
> 或在新对话中说"帮我回收最近文章的效果数据"
>
> 小红书/知乎的数据请手动记录后告诉我，我会写入 knowledge-base.md。

效果数据将自动写入 knowledge-base.md，供下一篇文章写作参考。

---

## 重要提醒

- **不要在任何阶段使用 emoji 装饰文章正文**
- **不要生成"AI 味"的过渡句**。宁可直接跳到下一段
- **自动模式下，Stage 1 到 6.7 + 8.2/8.3 归档之间不暂停**。全部跑完通过 Stage 7 前置门禁后，一次性展示给用户（含排版方案选择）
- **知识库是活的**。每次运行前必须读取+编译，每次运行后必须写入
- **对抗评估必须 spawn 独立 Agent**，不能自己评自己
- **作者固定为 `cyber brid`**（阿泽账号）。所有平台、所有发布中不可修改
- **插图每次必须生成 1 张**（放情绪转折处）。Stage 6.5 步骤二不可跳过
- **微信发布 2 次授权**（Block A + Block B）。不允许回退到 4 次授权结构
- **小红书通过 `xhs_publish.py` 自动填写**，最后一步由用户手动点击发布（风控原因）
- **图片后端优先级**：CDP可用→即梦/豆包 > MINIMAX_API_KEY→minimax > 兜底→pollinations
