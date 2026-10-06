"""鹤峰皮影剧团下乡场景播种数据。

故事线（2026 年秋，走马镇下乡）：
- 明清老皮影默认 research；佘太君、穆桂英老影偶有现代表演替身；
- 佘太君老影偶虫蛀脆化，修缮前后照片存档（含未公开细节）；
- 田老先生高龄退出、学徒小周请假、大锣故障，按最低阵容判断能否演出；
- 场地确认后签发节目/人员/运输清单，老物件自动改派替身；
- 出库、演出、逐件归还闭环；公开扫码只讲故事不泄密。
"""
from __future__ import annotations

from src.app import TroupeSystem

# ---- 标识 ----
OBJ_SHE = "obj-she-taijun"        # 明代·佘太君老影偶
OBJ_SHE_HEAD = "obj-she-head"     # 佘太君头茬（部件）
OBJ_MU = "obj-mu-guiying"         # 清代·穆桂英老影偶
OBJ_YANG = "obj-yang-zongbao"     # 现代·杨宗保影偶（常规道具）
OBJ_SCREEN = "obj-shadow-screen"  # 现代影窗与灯具
REP_SHE = "rep-she-taijun"        # 佘太君表演替身
REP_MU = "rep-mu-guiying"         # 穆桂英表演替身

ROLE_LEAD = "role-lead-puppeteer"
ROLE_SINGER = "role-singer"
ROLE_BACKUP = "role-backup-puppeteer"

P_TIAN = "person-tian"
P_XIANG = "person-xiang"
P_ZHOU = "person-zhou"
P_LI = "person-li"
P_WANG = "person-wang"

INST_SIHU = "inst-sihu"
INST_SUONA = "inst-suona"
INST_GONG = "inst-luogong"

PROG_FAN = "prog-fanjiangguan"
PROG_TEA = "prog-chashan"
VER_FAN = "ver-fanjiang-traditional"
VER_TEA = "ver-chashan-newera"

VENUE_MAPING = "venue-maping-cunyanchang"
ROSTER_FAN = "roster-2026-10-maping-fan"
TRIP_FAN = "trip-2026-10-maping"


