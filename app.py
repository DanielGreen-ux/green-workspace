import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import cloudinary
import cloudinary.uploader

app = Flask(__name__)
load_dotenv()

db_url = os.environ["DATABASE_URL"]
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config['SECRET_KEY'] = 'green-workspace-secret-key'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

cloudinary.config(
    cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
    api_key=os.environ["CLOUDINARY_API_KEY"],
    api_secret=os.environ["CLOUDINARY_API_SECRET"],
)

db = SQLAlchemy(app)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    tasks = db.relationship('Task', backref='owner', lazy=True)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='Pending')
    filename = db.Column(db.String(200), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return redirect(url_for('register'))
            
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password_hash=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('dashboard'))
            
        flash('Invalid username or password.', 'error')
        return redirect(url_for('login'))
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_tasks = Task.query.filter_by(user_id=session['user_id']).all()
    return render_template('dashboard.html', tasks=user_tasks)

@app.route('/add_task', methods=['POST'])
def add_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    title = request.form.get('title')
    notes = request.form.get('notes')
    file = request.files.get('file')
    filename = None
    
    if file and file.filename != '':
        result = cloudinary.uploader.upload(file)
        filename = result['secure_url']
    new_task = Task(title=title, notes=notes, filename=filename, user_id=session['user_id'])
    db.session.add(new_task)
    db.session.commit()
    flash('Task created successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/edit_task/<int:task_id>', methods=['POST'])
def edit_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    task = Task.query.get_or_404(task_id)
    if task.user_id == session['user_id']:
        task.title = request.form.get('title')
        task.notes = request.form.get('notes')
        
        file = request.files.get('file')
        if file and file.filename != '':
            result = cloudinary.uploader.upload(file)
            task.filename = result['secure_url']
        db.session.commit()
        flash('Task updated successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/toggle/<int:task_id>')
def toggle_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    task = Task.query.get_or_404(task_id)
    if task.user_id == session['user_id']:
        task.status = 'Completed' if task.status == 'Pending' else 'Pending'
        db.session.commit()
        flash(f'Task marked as {task.status}!', 'success')
        
    return redirect(url_for('dashboard'))

@app.route('/delete/<int:task_id>')
def delete_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    task = Task.query.get_or_404(task_id)
    if task.user_id == session['user_id']:
        db.session.delete(task)
        db.session.commit()
        flash('Task deleted.', 'success')
        
    return redirect(url_for('dashboard'))

@app.route('/delete_file/<int:task_id>')
def delete_file(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    task = Task.query.get_or_404(task_id)
    if task.user_id == session['user_id'] and task.filename:
        # Clear filename from the database record
        task.filename = None
        db.session.commit()
        flash('File removed.', 'success')
    return redirect(url_for('dashboard'))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)