import base64
import os
from collections import Counter
from io import BytesIO
from itertools import groupby

import streamlit as st

from utils.claude_client import parse_order
from utils.database import add_order, get_all_orders, clear_all_orders
from utils.excel_exporter import export_to_excel, parse_items

# ── 硬编码：全校配送地址 ────────────────────────────────
AREAS = {
    "🏫 教学楼": [
        "1号教学楼（一教）", "2号教学楼（二教）", "3号教学楼（三教）",
        "4号教学楼（法学院）", "5号教学楼（五教）", "6号教学楼（六教）",
        "7号教学楼（七教）", "8号教学楼（实验楼）", "9号教学楼（九教）",
        "10号教学楼（十教）", "11号教学楼（十一教）", "12号教学楼（十二教）",
        "13号教学楼（十三教）", "14号教学楼（十四教）", "15号教学楼（十五教）",
        "16号教学楼（建筑学院）", "经管大楼", "港航中心", "电苑楼",
        "图书馆A/B馆",
    ],
    "🌳 西苑": [
        "西苑1栋", "西苑2栋", "西苑3栋", "西苑4栋", "西苑5栋",
        "西苑6栋", "西苑7栋", "西苑8栋", "西苑9栋", "西苑10栋", "西苑11栋",
    ],
    "🌅 东苑": [
        "东苑1栋", "东苑2栋", "东苑3栋", "东苑4栋", "东苑5栋",
        "东苑6栋", "东苑7栋", "东苑8栋", "东苑9栋", "东苑10栋",
        "东苑11栋", "东苑12栋", "东苑13栋", "东苑14栋", "东苑15栋",
        "外教楼",
    ],
    "🌿 南苑": [
        "南苑1栋", "南苑2栋", "南苑3栋", "南苑4栋",
        "南苑5栋", "南苑6栋", "南苑7栋", "南苑8栋",
    ],
}
ALL_ADDRESSES = []
for area, buildings in AREAS.items():
    for b in buildings:
        ALL_ADDRESSES.append(f"{area.split()[1]} · {b}")

# ── 页面配置 ──────────────────────────────────────────────
st.set_page_config(
    page_title="麦当劳早餐配送",
    page_icon="🍔",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── 从 Secrets 读取敏感配置（Streamlit Cloud）──────────
AI_API_KEY = ""
AI_PROVIDER = "DeepSeek (兼容)"
try:
    AI_API_KEY = st.secrets.get("AI_API_KEY", os.getenv("AI_API_KEY", ""))
    AI_BASE_URL = st.secrets.get("AI_BASE_URL", os.getenv("AI_BASE_URL", ""))
except Exception:
    AI_API_KEY = os.getenv("AI_API_KEY", "")

ADMIN_PASSWORD = "mcd123"
try:
    ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "mcd123")
except Exception:
    pass

# ── 判断管理员 ───────────────────────────────────────────
query_params = st.query_params
is_admin = bool(
    query_params.get("mode") == "admin" or st.session_state.get("admin")
)

# ── 侧边栏（只对管理员显示入口）─────────────────────────
with st.sidebar:
    pwd = st.text_input(
        "管理员验证", type="password", placeholder="输入密码",
        label_visibility="collapsed",
    )
    if pwd == ADMIN_PASSWORD:
        st.session_state["admin"] = True
        is_admin = True
        st.success("✅ 管理员模式已激活")
    elif pwd:
        st.error("❌ 密码错误")

# ── 学生端 ────────────────────────────────────────────────
st.title("🍔 麦当劳早餐配送")
st.markdown("上传截图 → 选择地址 → 提交，你的早餐信息直达配单员。")

st.subheader("📌 步骤一：上传订单截图")
uploaded_file = st.file_uploader(
    "上传麦当劳订单截图",
    type=["jpg", "jpeg", "png"],
    label_visibility="collapsed",
)
if uploaded_file:
    st.image(uploaded_file, use_container_width=True)
else:
    st.info("📷 点击上方按钮从相册选择截图")

st.subheader("📌 步骤二：选择配送地址")
col_area, col_addr = st.columns([1, 2])
with col_area:
    selected_area = st.selectbox("区域", list(AREAS.keys()), index=0, label_visibility="collapsed")
