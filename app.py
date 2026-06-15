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
    "APP_TITLE": "CMMS - bel",
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
    "CUSTOM_TABS": ["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن", "🛠 تعديل وإدارة البيانات", "👥 إدارة المستخدمين", "📞 الدعم الفني"]
}

# ===============================
# 🗂 إعدادات الملفات
# ===============================
USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=APP_CONFIG["SESSION_DURATION_MINUTES"])
MAX_ACTIVE_USERS = APP_CONFIG["MAX_ACTIVE_USERS"]

# إنشاء رابط GitHub تلقائياً من الإعدادات
GITHUB_EXCEL_URL = f"https://github.com/{APP_CONFIG['REPO_NAME'].split('/')[0]}/{APP_CONFIG['REPO_NAME'].split('/')[1]}/raw/{APP_CONFIG['BRANCH']}/{APP_CONFIG['FILE_PATH']}"

# -------------------------------
# 🧩 دوال مساعدة للملفات والحالة
# -------------------------------
def load_users():
    """تحميل بيانات المستخدمين من ملف JSON"""
    if not os.path.exists(USERS_FILE):
        # إنشاء مستخدمين افتراضيين مع الصلاحيات المطلوبة
        default_users = {
            "admin": {
                "password": "admin123", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"]
            },
            "user1": {
                "password": "user1123", 
                "role": "editor", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["view", "edit"]
            },
            "user2": {
                "password": "user2123", 
                "role": "viewer", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["view"]
            }
        }
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_users, f, indent=4, ensure_ascii=False)
        return default_users
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
            # التأكد من وجود جميع الحقول المطلوبة لكل مستخدم
            for username, user_data in users.items():
                if "role" not in user_data:
                    # تحديد الدور بناءً على اسم المستخدم إذا لم يكن موجوداً
                    if username == "admin":
                        user_data["role"] = "admin"
                        user_data["permissions"] = ["all"]
                    else:
                        user_data["role"] = "viewer"
                        user_data["permissions"] = ["view"]
                
                if "permissions" not in user_data:
                    # تعيين الصلاحيات الافتراضية بناءً على الدور
                    if user_data["role"] == "admin":
                        user_data["permissions"] = ["all"]
                    elif user_data["role"] == "editor":
                        user_data["permissions"] = ["view", "edit"]
                    else:
                        user_data["permissions"] = ["view"]
                        
                if "created_at" not in user_data:
                    user_data["created_at"] = datetime.now().isoformat()
                    
            return users
    except Exception as e:
        st.error(f"❌ خطأ في ملف users.json: {e}")
        # إرجاع المستخدمين الافتراضيين في حالة الخطأ
        return {
            "admin": {
                "password": "admin123", 
                "role": "admin", 
                "created_at": datetime.now().isoformat(),
                "permissions": ["all"]
            }
        }

def save_users(users):
    """حفظ بيانات المستخدمين إلى ملف JSON"""
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

# -------------------------------
# 🔐 تسجيل الخروج
# -------------------------------
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
# 🧠 واجهة تسجيل الدخول
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

    # تحميل قائمة المستخدمين مباشرة من الملف
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            current_users = json.load(f)
        user_list = list(current_users.keys())
    except:
        user_list = list(users.keys())

    # اختيار المستخدم
    username_input = st.selectbox("👤 اختر المستخدم", user_list)
    password = st.text_input("🔑 كلمة المرور", type="password")

    active_users = [u for u, v in state.items() if v.get("active")]
    active_count = len(active_users)
    st.caption(f"🔒 المستخدمون النشطون الآن: {active_count} / {MAX_ACTIVE_USERS}")

    if not st.session_state.logged_in:
        if st.button("تسجيل الدخول"):
            # تحميل المستخدمين من جديد للتأكد من أحدث بيانات
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

# -------------------------------
# 🔄 طرق جلب الملف من GitHub
# -------------------------------
def fetch_from_github_requests():
    """تحميل بإستخدام رابط RAW (requests)"""
    try:
        response = requests.get(GITHUB_EXCEL_URL, stream=True, timeout=15)
        response.raise_for_status()
        with open(APP_CONFIG["LOCAL_FILE"], "wb") as f:
            shutil.copyfileobj(response.raw, f)
        # امسح الكاش
        try:
            st.cache_data.clear()
        except:
            pass
        return True
    except Exception as e:
        st.error(f"⚠ فشل التحديث من GitHub: {e}")
        return False

def fetch_from_github_api():
    """تحميل عبر GitHub API (باستخدام PyGithub token في secrets)"""
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

# -------------------------------
# 📂 تحميل الشيتات (مخبأ) - معدل لقراءة جميع الشيتات
# -------------------------------
@st.cache_data(show_spinner=False)
def load_all_sheets():
    """تحميل جميع الشيتات من ملف Excel"""
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        return None
    
    try:
        # قراءة جميع الشيتات
        sheets = pd.read_excel(APP_CONFIG["LOCAL_FILE"], sheet_name=None)
        
        if not sheets:
            return None
        
        # تنظيف أسماء الأعمدة لكل شيت
        for name, df in sheets.items():
            df.columns = df.columns.astype(str).str.strip()
        
        return sheets
    except Exception as e:
        return None

# نسخة مع dtype=object لواجهة التحرير
@st.cache_data(show_spinner=False)
def load_sheets_for_edit():
    """تحميل جميع الشيتات للتحرير"""
    if not os.path.exists(APP_CONFIG["LOCAL_FILE"]):
        return None
    
    try:
        # قراءة جميع الشيتات مع dtype=object للحفاظ على تنسيق البيانات
        sheets = pd.read_excel(APP_CONFIG["LOCAL_FILE"], sheet_name=None, dtype=object)
        
        if not sheets:
            return None
        
        # تنظيف أسماء الأعمدة لكل شيت
        for name, df in sheets.items():
            df.columns = df.columns.astype(str).str.strip()
        
        return sheets
    except Exception as e:
        return None

# -------------------------------
# 🔁 حفظ محلي + رفع على GitHub + مسح الكاش + إعادة تحميل
# -------------------------------
def save_local_excel_and_push(sheets_dict, commit_message="Update from Streamlit"):
    """دالة محسنة للحفظ التلقائي المحلي والرفع إلى GitHub"""
    # احفظ محلياً
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

    # امسح الكاش
    try:
        st.cache_data.clear()
    except:
        pass

    # حاول الرفع عبر PyGithub token في secrets
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
            # حاول رفع كملف جديد أو إنشاء
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
    """دالة الحفظ التلقائي المحسنة"""
    username = st.session_state.get("username", "unknown")
    commit_message = f"{operation_description} by {username} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    result = save_local_excel_and_push(sheets_dict, commit_message)
    if result is not None:
        st.success("✅ تم حفظ التغييرات تلقائياً في GitHub")
        return result
    else:
        st.error("❌ فشل الحفظ التلقائي")
        return sheets_dict

# -------------------------------
# 🧰 دوال مساعدة للمعالجة والنصوص
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
        "Card Number": "background-color: #ebdef0; color:#4a235a; font-weight:bold;"
    }
    return color_map.get(col_name, "")

def style_table(row):
    return [highlight_cell(row[col], col) for col in row.index]

def get_user_permissions(user_role, user_permissions):
    """الحصول على صلاحيات المستخدم بناءً على الدور والصلاحيات"""
    # إذا كان الدور admin، يعطى جميع الصلاحيات
    if user_role == "admin":
        return {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": True,
            "can_see_tech_support": True
        }
    
    # إذا كان الدور editor
    elif user_role == "editor":
        return {
            "can_view": True,
            "can_edit": True,
            "can_manage_users": False,
            "can_see_tech_support": False
        }
    
    # إذا كان الدور viewer أو أي دور آخر
    else:
        # التحقق من الصلاحيات الفردية
        return {
            "can_view": "view" in user_permissions or "edit" in user_permissions or "all" in user_permissions,
            "can_edit": "edit" in user_permissions or "all" in user_permissions,
            "can_manage_users": "manage_users" in user_permissions or "all" in user_permissions,
            "can_see_tech_support": "tech_support" in user_permissions or "all" in user_permissions
        }

