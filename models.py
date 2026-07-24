from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint
from werkzeug.security import check_password_hash, generate_password_hash


# app.py에서 초기화하여 사용할 데이터베이스 객체
db = SQLAlchemy()


class User(UserMixin, db.Model):
    """플랫폼 사용자 정보를 저장하는 모델."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    # 로그인에 사용하는 고유 아이디
    username = db.Column(
        db.String(30),
        unique=True,
        nullable=False,
        index=True,
    )

    # 화면에 표시되는 이름
    display_name = db.Column(
        db.String(30),
        nullable=False,
    )

    # 실제 비밀번호가 아닌 단방향 해시값만 저장
    password_hash = db.Column(
        db.String(255),
        nullable=False,
    )

    bio = db.Column(
        db.String(300),
        nullable=False,
        default="",
    )

    # USER 또는 ADMIN
    role = db.Column(
        db.String(20),
        nullable=False,
        default="USER",
    )

    # ACTIVE 또는 SUSPENDED
    status = db.Column(
        db.String(20),
        nullable=False,
        default="ACTIVE",
    )

    # 실제 현금이 아닌 플랫폼 내부 가상 포인트
    points = db.Column(
        db.Integer,
        nullable=False,
        default=10000,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "points >= 0",
            name="check_user_points_nonnegative",
        ),
        CheckConstraint(
            "role IN ('USER', 'ADMIN')",
            name="check_user_role",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED')",
            name="check_user_status",
        ),
    )

    def set_password(self, password: str) -> None:
        """비밀번호를 안전한 단방향 해시로 변환하여 저장한다."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """입력된 비밀번호와 저장된 해시값을 비교한다."""
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self) -> bool:
        """휴면·정지 계정은 로그인 상태를 유지할 수 없도록 한다."""
        return self.status == "ACTIVE"

    @property
    def is_admin(self) -> bool:
        return self.role == "ADMIN"

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"

class Product(db.Model):
    """사용자가 등록한 중고 상품 정보."""

    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(
        db.String(100),
        nullable=False,
        index=True,
    )

    description = db.Column(
        db.Text,
        nullable=False,
    )

    price = db.Column(
        db.Integer,
        nullable=False,
    )

    image_url = db.Column(
        db.String(500),
        nullable=True,
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="SELLING",
    )

    is_blocked = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    report_count = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    seller_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    seller = db.relationship(
        "User",
        backref=db.backref(
            "products",
            lazy=True,
            cascade="all, delete-orphan",
        ),
    )

    __table_args__ = (
        CheckConstraint(
            "price >= 0",
            name="check_product_price_nonnegative",
        ),
        CheckConstraint(
            "report_count >= 0",
            name="check_product_report_count_nonnegative",
        ),
        CheckConstraint(
            "status IN ('SELLING', 'SOLD', 'HIDDEN')",
            name="check_product_status",
        ),
    )

    @property
    def is_available(self) -> bool:
        return (
            self.status == "SELLING"
            and not self.is_blocked
        )

    def __repr__(self) -> str:
        return f"<Product id={self.id} title={self.title!r}>"

class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    content = db.Column(
        db.Text,
        nullable=False,
    )

    sender_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    receiver_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=True,
        index=True,
    )

    is_read = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    sender = db.relationship(
        "User",
        foreign_keys=[sender_id],
        backref=db.backref(
            "sent_messages",
            lazy="dynamic",
        ),
    )

    receiver = db.relationship(
        "User",
        foreign_keys=[receiver_id],
        backref=db.backref(
            "received_messages",
            lazy="dynamic",
        ),
    )

    product = db.relationship(
        "Product",
        backref=db.backref(
            "messages",
            lazy="dynamic",
        ),
    )

    __table_args__ = (
        CheckConstraint(
            "sender_id != receiver_id",
            name="ck_message_sender_receiver_different",
        ),
        CheckConstraint(
            "length(content) >= 1",
            name="ck_message_content_not_empty",
        ),
    )

class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    reason = db.Column(
        db.String(50),
        nullable=False,
    )

    details = db.Column(
        db.Text,
        nullable=False,
        default="",
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="PENDING",
        index=True,
    )

    reporter_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    reported_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    reported_product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=True,
        index=True,
    )

    admin_note = db.Column(
        db.Text,
        nullable=False,
        default="",
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    resolved_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    reporter = db.relationship(
        "User",
        foreign_keys=[reporter_id],
        backref=db.backref(
            "submitted_reports",
            lazy="dynamic",
        ),
    )

    reported_user = db.relationship(
        "User",
        foreign_keys=[reported_user_id],
        backref=db.backref(
            "received_reports",
            lazy="dynamic",
        ),
    )

    reported_product = db.relationship(
        "Product",
        foreign_keys=[reported_product_id],
        backref=db.backref(
            "received_reports",
            lazy="dynamic",
        ),
    )

    __table_args__ = (
        CheckConstraint(
            """
            (
                reported_user_id IS NOT NULL
                AND reported_product_id IS NULL
            )
            OR
            (
                reported_user_id IS NULL
                AND reported_product_id IS NOT NULL
            )
            """,
            name="ck_report_exactly_one_target",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'RESOLVED', 'REJECTED')",
            name="ck_report_valid_status",
        ),
        CheckConstraint(
            "length(reason) >= 1",
            name="ck_report_reason_not_empty",
        ),
    )

class Transfer(db.Model):
    __tablename__ = "transfers"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    amount = db.Column(
        db.Integer,
        nullable=False,
    )

    memo = db.Column(
        db.String(200),
        nullable=False,
        default="",
    )

    sender_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    receiver_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    sender = db.relationship(
        "User",
        foreign_keys=[sender_id],
        backref=db.backref(
            "sent_transfers",
            lazy="dynamic",
        ),
    )

    receiver = db.relationship(
        "User",
        foreign_keys=[receiver_id],
        backref=db.backref(
            "received_transfers",
            lazy="dynamic",
        ),
    )

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_transfer_amount_positive",
        ),
        CheckConstraint(
            "sender_id != receiver_id",
            name="ck_transfer_different_users",
        ),
    )