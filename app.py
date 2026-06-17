import streamlit as st
import pandas as pd
import json
import os
import io
import requests
import shutil
import re
from datetime import datetime, timedelta
from base64 import b64decode
import uuid
import time

# محاولة استيراد PyGithub (لرفع التعديلات)
try:
    from github import Github
    GITHUB_AVAILABLE = True
except Exception:
    GITHUB_AVAILABLE = False

# ===============================
# ⚙ إعدادات التطبيق
# ===============================
APP_CONFIG = {
    "APP_TITLE": "CMMS - سيرفيس تحضيرات بيل يارن 11",
    "APP_ICON": "🏭",
    "REPO_NAME": "mahmedabdallh123/servise-card",
    "BRANCH": "main",
    "FILE_PATH": "l4.xlsx",
    "LOCAL_FILE": "l4.xlsx",
    "MAX_ACTIVE_USERS": 2,
    "SESSION_DURATION_MINUTES": 15,
    "SHOW_TECH_SUPPORT_TO_ALL": False,
    "CUSTOM_TABS": ["📊 فحص السيرفيس", "🛠 تعديل وإدارة البيانات", "🛠 الصيانة الوقائية"],
    "IMAGES_FOLDER": "event_images",
    "ALLOWED_IMAGE_TYPES": ["jpg", "jpeg", "png", "gif", "bmp"],
    "MAX_IMAGE_SIZE_MB": 5
}

# ===============================
# 🗂 إعدادات الملفات
# ===============================
USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]
IMAGES_FOLDER = APP_CONFIG["IMAGES_FOLDER"]
GITHUB_EXCEL_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['FILE_PATH']}"

# ===============================
# 🧩 دوال مساعدة للصور
# ===============================
def setup_images_folder():
    if not os.path.exists(IMAGES_FOLDER):
        os.makedirs(IMAGES_FOLDER)
        with open(os.path.join(IMAGES_FOLDER, ".gitkeep"), "w") as f:
            pass

def get_image_url(image_filename):
    if not image_filename:
        return None
    file_path = os.path.join(IMAGES_FOLDER, image_filename)
    if os.path.exists(file_path):
        return file_path
    return None

def display_images(image_filenames, caption="الصور المرفقة"):
    if not image_filenames:
        return
    st.markdown(f"**{caption}:**")
    images = image_filenames.split(',') if isinstance(image_filenames, str) else image_filenames
    for img in images:
        img = img.strip()
        if img:
            path = get_image_url(img)
            if path and os.path.exists(path):
                try:
                    st.image(path, caption=img, use_column_width=True)
                except:
                    st.write(f"📷 {img}")
            else:
                st.write(f"📷 {img} (غير موجود)")

# ===============================
# 🧩 دوال المستخدمين والجلسات
# ===============================
def load_users():
    if not os.path.exists(USERS_FILE):
        default_users = {
            "admin": {
                "password": "admin123",
                "role": "admin",
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"]
            }
        }
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_users, f, indent=4, ensure_ascii=False)
        return default_users
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"admin": {"password": "admin123", "role": "admin", "permissions": ["all"]}}

def save_users(users):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
        return True
    except:
        return False

def load_state():
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)

def cleanup_sessions(state):
    now = datetime.now()
    changed = False
    for user, info in list(state.items()):
        if info.get("active") and "login_time" in info:
            try:
                login_time = datetime.fromisoformat(info["login_time"])
                if now - login_time > SESSION_DURATION:
                    info["active"] = False
                    info.pop("login_time", None)
                    changed = True
            except:
                info["active"] = False
                changed = True
    if changed:
        save_state(state)
    return state

def remaining_time(state, username):
    if not username or username not in state:
        return None
    info = state.get(username)
    if not info or not info.get("active"):
        return None
    try:
        lt = datetime.fromisoformat(info["login_time"])
        remaining = SESSION_DURATION - (datetime.now() - lt)
        if remaining.total_seconds() <= 0:
            return None
        return remaining
    except:
        return None

def logout_action():
    state = load_state()
    username = st.session_state.get("username")
    if username and username in state:
        state[username]["active"] = False
        state[username].pop("login_time", None)
        save_state(state)
    for k in list(st.session_state.keys()):
        st.session_state.pop(k, None)
    st.rerun()