def get_servised_by_value(row):
    """استخراج قيمة فني الخدمة من الصف"""
    # قائمة بالأعمدة المحتملة لفني الخدمة
    servised_columns = [
        "Servised by", "SERVISED BY", "servised by", "Servised By",
        "Serviced by", "Service by", "Serviced By", "Service By",
        "خدم بواسطة", "تم الخدمة بواسطة", "فني الخدمة"
    ]
    
    # البحث في الأعمدة المعروفة
    for col in servised_columns:
        if col in row.index:
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    
    # البحث في جميع الأعمدة التي قد تحتوي على فني الخدمة
    for col in row.index:
        col_normalized = normalize_name(col)
        if any(keyword in col_normalized for keyword in ["servisedby", "servicedby", "serviceby", "خدمبواسطة", "فني"]):
            value = str(row[col]).strip()
            if value and value.lower() not in ["nan", "none", ""]:
                return value
    
    return "-"

# -------------------------------
# 🖥 دالة فحص السيرفيس فقط - من الشيتات الجديدة
# -------------------------------
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
    
    # إذا لم يكن هناك شيت خدمات منفصل، نبحث في الشيت القديم
    if card_services_sheet_name not in all_sheets:
        # محاولة البحث في الشيت القديم
        card_old_sheet_name = f"Card{card_num}"
        if card_old_sheet_name in all_sheets:
            card_df = all_sheets[card_old_sheet_name]
            # فلترة فقط الصفوف التي لها Min_Tones و Max_Tones
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

    # اختيار الشرائح
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
        "service_counts": {},  # تعداد كل خدمة مطلوبة
        "service_done_counts": {},  # تعداد الخدمات المنفذة
        "total_needed_services": 0,
        "total_done_services": 0,
        "by_slice": {}  # إحصائيات حسب الشريحة
    }
    
    for _, current_slice in selected_slices.iterrows():
        slice_min = current_slice["Min_Tones"]
        slice_max = current_slice["Max_Tones"]
        slice_key = f"{slice_min}-{slice_max}"
        
        needed_service_raw = current_slice.get("Service", "")
        needed_parts = split_needed_services(needed_service_raw)
        needed_norm = [normalize_name(p) for p in needed_parts]
        
        # تحديث إحصائيات الخدمات المطلوبة
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

        # البحث في خدمات الماكينة
        mask = (services_df.get("Min_Tones", 0).fillna(0) <= slice_max) & (services_df.get("Max_Tones", 0).fillna(0) >= slice_min)
        matching_rows = services_df[mask]

        if not matching_rows.empty:
            for _, row in matching_rows.iterrows():
                done_services_set = set()
                
                # تحديد الأعمدة التي تحتوي على خدمات منجزة (استبعاد أعمدة البيانات الوصفية)
                metadata_columns = {
                    "card", "Tones", "Min_Tones", "Max_Tones", "Date", 
                    "Other", "Servised by", "Event", "Correction",
                    "Card", "TONES", "MIN_TONES", "MAX_TONES", "DATE",
                    "OTHER", "EVENT", "CORRECTION", "SERVISED BY",
                    "servised by", "Servised By", 
                    "Serviced by", "Service by", "Serviced By", "Service By",
                    "خدم بواسطة", "تم الخدمة بواسطة", "فني الخدمة"
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
                            # تحديث إحصائيات الخدمات المنفذة
                            service_stats["service_done_counts"][col] = service_stats["service_done_counts"].get(col, 0) + 1
                            service_stats["total_done_services"] += 1

                # جمع بيانات السيرفيس فقط
                current_date = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else "-"
                current_tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
                
                # البحث عن فني الخدمة
                servised_by_value = get_servised_by_value(row)
                
                done_services = sorted(list(done_services_set))
                done_norm = [normalize_name(c) for c in done_services]
                
                # تحديث إحصائيات الشريحة
                service_stats["by_slice"][slice_key]["done"].extend(done_services)
                service_stats["by_slice"][slice_key]["total_done"] += len(done_services)
                
                # مقارنة الخدمات المنجزة مع المطلوبة
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
                    "Date": current_date
                })
        else:
            # إذا لم توجد سجلات سيرفيس
            all_results.append({
                "Card Number": card_num,
                "Min_Tons": slice_min,
                "Max_Tons": slice_max,
                "Service Needed": " + ".join(needed_parts) if needed_parts else "-",
                "Service Done": "-",
                "Service Didn't Done": ", ".join(needed_parts) if needed_parts else "-",
                "Tones": "-",
                "Servised by": "-",
                "Date": "-"
            })
            
            # تحديث إحصائيات الشريحة (لا يوجد خدمات منفذة)
            service_stats["by_slice"][slice_key]["not_done"] = needed_parts.copy()

    result_df = pd.DataFrame(all_results).dropna(how="all").reset_index(drop=True)

    st.markdown("### 📋 نتائج فحص السيرفيس")
    if not result_df.empty:
        st.dataframe(result_df.style.apply(style_table, axis=1), use_container_width=True)

        # عرض الإحصائيات والنسب
        show_service_statistics(service_stats, result_df)

        # تنزيل النتائج
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