def bootstrap() -> TroupeSystem:
    """构建演出前一天（大锣已修好、学徒已请假）的系统状态。"""
    sys_ = TroupeSystem()
    e = sys_

    # ---- 藏品：材质、年代、库位、使用策略 ----
    e.classify_object(
        OBJ_SHE, name="佘太君影偶（明代传世）", category="整身影偶",
        material="驴皮硝制雕刻", era="明代", year_estimate="约16世纪",
        use_policy="research", storage_location="藏柜A-12-03",
        heritage_note="田氏家传，鹤峰西路皮影开脸样式的代表",
        occurred_at="2026-09-20T09:00:00+08:00")
    e.register_component(
        OBJ_SHE_HEAD, parent_object_id=OBJ_SHE, name="佘太君头茬",
        position="头部（可插拔头茬）", material="驴皮", era="明代",
        use_policy="research", storage_location="藏柜A-12-04",
        occurred_at="2026-09-20T09:20:00+08:00")
    e.classify_object(
        OBJ_MU, name="穆桂英影偶（清代传世）", category="整身影偶",
        material="黄牛皮雕刻", era="清代", year_estimate="约19世纪",
        use_policy="controlled_display", storage_location="藏柜A-13-01",
        occurred_at="2026-09-20T09:40:00+08:00")
    e.classify_object(
        OBJ_YANG, name="杨宗保影偶（现代演出用）", category="整身影偶",
        material="牛皮雕刻", era="现代", year_estimate="2018年",
        use_policy="performance", storage_location="道具架B-02",
        occurred_at="2026-09-20T10:00:00+08:00")
    e.classify_object(
        OBJ_SCREEN, name="下乡影窗与LED灯组", category="舞台装置",
        material="白布幕、铝合金架", era="现代", use_policy="performance",
        storage_location="道具架B-08", occurred_at="2026-09-20T10:20:00+08:00")

    # ---- 替身道具 ----
    e.classify_object(
        REP_SHE, name="佘太君影偶（2021复制件）", category="整身影偶",
        material="牛皮雕刻", era="现代", year_estimate="2021年",
        use_policy="performance", storage_location="道具架B-03",
        occurred_at="2026-09-20T10:40:00+08:00")
    e.designate_replica(REP_SHE, target_object_id=OBJ_SHE, replica_type="performance",
                        quality_note="按原件开脸与尺寸复制，签杆加固适合巡演",
                        occurred_at="2026-09-20T10:50:00+08:00")
    e.classify_object(
        REP_MU, name="穆桂英影偶（2022复制件）", category="整身影偶",
        material="牛皮雕刻", era="现代", year_estimate="2022年",
        use_policy="performance", storage_location="道具架B-04",
        occurred_at="2026-09-20T11:00:00+08:00")
    e.designate_replica(REP_MU, target_object_id=OBJ_MU, replica_type="performance",
                        quality_note="靠子与翎子做了耐振处理",
                        occurred_at="2026-09-20T11:10:00+08:00")

    # ---- 病害与修缮（照片全程保留） ----
    e.assess_condition(
        OBJ_SHE, assessment_id="assess-2026-001", condition="病害严重",
        diseases=["虫蛀孔洞3处", "皮质脆化", "右臂签线松脱"],
        assessor="州博物馆 冉修复师", occurred_at="2026-09-22T14:00:00+08:00",
        note="仅适合研究与受控展示，禁止操作签杆")
    e.document_repair(
        OBJ_SHE, repair_id="repair-2026-001", status="in_progress",
        scope="虫蛀孔洞加固与右臂签线复位", method="传统鱼鳔拼贴 + 衬皮加固",
        repaired_by="冉修复师",
        before_photos=[
            {"uri": "photo://repair-2026-001/before-1", "caption": "右臂虫蛀孔洞全景"},
            {"uri": "photo://repair-2026-001/before-2", "caption": "头茬榫口脆化细部"},
        ],
        started_at="2026-09-25T09:00:00+08:00",
        occurred_at="2026-09-25T09:05:00+08:00",
        private_note="内衬用旧档案皮样比对取样，检测数据未公开", disclosed=False)
    e.document_repair(
        OBJ_SHE, repair_id="repair-2026-001", status="completed",
        scope="虫蛀孔洞加固与右臂签线复位", method="传统鱼鳔拼贴 + 衬皮加固",
        repaired_by="冉修复师",
        before_photos=[
            {"uri": "photo://repair-2026-001/before-1", "caption": "右臂虫蛀孔洞全景"},
            {"uri": "photo://repair-2026-001/before-2", "caption": "头茬榫口脆化细部"},
        ],
        after_photos=[
            {"uri": "photo://repair-2026-001/after-1", "caption": "加固后右臂正面"},
        ],
        started_at="2026-09-25T09:00:00+08:00",
        completed_at="2026-10-04T17:00:00+08:00",
        occurred_at="2026-10-04T17:10:00+08:00",
        private_note="固化后仍建议平放，不进演出囊匣", disclosed=False)
    # 复检补拍：后继事件只能增补照片，旧照片不丢
    e.document_repair(
        OBJ_SHE, repair_id="repair-2026-001", status="completed",
        scope="虫蛀孔洞加固与右臂签线复位（复检补拍）",
        method="传统鱼鳔拼贴 + 衬皮加固", repaired_by="冉修复师",
        before_photos=[],
        after_photos=[
            {"uri": "photo://repair-2026-001/after-2", "caption": "复检背面衬皮贴合情况"},
        ],
        completed_at="2026-10-05T11:00:00+08:00",
        occurred_at="2026-10-05T11:05:00+08:00", disclosed=True)

    # ---- 角色（传统剧目与新编剧共用） ----
    e.define_role(ROLE_LEAD, name="主签手", role_kind="manipulation",
                  note="挑大梁操控主角影偶", occurred_at="2026-08-28T09:00:00+08:00")
    e.define_role(ROLE_SINGER, name="主唱", role_kind="vocal", note="旦末主唱兼念白",
                  occurred_at="2026-08-28T09:05:00+08:00")
    e.define_role(ROLE_BACKUP, name="副签手", role_kind="manipulation", note="配角与换茬",
                  occurred_at="2026-08-28T09:10:00+08:00")

    # ---- 人员（含高龄艺人与未成年学徒） ----
    e.register_person(P_TIAN, name="田老先生", is_minor=False, birth_year=1947,
                      note="西路皮影老艺人，佘太君戏路传人",
                      occurred_at="2026-08-28T10:00:00+08:00")
    e.register_person(P_XIANG, name="向师傅", is_minor=False, birth_year=1971,
                      occurred_at="2026-08-28T10:05:00+08:00")
    e.register_person(P_ZHOU, name="小周", is_minor=True, birth_year=2010,
                      apprentice_of=P_XIANG, contact="监护人 周师傅 13900000000",
                      occurred_at="2026-08-28T10:10:00+08:00")
    e.register_person(P_LI, name="李姐", is_minor=False, birth_year=1984,
                      occurred_at="2026-08-28T10:15:00+08:00")
    e.register_person(P_WANG, name="王乐师", is_minor=False, birth_year=1979,
                      occurred_at="2026-08-28T10:20:00+08:00")

    e.grant_role_qualification(P_TIAN, role_id=ROLE_LEAD,
                               occurred_at="2026-09-01T10:00:00+08:00")
    e.grant_role_qualification(P_TIAN, role_id=ROLE_SINGER,
                               occurred_at="2026-09-01T10:05:00+08:00")
    e.grant_role_qualification(P_XIANG, role_id=ROLE_LEAD,
                               occurred_at="2026-09-01T10:10:00+08:00")
    e.grant_role_qualification(P_XIANG, role_id=ROLE_SINGER,
                               occurred_at="2026-09-01T10:15:00+08:00")
    e.grant_role_qualification(P_LI, role_id=ROLE_BACKUP,
                               occurred_at="2026-09-01T10:20:00+08:00")
    e.grant_role_qualification(P_LI, role_id=ROLE_SINGER,
                               occurred_at="2026-09-01T10:25:00+08:00")
    e.grant_role_qualification(P_ZHOU, role_id=ROLE_BACKUP,
                               occurred_at="2026-09-01T10:30:00+08:00",
                               note="学徒，可任副签手")
    e.grant_accompaniment_qualification(P_WANG, instrument_id=INST_SIHU,
                                        occurred_at="2026-09-01T10:35:00+08:00")
    e.grant_accompaniment_qualification(P_WANG, instrument_id=INST_SUONA,
                                        occurred_at="2026-09-01T10:40:00+08:00")
    e.grant_accompaniment_qualification(P_WANG, instrument_id=INST_GONG,
                                        occurred_at="2026-09-01T10:45:00+08:00")

    # ---- 乐器 ----
    e.register_instrument(INST_SIHU, name="四胡", instrument_kind="string",
                          transport_note="琴筒朝上平放，避免受压",
                          occurred_at="2026-08-28T11:00:00+08:00")
    e.register_instrument(INST_SUONA, name="唢呐", instrument_kind="wind",
                          transport_note="哨片单独收纳防潮",
                          occurred_at="2026-08-28T11:05:00+08:00")
    e.register_instrument(INST_GONG, name="大锣", instrument_kind="percussion",
                          transport_note="锣面之间加软隔垫",
                          occurred_at="2026-08-28T11:10:00+08:00")

    # ---- 高龄艺人退出、学徒缺席、乐器故障 → 后修复 ----
    e.change_member_status(P_TIAN, status="retired", reason="高龄退出一线演出，转艺术顾问",
                           occurred_at="2026-09-28T09:00:00+08:00")
    e.change_member_status(P_ZHOU, status="apprentice_leave",
                           reason="随监护人外出，10月中旬缺席",
                           occurred_at="2026-10-15T18:00:00+08:00")
    e.change_instrument_status(INST_GONG, status="faulty", reason="锣绳断裂、锣槌开裂",
                               occurred_at="2026-10-15T19:30:00+08:00",
                               transport_note="故障待修，暂不装车")
    e.change_instrument_status(INST_GONG, status="available", reason="更换锣绳与锣槌，试音正常",
                               occurred_at="2026-10-16T11:00:00+08:00",
                               transport_note="锣面之间加软隔垫")

    # ---- 节目与最低阵容 ----
    e.define_program(
        PROG_FAN, title="樊江关",
        cast_requirements=[{"role_id": ROLE_LEAD, "count": 1},
                           {"role_id": ROLE_SINGER, "count": 1},
                           {"role_id": ROLE_BACKUP, "count": 1}],
        accompaniment_requirements=[{"instrument_id": INST_SIHU, "count": 1},
                                    {"instrument_id": INST_SUONA, "count": 1},
                                    {"instrument_id": INST_GONG, "count": 1}],
        note="传统袍带戏，下乡常演", occurred_at="2026-09-02T09:00:00+08:00")
    e.define_program(
        PROG_TEA, title="鹤峰新风·茶山趣事",
        cast_requirements=[{"role_id": ROLE_LEAD, "count": 1},
                           {"role_id": ROLE_BACKUP, "count": 1}],
        accompaniment_requirements=[{"instrument_id": INST_SIHU, "count": 1},
                                    {"instrument_id": INST_GONG, "count": 1}],
        note="新时代现实题材改编，角色与传统戏共用",
        occurred_at="2026-09-02T09:30:00+08:00")

    # ---- 剧目版本：唱词来源与适用场合分别审定 ----
    e.create_script_version(
        VER_FAN, program_id=PROG_FAN, title="樊江关",
        version_label="田氏口述本·1986整理", lineage="traditional",
        lyrics_source="田氏家传口述老唱本（1986年县文化馆记谱）",
        synopsis="樊江关姑嫂较艺、姑嫂释怨的传统故事",
        public_synopsis="鹤峰西路皮影传统剧目，唱腔风趣，展现姑嫂和解。",
        occurred_at="2026-09-05T09:00:00+08:00")
    e.approve_lyrics(VER_FAN, lyrics_source="田氏家传口述老唱本（1986年县文化馆记谱）",
                     decision="approved", approved_by="县非遗保护中心审定组",
                     occurred_at="2026-09-12T10:00:00+08:00")
    e.approve_occasion(VER_FAN, occasion="countryside_tour", decision="approved",
                       approved_by="县非遗保护中心审定组",
                       occurred_at="2026-09-12T10:10:00+08:00")
    e.approve_occasion(VER_FAN, occasion="school", decision="approved",
                       approved_by="县非遗保护中心审定组",
                       occurred_at="2026-09-12T10:20:00+08:00",
                       conditions="演出前加5分钟方言讲解")

    e.create_script_version(
        VER_TEA, program_id=PROG_TEA, title="鹤峰新风·茶山趣事",
        version_label="2024县文化馆改编本", lineage="new_era_adaptation",
        lyrics_source="县文化馆2024年新时代题材改编唱词",
        based_on_version_id=VER_FAN,
        synopsis="茶山村年轻人返乡办茶厂的现代故事",
        public_synopsis="取材鹤峰茶山的新编剧，老皮偶演身边新事。",
        occurred_at="2026-09-05T10:00:00+08:00")
    e.approve_lyrics(VER_TEA, lyrics_source="县文化馆2024年新时代题材改编唱词",
                     decision="approved", approved_by="县文旅局内容审定组",
                     occurred_at="2026-09-15T15:00:00+08:00")
    e.approve_occasion(VER_TEA, occasion="countryside_tour", decision="approved",
                       approved_by="县文旅局内容审定组",
                       occurred_at="2026-09-15T15:10:00+08:00")
    e.approve_occasion(VER_TEA, occasion="school", decision="approved",
                       approved_by="县文旅局内容审定组",
                       occurred_at="2026-09-15T15:20:00+08:00")

    # ---- 场地方确认日期与条件 ----
    e.record_venue(
        VENUE_MAPING, name="走马镇马家坪村晒谷场",
        performance_date="2026-10-17",
        conditions={"台口宽度": "3.2米", "电源": "有220V", "场地": "露天/自备雨布"},
        transport_access="村道限高2.8米，大车停小学操场，用小板车转运",
        contact="村部 马主任 13800000000",
        occurred_at="2026-10-10T11:00:00+08:00")

    # ---- 排班：沿用旧本子的装车习惯，申请里又写了老影偶 ----
    e.confirm_roster(
        ROSTER_FAN, program_id=PROG_FAN, version_id=VER_FAN,
        venue_id=VENUE_MAPING, performance_date="2026-10-17",
        occasion="countryside_tour", venue_confirmed=True,
        object_ids=[OBJ_SHE, OBJ_MU, OBJ_YANG, OBJ_SCREEN],
        confirmed_by="向师傅", occurred_at="2026-10-16T15:00:00+08:00",
        note="排练后照单点的装车单，误填了明代佘太君")

    # ---- 公开扫码资料：只讲技艺故事 ----
    e.publish_public_profile(
        "puppet_object", OBJ_SHE, profile_kind="object",
        title="明代佘太君影偶：驴皮上的鹤峰开脸",
        story="这件传世影偶以驴皮硝制后手工雕刻，采用鹤峰西路特有的整脸刻法，"
              "刀法刚劲、染色经数百年仍沉着。老艺人口传，影偶开脸要'一身之戏在于脸'。",
        craft_note="传统鱼鳔拼贴与衬皮加固工艺可用于影偶病害保护。",
        public_photo_uris=["photo://public/she-taijun-face"],
        occurred_at="2026-10-08T10:00:00+08:00")
    e.publish_public_profile(
        "repertoire_version", VER_FAN, profile_kind="program",
        title="传统剧目《樊江关》",
        story="《樊江关》是鹤峰皮影下乡常演的袍带戏，唱念并重，"
              "一口道尽千古事，双手对舞百万兵。",
        occurred_at="2026-10-08T10:20:00+08:00")

    return sys_
