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

# محاولة استيراد PyGithub
try:
    from github import Github
    GITHUB_AVAILABLE = True
except Exception:
    GITHUB_AVAILABLE = False

# ===============================
# ⚙ إعدادات التطبيق
# ===============================
APP_CONFIG = {
    "APP_TITLE": "CMMS - سيرفيس تحضيرات بيل يارن",
    "APP_ICON": "🏭",
    "REPO_NAME": "mahmedabdallh123/servise-card",
    "BRANCH": "main",
    "FILE_PATH": "l4.xlsx",
    "LOCAL_FILE": "l4.xlsx",
    "MAX_ACTIVE_USERS": 2,
    "SESSION_DURATION_MINUTES": 15,
    "CUSTOM_TABS": ["📊 فحص السيرفيس", "🛠 تعديل وإدارة البيانات"],
    "IMAGES_FOLDER": "event_images",
    "ALLOWED_IMAGE_TYPES": ["jpg", "jpeg", "png", "gif", "bmp"],
    "MAX_IMAGE_SIZE_MB": 5,
}

USERS_FILE = "users.json"
STATE_FILE = "state.json"
NOTIFICATIONS_FILE = "notifications.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]
IMAGES_FOLDER = APP_CONFIG["IMAGES_FOLDER"]
GITHUB_EXCEL_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['FILE_PATH']}"