def show_service_statistics(service_stats, result_df):
    """عرض الإحصائيات والنسب المئوية لفحص السيرفيس"""
    st.markdown("---")
    st.markdown("### 📊 الإحصائيات والنسب المئوية")
    
    if service_stats["total_needed_services"] == 0:
        st.info("ℹ️ لا توجد خدمات مطلوبة في النطاق المحدد.")
        return
    
    # حساب النسبة العامة
    completion_rate = (service_stats["total_done_services"] / service_stats["total_needed_services"]) * 100 if service_stats["total_needed_services"] > 0 else 0
    
    # عرض النسب العامة
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📈 نسبة الإنجاز العامة",
            value=f"{completion_rate:.1f}%",
            delta=f"{service_stats['total_done_services']}/{service_stats['total_needed_services']}"
        )
    
    with col2:
        st.metric(
            label="🔢 عدد الخدمات المطلوبة",
            value=service_stats["total_needed_services"]
        )
    
    with col3:
        st.metric(
            label="✅ الخدمات المنفذة",
            value=service_stats["total_done_services"]
        )
    
    with col4:
        remaining = service_stats["total_needed_services"] - service_stats["total_done_services"]
        st.metric(
            label="⏳ الخدمات المتبقية",
            value=remaining
        )
    
    st.markdown("---")
    
    # تبويبات للإحصائيات التفصيلية
    stat_tabs = st.tabs([
        "📝 إحصائيات الخدمات",
        "📋 توزيع الخدمات",
        "📊 حسب الشريحة"
    ])
    
    with stat_tabs[0]:
        st.markdown("#### 📝 إحصائيات مفصلة لكل خدمة")
        
        # إنشاء DataFrame للإحصائيات
        stat_data = []
        all_services = set(service_stats["service_counts"].keys()).union(
            set(service_stats["service_done_counts"].keys())
        )
        
        for service in sorted(all_services):
            needed_count = service_stats["service_counts"].get(service, 0)
            done_count = service_stats["service_done_counts"].get(service, 0)
            completion_rate_service = (done_count / needed_count * 100) if needed_count > 0 else 0
            
            stat_data.append({
                "الخدمة": service,
                "مطلوبة": needed_count,
                "منفذة": done_count,
                "متبقية": needed_count - done_count,
                "نسبة الإنجاز": f"{completion_rate_service:.1f}%",
                "حالة": "✅ ممتاز" if completion_rate_service >= 90 else 
                       "🟢 جيد" if completion_rate_service >= 70 else 
                       "🟡 متوسط" if completion_rate_service >= 50 else 
                       "🔴 ضعيف"
            })
        
        if stat_data:
            stat_df = pd.DataFrame(stat_data)
            st.dataframe(stat_df, use_container_width=True, height=400)
        else:
            st.info("ℹ️ لا توجد بيانات إحصائية للخدمات.")
    
    with stat_tabs[1]:
        st.markdown("#### 📋 توزيع الخدمات")
        
        if service_stats["service_counts"]:
            # محاولة استخدام plotly إذا كان متاحاً
            try:
                import plotly.express as px
                
                plot_data = []
                for service, needed_count in service_stats["service_counts"].items():
                    done_count = service_stats["service_done_counts"].get(service, 0)
                    
                    plot_data.append({
                        "الخدمة": service,
                        "النوع": "مطلوبة",
                        "العدد": needed_count
                    })
                    plot_data.append({
                        "الخدمة": service,
                        "النوع": "منفذة",
                        "العدد": done_count
                    })
                
                plot_df = pd.DataFrame(plot_data)
                
                # عرض المخطط
                fig = px.bar(
                    plot_df, 
                    x="الخدمة", 
                    y="العدد", 
                    color="النوع",
                    barmode="group",
                    title="توزيع الخدمات المطلوبة والمنفذة",
                    color_discrete_map={
                        "مطلوبة": "#FF6B6B",
                        "منفذة": "#4ECDC4"
                    }
                )
                fig.update_layout(
                    xaxis_title="الخدمة",
                    yaxis_title="العدد",
                    showlegend=True,
                    height=500
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # مخطط دائري للنسبة العامة
                fig2 = px.pie(
                    names=["✅ منفذة", "⏳ غير منفذة"],
                    values=[service_stats["total_done_services"], 
                           service_stats["total_needed_services"] - service_stats["total_done_services"]],
                    title="نسبة الإنجاز العامة",
                    color_discrete_sequence=["#4ECDC4", "#FF6B6B"]
                )
                fig2.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig2, use_container_width=True)
                
            except ImportError:
                # استخدام streamlit native charts بدلاً من plotly
                st.info("📊 عرض البيانات باستخدام الرسوم البيانية المضمنة في Streamlit")
                
                # عرض جدول بسيط للتوزيع
                st.markdown("**📋 توزيع الخدمات:**")
                
                dist_data = []
                for service, needed_count in service_stats["service_counts"].items():
                    done_count = service_stats["service_done_counts"].get(service, 0)
                    completion_rate = (done_count / needed_count * 100) if needed_count > 0 else 0
                    
                    dist_data.append({
                        "الخدمة": service,
                        "مطلوبة": needed_count,
                        "منفذة": done_count,
                        "نسبة": f"{completion_rate:.1f}%"
                    })
                
                if dist_data:
                    dist_df = pd.DataFrame(dist_data).sort_values("نسبة", ascending=False)
                    st.dataframe(dist_df, use_container_width=True, height=300)
                
                # مخطط شريطي بسيط باستخدام streamlit
                st.markdown("**📊 مخطط الخدمات المطلوبة مقابل المنفذة:**")
                
                # تحضير البيانات للرسم البياني
                chart_data = pd.DataFrame({
                    "الخدمة": list(service_stats["service_counts"].keys()),
                    "مطلوبة": list(service_stats["service_counts"].values()),
                    "منفذة": [service_stats["service_done_counts"].get(service, 0) 
                              for service in service_stats["service_counts"].keys()]
                })
                
                # أخذ أول 10 خدمات لعرضها بشكل أوضح
                if len(chart_data) > 10:
                    chart_data = chart_data.nlargest(10, "مطلوبة")
                
                st.bar_chart(
                    chart_data.set_index("الخدمة"),
                    height=400
                )
                
                # عرض النسبة العامة كـ progress bar
                st.markdown(f"**📈 نسبة الإنجاز العامة:** {completion_rate:.1f}%")
                st.progress(completion_rate / 100)
        else:
            st.info("ℹ️ لا توجد بيانات كافية لعرض المخططات.")
    
    with stat_tabs[2]:
        st.markdown("#### 📊 الإحصائيات حسب الشريحة")
        
        slice_stats_data = []
        for slice_key, slice_data in service_stats["by_slice"].items():
            completion_rate_slice = (slice_data["total_done"] / slice_data["total_needed"] * 100) if slice_data["total_needed"] > 0 else 0
            
            slice_stats_data.append({
                "الشريحة": slice_key,
                "الخدمات المطلوبة": slice_data["total_needed"],
                "الخدمات المنفذة": slice_data["total_done"],
                "الخدمات المتبقية": slice_data["total_needed"] - slice_data["total_done"],
                "نسبة الإنجاز": f"{completion_rate_slice:.1f}%",
                "حالة الشريحة": "✅ ممتازة" if completion_rate_slice >= 90 else 
                               "🟢 جيدة" if completion_rate_slice >= 70 else 
                               "🟡 متوسطة" if completion_rate_slice >= 50 else 
                               "🔴 ضعيفة"
            })
        
        if slice_stats_data:
            slice_stats_df = pd.DataFrame(slice_stats_data)
            st.dataframe(slice_stats_df, use_container_width=True, height=400)
            
            # محاولة استخدام plotly للمخططات التفاعلية
            try:
                import plotly.graph_objects as go
                
                # تحليل نطاقات الشرائح
                slice_ranges = []
                completion_rates = []
                
                for slice_item in slice_stats_data:
                    slice_key = slice_item["الشريحة"]
                    slice_range = slice_key.split("-")
                    if len(slice_range) == 2:
                        try:
                            mid_point = (int(slice_range[0]) + int(slice_range[1])) / 2
                            slice_ranges.append(mid_point)
                            
                            # استخراج النسبة من النص
                            rate_text = slice_item["نسبة الإنجاز"]
                            rate_value = float(rate_text.replace("%", "").strip())
                            completion_rates.append(rate_value)
                        except:
                            continue
                
                if slice_ranges and completion_rates:
                    fig3 = go.Figure()
                    fig3.add_trace(go.Scatter(
                        x=slice_ranges,
                        y=completion_rates,
                        mode='lines+markers',
                        name='نسبة الإنجاز',
                        line=dict(color='#4ECDC4', width=3),
                        marker=dict(size=10, color='#FF6B6B')
                    ))
                    
                    fig3.update_layout(
                        title="نسبة الإنجاز حسب نطاق الأطنان",
                        xaxis_title="نطاق الأطنان (منتصف الشريحة)",
                        yaxis_title="نسبة الإنجاز (%)",
                        height=400,
                        showlegend=True
                    )
                    
                    st.plotly_chart(fig3, use_container_width=True)
                    
            except ImportError:
                # استخدام streamlit line chart بديل
                if slice_stats_data:
                    # تحضير البيانات للرسم البياني
                    chart_data = []
                    for slice_item in slice_stats_data:
                        slice_key = slice_item["الشريحة"]
                        slice_range = slice_key.split("-")
                        if len(slice_range) == 2:
                            try:
                                mid_point = (int(slice_range[0]) + int(slice_range[1])) / 2
                                rate_text = slice_item["نسبة الإنجاز"]
                                rate_value = float(rate_text.replace("%", "").strip())
                                
                                chart_data.append({
                                    "نطاق الأطنان": mid_point,
                                    "نسبة الإنجاز": rate_value
                                })
                            except:
                                continue
                    
                    if chart_data:
                        chart_df = pd.DataFrame(chart_data).sort_values("نطاق الأطنان")
                        st.line_chart(chart_df.set_index("نطاق الأطنان"), height=400)
        else:
            st.info("ℹ️ لا توجد بيانات إحصائية للشرائح.")

