from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    EqualTo,
    InputRequired,
    Length,
    NumberRange,
    Optional,
    Regexp,
    URL,
    ValidationError,
)
from wtforms.validators import (
    DataRequired,
    EqualTo,
    Length,
    NumberRange,
    Optional,
    Regexp,
    URL,
    ValidationError,
)

from models import User


class RegisterForm(FlaskForm):
    username = StringField(
        "아이디",
        validators=[
            DataRequired(message="아이디를 입력해 주세요."),
            Length(
                min=4,
                max=20,
                message="아이디는 4자 이상 20자 이하로 입력해 주세요.",
            ),
            Regexp(
                r"^[a-zA-Z0-9_]+$",
                message="아이디는 영문, 숫자, 밑줄만 사용할 수 있습니다.",
            ),
        ],
    )

    display_name = StringField(
        "이름",
        validators=[
            DataRequired(message="이름을 입력해 주세요."),
            Length(
                min=2,
                max=20,
                message="이름은 2자 이상 20자 이하로 입력해 주세요.",
            ),
        ],
    )

    password = PasswordField(
        "비밀번호",
        validators=[
            DataRequired(message="비밀번호를 입력해 주세요."),
            Length(
                min=8,
                max=64,
                message="비밀번호는 8자 이상 64자 이하로 입력해 주세요.",
            ),
            Regexp(
                r"^(?=.*[A-Za-z])(?=.*\d).+$",
                message="비밀번호에는 영문과 숫자가 각각 하나 이상 포함되어야 합니다.",
            ),
        ],
    )

    password_confirm = PasswordField(
        "비밀번호 확인",
        validators=[
            DataRequired(message="비밀번호 확인을 입력해 주세요."),
            EqualTo(
                "password",
                message="비밀번호와 비밀번호 확인이 일치하지 않습니다.",
            ),
        ],
    )

    submit = SubmitField("회원가입")

    def validate_username(self, field: StringField) -> None:
        username = field.data.strip().lower()

        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            raise ValidationError("이미 사용 중인 아이디입니다.")


class LoginForm(FlaskForm):
    username = StringField(
        "아이디",
        validators=[
            DataRequired(message="아이디를 입력해 주세요."),
            Length(
                min=4,
                max=20,
                message="올바른 아이디를 입력해 주세요.",
            ),
        ],
    )

    password = PasswordField(
        "비밀번호",
        validators=[
            DataRequired(message="비밀번호를 입력해 주세요."),
            Length(
                min=8,
                max=64,
                message="올바른 비밀번호를 입력해 주세요.",
            ),
        ],
    )

    remember = BooleanField("로그인 상태 유지")

    submit = SubmitField("로그인")

class ProfileForm(FlaskForm):
    display_name = StringField(
        "이름",
        validators=[
            DataRequired(message="이름을 입력해 주세요."),
            Length(
                min=2,
                max=20,
                message="이름은 2자 이상 20자 이하로 입력해 주세요.",
            ),
        ],
    )

    bio = StringField(
        "소개글",
        validators=[
            Length(
                max=300,
                message="소개글은 300자 이하로 입력해 주세요.",
            ),
        ],
    )

    submit = SubmitField("프로필 저장")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(
        "현재 비밀번호",
        validators=[
            DataRequired(message="현재 비밀번호를 입력해 주세요."),
        ],
    )

    new_password = PasswordField(
        "새 비밀번호",
        validators=[
            DataRequired(message="새 비밀번호를 입력해 주세요."),
            Length(
                min=8,
                max=64,
                message="비밀번호는 8자 이상 64자 이하로 입력해 주세요.",
            ),
            Regexp(
                r"^(?=.*[A-Za-z])(?=.*\d).+$",
                message="비밀번호에는 영문과 숫자가 각각 하나 이상 포함되어야 합니다.",
            ),
        ],
    )

    new_password_confirm = PasswordField(
        "새 비밀번호 확인",
        validators=[
            DataRequired(message="새 비밀번호 확인을 입력해 주세요."),
            EqualTo(
                "new_password",
                message="새 비밀번호가 일치하지 않습니다.",
            ),
        ],
    )

    submit = SubmitField("비밀번호 변경")

