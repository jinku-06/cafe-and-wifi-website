from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    make_response,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)

app = Flask(__name__)


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///cafes.db"
app.config["SECRET_KEY"] = "Your_key_goes_here"
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


class Cafe(db.Model):
    __tablename__ = "cafe"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    map_url = db.Column(db.String(255), nullable=False)
    img_url = db.Column(db.String(255), nullable=True)
    location = db.Column(db.String(100), nullable=False)
    has_sockets = db.Column(db.Boolean, nullable=False)
    has_toilet = db.Column(db.Boolean, nullable=False)
    has_wifi = db.Column(db.Boolean, nullable=False)
    can_take_calls = db.Column(db.Boolean, nullable=False)
    seats = db.Column(db.String(20), nullable=True)
    coffee_price = db.Column(db.String(10), nullable=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"))

    user = db.relationship("User", back_populates="cafe")

    def __repr__(self):
        return f"<Cafe {self.name}>"


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, nullable=False)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    password: Mapped[str] = mapped_column(nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password=password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    cafe = db.relationship("Cafe", back_populates="user")


@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))


with app.app_context():
    db.create_all()


@app.after_request
def add_header(response):
    response.cache_control.no_store = True
    return response


@app.route("/")
@login_required
def home():
    is_admin = False
    if current_user.id == 1:
        is_admin = True
    page = request.args.get("page", 1, type=int)
    cafe_per_page = 8
    sort_by = request.args.get("sort_by", "")

    if sort_by == "location":
        cafes = (
            db.session.query(Cafe)
            .order_by(Cafe.location)
            .paginate(page=page, per_page=cafe_per_page)
        )
    elif sort_by == "price":
        cafes = (
            db.session.query(Cafe)
            .order_by(Cafe.coffee_price)
            .paginate(page=page, per_page=cafe_per_page)
        )
    else:
        cafes = (
            db.session.query(Cafe)
            .order_by(Cafe.id)
            .paginate(page=page, per_page=cafe_per_page)
        )

    return render_template(
        "index.html", cafes_data=cafes, status=True, admin=is_admin, user=current_user
    )


@app.route("/cafe/<int:id>")
@login_required
def cafe(id):
    cafe = Cafe.query.filter_by(id=id).first()
    return render_template("cafe.html", cafe_data=cafe)


@app.route("/search")
def search():
    query = request.args.get("query")
    if query:
        results = (
            Cafe.query.filter(
                Cafe.name.icontains(query) | Cafe.location.icontains(query)
            )
            .order_by(Cafe.id.asc())
            .limit(10)
            .all()
        )
    else:
        results = Cafe.query.limit(20).all()
    return render_template("search_results.html", results=results)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    if request.method == "POST":
        username = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        existing_user = db.session.execute(
            db.select(User).filter((User.email == email) | (User.username == username))
        ).scalar_one_or_none()

        if existing_user:
            flash(
                "User already exists. Please login or choose a different username/email.",
                "danger",
            )
            return redirect(url_for("register"))

        new_user = User(username=username, email=email)
        new_user.set_password(password=password)
        db.session.add(new_user)
        db.session.commit()

        flash("Signup successful! You can now login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = db.session.execute(
            db.select(User).filter_by(email=email)
        ).scalar_one_or_none()

        if user and user.check_password(password):
            login_user(user)
            flash("Login successful! ", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid credentials. Please try again.", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out", "info")
    return redirect("login")


@app.route("/update/<int:id>", methods=["GET", "POST"])
@login_required
def update_cafe(id):
    cafe = Cafe.query.get_or_404(id)
    if current_user.id != 1:
        return redirect("/")

    if request.method == "POST":
        name = request.form.get("name")
        map_url = request.form.get("map_url")
        img_url = request.form.get("img_url")
        location = request.form.get("location")

        has_sockets = True if request.form.get("has_sockets") == "on" else False
        has_toilet = True if request.form.get("has_toilet") == "on" else False
        has_wifi = True if request.form.get("has_wifi") == "on" else False
        can_take_calls = True if request.form.get("can_take_calls") == "on" else False

        seats = request.form.get("seats")
        coffee_price = request.form.get("coffee_price")
        cafe.name = name
        cafe.map_url = map_url
        cafe.img_url = img_url
        cafe.location = location
        cafe.has_sockets = has_sockets
        cafe.has_toilet = has_toilet
        cafe.has_wifi = has_wifi
        cafe.can_take_calls = can_take_calls
        cafe.seats = seats
        cafe.coffee_price = coffee_price
        db.session.commit()
        return redirect(url_for("home"))

    cafe = Cafe.query.filter_by(id=id).first()
    return render_template("update.html", cafe=cafe)


@app.route("/add_cafe", methods=["GET", "POST"])
@login_required
def add_cafe():
    if current_user.id != 1:
        return redirect("/")

    if request.method == "POST":
        name = request.form.get("name")
        map_url = request.form.get("map_url")
        img_url = request.form.get("img_url")
        location = request.form.get("location")

        has_sockets = True if request.form.get("has_sockets") == "on" else False
        has_toilet = True if request.form.get("has_toilet") == "on" else False
        has_wifi = True if request.form.get("has_wifi") == "on" else False
        can_take_calls = True if request.form.get("can_take_calls") == "on" else False
        seats = request.form.get("seats")
        coffee_price = request.form.get("coffee_price")

        new_cafe = Cafe(
            name=name,
            map_url=map_url,
            img_url=img_url,
            location=location,
            has_sockets=has_sockets,
            has_toilet=has_toilet,
            has_wifi=has_wifi,
            can_take_calls=can_take_calls,
            seats=seats,
            coffee_price=coffee_price,
            user_id=current_user.id,
        )
        db.session.add(new_cafe)
        db.session.commit()
        return redirect(url_for("home"))

    return render_template("update.html", cafe=None)


@app.route("/delete/<int:id>")
@login_required
def delete(id):
    if not current_user.id == 1:
        return redirect("/")

    else:
        page = request.args.get("page", 1, type=int)
        d_cafe = db.get_or_404(Cafe, id)
        db.session.delete(d_cafe)
        db.session.commit()
        return redirect(f"/?page={page}")


if __name__ == "__main__":
    app.run(debug=True)
