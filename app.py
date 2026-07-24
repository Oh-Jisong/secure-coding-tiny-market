import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import and_, func, or_, select, update

from forms import (
    ChangePasswordForm,
    LoginForm,
    MessageForm,
    ProductForm,
    ProductSearchForm,
    ProfileForm,
    RegisterForm,
    ReportForm,
    TransferForm,
)
from models import (
    Message,
    Product,
    Report,
    Transfer,
    User,
    db,
)


login_manager = LoginManager()
csrf = CSRFProtect()


def load_or_create_secret_key(app: Flask) -> str:
    environment_secret = os.environ.get("SECRET_KEY")

    if environment_secret:
        return environment_secret

    instance_path = Path(app.instance_path)
    instance_path.mkdir(parents=True, exist_ok=True)

    secret_file = instance_path / ".secret_key"

    if secret_file.exists():
        return secret_file.read_text(
            encoding="utf-8"
        ).strip()

    generated_secret = secrets.token_hex(32)

    secret_file.write_text(
        generated_secret,
        encoding="utf-8",
    )

    try:
        secret_file.chmod(0o600)
    except OSError:
        pass

    return generated_secret


def is_safe_redirect_url(target: str | None) -> bool:
    if not target:
        return False

    host_url = request.host_url
    reference_url = urlsplit(host_url)
    test_url = urlsplit(
        urljoin(host_url, target)
    )

    return (
        test_url.scheme in {"http", "https"}
        and reference_url.netloc == test_url.netloc
    )


def admin_required(view_function):
    @wraps(view_function)
    @login_required
    def wrapped_view(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)

        return view_function(*args, **kwargs)

    return wrapped_view


