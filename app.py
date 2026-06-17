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
# ⚙ إعدادات التطبيق - يمكن تعديلها بسهولة
# ===============================
APP_CONFIG = {
    # إعدادات التطبيق العامة
    "APP_TITLE": "CMMS -سيرفيس تحضيرات بيل يارن 11",
    "APP_ICON": "🏭",
    
    # إعدادات GitHub
    "REPO_NAME": "mahmedabdallh123/servise-card",
    "BRANCH": "main",
    "FILE_PATH": "l4.xlsx",
    "LOCAL_FILE": "l4.xlsx",
    
    # إعدادات الأمان
    "MAX_ACTIVE_USERS": 2,
    "SESSION_DURATION_MINUTES": 15,
    
    # إعدادات الواجهة
    "SHOW_TECH_SUPPORT_TO_ALL": False,
    "CUSTOM_TABS": ["📊 فحص السيرفيس", "🛠 تعديل وإدارة البيانات", "🛠 الصيانة الوقائية"],
    
    # إعدادات الصور
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

# إنشاء رابط GitHub تلقائياً من الإعدادات
GITHUB_EXCEL_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['FILE_PATH']}"

# -------------------------------
# 🧩 دوال مساعدة للصور
# -------------------------------
def setup_images_folder():
    """إنشاء وإعداد مجلد الصور"""
    if not os.path.exists(IMAGES_FOLDER):
        os.makedirs(IMAGES_FOLDER)
        with open(os.path.join(IMAGES_FOLDER, ".gitkeep"), "w") as f:
            pass
        st.info(f"📁 تم إنشاء مجلد الصور: {IMAGES_FOLDER}")

def save_uploaded_images(uploaded_files):
    """حفظ الصور المرفوعة وإرجاع أسماء الملفات"""
    if not uploaded_files:
        return []
    
    saved_files = []
    for uploaded_file in uploaded_files:
        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension not in APP_CONFIG["ALLOWED_IMAGE_TYPES"]:
            st.warning(f"⚠ تم تجاهل الملف {uploaded_file.name} لأن نوعه غير مدعوم")
            continue
        
        file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
        if file_size_mb > APP_CONFIG["MAX_IMAGE_SIZE_MB"]:
            st.warning(f"⚠ تم تجاهل الملف {uploaded_file.name} لأن حجمه ({file_size_mb:.2f}MB) يتجاوز الحد المسموح ({APP_CONFIG['MAX_IMAGE_SIZE_MB']}MB)")
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
        pass
    return False

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
    images_per_row = 3
    images = image_filenames.split(',') if isinstance(image_filenames, str) else image_filenames
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
# 🧩 دوال مساعدة للملفات والحالة
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
                if username == "admin":
                    user_data["role"] = "admin"
                    user_data["permissions"] = ["all"]
                else:
                    user_data["role"] = "viewer"
                    user_data["permissions"] = ["view"]
            
            if "permissions" not in user_data:
                if user_data.get("role") == "admin":
                    user_data["permissions"] = ["all"]
                elif user_data.get("role") == "editor":
                    user_data["permissions"] = ["view", "edit"]
                else:
                    user_data["permissions"] = ["view"]
                    
            if "created_at" not in user_data:
                user_data["created_at"] = datetime.now().isoformat()
        
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
        
        return users
    except Exception as e:
        st.error(f"❌ خطأ في ملف users.json: {e}")
        return {
            "admin": {
                "password": "admin123", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"]
            }
        }

