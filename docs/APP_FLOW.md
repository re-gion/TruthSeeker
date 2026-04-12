# TruthSeeker -系统数据流转与多智能体状态机拓扑

##1.全局状态定义 (Global State)

```typescript
interface InvestigationState {
 //任务元数据
 caseId: string;
 createdAt: DateTime;
 priorityModality: 'video' | 'audio' | 'image' | 'text' | 'mixed';
 status: 'pending' | 'analyzing' | 'deliberating' | 'converged' | 'adjudicated' | 'error';

 //原始输入
 inputArtifacts: {
 video?: { url: string; metadata: VideoMeta };
 audio?: { url: string; metadata: AudioMeta };
 image?: { url: string; metadata: ImageMeta };
 text?: { content: string; extractedUrls: string[] };
 };

 //电子证据板 (Evidence Board) -各Agent钉上的证据
 evidenceBoard: {
 visualForensics: VisualEvidence[];
 audioForensics: AudioEvidence[];
 osintIntelligence: OsintEvidence[];
 crossValidation: CrossCheckEvidence[];
 };

 // Agent置信度历史 (用于收敛判定)
 confidenceHistory: {
 round: number;
 timestamp: DateTime;
 forensicsAgent: { score: number; reasoning: string };
 osintAgent: { score: number; reasoning: string };
 inquisitorAgent: { challenges: Challenge[]; satisfaction: number };
 }[];

 //当前辩论轮次
 currentRound: number;
 maxRounds: number;
 convergenceThreshold: number; //默认0.05 (5%变化视为收敛)

 //专家会诊介入记录
 expertInterventions: ExpertIntervention[];

 //最终裁决
 finalVerdict?: {
 classification: 'authentic' | 'suspicious' | 'fabricated' | 'inconclusive';
 confidence: number;
 summary: string;
 recommendations: string[];
 chainOfEvidence: EvidenceChainItem[];
 };
}
```

##2. LangGraph状态机拓扑图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ TruthSeeker Multi-Agent DAG │
└─────────────────────────────────────────────────────────────────────────────┘

 ┌──────────────┐
 │ START │
 │ (用户提交) │
 └──────┬───────┘
 │
 ▼
 ┌────────────────────────────────┐
 │ Input Preprocessor │
 │ •文件类型识别 │
 │ •元数据提取 │
 │ • URL/域名解析 │
 └──────────────┬─────────────────┘
 │
 ┌────────────────────┼────────────────────┐
 │ │ │
 ▼ ▼ ▼
 ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
 │ 🎬 Forensics │ │ 🔍 OSINT │ │ ⚖️ Inquisitor │
 │ Agent │ │ Agent │ │ (Observer) │
 │ │ │ │ │ │
 │ •视频帧分析 │ │ •威胁情报查询 │ │ •审视证据板 │
 │ •音频频谱检测 │ │ •域名溯源 │ │ •提出质询 │
 │ •图像篡改定位 │ │ •文本情感分析 │ │ •挑战置信度 │
 └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
 │ │ │
 │ ┌───────────────┴────────────────────┘
 │ │ │
 ▼ ▼ ▼
 ┌─────────────────────────────────────────────────────────┐
 │ EVIDENCE BOARD │
 │ ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐ │
 │ │视觉证据 │ │音频证据 │ │溯源情报 │ │
 │ │ •帧级异常 │ │ •频谱异常 │ │ •域名信誉 │ │
 │ │ •边缘融合 │ │ •噪声模式 │ │ • IP归属 │ │
 │ │ •光影不一致│ │ •压缩伪影 │ │ •关联图谱 │ │
 │ └─────────────┘ └─────────────┘ └─────────────────┘ │
 └────────────────────────┬────────────────────────────────┘
 │
 ▼
 ┌──────────────────────────────┐
 │ Convergence Check │
 │收敛判定节点 │
 │ •轮次 >= maxRounds? │
 │ •置信度变化 < threshold? │
 │ •质询官满意度达标? │
 └──────────────┬───────────────┘
 │
 ┌──────────────┴───────────────┐
 │ │
 ▼ NO ▼ YES
 ┌─────────────────────┐ ┌─────────────────────┐
 │ Challenge Loop │ │ 👨‍⚖️ Commander │
 │ (返回质询流程) │ │ Agent │
 │ │ │ │
 │质询官生成Challenge →│ │ •综合权重计算 │
 │触发API重检或深度分析 │ │ •证据链验证 │
 │更新置信度历史 │ │ •生成最终报告 │
 └─────────────────────┘ └──────────┬──────────┘
 │
 ▼
 ┌─────────────────────┐
 │ END │
 │ (报告导出/存档) │
 └─────────────────────┘
