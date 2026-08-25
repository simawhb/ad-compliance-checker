# 消费维权助手信息架构

更新：2026-08-21（Asia/Shanghai）
状态：Stage 1 冻结；Stage 2 仅实现静态 UI Shell。

## 路由

| 路径 | 页面职责 |
|---|---|
| `/weiquan/` | 角色选择、隐私提示、统一免责声明。|
| `/weiquan/consumer/` | 消费者纠纷描述、诊断/证据/路径/协商函结果区。|
| `/weiquan/business/` | 经营者投诉描述、双维度分析/反证/合规/回复函结果区。|

## 角色选择页

复用门户 Header、视觉语言和 Footer。Hero 固定为“消费维权助手 / 依法保护消费者与经营者双方合法权益”。说明固定为流程指引、证据整理与沟通模板参考，优先协商。

- 消费者卡：判断纠纷、整理证据、明确路径、生成协商函；跳转 `/weiquan/consumer/`。
- 经营者卡：分析投诉、核实事实、整理反证、合规应对、生成回复函；跳转 `/weiquan/business/`。
- 两卡之前展示敏感信息提示和“不支持证据文件上传”。

## 消费者流程与顺序

```text
Header → Intro → Privacy Notice → Problem Input → Primary Action
→ Diagnosis → Facts Missing → Legal Basis → Recommended Path
→ Evidence Checklist → Special Notes → Negotiation Letter → Copy
→ Disclaimer → Footer
```

输入为一个多行 `text`，提示商品/服务、购买与争议时间、商家及既有沟通、平台/直播/AI 客服/预付费/自动续费，以及希望结果；禁止输入无必要敏感信息。

## 经营者流程与顺序

```text
Header → Intro → Privacy Notice → Complaint Input → Primary Action
→ Dispute Classification → Facts Known → Facts Missing
→ Consumer Claim Basis → Business Response Points → Evidence
→ Possible Abnormal Claim Features → Compliance Check → Recommended Path
→ Formal Reply → Advertising Review Link → Disclaimer → Footer
```

经营者分析固定为两维：

1. **争议本身**：可能存在真实商品问题、售后履行问题、使用不当、证据不足、事实争议或暂无法判断。
2. **异常索赔特征**：仅供进一步核实，如批量/高频/同类集中购买、模板化投诉、关联争议、未充分协商即异常高额索赔。

异常特征不等于职业打假或恶意投诉结论。页面及后续模型不得输出“职业打假人”“恶意投诉”“消费者无权投诉”“无需赔偿”或“敲诈”等定性。

## Stage 2 UI 状态

消费者端和经营者端都必须实现：Empty、Typing、Loading、Success、Error、Provider unavailable、Copy success、Input validation。Stage 2 使用静态数据，不作真实请求。

## MVP 非范围

账号、登录、收费、案件历史、文件上传、OCR、律师服务/匹配、自动提交 12315、自动发函/发邮件、诉讼材料包、RAG/向量库、CRM、画像、职业打假数据库、黑名单均不做。
