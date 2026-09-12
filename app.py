import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import cloudinary
import cloudinary.uploader
from fpdf import FPDF
from datetime import datetime

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

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt', 'xlsx', 'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def task_to_markdown(task):
    lines = [
        f"# {task.title}",
        f"**Status:** {task.status}",
        "",
        "## Notes",
        task.notes if task.notes else "_No notes added._",
    ]
    if task.filename:
        lines.append("")
        lines.append("## Attached File")
        lines.append(task.filename)
    return "\n".join(lines)

def tasks_to_markdown(tasks):
    sections = [f"# Green Workspace Export", f"_Exported on {datetime.now().strftime('%B %d, %Y')}_", ""]
    for task in tasks:
        sections.append(task_to_markdown(task))
        sections.append("\n---\n")
    return "\n".join(sections)

def task_to_pdf(task):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, 10, safe_pdf_text(task.title))
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, 8, f"Status: {task.status}")
    pdf.ln(4)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, 8, "Notes:")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, 7, safe_pdf_text(task.notes) if task.notes else "No notes added.")
    if task.filename:
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(pdf.epw, 8, "Attached File:")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 255)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(pdf.epw, 7, task.filename)
    return bytes(pdf.output())

def safe_pdf_text(text):
    if not text:
        return text
    text = text.encode('latin-1', 'replace').decode('latin-1')
    words = text.split(' ')
    fixed_words = []
    for word in words:
        if len(word) > 60:
            chunks = [word[i:i+60] for i in range(0, len(word), 60)]
            fixed_words.append(' '.join(chunks))
        else:
            fixed_words.append(word)
    return ' '.join(fixed_words)

def tasks_to_pdf(tasks):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, 12, "Green Workspace Export")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(pdf.epw, 8, f"Exported on {datetime.now().strftime('%B %d, %Y')}")
    pdf.set_text_color(0, 0, 0)
    for task in tasks:
        pdf.ln(6)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(pdf.epw, 8, safe_pdf_text(task.title))
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(100, 100, 100)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(pdf.epw, 6, f"Status: {task.status}")
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(pdf.epw, 6, safe_pdf_text(task.notes) if task.notes else "No notes added.")
        if task.filename:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(0, 0, 255)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(pdf.epw, 6, f"File: {task.filename}")
            pdf.set_text_color(0, 0, 0)
        pdf.ln(2)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    return bytes(pdf.output())
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
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    
    query = Task.query.filter_by(user_id=session['user_id'])
    
    if search:
        query = query.filter(Task.title.ilike(f'%{search}%'))
    if status_filter in ('Pending', 'Completed'):
        query = query.filter_by(status=status_filter)
    
    user_tasks = query.all()
    return render_template('dashboard.html', tasks=user_tasks, search=search, status_filter=status_filter)

@app.route('/add_task', methods=['POST'])
def add_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    title = request.form.get('title')
    notes = request.form.get('notes')
    file = request.files.get('file')
    filename = None
    
    if file and file.filename != '':
        if not allowed_file(file.filename):
            flash('File type not allowed. Please upload an image, PDF, or document.', 'error')
            return redirect(url_for('dashboard'))
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
            if not allowed_file(file.filename):
                flash('File type not allowed. Please upload an image, PDF, or document.', 'error')
                return redirect(url_for('dashboard'))
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
        task.filename = None
        db.session.commit()
        flash('File removed.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/export/task/<int:task_id>/<fmt>')
def export_task(task_id, fmt):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    task = Task.query.get_or_404(task_id)
    if task.user_id != session['user_id']:
        return redirect(url_for('dashboard'))

    safe_name = "".join(c for c in task.title if c.isalnum() or c in (' ', '_')).strip() or "task"

    if fmt == 'pdf':
        pdf_bytes = task_to_pdf(task)
        return Response(pdf_bytes, mimetype='application/pdf',
                         headers={'Content-Disposition': f'attachment; filename="{safe_name}.pdf"'})
    elif fmt == 'md':
        md_text = task_to_markdown(task)
        return Response(md_text, mimetype='text/markdown',
                         headers={'Content-Disposition': f'attachment; filename="{safe_name}.md"'})
    else:
        flash('Invalid export format.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/export/all/<fmt>')
def export_all(fmt):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    tasks = Task.query.filter_by(user_id=session['user_id']).all()

    if fmt == 'pdf':
        pdf_bytes = tasks_to_pdf(tasks)
        return Response(pdf_bytes, mimetype='application/pdf',
                         headers={'Content-Disposition': 'attachment; filename="green_workspace_export.pdf"'})
    elif fmt == 'md':
        md_text = tasks_to_markdown(tasks)
        return Response(md_text, mimetype='text/markdown',
                         headers={'Content-Disposition': 'attachment; filename="green_workspace_export.md"'})
    else:
        flash('Invalid export format.', 'error')
        return redirect(url_for('dashboard'))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)