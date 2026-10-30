import os
import sqlite3
import hashlib
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)
app.secret_key = "maum_secret_forecast_key_2026_v8"
DB_NAME = "maum.db"

ADMIN_KEY = "maum1234"

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_IMG = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_AUDIO = {'mp3', 'wav', 'ogg', 'm4a'}

def allowed_file(filename, allowed_set):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_set

def hash_pw(pw):
    return hashlib.sha256(pw.encode('utf-8')).hexdigest()

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_token TEXT PRIMARY KEY,
            nickname TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            board_type INTEGER NOT NULL,
            title TEXT NOT NULL,
            emotion TEXT NOT NULL,
            weather_icon TEXT NOT NULL,
            weather_theme TEXT NOT NULL,
            author_token TEXT NOT NULL,
            content TEXT NOT NULL,
            image_path TEXT,
            audio_path TEXT,
            likes INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            author_token TEXT NOT NULL,
            content TEXT NOT NULL,
            likes INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES posts (id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_date TEXT NOT NULL,
            author_token TEXT NOT NULL,
            content TEXT NOT NULL,
            likes INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS direct_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_token TEXT NOT NULL,
            receiver_token TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_token TEXT NOT NULL,
            nickname TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            ip_address TEXT,
            visited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

EMOTION_CONFIG = {
    '행복': {'icon': '☀️ 햇살', 'theme': 'theme-sun'},
    '기쁨': {'icon': '🌈 무지개', 'theme': 'theme-sun'},
    '희망': {'icon': '🌤️ 맑음', 'theme': 'theme-sun'},
    '슬픔': {'icon': '🌧️ 비', 'theme': 'theme-rain'},
    '우울': {'icon': '🌫️ 안개', 'theme': 'theme-rain'},
    '좌절': {'icon': '🌨️ 진눈깨비', 'theme': 'theme-rain'},
    '화남': {'icon': '⚡ 번개', 'theme': 'theme-storm'},
    '분노': {'icon': '🌩️ 낙뢰', 'theme': 'theme-storm'},
    '짜증남': {'icon': '💨 돌풍', 'theme': 'theme-storm'},
    '불안': {'icon': '☁️ 먹구름', 'theme': 'theme-cloud'},
    '평온': {'icon': '⛅ 구름조금', 'theme': 'theme-cloud'}
}

DAILY_QUESTIONS = [
    "마음에 비가 주룩주룩 내릴 때, 기분을 달래주는 나만의 '소울 푸드'는 무엇인가요?",
    "마음이 구름 한 점 없이 맑고 기쁜 날, 꼭 듣고 싶은 노래 한 곡을 추천해 주세요! 🎵",
    "오늘 내 마음에 부는 바람의 온도는 몇 도쯤 될까요? (따스한 봄바람? 쌀쌀한 가을바람?)",
    "예상치 못한 천둥번개 같은 스트레스를 받았을 때, 10분 만에 진정하는 꿀팁이 있나요?",
    "지금 당장 하늘을 올려다본다면, 구름 사이로 어떤 풍경이나 색깔을 보고 싶으신가요?",
    "마음 속 먹구름을 걷어내고 따뜻한 햇살을 비춰준 최근의 사소하고 감사한 기억은?",
    "나를 위로해주는 '마음의 우산' 같은 사람이나 물건, 혹은 취미가 있다면 무엇인가요?"
]

def get_today_question():
    today_str = datetime.now().strftime("%Y-%m-%d")
    idx = int(hashlib.md5(today_str.encode()).hexdigest(), 16) % len(DAILY_QUESTIONS)
    return today_str, DAILY_QUESTIONS[idx]

@app.before_request
def check_login_and_log():
    allowed_routes = ['login', 'register', 'static']
    if request.endpoint and any(request.endpoint.startswith(r) for r in allowed_routes):
        return

    if 'user_token' not in session:
        return redirect(url_for('login'))

    token = session['user_token']
    db = get_db()
    db.execute("UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_token = ?", (token,))
    
    if not request.path.startswith('/static') and not request.path.startswith('/like'):
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        db.execute("INSERT INTO access_logs (user_token, nickname, endpoint, ip_address) VALUES (?, ?, ?, ?)",
                   (token, session.get('user_name', '알 수 없음'), request.path, ip))
    db.commit()
    db.close()

@app.context_processor
def inject_global_vars():
    return {
        'current_user_name': session.get('user_name', ''),
        'current_user_token': session.get('user_token', ''),
        'is_admin': session.get('is_admin', False)
    }

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        nickname = request.form.get('nickname', '').strip()
        password = request.form.get('password', '').strip()
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE nickname = ?", (nickname,)).fetchone()
        db.close()
        
        if user and user['password_hash'] == hash_pw(password):
            session['user_token'] = user['user_token']
            session['user_name'] = user['nickname']
            session['is_admin'] = bool(user['is_admin'])
            return redirect(url_for('index'))
        else:
            error = "닉네임 또는 비밀번호가 일치하지 않습니다."
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        nickname = request.form.get('nickname', '').strip()
        password = request.form.get('password', '').strip()
        if not nickname or not password:
            error = "닉네임과 비밀번호를 모두 입력해주세요."
        else:
            db = get_db()
            existing = db.execute("SELECT * FROM users WHERE nickname = ?", (nickname,)).fetchone()
            if existing:
                error = "이미 사용 중인 닉네임입니다."
                db.close()
            else:
                new_token = str(uuid.uuid4())
                db.execute("INSERT INTO users (user_token, nickname, password_hash, is_admin) VALUES (?, ?, ?, 0)",
                           (new_token, nickname, hash_pw(password)))
                db.commit()
                db.close()
                session['user_token'] = new_token
                session['user_name'] = nickname
                session['is_admin'] = False
                return redirect(url_for('index'))
    return render_template('register.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/daily', methods=['GET', 'POST'])
def daily():
    today_date, question_text = get_today_question()
    db = get_db()
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if content:
            db.execute("INSERT INTO daily_answers (question_date, author_token, content) VALUES (?, ?, ?)",
                       (today_date, session['user_token'], content))
            db.commit()
        return redirect(url_for('daily'))

    answers = db.execute("""
        SELECT a.*, COALESCE(u.nickname, '익명의 날씨') as author_name
        FROM daily_answers a
        LEFT JOIN users u ON a.author_token = u.user_token
        WHERE a.question_date = ?
        ORDER BY a.id DESC
    """, (today_date,)).fetchall()
    db.close()
    return render_template('daily.html', today_date=today_date, question=question_text, answers=answers)

@app.route('/like_daily/<int:answer_id>', methods=['POST'])
def like_daily(answer_id):
    db = get_db()
    db.execute("UPDATE daily_answers SET likes = likes + 1 WHERE id = ?", (answer_id,))
    db.commit()
    db.close()
    return redirect(url_for('daily'))

@app.route('/update_profile', methods=['POST'])
def update_profile():
    new_name = request.form.get('new_name', '').strip()
    if new_name:
        db = get_db()
        existing = db.execute("SELECT * FROM users WHERE nickname = ? AND user_token != ?", (new_name, session['user_token'])).fetchone()
        if not existing:
            db.execute("UPDATE users SET nickname = ? WHERE user_token = ?", (new_name, session['user_token']))
            db.commit()
            session['user_name'] = new_name
        db.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/admin_login', methods=['POST'])
def admin_login():
    input_key = request.form.get('admin_key', '').strip()
    if input_key == ADMIN_KEY:
        db = get_db()
        db.execute("UPDATE users SET is_admin = 1 WHERE user_token = ?", (session['user_token'],))
        db.commit()
        db.close()
        session['is_admin'] = True
    return redirect(request.referrer or url_for('index'))

@app.route('/admin_logout')
def admin_logout():
    db = get_db()
    db.execute("UPDATE users SET is_admin = 0 WHERE user_token = ?", (session['user_token'],))
    db.commit()
    db.close()
    session['is_admin'] = False
    return redirect(url_for('index'))

@app.route('/admin/logs')
def admin_logs():
    if not session.get('is_admin'):
        return "관리자만 접근할 수 있습니다.", 403
    db = get_db()
    users = db.execute("""
        SELECT u.*, 
               (SELECT COUNT(*) FROM posts WHERE author_token = u.user_token) as post_count,
               (SELECT COUNT(*) FROM comments WHERE author_token = u.user_token) as comment_count
        FROM users u 
        ORDER BY u.last_active DESC
    """).fetchall()

    user_logs = {}
    for u in users:
        logs = db.execute("""
            SELECT endpoint, visited_at, ip_address 
            FROM access_logs 
            WHERE user_token = ? 
            ORDER BY id DESC LIMIT 6
        """, (u['user_token'],)).fetchall()
        user_logs[u['user_token']] = logs

    total_posts = db.execute("SELECT COUNT(*) as cnt FROM posts").fetchone()['cnt']
    total_comments = db.execute("SELECT COUNT(*) as cnt FROM comments").fetchone()['cnt']
    total_users = len(users)
    db.close()

    return render_template('admin_logs.html', users=users, user_logs=user_logs, 
                           total_posts=total_posts, total_comments=total_comments, total_users=total_users)

@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    if not session.get('is_admin'):
        return "권한이 없습니다.", 403
    db = get_db()
    db.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
    db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    db.commit()
    db.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/delete_comment/<int:comment_id>', methods=['POST'])
def delete_comment(comment_id):
    if not session.get('is_admin'):
        return "권한이 없습니다.", 403
    db = get_db()
    db.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    db.commit()
    db.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/board/<int:board_type>', methods=['GET', 'POST'])
def board(board_type):
    db = get_db()
    if request.method == 'POST':
        title = request.form.get('title', '').strip() or '마음 날씨 이야기'
        content = request.form.get('content', '').strip()
        emotion = request.form.get('emotion', '평온')
        
        cfg = EMOTION_CONFIG.get(emotion, {'icon': '⛅ 구름조금', 'theme': 'theme-cloud'})
        weather_icon = cfg['icon']
        weather_theme = cfg['theme']
        
        image_filename = None
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file and allowed_file(file.filename, ALLOWED_IMG):
                ext = file.filename.rsplit('.', 1)[1].lower()
                image_filename = f"img_{uuid.uuid4().hex[:10]}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

        audio_filename = None
        if 'audio_file' in request.files:
            file = request.files['audio_file']
            if file and allowed_file(file.filename, ALLOWED_AUDIO):
                ext = file.filename.rsplit('.', 1)[1].lower()
                audio_filename = f"audio_{uuid.uuid4().hex[:10]}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], audio_filename))

        if content:
            db.execute("""
                INSERT INTO posts (board_type, title, emotion, weather_icon, weather_theme, author_token, content, image_path, audio_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (board_type, title, emotion, weather_icon, weather_theme, session['user_token'], content, image_filename, audio_filename))
            db.commit()
        return redirect(url_for('board', board_type=board_type))

    posts = db.execute("""
        SELECT p.*, COALESCE(u.nickname, '익명의 날씨') as author_name
        FROM posts p
        LEFT JOIN users u ON p.author_token = u.user_token
        WHERE p.board_type = ?
        ORDER BY p.id DESC
    """, (board_type,)).fetchall()
    db.close()
    
    board_info = {
        1: {
            "title": "🌧️ 마음 흐림 구역 (고민 나누기)", 
            "sub": "혼자 감당하기 벅찬 비바람을 털어놓고 서로의 우산이 되어주어요.",
            "theme": "rain"
        },
        2: {
            "title": "☀️ 마음 맑음 구역 (해결방법 & 처방전)", 
            "sub": "구름 걷힌 날의 햇살처럼 따뜻한 생각과 나만의 해법을 건네주세요.",
            "theme": "sun"
        }
    }
    current_board = board_info.get(board_type, board_info[1])
    return render_template('board.html', board_type=board_type, info=current_board, posts=posts)

@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def post_detail(post_id):
    db = get_db()
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if content:
            db.execute("INSERT INTO comments (post_id, author_token, content) VALUES (?, ?, ?)",
                       (post_id, session['user_token'], content))
            db.commit()
        return redirect(url_for('post_detail', post_id=post_id))

    post = db.execute("""
        SELECT p.*, COALESCE(u.nickname, '익명의 날씨') as author_name
        FROM posts p
        LEFT JOIN users u ON p.author_token = u.user_token
        WHERE p.id = ?
    """, (post_id,)).fetchone()

    comments = db.execute("""
        SELECT c.*, COALESCE(u.nickname, '익명의 날씨') as author_name
        FROM comments c
        LEFT JOIN users u ON c.author_token = u.user_token
        WHERE c.post_id = ?
        ORDER BY c.id ASC
    """, (post_id,)).fetchall()
    db.close()
    return render_template('post_detail.html', post=post, comments=comments)

@app.route('/like/<int:post_id>', methods=['POST'])
def like_post(post_id):
    db = get_db()
    db.execute("UPDATE posts SET likes = likes + 1 WHERE id = ?", (post_id,))
    db.commit()
    db.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/like_comment/<int:comment_id>', methods=['POST'])
def like_comment(comment_id):
    db = get_db()
    db.execute("UPDATE comments SET likes = likes + 1 WHERE id = ?", (comment_id,))
    db.commit()
    db.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/send_dm', methods=['POST'])
def send_dm():
    receiver_token = request.form.get('receiver_token')
    message = request.form.get('message', '').strip()
    
    if receiver_token and message:
        db = get_db()
        db.execute("INSERT INTO direct_messages (sender_token, receiver_token, message) VALUES (?, ?, ?)",
                   (session['user_token'], receiver_token, message))
        db.commit()
        db.close()
    
    if request.form.get('from_chat') == '1':
        return redirect(url_for('chat_room', partner_token=receiver_token))
    return redirect(request.referrer or url_for('inbox'))

@app.route('/inbox')
def inbox():
    my_token = session['user_token']
    db = get_db()
    dialog_rows = db.execute("""
        SELECT 
            CASE WHEN sender_token = ? THEN receiver_token ELSE sender_token END as partner_token,
            MAX(created_at) as last_time
        FROM direct_messages
        WHERE sender_token = ? OR receiver_token = ?
        GROUP BY partner_token
        ORDER BY last_time DESC
    """, (my_token, my_token, my_token)).fetchall()

    chat_rooms = []
    for row in dialog_rows:
        p_token = row['partner_token']
        partner = db.execute("SELECT nickname FROM users WHERE user_token = ?", (p_token,)).fetchone()
        partner_name = partner['nickname'] if partner else "알 수 없는 사용자"
        
        last_msg = db.execute("""
            SELECT message, sender_token, created_at FROM direct_messages 
            WHERE (sender_token = ? AND receiver_token = ?) OR (sender_token = ? AND receiver_token = ?)
            ORDER BY id DESC LIMIT 1
        """, (my_token, p_token, p_token, my_token)).fetchone()

        chat_rooms.append({
            'partner_token': p_token,
            'partner_name': partner_name,
            'last_message': last_msg['message'] if last_msg else '',
            'last_time': row['last_time'],
            'is_me_last': (last_msg['sender_token'] == my_token) if last_msg else False
        })

    db.close()
    return render_template('inbox.html', chat_rooms=chat_rooms)

@app.route('/chat/<partner_token>')
def chat_room(partner_token):
    my_token = session['user_token']
    db = get_db()
    partner = db.execute("SELECT nickname FROM users WHERE user_token = ?", (partner_token,)).fetchone()
    partner_name = partner['nickname'] if partner else "알 수 없는 사용자"

    messages = db.execute("""
        SELECT * FROM direct_messages
        WHERE (sender_token = ? AND receiver_token = ?) OR (sender_token = ? AND receiver_token = ?)
        ORDER BY id ASC
    """, (my_token, partner_token, partner_token, my_token)).fetchall()
    db.close()

    return render_template('chat_room.html', partner_token=partner_token, partner_name=partner_name, messages=messages)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
