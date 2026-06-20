# TruthSeeker 45 秒宣传片导演说明

## Statement

这支片不是普通功能罗列，也不是单纯展示界面的录屏。它要在 45 秒内告诉评委：TruthSeeker 的价值不在于“又多接了几个检测 API”，而在于把跨模态鉴伪、情报溯源、逻辑质询、人机协同和可审计报告组织成一个完整的可信研判系统。

核心 thesis：**让每一次判断，都能追溯到证据。**

主要受众是比赛评委，同时兼顾后续路演宣传。评委关心创新点、系统完整度和落地可信度，所以节奏不能像广告一样只喊口号；每个视觉 beat 都要落到一个系统能力：多源检材、Agent 链路、Challenger 质询、人机协同、溯源图谱、报告与案例沉淀。

视觉基调采用深色安全科技，但避免通用紫色霓虹。底色使用近黑蓝灰，强调色使用项目 UI 中已有的荧光黄绿和青色。运动语言用“证据链汇聚”作为 hero element：碎片化风险信号逐步被 Agent 链路收束为图谱、报告和 logo。

## Visual System

- 画布：1920 x 1080，横屏 16:9。
- 字体：中文使用系统黑体栈，标题重字重；少量英文/数值使用等宽字体。
- 色彩：
  - 背景：`#05070A`、`#0B1018`
  - 主文字：`#F7F8ED`
  - 次文字：`rgba(247,248,237,.70)`
  - 强调绿：`#D4FF12`
  - 情报青：`#67E8F9`
  - 风险红：`#FF5A5F`
- 动画：
  - 入场用 expo-out 物理缓出。
  - 场景之间不断片，统一用流动线条和屏幕卡片作连续视觉锚点。
  - 结尾 hold 清晰 logo，不 fade to black。
- 音频：
  - HTML 内置 WebAudio 合成：低频氛围底 + 若干同步 SFX。
  - 若浏览器录制不带系统外部音频，HTML 播放时仍有 BGM/SFX；最终若需 H.264 MP4 + AAC，建议再用 ffmpeg 转码。

## Storyboard

### Shot 01 - Threat Flood

Timecode: 0.0-7.0s

画面从黑场打开，碎片化风险词从四周进入：文本、图像、音频、视频、URL、元数据。红色扫描线快速掠过，主标题出现：“恶意 AIGC 不再是单点伪造”。字幕强调跨模态复合攻击。

Purpose: 建立问题，不急着讲产品。

### Shot 02 - System Enters

Timecode: 7.0-14.5s

主页面和上传界面以 3D 卡片形态入场。项目 logo 作为左上角可信锚点，字幕：“TruthSeeker 不是另一个检测按钮，而是一条可信研判链。”

Purpose: 从风险转入系统定位，避免把项目降格成工具页面。

### Shot 03 - Agent Chain

Timecode: 14.5-24.5s

检测控制台成为主画面，四个 Agent 节点在画面下方依次点亮：电子取证、Challenger、情报溯源、Commander。Challenger 节点两次发出质询脉冲，显示“0.8 质量门槛 / 第 5 轮残留风险放行”。

Purpose: 把核心创新点讲清楚：不是串 API，而是阶段式质询拓扑。

### Shot 04 - Human Collaboration

Timecode: 24.5-32.0s

人机协同面板浮出，专家意见像便签一样进入证据流，回写到 Commander 轨道。字幕：“人工经验进入主推理链路，而不是事后批注。”

Purpose: 突出人机协同的差异化。

### Shot 05 - Provenance & Report

Timecode: 32.0-39.8s

溯源图谱、公开案例库、个人经验库和数据大屏形成四卡画廊。中心出现报告卡片：Markdown / PDF / Audit Log / report_hash。字幕：“证据图谱、审计日志、报告哈希，形成可复核闭环。”

Purpose: 给评委看到工程闭环和可审计结果。

### Shot 06 - Final Lockup

Timecode: 39.8-45.0s

所有线条向中心收束为 logo。最后一帧显示：

TruthSeeker
基于多智能体协同的跨模态恶意 AIGC 鉴伪与溯源系统
让每一次判断，都能追溯到证据。

Purpose: 品牌记忆点，稳定收尾。

## Production Manifest

- 主文件：`truthseeker-promo.html`
- 素材目录：`assets/`
- 建议人工检查时间点：0.5s、5s、9s、16s、22s、27s、34s、41s、44.8s
- 交付优先级：
  1. 浏览器可播放 HTML 动画。
  2. 若浏览器 MediaRecorder 支持，导出 WebM 视频。
  3. 若本机具备 ffmpeg/Playwright，再转 H.264 MP4。

