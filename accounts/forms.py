import logging

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.template import loader

from .models import AccountEmail
from .registration_services import create_pending_registration


logger = logging.getLogger(__name__)


class VietnameseFormErrorMixin:
    """Keep account-form validation concise and consistently Vietnamese."""

    field_labels = {}
    field_help_texts = {}

    error_messages_by_code = {
        "invalid": "Thông tin không hợp lệ",
        "invalid_choice": "Lựa chọn không hợp lệ",
        "max_length": "Nội dung không được vượt quá %(limit_value)s ký tự",
        "min_length": "Nội dung phải có ít nhất %(limit_value)s ký tự",
        "null_characters_not_allowed": "Nội dung không được chứa ký tự rỗng",
        "password_entirely_numeric": "Mật khẩu không được chỉ gồm chữ số",
        "password_mismatch": "Hai mật khẩu không khớp",
        "password_too_common": "Mật khẩu này quá phổ biến",
        "password_too_short": "Mật khẩu phải có ít nhất %(min_length)s ký tự",
        "password_too_similar": "Mật khẩu quá giống thông tin tài khoản",
        "required": "Vui lòng nhập %(field_label)s",
        "unique": "Thông tin này đã được sử dụng",
    }
    field_error_messages = {
        ("email", "invalid"): "Nhập địa chỉ email hợp lệ",
        ("email", "unique"): "Email này đã được sử dụng",
        ("username", "invalid"): (
            "Tên đăng nhập chỉ được chứa chữ cái, chữ số và các ký tự @ . + - _"
        ),
        ("username", "unique"): "Tên đăng nhập này đã được sử dụng",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, label in self.field_labels.items():
            if field_name in self.fields:
                self.fields[field_name].label = label
        for field_name, help_text in self.field_help_texts.items():
            if field_name in self.fields:
                self.fields[field_name].help_text = help_text
        for field_name, field in self.fields.items():
            field.widget.attrs["data-auth-input"] = ""
            if field.help_text:
                field.widget.attrs["aria-describedby"] = f"id_{field_name}_help"
        for field_name in ("password1", "password2", "new_password1", "new_password2"):
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.setdefault("minlength", "8")
        if "password2" in self.fields:
            self.fields["password2"].widget.attrs["data-auth-match"] = "id_password1"
        if "new_password2" in self.fields:
            self.fields["new_password2"].widget.attrs[
                "data-auth-match"
            ] = "id_new_password1"

    def _update_error_attributes(self):
        for field_name, field in self.fields.items():
            described_by = []
            if field.help_text:
                described_by.append(f"id_{field_name}_help")
            if field_name in self.errors:
                described_by.append(f"id_{field_name}_error")
                field.widget.attrs["aria-invalid"] = "true"
            else:
                field.widget.attrs.pop("aria-invalid", None)
            if described_by:
                field.widget.attrs["aria-describedby"] = " ".join(described_by)
            else:
                field.widget.attrs.pop("aria-describedby", None)

    def add_error(self, field, error):
        super().add_error(field, error)
        if hasattr(self, "fields"):
            self._update_error_attributes()

    def full_clean(self):
        super().full_clean()
        for field_name, errors in self._errors.items():
            translated = []
            for error in errors.as_data():
                message = self.field_error_messages.get((field_name, error.code))
                if message is None:
                    message = self.error_messages_by_code.get(error.code)
                if message is None:
                    message = str(error.message)
                params = dict(error.params or {})
                if field_name in self.fields:
                    params["field_label"] = self.fields[field_name].label.lower()
                translated.append(message % params if params else message)
            self._errors[field_name] = self.error_class(
                translated,
                renderer=self.renderer,
                field_id=errors.field_id,
            )
        self._update_error_attributes()


class CodeHeheAuthenticationForm(VietnameseFormErrorMixin, AuthenticationForm):
    field_labels = {"username": "Tên đăng nhập", "password": "Mật khẩu"}
    error_messages = {
        "invalid_login": (
            "Tên đăng nhập hoặc mật khẩu không đúng. Nếu vừa đăng ký, "
            "hãy xác minh email trước"
        ),
        "inactive": (
            "Tên đăng nhập hoặc mật khẩu không đúng. Nếu vừa đăng ký, "
            "hãy xác minh email trước"
        ),
    }


class RegisterForm(VietnameseFormErrorMixin, UserCreationForm):
    field_labels = {
        "username": "Tên đăng nhập",
        "password1": "Mật khẩu",
        "password2": "Nhập lại mật khẩu",
    }
    field_help_texts = {
        "username": (
            "Tối đa 150 ký tự; chỉ dùng chữ cái, chữ số và các ký tự @ . + - _"
        ),
        "password1": (
            "Dùng ít nhất 8 ký tự; không chọn mật khẩu quá phổ biến, "
            "quá giống thông tin tài khoản hoặc chỉ gồm chữ số"
        ),
        "password2": "Nhập lại mật khẩu để xác nhận",
    }
    email = forms.EmailField(
        label="Email",
        help_text="Email này dùng để xác minh tài khoản và khôi phục mật khẩu",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = AccountEmail.normalize(self.cleaned_data["email"])
        if AccountEmail.objects.filter(email=email).exists():
            raise forms.ValidationError("Email này đã được sử dụng")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        if not commit:
            return user
        return create_pending_registration(
            username=user.username,
            email=self.cleaned_data["email"],
            password_hash=user.password,
        )


class EmailAddressForm(VietnameseFormErrorMixin, forms.Form):
    email = forms.EmailField(label="Email")

    def clean_email(self):
        return AccountEmail.normalize(self.cleaned_data["email"])


class VerifiedEmailPasswordResetForm(VietnameseFormErrorMixin, PasswordResetForm):
    def clean_email(self):
        return AccountEmail.normalize(self.cleaned_data["email"])

    def get_users(self, email):
        account_emails = (
            AccountEmail.objects.filter(
                email=AccountEmail.normalize(email),
                verified_at__isnull=False,
                user__is_active=True,
            )
            .select_related("user")
            .only(
                "email",
                "user__id",
                "user__email",
                "user__password",
                "user__is_active",
            )
        )
        for account_email in account_emails:
            if account_email.user.has_usable_password():
                yield account_email.user

    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        try:
            subject = "".join(
                loader.render_to_string(subject_template_name, context).splitlines()
            )
            body = loader.render_to_string(email_template_name, context)
            message = EmailMultiAlternatives(subject, body, from_email, [to_email])
            if html_email_template_name:
                html_body = loader.render_to_string(
                    html_email_template_name,
                    context,
                )
                message.attach_alternative(html_body, "text/html")
            message.send()
        except Exception as error:  # SMTP is an external boundary.
            logger.warning(
                "Password recovery email delivery failed (%s)",
                type(error).__name__,
            )


class CodeHeheSetPasswordForm(VietnameseFormErrorMixin, SetPasswordForm):
    field_labels = {
        "new_password1": "Mật khẩu mới",
        "new_password2": "Nhập lại mật khẩu mới",
    }
    field_help_texts = {
        "new_password1": (
            "Dùng ít nhất 8 ký tự; không chọn mật khẩu quá phổ biến, "
            "quá giống thông tin tài khoản hoặc chỉ gồm chữ số"
        ),
        "new_password2": "Nhập lại mật khẩu mới để xác nhận",
    }
