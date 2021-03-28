from flask import render_template, url_for, flash, redirect, request, abort
from mainpackage import app, db, bcrypt, mail
from mainpackage.form import RegistrationForm, LoginForm, UpdateAccountForm, PostForm, RequestResetForm, ResetPasswordForm
from mainpackage.models import User, Post
from flask_login import login_user, current_user, logout_user, login_required
import secrets
import os
from PIL import Image
from flask_mail import Message

@app.route('/')
@app.route('/home')
@login_required
def home():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.date_posted.desc()).paginate(page=page, per_page=5)
    return render_template('home.html', posts=posts)

@app.route('/user/<string:username>')
def user_posts(username):
    user = User.query.filter_by(username=username).first_or_404()
    image_file = url_for('static', filename='profile_picture/' + user.image_file)
    page = request.args.get('page', 1, type=int)
    posts = Post.query.filter_by(author=user).order_by(Post.date_posted.desc()).paginate(page=page, per_page=5)
    return render_template('user_posts.html', posts=posts, user=user, image_file=image_file)

'''
This code is for showing other users profile info if clicked on there name in (users Posts Page )

@app.route('/user_info/<string:username>')
def user_info(username):
    user = User.query.filter_by(username=username).first_or_404()
    image_file = url_for('static', filename='profile_picture/' + user.image_file)
    return render_template('user_info.html', user=user, image_file=image_file)
'''

@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():  # if the form validates (from front-end)
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')  # hashing the password
        user = User(first_name=form.first_name.data,
                    last_name=form.last_name.data,
                    username=form.username.data,
                    gender=form.gender.data,
                    email=form.email.data,
                    password=hashed_password)  # passing all the info from form to the database userclass
        db.session.add(user)  # adding
        db.session.commit()  # commiting the changes
        flash(f'Account created for {form.username.data}', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))

        else:
            flash('Login Unsuccessful, Please check Email and Password again', 'danger')
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged Out Successfully', 'info')
    return redirect(url_for('login'))


def save_picture(form_pic):
    random_hex = secrets.token_hex(8)
    f_name, f_ext = os.path.splitext(form_pic.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path + '\\static\\profile_picture\\' + picture_fn)
    output_size = (125, 125)  # setting image pixel size
    i = Image.open(form_pic)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture_fn


@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            pic = save_picture(form.picture.data)
            current_user.image_file = pic
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your account has been updated', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.first_name.data = current_user.first_name
        form.last_name.data = current_user.last_name
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for('static', filename='profile_picture/' + current_user.image_file)
    return render_template('account.html', current_user=current_user, image_file=image_file, form=form)


@app.route('/post/new', methods=['GET', 'POST'])
@login_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(title=form.title.data, content=form.content.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('Your post has been created', 'success')
        return redirect(url_for('home'))
    return render_template('create_post.html', form=form, legend='Update Post')


@app.route('/post/<int:post_id>')
def post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('post.html', title=post.title, post=post)


@app.route('/post/<int:post_id>/update', methods=['GET', 'POST'])
@login_required
def update_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    form = PostForm()  # Re-using the Postform and getting the data populated as user clicks and Post that he wants to update
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        db.session.commit()
        flash('Post updated successfully', 'success')
        return redirect(url_for('post', post_id=post.id))
    elif request.method == 'GET':
        form.title.data = post.title
        form.content.data = post.content
    return render_template('create_post.html', form=form, legend='Update Post')


@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:  # verify that the post selected belong to the current user or not
        abort(403)  # show abort error

    db.session.delete(post)  # else delete
    db.session.commit()
    flash('Post deleted successfully', 'success')
    return redirect(url_for('home'))



def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Message Reset Request', sender='noreply@facemash.com', recipients=[user.email])
    msg.body = f'''To reset your password visit following link
{ url_for('reset_token', token=token, _external = True) }

If you did not request any reset then simply ignore and no changes will be made
Regards
Facemash.com
'''
    mail.send(msg)


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return render_template('home')

    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()      # getting the user for the submitted email
        send_reset_email(user)
        flash('An email has been sent with instructions to reset password !', 'info')
    return render_template('reset_request.html', form=form)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:     # user needs to logout first and until they're not logged out they cannot apply for resetting password
        return render_template('home')

    user = User.verify_token(token)     # function created in Models.py file for getting the user_id if token verifies
    if user is None:            # if no user is returned after verifying token
        flash('This is an invalid or expired token', 'warning')
        return redirect(url_for('reset_request'))

    form = ResetPasswordForm()
    if form.validate_on_submit():  # if the form validates (from front-end)
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')  # hashing the password
        user.password = hashed_password
        db.session.commit()  # commiting the changes
        flash(f'Password has been updated, you can login now !', 'success')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)