# -------------------------------
# 🖥 دالة فحص الإيفينت والكوريكشن - واجهة مبسطة واحترافية
# -------------------------------
def check_events_and_corrections(all_sheets):
    """فحص الإيفينت والكوريكشن بواجهة مبسطة واحترافية"""
    if not all_sheets:
        st.error("❌ لم يتم تحميل أي شيتات.")
        return
    
    # تهيئة session state إذا لزم الأمر
    if "search_params" not in st.session_state:
        st.session_state.search_params = {
            "card_numbers": "",
            "date_range": "",
            "tech_names": "",
            "search_text": "",
            "exact_match": False,
            "include_empty": True,
            "sort_by": "رقم الماكينة"
        }
    
    if "search_triggered" not in st.session_state:
        st.session_state.search_triggered = False
    
    # قسم البحث - واجهة احترافية
    with st.container():
        st.markdown("### 🔍 بحث متعدد المعايير")
        st.markdown("استخدم الحقول التالية للبحث المحدد. يمكنك ملء واحد أو أكثر من الحقول.")
        
        # تقسيم الشاشة إلى أعمدة
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # قسم أرقام الماكينات
            with st.expander("🔢 **أرقام الماكينات**", expanded=True):
                st.caption("أدخل أرقام الماكينات (مفصولة بفواصل أو نطاقات)")
                card_numbers = st.text_input(
                    "مثال: 1,3,5 أو 1-5 أو 2,4,7-10",
                    value=st.session_state.search_params.get("card_numbers", ""),
                    key="input_cards",
                    placeholder="اتركه فارغاً للبحث في كل الماكينات"
                )
                
                # أزرار سريعة لأرقام الماكينات
                st.caption("أو اختر من:")
                quick_cards_col1, quick_cards_col2, quick_cards_col3 = st.columns(3)
                with quick_cards_col1:
                    if st.button("🔟 أول 10 ماكينات", key="quick_10"):
                        st.session_state.search_params["card_numbers"] = "1-10"
                        st.session_state.search_triggered = True
                        st.rerun()
                with quick_cards_col2:
                    if st.button("🔟 ماكينات 11-20", key="quick_20"):
                        st.session_state.search_params["card_numbers"] = "11-20"
                        st.session_state.search_triggered = True
                        st.rerun()
                with quick_cards_col3:
                    if st.button("🗑 مسح", key="clear_cards"):
                        st.session_state.search_params["card_numbers"] = ""
                        st.rerun()
            
            # قسم التواريخ
            with st.expander("📅 **التواريخ**", expanded=True):
                st.caption("ابحث بالتاريخ (سنة، شهر/سنة)")
                date_input = st.text_input(
                    "مثال: 2024 أو 1/2024 أو 2024,2025",
                    value=st.session_state.search_params.get("date_range", ""),
                    key="input_date",
                    placeholder="اتركه فارغاً للبحث في كل التواريخ"
                )
                
                # شهور السنة
                months = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", 
                         "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
                
                month_cols = st.columns(4)
                for i, month in enumerate(months):
                    with month_cols[i % 4]:
                        if st.button(f"{i+1}. {month}", key=f"month_{i+1}"):
                            current_date = st.session_state.search_params.get("date_range", "")
                            if current_date:
                                st.session_state.search_params["date_range"] = f"{current_date},{i+1}/"
                            else:
                                st.session_state.search_params["date_range"] = f"{i+1}/"
                            st.rerun()
        
        with col2:
            # قسم فنيي الخدمة
            with st.expander("👨‍🔧 **فنيو الخدمة**", expanded=True):
                st.caption("ابحث بأسماء فنيي الخدمة")
                tech_names = st.text_input(
                    "مثال: أحمد, محمد, علي",
                    value=st.session_state.search_params.get("tech_names", ""),
                    key="input_techs",
                    placeholder="اتركه فارغاً للبحث في كل الفنيين"
                )
                
                # استخراج أسماء الفنيين المتاحة
                available_techs = extract_available_techs(all_sheets)
                if available_techs:
                    st.caption(f"📋 فنيون متاحون ({len(available_techs)}):")
                    
                    # الحصول على الفنيين المحددين حالياً بشكل آمن
                    current_techs_input = st.session_state.search_params.get("tech_names", "")
                    current_techs = []
                    if current_techs_input:
                        # تنظيف القائمة من القيم الفارغة
                        current_techs = [t.strip() for t in current_techs_input.split(',') 
                                        if t.strip() and t.strip() in available_techs]
                    
                    # استخدام multiselect بدون default أولاً
                    selected_techs = st.multiselect(
                        "اختر فنيين:",
                        options=available_techs,
                        key="select_techs",
                        label_visibility="collapsed"
                    )
                    
                    # تحديث الحقل النصي بناءً على الاختيار
                    if selected_techs:
                        tech_names = ", ".join(selected_techs)
            
            # قسم نص البحث
            with st.expander("📝 **نص البحث**", expanded=True):
                st.caption("ابحث في وصف الحدث أو التصحيح")
                search_text = st.text_input(
                    "مثال: صيانة, إصلاح, تغيير",
                    value=st.session_state.search_params.get("search_text", ""),
                    key="input_text",
                    placeholder="اتركه فارغاً للبحث في كل النصوص"
                )
                
                # كلمات شائعة
                common_words = ["صيانة", "إصلاح", "تغيير", "تنظيف", "فحص", "تركيب", "تبديل"]
                word_cols = st.columns(4)
                for i, word in enumerate(common_words):
                    with word_cols[i % 4]:
                        if st.button(word, key=f"word_{word}"):
                            current_text = st.session_state.search_params.get("search_text", "")
                            if current_text:
                                st.session_state.search_params["search_text"] = f"{current_text},{word}"
                            else:
                                st.session_state.search_params["search_text"] = word
                            st.rerun()
        
        # قسم خيارات البحث المتقدمة
        with st.expander("⚙ **خيارات متقدمة**", expanded=False):
            col_adv1, col_adv2, col_adv3 = st.columns(3)
            with col_adv1:
                search_mode = st.radio(
                    "🔍 طريقة البحث:",
                    ["بحث جزئي", "مطابقة كاملة"],
                    index=0 if not st.session_state.search_params.get("exact_match") else 1,
                    key="radio_search_mode",
                    help="بحث جزئي: يبحث عن النص في أي مكان. مطابقة كاملة: يبحث عن النص مطابق تماماً"
                )
            with col_adv2:
                include_empty = st.checkbox(
                    "🔍 تضمين الحقول الفارغة",
                    value=st.session_state.search_params.get("include_empty", True),
                    key="checkbox_include_empty",
                    help="تضمين النتائج التي تحتوي على حقول فارغة"
                )
            with col_adv3:
                sort_by = st.selectbox(
                    "📊 ترتيب النتائج:",
                    ["رقم الماكينة", "التاريخ", "فني الخدمة"],
                    index=["رقم الماكينة", "التاريخ", "فني الخدمة"].index(
                        st.session_state.search_params.get("sort_by", "رقم الماكينة")
                    ),
                    key="select_sort_by"
                )
        
        # زر البحث الرئيسي
        st.markdown("---")
        col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])
        with col_btn1:
            search_clicked = st.button(
                "🔍 **بدء البحث**",
                type="primary",
                use_container_width=True,
                key="main_search_btn"
            )
        with col_btn2:
            if st.button("🗑 **مسح الحقول**", use_container_width=True, key="clear_fields"):
                st.session_state.search_params = {
                    "card_numbers": "",
                    "date_range": "",
                    "tech_names": "",
                    "search_text": "",
                    "exact_match": False,
                    "include_empty": True,
                    "sort_by": "رقم الماكينة"
                }
                st.session_state.search_triggered = False
                st.rerun()
        with col_btn3:
            if st.button("📊 **عرض كل البيانات**", use_container_width=True, key="show_all"):
                st.session_state.search_params = {
                    "card_numbers": "",
                    "date_range": "",
                    "tech_names": "",
                    "search_text": "",
                    "exact_match": False,
                    "include_empty": True,
                    "sort_by": "رقم الماكينة"
                }
                st.session_state.search_triggered = True
                st.rerun()
    
    # تحديث معايير البحث عند تغيير الحقول
    if card_numbers != st.session_state.search_params.get("card_numbers", ""):
        st.session_state.search_params["card_numbers"] = card_numbers
    
    if date_input != st.session_state.search_params.get("date_range", ""):
        st.session_state.search_params["date_range"] = date_input
    
    if tech_names != st.session_state.search_params.get("tech_names", ""):
        st.session_state.search_params["tech_names"] = tech_names
    
    if search_text != st.session_state.search_params.get("search_text", ""):
        st.session_state.search_params["search_text"] = search_text
    
    st.session_state.search_params["exact_match"] = (search_mode == "مطابقة كاملة")
    st.session_state.search_params["include_empty"] = include_empty
    st.session_state.search_params["sort_by"] = sort_by
    
    # تحديث tech_names من multiselect إذا تم الاختيار
    if "select_techs" in st.session_state and st.session_state.select_techs:
        selected_techs_list = st.session_state.select_techs
        if selected_techs_list:
            st.session_state.search_params["tech_names"] = ", ".join(selected_techs_list)
    
    # معالجة البحث
    if search_clicked or st.session_state.search_triggered:
        st.session_state.search_triggered = True
        
        # جمع معايير البحث
        search_params = st.session_state.search_params.copy()
        
        # عرض معايير البحث
        show_search_params(search_params)
        
        # تنفيذ البحث
        show_advanced_search_results(search_params, all_sheets)

def extract_available_techs(all_sheets):
    """استخراج أسماء فنيي الخدمة المتاحة في البيانات"""
    techs_set = set()
    
    for sheet_name, df in all_sheets.items():
        if sheet_name == "ServicePlan":
            continue
            
        for _, row in df.iterrows():
            tech = get_servised_by_value(row)
            if tech != "-":
                techs_set.add(tech)
    
    return sorted(list(techs_set))

def show_search_params(search_params):
    """عرض معايير البحث المستخدمة"""
    with st.container():
        st.markdown("### ⚙ معايير البحث المستخدمة")
        
        params_display = []
        if search_params["card_numbers"]:
            params_display.append(f"**🔢 أرقام الماكينات:** {search_params['card_numbers']}")
        if search_params["date_range"]:
            params_display.append(f"**📅 التواريخ:** {search_params['date_range']}")
        if search_params["tech_names"]:
            params_display.append(f"**👨‍🔧 فنيو الخدمة:** {search_params['tech_names']}")
        if search_params["search_text"]:
            params_display.append(f"**📝 نص البحث:** {search_params['search_text']}")
        
        if params_display:
            st.info(" | ".join(params_display))
        else:
            st.info("🔍 **بحث في كل البيانات**")