```

##3.条件边 (Conditional Edges)详解

###3.1从 Evidence Board到 Convergence Check

```python
#伪代码表示条件边逻辑
def should_converge(state: InvestigationState) -> str:
 """判定是否满足收敛条件，终止辩论"""

 #条件1:达到最大轮次
 if state.currentRound >= state.maxRounds:
 return "force_adjudicate"

 #条件2:专家强制介入终止
 if has_expert_forced_stop(state.expertInterventions):
 return "expert_adjudicate"

 #条件3:置信度收敛判定
 if len(state.confidenceHistory) >=2:
 prev = state.confidenceHistory[-2]
 curr = state.confidenceHistory[-1]

 forensics_delta = abs(curr.forensicsAgent.score - prev.forensicsAgent.score)
 osint_delta = abs(curr.osintAgent.score - prev.osintAgent.score)

 #连续两轮变化都小于阈值
 if forensics_delta < state.convergenceThreshold and \
 osint_delta < state.convergenceThreshold and \
 curr.inquisitorAgent.satisfaction >0.8:
 return "converged"

 #继续辩论
 return "continue_deliberation"
```

###3.2从 Convergence Check的分支

|分支结果 |目标节点 |说明 |
|---------|---------|------|
| `force_adjudicate` | Commander Agent |强制进入裁决（达到最大轮次） |
| `expert_adjudicate` | Commander Agent |专家要求立即裁决 |
| `converged` | Commander Agent |自然收敛，证据链稳定 |
| `continue_deliberation` | Inquisitor Agent |继续质询循环 |

##4.质询循环详细流程

```
┌─────────────────────────────────────────────────────────────────┐
│ Challenge Loop Detail │
└─────────────────────────────────────────────────────────────────┘

Inquisitor Agent审视 Evidence Board:
│
├─→发现置信度不足的证据点
│ │
│ ├─→生成 Challenge对象:
│ │ {
│ │ challengeId: string,
│ │ targetAgent: 'forensics' | 'osint',
│ │ targetEvidenceId: string,
│ │ question: "当前面部边缘融合概率72%，是否可能是微信压缩导致的伪影？",
│ │ requiredAction: 'reinspect_with_higher_precision' | 'cross_reference_alternative_api',
│ │ priority: 'high' | 'medium' | 'low'
│ │ }
│ │
│ └─→将 Challenge广播到 Realtime Channel
│ │
│ ├─→ Frontend:在质询面板高亮显示
│ │
│ └─→ Target Agent接收 Challenge:
│ │
│ ├─→调用更高精度API /备选模型
│ │
│ ├─→生成新证据覆盖/补充原证据
│ │
│ └─→更新 Confidence Score和 Reasoning
│
└─→新一轮 Evidence Board更新完成
 │
 └─→触发下一轮 Convergence Check
```

##5. Supabase Realtime数据流

###5.1 Broadcast Channels

```typescript
// Channel1: Agent状态流
const agentChannel = supabase.channel('agent-updates')
 .on('broadcast', { event: 'forensics_progress' }, (payload) => {
 //视听鉴伪AgentAgent进度更新
 })
 .on('broadcast', { event: 'osint_progress' }, (payload) => {
 //情报溯源AgentAgent进度更新
 })
 .on('broadcast', { event: 'challenge_issued' }, (payload) => {
 //质询官发起质询
 })
 .on('broadcast', { event: 'evidence_added' }, (payload) => {
 //新证据钉上证据板
 })
 .subscribe();

// Channel2:专家会诊协作
const expertChannel = supabase.channel(`case-${caseId}-expert`)
 .on('broadcast', { event: 'expert_joined' }, (payload) => {
 //专家加入会诊
 })
 .on('broadcast', { event: 'expert_comment' }, (payload) => {
 //专家发表评论
 })
 .on('broadcast', { event: 'expert_intervention' }, (payload) => {
 //专家强制干预（如要求立即裁决）
 })
 .subscribe();

// Channel3:系统事件
const systemChannel = supabase.channel('system-events')
 .on('broadcast', { event: 'convergence_reached' }, (payload) => {
 //辩论收敛
 })
 .on('broadcast', { event: 'verdict_ready' }, (payload) => {
 //最终裁决完成
 })
 .subscribe();
```

###5.2 Presence (在线状态)

```typescript
//追踪当前查看该案件的专家和用户
const presenceChannel = supabase.channel(`case-${caseId}-presence`)
 .on('presence', { event: 'sync' }, () => {
 const state = presenceChannel.presenceState();
 //更新UI显示当前在线的专家列表
 })
 .subscribe(async (status) => {
 if (status === 'SUBSCRIBED') {
 await presenceChannel.track({
 userId: currentUser.id,
 role: currentUser.role, // 'viewer' | 'expert' | 'admin'
 joinedAt: new Date().toISOString(),
 });
 }
 });
