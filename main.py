from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import create_engine, Column, Integer, String, Date
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from flask_moment import Moment
from functools import wraps
from dotenv import load_dotenv
load_dotenv()
import os
import psycopg2

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
ckeditor = CKEditor(app)
Bootstrap(app)
Moment(app)

Base = declarative_base()

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# #CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# DATABASE_URI = 'postgres+psycopg2://postgres:password@localhost:5432/blog'
DATABASE_URI = os.environ.get('DATABASE_URI1')
DATABASE_URL = os.environ.get('DATABASE_URL')

conn = psycopg2.connect(DATABASE_URL, sslmode='require')
engine = create_engine(DATABASE_URI)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
s = Session()

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return s.query(User).get(int(user_id))


##CONFIGURE TABLES

##CREATE USER TABLE IN DB
class User(UserMixin, Base):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))

    # *******Add parent relationships*******#
    posts = relationship("BlogPost", back_populates="author")
    # "comment_author" refers to the comment_author property in the Comment class.
    comments = relationship("Comment", back_populates="comment_author")


class BlogPost(Base):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    # create foreign key, "users.id" the users refers to the table name of User.
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Create reference to the User object, the "posts" refers to the posts property in the User class.
    author = relationship('User', back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    # Parent relationship for comments
    comments = relationship('Comment', back_populates="parent_post")


# #Comments table in DB
class Comment(Base):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    # *******Add child relationship*******#
    # "users.id" The users refers to the table name of the Users class.
    # "comments" refers to the comments property in the User class.
    author_id = db.Column(Integer, db.ForeignKey('users.id'))
    comment_author = relationship('User', back_populates="comments")

    post_id = db.Column(Integer, db.ForeignKey('blog_posts.id'))
    parent_post = relationship('BlogPost', back_populates="comments")


Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)

s = Session()

@app.route('/')
def get_all_posts():
    posts = s.query(BlogPost).all()
    return render_template("index.html", all_posts=posts, current_user=current_user)


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)

    return decorated_function


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if s.query(User).filter_by(email=form.email.data).first():
            # user already in db
            flash("You have already signed up with that email, log in instead")
            return redirect(url_for('login'))

        hash_password = generate_password_hash(form.password.data, method='pbkdf2:sha256', salt_length=8)
        new_user = User(
            email=form.email.data,
            password=hash_password,
            name=form.name.data
        )
        s.add(new_user)
        s.commit()

        login_user(new_user)
        return redirect(url_for("get_all_posts"))

    return render_template("register.html", form=form, current_user=current_user)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        # Login and validate the user.
        # user should be an instance of your `User` class
        email = form.email.data
        password = form.password.data
        # name = form.name.data
        user = s.query(User).filter_by(email=email).first()

        if not user:
            flash("That email is not registered, please try again.")
            return redirect(url_for('login'))
        elif not check_password_hash(user.password, password):
            flash("Incorrect password, please try again.")
            return redirect(url_for('login'))
        else:

            login_user(user)

            return redirect(url_for('get_all_posts'))

    return render_template('login.html', form=form, current_user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    form = CommentForm()
    requested_post = s.query(BlogPost).get(post_id)
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))
        new_comment = Comment(
            text=form.comment_text.data,
            comment_author=current_user,
            parent_post=requested_post
        )
        s.add(new_comment)
        s.commit()

    form.comment_text.data = ""
    return render_template("post.html", post=requested_post, current_user=current_user, form=form)


@app.route("/about")
def about():
    return render_template("about.html", current_user=current_user)


@app.route("/contact")
def contact():
    return render_template("contact.html", current_user=current_user)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        s.add(new_post)
        s.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, current_user=current_user)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = s.query(BlogPost).get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        # author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        # post.author = edit_form.author.data
        post.body = edit_form.body.data
        s.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, current_user=current_user)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = s.query(BlogPost).get(post_id)
    s.delete(post_to_delete)
    s.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
