import base64
import os
from collections import Counter
from io import BytesIO
from itertools import groupby

import pandas as pd
import psycopg2
import streamlit as st

# ── 页面配置 ──────────────────────────────────────────────
st.set_page_config(
    page_title="麦当劳早餐配送",
    page_icon="🍔",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── 数据库连接 ────────────────────────────────────────────
def get_conn():
    try:
        return psycopg2.connect(st.secrets["DATABASE_URL"])
    except Exception as e:
        st.error(f"❌ 数据库连接失败: {e}")
        return None


def init_db():
    conn = get_conn()
    if conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS mcd_orders (
                    id SERIAL PRIMARY KEY,
                    address TEXT NOT NULL,
                    image_base64 TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
        conn.close()


init_db()

# ── 硬编码地址 ────────────────────────────────────────────
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
        "西苑6栋", "西苑7栋", "西苑8栋", "西苑9栋", "西苑10栋",
        "西苑11栋",
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

# ── 管理员状态 ────────────────────────────────────────────
if "admin" not in st.session_state:
    st.session_state["admin"] = False

# URL 参数自动激活管理员
query_params = st.query_params
if query_params.get("mode") == "admin":
    st.session_state["admin"] = True

# ── 侧边栏：仅管理员密码入口 ─────────────────────────────
with st.sidebar:
    admin_pwd = st.text_input(
        "管理员密码",
        type="password",
        placeholder="输入密码解锁后台",
        label_visibility="collapsed",
    )
    if admin_pwd:
        ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "mcd123")
        if admin_pwd == ADMIN_PASSWORD:
            st.session_state["admin"] = True
            st.success("✅ 管理员模式已激活")
        else:
            st.error("❌ 密码错误")

# ── 学生端 ────────────────────────────────────────────────
st.title("🍔 麦当劳早餐配送提交")
st.write("上传订单截图 + 选择地址 = 提交成功，配单员直接看图打包。")

st.subheader("📌 步骤一：上传订单截图")
uploaded_file = st.file_uploader(
    "上传麦当劳订单截图",
    type=["png", "jpg", "jpeg"],
    label_visibility="collapsed",
)
if uploaded_file:
    st.image(uploaded_file, use_container_width=True)
else:
    st.info("📷 点击上方按钮从相册选择截图")

st.subheader("📌 步骤二：选择配送地址")

# ✅ 修复：两级联动下拉，不会互相覆盖
col_area, col_bldg = st.columns([1, 2])
with col_area:
    sel_area = st.selectbox("区域", list(AREAS.keys()), index=0, label_visibility="collapsed")
with col_bldg:
    sel_bldg = st.selectbox(
        "楼栋", AREAS[sel_area], index=0, label_visibility="collapsed"
    )

final_address = f"{sel_area.split()[1]} · {sel_bldg}"
st.success(f"🎯 当前地址：**{final_address}**")

# 提交按钮
if st.button("📤 提交订单", type="primary", use_container_width=True):
    if not uploaded_file:
        st.error("❌ 请先上传订单截图！")
    else:
        with st.spinner("正在提交..."):
            try:
                img_b64 = base64.b64encode(uploaded_file.getvalue()).decode("utf-8")
                conn = get_conn()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO mcd_orders (address, image_base64) VALUES (%s, %s);",
                            (final_address, img_b64),
                        )
                        conn.commit()
                    conn.close()
                    st.success(f"✅ 提交成功！已绑定至：{final_address} 🎉")
            except Exception as e:
                st.error(f"❌ 提交失败: {e}")

# ── 管理员后台 ────────────────────────────────────────────
if st.session_state["admin"]:
    st.divider()
    st.subheader("📊 管理员 · 今日配单看板")
    st.caption(
        "💡 下次直接访问 `https://mcd-breakfast-app.streamlit.app/?mode=admin` 自动进入"
    )

    conn = get_conn()
    orders = []
    if conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT address, image_base64, created_at FROM mcd_orders ORDER BY address, id;"
            )
            for row in cur.fetchall():
                orders.append(
                    {
                        "address": row[0],
                        "image_base64": row[1],
                        "created_at": row[2].strftime("%H:%M") if row[2] else "",
                    }
                )
        conn.close()

    if not orders:
        st.info("暂无订单数据。")
    else:
        st.markdown(f"**共 {len(orders)} 个订单**")

        # ── 数据总表 ──
        df = pd.DataFrame(orders)
        df.rename(
            columns={
                "address": "配送地址",
                "created_at": "提交时间",
            },
            inplace=True,
        )
        st.dataframe(df[["配送地址", "提交时间"]], use_container_width=True, hide_index=True)

        # ── 地址图片墙 ──
        st.markdown("---")
        st.markdown("**🖼️ 按地址配单看板**")
        for addr, group in groupby(orders, key=lambda r: r["address"]):
            glist = list(group)
            with st.expander(f"📍 {addr}（共 {len(glist)} 单）", expanded=False):
                for i in range(0, len(glist), 2):
                    row = glist[i : i + 2]
                    cols = st.columns(len(row))
                    for col, item in zip(cols, row):
                        with col:
                            if item.get("image_base64"):
                                st.image(
                                    BytesIO(base64.b64decode(item["image_base64"])),
                                    use_container_width=True,
                                )
                            st.caption(f"🕐 {item['created_at']}")

        # ── Excel 导出 ──
        st.markdown("---")
        col_a, col_b, _ = st.columns([1, 1, 4])
        with col_a:
            df_out = pd.DataFrame(
                [{"配送地址": o["address"], "提交时间": o["created_at"]} for o in orders]
            )
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df_out.to_excel(writer, index=False, sheet_name="配送统计")
            buffer.seek(0)
            st.download_button(
                "📥 导出 Excel",
                data=buffer,
                file_name="麦当劳早餐配送统计.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with col_b:
            if st.button("🗑️ 清空全部数据", type="secondary", use_container_width=True):
                conn2 = get_conn()
                if conn2:
                    with conn2.cursor() as cur:
                        cur.execute("TRUNCATE TABLE mcd_orders;")
                        conn2.commit()
                    conn2.close()
                    st.success("已清空全部数据")
                    st.rerun()
