from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "supersecretkey"  # change in production

# Upload folder
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ---------------- DATABASE INIT ----------------
def init_sqlite_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Users
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL)''')

#post
    c.execute('''CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    author_email TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    image TEXT,
                    video TEXT,
                    genre TEXT)''')

    # Subscriptions
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subscriber_email TEXT NOT NULL,
                    subscribed_to_email TEXT NOT NULL)''')

    # Comments
    c.execute('''CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER NOT NULL,
                    author_email TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(post_id) REFERENCES posts(id))''')

    # User streaks
    c.execute('''CREATE TABLE IF NOT EXISTS user_streaks (
                    email TEXT PRIMARY KEY,
                    streak INTEGER DEFAULT 0,
                    last_visit TEXT)''')

    conn.commit()
    conn.close()

init_sqlite_db()

# ---------------- BADGES ----------------
def get_user_badges(email):
    """
    Returns a list of badges the user has earned
    Example return: [('First Post',), ('Multimedia Post',)]
    """
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    badges = []

    # Count posts
    c.execute("SELECT COUNT(*) FROM posts WHERE author_email=?", (email,))
    post_count = c.fetchone()[0]

    # First post
    if post_count >= 1:
        badges.append(('First Post',))

    # 10 posts
    if post_count >= 10:
        badges.append(('10 Posts',))

    # Multimedia post
    c.execute("SELECT * FROM posts WHERE author_email=? AND (image IS NOT NULL OR video IS NOT NULL)", (email,))
    multimedia_post = c.fetchone()
    if multimedia_post:
        badges.append(('Multimedia Post',))

    conn.close()
    return badges

# ---------------- ROUTES ----------------
@app.route('/')
def index():
    return redirect(url_for('login'))

# ---------------- AUTH ----------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        try:
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, password))
            conn.commit()
            conn.close()
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Email already registered!", "danger")
            return redirect(url_for('signup'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        if user and check_password_hash(user[2], password):
            session['user'] = email

            # ---------------- UPDATE STREAK ----------------
            today = datetime.now().date()
            c.execute("SELECT streak, last_visit FROM user_streaks WHERE email=?", (email,))
            data = c.fetchone()
            if data:
                streak, last_visit = data
                last_visit_date = datetime.strptime(last_visit, "%Y-%m-%d").date()
                if last_visit_date == today:
                    pass  # already logged in today
                elif last_visit_date == today - timedelta(days=1):
                    streak += 1  # increment streak
                else:
                    streak = 1  # missed a day, reset streak
                c.execute("UPDATE user_streaks SET streak=?, last_visit=? WHERE email=?",
                          (streak, today.strftime("%Y-%m-%d"), email))
            else:
                streak = 1
                c.execute("INSERT INTO user_streaks (email, streak, last_visit) VALUES (?, ?, ?)",
                          (email, streak, today.strftime("%Y-%m-%d")))
            conn.commit()
            conn.close()

            return redirect(url_for('home'))
        else:
            conn.close()
            flash("Invalid login credentials!", "danger")
            return redirect(url_for('login'))
    return render_template('login.html')

# ---------------- HOME ----------------
@app.route('/home')
def home():
    if 'user' not in session:
        return redirect(url_for('login'))

    search = request.args.get("search")
    genre_filter = request.args.get("genre")

    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # ---------------- STREAK ----------------
    c.execute("SELECT streak FROM user_streaks WHERE email=?", (session['user'],))
    streak_data = c.fetchone()
    streak = streak_data[0] if streak_data else 0

    query = "SELECT * FROM posts"
    params = []

    if search and genre_filter:
        query += " WHERE (title LIKE ? OR content LIKE ?) AND genre=?"
        params = [f'%{search}%', f'%{search}%', genre_filter]
    elif search:
        query += " WHERE title LIKE ? OR content LIKE ?"
        params = [f'%{search}%', f'%{search}%']
    elif genre_filter:
        query += " WHERE genre=?"
        params = [genre_filter]

    query += " ORDER BY id DESC"
    c.execute(query, params)
    posts = c.fetchall()

    # Leaderboard
    c.execute("SELECT author_email, COUNT(*) as count FROM posts GROUP BY author_email ORDER BY count DESC")
    leaderboard = c.fetchall()

    # Fetch comments
    comments_dict = {}
    for post in posts:
        c.execute("SELECT author_email, content, created_at FROM comments WHERE post_id = ? ORDER BY id DESC", (post[0],))
        comments_dict[post[0]] = c.fetchall()

    conn.close()
    return render_template('home.html', user=session['user'], posts=posts, leaderboard=leaderboard, comments=comments_dict, streak=streak)

# ---------------- WRITE POST ----------------
@app.route('/write', methods=['GET', 'POST'])
def write():
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        genre = request.form['genre']
        author = session['user']

        # Image
        image_file = request.files.get('image')
        image_filename = None
        if image_file and image_file.filename.strip() != "":
            image_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(image_file.filename)}"
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

        # Video
        video_file = request.files.get('video')
        video_filename = None
        if video_file and video_file.filename.strip() != "":
            video_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(video_file.filename)}"
            video_file.save(os.path.join(app.config['UPLOAD_FOLDER'], video_filename))

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute(
            "INSERT INTO posts (title, content, author_email, created_at, image, video, genre) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, content, author, datetime.now().strftime("%Y-%m-%d %H:%M"), image_filename, video_filename, genre)
        )
        conn.commit()
        conn.close()
        flash("Blog posted successfully!", "success")
        return redirect(url_for('home'))

    return render_template('write.html')