# -------------------------------
# دوال الإشعارات (كما هي)
# -------------------------------
def load_notifications():
    if not os.path.exists(NOTIFICATIONS_FILE):
        with open(NOTIFICATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4, ensure_ascii=False)
        return []
    try:
        with open(NOTIFICATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_notifications(notifications):
    try:
        with open(NOTIFICATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(notifications, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False

def add_notification(username, action, details, target_sheet=None, target_row=None):
    notifications = load_notifications()
    new_notification = {
        "id": str(uuid.uuid4()),
        "username": username,
        "action": action,
        "details": details,
        "target_sheet": target_sheet,
        "target_row": target_row,
        "timestamp": datetime.now().isoformat(),
        "read_by_admin": False
    }
    notifications.insert(0, new_notification)
    save_notifications(notifications)
    return new_notification

# -------------------------------
# دوال مساعدة للصور
# -------------------------------
def setup_images_folder():
    if not os.path.exists(IMAGES_FOLDER):
        os.makedirs(IMAGES_FOLDER)
        with open(os.path.join(IMAGES_FOLDER, ".gitkeep"), "w") as f:
            pass

def save_uploaded_images(uploaded_files):
    if not uploaded_files:
        return []
    saved_files = []
    for uploaded_file in uploaded_files:
        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension not in APP_CONFIG["ALLOWED_IMAGE_TYPES"]:
            st.warning(f"⚠ تم تجاهل {uploaded_file.name}")
            continue
        file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
        if file_size_mb > APP_CONFIG["MAX_IMAGE_SIZE_MB"]:
            st.warning(f"⚠ حجم {uploaded_file.name} كبير")
            continue
        unique_id = str(uuid.uuid4())[:8]
        original_name = uploaded_file.name.split('.')[0]
        safe_name = re.sub(r'[^\w\-_]', '_', original_name)
        new_filename = f"{safe_name}_{unique_id}.{file_extension}"
        file_path = os.path.join(IMAGES_FOLDER, new_filename)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        saved_files.append(new_filename)
    return saved_files

def delete_image_file(image_filename):
    try:
        file_path = os.path.join(IMAGES_FOLDER, image_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception:
        return False
    return False

def get_image_url(image_filename):
    if not image_filename:
        return None
    file_path = os.path.join(IMAGES_FOLDER, image_filename)
    return file_path if os.path.exists(file_path) else None

def display_images(image_filenames, caption="الصور المرفقة"):
    if not image_filenames:
        return
    st.markdown(f"**{caption}:**")
    images = image_filenames.split(',') if isinstance(image_filenames, str) else image_filenames
    images_per_row = 3
    for i in range(0, len(images), images_per_row):
        cols = st.columns(images_per_row)
        for j in range(images_per_row):
            idx = i + j
            if idx < len(images):
                image_filename = images[idx].strip()
                with cols[j]:
                    image_path = get_image_url(image_filename)
                    if image_path and os.path.exists(image_path):
                        try:
                            st.image(image_path, caption=image_filename, use_column_width=True)
                        except:
                            st.write(f"📷 {image_filename}")
                    else:
                        st.write(f"📷 {image_filename} (غير موجود)")

# -------------------------------
# دوال المستخدمين والجلسات
# -------------------------------
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
            users = json.load(f)
        if "admin" not in users:
            users["admin"] = {
                "password": "admin123",
                "role": "admin",
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"]
            }
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(users, f, indent=4, ensure_ascii=False)
        for username, user_data in users.items():
            if "role" not in user_data:
                user_data["role"] = "admin" if username == "admin" else "viewer"
            if "permissions" not in user_data:
                user_data["permissions"] = ["all"] if user_data["role"] == "admin" else ["view"]
            if "created_at" not in user_data:
                user_data["created_at"] = datetime.now().isoformat()
        return users
    except Exception:
        return {"admin": {"password": "admin123", "role": "admin", "permissions": ["all"], "created_at": datetime.now().isoformat()}}

def save_users(users):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False

def load_state():
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4, ensure_ascii=False)
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
    keys = list(st.session_state.keys())
    for k in keys:
        st.session_state.pop(k, None)
    st.rerun()

# -------------------------------
# واجهة تسجيل الدخول
# -------------------------------
def login_ui():
    users = load_users()
    state = cleanup_sessions(load_state())
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.user_role = None
        st.session_state.user_permissions = []

    st.title(f"{APP_CONFIG['APP_ICON']} تسجيل الدخول - {APP_CONFIG['APP_TITLE']}")

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            current_users = json.load(f)
        user_list = list(current_users.keys())
    except:
        user_list = list(users.keys())

    username_input = st.selectbox("👤 اختر المستخدم", user_list)
    password = st.text_input("🔑 كلمة المرور", type="password")

    active_users = [u for u, v in state.items() if v.get("active")]
    active_count = len(active_users)
    st.caption(f"🔒 المستخدمون النشطون الآن: {active_count} / {MAX_ACTIVE_USERS}")

    if not st.session_state.logged_in:
        if st.button("تسجيل الدخول"):
            current_users = load_users()
            if username_input in current_users and current_users[username_input]["password"] == password:
                if username_input in active_users:
                    st.warning("⚠ هذا المستخدم مسجل دخول بالفعل.")
                    return False
                if active_count >= MAX_ACTIVE_USERS:
                    st.error("🚫 الحد الأقصى للمستخدمين المتصلين حالياً.")
                    return False
                state[username_input] = {"active": True, "login_time": datetime.now().isoformat()}
                save_state(state)
                st.session_state.logged_in = True
                st.session_state.username = username_input
                st.session_state.user_role = current_users[username_input].get("role", "viewer")
                st.session_state.user_permissions = current_users[username_input].get("permissions", ["view"])
                st.success(f"✅ تم تسجيل الدخول: {username_input} ({st.session_state.user_role})")
                st.rerun()
            else:
                st.error("❌ كلمة المرور غير صحيحة.")
        return False
    else:
        username = st.session_state.username
        user_role = st.session_state.user_role
        st.success(f"✅ مسجل الدخول كـ: {username} ({user_role})")
        rem = remaining_time(state, username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.info(f"⏳ الوقت المتبقي: {mins:02d}:{secs:02d}")
        else:
            st.warning("⏰ انتهت الجلسة، سيتم تسجيل الخروج.")
            logout_action()
        if st.button("🚪 تسجيل الخروج"):
            logout_action()
        return True

# -------------------------------
# جلب الملف من GitHub
# -------------------------------
def fetch_from_github_requests():
    try:
        response = requests.get(GITHUB_EXCEL_URL, stream=True, timeout=15)
        response.raise_for_status()
        with open(APP_CONFIG["LOCAL_FILE"], "wb") as f:
            shutil.copyfileobj(response.raw, f)
        return True
    except Exception as e:
        st.error(f"⚠ فشل التحديث من GitHub: {e}")
        return False

def fetch_from_github_api():
    if not GITHUB_AVAILABLE:
        return fetch_from_github_requests()
    try:
        token = st.secrets.get("github", {}).get("token", None)
        if not token:
            return fetch_from_github_requests()
        g = Github(token)
        repo = g.get_repo(APP_CONFIG["REPO_NAME"])
        file_content = repo.get_contents(APP_CONFIG["FILE_PATH"], ref=APP_CONFIG["BRANCH"])
        content = b64decode(file_content.content)
        with open(APP_CONFIG["LOCAL_FILE"], "wb") as f:
            f.write(content)
        return True
    except Exception as e:
        st.error(f"⚠ فشل تحميل الملف من GitHub: {e}")
        return False

# -------------------------------
# تحميل البيانات (لا تخزين مؤقت)
# -------------------------------
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
        st.error(f"❌ خطأ في قراءة الملف: {e}")
        return None

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
    except Exception as e:
        st.error(f"❌ خطأ في قراءة الملف للتعديل: {e}")
        return None

def reload_all_data():
    """إعادة تحميل البيانات لتبويب التعديل فقط"""
    try:
        sheets_edit = load_sheets_for_edit()
        st.session_state['sheets_edit'] = sheets_edit
        return sheets_edit
    except Exception as e:
        st.error(f"❌ خطأ في إعادة تحميل البيانات: {e}")
        return None

# -------------------------------
# حفظ ورفع الملف
# -------------------------------
def save_local_excel_and_push(sheets_dict, commit_message="Update from Streamlit"):
    try:
        with pd.ExcelWriter(APP_CONFIG["LOCAL_FILE"], engine="openpyxl") as writer:
            for name, sh in sheets_dict.items():
                try:
                    sh.to_excel(writer, sheet_name=name, index=False)
                except Exception:
                    sh.astype(object).to_excel(writer, sheet_name=name, index=False)
    except Exception as e:
        st.error(f"⚠ خطأ أثناء الحفظ المحلي: {e}")
        return None
    token = st.secrets.get("github", {}).get("token", None)
    if not token or not GITHUB_AVAILABLE:
        st.warning("⚠ لم يتم العثور على GitHub token. سيتم الحفظ محلياً فقط.")
        return load_sheets_for_edit()
    try:
        g = Github(token)
        repo = g.get_repo(APP_CONFIG["REPO_NAME"])
        with open(APP_CONFIG["LOCAL_FILE"], "rb") as f:
            content = f.read()
        try:
            contents = repo.get_contents(APP_CONFIG["FILE_PATH"], ref=APP_CONFIG["BRANCH"])
            repo.update_file(path=APP_CONFIG["FILE_PATH"], message=commit_message, content=content, sha=contents.sha, branch=APP_CONFIG["BRANCH"])
            st.success(f"✅ تم الحفظ والرفع إلى GitHub بنجاح: {commit_message}")
            return load_sheets_for_edit()
        except Exception:
            repo.create_file(path=APP_CONFIG["FILE_PATH"], message=commit_message, content=content, branch=APP_CONFIG["BRANCH"])
            st.success(f"✅ تم إنشاء ملف جديد على GitHub: {commit_message}")
            return load_sheets_for_edit()
    except Exception as e:
        st.error(f"❌ فشل الرفع إلى GitHub: {e}")
        return None

def auto_save_to_github(sheets_dict, operation_description):
    username = st.session_state.get("username", "unknown")
    commit_message = f"{operation_description} by {username} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    if st.session_state.get("user_role") != "admin":
        add_notification(username=username, action="تعديل بيانات", details=operation_description, target_sheet=operation_description)
    result = save_local_excel_and_push(sheets_dict, commit_message)
    if result is not None:
        st.success("✅ تم حفظ التغييرات تلقائياً في GitHub")
        reload_all_data()  # تحديث نسخة التعديل
        return result
    else:
        st.error("❌ فشل الحفظ التلقائي")
        return sheets_dict

# -------------------------------
# دوال مساعدة للنصوص والصلاحيات
# -------------------------------
def normalize_name(s):
    if s is None: return ""
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
    servised_columns = [
        "Servised by", "SERVISED BY", "servised by", "Servised By",
        "Serviced by", "Service by", "Serviced By", "Service By",
        "خدم بواسطة", "تم الخدمة بواسطة", "فني الخدمة"
    ]
    for col in servised_columns:
        if col in row.index:
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    for col in row.index:
        col_normalized = normalize_name(col)
        if any(keyword in col_normalized for keyword in ["servisedby", "servicedby", "serviceby", "خدمبواسطة", "فني"]):
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    return "-"

def get_images_value(row):
    images_columns = [
        "Images", "images", "Pictures", "pictures", "Attachments", "attachments",
        "صور", "الصور", "مرفقات", "المرفقات", "صور الحدث"
    ]
    for col in images_columns:
        if col in row.index:
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    for col in row.index:
        col_normalized = normalize_name(col)
        if any(keyword in col_normalized for keyword in ["images", "pictures", "attachments", "صور", "مرفقات"]):
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    return ""

def get_user_permissions(user_role, user_permissions):
    if user_role == "admin":
        return {"can_view": True, "can_edit": True, "can_manage_users": False, "can_see_tech_support": False, "can_export_data": True}
    elif user_role == "editor":
        return {"can_view": True, "can_edit": True, "can_manage_users": False, "can_see_tech_support": False, "can_export_data": False}
    else:
        return {"can_view": True, "can_edit": False, "can_manage_users": False, "can_see_tech_support": False, "can_export_data": False}

# -------------------------------
# دالة فحص السيرفيس (تقرأ الملف مباشرة)
# -------------------------------
def find_sheet_by_name(all_sheets, sheet_name_pattern):
    found_sheets = []
    for sheet_name in all_sheets.keys():
        if sheet_name.lower() == sheet_name_pattern.lower():
            return [sheet_name]
        if sheet_name_pattern.lower() in sheet_name.lower():
            found_sheets.append(sheet_name)
    return found_sheets

# -------------------------------
# 🖥 دالة فحص السيرفيس (النسخة المعدلة بالكامل)
# -------------------------------
def check_service_status(card_num, current_tons, all_sheets_param=None):
    if all_sheets_param is None:
        all_sheets_data = st.session_state.get('all_sheets')
    else:
        all_sheets_data = all_sheets_param

    if not all_sheets_data:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return

    # 1. البحث عن شيت الخدمات (ServicePlan)
    service_plan_sheets = find_sheet_by_name(all_sheets_data, "ServicePlan")
    if not service_plan_sheets:
        alternative_names = ["Service", "Services", "سيرفيس", "الخدمات", "خطط الخدمة"]
        for name in alternative_names:
            service_plan_sheets = find_sheet_by_name(all_sheets_data, name)
            if service_plan_sheets:
                break
    if not service_plan_sheets:
        st.error("❌ لم يتم العثور على شيت الخدمات (ServicePlan أو ما شابه).")
        return

    service_plan_df = all_sheets_data[service_plan_sheets[0]].copy()

    # 2. البحث عن شيت الماكينة المحددة
    machine_service_sheets = [s for s in all_sheets_data.keys() if str(card_num) in s]
    if not machine_service_sheets:
        st.warning(f"⚠ لم يتم العثور على شيت لرقم الماكينة {card_num}")
        return
    card_df = all_sheets_data[machine_service_sheets[0]].copy()

    # 3. تجهيز أعمدة النطاق والخدمات في شيت الماكينة
    min_tone_cols = [col for col in card_df.columns if "min" in normalize_name(col) and "ton" in normalize_name(col)]
    max_tone_cols = [col for col in card_df.columns if "max" in normalize_name(col) and "ton" in normalize_name(col)]
    min_col = min_tone_cols[0] if min_tone_cols else None
    max_col = max_tone_cols[0] if max_tone_cols else None

    # تقسيم بيانات الماكينة: صفوف لها نطاق طن (خدمات) وأخرى بدون نطاق (أحداث/ملاحظات)
    rows_with_range = pd.DataFrame()
    rows_without_range = pd.DataFrame()
    if min_col and max_col:
        # تحويل الأعمدة إلى رقمية لتجنب الأخطاء
        card_df[min_col] = pd.to_numeric(card_df[min_col], errors='coerce')
        card_df[max_col] = pd.to_numeric(card_df[max_col], errors='coerce')
        
        mask_with_range = card_df[min_col].notna() & card_df[max_col].notna()
        rows_with_range = card_df[mask_with_range].copy()
        rows_without_range = card_df[~mask_with_range].copy()
    else:
        rows_without_range = card_df.copy()

    # 4. تجهيز شيت خطة الخدمات
    service_min_cols = [col for col in service_plan_df.columns if "min" in normalize_name(col) and "ton" in normalize_name(col)]
    service_max_cols = [col for col in service_plan_df.columns if "max" in normalize_name(col) and "ton" in normalize_name(col)]
    if not service_min_cols or not service_max_cols:
        st.error("❌ لم يتم العثور على أعمدة Min_Tones و Max_Tones في شيت الخدمات.")
        return
    service_min_col = service_min_cols[0]
    service_max_col = service_max_cols[0]
    
    # تحويل أعمدة الخطة إلى أرقام
    service_plan_df[service_min_col] = pd.to_numeric(service_plan_df[service_min_col], errors='coerce')
    service_plan_df[service_max_col] = pd.to_numeric(service_plan_df[service_max_col], errors='coerce')
    service_plan_df = service_plan_df.dropna(subset=[service_min_col, service_max_col])

    service_cols_in_plan = [col for col in service_plan_df.columns if "service" in normalize_name(col) or "خدم" in normalize_name(col)]
    service_col_in_plan = service_cols_in_plan[0] if service_cols_in_plan else "Service"

    # 5. واجهة المستخدم لاختيار نطاق العرض
    st.subheader("⚙ نطاق العرض")
    view_option = st.radio("اختر نطاق العرض:",
                           ("الشريحة الحالية فقط", "كل الشرائح الأقل", "كل الشرائح الأعلى", "نطاق مخصص", "كل الشرائح"),
                           horizontal=True, key=f"service_view_option_{card_num}")
    
    # تحويل current_tons إلى رقم
    try:
        current_tons_num = float(current_tons)
    except (ValueError, TypeError):
        current_tons_num = 0
        st.warning("⚠ لم يتم إدخال عدد أطنان صحيح، سيتم اعتباره صفراً.")

    # تعريف min_range و max_range للاستخدام في حالة النطاق المخصص
    min_range = st.session_state.get(f"service_min_range_{card_num}", max(0, current_tons_num - 500))
    max_range = st.session_state.get(f"service_max_range_{card_num}", current_tons_num + 500)
    if view_option == "نطاق مخصص":
        col1, col2 = st.columns(2)
        with col1:
            min_range = st.number_input("من (طن):", min_value=0, step=100, value=int(min_range), key=f"service_min_range_{card_num}")
        with col2:
            max_range = st.number_input("إلى (طن):", min_value=int(min_range), step=100, value=int(max_range), key=f"service_max_range_{card_num}")

    # 6. تحديد الشرائح المطلوبة من خطة الخدمات بناءً على الخيار المختار
    if view_option == "الشريحة الحالية فقط":
        selected_slices = service_plan_df[(service_plan_df[service_min_col] <= current_tons_num) & (service_plan_df[service_max_col] >= current_tons_num)]
    elif view_option == "كل الشرائح الأقل":
        selected_slices = service_plan_df[service_plan_df[service_max_col] <= current_tons_num]
    elif view_option == "كل الشرائح الأعلى":
        selected_slices = service_plan_df[service_plan_df[service_min_col] >= current_tons_num]
    elif view_option == "نطاق مخصص":
        selected_slices = service_plan_df[(service_plan_df[service_min_col] >= min_range) & (service_plan_df[service_max_col] <= max_range)]
    else:  # كل الشرائح
        selected_slices = service_plan_df.copy()

    if selected_slices.empty:
        st.warning("⚠ لا توجد شرائح مطابقة حسب النطاق المحدد.")
        # حتى لو لا توجد شرائح، يمكن عرض الصفوف التي ليس لها نطاق
        if not rows_without_range.empty:
            st.info("ℹ️ توجد أحداث أو ملاحظات بدون نطاق طن، سيتم عرضها أدناه.")
        else:
            return

    # 7. تحليل النتائج
    all_results = []
    service_stats = {"service_counts": {}, "service_done_counts": {}, "total_needed_services": 0, "total_done_services": 0, "by_slice": {}}

    # 7.1 معالجة الشرائح المحددة
    for _, current_slice in selected_slices.iterrows():
        slice_min = current_slice[service_min_col]
        slice_max = current_slice[service_max_col]
        slice_key = f"{slice_min}-{slice_max}"
        
        needed_service_raw = current_slice.get(service_col_in_plan, "")
        needed_parts = split_needed_services(needed_service_raw)
        needed_norm = [normalize_name(p) for p in needed_parts]
        
        service_stats["by_slice"][slice_key] = {"needed": needed_parts, "done": [], "not_done": [], "total_needed": len(needed_parts), "total_done": 0}
        for service in needed_parts:
            service_stats["service_counts"][service] = service_stats["service_counts"].get(service, 0) + 1
        service_stats["total_needed_services"] += len(needed_parts)
        
        # البحث عن صفوف الماكينة التي تقع ضمن هذا النطاق
        if min_col and max_col and not rows_with_range.empty:
            mask = (rows_with_range[min_col] <= slice_max) & (rows_with_range[max_col] >= slice_min)
            matching_rows = rows_with_range[mask]
        else:
            matching_rows = pd.DataFrame()
        
        if not matching_rows.empty:
            for _, row in matching_rows.iterrows():
                done_services_set = set()
                # استخراج الخدمات المنفذة من الأعمدة غير الأساسية
                metadata_columns = {min_col, max_col, "card", "Tones", "Date", "Other", "Event", "Correction", "Images",
                                    "Card", "TONES", "DATE", "OTHER", "EVENT", "CORRECTION", "IMAGES",
                                    "servised by", "Servised By", "Serviced by", "Service by",
                                    "خدم بواسطة", "تم الخدمة بواسطة", "فني الخدمة",
                                    "صور", "الصور", "مرفقات", "المرفقات"}
                # إزالة القيم None من set
                metadata_columns = {c for c in metadata_columns if c is not None}
                all_columns = set(rows_with_range.columns)
                service_columns = all_columns - metadata_columns
                final_service_columns = set()
                for col in service_columns:
                    col_normalized = normalize_name(col)
                    if not any(normalize_name(mc) == col_normalized for mc in metadata_columns):
                        final_service_columns.add(col)
                for col in final_service_columns:
                    val = str(row.get(col, "")).strip()
                    if val and val.lower() not in ["nan", "none", "", "null", "0"]:
                        if val.lower() not in ["no", "false", "not done", "لم تتم", "x", "-"]:
                            done_services_set.add(col)
                            service_stats["service_done_counts"][col] = service_stats["service_done_counts"].get(col, 0) + 1
                            service_stats["total_done_services"] += 1
                
                # استخراج البيانات للعرض
                date_cols = [col for col in row.index if "date" in normalize_name(col) or "تاريخ" in normalize_name(col)]
                date_col = date_cols[0] if date_cols else "Date"
                current_date = str(row.get(date_col, "")).strip() if pd.notna(row.get(date_col)) else "-"
                
                tone_cols = [col for col in row.index if "ton" in normalize_name(col) and not ("min" in normalize_name(col) or "max" in normalize_name(col))]
                tone_col = tone_cols[0] if tone_cols else "Tones"
                current_tones = str(row.get(tone_col, "")).strip() if pd.notna(row.get(tone_col)) else "-"
                
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
            # لا توجد صفوف مطابقة لهذه الشريحة
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
    
    # 7.2 معالجة الصفوف التي ليس لها نطاق طن (الأحداث والملاحظات)
    additional_results = []
    if not rows_without_range.empty:
        for _, row in rows_without_range.iterrows():
            done_services_set = set()
            metadata_columns = {"card", "Tones", "Date", "Other", "Event", "Correction", "Images",
                                "Card", "TONES", "DATE", "OTHER", "EVENT", "CORRECTION", "IMAGES",
                                "servised by", "Servised By", "Serviced by", "Service by",
                                "خدم بواسطة", "تم الخدمة بواسطة", "فني الخدمة",
                                "صور", "الصور", "مرفقات", "المرفقات"}
            if min_col:
                metadata_columns.add(min_col)
            if max_col:
                metadata_columns.add(max_col)
            metadata_columns = {c for c in metadata_columns if c is not None}
            all_columns = set(rows_without_range.columns)
            service_columns = all_columns - metadata_columns
            final_service_columns = set()
            for col in service_columns:
                col_normalized = normalize_name(col)
                if not any(normalize_name(mc) == col_normalized for mc in metadata_columns):
                    final_service_columns.add(col)
            for col in final_service_columns:
                val = str(row.get(col, "")).strip()
                if val and val.lower() not in ["nan", "none", "", "null", "0"]:
                    if val.lower() not in ["no", "false", "not done", "لم تتم", "x", "-"]:
                        done_services_set.add(col)
                        # لا نضيفها إلى إحصائيات الخدمات المطلوبة لأنها ليست ضمن خطة
            date_cols = [col for col in row.index if "date" in normalize_name(col) or "تاريخ" in normalize_name(col)]
            date_col = date_cols[0] if date_cols else "Date"
            current_date = str(row.get(date_col, "")).strip() if pd.notna(row.get(date_col)) else "-"
            
            tone_cols = [col for col in row.index if "ton" in normalize_name(col) and not ("min" in normalize_name(col) or "max" in normalize_name(col))]
            tone_col = tone_cols[0] if tone_cols else "Tones"
            current_tones = str(row.get(tone_col, "")).strip() if pd.notna(row.get(tone_col)) else "-"
            
            servised_by_value = get_servised_by_value(row)
            images_value = get_images_value(row)
            done_services = sorted(list(done_services_set))
            
            additional_results.append({
                "Card Number": card_num,
                "Min_Tons": "بدون نطاق",
                "Max_Tons": "بدون نطاق",
                "Service Needed": "(حدث/ملاحظة خارج خطة الخدمة)",
                "Service Done": ", ".join(done_services) if done_services else "-",
                "Service Didn't Done": "-",
                "Tones": current_tones,
                "Servised by": servised_by_value,
                "Date": current_date,
                "Images": images_value if images_value else "-"
            })
    
    # دمج النتائج
    all_results.extend(additional_results)
    result_df = pd.DataFrame(all_results).dropna(how="all").reset_index(drop=True)
    
    # 8. عرض النتائج والإحصائيات
    st.markdown("### 📋 نتائج فحص السيرفيس")
    if not result_df.empty:
        st.dataframe(result_df.style.apply(style_table, axis=1), use_container_width=True)
        show_service_statistics(service_stats, result_df, has_additional_rows=bool(additional_results))
        if "Images" in result_df.columns:
            for idx, row in result_df.iterrows():
                images_value = row.get("Images", "")
                if images_value and images_value != "-":
                    display_images(images_value, f"📷 صور للحدث #{idx+1}")
        permissions = get_user_permissions(st.session_state.get("user_role", "viewer"), st.session_state.get("user_permissions", ["view"]))
        if permissions["can_export_data"]:
            buffer = io.BytesIO()
            result_df.to_excel(buffer, index=False, engine="openpyxl")
            st.download_button(label="💾 حفظ النتائج كـ Excel (للادمن فقط)", data=buffer.getvalue(),
                               file_name=f"Service_Report_Card{card_num}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("ℹ️ لا توجد خدمات مسجلة لهذه الماكينة.")

# -------------------------------
# 📊 دالة عرض الإحصائيات (معدلة لدعم الصفوف الإضافية)
# -------------------------------
def show_service_statistics(service_stats, result_df, has_additional_rows=False):
    st.markdown("---")
    st.markdown("### 📊 الإحصائيات والنسب المئوية")
    if service_stats["total_needed_services"] == 0 and not has_additional_rows:
        st.info("ℹ️ لا توجد خدمات مطلوبة في النطاق المحدد.")
        return
    
    if service_stats["total_needed_services"] > 0:
        completion_rate = (service_stats["total_done_services"] / service_stats["total_needed_services"]) * 100
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(label="📈 نسبة الإنجاز العامة", value=f"{completion_rate:.1f}%", delta=f"{service_stats['total_done_services']}/{service_stats['total_needed_services']}")
        with col2:
            st.metric(label="🔢 عدد الخدمات المطلوبة", value=service_stats["total_needed_services"])
        with col3:
            st.metric(label="✅ الخدمات المنفذة", value=service_stats["total_done_services"])
        with col4:
            remaining = service_stats["total_needed_services"] - service_stats["total_done_services"]
            st.metric(label="⏳ الخدمات المتبقية", value=remaining)
        st.markdown("---")
    else:
        st.info("ℹ️ لا توجد خدمات مطلوبة في النطاق المحدد، ولكن توجد أحداث أو ملاحظات خارج الخطة.")
        st.markdown("---")
    
    if has_additional_rows:
        st.info("📌 ملاحظة: يوجد صفوف في الجدول تحمل عبارة 'بدون نطاق' أو '(حدث/ملاحظة خارج خطة الخدمة)'، وهي أحداث أو ملاحظات ليس لها نطاق طن محدد ولا تدخل في إحصائيات الخدمات أعلاه.")
    
    # باقي الإحصائيات (توزيع الخدمات، حسب الشريحة) تبقى كما هي إذا كانت هناك خدمات مطلوبة
    if service_stats["total_needed_services"] == 0:
        return
        
    stat_tabs = st.tabs(["📝 إحصائيات الخدمات", "📋 توزيع الخدمات", "📊 حسب الشريحة"])
    with stat_tabs[0]:
        st.markdown("#### 📝 إحصائيات مفصلة لكل خدمة")
        stat_data = []
        all_services = set(service_stats["service_counts"].keys()).union(set(service_stats["service_done_counts"].keys()))
        for service in sorted(all_services):
            needed_count = service_stats["service_counts"].get(service, 0)
            done_count = service_stats["service_done_counts"].get(service, 0)
            completion_rate_service = (done_count / needed_count * 100) if needed_count > 0 else 0
            stat_data.append({"الخدمة": service, "مطلوبة": needed_count, "منفذة": done_count,
                              "متبقية": needed_count - done_count, "نسبة الإنجاز": f"{completion_rate_service:.1f}%",
                              "حالة": "✅ ممتاز" if completion_rate_service >= 90 else "🟢 جيد" if completion_rate_service >= 70 else "🟡 متوسط" if completion_rate_service >= 50 else "🔴 ضعيف"})
        if stat_data:
            stat_df = pd.DataFrame(stat_data)
            st.dataframe(stat_df, use_container_width=True, height=400)
    with stat_tabs[1]:
        st.markdown("#### 📋 توزيع الخدمات")
        try:
            import plotly.express as px
            plot_data = []
            for service, needed_count in service_stats["service_counts"].items():
                done_count = service_stats["service_done_counts"].get(service, 0)
                plot_data.append({"الخدمة": service, "النوع": "مطلوبة", "العدد": needed_count})
                plot_data.append({"الخدمة": service, "النوع": "منفذة", "العدد": done_count})
            plot_df = pd.DataFrame(plot_data)
            fig = px.bar(plot_df, x="الخدمة", y="العدد", color="النوع", barmode="group",
                         title="توزيع الخدمات المطلوبة والمنفذة",
                         color_discrete_map={"مطلوبة": "#FF6B6B", "منفذة": "#4ECDC4"})
            fig.update_layout(xaxis_title="الخدمة", yaxis_title="العدد", showlegend=True, height=500)
            st.plotly_chart(fig, use_container_width=True)
            fig2 = px.pie(names=["✅ منفذة", "⏳ غير منفذة"],
                          values=[service_stats["total_done_services"], service_stats["total_needed_services"] - service_stats["total_done_services"]],
                          title="نسبة الإنجاز العامة", color_discrete_sequence=["#4ECDC4", "#FF6B6B"])
            fig2.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig2, use_container_width=True)
        except ImportError:
            st.info("📊 عرض البيانات باستخدام الرسوم البيانية المضمنة")
            dist_data = []
            for service, needed_count in service_stats["service_counts"].items():
                done_count = service_stats["service_done_counts"].get(service, 0)
                completion_rate = (done_count / needed_count * 100) if needed_count > 0 else 0
                dist_data.append({"الخدمة": service, "مطلوبة": needed_count, "منفذة": done_count, "نسبة": f"{completion_rate:.1f}%"})
            if dist_data:
                dist_df = pd.DataFrame(dist_data).sort_values("نسبة", ascending=False)
                st.dataframe(dist_df, use_container_width=True, height=300)
            chart_data = pd.DataFrame({"الخدمة": list(service_stats["service_counts"].keys()),
                                       "مطلوبة": list(service_stats["service_counts"].values()),
                                       "منفذة": [service_stats["service_done_counts"].get(service, 0) for service in service_stats["service_counts"].keys()]})
            if len(chart_data) > 10:
                chart_data = chart_data.nlargest(10, "مطلوبة")
            st.bar_chart(chart_data.set_index("الخدمة"), height=400)
            st.markdown(f"**📈 نسبة الإنجاز العامة:** {completion_rate:.1f}%")
            progress_value = min(max(completion_rate / 100, 0.0), 1.0)
            st.progress(progress_value)
    with stat_tabs[2]:
        st.markdown("#### 📊 الإحصائيات حسب الشريحة")
        slice_stats_data = []
        for slice_key, slice_data in service_stats["by_slice"].items():
            completion_rate_slice = (slice_data["total_done"] / slice_data["total_needed"] * 100) if slice_data["total_needed"] > 0 else 0
            slice_stats_data.append({"الشريحة": slice_key, "الخدمات المطلوبة": slice_data["total_needed"],
                                     "الخدمات المنفذة": slice_data["total_done"], "الخدمات المتبقية": slice_data["total_needed"] - slice_data["total_done"],
                                     "نسبة الإنجاز": f"{completion_rate_slice:.1f}%",
                                     "حالة الشريحة": "✅ ممتازة" if completion_rate_slice >= 90 else "🟢 جيدة" if completion_rate_slice >= 70 else "🟡 متوسطة" if completion_rate_slice >= 50 else "🔴 ضعيفة"})
        if slice_stats_data:
            slice_stats_df = pd.DataFrame(slice_stats_data)
            st.dataframe(slice_stats_df, use_container_width=True, height=400)
# -------------------------------
# دوال تعديل البيانات (بدون إدارة مستخدمين)
# -------------------------------
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
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("💾 حفظ التغييرات", key=f"save_{sheet_name}", type="primary"):
                sheets_edit[sheet_name] = edited_df.astype(object)
                if st.session_state.get("user_role") != "admin":
                    add_notification(username=st.session_state.get("username", "غير معروف"), action="تعديل شيت",
                                     details=f"تم تعديل شيت '{sheet_name}' - {len(edited_df)} صف، {len(edited_df.columns)} عمود",
                                     target_sheet=sheet_name)
                new_sheets = auto_save_to_github(sheets_edit, f"تعديل يدوي في شيت {sheet_name}")
                if new_sheets is not None:
                    sheets_edit = new_sheets
                    st.session_state.unsaved_changes[sheet_name] = False
                    st.session_state['sheets_edit'] = sheets_edit
                    st.success(f"✅ تم حفظ التغييرات في شيت {sheet_name} بنجاح!")
                    st.rerun()
                else:
                    st.error("❌ فشل حفظ التغييرات!")
        with col2:
            if st.button("↩️ تراجع عن التغييرات", key=f"undo_{sheet_name}"):
                if sheet_name in st.session_state.original_sheets:
                    sheets_edit[sheet_name] = st.session_state.original_sheets[sheet_name].astype(object)
                    st.session_state.unsaved_changes[sheet_name] = False
                    st.info(f"↩️ تم التراجع عن التغييرات في شيت {sheet_name}")
                    st.rerun()
                else:
                    st.warning("⚠ لا توجد بيانات أصلية للتراجع!")
        with col3:
            with st.expander("📊 ملخص التغييرات", expanded=False):
                changes_count = 0
                if len(edited_df) > len(df):
                    added_rows = len(edited_df) - len(df)
                    st.write(f"➕ **صفوف مضافة:** {added_rows}")
                    changes_count += added_rows
                elif len(edited_df) < len(df):
                    deleted_rows = len(df) - len(edited_df)
                    st.write(f"🗑️ **صفوف محذوفة:** {deleted_rows}")
                    changes_count += deleted_rows
                changed_cells = 0
                if len(edited_df) == len(df) and edited_df.columns.equals(df.columns):
                    for col in df.columns:
                        if not edited_df[col].equals(df[col]):
                            col_changes = (edited_df[col] != df[col]).sum()
                            changed_cells += col_changes
                if changed_cells > 0:
                    st.write(f"✏️ **خلايا معدلة:** {changed_cells}")
                    changes_count += changed_cells
                if changes_count == 0:
                    st.write("🔄 **لا توجد تغييرات**")
    else:
        if st.session_state.unsaved_changes.get(sheet_name, False):
            st.info("ℹ️ التغييرات السابقة تم حفظها.")
            st.session_state.unsaved_changes[sheet_name] = False
        if st.button("🔄 تحديث البيانات", key=f"refresh_{sheet_name}"):
            st.rerun()
    return sheets_edit

def add_new_sheet(sheets_edit):
    st.subheader("🆕 إضافة شيت جديد")
    st.markdown("### إضافة شيت جديد بأي اسم")
    col1, col2 = st.columns(2)
    with col1:
        new_sheet_name = st.text_input("اسم الشيت الجديد:", placeholder="أدخل أي اسم للشيت", key="new_sheet_name_input")
        st.caption("أو اختر من الأسماء المقترحة:")
        suggested_names = st.columns(3)
        with suggested_names[0]:
            if st.button("📊 تقرير 2025", key="suggest_report"):
                st.session_state.new_sheet_name_input = "تقرير 2025"
                st.rerun()
        with suggested_names[1]:
            if st.button("🔧 صيانة جديدة", key="suggest_maintenance"):
                st.session_state.new_sheet_name_input = "صيانة جديدة"
                st.rerun()
        with suggested_names[2]:
            if st.button("📈 إحصائيات", key="suggest_stats"):
                st.session_state.new_sheet_name_input = "إحصائيات"
                st.rerun()
    with col2:
        st.markdown("**خيارات الشيت الجديد:**")
        create_with_template = st.checkbox("إنشاء بنموذج قياسي", value=True, key="create_with_template")
        if create_with_template:
            template_type = st.selectbox("نموذج الشيت:", ["ماكينة جديدة", "سجل أحداث", "سجل خدمات", "جدول بيانات عام"], key="sheet_template")
        num_initial_rows = st.number_input("عدد الصفوف الابتدائية:", min_value=1, max_value=100, value=10, key="initial_rows")
    if create_with_template:
        if template_type == "ماكينة جديدة":
            default_columns = ["Card", "Date", "Event", "Correction", "Servised by", "Tones", "Notes"]
        elif template_type == "سجل أحداث":
            default_columns = ["Event_ID", "Date", "Machine_Number", "Event_Type", "Description", "Technician", "Status"]
        elif template_type == "سجل خدمات":
            default_columns = ["Service_ID", "Date", "Machine_Number", "Service_Type", "Details", "Technician", "Cost", "Status"]
        else:
            default_columns = ["ID", "Date", "Description", "Value", "Category", "Notes"]
    else:
        default_columns = ["Column1", "Column2", "Column3", "Column4", "Column5"]
    st.markdown("### ✏ تعديل أعمدة الشيت الجديد")
    columns_data = []
    for i in range(len(default_columns)):
        col1, col2 = st.columns([3, 1])
        with col1:
            col_name = st.text_input(f"اسم العمود {i+1}:", value=default_columns[i] if i < len(default_columns) else f"Column{i+1}", key=f"col_name_{i}")
        with col2:
            col_type = st.selectbox("نوع البيانات:", ["نص", "رقم", "تاريخ", "ملاحظات"], key=f"col_type_{i}")
        columns_data.append({"name": col_name, "type": col_type})
    if st.button("➕ إضافة عمود جديد", key="add_more_columns"):
        if "extra_columns" not in st.session_state:
            st.session_state.extra_columns = 0
        st.session_state.extra_columns += 1
        st.rerun()
    if "extra_columns" in st.session_state and st.session_state.extra_columns > 0:
        for i in range(st.session_state.extra_columns):
            extra_idx = len(default_columns) + i
            col1, col2 = st.columns([3, 1])
            with col1:
                col_name = st.text_input(f"اسم العمود الإضافي {i+1}:", value=f"Extra_Column_{i+1}", key=f"extra_col_name_{i}")
            with col2:
                col_type = st.selectbox("نوع البيانات:", ["نص", "رقم", "تاريخ", "ملاحظات"], key=f"extra_col_type_{i}")
            columns_data.append({"name": col_name, "type": col_type})
    if st.button("🆕 إنشاء الشيت الجديد", type="primary", key="create_new_sheet_btn"):
        if not new_sheet_name.strip():
            st.warning("⚠ الرجاء إدخال اسم للشيت الجديد.")
            return
        if new_sheet_name in sheets_edit:
            st.error(f"❌ الشيت '{new_sheet_name}' موجود بالفعل.")
            return
        column_names = [col["name"] for col in columns_data]
        initial_data = {}
        for i, col_name in enumerate(column_names):
            col_type = columns_data[i]["type"]
            if col_type == "رقم":
                initial_data[col_name] = [0] * num_initial_rows
            elif col_type == "تاريخ":
                initial_data[col_name] = [datetime.now().strftime("%d/%m/%Y")] * num_initial_rows
            else:
                initial_data[col_name] = [""] * num_initial_rows
        new_df = pd.DataFrame(initial_data)
        sheets_edit[new_sheet_name] = new_df.astype(object)
        add_notification(username=st.session_state.get("username", "غير معروف"), action="إضافة شيت جديد",
                         details=f"تم إنشاء شيت جديد باسم '{new_sheet_name}' يحتوي على {len(column_names)} أعمدة و {num_initial_rows} صف",
                         target_sheet=new_sheet_name)
        new_sheets = auto_save_to_github(sheets_edit, f"إضافة شيت جديد: {new_sheet_name}")
        if new_sheets is not None:
            sheets_edit = new_sheets
            st.session_state['sheets_edit'] = sheets_edit
            st.success(f"✅ تم إنشاء الشيت '{new_sheet_name}' بنجاح!")
            st.info(f"📊 يحتوي الشيت على {len(column_names)} أعمدة و {num_initial_rows} صف")
            with st.expander("👁️ معاينة الشيت الجديد", expanded=True):
                st.dataframe(new_df.head(5), use_container_width=True)
            if "extra_columns" in st.session_state:
                del st.session_state.extra_columns
            st.rerun()
        else:
            st.error("❌ فشل إنشاء الشيت الجديد.")

def add_new_event(sheets_edit):
    st.subheader("➕ إضافة حدث جديد مع صور")
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="add_event_sheet")
    df = sheets_edit[sheet_name].astype(str)
    st.markdown("أدخل بيانات الحدث الجديد:")
    col1, col2 = st.columns(2)
    with col1:
        card_num = st.text_input("رقم الماكينة:", key="new_event_card")
        event_text = st.text_area("الحدث:", key="new_event_text")
    with col2:
        correction_text = st.text_area("التصحيح:", key="new_correction_text")
        serviced_by = st.text_input("فني الخدمة:", key="new_serviced_by")
    event_date = st.text_input("التاريخ (مثال: 20/5/2025):", key="new_event_date")
    st.markdown("---")
    st.markdown("### 📷 رفع صور للحدث (اختياري)")
    uploaded_files = st.file_uploader("اختر الصور المرفقة للحدث:", type=APP_CONFIG["ALLOWED_IMAGE_TYPES"], accept_multiple_files=True, key="event_images_uploader")
    if uploaded_files:
        st.info(f"📁 تم اختيار {len(uploaded_files)} صورة")
        preview_cols = st.columns(min(3, len(uploaded_files)))
        for idx, uploaded_file in enumerate(uploaded_files):
            with preview_cols[idx % 3]:
                try:
                    st.image(uploaded_file, caption=uploaded_file.name, use_column_width=True)
                except:
                    st.write(f"📷 {uploaded_file.name}")
    if st.button("💾 إضافة الحدث الجديد مع الصور", key="add_new_event_btn"):
        if not card_num.strip():
            st.warning("⚠ الرجاء إدخال رقم الماكينة.")
            return
        saved_images = save_uploaded_images(uploaded_files) if uploaded_files else []
        if saved_images:
            st.success(f"✅ تم حفظ {len(saved_images)} صورة بنجاح")
        new_row = {}
        new_row["card"] = card_num.strip()
        if event_date.strip():
            new_row["Date"] = event_date.strip()
        event_columns = [col for col in df.columns if normalize_name(col) in ["event", "events", "الحدث", "الأحداث"]]
        if event_columns and event_text.strip():
            new_row[event_columns[0]] = event_text.strip()
        elif not event_columns and event_text.strip():
            new_row["Event"] = event_text.strip()
        correction_columns = [col for col in df.columns if normalize_name(col) in ["correction", "correct", "تصحيح", "تصويب"]]
        if correction_columns and correction_text.strip():
            new_row[correction_columns[0]] = correction_text.strip()
        elif not correction_columns and correction_text.strip():
            new_row["Correction"] = correction_text.strip()
        servised_col = None
        servised_columns = [col for col in df.columns if normalize_name(col) in ["servisedby", "servicedby", "serviceby", "خدمبواسطة"]]
        if servised_columns:
            servised_col = servised_columns[0]
        else:
            for col in df.columns:
                if "servis" in normalize_name(col) or "service" in normalize_name(col) or "فني" in col:
                    servised_col = col
                    break
            if not servised_col:
                servised_col = "Servised by"
        if serviced_by.strip():
            new_row[servised_col] = serviced_by.strip()
        if saved_images:
            images_col = None
            images_columns = [col for col in df.columns if normalize_name(col) in ["images", "pictures", "attachments", "صور", "مرفقات"]]
            if images_columns:
                images_col = images_columns[0]
            else:
                images_col = "Images"
                if images_col not in df.columns:
                    df[images_col] = ""
            new_row[images_col] = ", ".join(saved_images)
        new_row_df = pd.DataFrame([new_row]).astype(str)
        df_new = pd.concat([df, new_row_df], ignore_index=True)
        sheets_edit[sheet_name] = df_new.astype(object)
        add_notification(username=st.session_state.get("username", "غير معروف"), action="إضافة حدث جديد",
                         details=f"تمت إضافة حدث جديد للماكينة {card_num} في شيت {sheet_name}" + (f" مع {len(saved_images)} صورة" if saved_images else ""),
                         target_sheet=sheet_name, target_row=len(df_new) - 1)
        new_sheets = auto_save_to_github(sheets_edit, f"إضافة حدث جديد في {sheet_name}" + (f" مع {len(saved_images)} صورة" if saved_images else ""))
        if new_sheets is not None:
            sheets_edit = new_sheets
            st.session_state['sheets_edit'] = sheets_edit
            st.success("✅ تم إضافة الحدث الجديد بنجاح!")
            with st.expander("📋 ملخص الحدث المضافة", expanded=True):
                st.markdown(f"**رقم الماكينة:** {card_num}")
                st.markdown(f"**الحدث:** {event_text[:100]}{'...' if len(event_text) > 100 else ''}")
                if saved_images:
                    st.markdown(f"**عدد الصور المرفقة:** {len(saved_images)}")
                    display_images(saved_images, "الصور المحفوظة")
            st.rerun()

def edit_events_and_corrections(sheets_edit):
    st.subheader("✏ تعديل الحدث والتصحيح والصور")
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_events_sheet")
    df = sheets_edit[sheet_name].astype(str)
    st.markdown("### 📋 البيانات الحالية (الحدث والتصحيح والصور)")
    display_columns = ["card", "Date"]
    event_columns = [col for col in df.columns if normalize_name(col) in ["event", "events", "الحدث", "الأحداث"]]
    if event_columns:
        display_columns.append(event_columns[0])
    correction_columns = [col for col in df.columns if normalize_name(col) in ["correction", "correct", "تصحيح", "تصويب"]]
    if correction_columns:
        display_columns.append(correction_columns[0])
    servised_columns = [col for col in df.columns if normalize_name(col) in ["servisedby", "servicedby", "serviceby", "خدمبواسطة"]]
    if servised_columns:
        display_columns.append(servised_columns[0])
    images_columns = [col for col in df.columns if normalize_name(col) in ["images", "pictures", "attachments", "صور", "مرفقات"]]
    if images_columns:
        display_columns.append(images_columns[0])
    display_df = df[display_columns].copy()
    st.dataframe(display_df, use_container_width=True)
    st.markdown("### ✏ اختر الصف للتعديل")
    row_index = st.number_input("رقم الصف (ابدأ من 0):", min_value=0, max_value=len(df)-1, step=1, key="edit_row_index")
    if st.button("تحميل بيانات الصف", key="load_row_data"):
        if 0 <= row_index < len(df):
            st.session_state["editing_row"] = row_index
            st.session_state["editing_data"] = df.iloc[row_index].to_dict()
    if "editing_data" in st.session_state:
        editing_data = st.session_state["editing_data"]
        st.markdown("### تعديل البيانات")
        col1, col2 = st.columns(2)
        with col1:
            new_card = st.text_input("رقم الماكينة:", value=editing_data.get("card", ""), key="edit_card")
            new_date = st.text_input("التاريخ:", value=editing_data.get("Date", ""), key="edit_date")
        with col2:
            new_serviced_by = st.text_input("فني الخدمة:", value=editing_data.get("Servised by", ""), key="edit_serviced_by")
        event_col = None
        correction_col = None
        for col in df.columns:
            col_norm = normalize_name(col)
            if col_norm in ["event", "events", "الحدث", "الأحداث"]:
                event_col = col
            elif col_norm in ["correction", "correct", "تصحيح", "تصويب"]:
                correction_col = col
        if event_col:
            new_event = st.text_area("الحدث:", value=editing_data.get(event_col, ""), key="edit_event")
        if correction_col:
            new_correction = st.text_area("التصحيح:", value=editing_data.get(correction_col, ""), key="edit_correction")
        st.markdown("---")
        st.markdown("### 📷 إدارة صور الحدث")
        images_col = None
        for col in df.columns:
            col_norm = normalize_name(col)
            if col_norm in ["images", "pictures", "attachments", "صور", "مرفقات"]:
                images_col = col
                break
        existing_images = []
        if images_col and images_col in editing_data:
            existing_images_str = editing_data.get(images_col, "")
            if existing_images_str and existing_images_str != "-":
                existing_images = [img.strip() for img in existing_images_str.split(",") if img.strip()]
        if existing_images:
            st.markdown("**الصور الحالية:**")
            display_images(existing_images, "")
            if st.checkbox("🗑️ حذف كل الصور الحالية", key="delete_existing_images"):
                existing_images = []
        st.markdown("**إضافة صور جديدة:**")
        new_uploaded_files = st.file_uploader("اختر صور جديدة لإضافتها:", type=APP_CONFIG["ALLOWED_IMAGE_TYPES"], accept_multiple_files=True, key="edit_images_uploader")
        all_images = existing_images.copy()
        if new_uploaded_files:
            st.info(f"📁 تم اختيار {len(new_uploaded_files)} صورة جديدة")
            new_saved_images = save_uploaded_images(new_uploaded_files)
            if new_saved_images:
                all_images.extend(new_saved_images)
                st.success(f"✅ تم حفظ {len(new_saved_images)} صورة جديدة")
        if st.button("💾 حفظ التعديلات والصور", key="save_edits_btn"):
            df.at[row_index, "card"] = new_card
            df.at[row_index, "Date"] = new_date
            if event_col:
                df.at[row_index, event_col] = new_event
            if correction_col:
                df.at[row_index, correction_col] = new_correction
            servised_col = None
            for col in df.columns:
                if normalize_name(col) in ["servisedby", "servicedby", "serviceby", "خدمبواسطة"]:
                    servised_col = col
                    break
            if servised_col and new_serviced_by.strip():
                df.at[row_index, servised_col] = new_serviced_by.strip()
            if images_col:
                if all_images:
                    df.at[row_index, images_col] = ", ".join(all_images)
                else:
                    df.at[row_index, images_col] = ""
            elif all_images:
                images_col = "Images"
                df[images_col] = ""
                df.at[row_index, images_col] = ", ".join(all_images)
            sheets_edit[sheet_name] = df.astype(object)
            add_notification(username=st.session_state.get("username", "غير معروف"), action="تعديل حدث",
                             details=f"تم تعديل حدث للماكينة {new_card} في شيت {sheet_name} (الصف {row_index})" + (f" مع تحديث {len(all_images)} صورة" if all_images else ""),
                             target_sheet=sheet_name, target_row=row_index)
            new_sheets = auto_save_to_github(sheets_edit, f"تعديل حدث في {sheet_name} - الصف {row_index}" + (f" مع تحديث الصور" if all_images else ""))
            if new_sheets is not None:
                sheets_edit = new_sheets
                st.session_state['sheets_edit'] = sheets_edit
                st.success("✅ تم حفظ التعديلات بنجاح!")
                if all_images:
                    st.info(f"📷 العدد النهائي للصور: {len(all_images)}")
                    display_images(all_images, "الصور المحفوظة")
                if "editing_row" in st.session_state:
                    del st.session_state["editing_row"]
                if "editing_data" in st.session_state:
                    del st.session_state["editing_data"]
                st.rerun()

# ===============================
# الواجهة الرئيسية
# ===============================
st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")
setup_images_folder()

# تهيئة session_state لبيانات التعديل فقط
if 'sheets_edit' not in st.session_state:
    sheets_edit = load_sheets_for_edit()
    st.session_state['sheets_edit'] = sheets_edit
else:
    if st.session_state.get('sheets_edit') is None:
        st.session_state['sheets_edit'] = load_sheets_for_edit()

sheets_edit = st.session_state['sheets_edit']

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
            st.session_state['sheets_edit'] = load_sheets_for_edit()
            st.rerun()
    if st.button("🗑 مسح الكاش", key="clear_cache"):
        try:
            st.cache_data.clear()
            st.session_state['sheets_edit'] = load_sheets_for_edit()
            st.rerun()
        except Exception as e:
            st.error(f"❌ خطأ في مسح الكاش: {e}")
    if st.button("🔄 تحديث الجلسة", key="refresh_session"):
        users = load_users()
        username = st.session_state.get("username")
        if username and username in users:
            st.session_state.user_role = users[username].get("role", "viewer")
            st.session_state.user_permissions = users[username].get("permissions", ["view"])
            st.success("✅ تم تحديث بيانات الجلسة!")
            st.rerun()
        else:
            st.warning("⚠ لا يمكن تحديث الجلسة.")
    if st.session_state.get("unsaved_changes", {}):
        unsaved_count = sum(1 for v in st.session_state.unsaved_changes.values() if v)
        if unsaved_count > 0:
            st.markdown("---")
            st.warning(f"⚠ لديك {unsaved_count} شيت به تغييرات غير محفوظة")
            if st.button("💾 حفظ جميع التغييرات", key="save_all_changes", type="primary"):
                st.session_state["save_all_requested"] = True
                st.rerun()
    st.markdown("---")
    if st.button("🚪 تسجيل الخروج", key="logout_btn"):
        logout_action()

st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")

username = st.session_state.get("username")
user_role = st.session_state.get("user_role", "viewer")
user_permissions = st.session_state.get("user_permissions", ["view"])
permissions = get_user_permissions(user_role, user_permissions)

tabs = st.tabs(APP_CONFIG["CUSTOM_TABS"])

# Tab: فحص السيرفيس
with tabs[0]:
    st.header("📊 فحص السيرفيس")
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            card_num = st.number_input("رقم الماكينة:", min_value=1, step=1, key="card_num_service")
        with col2:
            current_tons = st.number_input("عدد الأطنان الحالية:", min_value=0, step=100, key="current_tons_service")
        if st.button("عرض حالة السيرفيس", key="show_service"):
            # نقرأ الملف مباشرة ونعرض النتائج (بدون تخزين النتائج في session_state)
            check_service_status(card_num, current_tons)

# Tab: تعديل وإدارة البيانات
if permissions["can_edit"]:
    with tabs[1]:
        st.header("🛠 تعديل وإدارة البيانات")
        if sheets_edit is None:
            st.warning("❗ الملف المحلي غير موجود. اضغط تحديث من GitHub في الشريط الجانبي أولًا.")
        else:
            tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
                "عرض وتعديل شيت", "إضافة صف جديد", "إضافة عمود جديد",
                "🆕 إضافة شيت جديد", "➕ إضافة حدث جديد مع صور",
                "✏ تعديل الحدث والصور", "📷 إدارة الصور"
            ])
            with tab1:
                if st.session_state.get("save_all_requested", False):
                    st.info("💾 جاري حفظ جميع التغييرات...")
                    st.session_state["save_all_requested"] = False
                sheets_edit = edit_sheet_with_save_button(sheets_edit)
                st.session_state['sheets_edit'] = sheets_edit
            with tab2:
                st.subheader("➕ إضافة صف جديد")
                sheet_name_add = st.selectbox("اختر الشيت لإضافة صف:", list(sheets_edit.keys()), key="add_sheet")
                df_add = sheets_edit[sheet_name_add].astype(str).reset_index(drop=True)
                st.markdown("أدخل بيانات الصف الجديد:")
                new_data = {}
                cols = st.columns(3)
                for i, col in enumerate(df_add.columns):
                    with cols[i % 3]:
                        new_data[col] = st.text_input(f"{col}", key=f"add_{sheet_name_add}_{col}")
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("💾 إضافة الصف الجديد", key=f"add_row_{sheet_name_add}", type="primary"):
                        new_row_df = pd.DataFrame([new_data]).astype(str)
                        df_new = pd.concat([df_add, new_row_df], ignore_index=True)
                        sheets_edit[sheet_name_add] = df_new.astype(object)
                        if st.session_state.get("user_role") != "admin":
                            add_notification(username=st.session_state.get("username", "غير معروف"), action="إضافة صف جديد",
                                             details=f"تمت إضافة صف جديد في شيت '{sheet_name_add}'",
                                             target_sheet=sheet_name_add, target_row=len(df_new) - 1)
                        new_sheets = auto_save_to_github(sheets_edit, f"إضافة صف جديد في {sheet_name_add}")
                        if new_sheets is not None:
                            sheets_edit = new_sheets
                            st.session_state['sheets_edit'] = sheets_edit
                            st.success("✅ تم إضافة الصف الجديد بنجاح!")
                            st.rerun()
                with col_btn2:
                    if st.button("🗑 مسح الحقول", key=f"clear_{sheet_name_add}"):
                        st.rerun()
            with tab3:
                st.subheader("🆕 إضافة عمود جديد")
                sheet_name_col = st.selectbox("اختر الشيت لإضافة عمود:", list(sheets_edit.keys()), key="add_col_sheet")
                df_col = sheets_edit[sheet_name_col].astype(str)
                new_col_name = st.text_input("اسم العمود الجديد:", key="new_col_name")
                default_value = st.text_input("القيمة الافتراضية لكل الصفوف (اختياري):", "", key="default_value")
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("💾 إضافة العمود الجديد", key=f"add_col_{sheet_name_col}", type="primary"):
                        if new_col_name:
                            df_col[new_col_name] = default_value
                            sheets_edit[sheet_name_col] = df_col.astype(object)
                            if st.session_state.get("user_role") != "admin":
                                add_notification(username=st.session_state.get("username", "غير معروف"), action="إضافة عمود جديد",
                                                 details=f"تمت إضافة عمود جديد '{new_col_name}' إلى شيت '{sheet_name_col}'",
                                                 target_sheet=sheet_name_col)
                            new_sheets = auto_save_to_github(sheets_edit, f"إضافة عمود جديد '{new_col_name}' إلى {sheet_name_col}")
                            if new_sheets is not None:
                                sheets_edit = new_sheets
                                st.session_state['sheets_edit'] = sheets_edit
                                st.success("✅ تم إضافة العمود الجديد بنجاح!")
                                st.rerun()
                        else:
                            st.warning("⚠ الرجاء إدخال اسم العمود الجديد.")
                with col_btn2:
                    if st.button("🗑 مسح", key=f"clear_col_{sheet_name_col}"):
                        st.rerun()
            with tab4:
                add_new_sheet(sheets_edit)
            with tab5:
                add_new_event(sheets_edit)
            with tab6:
                edit_events_and_corrections(sheets_edit)
            with tab7:
                st.subheader("📷 إدارة الصور المخزنة")
                if os.path.exists(IMAGES_FOLDER):
                    image_files = [f for f in os.listdir(IMAGES_FOLDER) if f.lower().endswith(tuple(APP_CONFIG["ALLOWED_IMAGE_TYPES"]))]
                    if image_files:
                        st.info(f"عدد الصور المخزنة: {len(image_files)}")
                        search_term = st.text_input("🔍 بحث عن صور:", placeholder="ابحث باسم الصورة")
                        filtered_images = image_files
                        if search_term:
                            filtered_images = [img for img in image_files if search_term.lower() in img.lower()]
                            st.caption(f"تم العثور على {len(filtered_images)} صورة")
                        images_per_page = 9
                        if "image_page" not in st.session_state:
                            st.session_state.image_page = 0
                        total_pages = (len(filtered_images) + images_per_page - 1) // images_per_page
                        if filtered_images:
                            col_nav1, col_nav2, col_nav3 = st.columns([1, 2, 1])
                            with col_nav1:
                                if st.button("⏪ السابق", disabled=st.session_state.image_page == 0):
                                    st.session_state.image_page = max(0, st.session_state.image_page - 1)
                                    st.rerun()
                            with col_nav2:
                                st.caption(f"الصفحة {st.session_state.image_page + 1} من {total_pages}")
                            with col_nav3:
                                if st.button("التالي ⏩", disabled=st.session_state.image_page == total_pages - 1):
                                    st.session_state.image_page = min(total_pages - 1, st.session_state.image_page + 1)
                                    st.rerun()
                            start_idx = st.session_state.image_page * images_per_page
                            end_idx = min(start_idx + images_per_page, len(filtered_images))
                            for i in range(start_idx, end_idx, 3):
                                cols = st.columns(3)
                                for j in range(3):
                                    idx = i + j
                                    if idx < end_idx:
                                        with cols[j]:
                                            img_file = filtered_images[idx]
                                            img_path = os.path.join(IMAGES_FOLDER, img_file)
                                            try:
                                                st.image(img_path, caption=img_file, use_column_width=True)
                                                if st.button(f"🗑 حذف", key=f"delete_{img_file}"):
                                                    if delete_image_file(img_file):
                                                        st.success(f"✅ تم حذف {img_file}")
                                                        st.rerun()
                                                    else:
                                                        st.error(f"❌ فشل حذف {img_file}")
                                            except:
                                                st.write(f"📷 {img_file}")
                                                st.caption("⚠ لا يمكن عرض الصورة")
                    else:
                        st.info("ℹ️ لا توجد صور مخزنة بعد")
                else:
                    st.warning(f"⚠ مجلد الصور {IMAGES_FOLDER} غير موجود")
else:
    st.info("⛔ ليس لديك صلاحية لتعديل البيانات. يرجى الاتصال بالمسؤول.")
