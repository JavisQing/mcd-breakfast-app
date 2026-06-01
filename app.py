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

# ── 彻底隐藏所有 Streamlit 品牌痕迹 ──────────────────────
hide_streamlit_style = """
    <style>
        /* 隐藏顶部红色装饰线 */
        div[data-testid="stDecoration"] {display: none !important;}

        /* 隐藏顶部标题栏（含 Fork 按钮、菜单、头像） */
        header[data-testid="stHeader"] {display: none !important;}

        /* 隐藏底部 "Made with Streamlit" */
        footer {display: none !important;}

        /* 隐藏右上角三点菜单 */
        #MainMenu {visibility: hidden !important;}

        /* 隐藏侧边栏切换按钮 */
        button[kind="icon"][data-testid="collapsedControl"] {display: none !important;}

        /* 隐藏状态指示器（Running…） */
        div[data-testid="stStatusWidget"] {display: none !important;}

        /* 隐藏 Toolbar（包含 Fork 按钮） */
        div[data-testid="stToolbar"] {display: none !important;}

        /* 隐藏 Streamlit 的 App 头像 */
        a[href*="share.streamlit.io"], a[href*="streamlit.io/cloud"] {display: none !important;}
        img[alt="App Creator Avatar"] {display: none !important;}

        /* 隐藏侧边栏 */
        section[data-testid="stSidebar"] {display: none !important;}

        /* 如果有 Streamlit 社区 logo 也隐藏 */
        .stApp > div:first-child > div:last-child > a {display: none !important;}

        /* 移除 app 的默认最大宽度限制并增加内边距 */
        .main > div {
            padding-top: 0.5rem !important;
            padding-bottom: 0 !important;
        }

        /* 自定义整体背景和字体 */
        .stApp {
            background: #f8f5f0;
        }
        h1, h2, h3 {
            color: #2d2d2d !important;
        }
        .block-container {
            background: transparent !important;
        }

        /* 卡片样式 */
        .card {
            background: white;
            border-radius: 16px;
            padding: 2rem 1.8rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        }

        /* 上传区域美化 */
        div[data-testid="stFileUploader"] {
            background: white;
            border-radius: 16px;
            padding: 1.5rem;
            border: 2px dashed #ddd;
        }
        div[data-testid="stFileUploader"]:hover {
            border-color: #ff6b35;
        }

        /* 成功/信息提示圆角 */
        div[data-testid="stAlert"] {
            border-radius: 12px !important;
        }

        /* 展开面板美化 */
        div[data-testid="stExpander"] {
            background: white;
            border-radius: 12px !important;
            border: 1px solid #eee !important;
            margin-bottom: 0.5rem !important;
        }
        div[data-testid="stExpander"] summary {
            font-weight: 600;
            padding: 0.8rem 1rem !important;
        }

        /* 按钮圆角 */
        button[kind="primary"] {
            border-radius: 12px !important;
            font-weight: 600 !important;
        }

        /* 下拉框圆角 */
        div[data-baseweb="select"] > div {
            border-radius: 10px !important;
        }

        /* 分割线美化 */
        hr {
            margin: 2rem 0 !important;
            border-color: #e0ddd8 !important;
        }
    </style>
    <script>
        // 完全去掉标题中的 "Streamlit" 字样
        const observer = new MutationObserver(() => {
            if (document.title.includes("Streamlit")) {
                document.title = "麦当劳早餐配送";
            }
        });
        observer.observe(document.querySelector('head'), { childList: true, subtree: true });
        document.title = "麦当劳早餐配送";
    </script>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

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

# ── 学生端 ────────────────────────────────────────────────
st.markdown('<div class="card">', unsafe_allow_html=True)
st.title("🍔 麦当劳早餐配送")
st.markdown("上传订单截图 + 选择地址即可提交，配单员直接看图打包。")
st.markdown('</div>', unsafe_allow_html=True)

# 步骤一
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### 📌 第一步：上传订单截图")
uploaded_file = st.file_uploader(
    "选择麦当劳订单截图",
    type=["png", "jpg", "jpeg"],
    label_visibility="collapsed",
)
if uploaded_file:
    st.image(uploaded_file, use_container_width=True)
else:
    st.info("📷 点击上方按钮从相册选择截图")
st.markdown('</div>', unsafe_allow_html=True)

# 步骤二
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown("### 📌 第二步：选择配送地址")

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
st.markdown('</div>', unsafe_allow_html=True)

# ── 管理员入口 ──────────────────────────────────────────
st.markdown("---")
with st.expander("🔐 管理员通道"):
    admin_pwd = st.text_input(
        "管理员密码",
        type="password",
        placeholder="输入密码进入后台",
        label_visibility="collapsed",
    )
    ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD")
    if not ADMIN_PASSWORD:
        st.error("⚠️ 服务器未配置管理员密码，请联系开发者。")
    elif admin_pwd:
        if admin_pwd == ADMIN_PASSWORD:
            st.session_state["admin"] = True
            st.success("✅ 管理员模式已激活")
        else:
            st.error("❌ 密码错误")

if st.session_state["admin"] and ADMIN_PASSWORD:
    st.divider()
    st.subheader("📊 管理员 · 今日配单看板")

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

        # 数据总表
        df = pd.DataFrame(orders)
        df.rename(
            columns={
                "address": "配送地址",
                "created_at": "提交时间",
            },
            inplace=True,
        )
        st.dataframe(df[["配送地址", "提交时间"]], use_container_width=True, hide_index=True)

        # 地址图片墙
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

        # Excel 导出 + 清空
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