with col_addr:
    buildings = AREAS[selected_area]
    selected_building = st.selectbox("地址", buildings, index=0, label_visibility="collapsed")

final_address = f"{selected_area.split()[1]} · {selected_building}"

if st.button("📤 提交订单", type="primary", use_container_width=True):
    if not uploaded_file:
        st.error("❌ 请先上传订单截图")
        st.stop()

    image_bytes = uploaded_file.getvalue()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    # AI 解析（如果配置了 API Key）
    pickup_time, items, amount = "", "", ""
    if AI_API_KEY:
        with st.spinner("🤖 正在识别订单内容..."):
            result = parse_order(image_bytes, AI_API_KEY)
            if result:
                pickup_time = result.get("pickup_time", "")
                items = result.get("items", "")
                amount = result.get("amount", "")
            else:
                st.warning("⚠️ AI 识别未返回有效数据，将以纯图片形式保存")

    ok = add_order(
        address=final_address,
        image_base64=image_b64,
        pickup_time=pickup_time,
        items=items,
        amount=amount,
    )

    if ok:
        st.success("✅ 提交成功！感谢配合 🎉")
        if pickup_time:
            with st.expander("📋 AI 识别详情", expanded=True):
                c1, c2 = st.columns(2)
                c1.metric("配送地址", final_address)
                c1.metric("取餐时间", pickup_time)
                c2.metric("餐品详情", items)
                c2.metric("实付金额", amount)
    else:
        st.error("❌ 提交失败，请稍后重试")

# ── 管理员端 ──────────────────────────────────────────────
if is_admin:
    st.divider()
    st.subheader("📊 管理员 · 今日配单看板")
    st.caption(
        "💡 下次直接访问 "
        f"`http://localhost:8501/?mode=admin` 即可自动进入"
    )

    orders = get_all_orders()
    if not orders:
        st.info("暂无订单数据。")
    else:
        st.markdown(f"**共 {len(orders)} 个订单**")

        # 数据总表
        df_data = [
            {
                "配送地址": r.get("address", ""),
                "取餐时间": r.get("pickup_time", ""),
                "餐品详情": r.get("items", ""),
                "金额": r.get("amount", ""),
            }
            for r in orders
        ]
        st.dataframe(df_data, use_container_width=True, hide_index=True)

        # 餐品汇总
        st.markdown("**🧾 餐品总量汇总**")
        counter: dict[str, int] = Counter()
        for r in orders:
            for name, qty in parse_items(r.get("items", "")):
                counter[name] += qty
        if counter:
            st.dataframe(
                [{"餐品名称": n, "总计份数": q} for n, q in sorted(counter.items())],
                use_container_width=True,
                hide_index=True,
            )

        # 地址图片墙
        st.markdown("---")
        st.markdown("**🖼️ 按地址配单视觉看板**")
        for address, group in groupby(
            sorted(orders, key=lambda r: r["address"]),
            key=lambda r: r["address"],
        ):
            glist = list(group)
            with st.expander(f"📍 {address}（共 {len(glist)} 单）", expanded=False):
                for i in range(0, len(glist), 3):
                    row = glist[i : i + 3]
                    cols = st.columns(len(row))
                    for col, item in zip(cols, row):
                        with col:
                            b64 = item.get("image_base64", "")
                            if b64:
                                st.image(BytesIO(base64.b64decode(b64)), use_container_width=True)
                            info = []
                            if item.get("pickup_time"):
                                info.append(f"🕐 {item['pickup_time']}")
                            if item.get("items"):
                                info.append(f"🍔 {item['items']}")
                            if info:
                                st.caption(" | ".join(info))
                            st.caption(f"⏱ {item.get('created_at', '')}")

        # 操作按钮
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 1, 4])
        with col1:
            buf = export_to_excel(orders)
            st.download_button(
                "📥 导出 Excel",
                data=buf,
                file_name="麦当劳早餐配送统计.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with col2:
            if st.button("🗑️ 清空数据", type="secondary", use_container_width=True):
                deleted = clear_all_orders()
                if deleted:
                    st.success(f"已清空 {deleted} 条数据")
                    st.rerun()
