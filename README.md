# 皮影剧团藏用协同台

鹤峰皮影剧团的藏用协同系统：以**只追加的领域事件**统一管理皮影物件（含部件、材质年代、病害修缮、替身道具）、剧目脚本版本（唱词来源与适用场合分别审定）、角色与伴奏资格、人员状态、乐器、场地条件、排班、出入库交接与实际演出，并对公开扫码内容做白名单脱敏。

## 为什么是事件账本

下乡排练时老艺人差点把明清老皮影当普通道具装车，根源是藏品保护、节目排班、借用交接分散在不同人的本子里。系统规定：

- **每次变化都是一条事件**，只追加，不改写；标识、发生时间、版本不可原地修改，更正只能追加同聚合 `version+1` 的后继记录；
- 事件先过契约校验（信封 + 载荷取值域），再过业务规则（最低阵容、老物件使用策略、出库拦截、脱敏）；
- 修复前后照片随 `REPAIR_DOCUMENTED` 永久保留，投影时照片**只增不删**。

## 资料范围

- `contracts/domain.schema.json`：事件信封、聚合类型与事件名称（与 `src/contracts.py` 一致，测试会双向核对）。
- `src/contracts.py`：事件目录、载荷约定、公开内容脱敏检查。
- `src/event_store.py`：事件存储——版本连续、时间单调、ID 唯一、公开泄密写入即拒。
- `src/projection.py`：事件流 → 当前状态投影（含修缮照片累积、出入库串联）。
- `src/domain.py`：纯函数业务策略（最低阵容、替身改派、计划生成、归还闭环、公开卡）。
- `src/app.py`：应用服务，把操作翻译成事件。
- `src/seed.py`：走马镇下乡场景播种（老物件、替身、修缮、高龄退出/学徒缺席/大锣故障与修复）。
- `src/demo.py`：端到端演示。
- `data/sample.json`：一条中文联调样例。
- `tests/`：契约/存储/脱敏与完整场景测试。

个人、机构及商业敏感信息仅向履行职责所需的调用方开放；公开扫码视图只含技艺故事，不含藏品库位、未成年人资料与未公开修复细节。

## 事件目录

| 聚合 | 事件 | 含义 |
|---|---|---|
| `puppet_object` | `OBJECT_CLASSIFIED` | 整身影偶/道具建档：材质、年代、使用策略（research/controlled_display/performance）、库位（内部） |
| `puppet_object` | `COMPONENT_REGISTERED` | 部件（头茬、签杆等）登记并挂到父物件 |
| `puppet_object` | `CONDITION_ASSESSED` | 病害评估（虫蛀、脆化等）与当前完损状况 |
| `puppet_object` | `REPAIR_DOCUMENTED` | 修缮记录；同一 repair_id 的后继事件只能增补前后照片，不能删除 |
| `puppet_object` | `REPLICA_DESIGNATED` | 指定表演/展示替身，替身与原件双向关联 |
| `role` | `ROLE_DEFINED` | 角色（主签手、主唱、副签手等），传统戏与新编剧共用 |
| `person` | `PERSON_REGISTERED` | 人员建档（含 is_minor，未成年人资料不进公开视图） |
| `person` | `ROLE_QUALIFICATION_GRANTED` | 角色资格授予/暂停/撤销 |
| `person` | `ACCOMPANIMENT_QUALIFICATION_GRANTED` | 伴奏资格授予/暂停/撤销 |
| `person` | `MEMBER_STATUS_CHANGED` | 在团状态：active/apprentice_leave/retired/exited |
| `instrument` | `INSTRUMENT_REGISTERED` / `INSTRUMENT_STATUS_CHANGED` | 乐器建档；available/faulty/retired |
| `program` | `PROGRAM_MIN_STAFF_DEFINED` | 节目与最低阵容（角色位数、伴奏位数） |
| `repertoire_version` | `SCRIPT_VERSION_CREATED` | 剧目脚本版本：traditional / new_era_adaptation、唱词来源、承袭版本 |
| `repertoire_version` | `LYRICS_APPROVED` | 唱词来源审定（与场合分别审定） |
| `repertoire_version` | `OCCASION_APPROVED` | 适用场合审定（下乡、校园、文化节、受控展示等） |
| `venue` | `VENUE_CONDITIONS_RECORDED` | 场地方确认的日期、台口/电源条件、进场运输条件 |
| `performance_roster` | `ROSTER_CONFIRMED` / `PERFORMANCE_LOGGED` | 排班确认（须场地已确认）；实际演出记录挂接同一排班 |
| `trip` | `TRIP_PLAN_ISSUED` | 场地确认后签发真正可用的节目/人员/运输清单 |
| `loan_handoff` | `OBJECT_CHECKED_OUT` / `OBJECT_RETURNED` | 出库交接与归还入库，按交接逐件闭环 |
| `puppet_object` / `repertoire_version` / `role` | `PUBLIC_PROFILE_PUBLISHED` | 公开扫码资料；写入时做库位/未成年人/未公开信息泄密检查 |

## 关键规则

1. **老物件保护**：`research` 物件不能出库；`controlled_display` 仅限受控展示。下乡装车时系统自动改派表演替身，无替身则阻断计划。
2. **最低阵容**：按节目定义逐岗核对“在岗（active）+ 资格有效 + 乐器可用”。高龄艺人退出、学徒请假、乐器故障任一导致缺岗，节目即判不可演；故障修复后追加状态事件即可恢复。
3. **计划签发**：场地确认 + 版本唱词与场合双审定通过 + 最低阵容可满足 + 装车清单无阻断，才允许 `TRIP_PLAN_ISSUED`。
4. **出入库闭环**：只能按已签清单出库；老物件、修缮中、重复出库直接拦截；演出后逐件归还，`closure` 核对未还/逾期，重复归还被拒。
5. **公开脱敏**：公开卡为白名单字段；人员不提供公开卡；修缮只展示 `disclosed=True` 完成记录的工艺性描述（不含照片与私注）；含库位、联系方式、估价、未成年人等字样的公开文案写入即拒。

## 本地检查

```bash
python3 -m unittest discover -s tests
python3 -m src.demo
```