def save_users(users):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"❌ خطأ في حفظ ملف users.json: {e}")
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
                if username_input == "admin":
                    pass
                elif username_input in active_users:
                    st.warning("⚠ هذا المستخدم مسجل دخول بالفعل.")
                    return False
                elif active_count >= MAX_ACTIVE_USERS:
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
        try:
            st.cache_data.clear()
        except:
            pass
        return True
    except Exception as e:
        st.error(f"⚠ فشل تحميل الملف من GitHub: {e}")
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
    except Exception as e:
        return None

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

    try:
        st.cache_data.clear()
    except:
        pass

    token = st.secrets.get("github", {}).get("token", None)
    if not token:
        st.warning("⚠ لم يتم العثور على GitHub token. سيتم الحفظ محلياً فقط.")
        return load_sheets_for_edit()

    if not GITHUB_AVAILABLE:
        st.warning("⚠ PyGithub غير متوفر. سيتم الحفظ محلياً فقط.")
        return load_sheets_for_edit()

    try:
        g = Github(token)
        repo = g.get_repo(APP_CONFIG["REPO_NAME"])
        with open(APP_CONFIG["LOCAL_FILE"], "rb") as f:
            content = f.read()

        try:
            contents = repo.get_contents(APP_CONFIG["FILE_PATH"], ref=APP_CONFIG["BRANCH"])
            result = repo.update_file(path=APP_CONFIG["FILE_PATH"], message=commit_message, content=content, sha=contents.sha, branch=APP_CONFIG["BRANCH"])
            st.success(f"✅ تم الحفظ والرفع إلى GitHub بنجاح: {commit_message}")
            return load_sheets_for_edit()
        except Exception as e:
            try:
                result = repo.create_file(path=APP_CONFIG["FILE_PATH"], message=commit_message, content=content, branch=APP_CONFIG["BRANCH"])
                st.success(f"✅ تم إنشاء ملف جديد على GitHub: {commit_message}")
                return load_sheets_for_edit()
            except Exception as create_error:
                st.error(f"❌ فشل إنشاء ملف جديد على GitHub: {create_error}")
                return None

    except Exception as e:
        st.error(f"❌ فشل الرفع إلى GitHub: {e}")
        return None

def auto_save_to_github(sheets_dict, operation_description):
    username = st.session_state.get("username", "unknown")
    commit_message = f"{operation_description} by {username} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    result = save_local_excel_and_push(sheets_dict, commit_message)
    if result is not None:
        st.success("✅ تم حفظ التغييرات تلقائياً في GitHub")
        return result
    else:
        st.error("❌ فشل الحفظ التلقائي")
        return sheets_dict

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

def get_user_permissions(user_role, user_permissions):
    if user_role == "admin":
        return {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": False,
            "can_see_tech_support": False
        }
    elif user_role == "editor":
        return {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": False,
            "can_see_tech_support": False
        }
    else:
        return {
            "can_view": "view" in user_permissions or "edit" in user_permissions or "all" in user_permissions,
            "can_edit": "edit" in user_permissions or "all" in user_permissions,
            "can_manage_users": False,
            "can_see_tech_support": False
        }

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

# -------------------------------
# 🆕 دوال الصيانة الوقائية الجديدة
# -------------------------------

def initialize_machine_data_sheet(sheets_edit):
    """إنشاء ورقة MachineData إذا لم تكن موجودة"""
    if "MachineData" not in sheets_edit:
        df = pd.DataFrame(columns=[
            "Card_Number", "Current_Tons", "Production_Speed_tons_per_hour",
            "Last_Update", "Last_Tons_Recorded"
        ])
        sheets_edit["MachineData"] = df
        sheets_edit = auto_save_to_github(sheets_edit, "تهيئة ورقة MachineData")
    return sheets_edit

def initialize_service_log_sheet(sheets_edit):
    """إنشاء ورقة ServiceLog إذا لم تكن موجودة"""
    if "ServiceLog" not in sheets_edit:
        df = pd.DataFrame(columns=[
            "Card_Number", "Slice_Min_Tons", "Slice_Max_Tons", 
            "Service_Name", "Execution_Date", "Performed_By", "Notes"
        ])
        sheets_edit["ServiceLog"] = df
        sheets_edit = auto_save_to_github(sheets_edit, "تهيئة ورقة ServiceLog")
    return sheets_edit

def get_all_machine_numbers(sheets_edit):
    """استخراج أرقام الماكينات من شيتات CardX_Services أو من MachineData"""
    machine_numbers = set()
    # أولاً من MachineData
    if "MachineData" in sheets_edit:
        md = sheets_edit["MachineData"]
        if not md.empty and "Card_Number" in md.columns:
            machine_numbers.update(md["Card_Number"].dropna().astype(int).tolist())
    # ثم من شيتات CardX_Services
    for sheet_name in sheets_edit.keys():
        if sheet_name.startswith("Card") and "_Services" in sheet_name:
            try:
                num = int(sheet_name.split("_")[0].replace("Card", ""))
                machine_numbers.add(num)
            except:
                pass
    return sorted(machine_numbers)