# ---------------- COMMENTS ----------------
@app.route('/comment/<int:post_id>', methods=['POST'])
def comment(post_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    content = request.form['content']
    author = session['user']

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("INSERT INTO comments (post_id, author_email, content, created_at) VALUES (?, ?, ?, ?)",
              (post_id, author, content, datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()
    flash("Comment added!", "success")
    return redirect(url_for('home'))

# ---------------- PROFILE ----------------
@app.route('/profile')
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM posts WHERE author_email = ? ORDER BY id DESC", (session['user'],))
    my_posts = c.fetchall()
    conn.close()

    # Get badges
    badges = get_user_badges(session['user'])

    return render_template('profile.html', user=session['user'], my_posts=my_posts, badges=badges)

# ---------------- LEADERBOARD ----------------
@app.route('/leaderboard')
def leaderboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT author_email, COUNT(*) as count FROM posts GROUP BY author_email ORDER BY count DESC")
    leaderboard = c.fetchall()
    conn.close()
    return render_template('leaderboard.html', leaderboard=leaderboard)

# ---------------- SUBSCRIPTIONS ----------------
@app.route('/subscribe/<string:author_email>')
def subscribe(author_email):
    if 'user' not in session:
        return redirect(url_for('login'))

    subscriber = session['user']
    if subscriber == author_email:
        flash("You cannot subscribe to yourself!", "warning")
        return redirect(url_for('home'))

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM subscriptions WHERE subscriber_email = ? AND subscribed_to_email = ?", 
              (subscriber, author_email))
    exists = c.fetchone()
    if not exists:
        c.execute("INSERT INTO subscriptions (subscriber_email, subscribed_to_email) VALUES (?, ?)",
                  (subscriber, author_email))
        conn.commit()
        flash(f"Subscribed to {author_email}", "success")
    else:
        flash(f"Already subscribed to {author_email}", "info")
    conn.close()
    return redirect(url_for('subscriptions'))


@app.route('/subscriptions')
def subscriptions():
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT subscribed_to_email FROM subscriptions WHERE subscriber_email = ?", (session['user'],))
    subscribed_users = [row[0] for row in c.fetchall()]
    conn.close()
    return render_template('subscriptions.html', user=session['user'], subscribed_users=subscribed_users)

@app.route('/unsubscribe/<string:author_email>')
def unsubscribe(author_email):
    if 'user' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("DELETE FROM subscriptions WHERE subscriber_email = ? AND subscribed_to_email = ?",
              (session['user'], author_email))
    conn.commit()
    conn.close()
    flash(f"Unsubscribed from {author_email}", "info")
    return redirect(url_for('subscriptions'))

# ---------------- VIEW SINGLE POST ----------------
@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def view_post(post_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Fetch post
    c.execute("SELECT * FROM posts WHERE id=?", (post_id,))
    post = c.fetchone()
    if not post:
        conn.close()
        flash("Post not found!", "danger")
        return redirect(url_for('home'))

    # Fetch comments
    c.execute("SELECT author_email, content, created_at FROM comments WHERE post_id=? ORDER BY id DESC", (post_id,))
    comments = c.fetchall()

    # Check subscription
    subscribed = False
    if session['user'] != post[3]:
        c.execute("SELECT * FROM subscriptions WHERE subscriber_email=? AND subscribed_to_email=?",
                  (session['user'], post[3]))
        subscribed = c.fetchone() is not None

    conn.close()
    return render_template('view_post.html', post=post, comments=comments, subscribed=subscribed)

# ---------------- DELETE POST ----------------
@app.route('/delete_post/<int:post_id>', methods=['POST', 'GET'])
def delete_post(post_id):
    if 'user' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("DELETE FROM posts WHERE id = ? AND author_email = ?", (post_id, session['user']))
    conn.commit()
    conn.close()
    flash("Post deleted successfully!", "info")
    return redirect(url_for('home'))

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("Logged out successfully!", "info")
    return redirect(url_for('login'))

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)

