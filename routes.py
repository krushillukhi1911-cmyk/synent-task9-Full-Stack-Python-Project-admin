from flask import render_template, flash, redirect, url_for, request
from flask_login import login_user, logout_user, current_user, login_required
from urllib.parse import urlsplit
from taskmaster import db
from taskmaster.models import User, Task
from taskmaster.forms import RegistrationForm, LoginForm, TaskForm, UpdateProfileForm, UpdatePasswordForm
from sqlalchemy import or_

def init_app(app):
    @app.route('/')
    @app.route('/index')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return render_template('index.html', title='Home')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        form = RegistrationForm()
        if form.validate_on_submit():
            user = User(fullname=form.fullname.data, username=form.username.data, email=form.email.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('Congratulations, you are now a registered user!', 'success')
            return redirect(url_for('login'))
        return render_template('register.html', title='Register', form=form)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter((User.username == form.username_or_email.data) | (User.email == form.username_or_email.data)).first()
            if user is None or not user.check_password(form.password.data):
                flash('Invalid username or password', 'danger')
                return redirect(url_for('login'))
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or urlsplit(next_page).netloc != '':
                next_page = url_for('dashboard')
            return redirect(next_page)
        return render_template('login.html', title='Sign In', form=form)

    @app.route('/logout')
    def logout():
        logout_user()
        return redirect(url_for('index'))

    @app.route('/dashboard')
    @login_required
    def dashboard():
        tasks = current_user.tasks.all()
        total_tasks = len(tasks)
        
        # Calculate stats
        completed_tasks = sum(1 for t in tasks if t.status == 'Completed')
        pending_tasks = sum(1 for t in tasks if t.status == 'Pending')
        in_progress_tasks = sum(1 for t in tasks if t.status == 'In Progress')
        high_priority = sum(1 for t in tasks if t.priority == 'High')
        
        recent_tasks = current_user.tasks.order_by(Task.created_at.desc()).limit(3).all()
        upcoming_tasks = current_user.tasks.filter(Task.status != 'Completed').order_by(Task.due_date.asc()).limit(3).all()
        
        completion_percentage = int((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0
        
        status_data = {
            'Completed': completed_tasks,
            'Pending': pending_tasks,
            'In Progress': in_progress_tasks
        }
        
        from datetime import date
        today_date = date.today()
        
        return render_template('dashboard.html', title='Dashboard', 
                               total_tasks=total_tasks, completed_tasks=completed_tasks,
                               pending_tasks=pending_tasks + in_progress_tasks, high_priority=high_priority,
                               recent_tasks=recent_tasks, upcoming_tasks=upcoming_tasks,
                               completion_percentage=completion_percentage,
                               status_data=status_data, today_date=today_date)

    @app.route('/tasks')
    @login_required
    def tasks():
        search = request.args.get('search', '')
        status_filter = request.args.get('status', '')
        priority_filter = request.args.get('priority', '')
        sort_by = request.args.get('sort', 'due_date')
        
        query = current_user.tasks
        
        if search:
            query = query.filter(Task.title.ilike(f'%{search}%') | Task.description.ilike(f'%{search}%'))
        if status_filter:
            query = query.filter_by(status=status_filter)
        if priority_filter:
            query = query.filter_by(priority=priority_filter)
            
        if sort_by == 'due_date':
            query = query.order_by(Task.due_date.asc())
        elif sort_by == 'due_date_desc':
            query = query.order_by(Task.due_date.desc())
        elif sort_by == 'created_at':
            query = query.order_by(Task.created_at.desc())
            
        page = request.args.get('page', 1, type=int)
        tasks = query.paginate(page=page, per_page=5, error_out=False)
        return render_template('tasks.html', title='My Tasks', tasks=tasks)

    @app.route('/task/new', methods=['GET', 'POST'])
    @login_required
    def create_task():
        form = TaskForm()
        if form.validate_on_submit():
            task = Task(title=form.title.data, description=form.description.data,
                        due_date=form.due_date.data, priority=form.priority.data,
                        status=form.status.data, author=current_user)
            db.session.add(task)
            db.session.commit()
            flash('Your task has been created!', 'success')
            return redirect(url_for('tasks'))
        return render_template('create_task.html', title='New Task', form=form)

    @app.route('/task/<int:task_id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_task(task_id):
        task = Task.query.get_or_404(task_id)
        if task.author != current_user:
            flash('You are not authorized to edit this task.', 'danger')
            return redirect(url_for('tasks'))
        form = TaskForm()
        if form.validate_on_submit():
            task.title = form.title.data
            task.description = form.description.data
            task.due_date = form.due_date.data
            task.priority = form.priority.data
            task.status = form.status.data
            db.session.commit()
            flash('Your task has been updated.', 'success')
            return redirect(url_for('tasks'))
        elif request.method == 'GET':
            form.title.data = task.title
            form.description.data = task.description
            form.due_date.data = task.due_date
            form.priority.data = task.priority
            form.status.data = task.status
        return render_template('edit_task.html', title='Edit Task', form=form, task=task)

    @app.route('/task/<int:task_id>/delete', methods=['POST'])
    @login_required
    def delete_task(task_id):
        task = Task.query.get_or_404(task_id)
        if task.author != current_user:
            flash('You are not authorized to delete this task.', 'danger')
            return redirect(url_for('tasks'))
        db.session.delete(task)
        db.session.commit()
        flash('Task has been deleted.', 'success')
        return redirect(url_for('tasks'))

    @app.route('/profile', methods=['GET', 'POST'])
    @login_required
    def profile():
        profile_form = UpdateProfileForm(current_user.username, current_user.email)
        password_form = UpdatePasswordForm()
        
        if 'profile_submit' in request.form and profile_form.validate_on_submit():
            current_user.fullname = profile_form.fullname.data
            current_user.username = profile_form.username.data
            current_user.email = profile_form.email.data
            db.session.commit()
            flash('Your profile has been updated!', 'success')
            return redirect(url_for('profile'))
        elif request.method == 'GET':
            profile_form.fullname.data = current_user.fullname
            profile_form.username.data = current_user.username
            profile_form.email.data = current_user.email
            
        if 'password_submit' in request.form and password_form.validate_on_submit():
            if current_user.check_password(password_form.current_password.data):
                current_user.set_password(password_form.new_password.data)
                db.session.commit()
                flash('Your password has been updated!', 'success')
                return redirect(url_for('profile'))
            else:
                flash('Invalid current password.', 'danger')
                
        return render_template('profile.html', title='Profile', profile_form=profile_form, password_form=password_form)

    @app.route('/calendar')
    @login_required
    def calendar():
        # Get tasks sorted by due date
        tasks = current_user.tasks.order_by(Task.due_date.asc()).all()
        return render_template('calendar.html', title='Calendar', tasks=tasks)

    @app.route('/settings')
    @login_required
    def settings():
        return render_template('settings.html', title='Settings')

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('500.html'), 500