```

##6.数据库表设计 (Supabase Schema)

###6.1核心表

```sql
--案件主表
CREATE TABLE investigations (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 case_id TEXT UNIQUE NOT NULL,
 created_by UUID REFERENCES auth.users(id),
 priority_modality TEXT CHECK (priority_modality IN ('video', 'audio', 'image', 'text', 'mixed')),
 status TEXT CHECK (status IN ('pending', 'analyzing', 'deliberating', 'converged', 'adjudicated', 'error')),
 current_round INTEGER DEFAULT0,
 max_rounds INTEGER DEFAULT5,
 convergence_threshold FLOAT DEFAULT0.05,
 input_artifacts JSONB NOT NULL,
 final_verdict JSONB,
 created_at TIMESTAMPTZ DEFAULT NOW(),
 updated_at TIMESTAMPTZ DEFAULT NOW(),
 retention_until TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '7 days')
);

--证据表
CREATE TABLE evidences (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
 agent_type TEXT CHECK (agent_type IN ('forensics', 'osint', 'cross_validation')),
 evidence_type TEXT, -- 'visual_anomaly', 'audio_spectrum', 'domain_reputation', etc.
 content JSONB NOT NULL, --具体证据内容
 confidence_score FLOAT CHECK (confidence_score >=0 AND confidence_score <=1),
 source_api TEXT, --来源API名称
 created_at TIMESTAMPTZ DEFAULT NOW()
);

--质询记录表
CREATE TABLE challenges (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
 round INTEGER NOT NULL,
 target_agent TEXT,
 target_evidence_id UUID REFERENCES evidences(id),
 question TEXT NOT NULL,
 required_action TEXT,
 priority TEXT,
 resolved BOOLEAN DEFAULT FALSE,
 resolution_result JSONB,
 created_at TIMESTAMPTZ DEFAULT NOW()
);

--专家会诊记录
CREATE TABLE expert_interventions (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 investigation_id UUID REFERENCES investigations(id) ON DELETE CASCADE,
 expert_id UUID REFERENCES auth.users(id),
 intervention_type TEXT CHECK (intervention_type IN ('comment', 'force_stop', 'request_recheck')),
 content TEXT NOT NULL,
 created_at TIMESTAMPTZ DEFAULT NOW()
);

--审计日志表
CREATE TABLE audit_logs (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 investigation_id UUID REFERENCES investigations(id) ON DELETE SET NULL,
 user_id UUID REFERENCES auth.users(id),
 action TEXT NOT NULL,
 details JSONB,
 ip_address INET,
 created_at TIMESTAMPTZ DEFAULT NOW()
);
```

###6.2 RLS (行级安全)策略

```sql
--用户只能看到自己的案件（除非是管理员或受邀专家）
CREATE POLICY "Users can view own investigations" ON investigations
 FOR SELECT USING (
 auth.uid() = created_by
 OR auth.uid() IN (
 SELECT expert_id FROM expert_interventions
 WHERE investigation_id = investigations.id
 )
 OR EXISTS (
 SELECT1 FROM user_roles
 WHERE user_id = auth.uid() AND role = 'admin'
 )
 );

--只有创建者可以删除自己的案件
CREATE POLICY "Users can delete own investigations" ON investigations
 FOR DELETE USING (auth.uid() = created_by);
```

##7.向量存储 (pgvector)设计

```sql
--高危特征向量库（用于快速比对）
CREATE TABLE threat_vectors (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 vector_type TEXT, -- 'deepfake_pattern', 'malicious_domain', 'audio_fingerprint'
 embedding VECTOR(1536), -- OpenAI/text-embedding-3-large维度
 metadata JSONB,
 source_case_id TEXT,
 created_at TIMESTAMPTZ DEFAULT NOW()
);

--创建相似度搜索索引
CREATE INDEX ON threat_vectors USING ivfflat (embedding vector_cosine_ops);

-- Agent记忆向量（长期学习能力）
CREATE TABLE agent_memories (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 agent_type TEXT,
 memory_type TEXT, -- 'success_pattern', 'failure_lesson', 'edge_case'
 embedding VECTOR(1536),
 content TEXT,
 case_reference UUID,
 created_at TIMESTAMPTZ DEFAULT NOW()
);
```

##8.前端状态管理 (Zustand Store)

```typescript
interface InvestigationStore {
 //当前案件状态
 currentCase: InvestigationState | null;

 //3D视图状态
 cameraPosition: { x: number; y: number; z: number };
 focusedPanel: 'media' | 'forensics' | 'osint' | 'inquisitor' | null;

 //实时连接
 isConnected: boolean;
 onlineExperts: UserPresence[];

 // UI状态
 showDetailedLogs: boolean;
 selectedEvidenceId: string | null;
 playbackState: 'idle' | 'playing' | 'paused';

 // Actions
 setCameraPosition: (pos: Vector3) => void;
 focusPanel: (panel: PanelType) => void;
 toggleDetailedLogs: () => void;
 addExpertComment: (comment: ExpertComment) => void;
}
```

---

*文档版本: v1.0*
*更新日期:2026-03-01*