def create_app() -> Flask:
    app = Flask(__name__)

    app.config["SECRET_KEY"] = (
        load_or_create_secret_key(app)
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///tiny_market.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = (
        os.environ.get("FLASK_ENV") == "production"
    )

    app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"
    app.config["REMEMBER_COOKIE_SECURE"] = (
        os.environ.get("FLASK_ENV") == "production"
    )

    app.config["PERMANENT_SESSION_LIFETIME"] = (
        timedelta(hours=2)
    )

    app.config["REMEMBER_COOKIE_DURATION"] = (
        timedelta(days=7)
    )

    app.config["MAX_CONTENT_LENGTH"] = (
        2 * 1024 * 1024
    )

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "login"
    login_manager.login_message = (
        "로그인이 필요한 기능입니다."
    )
    login_manager.login_message_category = "warning"

    @app.before_request
    def block_suspended_session():
        if (
            current_user.is_authenticated
            and current_user.status != "ACTIVE"
        ):
            logout_user()

            flash(
                "이용이 제한된 계정입니다.",
                "error",
            )

            return redirect(
                url_for("login")
            )

        return None

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = (
            "nosniff"
        )

        response.headers["X-Frame-Options"] = (
            "SAMEORIGIN"
        )

        response.headers["Referrer-Policy"] = (
            "strict-origin-when-cross-origin"
        )

        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )

        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' https: data:; "
            "style-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "font-src 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'self'; "
            "base-uri 'self'"
        )

        if request.endpoint not in {"static"}:
            response.headers["Cache-Control"] = (
                "no-store"
            )

        return response

    @app.errorhandler(403)
    def forbidden_error(error):
        return (
            render_template(
                "errors/403.html"
            ),
            403,
        )

    @app.errorhandler(404)
    def not_found_error(error):
        return (
            render_template(
                "errors/404.html"
            ),
            404,
        )

    @app.errorhandler(413)
    def request_too_large_error(error):
        flash(
            "요청 데이터의 크기가 너무 큽니다.",
            "error",
        )

        return (
            render_template(
                "errors/413.html"
            ),
            413,
        )

    @app.errorhandler(500)
    def internal_server_error(error):
        db.session.rollback()

        return (
            render_template(
                "errors/500.html"
            ),
            500,
        )

    @app.get("/")
    def index():
        return render_template(
            "index.html"
        )

    @app.route(
        "/register",
        methods=["GET", "POST"],
    )
    def register():
        if current_user.is_authenticated:
            return redirect(
                url_for("index")
            )

        form = RegisterForm()

        if form.validate_on_submit():
            username = (
                form.username.data
                .strip()
                .lower()
            )

            display_name = (
                form.display_name.data
                .strip()
            )

            existing_user = db.session.scalar(
                select(User).where(
                    User.username == username
                )
            )

            if existing_user is not None:
                form.username.errors.append(
                    "이미 사용 중인 아이디입니다."
                )

                return render_template(
                    "register.html",
                    form=form,
                )

            user = User(
                username=username,
                display_name=display_name,
            )

            user.set_password(
                form.password.data
            )

            db.session.add(user)
            db.session.commit()

            flash(
                "회원가입이 완료되었습니다. "
                "로그인해 주세요.",
                "success",
            )

            return redirect(
                url_for("login")
            )

        return render_template(
            "register.html",
            form=form,
        )

    @app.route(
        "/login",
        methods=["GET", "POST"],
    )
    def login():
        if current_user.is_authenticated:
            return redirect(
                url_for("index")
            )

        form = LoginForm()

        if form.validate_on_submit():
            username = (
                form.username.data
                .strip()
                .lower()
            )

            user = db.session.scalar(
                select(User).where(
                    User.username == username
                )
            )

            login_failed = (
                user is None
                or not user.check_password(
                    form.password.data
                )
            )

            if login_failed:
                flash(
                    "아이디 또는 비밀번호가 "
                    "올바르지 않습니다.",
                    "error",
                )

                return render_template(
                    "login.html",
                    form=form,
                )

            if user.status != "ACTIVE":
                flash(
                    "이용이 제한된 계정입니다.",
                    "error",
                )

                return render_template(
                    "login.html",
                    form=form,
                )

            login_user(
                user,
                remember=form.remember.data,
            )

            flash(
                f"{user.display_name}님, 환영합니다.",
                "success",
            )

            next_url = request.args.get(
                "next"
            )

            if is_safe_redirect_url(next_url):
                return redirect(next_url)

            return redirect(
                url_for("index")
            )

        return render_template(
            "login.html",
            form=form,
        )

    @app.post("/logout")
    def logout():
        if current_user.is_authenticated:
            logout_user()

            flash(
                "로그아웃되었습니다.",
                "success",
            )

        return redirect(
            url_for("index")
        )

    @app.route(
        "/mypage",
        methods=["GET", "POST"],
    )
    @login_required
    def mypage():
        profile_form = ProfileForm(
            prefix="profile"
        )

        password_form = ChangePasswordForm(
            prefix="password"
        )

        if (
            profile_form.submit.data
            and profile_form.validate_on_submit()
        ):
            current_user.display_name = (
                profile_form
                .display_name
                .data
                .strip()
            )

            current_user.bio = (
                profile_form.bio.data or ""
            ).strip()

            db.session.commit()

            flash(
                "프로필이 수정되었습니다.",
                "success",
            )

            return redirect(
                url_for("mypage")
            )

        if (
            password_form.submit.data
            and password_form.validate_on_submit()
        ):
            if not current_user.check_password(
                password_form
                .current_password
                .data
            ):
                password_form.current_password.errors.append(
                    "현재 비밀번호가 올바르지 않습니다."
                )

            elif current_user.check_password(
                password_form
                .new_password
                .data
            ):
                password_form.new_password.errors.append(
                    "새 비밀번호는 현재 비밀번호와 "
                    "다르게 설정해 주세요."
                )

            else:
                current_user.set_password(
                    password_form
                    .new_password
                    .data
                )

                db.session.commit()

                flash(
                    "비밀번호가 변경되었습니다.",
                    "success",
                )

                return redirect(
                    url_for("mypage")
                )

        if not profile_form.is_submitted():
            profile_form.display_name.data = (
                current_user.display_name
            )

            profile_form.bio.data = (
                current_user.bio
            )

        return render_template(
            "mypage.html",
            profile_form=profile_form,
            password_form=password_form,
        )

    @app.get("/products")
    def product_list():
        form = ProductSearchForm(
            request.args,
            meta={"csrf": False},
        )

        keyword = (
            request.args.get("keyword")
            or ""
        ).strip()

        status = (
            request.args.get("status")
            or ""
        ).strip()

        query = select(Product).where(
            Product.is_blocked.is_(False),
            Product.status != "HIDDEN",
        )

        if keyword:
            safe_keyword = keyword[:100]

            query = query.where(
                Product.title.contains(
                    safe_keyword,
                    autoescape=True,
                )
            )

        if status in {
            "SELLING",
            "SOLD",
        }:
            query = query.where(
                Product.status == status
            )

        query = query.order_by(
            Product.created_at.desc()
        )

        products = db.session.scalars(
            query
        ).all()

        return render_template(
            "products/list.html",
            form=form,
            products=products,
            keyword=keyword,
            selected_status=status,
        )

    @app.route(
        "/products/new",
        methods=["GET", "POST"],
    )
    @login_required
    def product_create():
        form = ProductForm()

        if form.validate_on_submit():
            product = Product(
                title=form.title.data.strip(),
                description=(
                    form.description.data.strip()
                ),
                price=form.price.data,
                image_url=(
                    form.image_url.data or ""
                ).strip() or None,
                status=form.status.data,
                seller_id=current_user.id,
            )

            db.session.add(product)
            db.session.commit()

            flash(
                "상품이 등록되었습니다.",
                "success",
            )

            return redirect(
                url_for(
                    "product_detail",
                    product_id=product.id,
                )
            )

        return render_template(
            "products/form.html",
            form=form,
            page_title="새 상품 등록",
            submit_label="상품 등록",
        )

    @app.get(
        "/products/<int:product_id>"
    )
    def product_detail(
        product_id: int,
    ):
        product = db.session.get(
            Product,
            product_id,
        )

        if product is None:
            abort(404)

        can_manage = (
            current_user.is_authenticated
            and (
                current_user.id
                == product.seller_id
                or current_user.is_admin
            )
        )

        if (
            product.is_blocked
            or product.status == "HIDDEN"
        ) and not can_manage:
            abort(404)

        return render_template(
            "products/detail.html",
            product=product,
            can_manage=can_manage,
        )

    @app.route(
        "/products/<int:product_id>/edit",
        methods=["GET", "POST"],
    )
    @login_required
    def product_edit(
        product_id: int,
    ):
        product = db.session.get(
            Product,
            product_id,
        )

        if product is None:
            abort(404)

        if (
            current_user.id
            != product.seller_id
            and not current_user.is_admin
        ):
            abort(403)

        form = ProductForm(
            obj=product
        )

        if form.validate_on_submit():
            product.title = (
                form.title.data.strip()
            )

            product.description = (
                form.description.data.strip()
            )

            product.price = (
                form.price.data
            )

            product.image_url = (
                form.image_url.data or ""
            ).strip() or None

            product.status = (
                form.status.data
            )

            db.session.commit()

            flash(
                "상품 정보가 수정되었습니다.",
                "success",
            )

            return redirect(
                url_for(
                    "product_detail",
                    product_id=product.id,
                )
            )

        return render_template(
            "products/form.html",
            form=form,
            page_title="상품 수정",
            submit_label="수정 저장",
            product=product,
        )

    @app.post(
        "/products/<int:product_id>/delete"
    )
    @login_required
    def product_delete(
        product_id: int,
    ):
        product = db.session.get(
            Product,
            product_id,
        )

        if product is None:
            abort(404)

        if (
            current_user.id
            != product.seller_id
            and not current_user.is_admin
        ):
            abort(403)

        db.session.delete(product)
        db.session.commit()

        flash(
            "상품이 삭제되었습니다.",
            "success",
        )

        return redirect(
            url_for("product_list")
        )

    @app.get("/messages")
    @login_required
    def message_list():
        users = db.session.scalars(
            select(User)
            .where(
                User.id != current_user.id,
                User.status == "ACTIVE",
            )
            .order_by(
                User.display_name.asc()
            )
        ).all()

        recent_messages = {}

        for user in users:
            last_message = db.session.scalar(
                select(Message)
                .where(
                    or_(
                        and_(
                            Message.sender_id
                            == current_user.id,
                            Message.receiver_id
                            == user.id,
                        ),
                        and_(
                            Message.sender_id
                            == user.id,
                            Message.receiver_id
                            == current_user.id,
                        ),
                    )
                )
                .order_by(
                    Message.created_at.desc()
                )
                .limit(1)
            )

            unread_count = db.session.scalar(
                select(
                    func.count(Message.id)
                ).where(
                    Message.sender_id == user.id,
                    Message.receiver_id
                    == current_user.id,
                    Message.is_read.is_(False),
                )
            )

            recent_messages[user.id] = {
                "message": last_message,
                "unread_count": (
                    unread_count or 0
                ),
            }

        return render_template(
            "messages/list.html",
            users=users,
            recent_messages=recent_messages,
        )

    @app.route(
        "/messages/<int:user_id>",
        methods=["GET", "POST"],
    )
    @login_required
    def message_room(
        user_id: int,
    ):
        other_user = db.session.get(
            User,
            user_id,
        )

        if other_user is None:
            abort(404)

        if other_user.id == current_user.id:
            flash(
                "자기 자신에게는 메시지를 "
                "보낼 수 없습니다.",
                "warning",
            )

            return redirect(
                url_for("message_list")
            )

        if other_user.status != "ACTIVE":
            abort(404)

        form = MessageForm()

        if form.validate_on_submit():
            message = Message(
                content=(
                    form.content.data.strip()
                ),
                sender_id=current_user.id,
                receiver_id=other_user.id,
            )

            db.session.add(message)
            db.session.commit()

            flash(
                "메시지를 보냈습니다.",
                "success",
            )

            return redirect(
                url_for(
                    "message_room",
                    user_id=other_user.id,
                )
            )

        messages = db.session.scalars(
            select(Message)
            .where(
                or_(
                    and_(
                        Message.sender_id
                        == current_user.id,
                        Message.receiver_id
                        == other_user.id,
                    ),
                    and_(
                        Message.sender_id
                        == other_user.id,
                        Message.receiver_id
                        == current_user.id,
                    ),
                )
            )
            .order_by(
                Message.created_at.asc()
            )
        ).all()

        has_unread_messages = False

        for message in messages:
            if (
                message.receiver_id
                == current_user.id
                and not message.is_read
            ):
                message.is_read = True
                has_unread_messages = True

        if has_unread_messages:
            db.session.commit()

        return render_template(
            "messages/room.html",
            other_user=other_user,
            messages=messages,
            form=form,
        )

    @app.route(
        "/products/<int:product_id>/report",
        methods=["GET", "POST"],
    )
    @login_required
    def report_product(
        product_id: int,
    ):
        product = db.session.get(
            Product,
            product_id,
        )

        if product is None:
            abort(404)

        if (
            product.is_blocked
            or product.status == "HIDDEN"
        ):
            abort(404)

        if (
            product.seller_id
            == current_user.id
        ):
            flash(
                "자신이 등록한 상품은 "
                "신고할 수 없습니다.",
                "warning",
            )

            return redirect(
                url_for(
                    "product_detail",
                    product_id=product.id,
                )
            )

        existing_report = db.session.scalar(
            select(Report).where(
                Report.reporter_id
                == current_user.id,
                Report.reported_product_id
                == product.id,
                Report.status == "PENDING",
            )
        )

        if existing_report is not None:
            flash(
                "이미 처리 대기 중인 "
                "신고가 있습니다.",
                "warning",
            )

            return redirect(
                url_for(
                    "product_detail",
                    product_id=product.id,
                )
            )

        form = ReportForm()

        if form.validate_on_submit():
            report = Report(
                reason=form.reason.data,
                details=(
                    form.details.data.strip()
                ),
                reporter_id=current_user.id,
                reported_product_id=product.id,
            )

            product.report_count += 1

            db.session.add(report)
            db.session.commit()

            flash(
                "상품 신고가 접수되었습니다.",
                "success",
            )

            return redirect(
                url_for(
                    "product_detail",
                    product_id=product.id,
                )
            )

        return render_template(
            "reports/form.html",
            form=form,
            page_title="상품 신고",
            target_title=product.title,
            target_type="상품",
            cancel_url=url_for(
                "product_detail",
                product_id=product.id,
            ),
        )

    @app.route(
        "/users/<int:user_id>/report",
        methods=["GET", "POST"],
    )
    @login_required
    def report_user(
        user_id: int,
    ):
        reported_user = db.session.get(
            User,
            user_id,
        )

        if reported_user is None:
            abort(404)

        if (
            reported_user.id
            == current_user.id
        ):
            flash(
                "자기 자신은 신고할 수 없습니다.",
                "warning",
            )

            return redirect(
                url_for("message_list")
            )

        if reported_user.status != "ACTIVE":
            abort(404)

        existing_report = db.session.scalar(
            select(Report).where(
                Report.reporter_id
                == current_user.id,
                Report.reported_user_id
                == reported_user.id,
                Report.status == "PENDING",
            )
        )

        if existing_report is not None:
            flash(
                "이미 처리 대기 중인 "
                "신고가 있습니다.",
                "warning",
            )

            return redirect(
                url_for(
                    "message_room",
                    user_id=reported_user.id,
                )
            )

        form = ReportForm()

        if form.validate_on_submit():
            report = Report(
                reason=form.reason.data,
                details=(
                    form.details.data.strip()
                ),
                reporter_id=current_user.id,
                reported_user_id=reported_user.id,
            )

            db.session.add(report)
            db.session.commit()

            flash(
                "사용자 신고가 접수되었습니다.",
                "success",
            )

            return redirect(
                url_for(
                    "message_room",
                    user_id=reported_user.id,
                )
            )

        return render_template(
            "reports/form.html",
            form=form,
            page_title="사용자 신고",
            target_title=(
                reported_user.display_name
            ),
            target_type="사용자",
            cancel_url=url_for(
                "message_room",
                user_id=reported_user.id,
            ),
        )

    @app.route(
        "/transfers",
        methods=["GET", "POST"],
    )
    @login_required
    def transfer_page():
        form = TransferForm()

        if request.method == "GET":
            receiver_username = (
                request.args.get("to")
                or ""
            ).strip().lower()

            if receiver_username:
                form.receiver_username.data = (
                    receiver_username[:20]
                )

        if form.validate_on_submit():
            receiver_username = (
                form.receiver_username
                .data
                .strip()
                .lower()
            )

            amount = form.amount.data

            memo = (
                form.memo.data or ""
            ).strip()

            receiver = db.session.scalar(
                select(User).where(
                    User.username
                    == receiver_username
                )
            )

            if receiver is None:
                form.receiver_username.errors.append(
                    "받는 사람을 찾을 수 없습니다."
                )

            elif receiver.id == current_user.id:
                form.receiver_username.errors.append(
                    "자기 자신에게는 송금할 수 없습니다."
                )

            elif receiver.status != "ACTIVE":
                form.receiver_username.errors.append(
                    "현재 송금할 수 없는 사용자입니다."
                )

            else:
                try:
                    sender_result = (
                        db.session.execute(
                            update(User)
                            .where(
                                User.id
                                == current_user.id,
                                User.status
                                == "ACTIVE",
                                User.points
                                >= amount,
                            )
                            .values(
                                points=(
                                    User.points - amount
                                )
                            )
                        )
                    )

                    if sender_result.rowcount != 1:
                        db.session.rollback()

                        form.amount.errors.append(
                            "보유 포인트가 부족합니다."
                        )

                    else:
                        receiver_result = (
                            db.session.execute(
                                update(User)
                                .where(
                                    User.id
                                    == receiver.id,
                                    User.status
                                    == "ACTIVE",
                                )
                                .values(
                                    points=(
                                        User.points + amount
                                    )
                                )
                            )
                        )

                        if (
                            receiver_result.rowcount
                            != 1
                        ):
                            db.session.rollback()

                            form.receiver_username.errors.append(
                                "현재 송금할 수 없는 사용자입니다."
                            )

                        else:
                            transfer = Transfer(
                                amount=amount,
                                memo=memo,
                                sender_id=current_user.id,
                                receiver_id=receiver.id,
                            )

                            db.session.add(
                                transfer
                            )

                            db.session.commit()

                            flash(
                                f"{receiver.display_name}님에게 "
                                f"{amount:,}P를 송금했습니다.",
                                "success",
                            )

                            return redirect(
                                url_for(
                                    "transfer_page"
                                )
                            )

                except Exception:
                    db.session.rollback()
                    raise

        transfers = db.session.scalars(
            select(Transfer)
            .where(
                or_(
                    Transfer.sender_id
                    == current_user.id,
                    Transfer.receiver_id
                    == current_user.id,
                )
            )
            .order_by(
                Transfer.created_at.desc()
            )
        ).all()

        db.session.refresh(
            current_user
        )

        return render_template(
            "transfers/index.html",
            form=form,
            transfers=transfers,
        )

    @app.get("/admin")
    @admin_required
    def admin_dashboard():
        users = db.session.scalars(
            select(User).order_by(
                User.created_at.desc()
            )
        ).all()

        products = db.session.scalars(
            select(Product).order_by(
                Product.created_at.desc()
            )
        ).all()

        reports = db.session.scalars(
            select(Report).order_by(
                Report.created_at.desc()
            )
        ).all()

        messages = db.session.scalars(
            select(Message).order_by(
                Message.created_at.desc()
            )
        ).all()

        transfers = db.session.scalars(
            select(Transfer).order_by(
                Transfer.created_at.desc()
            )
        ).all()

        pending_report_count = (
            db.session.scalar(
                select(
                    func.count(Report.id)
                ).where(
                    Report.status == "PENDING"
                )
            )
            or 0
        )

        active_user_count = (
            db.session.scalar(
                select(
                    func.count(User.id)
                ).where(
                    User.status == "ACTIVE"
                )
            )
            or 0
        )

        blocked_product_count = (
            db.session.scalar(
                select(
                    func.count(Product.id)
                ).where(
                    Product.is_blocked.is_(True)
                )
            )
            or 0
        )

        message_count = (
            db.session.scalar(
                select(
                    func.count(Message.id)
                )
            )
            or 0
        )

        transfer_count = (
            db.session.scalar(
                select(
                    func.count(Transfer.id)
                )
            )
            or 0
        )

        return render_template(
            "admin/dashboard.html",
            users=users,
            products=products,
            reports=reports,
            messages=messages,
            transfers=transfers,
            pending_report_count=pending_report_count,
            active_user_count=active_user_count,
            blocked_product_count=blocked_product_count,
            message_count=message_count,
            transfer_count=transfer_count,
        )

    @app.post(
        "/admin/users/<int:user_id>/toggle-status"
    )
    @admin_required
    def admin_toggle_user_status(
        user_id: int,
    ):
        user = db.session.get(
            User,
            user_id,
        )

        if user is None:
            abort(404)

        if user.id == current_user.id:
            flash(
                "현재 로그인한 관리자 계정은 "
                "정지할 수 없습니다.",
                "warning",
            )

            return redirect(
                url_for("admin_dashboard")
            )

        if user.role == "ADMIN":
            flash(
                "관리자 계정은 정지할 수 없습니다.",
                "warning",
            )

            return redirect(
                url_for("admin_dashboard")
            )

        if user.status == "ACTIVE":
            user.status = "SUSPENDED"
            message = (
                "사용자 계정이 정지되었습니다."
            )

        else:
            user.status = "ACTIVE"
            message = (
                "사용자 계정이 복구되었습니다."
            )

        db.session.commit()

        flash(
            message,
            "success",
        )

        return redirect(
            url_for("admin_dashboard")
        )

    @app.post(
        "/admin/products/<int:product_id>/toggle-block"
    )
    @admin_required
    def admin_toggle_product_block(
        product_id: int,
    ):
        product = db.session.get(
            Product,
            product_id,
        )

        if product is None:
            abort(404)

        product.is_blocked = (
            not product.is_blocked
        )

        if product.is_blocked:
            message = (
                "상품이 차단되었습니다."
            )
        else:
            message = (
                "상품 차단이 해제되었습니다."
            )

        db.session.commit()

        flash(
            message,
            "success",
        )

        return redirect(
            url_for("admin_dashboard")
        )

    @app.post(
        "/admin/reports/<int:report_id>/process"
    )
    @admin_required
    def admin_process_report(
        report_id: int,
    ):
        report = db.session.get(
            Report,
            report_id,
        )

        if report is None:
            abort(404)

        if report.status != "PENDING":
            flash(
                "이미 처리된 신고입니다.",
                "warning",
            )

            return redirect(
                url_for("admin_dashboard")
            )

        action = (
            request.form.get("action")
            or ""
        ).strip().upper()

        admin_note = (
            request.form.get("admin_note")
            or ""
        ).strip()[:500]

        if action not in {
            "RESOLVE",
            "REJECT",
        }:
            abort(400)

        report.admin_note = admin_note
        report.resolved_at = (
            datetime.now(timezone.utc)
        )

        if action == "REJECT":
            report.status = "REJECTED"

            db.session.commit()

            flash(
                "신고가 반려되었습니다.",
                "success",
            )

            return redirect(
                url_for("admin_dashboard")
            )

        report.status = "RESOLVED"

        if (
            report.reported_product_id
            is not None
        ):
            product = db.session.get(
                Product,
                report.reported_product_id,
            )

            if product is not None:
                product.is_blocked = True

        if (
            report.reported_user_id
            is not None
        ):
            reported_user = db.session.get(
                User,
                report.reported_user_id,
            )

            if (
                reported_user is not None
                and reported_user.role
                != "ADMIN"
            ):
                reported_user.status = (
                    "SUSPENDED"
                )

        db.session.commit()

        flash(
            "신고가 승인되고 대상이 "
            "차단되었습니다.",
            "success",
        )

        return redirect(
            url_for("admin_dashboard")
        )

    with app.app_context():
        db.create_all()

    return app


@login_manager.user_loader
def load_user(
    user_id: str,
):
    if not user_id.isdigit():
        return None

    return db.session.get(
        User,
        int(user_id),
    )


app = create_app()


if __name__ == "__main__":
    debug_mode = (
        os.environ.get(
            "FLASK_DEBUG",
            "0",
        )
        == "1"
    )

    app.run(
        host="127.0.0.1",
        port=5001,
        debug=debug_mode,
    )