def show_advanced_search_results(search_params, all_sheets):
    """عرض نتائج البحث المتقدم"""
    st.markdown("### 📊 نتائج البحث")
    
    # شريط التقدم
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # البحث في البيانات
    all_results = []
    total_machines = 0
    processed_machines = 0
    
    # حساب إجمالي عدد الماكينات
    for sheet_name in all_sheets.keys():
        if sheet_name != "ServicePlan" and sheet_name.startswith("Card"):
            total_machines += 1
    
    # معالجة أرقام الماكينات المطلوبة
    target_card_numbers = parse_card_numbers(search_params["card_numbers"])
    
    # معالجة أسماء الفنيين
    target_techs = []
    if search_params["tech_names"]:
        techs = search_params["tech_names"].split(',')
        target_techs = [tech.strip().lower() for tech in techs if tech.strip()]
    
    # معالجة التواريخ
    target_dates = []
    if search_params["date_range"]:
        dates = search_params["date_range"].split(',')
        target_dates = [date.strip().lower() for date in dates if date.strip()]
    
    # معالجة نص البحث
    search_terms = []
    if search_params["search_text"]:
        terms = search_params["search_text"].split(',')
        search_terms = [term.strip().lower() for term in terms if term.strip()]
    
    # البحث في جميع الشيتات
    for sheet_name in all_sheets.keys():
        if sheet_name == "ServicePlan":
            continue
        
        # استخراج رقم الماكينة
        card_num_match = re.search(r'Card(\d+)', sheet_name)
        if not card_num_match:
            continue
            
        card_num = int(card_num_match.group(1))
        
        # التحقق من رقم الماكينة إذا كان هناك تحديد
        if target_card_numbers and card_num not in target_card_numbers:
            continue
        
        processed_machines += 1
        if total_machines > 0:
            progress_bar.progress(processed_machines / total_machines)
        status_text.text(f"🔍 جاري معالجة الماكينة {card_num}...")
        
        df = all_sheets[sheet_name].copy()
        
        # البحث في الصفوف
        for _, row in df.iterrows():
            # تطبيق معايير البحث
            if not check_row_criteria(row, df, card_num, target_techs, target_dates, 
                                     search_terms, search_params):
                continue
            
            # استخراج البيانات
            result = extract_row_data(row, df, card_num)
            if result:
                all_results.append(result)
    
    # إخفاء شريط التقدم
    progress_bar.empty()
    status_text.empty()
    
    # عرض النتائج
    if all_results:
        display_search_results(all_results, search_params)
    else:
        st.warning("⚠ لم يتم العثور على نتائج تطابق معايير البحث")
        st.info("💡 حاول تعديل معايير البحث أو استخدام مصطلحات أوسع")

def check_row_criteria(row, df, card_num, target_techs, target_dates, 
                      search_terms, search_params):
    """التحقق من مطابقة الصف لمعايير البحث"""
    
    # 1. التحقق من فني الخدمة
    if target_techs:
        row_tech = get_servised_by_value(row).lower()
        if row_tech == "-" and not search_params["include_empty"]:
            return False
        
        tech_match = False
        if row_tech != "-":
            for tech in target_techs:
                if search_params["exact_match"]:
                    if tech == row_tech:
                        tech_match = True
                        break
                else:
                    if tech in row_tech:
                        tech_match = True
                        break
        
        if not tech_match:
            return False
    
    # 2. التحقق من التاريخ
    if target_dates:
        row_date = str(row.get("Date", "")).strip().lower() if pd.notna(row.get("Date")) else ""
        if not row_date and not search_params["include_empty"]:
            return False
        
        date_match = False
        if row_date:
            for date_term in target_dates:
                if search_params["exact_match"]:
                    if date_term == row_date:
                        date_match = True
                        break
                else:
                    if date_term in row_date:
                        date_match = True
                        break
        
        if not date_match:
            return False
    
    # 3. التحقق من نص البحث
    if search_terms:
        row_event, row_correction = extract_event_correction(row, df)
        row_event_lower = row_event.lower()
        row_correction_lower = row_correction.lower()
        
        if not row_event and not row_correction and not search_params["include_empty"]:
            return False
        
        text_match = False
        combined_text = f"{row_event_lower} {row_correction_lower}"
        
        for term in search_terms:
            if search_params["exact_match"]:
                if term == row_event_lower or term == row_correction_lower:
                    text_match = True
                    break
            else:
                if term in combined_text:
                    text_match = True
                    break
        
        if not text_match:
            return False
    
    return True

def extract_event_correction(row, df):
    """استخراج الحدث والتصحيح من الصف"""
    event_value = "-"
    correction_value = "-"
    
    for col in df.columns:
        col_normalized = normalize_name(col)
        if "event" in col_normalized or "الحدث" in col_normalized:
            if col in row and pd.notna(row[col]) and str(row[col]).strip() != "":
                event_value = str(row[col]).strip()
        
        if "correction" in col_normalized or "تصحيح" in col_normalized:
            if col in row and pd.notna(row[col]) and str(row[col]).strip() != "":
                correction_value = str(row[col]).strip()
    
    return event_value, correction_value

def extract_row_data(row, df, card_num):
    """استخراج بيانات الصف"""
    card_num_value = str(row.get("card", "")).strip() if pd.notna(row.get("card")) else str(card_num)
    date = str(row.get("Date", "")).strip() if pd.notna(row.get("Date")) else "-"
    tones = str(row.get("Tones", "")).strip() if pd.notna(row.get("Tones")) else "-"
    
    event_value, correction_value = extract_event_correction(row, df)
    
    # إذا كانت كل الحقول فارغة، نتجاهل الصف
    if (event_value == "-" and correction_value == "-" and 
        date == "-" and tones == "-"):
        return None
    
    servised_by_value = get_servised_by_value(row)
    
    return {
        "Card Number": card_num_value,
        "Event": event_value,
        "Correction": correction_value,
        "Servised by": servised_by_value,
        "Tones": tones,
        "Date": date
    }

def parse_card_numbers(card_numbers_str):
    """تحليل سلسلة أرقام الماكينات إلى قائمة أرقام"""
    if not card_numbers_str:
        return set()
    
    numbers = set()
    
    try:
        parts = card_numbers_str.split(',')
        for part in parts:
            part = part.strip()
            if '-' in part:
                try:
                    start_str, end_str = part.split('-')
                    start = int(start_str.strip())
                    end = int(end_str.strip())
                    numbers.update(range(start, end + 1))
                except:
                    continue
            else:
                try:
                    num = int(part)
                    numbers.add(num)
                except:
                    continue
    except:
        return set()
    
    return numbers

