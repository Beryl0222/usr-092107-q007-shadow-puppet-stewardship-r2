"""命令行演示：鹤峰皮影剧团下乡全流程。

运行：python3 -m src.demo
"""
from __future__ import annotations

import json

from src.app import DomainRuleError
from src.domain import check_min_staff
from src.projection import build_state
from src.seed import (
    OBJ_SHE, OBJ_YANG, P_ZHOU, PROG_FAN, ROSTER_FAN, TRIP_FAN, bootstrap,
)


def line(title: str) -> None:
    print(f"\n{'=' * 66}\n{title}\n{'=' * 66}")


def main() -> None:
    system = bootstrap()
    store = system.store

    line("一、事件账本：只追加、不改写")
    print(f"已接收领域事件 {len(store.events)} 条，聚合 {len({e['aggregate_id'] for e in store.events})} 个")
    print("任何字段更正都只能追加同聚合 version+1 的后继事件（如大锣 faulty→available）")

    line("二、场地确认后，生成真正可用的节目/人员/运输清单")
    plan = system.trip_plan(ROSTER_FAN)
    print(f"排班 {ROSTER_FAN} 可行性：{'可行' if plan['feasible'] else '不可行'}")
    print(f"节目：{plan['program']['title']}｜版本：{plan['version']['version_label']}"
          f"（{plan['version']['lineage']}）｜场地：{plan['venue']['name']}")
    print("装车核对：")
    for item in plan["objects"]:
        tag = {"loaded": "照常装车", "replaced": "改派替身", "blocked": "禁止装车"}[item["status"]]
        extra = f"（替身替代 {item['replica_for']}）" if item.get("replica_for") else ""
        print(f"  - [{tag}] {item['name']}{extra}：{item['reason']}")
    print("自动提示：")
    for warning in plan["warnings"]:
        print(f"  ! {warning}")
    print("人员最低阵容：")
    for row in plan["cast"]:
        print(f"  - {row['role_name']} 需{row['required']}，在岗合格{row['available']}")
    for row in plan["accompaniment"]:
        print(f"  - {row['instrument_name']} 需{row['required']}，"
              f"乐器状态 {row['instrument_status']}，合格乐手{row['qualified_players']}")

    line("三、签发计划并出库：老物件直接出库会被拦截")
    system.issue_trip_plan(TRIP_FAN, ROSTER_FAN, issued_by="向师傅",
                           occurred_at="2026-10-16T16:00:00+08:00")
    trip = system.state.trips[TRIP_FAN]
    print("拦截明代老影偶出库：")
    try:
        system.checkout(TRIP_FAN, OBJ_SHE, handler="向师傅",
                        expected_return_at="2026-10-17T22:00:00+08:00",
                        occurred_at="2026-10-17T07:30:00+08:00")
    except DomainRuleError as exc:
        print(f"  {exc}（老影偶留在藏柜，未上车）")

    print("按计划逐件出库：")
    for item in trip["objects"]:
        substitute_for = item.get("replica_for")
        system.checkout(TRIP_FAN, item["load_id"], handler="向师傅",
                        expected_return_at="2026-10-17T22:00:00+08:00",
                        occurred_at="2026-10-17T07:40:00+08:00",
                        substitute_for=substitute_for)
        print(f"  - 已出库：{item['name']}（{item['load_id']}）")

    line("四、最低阵容随情况变化：大锣故障时不能演，修复后可演")
    cutoff_state = build_state([e for e in store.events
                                if e["occurred_at"] < "2026-10-16T00:00:00+08:00"])
    before = check_min_staff(cutoff_state, PROG_FAN)
    after = check_min_staff(system.state, PROG_FAN)
    print("10月15日晚（大锣故障、学徒请假、田老退出）：")
    for block in before["blocks"]:
        print(f"  - {block}")
    print(f"  => 结论：{'可演出' if before['feasible'] else '不能演出，按最低阵容叫停/换节目'}")
    print("10月16日大锣修复试音后：")
    print(f"  => 结论：{'可演出' if after['feasible'] else '不能演出'}（每个岗位仍有在岗合格人员）")

    line("五、演出与逐件闭环归还")
    system.log_performance(ROSTER_FAN, trip_id=TRIP_FAN,
                           performed_at="2026-10-17T19:30:00+08:00",
                           attendance=260, note="晒谷场露天演出，观众约260人")
    print("演出已记录。归还前闭环核对：")
    open_closure = system.closure(TRIP_FAN, now="2026-10-17T22:30:00+08:00")
    print(f"  all_closed = {open_closure['all_closed']}；"
          f"未还 {sum(i['status'] != 'returned' for i in open_closure['items'])} 件")
    for item in trip["objects"]:
        system.return_object(
            f"handoff-{TRIP_FAN}-{item['load_id']}",
            returned_at="2026-10-17T21:40:00+08:00",
            condition_on_return="完好", note="点收入库")
    closed = system.closure(TRIP_FAN)
    print(f"逐件归还后：all_closed = {closed['all_closed']}，共 {len(closed['items'])} 件全部闭环")

    line("六、公开扫码：只讲技艺故事，内部信息零暴露")
    card = system.public_card("puppet_object", OBJ_SHE)
    print("明代佘太君公开介绍卡（白名单字段）：")
    print(json.dumps(card, ensure_ascii=False, indent=2))
    leaked = ["storage_location", "contact", "is_minor", "private_note"]
    shown = [k for k in card if k in leaked]
    print(f"库位/联系方式/未成年标记/未公开修缮字段出现在公开卡中：{shown or '无'}")
    repairs = system.state.objects[OBJ_SHE]["repairs"][0]
    print(f"内部修缮档案仍完整保留：修复前照片 {len(repairs['before_photos'])} 张、"
          f"修复后照片 {len(repairs['after_photos'])} 张（只增不删）")
    print(f"人员不提供公开卡（未成年人资料零暴露）：{system.public_card('person', P_ZHOU)}")

    try:
        system.publish_public_profile(
            "puppet_object", OBJ_YANG, profile_kind="object",
            title="测试", story="藏品库位在道具架B-02，估价三万元",
            occurred_at="2026-10-08T11:00:00+08:00")
    except DomainRuleError as exc:
        print(f"含库位/估价的扫码资料被拒绝发布：{exc}")


if __name__ == "__main__":
    main()
