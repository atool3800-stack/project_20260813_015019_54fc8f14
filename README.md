# project_20260813_015019_54fc8f14

North American logistics transportation exception tickets (US & Canada) — weekly exception summary auto-synced to README.

## 项目介绍 (Project Overview)

本仓库用于管理北美（美国、加拿大）物流运输公司的运输异常工单（约 5600+ 条），覆盖延误、货损、清关异常、温控偏差等异常类型。每周一运营团队通过自动化脚本从 GitHub Issues 中拉取过去 7 天符合条件的工单，自动生成 **Weekly Logistics Exception Summary** 周报并同步到本 README 的指定区块，替代人工筛选统计（原先耗时 3+ 小时）。

### 工单标签约定 (Ticket Labeling Convention)

每个运输异常工单使用以下标签进行分类：

| 维度 | 标签 |
| --- | --- |
| 工单类型 | `logistics` |
| 国家/地区 | `location:us`, `location:ca` |
| 区域 | `region:us-west`, `region:us-midwest`, `region:us-east`, `region:ca-west`, `region:ca-east` |
| 异常类型 | `type:delay`, `type:damage`, `type:customs`, `type:temperature`, `type:other` |

### 自动化流程 (Automation Workflow)

1. 通过 GitHub API 分页拉取所有标签包含 `logistics` 且包含 `location:us` / `location:ca` 的工单（单页 100 条，完整分页、不遗漏）。
2. 筛选创建或更新时间在过去 7 天内的工单。
3. 按区域 × 异常类型分组统计：数量、总占比、平均处理小时数。
4. 生成 Markdown 周报并写入下方指定区块（仅替换区块内容，保留其余文档）。
5. 提交并推送，提交信息格式 `weekly-logistics-report YYYY-MM-DD`。

---

## Weekly Logistics Exception Summary

<!-- WEEKLY_LOGISTICS_REPORT_START -->
<!-- WEEKLY_LOGISTICS_REPORT_END -->

---

## 运维说明 (Operations Guide)

- 每周一上午运行 `python3 scripts/weekly_logistics_report.py` 即可自动刷新周报。
- 脚本使用环境变量 `GITHUB_TOKEN` 进行认证；仓库与分支可通过参数覆盖。
- 若某周无符合条件的工单，周报区块将显示“本周无异常工单”。
- 如需调整区域划分或异常类型，请修改脚本中的映射表并保持标签约定一致。

## 数据统计口径 (Metrics Definitions)

- **统计窗口**：过去 7 天（含）内创建或更新的工单。
- **平均处理小时数**：工单正文中 `Handling Hours` 字段的算术平均值。
- **占比**：各分组工单数 / 窗口内工单总数 × 100%。
- **Top 5 高频异常路线/客户**：按工单标题解析出的路线（Route）与客户（Customer）组合出现频次排序。

## License

Internal use only.