def display_search_results(results, search_params):
    """عرض نتائج البحث بشكل احترافي"""
    # تحويل النتائج إلى DataFrame
    result_df = pd.DataFrame(results)
    
    # ترتيب النتائج
    if search_params["sort_by"] == "التاريخ":
        result_df = result_df.sort_values(by="Date", ascending=False)
    elif search_params["sort_by"] == "فني الخدمة":
        result_df = result_df.sort_values(by="Servised by")
    else:  # رقم الماكينة
        result_df = result_df.sort_values(by="Card Number")
    
    # عرض الإحصائيات
    st.markdown("### 📈 إحصائيات النتائج")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📋 عدد النتائج", len(result_df))
    
    with col2:
        unique_machines = result_df["Card Number"].nunique()
        st.metric("🔢 عدد الماكينات", unique_machines)
    
    with col3:
        if "Servised by" in result_df.columns:
            unique_techs = result_df[result_df["Servised by"] != "-"]["Servised by"].nunique()
            st.metric("👨‍🔧 فنيين مختلفين", unique_techs)
    
    with col4:
        with_correction = result_df[result_df["Correction"] != "-"].shape[0]
        st.metric("✏ تحتوي على تصحيح", with_correction)
    
    # توزيع النتائج
    st.markdown("#### 📊 توزيع النتائج")
    
    tab1, tab2, tab3 = st.tabs(["حسب الماكينة", "حسب فني الخدمة", "حسب السنة"])
    
    with tab1:
        if not result_df.empty:
            machine_dist = result_df["Card Number"].value_counts().head(15)
            dist_df = pd.DataFrame({
                "رقم الماكينة": machine_dist.index,
                "عدد الأحداث": machine_dist.values,
                "النسبة %": (machine_dist.values / len(result_df) * 100).round(1)
            })
            st.dataframe(dist_df, use_container_width=True, height=300)
    
    with tab2:
        if "Servised by" in result_df.columns and not result_df[result_df["Servised by"] != "-"].empty:
            tech_dist = result_df[result_df["Servised by"] != "-"]["Servised by"].value_counts().head(10)
            tech_df = pd.DataFrame({
                "فني الخدمة": tech_dist.index,
                "عدد الأحداث": tech_dist.values,
                "النسبة %": (tech_dist.values / len(result_df) * 100).round(1)
            })
            st.dataframe(tech_df, use_container_width=True, height=300)
    
    with tab3:
        if "Date" in result_df.columns:
            years = []
            for date_str in result_df["Date"]:
                if date_str != "-":
                    year_match = re.search(r'(\d{4})', str(date_str))
                    if year_match:
                        years.append(year_match.group(1))
            
            if years:
                year_stats = pd.Series(years).value_counts().sort_index()
                year_df = pd.DataFrame({
                    "السنة": year_stats.index,
                    "عدد الأحداث": year_stats.values
                })
                st.dataframe(year_df, use_container_width=True, height=300)
    
    # عرض النتائج الرئيسية
    st.markdown("### 📋 النتائج التفصيلية")
    
    # فلترة النتائج
    st.markdown("#### 🔍 فلترة النتائج")
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    
    with filter_col1:
        show_with_event = st.checkbox("📝 مع حدث", True, key="filter_event")
    with filter_col2:
        show_with_correction = st.checkbox("✏ مع تصحيح", True, key="filter_correction")
    with filter_col3:
        show_with_tech = st.checkbox("👨‍🔧 مع فني خدمة", True, key="filter_tech")
    
    # تطبيق الفلاتر
    filtered_df = result_df.copy()
    
    if not show_with_event:
        filtered_df = filtered_df[filtered_df["Event"] == "-"]
    if not show_with_correction:
        filtered_df = filtered_df[filtered_df["Correction"] == "-"]
    if not show_with_tech:
        filtered_df = filtered_df[filtered_df["Servised by"] == "-"]
    
    # عرض البيانات
    st.dataframe(
        filtered_df.style.apply(style_table, axis=1),
        use_container_width=True,
        height=500
    )
    
    # خيارات التصدير
    st.markdown("---")
    st.markdown("### 💾 خيارات التصدير")
    
    export_col1, export_col2 = st.columns(2)
    
    with export_col1:
        # تصدير Excel
        buffer_excel = io.BytesIO()
        result_df.to_excel(buffer_excel, index=False, engine="openpyxl")
        st.download_button(
            label="📊 حفظ كملف Excel",
            data=buffer_excel.getvalue(),
            file_name=f"بحث_أحداث_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    
    with export_col2:
        # تصدير CSV
        buffer_csv = io.BytesIO()
        result_df.to_csv(buffer_csv, index=False, encoding='utf-8-sig')
        st.download_button(
            label="📄 حفظ كملف CSV",
            data=buffer_csv.getvalue(),
            file_name=f"بحث_أحداث_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

# -------------------------------
# 🖥 دالة إضافة إيفينت جديد - في الشيت المنفصل
# -------------------------------
def add_new_event(sheets_edit):
    """إضافة إيفينت جديد في شيت منفصل"""
    st.subheader("➕ إضافة حدث جديد")
    
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
    
    event_date = st.text_input("التاريخ (مثال: 20\\5\\2025):", key="new_event_date")
    
    if st.button("💾 إضافة الحدث الجديد", key="add_new_event_btn"):
        if not card_num.strip():
            st.warning("⚠ الرجاء إدخال رقم الماكينة.")
            return
        
        # إنشاء صف جديد
        new_row = {}
        
        # إضافة البيانات الأساسية للأحداث
        new_row["card"] = card_num.strip()
        if event_date.strip():
            new_row["Date"] = event_date.strip()
        
        # إضافة بيانات الإيفينت والكوريكشن
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
        
        # البحث عن عمود Servised by
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
        
        # إضافة الصف الجديد
        new_row_df = pd.DataFrame([new_row]).astype(str)
        df_new = pd.concat([df, new_row_df], ignore_index=True)
        
        sheets_edit[sheet_name] = df_new.astype(object)
        
        # حفظ تلقائي في GitHub
        new_sheets = auto_save_to_github(
            sheets_edit,
            f"إضافة حدث جديد في {sheet_name}"
        )
        if new_sheets is not None:
            sheets_edit = new_sheets
            st.success("✅ تم إضافة الحدث الجديد بنجاح!")
            st.rerun()

# -------------------------------
# 🖥 دالة تعديل الإيفينت والكوريكشن
# -------------------------------
def edit_events_and_corrections(sheets_edit):
    """تعديل الإيفينت والكوريكشن"""
    st.subheader("✏ تعديل الحدث والتصحيح")
    
    sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_events_sheet")
    df = sheets_edit[sheet_name].astype(str)
    
    # عرض البيانات الحالية
    st.markdown("### 📋 البيانات الحالية (الحدث والتصحيح)")
    
    # استخراج الأعمدة المطلوبة
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
    
    # عرض البيانات
    display_df = df[display_columns].copy()
    st.dataframe(display_df, use_container_width=True)
    
    # اختيار الصف للتعديل
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
        
        # حقول الإيفينت والكوريكشن
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
        
        if st.button("💾 حفظ التعديلات", key="save_edits_btn"):
            # تحديث البيانات
            df.at[row_index, "card"] = new_card
            df.at[row_index, "Date"] = new_date
            
            if event_col:
                df.at[row_index, event_col] = new_event
            if correction_col:
                df.at[row_index, correction_col] = new_correction
            
            # البحث عن عمود Servised by
            servised_col = None
            for col in df.columns:
                if normalize_name(col) in ["servisedby", "servicedby", "serviceby", "خدمبواسطة"]:
                    servised_col = col
                    break
            
            if servised_col and new_serviced_by.strip():
                df.at[row_index, servised_col] = new_serviced_by.strip()
            
            sheets_edit[sheet_name] = df.astype(object)
            
            # حفظ تلقائي في GitHub
            new_sheets = auto_save_to_github(
                sheets_edit,
                f"تعديل حدث في {sheet_name} - الصف {row_index}"
            )
            if new_sheets is not None:
                sheets_edit = new_sheets
                st.success("✅ تم حفظ التعديلات بنجاح!")
                # مسح بيانات الجلسة
                if "editing_row" in st.session_state:
                    del st.session_state["editing_row"]
                if "editing_data" in st.session_state:
                    del st.session_state["editing_data"]
                st.rerun()

# -------------------------------
# 👥 إدارة المستخدمين (للمسؤولين فقط)
# -------------------------------
def manage_users():
    """إدارة المستخدمين والصلاحيات"""
    st.header("👥 إدارة المستخدمين")
    
    users = load_users()
    
    # عرض المستخدمين الحاليين
    st.markdown("### 📋 المستخدمون الحاليون")
    
    if users:
        # إنشاء DataFrame للمستخدمين
        users_data = []
        for username, user_info in users.items():
            users_data.append({
                "اسم المستخدم": username,
                "الدور": user_info.get("role", "viewer"),
                "الصلاحيات": ", ".join(user_info.get("permissions", ["view"])),
                "تاريخ الإنشاء": user_info.get("created_at", "غير معروف")
            })
        
        users_df = pd.DataFrame(users_data)
        st.dataframe(users_df, use_container_width=True)
    else:
        st.info("ℹ️ لا توجد مستخدمين مسجلين بعد.")
    
    st.markdown("---")
    
    # تبويبات لإدارة المستخدمين
    user_tabs = st.tabs(["➕ إضافة مستخدم جديد", "✏ تعديل مستخدم", "🗑 حذف مستخدم"])
    
    with user_tabs[0]:
        st.markdown("#### ➕ إضافة مستخدم جديد")
        
        col1, col2 = st.columns(2)
        with col1:
            new_username = st.text_input("اسم المستخدم الجديد:", key="new_username")
            new_password = st.text_input("كلمة المرور:", type="password", key="new_password")
            confirm_password = st.text_input("تأكيد كلمة المرور:", type="password", key="confirm_password")
        
        with col2:
            user_role = st.selectbox(
                "دور المستخدم:",
                ["admin", "editor", "viewer"],
                index=2,
                key="new_user_role"
            )
            
            # اختيار الصلاحيات بناءً على الدور
            if user_role == "admin":
                default_permissions = ["all"]
                available_permissions = ["all", "view", "edit", "manage_users", "tech_support"]
            elif user_role == "editor":
                default_permissions = ["view", "edit"]
                available_permissions = ["view", "edit", "export"]
            else:
                default_permissions = ["view"]
                available_permissions = ["view", "export"]
            
            selected_permissions = st.multiselect(
                "الصلاحيات:",
                options=available_permissions,
                default=default_permissions,
                key="new_user_permissions"
            )
        
        if st.button("💾 إضافة المستخدم", key="add_user_btn"):
            if not new_username:
                st.warning("⚠ الرجاء إدخال اسم المستخدم.")
                return
            
            if new_username in users:
                st.error("❌ اسم المستخدم موجود بالفعل.")
                return
            
            if not new_password:
                st.warning("⚠ الرجاء إدخال كلمة المرور.")
                return
            
            if new_password != confirm_password:
                st.error("❌ كلمة المرور غير مطابقة.")
                return
            
            if len(new_password) < 6:
                st.warning("⚠ كلمة المرور يجب أن تكون 6 أحرف على الأقل.")
                return
            
            # إضافة المستخدم الجديد
            users[new_username] = {
                "password": new_password,
                "role": user_role,
                "permissions": selected_permissions if selected_permissions else default_permissions,
                "created_at": datetime.now().isoformat()
            }
            
            if save_users(users):
                st.success(f"✅ تم إضافة المستخدم '{new_username}' بنجاح!")
                st.rerun()
            else:
                st.error("❌ حدث خطأ أثناء حفظ المستخدم.")
    
    with user_tabs[1]:
        st.markdown("#### ✏ تعديل مستخدم")
        
        if not users:
            st.info("ℹ️ لا توجد مستخدمين لتعديلهم.")
        else:
            user_to_edit = st.selectbox(
                "اختر المستخدم للتعديل:",
                list(users.keys()),
                key="select_user_to_edit"
            )
            
            if user_to_edit:
                user_info = users[user_to_edit]
                
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"**المستخدم:** {user_to_edit}")
                    st.info(f"**الدور الحالي:** {user_info.get('role', 'viewer')}")
                    
                    # تغيير كلمة المرور
                    st.markdown("##### 🔐 تغيير كلمة المرور")
                    new_password_edit = st.text_input("كلمة المرور الجديدة:", type="password", key="edit_password")
                    confirm_password_edit = st.text_input("تأكيد كلمة المرور:", type="password", key="edit_confirm_password")
                
                with col2:
                    # تغيير الدور
                    new_role = st.selectbox(
                        "تغيير الدور:",
                        ["admin", "editor", "viewer"],
                        index=["admin", "editor", "viewer"].index(user_info.get("role", "viewer")),
                        key="edit_user_role"
                    )
                    
                    # تغيير الصلاحيات بناءً على الدور الجديد
                    if new_role == "admin":
                        default_permissions = ["all"]
                        available_permissions = ["all", "view", "edit", "manage_users", "tech_support"]
                    elif new_role == "editor":
                        default_permissions = ["view", "edit"]
                        available_permissions = ["view", "edit", "export"]
                    else:
                        default_permissions = ["view"]
                        available_permissions = ["view", "export"]
                    
                    current_permissions = user_info.get("permissions", default_permissions)
                    new_permissions = st.multiselect(
                        "تغيير الصلاحيات:",
                        options=available_permissions,
                        default=current_permissions,
                        key="edit_user_permissions"
                    )
                
                # أزرار التعديل
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("💾 حفظ التعديلات", key="save_user_edit"):
                        updated = False
                        
                        # تحديث الدور والصلاحيات
                        if user_info.get("role") != new_role or user_info.get("permissions") != new_permissions:
                            users[user_to_edit]["role"] = new_role
                            users[user_to_edit]["permissions"] = new_permissions if new_permissions else default_permissions
                            updated = True
                        
                        # تحديث كلمة المرور إذا تم إدخالها
                        if new_password_edit:
                            if new_password_edit != confirm_password_edit:
                                st.error("❌ كلمة المرور غير مطابقة.")
                                return
                            if len(new_password_edit) < 6:
                                st.warning("⚠ كلمة المرور يجب أن تكون 6 أحرف على الأقل.")
                                return
                            
                            users[user_to_edit]["password"] = new_password_edit
                            updated = True
                        
                        if updated:
                            if save_users(users):
                                st.success(f"✅ تم تحديث المستخدم '{user_to_edit}' بنجاح!")
                                
                                # إذا كان المستخدم الحالي هو الذي تم تعديله، قم بتحديث session state
                                if st.session_state.get("username") == user_to_edit:
                                    st.session_state.user_role = new_role
                                    st.session_state.user_permissions = new_permissions if new_permissions else default_permissions
                                    st.info("🔁 تم تحديث بيانات جلسة العمل الحالية.")
                                
                                st.rerun()
                            else:
                                st.error("❌ حدث خطأ أثناء حفظ التعديلات.")
                        else:
                            st.info("ℹ️ لم يتم إجراء أي تغييرات.")
                
                with col_btn2:
                    # زر إعادة تعيين كلمة المرور
                    if st.button("🔄 إعادة تعيين كلمة المرور", key="reset_password"):
                        # كلمة مرور افتراضية
                        default_password = "user123"
                        users[user_to_edit]["password"] = default_password
                        
                        if save_users(users):
                            st.warning(f"⚠ تم إعادة تعيين كلمة مرور '{user_to_edit}' إلى: {default_password}")
                            st.info("📋 يجب على المستخدم تغيير كلمة المرور عند أول تسجيل دخول.")
                            st.rerun()
    
    with user_tabs[2]:
        st.markdown("#### 🗑 حذف مستخدم")
        
        if not users:
            st.info("ℹ️ لا توجد مستخدمين لحذفهم.")
        else:
            # قائمة المستخدمين المتاحة للحذف (لا يمكن حذف المسؤول الرئيسي)
            deletable_users = [u for u in users.keys() if u != "admin"]
            
            if not deletable_users:
                st.warning("⚠ لا يمكن حذف أي مستخدمين (يوجد المسؤول الرئيسي فقط).")
            else:
                user_to_delete = st.selectbox(
                    "اختر المستخدم للحذف:",
                    deletable_users,
                    key="select_user_to_delete"
                )
                
                if user_to_delete:
                    user_info = users[user_to_delete]
                    
                    st.warning(f"⚠ **تحذير:** أنت على وشك حذف المستخدم '{user_to_delete}'")
                    st.info(f"**الدور:** {user_info.get('role', 'viewer')}")
                    st.info(f"**تاريخ الإنشاء:** {user_info.get('created_at', 'غير معروف')}")
                    
                    # تأكيد الحذف
                    confirm_delete = st.checkbox(f"أؤكد أنني أريد حذف المستخدم '{user_to_delete}'", key="confirm_delete")
                    
                    if confirm_delete:
                        if st.button("🗑️ حذف المستخدم نهائياً", type="primary", key="delete_user_final"):
                            # التحقق من أن المستخدم ليس مسجلاً دخولاً حالياً
                            state = load_state()
                            if user_to_delete in state and state[user_to_delete].get("active"):
                                st.error("❌ لا يمكن حذف المستخدم أثناء تسجيل دخوله.")
                                return
                            
                            # حذف المستخدم
                            del users[user_to_delete]
                            
                            if save_users(users):
                                st.success(f"✅ تم حذف المستخدم '{user_to_delete}' بنجاح!")
                                st.rerun()
                            else:
                                st.error("❌ حدث خطأ أثناء حذف المستخدم.")

# -------------------------------
# 📞 الدعم الفني
# -------------------------------
def tech_support():
    """قسم الدعم الفني"""
    st.header("📞 الدعم الفني")
    
    st.markdown(f"""
    ### ℹ️ معلومات التطبيق
    
    **اسم التطبيق:** {APP_CONFIG["APP_TITLE"]}
    **الملف الرئيسي:** {APP_CONFIG["FILE_PATH"]}
    **مستودع GitHub:** {APP_CONFIG["REPO_NAME"]}
    **فرع العمل:** {APP_CONFIG["BRANCH"]}
    
    ### 🔧 استكشاف الأخطاء وإصلاحها
    
    1. **المشكلة:** لا يمكن تحميل الملف من GitHub
       **الحل:** 
       - تأكد من اتصال الإنترنت
       - تحقق من رابط الملف في GitHub
       - اضغط على زر "🔄 تحديث الملف من GitHub"
    
    2. **المشكلة:** لا يمكن حفظ التعديلات
       **الحل:**
       - تأكد من وجود token GitHub في الإعدادات
       - تحقق من صلاحيات الرفع إلى المستودع
    
    3. **المشكلة:** التطبيق يعمل ببطء
       **الحل:**
       - اضغط على زر "🗑 مسح الكاش"
       - قلل عدد الصفوف المعروضة
       - استخدم فلاتر البحث
    
    ### 📊 إحصائيات النظام
    """)
    
    # عرض إحصائيات النظام
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # عدد المستخدمين
        users = load_users()
        st.metric("👥 عدد المستخدمين", len(users))
    
    with col2:
        # عدد الجلسات النشطة
        state = load_state()
        active_sessions = sum(1 for u in state.values() if u.get("active"))
        st.metric("🔒 جلسات نشطة", f"{active_sessions}/{MAX_ACTIVE_USERS}")
    
    with col3:
        # حجم الملف المحلي
        if os.path.exists(APP_CONFIG["LOCAL_FILE"]):
            file_size = os.path.getsize(APP_CONFIG["LOCAL_FILE"]) / (1024 * 1024)  # بالميجابايت
            st.metric("💾 حجم الملف", f"{file_size:.2f} MB")
        else:
            st.metric("💾 حجم الملف", "غير موجود")
    
    st.markdown("---")
    
    # معلومات الجلسة الحالية
    st.markdown("### 🖥 معلومات الجلسة الحالية")
    
    if st.session_state.get("logged_in"):
        session_info = {
            "المستخدم": st.session_state.get("username", "غير معروف"),
            "الدور": st.session_state.get("user_role", "غير معروف"),
            "الصلاحيات": ", ".join(st.session_state.get("user_permissions", [])),
            "وقت التسجيل": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        for key, value in session_info.items():
            st.text(f"**{key}:** {value}")
    else:
        st.info("ℹ️ لم يتم تسجيل الدخول")
    
    # زر إعادة التشغيل
    st.markdown("---")
    if st.button("🔄 إعادة تشغيل التطبيق", key="restart_app"):
        try:
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"❌ خطأ في إعادة التشغيل: {e}")

# ===============================
# 🖥 الواجهة الرئيسية المدمجة
# ===============================
# إعداد الصفحة
st.set_page_config(page_title=APP_CONFIG["APP_TITLE"], layout="wide")

# شريط تسجيل الدخول / معلومات الجلسة في الشريط الجانبي
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
    
    # زر مسح الكاش
    if st.button("🗑 مسح الكاش", key="clear_cache"):
        try:
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error(f"❌ خطأ في مسح الكاش: {e}")
    
    # زر تحديث الجلسة
    if st.button("🔄 تحديث الجلسة", key="refresh_session"):
        # تحميل أحدث بيانات المستخدم
        users = load_users()
        username = st.session_state.get("username")
        if username and username in users:
            st.session_state.user_role = users[username].get("role", "viewer")
            st.session_state.user_permissions = users[username].get("permissions", ["view"])
            st.success("✅ تم تحديث بيانات الجلسة!")
            st.rerun()
        else:
            st.warning("⚠ لا يمكن تحديث الجلسة.")
    
    st.markdown("---")
    # زر لإعادة تسجيل الخروج
    if st.button("🚪 تسجيل الخروج", key="logout_btn"):
        logout_action()

# تحميل الشيتات (عرض وتحليل)
all_sheets = load_all_sheets()

# تحميل الشيتات للتحرير (dtype=object)
sheets_edit = load_sheets_for_edit()

# واجهة التبويبات الرئيسية
st.title(f"{APP_CONFIG['APP_ICON']} {APP_CONFIG['APP_TITLE']}")

# التحقق من الصلاحيات - استخدم .get() لمنع الأخطاء
username = st.session_state.get("username")
user_role = st.session_state.get("user_role", "viewer")
user_permissions = st.session_state.get("user_permissions", ["view"])
permissions = get_user_permissions(user_role, user_permissions)

# تحديد التبويبات بناءً على الصلاحيات
if permissions["can_manage_users"]:  # admin
    tabs = st.tabs(APP_CONFIG["CUSTOM_TABS"])
    
    # Tab: إدارة المستخدمين (للمسؤولين فقط)
    with tabs[3]:
        manage_users()
    
    # Tab: الدعم الفني (للمسؤولين فقط أو إذا كان الإعداد يسمح للجميع)
    if APP_CONFIG["SHOW_TECH_SUPPORT_TO_ALL"] or permissions["can_manage_users"]:
        with tabs[4]:
            tech_support()
    
elif permissions["can_edit"]:  # editor
    tabs = st.tabs(["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن", "🛠 تعديل وإدارة البيانات"])
else:  # viewer
    tabs = st.tabs(["📊 فحص السيرفيس", "📋 فحص الإيفينت والكوريكشن"])

# -------------------------------
# Tab: فحص السيرفيس (لجميع المستخدمين)
# -------------------------------
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

# -------------------------------
# Tab: فحص الإيفينت والكوريكشن (لجميع المستخدمين)
# -------------------------------
with tabs[1]:
    st.header("📋 فحص الإيفينت والكوريكشن")
    
    if all_sheets is None:
        st.warning("❗ الملف المحلي غير موجود. استخدم زر التحديث في الشريط الجانبي لتحميل الملف من GitHub.")
    else:
        # واجهة بحث متعدد المعايير
        check_events_and_corrections(all_sheets)

# -------------------------------
# Tab: تعديل وإدارة البيانات - للمحررين والمسؤولين فقط
# -------------------------------
if permissions["can_edit"] and len(tabs) > 2:
    with tabs[2]:
        st.header("🛠 تعديل وإدارة البيانات")

        # تحقق صلاحية الرفع
        token_exists = bool(st.secrets.get("github", {}).get("token", None))
        can_push = token_exists and GITHUB_AVAILABLE

        if sheets_edit is None:
            st.warning("❗ الملف المحلي غير موجود. اضغط تحديث من GitHub في الشريط الجانبي أولًا.")
        else:
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "عرض وتعديل شيت",
                "إضافة صف جديد", 
                "إضافة عمود جديد",
                "➕ إضافة حدث جديد",
                "✏ تعديل الحدث"
            ])

            # Tab 1: تعديل بيانات وعرض
            with tab1:
                st.subheader("✏ تعديل البيانات")
                sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_sheet")
                df = sheets_edit[sheet_name].astype(str)

                edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, 
                                         key=f"editor_{sheet_name}")
                
                if not edited_df.equals(df):
                    st.info("🔄 يتم حفظ التغييرات تلقائياً...")
                    sheets_edit[sheet_name] = edited_df.astype(object)
                    new_sheets = auto_save_to_github(
                        sheets_edit, 
                        f"تعديل تلقائي في شيت {sheet_name}"
                    )
                    if new_sheets is not None:
                        sheets_edit = new_sheets
                        st.rerun()

            # Tab 2: إضافة صف جديد
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

                if st.button("💾 إضافة الصف الجديد", key=f"add_row_{sheet_name_add}"):
                    new_row_df = pd.DataFrame([new_data]).astype(str)
                    df_new = pd.concat([df_add, new_row_df], ignore_index=True)
                    
                    sheets_edit[sheet_name_add] = df_new.astype(object)

                    new_sheets = auto_save_to_github(
                        sheets_edit,
                        f"إضافة صف جديد في {sheet_name_add}"
                    )
                    if new_sheets is not None:
                        sheets_edit = new_sheets
                        st.rerun()

            # Tab 3: إضافة عمود جديد
            with tab3:
                st.subheader("🆕 إضافة عمود جديد")
                sheet_name_col = st.selectbox("اختر الشيت لإضافة عمود:", list(sheets_edit.keys()), key="add_col_sheet")
                df_col = sheets_edit[sheet_name_col].astype(str)
                
                new_col_name = st.text_input("اسم العمود الجديد:", key="new_col_name")
                default_value = st.text_input("القيمة الافتراضية لكل الصفوف (اختياري):", "", key="default_value")

                if st.button("💾 إضافة العمود الجديد", key=f"add_col_{sheet_name_col}"):
                    if new_col_name:
                        df_col[new_col_name] = default_value
                        sheets_edit[sheet_name_col] = df_col.astype(object)
                        
                        new_sheets = auto_save_to_github(
                            sheets_edit,
                            f"إضافة عمود جديد '{new_col_name}' إلى {sheet_name_col}"
                        )
                        if new_sheets is not None:
                            sheets_edit = new_sheets
                            st.rerun()
                    else:
                        st.warning("⚠ الرجاء إدخال اسم العمود الجديد.")

            # Tab 4: إضافة إيفينت جديد
            with tab4:
                add_new_event(sheets_edit)

            # Tab 5: تعديل الإيفينت والكوريكشن
            with tab5:
                edit_events_and_corrections(sheets_edit)
