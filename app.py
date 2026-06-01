import streamlit as st
import psycopg2
import base64

# 页面配置
st.set_page_config(page_title="麦当劳早餐配送", page_icon="🍔", layout="centered")

# 物理隐藏 Streamlit 所有官方品牌标记
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}      /* 隐藏右上角三点菜单 */
            footer {visibility: hidden;}         /* 隐藏底部 Made with Streamlit 水印 */
            header {visibility: hidden;}         /* 隐藏顶部空白带 */
            div[data-testid="stToolbar"] {visibility: hidden;} /* 隐藏右上角其他工具栏 */
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# 初始化数据库连接
def init_connection():
    try:
        return psycopg2.connect(st.secrets["DATABASE_URL"])
    except Exception as e:
        st.error(f"数据库连接失败，请检查配置。错误: {e}")
        return None

# 创建数据表
def init_db():
    conn = init_connection()
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

# 预设固定的校园地址列表
ADDRESS_DATA = {
    "🏫 教学楼区": [
        "1 号教学楼（一教）", "2 号教学楼（二教）", "3 号教学楼（三教）", 
        "4 号教学楼（法学院）", "5 号教学楼（五教）", "6 号教学楼（六教）", 
        "7 号教学楼（七教）", "8 号教学楼（实验楼）", "9 号教学楼（九教）", 
        "10 号教学楼（十教）", "11 号教学楼（十一教）", "12 号教学楼（十二教）", 
        "13 号教学楼（十三教）", "14 号教学楼（十四教）", "15 号教学楼（十五教）", 
        "16 号教学楼（建筑学院）", "经管大楼", "港航中心", "电苑楼", "图书馆A/B馆"
    ],
    "🍏 西苑宿舍区": [f"西苑 {i} 栋" for i in range(1, 12)],
    "🍓 东苑宿舍区": [f"东苑 {i} 栋" for i in range(1, 16)] + ["外教楼"],
    "🍊 南苑宿舍区": [f"南苑 {i} 栋" for i in range(1, 9)]
}

# 检查是否开启管理员入口
query_params = st.query_params
is_admin_mode = query_params.get("mode") == "admin"

# 如果不是管理员访问，则隐藏左侧边栏
if not is_admin_mode:
    st.markdown("<style>ul[data-testid='sidebar-nav-items'] {display: none;}</style>", unsafe_allow_html=True)
    st.markdown("<style>[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)

# --- 学生端主界面 ---
st.title("🍔 麦当劳早餐配送提交")
st.write("请上传您的麦当劳预约成功订单截图，并选择您的配送地点。")

st.subheader("📌 步骤一：上传订单截图")
uploaded_file = st.file_uploader("点击下方按钮选择手机相册中的麦当劳截图", type=["png", "jpg", "jpeg"])

if uploaded_file:
    st.image(uploaded_file, caption="已上传截图预览", width=300)

st.subheader("📌 步骤二：选择配送地址")
st.info("💡 点击下方你想送达的大区域大标题（点一次展开，再点一次整体隐藏）。")

selected_address = None

# 核心修改点：把“请选择具体地址”塞进 with 内部，跟下拉框一起由折叠面板控制！
for area, addresses in ADDRESS_DATA.items():
    # 默认全部折叠收起
    with st.expander(f"✨ 点击展开/收起：{area}", expanded=False):
        # 这一行由于缩进了，它现在完全属于 expander 的一部分，点击大标题它会跟着一起消失！
        st.write(f"📝 **请在下方勾选您的具体地址（{area}）**")
        res = st.selectbox(
            "选择楼栋", 
            addresses, 
            index=None,
            placeholder="--- 请点击此处选择具体楼栋 ---",
            label_visibility="collapsed",  # 隐藏原生的烦人标签，使用我们上面自定义的粗体字
            key=f"select_{area}"
        )
        if res:
            selected_address = res

# 实时显示学生当前锁定的目标地址
if selected_address:
    st.success(f"🎯 当前已锁定目标配送地址：**{selected_address}**")

# 提交按钮
st.write("")
if st.button("🚀 确认提交订单", type="primary", use_container_width=True):
    if not uploaded_file:
        st.error("❌ 请先上传您的麦当劳订单截图！")
    elif not selected_address:
        st.error("❌ 请先展开上方区域并选择具体的配送楼栋！")
    else:
        with st.spinner("正在提交中，请稍候..."):
            try:
                # 图片转 Base64 文本
                bytes_data = uploaded_file.getvalue()
                base64_str = base64.b64encode(bytes_data).decode("utf-8")
                
                # 存入数据库
                conn = init_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO mcd_orders (address, image_base64) VALUES (%s, %s);",
                            (selected_address, base64_str)
                        )
                        conn.commit()
                    conn.close()
                    st.success(f"🎉 提交成功！已成功绑定至：{selected_address}。感谢配合！")
            except Exception as e:
                st.error(f"提交失败，请联系管理员。错误: {e}")

# --- 管理员后台入口 ---
st.write("---")
admin_password_input = ""
if not is_admin_mode:
    with st.expander("🔐 管理员通道"):
        admin_password_input = st.text_input("请输入管理密码解锁后台", type="password")

# 验证密码或者暗号
if is_admin_mode or (admin_password_input == st.secrets.get("ADMIN_PASSWORD", "mcd123")):
    st.subheader("📊 麦当劳今日配送视觉看板（配单专用）")
    
    # 从数据库调取数据
    conn = init_connection()
    orders = []
    if conn:
        with conn.cursor() as cur:
            cur.execute("SELECT address, image_base64, created_at FROM mcd_orders ORDER BY created_at DESC;")
            orders = cur.fetchall()
        conn.close()
    
    if not orders:
        st.info("📭 今日暂无同学提交订单数据。")
    else:
        # 按地址分类归集
        grouped_orders = {}
        for addr, img_b64, t in orders:
            if addr not in grouped_orders:
                grouped_orders[addr] = []
            grouped_orders[addr].append(img_b64)
        
        st.write(f"📈 今日总计收到订单：`{len(orders)}` 单，分布在 `{len(grouped_orders)}` 个地址。")
        
        # 循环渲染图片墙
        for addr, imgs in grouped_orders.items():
            with st.expander(f"📍 {addr} （共 {len(imgs)} 单）", expanded=False):
                cols = st.columns(2)
                for idx, img_b64 in enumerate(imgs):
                    with cols[idx % 2]:
                        try:
                            img_bytes = base64.b64decode(img_b64)
                            st.image(img_bytes, use_column_width=True, caption=f"订单图片 #{idx+1}")
                        except Exception:
                            st.error("图片数据解析失败")
                            
        # 清空按钮
        st.write("---")
        if st.button("🚨 清空今日所有订单数据", type="secondary"):
            conn = init_connection()
            if conn:
                with conn.cursor() as cur:
                    cur.execute("TRUNCATE TABLE mcd_orders;")
                    conn.commit()
                conn.close()
                st.warning("💥 今日所有订单数据已全部清空！")
                st.rerun()