def login_ui():
    users = load_users()
    state = cleanup_sessions(load_state())
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.user_role = None
        st.session_state.user_permissions = []

    st.title(f"{APP_CONFIG['APP_ICON']} تسجيل الدخول - {APP_CONFIG['APP_TITLE']}")
    username_input = st.selectbox("👤 اختر المستخدم", list(users.keys()))
    password = st.text_input("🔑 كلمة المرور", type="password")
    active_users = [u for u, v in state.items() if v.get("active")]
    active_count = len(active_users)
    st.caption(f"🔒 المستخدمون النشطون: {active_count} / {MAX_ACTIVE_USERS}")

    if not st.session_state.logged_in:
        if st.button("تسجيل الدخول"):
            current_users = load_users()
            if username_input in current_users and current_users[username_input]["password"] == password:
                if username_input != "admin" and username_input in active_users:
                    st.warning("⚠ هذا المستخدم مسجل دخول بالفعل.")
                    return False
                elif active_count >= MAX_ACTIVE_USERS and username_input != "admin":
                    st.error("🚫 الحد الأقصى للمستخدمين المتصلين.")
                    return False
                state[username_input] = {"active": True, "login_time": datetime.now().isoformat()}
                save_state(state)
                st.session_state.logged_in = True
                st.session_state.username = username_input
                st.session_state.user_role = current_users[username_input].get("role", "viewer")
                st.session_state.user_permissions = current_users[username_input].get("permissions", ["view"])
                st.success(f"✅ تم تسجيل الدخول: {username_input}")
                st.rerun()
            else:
                st.error("❌ كلمة المرور غير صحيحة.")
        return False
    else:
        username = st.session_state.username
        st.success(f"✅ مسجل الدخول كـ: {username}")
        rem = remaining_time(state, username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.info(f"⏳ الوقت المتبقي: {mins:02d}:{secs:02d}")
        if st.button("🚪 تسجيل الخروج"):
            logout_action()
        return True

def get_user_permissions(user_role, user_permissions):
    if user_role == "admin":
        return {"can_view": True, "can_edit": True, "can_manage_users": False}
    elif user_role == "editor":
        return {"can_view": True, "can_edit": True, "can_manage_users": False}
    else:
        return {
            "can_view": "view" in user_permissions or "edit" in user_permissions or "all" in user_permissions,
            "can_edit": "edit" in user_permissions or "all" in user_permissions,
            "can_manage_users": False
        }

# ===============================
# 🧩 دوال التعامل مع الملفات
# ===============================
def fetch_from_github_requests():
    try:
        response = requests.get(GITHUB_EXCEL_URL, stream=True, timeout=15)
        response.raise_for_status()
        with open(APP_CONFIG["LOCAL_FILE"], "wb") as f:
            shutil.copyfileobj(response.raw, f)
        try:
            st.cache_data.clear()
        except:
            pass
        return True
    except Exception as e:
        st.error(f"⚠ فشل التحديث: {e}")
        return False

@st.cache_data(show_spinner=False)
def load_all_sheets():
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        return None
    try:
        sheets = pd.read_excel(APP_CONFIG["LOCAL_FILE"], sheet_name=None)
        if not sheets:
            return None
        for name, df in sheets.items():
            df.columns = df.columns.astype(str).str.strip()
        return sheets
    except Exception as e:
        return None

@st.cache_data(show_spinner=False)
def load_sheets_for_edit():
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        return None
    try:
        sheets = pd.read_excel(APP_CONFIG["LOCAL_FILE"], sheet_name=None, dtype=object)
        if not sheets:
            return None
        for name, df in sheets.items():
            df.columns = df.columns.astype(str).str.strip()
        return sheets
    except Exception:
        return None

def save_local_excel_and_push(sheets_dict, commit_message="Update"):
    try:
        with pd.ExcelWriter(APP_CONFIG["LOCAL_FILE"], engine="openpyxl") as writer:
            for name, sh in sheets_dict.items():
                try:
                    sh.to_excel(writer, sheet_name=name, index=False)
                except Exception:
                    sh.astype(object).to_excel(writer, sheet_name=name, index=False)
    except Exception as e:
        st.error(f"⚠ خطأ في الحفظ: {e}")
        return None
    try:
        st.cache_data.clear()
    except:
        pass
    token = st.secrets.get("github", {}).get("token", None)
    if not token or not GITHUB_AVAILABLE:
        return load_sheets_for_edit()
    try:
        g = Github(token)
        repo = g.get_repo(APP_CONFIG["REPO_NAME"])
        with open(APP_CONFIG["LOCAL_FILE"], "rb") as f:
            content = f.read()
        try:
            contents = repo.get_contents(APP_CONFIG["FILE_PATH"], ref=APP_CONFIG["BRANCH"])
            repo.update_file(path=APP_CONFIG["FILE_PATH"], message=commit_message, content=content, sha=contents.sha, branch=APP_CONFIG["BRANCH"])
        except:
            repo.create_file(path=APP_CONFIG["FILE_PATH"], message=commit_message, content=content, branch=APP_CONFIG["BRANCH"])
        st.success("✅ تم الرفع إلى GitHub")
        return load_sheets_for_edit()
    except Exception as e:
        st.error(f"❌ فشل الرفع: {e}")
        return None

def auto_save_to_github(sheets_dict, operation_description):
    username = st.session_state.get("username", "unknown")
    commit_message = f"{operation_description} by {username} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    result = save_local_excel_and_push(sheets_dict, commit_message)
    if result is not None:
        return result
    return sheets_dict

# ===============================
# 🧩 دوال المساعدة للنصوص
# ===============================
def normalize_name(s):
    if s is None:
        return ""
    s = str(s).replace("\n", "+")
    s = re.sub(r"[^0-9a-zA-Z\u0600-\u06FF\+\s_/.-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

def split_needed_services(needed_service_str):
    if not isinstance(needed_service_str, str) or needed_service_str.strip() == "":
        return []
    parts = re.split(r"\+|,|\n|;", needed_service_str)
    return [p.strip() for p in parts if p.strip() != ""]

def highlight_cell(val, col_name):
    color_map = {
        "Service Needed": "background-color: #fff3cd; color:#856404; font-weight:bold;",
        "Service Done": "background-color: #d4edda; color:#155724; font-weight:bold;",
        "Service Didn't Done": "background-color: #f8d7da; color:#721c24; font-weight:bold;",
        "Date": "background-color: #e7f1ff; color:#004085; font-weight:bold;",
        "Tones": "background-color: #e8f8f5; color:#0d5c4a; font-weight:bold;",
        "Event": "background-color: #e2f0d9; color:#2e6f32; font-weight:bold;",
        "Correction": "background-color: #fdebd0; color:#7d6608; font-weight:bold;",
        "Servised by": "background-color: #f0f0f0; color:#333; font-weight:bold;",
        "Card Number": "background-color: #ebdef0; color:#4a235a; font-weight:bold;",
        "Images": "background-color: #d6eaf8; color:#1b4f72; font-weight:bold;"
    }
    return color_map.get(col_name, "")

def style_table(row):
    return [highlight_cell(row[col], col) for col in row.index]

def get_servised_by_value(row):
    servised_columns = ["Servised by", "Serviced by", "Service by", "Serviced By", "Service By",
                        "خدم بواسطة", "تم الخدمة بواسطة", "فني الخدمة"]
    for col in servised_columns:
        if col in row.index:
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    for col in row.index:
        if any(k in normalize_name(col) for k in ["servisedby", "servicedby", "serviceby", "خدمبواسطة", "فني"]):
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    return "-"

def get_images_value(row):
    images_columns = ["Images", "images", "Pictures", "pictures", "Attachments", "attachments",
                      "صور", "الصور", "مرفقات", "المرفقات", "صور الحدث"]
    for col in images_columns:
        if col in row.index:
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    for col in row.index:
        if any(k in normalize_name(col) for k in ["images", "pictures", "attachments", "صور", "مرفقات"]):
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    return ""

# ===============================
# 📊 دالة show_service_statistics
# ===============================
def show_service_statistics(service_stats, result_df):
    """عرض الإحصائيات والنسب المئوية لفحص السيرفيس"""
    st.markdown("---")
    st.markdown("### 📊 الإحصائيات والنسب المئوية")
    
    if service_stats["total_needed_services"] == 0:
        st.info("ℹ️ لا توجد خدمات مطلوبة في النطاق المحدد.")
        return
    
    completion_rate = (service_stats["total_done_services"] / service_stats["total_needed_services"]) * 100 if service_stats["total_needed_services"] > 0 else 0
    completion_rate = max(0, min(100, completion_rate))
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📈 نسبة الإنجاز العامة", f"{completion_rate:.1f}%", f"{service_stats['total_done_services']}/{service_stats['total_needed_services']}")
    with col2:
        st.metric("🔢 عدد الخدمات المطلوبة", service_stats["total_needed_services"])
    with col3:
        st.metric("✅ الخدمات المنفذة", service_stats["total_done_services"])
    with col4:
        st.metric("⏳ الخدمات المتبقية", service_stats["total_needed_services"] - service_stats["total_done_services"])
    
    st.markdown("---")
    st.markdown("#### 📝 إحصائيات مفصلة لكل خدمة")
    stat_data = []
    all_services = set(service_stats["service_counts"].keys()).union(set(service_stats["service_done_counts"].keys()))
    for service in sorted(all_services):
        needed = service_stats["service_counts"].get(service, 0)
        done = service_stats["service_done_counts"].get(service, 0)
        if needed > 0:
            pct = (done / needed) * 100
        else:
            pct = 0
        stat_data.append({
            "الخدمة": service,
            "مطلوبة": needed,
            "منفذة": done,
            "متبقية": needed - done,
            "نسبة الإنجاز": f"{max(0,min(100,pct)):.1f}%"
        })
    if stat_data:
        st.dataframe(pd.DataFrame(stat_data), use_container_width=True)

# ===============================
# 🔍 دالة check_service_status
# ===============================
def check_service_status(card_num, current_tons, all_sheets):
    """فحص حالة السيرفيس من شيتات CardX الموجودة"""
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    if "ServicePlan" not in all_sheets:
        st.error("❌ الملف لا يحتوي على شيت ServicePlan.")
        return
    
    service_plan_df = all_sheets["ServicePlan"]
    
    # البحث عن شيت الماكينة (CardX أو CardX_Services)
    card_sheet_name = None
    for name in all_sheets.keys():
        if name == f"Card{card_num}" or name == f"Card{card_num}_Services":
            card_sheet_name = name
            break
    
    if card_sheet_name is None:
        st.warning(f"⚠ لا يوجد شيت للماكينة رقم {card_num}")
        return
    
    card_df = all_sheets[card_sheet_name].copy()
    
    # استخراج الصفوف التي تحتوي على Min_Tones و Max_Tones
    services_df = card_df[
        (card_df.get("Min_Tones", pd.NA).notna()) & 
        (card_df.get("Max_Tones", pd.NA).notna()) &
        (card_df.get("Min_Tones", "") != "") & 
        (card_df.get("Max_Tones", "") != "")
    ].copy()
    
    if services_df.empty:
        st.warning(f"⚠ لا توجد شرائح خدمة مسجلة للماكينة {card_num}")
        return

    st.subheader("⚙ نطاق العرض")
    view_option = st.radio(
        "اختر نطاق العرض:",
        ("الشريحة الحالية فقط", "كل الشرائح الأقل", "كل الشرائح الأعلى", "نطاق مخصص", "كل الشرائح"),
        horizontal=True,
        key=f"service_view_option_{card_num}"
    )

    min_range = st.session_state.get(f"service_min_range_{card_num}", max(0, current_tons - 500))
    max_range = st.session_state.get(f"service_max_range_{card_num}", current_tons + 500)
    if view_option == "نطاق مخصص":
        col1, col2 = st.columns(2)
        with col1:
            min_range = st.number_input("من (طن):", min_value=0, step=100, value=min_range, key=f"service_min_range_{card_num}")
        with col2:
            max_range = st.number_input("إلى (طن):", min_value=min_range, step=100, value=max_range, key=f"service_max_range_{card_num}")

    if view_option == "الشريحة الحالية فقط":
        selected_slices = service_plan_df[(service_plan_df["Min_Tones"] <= current_tons) & (service_plan_df["Max_Tones"] >= current_tons)]
    elif view_option == "كل الشرائح الأقل":
        selected_slices = service_plan_df[service_plan_df["Max_Tones"] <= current_tons]
    elif view_option == "كل الشرائح الأعلى":
        selected_slices = service_plan_df[service_plan_df["Min_Tones"] >= current_tons]
    elif view_option == "نطاق مخصص":
        selected_slices = service_plan_df[(service_plan_df["Min_Tones"] >= min_range) & (service_plan_df["Max_Tones"] <= max_range)]
    else:
        selected_slices = service_plan_df.copy()

    if selected_slices.empty:
        st.warning("⚠ لا توجد شرائح مطابقة حسب النطاق المحدد.")
        return

    all_results = []
    service_stats = {
        "service_counts": {},
        "service_done_counts": {},
        "total_needed_services": 0,
        "total_done_services": 0,
        "by_slice": {}
    }
    
    # أسماء الأعمدة التي تمثل الخدمات في شيت الماكينة
    service_columns = [col for col in services_df.columns if col not in 
                       ["card", "Min_Tones", "Max_Tones", "Tones", "Date", "Event", "Correction", "Servised by", "Serviced by", "Images", "card"]]
    
    for _, current_slice in selected_slices.iterrows():
        slice_min = current_slice["Min_Tones"]
        slice_max = current_slice["Max_Tones"]
        slice_key = f"{slice_min}-{slice_max}"
        
        needed_service_raw = current_slice.get("Service", "")
        needed_parts = split_needed_services(needed_service_raw)
        needed_norm = [normalize_name(p) for p in needed_parts]
        
        service_stats["by_slice"][slice_key] = {
            "needed": needed_parts,
            "done": [],
            "not_done": [],
            "total_needed": len(needed_parts),
            "total_done": 0
        }
        
        for service in needed_parts:
            service_stats["service_counts"][service] = service_stats["service_counts"].get(service, 0) + 1
        service_stats["total_needed_services"] += len(needed_parts)

        # البحث عن الصفوف في شيت الماكينة التي تطابق هذا النطاق
        mask = (services_df["Min_Tones"].fillna(0) <= slice_max) & (services_df["Max_Tones"].fillna(0) >= slice_min)
        matching_rows = services_df[mask]

        if not matching_rows.empty:
            for _, row in matching_rows.iterrows():
                done_services_set = set()
                
                for col in service_columns:
                    val = str(row.get(col, "")).strip()
                    if val and val.lower() not in ["nan", "none", "", "null", "0"]:
                        if val.lower() not in ["no", "false", "not done", "لم تتم", "x", "-"]:
                            done_services_set.add(col)
                            service_stats["service_done_counts"][col] = service_stats["service_done_counts"].get(col, 0) + 1
                            service_stats["total_done_services"] += 1

                current_date = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else "-"
                current_tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
                servised_by_value = get_servised_by_value(row)
                images_value = get_images_value(row)
                
                done_services = sorted(list(done_services_set))
                done_norm = [normalize_name(c) for c in done_services]
                
                service_stats["by_slice"][slice_key]["done"].extend(done_services)
                service_stats["by_slice"][slice_key]["total_done"] += len(done_services)
                
                not_done = []
                for needed_part, needed_norm_part in zip(needed_parts, needed_norm):
                    if needed_norm_part not in done_norm:
                        not_done.append(needed_part)
                
                service_stats["by_slice"][slice_key]["not_done"].extend(not_done)

                all_results.append({
                    "Card Number": card_num,
                    "Min_Tons": slice_min,
                    "Max_Tons": slice_max,
                    "Service Needed": " + ".join(needed_parts) if needed_parts else "-",
                    "Service Done": ", ".join(done_services) if done_services else "-",
                    "Service Didn't Done": ", ".join(not_done) if not_done else "-",
                    "Tones": current_tones,
                    "Servised by": servised_by_value,
                    "Date": current_date,
                    "Images": images_value if images_value else "-"
                })
        else:
            all_results.append({
                "Card Number": card_num,
                "Min_Tons": slice_min,
                "Max_Tons": slice_max,
                "Service Needed": " + ".join(needed_parts) if needed_parts else "-",
                "Service Done": "-",
                "Service Didn't Done": ", ".join(needed_parts) if needed_parts else "-",
                "Tones": "-",
                "Servised by": "-",
                "Date": "-",
                "Images": "-"
            })
            service_stats["by_slice"][slice_key]["not_done"] = needed_parts.copy()

    result_df = pd.DataFrame(all_results).dropna(how="all").reset_index(drop=True)

    st.markdown("### 📋 نتائج فحص السيرفيس")
    if not result_df.empty:
        st.dataframe(result_df.style.apply(style_table, axis=1), use_container_width=True)
        show_service_statistics(service_stats, result_df)
        if "Images" in result_df.columns:
            for idx, row in result_df.iterrows():
                images_value = row.get("Images", "")
                if images_value and images_value != "-":
                    display_images(images_value, f"📷 صور للحدث #{idx+1}")
        buffer = io.BytesIO()
        result_df.to_excel(buffer, index=False, engine="openpyxl")
        st.download_button(
            label="💾 حفظ النتائج كـ Excel",
            data=buffer.getvalue(),
            file_name=f"Service_Report_Card{card_num}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("ℹ️ لا توجد خدمات مسجلة لهذه الماكينة.")

# ===============================
# 🛠 دالة تعديل الشيت
# ===============================
def edit_sheet_with_save_button(sheets_edit):
    st.subheader("✏ تعديل البيانات")
    
    if "original_sheets" not in st.session_state:
        st.session_state.original_sheets = sheets_edit.copy()
    if "unsaved_changes" not in st.session_state:
        st.session_state.unsaved_changes = {}
    
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_sheet")
    if sheet_name not in st.session_state.unsaved_changes:
        st.session_state.unsaved_changes[sheet_name] = False
    
    df = sheets_edit[sheet_name].astype(str).copy()
    st.markdown(f"### 📋 تحرير شيت: {sheet_name}")
    st.info(f"عدد الصفوف: {len(df)} | عدد الأعمدة: {len(df.columns)}")
    
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, key=f"editor_{sheet_name}")
    has_changes = not edited_df.equals(df)
    
    if has_changes:
        st.session_state.unsaved_changes[sheet_name] = True
        st.warning("⚠ لديك تغييرات غير محفوظة!")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 حفظ التغييرات", key=f"save_{sheet_name}", type="primary"):
                sheets_edit[sheet_name] = edited_df.astype(object)
                new_sheets = auto_save_to_github(sheets_edit, f"تعديل في شيت {sheet_name}")
                if new_sheets is not None:
                    sheets_edit = new_sheets
                    st.session_state.unsaved_changes[sheet_name] = False
                    st.success("✅ تم الحفظ!")
                    st.rerun()
        with col2:
            if st.button("↩️ تراجع", key=f"undo_{sheet_name}"):
                if sheet_name in st.session_state.original_sheets:
                    sheets_edit[sheet_name] = st.session_state.original_sheets[sheet_name].astype(object)
                    st.session_state.unsaved_changes[sheet_name] = False
                    st.info("↩️ تم التراجع")
                    st.rerun()
    else:
        if st.session_state.unsaved_changes.get(sheet_name, False):
            st.session_state.unsaved_changes[sheet_name] = False
    return sheets_edit

# ===============================
# 🆕 دوال الصيانة الوقائية
# ===============================
def get_all_machine_numbers_from_sheets(sheets_edit):
    """استخراج أرقام الماكينات من أسماء الشيتات CardX"""
    machine_numbers = set()
    for sheet_name in sheets_edit.keys():
        if sheet_name.startswith("Card") and sheet_name not in ["Card", "Card_Services"]:
            try:
                num = int(re.search(r'\d+', sheet_name).group())
                machine_numbers.add(num)
            except:
                pass
    return sorted(machine_numbers)

def get_machine_card_sheet(sheets_edit, card_num):
    """الحصول على شيت الماكينة"""
    for name in sheets_edit.keys():
        if name == f"Card{card_num}" or name == f"Card{card_num}_Services":
            return name
    return None

def get_current_tons_from_card(sheets_edit, card_num):
    """استخراج آخر قيمة Tones من شيت الماكينة"""
    sheet_name = get_machine_card_sheet(sheets_edit, card_num)
    if not sheet_name:
        return 0.0
    df = sheets_edit[sheet_name]
    if "Tones" not in df.columns:
        return 0.0
    # البحث عن آخر قيمة غير فارغة في عمود Tones
    tones_values = df["Tones"].dropna()
    if tones_values.empty:
        return 0.0
    # محاولة تحويل آخر قيمة إلى رقم
    last_val = str(tones_values.iloc[-1]).strip()
    try:
        return float(last_val)
    except:
        return 0.0

def update_card_tones(sheets_edit, card_num, new_tons, performed_by=None):
    """تحديث قيمة Tones في شيت الماكينة وإضافة سجل"""
    sheet_name = get_machine_card_sheet(sheets_edit, card_num)
    if not sheet_name:
        return sheets_edit, "الماكينة غير موجودة"
    
    df = sheets_edit[sheet_name]
    # البحث عن الصف الذي يحتوي على Tones فارغ أو آخر صف
    # نضيف صف جديد مع Tones محدثة
    new_row = {col: "" for col in df.columns}
    new_row["Tones"] = new_tons
    new_row["Date"] = datetime.now().strftime("%d/%m/%Y")
    new_row["Event"] = f"تحديث الأطنان إلى {new_tons}"
    new_row["Serviced by"] = performed_by or st.session_state.get("username", "system")
    
    # إضافة الصف الجديد
    new_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    sheets_edit[sheet_name] = new_df
    sheets_edit = auto_save_to_github(sheets_edit, f"تحديث أطنان ماكينة {card_num} إلى {new_tons}")
    return sheets_edit, f"تم تحديث الأطنان إلى {new_tons}"

def get_machine_service_slices(sheets_edit, card_num):
    """استخراج شرائح الخدمة من شيت الماكينة"""
    sheet_name = get_machine_card_sheet(sheets_edit, card_num)
    if not sheet_name:
        return []
    df = sheets_edit[sheet_name]
    slices = []
    for _, row in df.iterrows():
        min_t = row.get("Min_Tones")
        max_t = row.get("Max_Tones")
        if pd.notna(min_t) and pd.notna(max_t) and str(min_t).strip() and str(max_t).strip():
            try:
                slices.append({
                    "min": float(min_t),
                    "max": float(max_t),
                    "row": row
                })
            except:
                pass
    return sorted(slices, key=lambda x: x["min"])

def get_current_slice_info(sheets_edit, card_num, current_tons):
    """الحصول على الشريحة الحالية والخدمات المطلوبة من ServicePlan"""
    if "ServicePlan" not in sheets_edit:
        return None, None, [], []
    service_plan = sheets_edit["ServicePlan"]
    for _, row in service_plan.iterrows():
        min_t = row.get("Min_Tones")
        max_t = row.get("Max_Tones")
        if pd.notna(min_t) and pd.notna(max_t):
            try:
                if float(min_t) <= current_tons <= float(max_t):
                    needed = split_needed_services(str(row.get("Service", "")))
                    return float(min_t), float(max_t), needed, []
            except:
                pass
    return None, None, [], []

def get_executed_services_from_card(sheets_edit, card_num, slice_min, slice_max):
    """استرجاع الخدمات المنفذة من شيت الماكينة لنطاق معين"""
    sheet_name = get_machine_card_sheet(sheets_edit, card_num)
    if not sheet_name:
        return []
    df = sheets_edit[sheet_name]
    executed = []
    service_cols = [col for col in df.columns if col not in 
                    ["card", "Min_Tones", "Max_Tones", "Tones", "Date", "Event", "Correction", "Servised by", "Serviced by", "Images"]]
    mask = (df["Min_Tones"].fillna(0) <= slice_max) & (df["Max_Tones"].fillna(0) >= slice_min)
    matching = df[mask]
    for _, row in matching.iterrows():
        for col in service_cols:
            val = str(row.get(col, "")).strip()
            if val and val.lower() not in ["nan", "none", "", "0", "no", "false", "not done", "لم تتم", "x", "-"]:
                executed.append(col)
    return list(set(executed))

def record_service_execution_in_card(sheets_edit, card_num, slice_min, slice_max, service_name, performed_by, notes=""):
    """تسجيل خدمة منفذة في شيت الماكينة"""
    sheet_name = get_machine_card_sheet(sheets_edit, card_num)
    if not sheet_name:
        return sheets_edit, "الماكينة غير موجودة"
    
    df = sheets_edit[sheet_name]
    # البحث عن صف موجود لهذا النطاق
    mask = (df["Min_Tones"].fillna(0) == slice_min) & (df["Max_Tones"].fillna(0) == slice_max)
    if mask.any():
        idx = df[mask].index[0]
        # تحديث العمود المناسب
        if service_name in df.columns:
            df.loc[idx, service_name] = "Done"
        else:
            # إضافة عمود جديد
            df[service_name] = ""
            df.loc[idx, service_name] = "Done"
        # تحديث تاريخ التنفيذ
        df.loc[idx, "Date"] = datetime.now().strftime("%d/%m/%Y")
        df.loc[idx, "Serviced by"] = performed_by or st.session_state.get("username", "system")
    else:
        # إضافة صف جديد
        new_row = {col: "" for col in df.columns}
        new_row["Min_Tones"] = slice_min
        new_row["Max_Tones"] = slice_max
        new_row["Tones"] = ""
        new_row["Date"] = datetime.now().strftime("%d/%m/%Y")
        new_row["Event"] = f"تنفيذ خدمة {service_name}"
        new_row["Correction"] = notes
        new_row["Serviced by"] = performed_by or st.session_state.get("username", "system")
        if service_name in new_row:
            new_row[service_name] = "Done"
        else:
            new_row[service_name] = "Done"
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    
    sheets_edit[sheet_name] = df
    sheets_edit = auto_save_to_github(sheets_edit, f"تسجيل خدمة {service_name} للماكينة {card_num}")
    return sheets_edit, f"تم تسجيل تنفيذ الخدمة {service_name}"

def preventive_maintenance_tab(sheets_edit):
    """تبويب الصيانة الوقائية"""
    st.header("🛠 الصيانة الوقائية - العداد التصاعدي والإشعارات")
    st.info("هنا يمكنك تتبع الأطنان الحالية لكل ماكينة وتسجيل الخدمات المطلوبة.")
    
    if sheets_edit is None:
        st.warning("لا توجد بيانات. قم بتحديث الملف من GitHub أولاً.")
        return sheets_edit
    
    machine_numbers = get_all_machine_numbers_from_sheets(sheets_edit)
    if not machine_numbers:
        st.warning("⚠ لم يتم العثور على أي ماكينة. تأكد من وجود شيتات CardX في ملف Excel.")
        return sheets_edit
    
    selected_card = st.selectbox("🔢 اختر رقم الماكينة:", machine_numbers, key="pm_card_select")
    
    # الحصول على الأطنان الحالية
    current_tons = get_current_tons_from_card(sheets_edit, selected_card)
    
    # عرض المعلومات الحالية
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📊 الأطنان الحالية", f"{current_tons:.1f} طن")
    with col2:
        st.metric("🆔 رقم الماكينة", selected_card)
    
    # تحديث الأطنان
    st.subheader("🔄 تحديث الأطنان")
    update_method = st.radio("طريقة التحديث:", ["إدخال يدوي", "إضافة كمية محددة"], horizontal=True, key="update_method_pm")
    
    if update_method == "إدخال يدوي":
        new_manual_tons = st.number_input("أدخل الأطنان الحالية:", min_value=0.0, value=float(current_tons), step=100.0, format="%.2f", key="manual_tons_pm")
        if st.button("💾 تحديث يدوي", key="manual_update_btn_pm"):
            if new_manual_tons != current_tons:
                sheets_edit, msg = update_card_tones(sheets_edit, selected_card, new_manual_tons)
                st.success(f"✅ {msg}")
                st.rerun()
            else:
                st.info("لم يتم تغيير القيمة.")
    else:
        additional_tons = st.number_input("كمية إضافية (طن):", min_value=0.0, step=10.0, format="%.2f", key="add_tons_pm")
        if st.button("➕ إضافة كمية", key="add_tons_btn_pm"):
            new_tons = current_tons + additional_tons
            sheets_edit, msg = update_card_tones(sheets_edit, selected_card, new_tons)
            st.success(f"✅ {msg}")
            st.rerun()
    
    # عرض النطاق الحالي والخدمات
    st.subheader("📌 النطاق الحالي والخدمات المطلوبة")
    slice_min, slice_max, required_services, _ = get_current_slice_info(sheets_edit, selected_card, current_tons)
    
    if slice_min is not None:
        st.info(f"**النطاق الحالي:** {slice_min} - {slice_max} طن")
        if required_services:
            executed = get_executed_services_from_card(sheets_edit, selected_card, slice_min, slice_max)
            st.markdown("**📋 الخدمات المطلوبة في هذا النطاق:**")
            for svc in required_services:
                if svc in executed:
                    st.success(f"✅ {svc} (تم تنفيذه)")
                else:
                    st.warning(f"⚠️ {svc} (لم ينفذ بعد)")
        else:
            st.success("✅ لا توجد خدمات مطلوبة في هذا النطاق.")
    else:
        st.warning("⚠ لم يتم العثور على نطاق يتطابق مع الأطنان الحالية.")
    
    # تسجيل خدمة جديدة
    st.subheader("📝 تسجيل خدمة منفذة")
    pending_services = []
    if slice_min is not None and required_services:
        executed = get_executed_services_from_card(sheets_edit, selected_card, slice_min, slice_max)
        for svc in required_services:
            if svc not in executed:
                pending_services.append(svc)
    
    if pending_services:
        service_to_record = st.selectbox("اختر الخدمة التي تم تنفيذها:", pending_services, key="record_service_select_pm")
        performed_by = st.text_input("اسم الفني المنفذ:", value=st.session_state.get("username", ""), key="record_performed_by_pm")
        notes = st.text_area("ملاحظات (اختياري):", key="record_notes_pm")
        if st.button("✅ تسجيل تنفيذ الخدمة", key="record_service_btn_pm"):
            if not performed_by:
                st.error("❌ الرجاء إدخال اسم الفني المنفذ.")
            else:
                sheets_edit, msg = record_service_execution_in_card(sheets_edit, selected_card, slice_min, slice_max, service_to_record, performed_by, notes)
                st.success(f"✅ {msg}")
                st.rerun()
    else:
        st.info("ℹ️ لا توجد خدمات معلقة في النطاق الحالي.")
    
    # عرض شرائح الخدمات
    st.subheader("📊 شرائح الخدمات المسجلة")
    slices = get_machine_service_slices(sheets_edit, selected_card)
    if slices:
        slice_data = []
        for s in slices:
            executed = get_executed_services_from_card(sheets_edit, selected_card, s["min"], s["max"])
            required = []
            if "ServicePlan" in sheets_edit:
                sp = sheets_edit["ServicePlan"]
                for _, row in sp.iterrows():
                    if pd.notna(row.get("Min_Tones")) and pd.notna(row.get("Max_Tones")):
                        try:
                            if float(row["Min_Tones"]) == s["min"] and float(row["Max_Tones"]) == s["max"]:
                                required = split_needed_services(str(row.get("Service", "")))
                                break
                        except:
                            pass
            slice_data.append({
                "النطاق": f"{s['min']} - {s['max']}",
                "الخدمات المطلوبة": ", ".join(required) if required else "-",
                "الخدمات المنفذة": ", ".join(executed) if executed else "-",
                "المتبقية": ", ".join([r for r in required if r not in executed]) if required else "-"
            })
        st.dataframe(pd.DataFrame(slice_data), use_container_width=True)
    else:
        st.info("لا توجد شرائح خدمة مسجلة لهذه الماكينة.")
    
    return sheets_edit

# ===============================
# 🖥 الواجهة الرئيسية
# ===============================
st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")
setup_images_folder()

with st.sidebar:
    st.header("👤 الجلسة")
    if not st.session_state.get("logged_in"):
        if not login_ui():
            st.stop()
    else:
        state = cleanup_sessions(load_state())
        username = st.session_state.username
        user_role = st.session_state.user_role
        rem = remaining_time(state, username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.success(f"👋 {username} | الدور: {user_role} | ⏳ {mins:02d}:{secs:02d}")
        else:
            logout_action()

    st.markdown("---")
    st.write("🔧 أدوات:")
    if st.button("🔄 تحديث الملف من GitHub", key="refresh_github"):
        if fetch_from_github_requests():
            st.rerun()
    if st.button("🗑 مسح الكاش", key="clear_cache"):
        try:
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"❌ خطأ: {e}")
    if st.button("🚪 تسجيل الخروج", key="logout_btn"):
        logout_action()

# تحميل البيانات
all_sheets = load_all_sheets()
sheets_edit = load_sheets_for_edit()

st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")

username = st.session_state.get("username")
user_role = st.session_state.get("user_role", "viewer")
user_permissions = st.session_state.get("user_permissions", ["view"])
permissions = get_user_permissions(user_role, user_permissions)

# بناء التبويبات
tabs_list = ["📊 فحص السيرفيس"]
if permissions["can_edit"]:
    tabs_list.append("🛠 تعديل وإدارة البيانات")
    tabs_list.append("🛠 الصيانة الوقائية")

tabs = st.tabs(tabs_list)

# تبويب فحص السيرفيس
with tabs[0]:
    st.header("📊 فحص السيرفيس")
    if all_sheets is None:
        st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            card_num = st.number_input("رقم الماكينة:", min_value=1, step=1, key="card_num_service")
        with col2:
            current_tons = st.number_input("عدد الأطنان الحالية:", min_value=0, step=100, key="current_tons_service")
        if st.button("عرض حالة السيرفيس", key="show_service"):
            st.session_state["show_service_results"] = True
        if st.session_state.get("show_service_results", False):
            check_service_status(card_num, current_tons, all_sheets)

# تبويب تعديل البيانات
if permissions["can_edit"] and len(tabs) > 1:
    with tabs[1]:
        st.header("🛠 تعديل وإدارة البيانات")
        if sheets_edit is None:
            st.warning("❗ الملف المحلي غير موجود.")
        else:
            tab1, tab2, tab3 = st.tabs(["عرض وتعديل شيت", "إضافة صف جديد", "إضافة عمود جديد"])
            with tab1:
                sheets_edit = edit_sheet_with_save_button(sheets_edit)
            with tab2:
                st.subheader("➕ إضافة صف جديد")
                sheet_name_add = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="add_sheet")
                df_add = sheets_edit[sheet_name_add].astype(str).reset_index(drop=True)
                st.markdown("أدخل بيانات الصف الجديد:")
                new_data = {}
                cols = st.columns(3)
                for i, col in enumerate(df_add.columns):
                    with cols[i % 3]:
                        new_data[col] = st.text_input(f"{col}", key=f"add_{sheet_name_add}_{col}")
                if st.button("💾 إضافة الصف", key=f"add_row_{sheet_name_add}", type="primary"):
                    new_row_df = pd.DataFrame([new_data]).astype(str)
                    df_new = pd.concat([df_add, new_row_df], ignore_index=True)
                    sheets_edit[sheet_name_add] = df_new.astype(object)
                    new_sheets = auto_save_to_github(sheets_edit, f"إضافة صف في {sheet_name_add}")
                    if new_sheets is not None:
                        sheets_edit = new_sheets
                        st.success("✅ تم الإضافة")
                        st.rerun()
            with tab3:
                st.subheader("🆕 إضافة عمود جديد")
                sheet_name_col = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="add_col_sheet")
                df_col = sheets_edit[sheet_name_col].astype(str)
                new_col_name = st.text_input("اسم العمود:", key="new_col_name")
                default_value = st.text_input("القيمة الافتراضية:", "", key="default_value")
                if st.button("💾 إضافة العمود", key=f"add_col_{sheet_name_col}", type="primary"):
                    if new_col_name:
                        df_col[new_col_name] = default_value
                        sheets_edit[sheet_name_col] = df_col.astype(object)
                        new_sheets = auto_save_to_github(sheets_edit, f"إضافة عمود {new_col_name}")
                        if new_sheets is not None:
                            sheets_edit = new_sheets
                            st.success("✅ تم الإضافة")
                            st.rerun()
                    else:
                        st.warning("⚠ الرجاء إدخال اسم العمود.")

# تبويب الصيانة الوقائية
if permissions["can_edit"] and len(tabs) > 2:
    with tabs[2]:
        sheets_edit = preventive_maintenance_tab(sheets_edit)