def get_machine_data(sheets_edit, card_num):
    """استرجاع بيانات الماكينة من MachineData (إن وجدت) أو إنشاء سجل جديد"""
    if "MachineData" not in sheets_edit:
        sheets_edit = initialize_machine_data_sheet(sheets_edit)
    df = sheets_edit["MachineData"]
    if df.empty or "Card_Number" not in df.columns:
        # إنشاء سجل جديد
        new_row = pd.DataFrame([{
            "Card_Number": card_num,
            "Current_Tons": 0.0,
            "Production_Speed_tons_per_hour": 0.08,  # 80 كجم = 0.08 طن/ساعة افتراضياً
            "Last_Update": datetime.now(),
            "Last_Tons_Recorded": 0.0
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        sheets_edit["MachineData"] = df
        sheets_edit = auto_save_to_github(sheets_edit, f"إنشاء بيانات ماكينة {card_num}")
        return sheets_edit, new_row.iloc[0].to_dict()
    
    mask = df["Card_Number"] == card_num
    if mask.any():
        return sheets_edit, df[mask].iloc[0].to_dict()
    else:
        new_row = pd.DataFrame([{
            "Card_Number": card_num,
            "Current_Tons": 0.0,
            "Production_Speed_tons_per_hour": 0.08,
            "Last_Update": datetime.now(),
            "Last_Tons_Recorded": 0.0
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        sheets_edit["MachineData"] = df
        sheets_edit = auto_save_to_github(sheets_edit, f"إضافة ماكينة {card_num}")
        return sheets_edit, new_row.iloc[0].to_dict()

def update_machine_tons(sheets_edit, card_num, new_tons, performed_by=None):
    """تحديث الأطنان الحالية للماكينة مع تسجيل الخدمات المستحقة تلقائياً"""
    if "MachineData" not in sheets_edit:
        sheets_edit = initialize_machine_data_sheet(sheets_edit)
    df = sheets_edit["MachineData"]
    mask = df["Card_Number"] == card_num
    if not mask.any():
        # إنشاء سجل جديد
        new_row = pd.DataFrame([{
            "Card_Number": card_num,
            "Current_Tons": new_tons,
            "Production_Speed_tons_per_hour": 0.08,
            "Last_Update": datetime.now(),
            "Last_Tons_Recorded": new_tons
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        sheets_edit["MachineData"] = df
        sheets_edit = auto_save_to_github(sheets_edit, f"تحديث أطنان ماكينة {card_num} إلى {new_tons}")
        return sheets_edit
    
    old_tons = df.loc[mask, "Current_Tons"].values[0]
    df.loc[mask, "Current_Tons"] = new_tons
    df.loc[mask, "Last_Update"] = datetime.now()
    df.loc[mask, "Last_Tons_Recorded"] = new_tons
    sheets_edit["MachineData"] = df
    
    # التحقق من الوصول إلى نطاقات جديدة وإصدار إشعارات
    check_and_notify_new_slices(sheets_edit, card_num, old_tons, new_tons, performed_by)
    
    sheets_edit = auto_save_to_github(sheets_edit, f"تحديث أطنان ماكينة {card_num} إلى {new_tons}")
    return sheets_edit

def get_service_plan(sheets_edit):
    """استرجاع خطة الخدمات من شيت ServicePlan"""
    if "ServicePlan" not in sheets_edit:
        st.error("❌ لا يوجد شيت ServicePlan في الملف")
        return pd.DataFrame()
    df = sheets_edit["ServicePlan"].copy()
    required_cols = ["Min_Tones", "Max_Tones", "Service"]
    for col in required_cols:
        if col not in df.columns:
            st.error(f"❌ شيت ServicePlan يفتقد العمود {col}")
            return pd.DataFrame()
    # تنظيف البيانات
    df["Min_Tones"] = pd.to_numeric(df["Min_Tones"], errors='coerce')
    df["Max_Tones"] = pd.to_numeric(df["Max_Tones"], errors='coerce')
    df = df.dropna(subset=["Min_Tones", "Max_Tones"])
    return df

def get_executed_services(sheets_edit, card_num, slice_min=None, slice_max=None):
    """استرجاع الخدمات المنفذة مسبقاً لنطاق معين"""
    if "ServiceLog" not in sheets_edit:
        return []
    df = sheets_edit["ServiceLog"]
    if df.empty:
        return []
    mask = df["Card_Number"] == card_num
    if slice_min is not None and slice_max is not None:
        mask &= (df["Slice_Min_Tons"] == slice_min) & (df["Slice_Max_Tons"] == slice_max)
    executed = df[mask]["Service_Name"].tolist()
    return executed

def get_services_for_slice(sheets_edit, slice_min, slice_max):
    """استرجاع الخدمات المطلوبة لنطاق معين من ServicePlan"""
    service_plan = get_service_plan(sheets_edit)
    if service_plan.empty:
        return []
    slice_row = service_plan[(service_plan["Min_Tones"] == slice_min) & (service_plan["Max_Tones"] == slice_max)]
    if slice_row.empty:
        return []
    needed_str = slice_row.iloc[0]["Service"]
    return split_needed_services(needed_str)

def check_and_notify_new_slices(sheets_edit, card_num, old_tons, new_tons, performed_by=None):
    """عند زيادة الأطنان، اكتشاف النطاقات الجديدة التي تم تجاوزها وإصدار إشعارات"""
    service_plan = get_service_plan(sheets_edit)
    if service_plan.empty:
        return
    
    # تحديد النطاقات التي كانت أقل أو تساوي old_tons والتي أصبحت أكبر من old_tons وأقل من أو تساوي new_tons
    new_slices = []
    for _, row in service_plan.iterrows():
        slice_min = row["Min_Tones"]
        slice_max = row["Max_Tones"]
        # إذا كان النطاق لم يتم تجاوزه سابقاً (slice_max > old_tons) وأصبح ضمن الأطنان الجديدة (slice_min <= new_tons)
        if slice_max > old_tons and slice_min <= new_tons:
            # التحقق من أن هذا النطاق لم يتم تنفيذ خدماته من قبل (يمكن تسجيله مرة واحدة)
            executed = get_executed_services(sheets_edit, card_num, slice_min, slice_max)
            required = get_services_for_slice(sheets_edit, slice_min, slice_max)
            # إذا كان هناك خدمات مطلوبة ولم يتم تنفيذها كلها
            if required and set(executed) != set(required):
                new_slices.append((slice_min, slice_max, required, executed))
    
    if new_slices:
        st.session_state["pending_services_notified"] = True
        with st.expander(f"🔔 **إشعار: خدمات جديدة مطلوبة للماكينة {card_num}**", expanded=True):
            for slice_min, slice_max, required, executed in new_slices:
                st.warning(f"**النطاق {slice_min} - {slice_max} طن**")
                not_done = [s for s in required if s not in executed]
                if not_done:
                    st.markdown(f"📋 الخدمات المطلوبة: {', '.join(required)}")
                    st.markdown(f"✅ المنفذة: {', '.join(executed) if executed else 'لا شيء'}")
                    st.markdown(f"⏳ المتبقية: {', '.join(not_done)}")
                    # إمكانية تسجيل الخدمات من هنا (سيتم في الواجهة)
                    st.session_state[f"pending_slice_{card_num}_{slice_min}_{slice_max}"] = not_done
        st.info("📌 يمكنك تسجيل تنفيذ هذه الخدمات من تبويب **الصيانة الوقائية** أسفل قسم 'تسجيل خدمات منفذة'.")

def get_current_slice_info(sheets_edit, card_num, current_tons):
    """الحصول على النطاق الحالي للأطنان"""
    service_plan = get_service_plan(sheets_edit)
    if service_plan.empty:
        return None, None, [], []
    for _, row in service_plan.iterrows():
        if row["Min_Tones"] <= current_tons <= row["Max_Tones"]:
            slice_min = row["Min_Tones"]
            slice_max = row["Max_Tones"]
            required = split_needed_services(row["Service"])
            executed = get_executed_services(sheets_edit, card_num, slice_min, slice_max)
            return slice_min, slice_max, required, executed
    return None, None, [], []

def record_service_execution(sheets_edit, card_num, slice_min, slice_max, service_name, performed_by, notes=""):
    """تسجيل تنفيذ خدمة في ServiceLog"""
    if "ServiceLog" not in sheets_edit:
        sheets_edit = initialize_service_log_sheet(sheets_edit)
    df = sheets_edit["ServiceLog"]
    new_row = pd.DataFrame([{
        "Card_Number": card_num,
        "Slice_Min_Tons": slice_min,
        "Slice_Max_Tons": slice_max,
        "Service_Name": service_name,
        "Execution_Date": datetime.now(),
        "Performed_By": performed_by,
        "Notes": notes
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    sheets_edit["ServiceLog"] = df
    sheets_edit = auto_save_to_github(sheets_edit, f"تسجيل خدمة {service_name} للماكينة {card_num} (نطاق {slice_min}-{slice_max})")
    return sheets_edit

def update_machine_speed(sheets_edit, card_num, new_speed_tons_per_hour):
    """تحديث سرعة الإنتاج للماكينة"""
    if "MachineData" not in sheets_edit:
        sheets_edit = initialize_machine_data_sheet(sheets_edit)
    df = sheets_edit["MachineData"]
    mask = df["Card_Number"] == card_num
    if mask.any():
        df.loc[mask, "Production_Speed_tons_per_hour"] = new_speed_tons_per_hour
    else:
        new_row = pd.DataFrame([{
            "Card_Number": card_num,
            "Current_Tons": 0.0,
            "Production_Speed_tons_per_hour": new_speed_tons_per_hour,
            "Last_Update": datetime.now(),
            "Last_Tons_Recorded": 0.0
        }])
        df = pd.concat([df, new_row], ignore_index=True)
    sheets_edit["MachineData"] = df
    sheets_edit = auto_save_to_github(sheets_edit, f"تحديث سرعة ماكينة {card_num} إلى {new_speed_tons_per_hour} طن/ساعة")
    return sheets_edit

def auto_update_tons_based_on_time(sheets_edit, card_num):
    """تحديث الأطنان تلقائياً بناءً على الوقت المنقضي وسرعة الإنتاج"""
    sheets_edit, machine_data = get_machine_data(sheets_edit, card_num)
    last_update = machine_data.get("Last_Update")
    if last_update is None:
        return sheets_edit, machine_data.get("Current_Tons", 0.0)
    if isinstance(last_update, str):
        last_update = datetime.fromisoformat(last_update)
    now = datetime.now()
    delta_hours = (now - last_update).total_seconds() / 3600.0
    speed = machine_data.get("Production_Speed_tons_per_hour", 0.08)
    additional_tons = delta_hours * speed
    new_tons = machine_data.get("Current_Tons", 0.0) + additional_tons
    sheets_edit = update_machine_tons(sheets_edit, card_num, new_tons, performed_by="Auto")
    return sheets_edit, new_tons

def preventive_maintenance_tab(sheets_edit):
    """تبويب الصيانة الوقائية الجديد"""
    st.header("🛠 الصيانة الوقائية - العداد التصاعدي والإشعارات")
    st.info("هنا يمكنك تتبع الأطنان الحالية لكل ماكينة، تحديثها تلقائياً بناءً على سرعة الإنتاج، وتسجيل الخدمات المطلوبة عند الوصول إلى نطاقات جديدة.")
    
    if sheets_edit is None:
        st.warning("لا توجد بيانات. قم بتحديث الملف من GitHub أولاً.")
        return sheets_edit
    
    # التأكد من وجود الأوراق اللازمة
    sheets_edit = initialize_machine_data_sheet(sheets_edit)
    sheets_edit = initialize_service_log_sheet(sheets_edit)
    
    # قائمة الماكينات
    machine_numbers = get_all_machine_numbers(sheets_edit)
    if not machine_numbers:
        st.warning("⚠ لم يتم العثور على أي ماكينة. تأكد من وجود شيتات CardX_Services في ملف Excel.")
        return sheets_edit
    
    selected_card = st.selectbox("🔢 اختر رقم الماكينة:", machine_numbers, key="pm_card_select")
    
    # استرجاع بيانات الماكينة
    sheets_edit, machine_data = get_machine_data(sheets_edit, selected_card)
    current_tons = machine_data.get("Current_Tons", 0.0)
    speed = machine_data.get("Production_Speed_tons_per_hour", 0.08)
    last_update = machine_data.get("Last_Update")
    
    # عرض المعلومات الحالية
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 الأطنان الحالية", f"{current_tons:.2f} طن")
    with col2:
        st.metric("⚡ سرعة الإنتاج", f"{speed*1000:.0f} كجم/ساعة  ({speed:.3f} طن/ساعة)")
    with col3:
        if last_update:
            if isinstance(last_update, str):
                last_update = datetime.fromisoformat(last_update)
            st.metric("🕒 آخر تحديث", last_update.strftime("%Y-%m-%d %H:%M"))
        else:
            st.metric("🕒 آخر تحديث", "غير معروف")
    
    # تحديث العداد
    st.subheader("🔄 تحديث الأطنان")
    update_method = st.radio("طريقة التحديث:", ["تحديث تلقائي (حسب الوقت المنقضي)", "إدخال يدوي", "إضافة كمية محددة"], horizontal=True, key="update_method")
    
    if update_method == "تحديث تلقائي (حسب الوقت المنقضي)":
        if st.button("📈 تحديث العداد تلقائياً", key="auto_update_btn"):
            with st.spinner("جاري حساب الإنتاج منذ آخر تحديث..."):
                sheets_edit, new_tons = auto_update_tons_based_on_time(sheets_edit, selected_card)
                st.success(f"✅ تم تحديث الأطنان إلى {new_tons:.2f} طن (إضافة {new_tons - current_tons:.2f} طن)")
                st.rerun()
    
    elif update_method == "إدخال يدوي":
        new_manual_tons = st.number_input("أدخل الأطنان الحالية:", min_value=0.0, value=float(current_tons), step=100.0, format="%.2f", key="manual_tons")
        if st.button("💾 تحديث يدوي", key="manual_update_btn"):
            if new_manual_tons != current_tons:
                sheets_edit = update_machine_tons(sheets_edit, selected_card, new_manual_tons, performed_by=st.session_state.get("username", "manual"))
                st.success(f"✅ تم تحديث الأطنان إلى {new_manual_tons:.2f} طن")
                st.rerun()
            else:
                st.info("لم يتم تغيير القيمة.")
    
    else:  # إضافة كمية محددة
        additional_tons = st.number_input("كمية إضافية (طن):", min_value=0.0, step=10.0, format="%.2f", key="add_tons")
        if st.button("➕ إضافة كمية", key="add_tons_btn"):
            new_tons = current_tons + additional_tons
            sheets_edit = update_machine_tons(sheets_edit, selected_card, new_tons, performed_by=st.session_state.get("username", "add"))
            st.success(f"✅ تمت إضافة {additional_tons:.2f} طن -> الإجمالي {new_tons:.2f} طن")
            st.rerun()
    
    # تعديل سرعة الإنتاج
    st.subheader("⚙ تعديل سرعة الإنتاج")
    new_speed_kg = st.number_input("سرعة الإنتاج (كجم/ساعة):", min_value=0, value=int(speed*1000), step=10, key="speed_kg")
    new_speed_tons = new_speed_kg / 1000.0
    if st.button("💾 حفظ السرعة", key="save_speed"):
        sheets_edit = update_machine_speed(sheets_edit, selected_card, new_speed_tons)
        st.success(f"✅ تم تحديث سرعة الإنتاج إلى {new_speed_kg} كجم/ساعة")
        st.rerun()
    
    # عرض النطاق الحالي والخدمات
    st.subheader("📌 النطاق الحالي والخدمات المطلوبة")
    slice_min, slice_max, required_services, executed_services = get_current_slice_info(sheets_edit, selected_card, current_tons)
    if slice_min is not None:
        st.info(f"**النطاق الحالي:** {slice_min} - {slice_max} طن")
        if required_services:
            st.markdown("**📋 الخدمات المطلوبة في هذا النطاق:**")
            for svc in required_services:
                if svc in executed_services:
                    st.success(f"✅ {svc} (تم تنفيذه)")
                else:
                    st.warning(f"⚠️ {svc} (لم ينفذ بعد)")
        else:
            st.success("✅ لا توجد خدمات مطلوبة في هذا النطاق.")
    else:
        st.warning("⚠ لم يتم العثور على نطاق يتطابق مع الأطنان الحالية. تأكد من وجود خطة خدمة مناسبة.")
    
    # تسجيل خدمة جديدة
    st.subheader("📝 تسجيل خدمة منفذة")
    # الحصول على جميع الخدمات المطلوبة في النطاق الحالي والتي لم تنفذ بعد
    pending_services = []
    if slice_min is not None and required_services:
        for svc in required_services:
            if svc not in executed_services:
                pending_services.append(svc)
    
    if pending_services:
        service_to_record = st.selectbox("اختر الخدمة التي تم تنفيذها:", pending_services, key="record_service_select")
        performed_by = st.text_input("اسم الفني المنفذ:", value=st.session_state.get("username", ""), key="record_performed_by")
        notes = st.text_area("ملاحظات (اختياري):", key="record_notes")
        if st.button("✅ تسجيل تنفيذ الخدمة", key="record_service_btn"):
            if not performed_by:
                st.error("❌ الرجاء إدخال اسم الفني المنفذ.")
            else:
                sheets_edit = record_service_execution(sheets_edit, selected_card, slice_min, slice_max, service_to_record, performed_by, notes)
                st.success(f"✅ تم تسجيل تنفيذ الخدمة '{service_to_record}'")
                st.rerun()
    else:
        st.info("ℹ️ لا توجد خدمات معلقة في النطاق الحالي.")
    
    # عرض سجل الخدمات السابقة لهذه الماكينة
    st.subheader("📜 سجل الخدمات المنفذة (لكل النطاقات)")
    if "ServiceLog" in sheets_edit:
        log_df = sheets_edit["ServiceLog"]
        if not log_df.empty and "Card_Number" in log_df.columns:
            card_log = log_df[log_df["Card_Number"] == selected_card].copy()
            if not card_log.empty:
                # تحويل التواريخ للعرض
                if "Execution_Date" in card_log.columns:
                    card_log["Execution_Date"] = pd.to_datetime(card_log["Execution_Date"]).dt.strftime("%Y-%m-%d %H:%M")
                st.dataframe(card_log[["Slice_Min_Tons", "Slice_Max_Tons", "Service_Name", "Execution_Date", "Performed_By", "Notes"]], use_container_width=True)
            else:
                st.info("لا توجد خدمات مسجلة لهذه الماكينة بعد.")
        else:
            st.info("لا توجد خدمات مسجلة بعد.")
    else:
        st.info("لا توجد خدمات مسجلة بعد.")
    
    return sheets_edit

# -------------------------------
# 🖥 دالة تعديل الشيت مع زر حفظ يدوي
# -------------------------------
def edit_sheet_with_save_button(sheets_edit):
    """تعديل بيانات الشيت مع زر حفظ يدوي"""
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
                new_sheets = auto_save_to_github(sheets_edit, f"تعديل يدوي في شيت {sheet_name}")
                if new_sheets is not None:
                    sheets_edit = new_sheets
                    st.session_state.unsaved_changes[sheet_name] = False
                    st.success(f"✅ تم حفظ التغييرات في شيت {sheet_name} بنجاح!")
                    st.session_state.original_sheets[sheet_name] = edited_df.copy()
                    time.sleep(1)
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
def check_service_status(card_num, current_tons, all_sheets):
    """فحص حالة السيرفيس فقط"""
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    if "ServicePlan" not in all_sheets:
        st.error("❌ الملف لا يحتوي على شيت ServicePlan.")
        return
    
    service_plan_df = all_sheets["ServicePlan"]
    card_services_sheet_name = f"Card{card_num}_Services"
    
    if card_services_sheet_name not in all_sheets:
        card_old_sheet_name = f"Card{card_num}"
        if card_old_sheet_name in all_sheets:
            card_df = all_sheets[card_old_sheet_name]
            services_df = card_df[
                (card_df.get("Min_Tones", pd.NA).notna()) & 
                (card_df.get("Max_Tones", pd.NA).notna()) &
                (card_df.get("Min_Tones", "") != "") & 
                (card_df.get("Max_Tones", "") != "")
            ].copy()
        else:
            st.warning(f"⚠ لا يوجد شيت باسم {card_services_sheet_name} أو {card_old_sheet_name}")
            return
    else:
        card_df = all_sheets[card_services_sheet_name]
        services_df = card_df.copy()

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

        if "Min_Tones" in services_df.columns and "Max_Tones" in services_df.columns:
            mask = (services_df["Min_Tones"].fillna(0) <= slice_max) & (services_df["Max_Tones"].fillna(0) >= slice_min)
        elif "Min_Tones" in services_df.columns:
            mask = (services_df["Min_Tones"].fillna(0) <= slice_max) & (services_df["Min_Tones"].fillna(0) >= slice_min)
        elif "Max_Tones" in services_df.columns:
            mask = (services_df["Max_Tones"].fillna(0) <= slice_max) & (services_df["Max_Tones"].fillna(0) >= slice_min)
        else:
            if "Tones" in services_df.columns:
                mask = services_df["Tones"].notna()
            else:
                mask = pd.Series([True] * len(services_df), index=services_df.index)
        
        matching_rows = services_df[mask]

        if not matching_rows.empty:
            for _, row in matching_rows.iterrows():
                done_services_set = set()
                
                metadata_columns = {
                    "card", "Tones", "Min_Tones", "Max_Tones", "Date", 
                    "Other", "Servised by", "Event", "Correction", "Images",
                    "Card", "TONES", "MIN_TONES", "MAX_TONES", "DATE",
                    "OTHER", "EVENT", "CORRECTION", "SERVISED BY", "IMAGES",
                    "servised by", "Servised By", 
                    "Serviced by", "Service by", "Serviced By", "Service By",
                    "خدم بواسطة", "تم الخدمة بواسطة", "فني الخدمة",
                    "صور", "الصور", "مرفقات", "المرفقات"
                }
                
                all_columns = set(services_df.columns)
                service_columns = all_columns - metadata_columns
                
                final_service_columns = set()
                for col in service_columns:
                    col_normalized = normalize_name(col)
                    metadata_normalized = {normalize_name(mc) for mc in metadata_columns}
                    if col_normalized not in metadata_normalized:
                        final_service_columns.add(col)
                
                for col in final_service_columns:
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
# 🖥 الواجهة الرئيسية المدمجة
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
    st.markdown("**📷 إدارة الصور:**")
    if os.path.exists(IMAGES_FOLDER):
        image_files = [f for f in os.listdir(IMAGES_FOLDER) if f.lower().endswith(tuple(APP_CONFIG["ALLOWED_IMAGE_TYPES"]))]
        st.caption(f"عدد الصور: {len(image_files)}")
    st.markdown("---")
    if st.button("🚪 تسجيل الخروج", key="logout_btn"):
        logout_action()

all_sheets = load_all_sheets()
sheets_edit = load_sheets_for_edit()

st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")

username = st.session_state.get("username")
user_role = st.session_state.get("user_role", "viewer")
user_permissions = st.session_state.get("user_permissions", ["view"])
permissions = get_user_permissions(user_role, user_permissions)

# بناء التبويبات حسب الصلاحيات
tabs_list = ["📊 فحص السيرفيس"]
if permissions["can_edit"]:
    tabs_list.append("🛠 تعديل وإدارة البيانات")
    tabs_list.append("🛠 الصيانة الوقائية")  # التبويب الجديد

tabs = st.tabs(tabs_list)

# تبويب فحص السيرفيس (موجود مسبقاً)
with tabs[0]:
    st.header("📊 فحص السيرفيس")
    if all_sheets is None:
        st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
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

# تبويب تعديل البيانات (إذا كان مسموحاً)
if permissions["can_edit"] and len(tabs) > 1:
    with tabs[1]:
        st.header("🛠 تعديل وإدارة البيانات")
        if sheets_edit is None:
            st.warning("❗ الملف المحلي غير موجود. اضغط تحديث من GitHub في الشريط الجانبي أولًا.")
        else:
            tab1, tab2, tab3 = st.tabs(["عرض وتعديل شيت", "إضافة صف جديد", "إضافة عمود جديد"])
            with tab1:
                if st.session_state.get("save_all_requested", False):
                    st.info("💾 جاري حفظ جميع التغييرات...")
                    st.session_state["save_all_requested"] = False
                sheets_edit = edit_sheet_with_save_button(sheets_edit)
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
                        new_sheets = auto_save_to_github(sheets_edit, f"إضافة صف جديد في {sheet_name_add}")
                        if new_sheets is not None:
                            sheets_edit = new_sheets
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
                            new_sheets = auto_save_to_github(sheets_edit, f"إضافة عمود جديد '{new_col_name}' إلى {sheet_name_col}")
                            if new_sheets is not None:
                                sheets_edit = new_sheets
                                st.success("✅ تم إضافة العمود الجديد بنجاح!")
                                st.rerun()
                        else:
                            st.warning("⚠ الرجاء إدخال اسم العمود الجديد.")
                with col_btn2:
                    if st.button("🗑 مسح", key=f"clear_col_{sheet_name_col}"):
                        st.rerun()

# تبويب الصيانة الوقائية الجديد (إذا كان مسموحاً بالتحرير)
if permissions["can_edit"] and len(tabs) > 2:
    with tabs[2]:
        sheets_edit = preventive_maintenance_tab(sheets_edit)