class ProductForm(FlaskForm):
    title = StringField(
        "상품명",
        validators=[
            DataRequired(message="상품명을 입력해 주세요."),
            Length(
                min=2,
                max=100,
                message="상품명은 2자 이상 100자 이하로 입력해 주세요.",
            ),
        ],
    )

    description = TextAreaField(
        "상품 설명",
        validators=[
            DataRequired(message="상품 설명을 입력해 주세요."),
            Length(
                min=10,
                max=2000,
                message="상품 설명은 10자 이상 2,000자 이하로 입력해 주세요.",
            ),
        ],
    )

    price = IntegerField(
        "가격",
        validators=[
            DataRequired(message="가격을 입력해 주세요."),
            NumberRange(
                min=0,
                max=100_000_000,
                message="가격은 0원 이상 1억 원 이하로 입력해 주세요.",
            ),
        ],
    )

    image_url = StringField(
        "상품 이미지 URL",
        validators=[
            Optional(),
            Length(
                max=500,
                message="이미지 주소가 너무 깁니다.",
            ),
            URL(
                message="올바른 URL 형식으로 입력해 주세요.",
                require_tld=False,
            ),
        ],
    )

    status = SelectField(
        "판매 상태",
        choices=[
            ("SELLING", "판매 중"),
            ("SOLD", "판매 완료"),
            ("HIDDEN", "숨김"),
        ],
        validators=[
            DataRequired(message="판매 상태를 선택해 주세요."),
        ],
    )

    submit = SubmitField("상품 저장")


class ProductSearchForm(FlaskForm):
    keyword = StringField(
        "검색어",
        validators=[
            Optional(),
            Length(
                max=100,
                message="검색어는 100자 이하로 입력해 주세요.",
            ),
        ],
    )

    status = SelectField(
        "판매 상태",
        choices=[
            ("", "전체 상태"),
            ("SELLING", "판매 중"),
            ("SOLD", "판매 완료"),
        ],
        validators=[Optional()],
    )

    submit = SubmitField("검색")

class MessageForm(FlaskForm):
    content = TextAreaField(
        "메시지",
        validators=[
            DataRequired(message="메시지 내용을 입력해 주세요."),
            Length(
                min=1,
                max=1000,
                message="메시지는 1자 이상 1,000자 이하로 입력해 주세요.",
            ),
        ],
    )

    submit = SubmitField("메시지 보내기")

class ReportForm(FlaskForm):
    reason = SelectField(
        "신고 사유",
        choices=[
            ("SPAM", "광고 또는 도배"),
            ("FRAUD", "사기 의심"),
            ("ABUSE", "욕설 또는 괴롭힘"),
            ("INAPPROPRIATE", "부적절한 콘텐츠"),
            ("FALSE_INFO", "허위 정보"),
            ("OTHER", "기타"),
        ],
        validators=[
            DataRequired(message="신고 사유를 선택해 주세요."),
        ],
    )

    details = TextAreaField(
        "상세 내용",
        validators=[
            DataRequired(message="신고 상세 내용을 입력해 주세요."),
            Length(
                min=10,
                max=1000,
                message="상세 내용은 10자 이상 1,000자 이하로 입력해 주세요.",
            ),
        ],
    )

    submit = SubmitField("신고 접수")

class TransferForm(FlaskForm):
    receiver_username = StringField(
        "받는 사람 아이디",
        validators=[
            DataRequired(
                message="받는 사람 아이디를 입력해 주세요."
            ),
            Length(
                min=4,
                max=20,
                message="아이디는 4자 이상 20자 이하로 입력해 주세요.",
            ),
            Regexp(
                r"^[a-zA-Z0-9_]+$",
                message="아이디는 영문, 숫자, 밑줄만 사용할 수 있습니다.",
            ),
        ],
    )

    amount = IntegerField(
        "송금할 포인트",
        validators=[
            InputRequired(
                message="송금할 포인트를 입력해 주세요."
            ),
            NumberRange(
                min=1,
                max=100_000_000,
                message="송금액은 1포인트 이상 입력해 주세요.",
            ),
        ],
    )

    memo = StringField(
        "메모",
        validators=[
            Optional(),
            Length(
                max=200,
                message="메모는 200자 이하로 입력해 주세요.",
            ),
        ],
    )

    submit = SubmitField("포인트 송금")