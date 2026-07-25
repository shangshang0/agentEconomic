# Agent Economic

[English README](README.md)

Agent Economic 是一套开放、可审计的多智能体制度经济实验。六个语言模型智能体在资源稀缺的世界中沟通、分配工作、生产奖励、转移能量，并受到可执行的生存规则约束。本仓库发布完整实验运行时、冻结协议、启动与恢复 provenance、MCP server、Codex Skill，以及公开数据的完整性审计工具。

## 发布内容

- `public-data-v1` 中恰好 8 个注册 Stage 1 confirmatory world 与 12 个注册机制消融 world；
- 经确定性脱敏的模型 prompt/response gateway trace、agent memory、追加式事件流、终态 state、watchdog 日志与 recovery amendment；
- 解释所有实验所需的运行时、配置、launcher、supervisor 与 watchdog 版本；
- 机器可读的 run catalog、源文件到公开文件的脱敏账本、SHA-256 manifest，以及可独立重算注册统计量的脚本；

探索性、technical-failed、contaminated、legacy 和 operator-history 资产不上传
GitHub，只保存在权限隔离的 Mac 本机 custody 归档中，且绝不会被悄悄并入
正式估计。Stage 2 与最终论文材料只在冻结终态及分析门禁通过后追加；
`public-data-v1` 不包含二者。

大型 trace 不作为普通 Git blob 提交，而是放在本仓库对应的版本化 GitHub Release 中。`data/catalog/releases.json` 会把每个 world 映射到具体分卷和校验值。

## 一键部署

需要 Docker Compose v2、Python 3.11+ 和 OpenAI-compatible provider 凭据。凭据只会写入本地权限为 0600、且被 Git 忽略的文件。

```bash
OPENAI_API_KEY='your-key' OPENAI_BASE_URL='https://api.example/v1' make deploy
```

该命令会生成本地控制 token、运行离线部署检查、构建隔离 Compose stack，
并等待 backend health check。仓库内置 task catalog 足以验证结构部署；不允许
再分发的 challenge 源文件必须从上游合法取得，并通过
`CTF_SOURCE_HOST_ROOT` 挂载。请只使用你有权使用的任务和 provider/model，
严禁提交 `.env.runtime`。

不调用 provider 的离线结构测试：

```bash
make smoke
```

## 下载并核验全部公开证据

```bash
python3 scripts/fetch_release.py --release public-data-v1 --all
python3 scripts/verify_manifest.py data/manifests/public-data-manifest.json \
  --root data/releases/public-data-v1/extracted
python3 scripts/audit_catalog.py data/catalog/worlds.jsonl \
  --assets data/catalog/assets.jsonl \
  --release-root data/releases/public-data-v1/extracted
```

`fetch_release.py` 核验每个 Release 分卷的哈希并拒绝不安全的归档成员；
`verify_manifest.py` 核验解压文件集合与哈希；`audit_catalog.py` 核验
run/asset 身份、证据资格、终态/事件一致性和 canonical asset 关联。每个
world 的 `TRACE_COMPLETENESS.json` 与 `audit_trace_completeness.py` 再核验
六 agent 的 gateway/model/tool 闭合链。这些是彼此独立、可组合的门禁，
不会把一个 manifest 命令夸大成全部语义证明。

## 重算已发布的 world-level 证据

```bash
make data
make reproduce
make audit
```

统计单位是 world，不会把 message 当作独立样本做伪重复。详细规则见 [审计协议](docs/AUDIT.md) 和 [证据分层](docs/EVIDENCE_TIERS.md)。

## MCP 与 Skill

MCP server：

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[mcp]'
.venv/bin/python -m agent_economic_mcp.server
```

它提供唯一 world 与实际 asset 双层检索、provenance、事件/对话搜索、
manifest 核验和注册分析入口。将 `skills/agent-economic-auditor` 复制或
链接到 Codex skills 目录后，可通过 `$agent-economic-auditor` 使用同一套审计流程。

## 目录

- `runtime/authority_world/`：冻结实验运行时与测试；
- `infrastructure/`：launcher、supervisor、watchdog 与 amendment；
- `data/catalog/`：唯一 run、实际归档 asset 与 Release 分卷索引；
- `data/manifests/`：完整性与脱敏 manifest；
- `mcp/`：本地审计/搜索 MCP server；
- `skills/`：Codex 审计 Skill；
- `legacy/`：保留用于 provenance 的早期模拟器与协议代码；
- `scripts/`：部署、导出、核验和复现工具。

## 许可证

代码采用 Apache-2.0；原创数据与论文材料采用 CC BY 4.0；第三方 CTF、字体和美术资源沿用上游许可证。引用时请使用 `CITATION.cff`，并注明所用数据 Release 的精确校验值。
