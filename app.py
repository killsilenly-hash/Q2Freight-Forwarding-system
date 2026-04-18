from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_file,
    flash,
    session,
)
import os
import uuid
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
import re
from datetime import datetime, date, timedelta
import pandas as pd
from io import BytesIO
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(   
    __name__, static_folder="trade_ops_system/static", static_url_path="/static"
)

# =========================
# FILE UPLOAD CONFIG
# =========================

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB
ALLOWED_FILE_EXTENSIONS = {
    "pdf",
    "xls",
    "xlsx",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.secret_key = os.getenv("SECRET_KEY", "export_system_secret_key")

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "sqlite:///database.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(200), nullable=False)
    company_prefix = db.Column(db.String(20), nullable=False, unique=True)
    number_lead_digit = db.Column(db.String(10), nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    jobs = db.relationship("Job", backref="company_ref", lazy=True)


class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)

    office_phone = db.Column(db.String(50))
    address = db.Column(db.Text)

    import_pic = db.Column(db.String(200))
    export_pic = db.Column(db.String(200))
    email = db.Column(db.String(200))
    mobile = db.Column(db.String(50))
    intercom = db.Column(db.String(50))

    is_active = db.Column(db.Boolean, default=True)
    jobs = db.relationship("Job", back_populates="client")


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_number = db.Column(db.String(50), unique=True, nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
    job_type = db.Column(db.String(50), nullable=False)
    workflow_template = db.Column(db.String(100), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    description = db.Column(db.Text, nullable=True)

    created_date = db.Column(db.Date, nullable=True)
    etd = db.Column(db.Date, nullable=True)
    eta = db.Column(db.Date, nullable=True)
    delivery_date = db.Column(db.Date, nullable=True)

    date_received = db.Column(db.Date, nullable=True)
    customer_name = db.Column(db.String(200), nullable=True)
    customer_po = db.Column(db.String(200), nullable=True)
    product_name = db.Column(db.String(200), nullable=True)
    quantity = db.Column(db.String(100), nullable=True)
    packaging_type = db.Column(db.String(100), nullable=True)
    destination_country = db.Column(db.String(100), nullable=True)
    incoterm = db.Column(db.String(50), nullable=True)
    vessel_flight = db.Column(db.String(200), nullable=True)
    requested_ship_date = db.Column(db.Date, nullable=True)
    pic = db.Column(db.String(100), nullable=True)

    last_updated_by = db.Column(db.String(100), nullable=True)
    last_updated_at = db.Column(db.DateTime, nullable=True)

    company = db.relationship("Company")
    client = db.relationship("Client", back_populates="jobs")


class JobStep(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False)
    step_order = db.Column(db.Integer, nullable=False)
    step_name = db.Column(db.String(255), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    job = db.relationship("Job", backref="steps")


class JobNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False)
    note_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    job = db.relationship("Job", backref="notes")

class JobFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    saved_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)

    uploaded_at = db.Column(db.DateTime, default=datetime.now)

    job = db.relationship("Job", backref="files") 


class ClientContact(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)

    contact_name = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(100))  # Import PIC / Export PIC / Finance etc

    email = db.Column(db.String(200))
    mobile = db.Column(db.String(50))
    office_phone = db.Column(db.String(50))
    intercom = db.Column(db.String(50))

    is_active = db.Column(db.Boolean, default=True)

    client = db.relationship("Client", backref="contacts")


class User(db.Model):
    avatar = db.Column(db.String(200), nullable=True)
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="staff")
    is_active = db.Column(db.Boolean, default=True)

    can_edit_companies = db.Column(db.Boolean, default=False)
    can_delete_companies_request = db.Column(db.Boolean, default=False)
    can_edit_clients = db.Column(db.Boolean, default=False)
    can_delete_clients_request = db.Column(db.Boolean, default=False)
    can_edit_client_contacts = db.Column(db.Boolean, default=False)

    can_create_jobs = db.Column(db.Boolean, default=False)
    can_edit_jobs = db.Column(db.Boolean, default=False)
    can_delete_job_files = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class AccountRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    requested_at = db.Column(db.DateTime, default=datetime.now)

    status = db.Column(db.String(20), nullable=False, default="pending")

    reviewed_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    reviewed_by = db.relationship(
        "User",
        foreign_keys=[reviewed_by_user_id],
        backref="account_requests_reviewed",
    )


class DeleteRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_type = db.Column(db.String(50), nullable=False)
    item_id = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text, nullable=False)

    status = db.Column(db.String(20), nullable=False, default="pending")

    requested_by_user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False
    )
    reviewed_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    requested_at = db.Column(db.DateTime, default=datetime.now)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    requested_by = db.relationship(
        "User",
        foreign_keys=[requested_by_user_id],
        backref="delete_requests_submitted",
    )

    reviewed_by = db.relationship(
        "User",
        foreign_keys=[reviewed_by_user_id],
        backref="delete_requests_reviewed",
    )


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)

    item_type = db.Column(db.String(50), nullable=False)
    item_id = db.Column(db.Integer, nullable=True)

    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    user = db.relationship("User", backref="audit_logs")


WORKFLOW_TEMPLATES = {
    "Full Shipment": [
        "Confirm booking",
        "Confirm shipment schedule",
        "Production completed",
        "QC inspection passed",
        "Packing completed",
        "Palletizing completed",
        "Fumigation arranged",
        "Fumigation certificate received",
        "Prepare for loading",
        "Container inspection",
        "Loading completed",
        "Prepare Commercial Invoice",
        "Prepare Packing List",
        "Apply Certificate of Origin",
        "Submit customs declaration",
        "Obtain Bill of Lading",
        "Send shipping documents",
        "Close job",
    ],
    "Documentation Only": [
        "Receive documents from client",
        "Verify documents",
        "Prepare Commercial Invoice",
        "Prepare Packing List",
        "Apply Certificate of Origin",
        "Submit customs declaration",
        "Obtain Bill of Lading",
        "Send documents to client",
        "Close job",
    ],
    "BL Submission Only": [
        "Receive shipping details",
        "Verify shipping details",
        "Submit shipping instruction",
        "Receive draft BL",
        "Verify draft BL",
        "Confirm BL with client",
        "Issue final BL",
        "Close job",
    ],
    "Handling": [
        "Receive purchase order",
        "Confirm supplier documents",
        "Arrange shipment",
        "Receive shipping documents",
        "Submit customs clearance",
        "Arrange delivery",
        "Close job",
    ],
}


def generate_next_numeric(company_prefix, lead_digit):
    jobs = Job.query.all()

    numbers = []
    pattern = re.compile(r"(?:IM|EX)(\d+)$")

    for job in jobs:
        match = pattern.search(job.job_number)
        if match:
            numbers.append(int(match.group(1)))

    if not numbers:
        return "1001"

    last_number = max(numbers)
    next_number = last_number + 1

    return str(next_number)


def create_job_steps(job_id, workflow_template):
    steps = WORKFLOW_TEMPLATES.get(workflow_template, [])
    for index, step_name in enumerate(steps, start=1):
        step = JobStep(job_id=job_id, step_order=index, step_name=step_name)
        db.session.add(step)
    db.session.commit()

def allowed_file(filename):
    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_FILE_EXTENSIONS


def is_previewable_image(filename):
    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in {"png", "jpg", "jpeg", "gif", "webp"}


def is_previewable_pdf(filename):
    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension == "pdf"

def update_job_last_updated(job):
    current_user = get_current_user()

    if current_user:
        job.last_updated_by = current_user.username
    else:
        job.last_updated_by = "System"

    job.last_updated_at = datetime.now()


# =========================
# AUTH HELPERS
# =========================


def get_current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    return User.query.filter_by(id=user_id, is_active=True).first()


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not get_current_user():
            return redirect(url_for("login"))

        return view_func(*args, **kwargs)

    return wrapped_view


def admin_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        user = get_current_user()

        if not user:
            return redirect(url_for("login"))

        if user.role != "admin":
            return render_template(
                "error.html",
                message="You do not have permission to access this page.",
            )

        return view_func(*args, **kwargs)

    return wrapped_view


def has_permission(user, permission_name):
    if not user:
        return False

    if user.role == "admin":
        return True

    return getattr(user, permission_name, False)


@app.context_processor
def inject_current_user():
    current_user = get_current_user()

    pending_account_requests = 0
    pending_delete_requests = 0

    if current_user and current_user.role == "admin":
        pending_account_requests = AccountRequest.query.filter_by(
            status="pending"
        ).count()
        pending_delete_requests = DeleteRequest.query.filter_by(
            status="pending"
        ).count()

    return {
        "current_user": current_user,
        "pending_account_requests": pending_account_requests,
        "pending_delete_requests": pending_delete_requests,
    }


# =========================
# DELETE APPROVAL HELPERS
# =========================


def create_delete_request(item_type, item_id, reason):
    user = get_current_user()

    existing_request = DeleteRequest.query.filter_by(
        item_type=item_type,
        item_id=item_id,
        status="pending",
    ).first()

    if existing_request:
        return False, "A delete request for this record is already pending approval."

    new_request = DeleteRequest(
        item_type=item_type,
        item_id=item_id,
        reason=reason,
        status="pending",
        requested_by_user_id=user.id,
    )

    db.session.add(new_request)
    db.session.commit()

    create_audit_log(
        action="delete_request_submitted",
        item_type=item_type,
        item_id=item_id,
        details=f"Delete request submitted for {item_type} #{item_id}",
    )

    return True, "Delete request submitted for admin approval."


def create_audit_log(action, item_type, item_id=None, details=None):
    user = get_current_user()

    new_log = AuditLog(
        user_id=user.id if user else None,
        action=action,
        item_type=item_type,
        item_id=item_id,
        details=details,
    )

    db.session.add(new_log)
    db.session.commit()


def perform_actual_delete(item_type, item_id):
    if item_type == "company":
        company = Company.query.get_or_404(item_id)

        if company.jobs:
            return (
                False,
                "Cannot delete this company because it is already used in jobs.",
            )

        db.session.delete(company)
        db.session.commit()
        return True, "Company deleted successfully."

    if item_type == "client":
        client = Client.query.get_or_404(item_id)

        if client.jobs:
            return (
                False,
                "Cannot delete this client company because it is used in existing jobs. Set it to Inactive instead.",
            )

        db.session.delete(client)
        db.session.commit()
        return True, "Client company deleted successfully."

    if item_type == "client_contact":
        contact = ClientContact.query.get_or_404(item_id)

        db.session.delete(contact)
        db.session.commit()
        return True, "Client contact deleted successfully."

    return False, "Invalid delete request type."


# =========================
# DATABASE MIGRATION HELPER
# =========================


def run_safe_migrations():
    db.create_all()

    # =========================
    # CLIENT TABLE
    # =========================
    client_columns_result = db.session.execute(text("PRAGMA table_info(client)"))
    client_columns = [row[1] for row in client_columns_result]

    if "address" not in client_columns:
        db.session.execute(text("ALTER TABLE client ADD COLUMN address TEXT"))
        db.session.commit()

    # =========================
    # USER TABLE
    # =========================
    user_columns_result = db.session.execute(text('PRAGMA table_info("user")'))
    user_columns = [row[1] for row in user_columns_result]

    if "avatar" not in user_columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN avatar VARCHAR(200)'))
        db.session.commit()

    if "last_login_at" not in user_columns:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN last_login_at DATETIME'))
        db.session.commit()

    if "can_edit_companies" not in user_columns:
        db.session.execute(
            text('ALTER TABLE "user" ADD COLUMN can_edit_companies BOOLEAN DEFAULT 0')
        )
        db.session.commit()

    if "can_delete_companies_request" not in user_columns:
        db.session.execute(
            text(
                'ALTER TABLE "user" ADD COLUMN can_delete_companies_request BOOLEAN DEFAULT 0'
            )
        )
        db.session.commit()

    if "can_edit_clients" not in user_columns:
        db.session.execute(
            text('ALTER TABLE "user" ADD COLUMN can_edit_clients BOOLEAN DEFAULT 0')
        )
        db.session.commit()

    if "can_delete_clients_request" not in user_columns:
        db.session.execute(
            text(
                'ALTER TABLE "user" ADD COLUMN can_delete_clients_request BOOLEAN DEFAULT 0'
            )
        )
        db.session.commit()

    if "can_edit_client_contacts" not in user_columns:
        db.session.execute(
            text(
                'ALTER TABLE "user" ADD COLUMN can_edit_client_contacts BOOLEAN DEFAULT 0'
            )
        )
        db.session.commit()

    if "can_create_jobs" not in user_columns:
        db.session.execute(
            text('ALTER TABLE "user" ADD COLUMN can_create_jobs BOOLEAN DEFAULT 0')
        )
        db.session.commit()

    if "can_delete_job_files" not in user_columns:
        db.session.execute(
            text('ALTER TABLE "user" ADD COLUMN can_delete_job_files BOOLEAN DEFAULT 0')
        )
        db.session.commit()

# =========================
# JOB FILE TABLE
# =========================
    db.create_all()

    job_file_columns_result = db.session.execute(text("PRAGMA table_info(job_file)"))
    job_file_columns = [row[1] for row in job_file_columns_result]

    if "original_filename" not in job_file_columns:
        db.session.execute(
            text("ALTER TABLE job_file ADD COLUMN original_filename VARCHAR(255)")
        )
        db.session.commit()

    if "saved_filename" not in job_file_columns:
        db.session.execute(
            text("ALTER TABLE job_file ADD COLUMN saved_filename VARCHAR(255)")
        )
        db.session.commit()

    if "original_filename" in job_file_columns:
        db.session.execute(
            text(
                "UPDATE job_file SET original_filename = filename WHERE original_filename IS NULL OR original_filename = ''"
            )
        )
        db.session.commit()

    if "saved_filename" in job_file_columns:
        db.session.execute(
            text(
                "UPDATE job_file SET saved_filename = filename WHERE saved_filename IS NULL OR saved_filename = ''"
            )
        )
        db.session.commit()

    # =========================
    # JOB TABLE
    # =========================
    job_columns_result = db.session.execute(text("PRAGMA table_info(job)"))
    job_columns = [row[1] for row in job_columns_result]

    if "last_updated_by" not in job_columns:
        db.session.execute(
            text("ALTER TABLE job ADD COLUMN last_updated_by VARCHAR(100)")
        )
        db.session.commit()

    if "last_updated_at" not in job_columns:
        db.session.execute(text("ALTER TABLE job ADD COLUMN last_updated_at DATETIME"))
        db.session.commit()

    # =========================
    # DEFAULT USERS (ONLY CREATE ONCE)
    # =========================
        db.session.commit()
# =========================
# UPLOAD FILE
# =========================


@app.route("/upload_job_file/<int:job_id>", methods=["POST"])
@login_required
def upload_job_file(job_id):
    job = Job.query.get_or_404(job_id)

    if "file" not in request.files:
        flash("No file selected.")
        return redirect(url_for("job_detail", job_id=job_id))

    files = request.files.getlist("file")

    valid_files = [file for file in files if file and file.filename.strip()]

    if not valid_files:
        flash("No file selected.")
        return redirect(url_for("job_detail", job_id=job_id))

    uploaded_count = 0

    rejected_files = []

    for file in valid_files:
        original_filename = secure_filename(file.filename)

        if not original_filename:
            continue

        if not allowed_file(original_filename):
            rejected_files.append(original_filename)
            continue

        unique_name = f"{uuid.uuid4().hex}_{original_filename}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)

        file.save(filepath)

        new_file = JobFile(
            job_id=job.id,
            filename=original_filename,
            original_filename=original_filename,
            saved_filename=unique_name,
            file_path=filepath,
        )

        db.session.add(new_file)
        uploaded_count += 1

    db.session.commit()

    if uploaded_count == 1:
        flash("1 file uploaded successfully.")
    elif uploaded_count > 1:
        flash(f"{uploaded_count} files uploaded successfully.")

    if rejected_files:
        flash(
            "These files were not uploaded because the file type is not allowed: "
            + ", ".join(rejected_files)
        )

    return redirect(url_for("job_detail", job_id=job_id))

# ============================
# DOWNLOAD FILE
# ============================

@app.route("/download_job_file/<int:file_id>")
@login_required
def download_job_file(file_id):
    file = JobFile.query.get_or_404(file_id)

    display_name = file.original_filename or file.filename

    return send_file(
        file.file_path,
        as_attachment=True,
        download_name=display_name,
    )

# Preview job file

@app.route("/preview_job_file/<int:file_id>")
@login_required
def preview_job_file(file_id):
    file = JobFile.query.get_or_404(file_id)

    display_name = file.original_filename or file.filename

    return send_file(
        file.file_path,
        as_attachment=False,
        download_name=display_name,
    )

# ============================
# DELETE UPLOAD FILE
# ============================

@app.route("/delete_job_file/<int:file_id>", methods=["POST"])
@login_required
def delete_job_file(file_id):
    file = JobFile.query.get_or_404(file_id)
    current_user = get_current_user()

    if not has_permission(current_user, "can_delete_job_files"):
        return render_template(
            "error.html",
            message="You do not have permission to delete uploaded files.",
        )

    if os.path.exists(file.file_path):
        os.remove(file.file_path)

    job_id = file.job_id

    db.session.delete(file)
    db.session.commit()

    flash("File deleted successfully.")
    return redirect(url_for("job_detail", job_id=job_id))




# ============================
# JOB COMPLETION DATE HELPER
# ============================

def get_job_completion_date(job):
    steps = (
        JobStep.query.filter_by(job_id=job.id).order_by(JobStep.step_order.asc()).all()
    )

    if not steps:
        return None

    total_steps = len(steps)
    completed_steps = [step for step in steps if step.completed]

    if len(completed_steps) != total_steps:
        return None

    completed_dates = [
        step.completed_at for step in completed_steps if step.completed_at
    ]

    if not completed_dates:
        return None

    return max(completed_dates).date()


# =========================
# Format Job Number (Display Only)
# =========================
def format_job_number(job_number):
    if not job_number or len(job_number) < 6:
        return job_number

    prefix = job_number[:2]
    job_type = job_number[2:4]
    number = job_number[4:]

    return f"{prefix} | {job_type} | {number}"


app.jinja_env.globals.update(
    format_job_number=format_job_number,
    has_permission=has_permission,
    is_previewable_image=is_previewable_image,
    is_previewable_pdf=is_previewable_pdf,
)

@app.errorhandler(413)
def file_too_large(error):
    flash("Upload failed. File size must be 10MB or below.")
    return redirect(request.referrer or url_for("dashboard"))


# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user():
        return redirect(url_for("dashboard"))

    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if " " in username or " " in password:
            error = "Username and password cannot contain spaces."
        elif not user or not user.is_active or not user.check_password(password):
            error = "Invalid username or password."
        else:
            user.last_login_at = datetime.now()
            db.session.commit()

            session["user_id"] = user.id
            return redirect(url_for("dashboard"))

    return render_template("login.html", error=error)


# =========================
# REGISTER
# =========================


@app.route("/register", methods=["GET", "POST"])
def register():
    if get_current_user():
        return redirect(url_for("dashboard"))

    error = None
    success_message = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not password or not confirm_password:
            error = "All fields are required."
        elif " " in username:
            error = "Username cannot contain spaces."
        elif " " in password:
            error = "Password cannot contain spaces."
        elif password != confirm_password:
            error = "Passwords do not match."
        elif User.query.filter_by(username=username).first():
            error = "This username is already active in the system."
        elif AccountRequest.query.filter_by(username=username).first():
            error = "This username already has an account request in the system. Please use a different username or ask admin to review the existing request."
        else:
            new_request = AccountRequest(
                username=username,
                password_hash=generate_password_hash(password),
                status="pending",
            )

            try:
                db.session.add(new_request)
                db.session.commit()
                success_message = (
                    "Account request submitted. Waiting for admin approval."
                )
            except Exception:
                db.session.rollback()
                error = (
                    "Unable to submit account request. This username may already exist."
                )

    return render_template(
        "register.html",
        error=error,
        success_message=success_message,
    )


# =========================
# LOGOUT
# =========================


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# =========================
# ACCOUNT REQUESTS
# =========================


@app.route("/account_requests")
@admin_required
def account_requests():
    requests = AccountRequest.query.order_by(
        AccountRequest.status.asc(),
        AccountRequest.requested_at.desc(),
    ).all()

    return render_template("account_requests.html", account_requests=requests)


@app.route("/approve_account_request/<int:request_id>", methods=["POST"])
@admin_required
def approve_account_request(request_id):
    account_request = AccountRequest.query.get_or_404(request_id)

    if account_request.status != "pending":
        return render_template(
            "error.html",
            message="This account request has already been reviewed.",
        )

    existing_user = User.query.filter_by(username=account_request.username).first()

    if existing_user:
        return render_template(
            "error.html",
            message="This username already exists in the system.",
        )

    new_user = User(
        username=account_request.username,
        password_hash=account_request.password_hash,
        role="staff",
        is_active=True,
        avatar="avatars/avatar_01.png",
    )

    db.session.add(new_user)

    user = get_current_user()
    account_request.status = "approved"
    account_request.reviewed_by_user_id = user.id
    account_request.reviewed_at = datetime.now()

    db.session.commit()

    create_audit_log(
        action="approve_account_request",
        item_type="account_request",
        item_id=account_request.id,
        details=f"Approved account request for username: {account_request.username}",
    )

    flash("Account request approved successfully.")
    return redirect(url_for("account_requests"))


@app.route("/reject_account_request/<int:request_id>", methods=["POST"])
@admin_required
def reject_account_request(request_id):
    account_request = AccountRequest.query.get_or_404(request_id)

    if account_request.status != "pending":
        return render_template(
            "error.html",
            message="This account request has already been reviewed.",
        )

    user = get_current_user()
    account_request.status = "rejected"
    account_request.reviewed_by_user_id = user.id
    account_request.reviewed_at = datetime.now()

    db.session.commit()

    create_audit_log(
        action="reject_account_request",
        item_type="account_request",
        item_id=account_request.id,
        details=f"Rejected account request for username: {account_request.username}",
    )

    flash("Account request rejected.")
    return redirect(url_for("account_requests"))


# =========================
# DELETE REQUESTS
# =========================


@app.route("/delete_requests")
@admin_required
def delete_requests():
    requests = DeleteRequest.query.order_by(
        DeleteRequest.status.asc(),
        DeleteRequest.requested_at.desc(),
    ).all()

    return render_template("delete_requests.html", delete_requests=requests)


@app.route("/approve_delete_request/<int:request_id>", methods=["POST"])
@admin_required
def approve_delete_request(request_id):
    delete_request = DeleteRequest.query.get_or_404(request_id)

    if delete_request.status != "pending":
        return render_template(
            "error.html",
            message="This delete request has already been reviewed.",
        )

    success, message = perform_actual_delete(
        delete_request.item_type,
        delete_request.item_id,
    )

    if not success:
        return render_template("error.html", message=message)

    user = get_current_user()
    delete_request.status = "approved"
    delete_request.reviewed_by_user_id = user.id
    delete_request.reviewed_at = datetime.now()

    db.session.commit()
    create_audit_log(
        action="delete_request_approved",
        item_type=delete_request.item_type,
        item_id=delete_request.item_id,
        details=f"Delete request approved for {delete_request.item_type} #{delete_request.item_id}",
    )
    flash("Delete request approved successfully.")
    return redirect(url_for("delete_requests"))


@app.route("/reject_delete_request/<int:request_id>", methods=["POST"])
@admin_required
def reject_delete_request(request_id):
    delete_request = DeleteRequest.query.get_or_404(request_id)

    if delete_request.status != "pending":
        return render_template(
            "error.html",
            message="This delete request has already been reviewed.",
        )

    user = get_current_user()
    delete_request.status = "rejected"
    delete_request.reviewed_by_user_id = user.id
    delete_request.reviewed_at = datetime.now()

    db.session.commit()
    create_audit_log(
        action="delete_request_rejected",
        item_type=delete_request.item_type,
        item_id=delete_request.item_id,
        details=f"Delete request rejected for {delete_request.item_type} #{delete_request.item_id}",
    )
    flash("Delete request rejected.")
    return redirect(url_for("delete_requests"))


# =========================
# DASHBOARD
# =========================


@app.route("/")
@login_required
def dashboard():
    search = request.args.get("search", "").strip()
    company_filter = request.args.get("company", "").strip()
    status_filter = request.args.get("status", "").strip()
    template_filter = request.args.get("template", "").strip()
    sort_by = request.args.get("sort_by", "").strip()
    overdue_filter = request.args.get("overdue", "").strip()
    week_filter = request.args.get("week_filter", "").strip()
    priority_filter = request.args.get("priority", "").strip()
    completion_filter = request.args.get("completion", "").strip()

    jobs_query = Job.query

    if search:
        jobs_query = jobs_query.join(Client).filter(
            db.or_(
                Job.job_number.ilike(f"%{search}%"), Client.name.ilike(f"%{search}%")
            )
        )

    if company_filter:
        jobs_query = jobs_query.filter(Job.company_id == int(company_filter))

    if template_filter:
        jobs_query = jobs_query.filter(Job.workflow_template == template_filter)

    if sort_by == "etd":
        jobs_query = jobs_query.order_by(Job.etd.asc(), Job.id.desc())
    elif sort_by == "eta":
        jobs_query = jobs_query.order_by(Job.eta.asc(), Job.id.desc())
    elif sort_by == "delivery_date":
        jobs_query = jobs_query.order_by(Job.delivery_date.asc(), Job.id.desc())
    else:
        jobs_query = jobs_query.order_by(Job.id.desc())

    jobs = jobs_query.all()

    dashboard_data = []
    critical_alerts = []
    today_alerts = []
    upcoming_alerts = []

    today = date.today()
    week_end = today + timedelta(days=6)
    next_two_days = today + timedelta(days=2)
    recent_completed_cutoff = today - timedelta(days=7)

    # =========================
    # =========================

    for job in jobs:
        steps = (
            JobStep.query.filter_by(job_id=job.id)
            .order_by(JobStep.step_order.asc())
            .all()
        )
        total_steps = len(steps)
        completed_steps = len([step for step in steps if step.completed])

        if total_steps == 0:
            status = "No workflow"
            status_icon = "⚫"
            latest_step = "No workflow"
            next_step = "-"
        elif completed_steps == 0:
            status = "Not started"
            status_icon = "🔴"
            latest_step = "Not started"
            next_step = steps[0].step_name if steps else "-"
        elif completed_steps == total_steps:
            status = "Completed"
            status_icon = "🟢"
            latest_step = "Completed"
            next_step = "-"
        else:
            status = "In progress"
            status_icon = "🟡"

            completed_step_names = [step.step_name for step in steps if step.completed]
            latest_step = (
                completed_step_names[-1] if completed_step_names else "In progress"
            )

            next_pending = [step for step in steps if not step.completed]
            next_step = next_pending[0].step_name if next_pending else "-"

        completed_date = get_job_completion_date(job)

        show_on_dashboard = True

        if status == "Completed":
            if completed_date is None:
                show_on_dashboard = False
            elif completed_date < recent_completed_cutoff:
                show_on_dashboard = False

        if not show_on_dashboard:
            continue

        if status_filter:
            if status_filter != status:
                continue

        etd_overdue = job.etd is not None and job.etd < today and status != "Completed"
        eta_overdue = job.eta is not None and job.eta < today and status != "Completed"
        delivery_overdue = (
            job.delivery_date is not None
            and job.delivery_date < today
            and status != "Completed"
        )

        is_overdue = etd_overdue or eta_overdue or delivery_overdue

        if overdue_filter == "yes" and not is_overdue:
            continue

        etd_urgent = job.etd is not None and today <= job.etd <= today + timedelta(
            days=2
        )
        eta_urgent = job.eta is not None and today <= job.eta <= today + timedelta(
            days=2
        )

        if is_overdue:
            priority = "Critical"
            priority_icon = "🔴"
        elif etd_urgent or eta_urgent:
            priority = "Urgent"
            priority_icon = "🟠"
        else:
            priority = "Normal"
            priority_icon = "🟢"

        if priority_filter and priority_filter != priority:
            continue

        if completion_filter == "active" and status == "Completed":
            continue

        if completion_filter == "completed" and status != "Completed":
            continue

        etd_this_week = job.etd is not None and today <= job.etd <= week_end
        eta_this_week = job.eta is not None and today <= job.eta <= week_end
        delivery_this_week = (
            job.delivery_date is not None and today <= job.delivery_date <= week_end
        )

        if week_filter == "etd" and not etd_this_week:
            continue
        if week_filter == "eta" and not eta_this_week:
            continue
        if week_filter == "delivery" and not delivery_this_week:
            continue

        latest_note_obj = (
            JobNote.query.filter_by(job_id=job.id)
            .order_by(JobNote.created_at.desc())
            .first()
        )
        latest_note = latest_note_obj.note_text if latest_note_obj else ""

        if job.etd is not None and status != "Completed":
            if job.etd < today:
                critical_alerts.append(
                    {
                        "job_id": job.id,
                        "job_number": job.job_number,
                        "client_name": job.client.name if job.client else "",
                        "alert_type": "ETD Overdue",
                        "alert_date": job.etd.strftime("%d %b %Y"),
                    }
                )
            elif job.etd == today:
                today_alerts.append(
                    {
                        "job_id": job.id,
                        "job_number": job.job_number,
                        "client_name": job.client.name if job.client else "",
                        "alert_type": "ETD Today",
                        "alert_date": job.etd.strftime("%d %b %Y"),
                    }
                )
            elif today < job.etd <= next_two_days:
                upcoming_alerts.append(
                    {
                        "job_id": job.id,
                        "job_number": job.job_number,
                        "client_name": job.client.name if job.client else "",
                        "alert_type": "ETD Soon",
                        "alert_date": job.etd.strftime("%d %b %Y"),
                    }
                )

        if job.eta is not None and status != "Completed":
            if job.eta < today:
                critical_alerts.append(
                    {
                        "job_id": job.id,
                        "job_number": job.job_number,
                        "client_name": job.client.name if job.client else "",
                        "alert_type": "ETA Overdue",
                        "alert_date": job.eta.strftime("%d %b %Y"),
                    }
                )
            elif job.eta == today:
                today_alerts.append(
                    {
                        "job_id": job.id,
                        "job_number": job.job_number,
                        "client_name": job.client.name if job.client else "",
                        "alert_type": "ETA Today",
                        "alert_date": job.eta.strftime("%d %b %Y"),
                    }
                )
            elif today < job.eta <= next_two_days:
                upcoming_alerts.append(
                    {
                        "job_id": job.id,
                        "job_number": job.job_number,
                        "client_name": job.client.name if job.client else "",
                        "alert_type": "ETA Soon",
                        "alert_date": job.eta.strftime("%d %b %Y"),
                    }
                )

        if job.delivery_date is not None and status != "Completed":
            if job.delivery_date < today:
                critical_alerts.append(
                    {
                        "job_id": job.id,
                        "job_number": job.job_number,
                        "client_name": job.client.name if job.client else "",
                        "alert_type": "Delivery Overdue",
                        "alert_date": job.delivery_date.strftime("%d %b %Y"),
                    }
                )
            elif job.delivery_date == today:
                today_alerts.append(
                    {
                        "job_id": job.id,
                        "job_number": job.job_number,
                        "client_name": job.client.name if job.client else "",
                        "alert_type": "Delivery Today",
                        "alert_date": job.delivery_date.strftime("%d %b %Y"),
                    }
                )
            elif today < job.delivery_date <= next_two_days:
                upcoming_alerts.append(
                    {
                        "job_id": job.id,
                        "job_number": job.job_number,
                        "client_name": job.client.name if job.client else "",
                        "alert_type": "Delivery Soon",
                        "alert_date": job.delivery_date.strftime("%d %b %Y"),
                    }
                )

        dashboard_data.append(
            {
                "job": job,
                "completed_steps": completed_steps,
                "total_steps": total_steps,
                "status": status,
                "status_icon": status_icon,
                "latest_step": latest_step,
                "next_step": next_step,
                "etd_overdue": etd_overdue,
                "eta_overdue": eta_overdue,
                "delivery_overdue": delivery_overdue,
                "latest_note": latest_note,
                "priority": priority,
                "priority_icon": priority_icon,
                "completed_date": completed_date,
            }
        )

    total_jobs = len(dashboard_data)
    not_started_jobs = len(
        [item for item in dashboard_data if item["status"] == "Not started"]
    )
    in_progress_jobs = len(
        [item for item in dashboard_data if item["status"] == "In progress"]
    )
    completed_jobs = len(
        [item for item in dashboard_data if item["status"] == "Completed"]
    )

    companies = Company.query.order_by(Company.company_name.asc()).all()
    workflow_templates = list(WORKFLOW_TEMPLATES.keys())

    pending_account_requests = AccountRequest.query.filter_by(status="pending").count()
    pending_delete_requests = DeleteRequest.query.filter_by(status="pending").count()
    recent_audit_logs = (
        AuditLog.query.order_by(AuditLog.created_at.desc()).limit(8).all()
    )

    print("TOTAL JOBS:", Job.query.count())
    print("DASHBOARD DATA:", dashboard_data)
    print("DB FILE:", app.config["SQLALCHEMY_DATABASE_URI"])

    pending_account_requests = AccountRequest.query.filter_by(status="pending").count()
    pending_delete_requests = DeleteRequest.query.filter_by(status="pending").count()

    return render_template(
        "dashboard.html",
        dashboard_data=dashboard_data,
        companies=companies,
        workflow_templates=workflow_templates,
        search=search,
        company_filter=company_filter,
        status_filter=status_filter,
        template_filter=template_filter,
        sort_by=sort_by,
        overdue_filter=overdue_filter,
        week_filter=week_filter,
        priority_filter=priority_filter,
        completion_filter=completion_filter,
        total_jobs=total_jobs,
        pending_account_requests=pending_account_requests,
        pending_delete_requests=pending_delete_requests,
        recent_audit_logs=recent_audit_logs,
        not_started_jobs=not_started_jobs,
        in_progress_jobs=in_progress_jobs,
        completed_jobs=completed_jobs,
        critical_alerts=critical_alerts,
        today_alerts=today_alerts,
        upcoming_alerts=upcoming_alerts,
    )


# =========================
# PROFILE
# =========================
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = get_current_user()

    if request.method == "POST":
        selected_avatar = request.form.get("avatar")

        if selected_avatar:
            user.avatar = selected_avatar
            db.session.commit()

            flash("Profile updated successfully.")

        return redirect(url_for("profile"))

    avatar_list = [
        "avatars/avatar_01.png",
        "avatars/avatar_02.png",
        "avatars/avatar_03.png",
        "avatars/avatar_04.png",
        "avatars/avatar_05.png",
        "avatars/avatar_06.png",
        "avatars/avatar_07.png",
        "avatars/avatar_08.png",
        "avatars/avatar_09.png",
        "avatars/avatar_10.png",
        "avatars/avatar_11.png",
        "avatars/avatar_12.png",
    ]

    return render_template(
        "profile.html", avatar_list=avatar_list, current_avatar=user.avatar
    )


# =========================
# USER MANAGEMENT
# =========================
@app.route("/users")
@admin_required
def users():
    all_users = User.query.order_by(User.role.asc(), User.username.asc()).all()
    return render_template("users.html", users=all_users)


@app.route("/toggle_user_status/<int:user_id>", methods=["POST"])
@admin_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    current_user = get_current_user()

    if user.id == current_user.id:
        return render_template(
            "error.html",
            message="You cannot deactivate your own account.",
        )

    if user.role == "admin":
        return render_template(
            "error.html",
            message="Admin account cannot be deactivated from this page.",
        )

    user.is_active = not user.is_active
    db.session.commit()

    status_text = "reactivated" if user.is_active else "deactivated"

    create_audit_log(
        action="toggle_user_status",
        item_type="user",
        item_id=user.id,
        details=f"User {user.username} was {status_text}",
    )

    flash(f"User {user.username} {status_text} successfully.")
    return redirect(url_for("users"))


# =========================
# RESET PASSWORD
# =========================


@app.route("/reset_user_password/<int:user_id>", methods=["POST"])
@admin_required
def reset_user_password(user_id):
    user = User.query.get_or_404(user_id)
    current_user = get_current_user()

    if user.id == current_user.id:
        return render_template(
            "error.html",
            message="You cannot reset your own password here.",
        )

    if user.role == "admin":
        return render_template(
            "error.html",
            message="Admin password cannot be reset from this page.",
        )

    new_password = request.form.get("new_password", "").strip()

    if not new_password:
        flash("Password cannot be empty.")
        return redirect(url_for("users"))

    if " " in new_password:
        flash("Password cannot contain spaces.")
        return redirect(url_for("users"))

    user.set_password(new_password)
    db.session.commit()

    create_audit_log(
        action="reset_user_password",
        item_type="user",
        item_id=user.id,
        details=f"Password reset for user {user.username}",
    )

    flash(f"Password reset successfully for {user.username}.")
    return redirect(url_for("users"))


# =========================
# STAFF PERMISSIONS
# =========================


@app.route("/staff_permissions", methods=["GET", "POST"])
@admin_required
def staff_permissions():
    users = User.query.filter(User.role != "admin").order_by(User.username.asc()).all()

    if request.method == "POST":
        for user in users:
            user.can_edit_companies = f"can_edit_companies_{user.id}" in request.form

            user.can_delete_companies_request = (
                f"can_delete_companies_request_{user.id}" in request.form
            )

            user.can_edit_clients = f"can_edit_clients_{user.id}" in request.form

            user.can_delete_clients_request = (
                f"can_delete_clients_request_{user.id}" in request.form
            )

            user.can_edit_client_contacts = (
                f"can_edit_client_contacts_{user.id}" in request.form
            )

            user.can_create_jobs = f"can_create_jobs_{user.id}" in request.form
            user.can_edit_jobs = f"can_edit_jobs_{user.id}" in request.form
            user.can_delete_job_files = (
                f"can_delete_job_files_{user.id}" in request.form
            )

        db.session.commit()
        flash("Staff permissions updated successfully.")
        return redirect(url_for("staff_permissions"))

    return render_template("staff_permissions.html", users=users)


# =========================
# COMPANY PAGE
# =========================


@app.route("/companies", methods=["GET", "POST"])
@login_required
def companies():
    if request.method == "POST":
        company_name = request.form["company_name"].strip()
        company_prefix = request.form["company_prefix"].strip().upper()
        number_lead_digit = "1"

        new_company = Company(
            company_name=company_name,
            company_prefix=company_prefix,
            number_lead_digit=number_lead_digit,
            is_active=True,
        )

        db.session.add(new_company)
        db.session.commit()

        return redirect("/companies")

    all_companies = Company.query.order_by(Company.company_name.asc()).all()
    return render_template("companies.html", companies=all_companies)


# =========================
# AUDIT LOGS
# =========================
@app.route("/audit_logs")
@login_required
def audit_logs():
    user = get_current_user()

    if user.role != "admin":
        return render_template(
            "error.html",
            message="Only admin can view audit logs.",
        )

    search = request.args.get("search", "").strip()
    action_filter = request.args.get("action", "").strip()
    type_filter = request.args.get("item_type", "").strip()
    user_filter = request.args.get("user_id", "").strip()
    page = request.args.get("page", 1, type=int)

    logs_query = AuditLog.query

    if search:
        logs_query = logs_query.filter(
            db.or_(
                AuditLog.action.ilike(f"%{search}%"),
                AuditLog.item_type.ilike(f"%{search}%"),
                AuditLog.details.ilike(f"%{search}%"),
            )
        )

    if action_filter:
        logs_query = logs_query.filter(AuditLog.action == action_filter)

    if type_filter:
        logs_query = logs_query.filter(AuditLog.item_type == type_filter)

    if user_filter:
        logs_query = logs_query.filter(AuditLog.user_id == int(user_filter))

    per_page = 10

    pagination = logs_query.order_by(AuditLog.created_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )

    logs = pagination.items
    audit_users = User.query.order_by(User.username.asc()).all()

    audit_actions = [
        row[0]
        for row in db.session.query(AuditLog.action)
        .distinct()
        .order_by(AuditLog.action.asc())
        .all()
        if row[0]
    ]

    audit_item_types = [
        row[0]
        for row in db.session.query(AuditLog.item_type)
        .distinct()
        .order_by(AuditLog.item_type.asc())
        .all()
        if row[0]
    ]

    return render_template(
        "audit_logs.html",
        logs=logs,
        pagination=pagination,
        search=search,
        action_filter=action_filter,
        type_filter=type_filter,
        user_filter=user_filter,
        audit_users=audit_users,
        audit_actions=audit_actions,
        audit_item_types=audit_item_types,
    )


# =========================
# EXPORT AUDIT LOGS
# =========================


@app.route("/export_audit_logs")
@admin_required
def export_audit_logs():
    search = request.args.get("search", "").strip()
    action_filter = request.args.get("action", "").strip()
    type_filter = request.args.get("item_type", "").strip()
    user_filter = request.args.get("user_id", "").strip()

    logs_query = AuditLog.query

    if search:
        logs_query = logs_query.filter(
            db.or_(
                AuditLog.action.ilike(f"%{search}%"),
                AuditLog.item_type.ilike(f"%{search}%"),
                AuditLog.details.ilike(f"%{search}%"),
            )
        )

    if action_filter:
        logs_query = logs_query.filter(AuditLog.action == action_filter)

    if type_filter:
        logs_query = logs_query.filter(AuditLog.item_type == type_filter)

    if user_filter:
        logs_query = logs_query.filter(AuditLog.user_id == int(user_filter))

    logs = logs_query.order_by(AuditLog.created_at.desc()).all()

    export_rows = []

    for log in logs:
        export_rows.append(
            {
                "ID": log.id,
                "Date": (
                    log.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    if log.created_at
                    else ""
                ),
                "User": log.user.username if log.user else "System",
                "Action": log.action,
                "Item Type": log.item_type,
                "Item ID": log.item_id if log.item_id else "",
                "Details": log.details if log.details else "",
            }
        )

    df = pd.DataFrame(export_rows)

    output = BytesIO()
    df.to_excel(output, index=False, sheet_name="Audit Logs")
    output.seek(0)

    filename = f"audit_logs_filtered_{datetime.now().strftime('%Y%m%d')}.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# =========================
# COMPLETED JOBS ARCHIVE
# =========================


@app.route("/completed_jobs")
@login_required
def completed_jobs():
    search = request.args.get("search", "").strip()
    company_filter = request.args.get("company", "").strip()
    sort_by = request.args.get("sort_by", "").strip()

    jobs_query = Job.query

    if search:
        jobs_query = jobs_query.join(Client).filter(
            db.or_(
                Job.job_number.ilike(f"%{search}%"), Client.name.ilike(f"%{search}%")
            )
        )

    if company_filter:
        jobs_query = jobs_query.filter(Job.company_id == int(company_filter))

    if sort_by == "etd":
        jobs_query = jobs_query.order_by(Job.etd.asc(), Job.id.desc())
    elif sort_by == "eta":
        jobs_query = jobs_query.order_by(Job.eta.asc(), Job.id.desc())
    elif sort_by == "delivery_date":
        jobs_query = jobs_query.order_by(Job.delivery_date.asc(), Job.id.desc())
    else:
        jobs_query = jobs_query.order_by(Job.id.desc())

    jobs = jobs_query.all()

    today = date.today()
    recent_completed_cutoff = today - timedelta(days=7)

    archive_data = []

    for job in jobs:
        steps = (
            JobStep.query.filter_by(job_id=job.id)
            .order_by(JobStep.step_order.asc())
            .all()
        )
        total_steps = len(steps)
        completed_steps = len([step for step in steps if step.completed])

        if total_steps == 0:
            continue

        if completed_steps != total_steps:
            continue

        completed_date = get_job_completion_date(job)

        if completed_date is None:
            continue

        if completed_date >= recent_completed_cutoff:
            continue

        latest_note_obj = (
            JobNote.query.filter_by(job_id=job.id)
            .order_by(JobNote.created_at.desc())
            .first()
        )
        latest_note = latest_note_obj.note_text if latest_note_obj else ""

        archive_data.append(
            {
                "job": job,
                "completed_steps": completed_steps,
                "total_steps": total_steps,
                "status": "Completed",
                "status_icon": "🟢",
                "latest_step": "Completed",
                "next_step": "-",
                "latest_note": latest_note,
                "completed_date": completed_date,
            }
        )

    companies = Company.query.order_by(Company.company_name.asc()).all()

    return render_template(
        "completed_jobs.html",
        archive_data=archive_data,
        companies=companies,
        search=search,
        company_filter=company_filter,
        sort_by=sort_by,
    )


# =========================
# Export Job
# =========================


@app.route("/export_jobs")
@login_required
def export_jobs():
    search = request.args.get("search", "").strip()
    company_filter = request.args.get("company", "").strip()
    status_filter = request.args.get("status", "").strip()
    template_filter = request.args.get("template", "").strip()
    sort_by = request.args.get("sort_by", "").strip()
    overdue_filter = request.args.get("overdue", "").strip()
    week_filter = request.args.get("week_filter", "").strip()

    jobs_query = Job.query

    if search:
        jobs_query = jobs_query.join(Client).filter(
            db.or_(
                Job.job_number.ilike(f"%{search}%"), Client.name.ilike(f"%{search}%")
            )
        )

    if company_filter:
        jobs_query = jobs_query.filter(Job.company_id == int(company_filter))

    if template_filter:
        jobs_query = jobs_query.filter(Job.workflow_template == template_filter)

    if sort_by == "etd":
        jobs_query = jobs_query.order_by(Job.etd.asc(), Job.id.desc())
    elif sort_by == "eta":
        jobs_query = jobs_query.order_by(Job.eta.asc(), Job.id.desc())
    elif sort_by == "delivery_date":
        jobs_query = jobs_query.order_by(Job.delivery_date.asc(), Job.id.desc())
    else:
        jobs_query = jobs_query.order_by(Job.id.desc())

    jobs = jobs_query.all()

    today = date.today()
    week_end = today + timedelta(days=6)
    recent_completed_cutoff = today - timedelta(days=7)

    export_rows = []

    for job in jobs:

        etd_overdue = False
        eta_overdue = False
        delivery_overdue = False

        steps = (
            JobStep.query.filter_by(job_id=job.id)
            .order_by(JobStep.step_order.asc())
            .all()
        )

        total_steps = len(steps)
        completed_steps = len([step for step in steps if step.completed])

        if total_steps == 0:
            status = "No workflow"
            latest_step = "No workflow"
        elif completed_steps == 0:
            status = "Not started"
            latest_step = "Not started"
        elif completed_steps == total_steps:
            status = "Completed"
            latest_step = "Completed"
        else:
            status = "In progress"
            completed_step_names = [step.step_name for step in steps if step.completed]
            latest_step = (
                completed_step_names[-1] if completed_step_names else "In progress"
            )

        completed_date = get_job_completion_date(job)

        show_on_dashboard = True

        if status == "Completed":
            if completed_date is None:
                show_on_dashboard = False
            elif completed_date < recent_completed_cutoff:
                show_on_dashboard = False

        if not show_on_dashboard:
            continue

        if status_filter:
            if status_filter != status:
                continue

        etd_overdue = job.etd is not None and job.etd < today and status != "Completed"

        eta_overdue = job.eta is not None and job.eta < today and status != "Completed"

        delivery_overdue = (
            job.delivery_date is not None
            and job.delivery_date < today
            and status != "Completed"
        )

        is_overdue = etd_overdue or eta_overdue or delivery_overdue

        if overdue_filter == "yes" and not is_overdue:
            continue

        etd_this_week = job.etd is not None and today <= job.etd <= week_end
        eta_this_week = job.eta is not None and today <= job.eta <= week_end
        delivery_this_week = (
            job.delivery_date is not None and today <= job.delivery_date <= week_end
        )

        if week_filter == "etd" and not etd_this_week:
            continue
        if week_filter == "eta" and not eta_this_week:
            continue
        if week_filter == "delivery" and not delivery_this_week:
            continue

        export_rows.append(
            {
                "Job Number": job.job_number,
                "Company": job.company.company_name if job.company else "",
                "Job Type": job.job_type,
                "Workflow Template": job.workflow_template,
                "Client": job.client.name if job.client else "",
                "Description": job.description or "",
                "Created Date": (
                    job.created_date.strftime("%Y-%m-%d") if job.created_date else ""
                ),
                "ETD": job.etd.strftime("%Y-%m-%d") if job.etd else "",
                "ETA": job.eta.strftime("%Y-%m-%d") if job.eta else "",
                "Delivery Date": (
                    job.delivery_date.strftime("%Y-%m-%d") if job.delivery_date else ""
                ),
                "Status": status,
                "Latest Step": latest_step,
                "Completed Steps": completed_steps,
                "Total Steps": total_steps,
                "Completed Date": (
                    completed_date.strftime("%Y-%m-%d") if completed_date else ""
                ),
                "ETD Overdue": "Yes" if etd_overdue else "No",
                "ETA Overdue": "Yes" if eta_overdue else "No",
                "Delivery Overdue": "Yes" if delivery_overdue else "No",
            }
        )

    df = pd.DataFrame(export_rows)

    output = BytesIO()
    df.to_excel(output, index=False, sheet_name="Jobs")
    output.seek(0)

    filename = f"job_list_{today.strftime('%Y%m%d')}.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# =========================
# EDIT COMPANY
# =========================


@app.route("/edit_company/<int:company_id>", methods=["GET", "POST"])
@login_required
def edit_company(company_id):
    user = get_current_user()

    if not user or user.role != "admin":
        return render_template(
            "error.html",
            message="Only admin can edit company records.",
        )

    company = Company.query.get_or_404(company_id)

    if request.method == "POST":
        company_name = request.form["company_name"].strip()
        company_prefix = request.form["company_prefix"].strip().upper()
        number_lead_digit = "1"
        is_active = True if request.form.get("is_active") == "yes" else False

        existing_company = Company.query.filter(
            Company.company_prefix == company_prefix,
            Company.id != company.id,
        ).first()

        if existing_company:
            return render_template(
                "error.html",
                message=f"Company prefix '{company_prefix}' already exists.",
            )

        changes = []

        if company.company_name != company_name:
            changes.append(
                f"Company Name: {company.company_name if company.company_name else '-'} → {company_name if company_name else '-'}"
            )

        if company.company_prefix != company_prefix:
            changes.append(
                f"Company Prefix: {company.company_prefix if company.company_prefix else '-'} → {company_prefix if company_prefix else '-'}"
            )

        if company.is_active != is_active:
            old_status = "Active" if company.is_active else "Inactive"
            new_status = "Active" if is_active else "Inactive"
            changes.append(f"Status: {old_status} → {new_status}")

        company.company_name = company_name
        company.company_prefix = company_prefix
        company.number_lead_digit = number_lead_digit
        company.is_active = is_active

        db.session.commit()

        change_details = ", ".join(changes) if changes else "No changes"

        create_audit_log(
            action="edit_company",
            item_type="company",
            item_id=company.id,
            details=f"{company.company_name} → {change_details}",
        )
        return redirect("/companies")

    return render_template("edit_company.html", company=company)


# =========================
# DELETE COMPANY
# =========================


@app.route("/delete_company/<int:company_id>", methods=["POST"])
@login_required
def delete_company(company_id):
    user = get_current_user()

    if user.role == "admin":
        success, message = perform_actual_delete("company", company_id)

        if not success:
            return render_template("error.html", message=message)

        flash("Company deleted successfully.")
        return redirect("/companies")

    if not has_permission(user, "can_delete_companies_request"):
        return render_template(
            "error.html",
            message="You do not have permission to submit company delete requests.",
        )

    reason = request.form.get("delete_reason", "").strip()

    if not reason:
        return render_template(
            "error.html",
            message="Delete reason is required before submitting for admin approval.",
        )

    success, message = create_delete_request("company", company_id, reason)

    if not success:
        return render_template("error.html", message=message)

    flash(message)
    return redirect("/companies")


# =========================
# ADD CLIENT
# =========================


@app.route("/clients", methods=["GET", "POST"])
@login_required
def clients():
    search = request.args.get("search", "").strip()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        office_phone = request.form.get("office_phone", "").strip()
        address = request.form.get("address", "").strip()

        all_clients = Client.query.order_by(Client.name.asc()).all()

        if not name:
            return render_template(
                "clients.html",
                clients=all_clients,
                error="Client Company name is required.",
                search=search,
            )

        existing_client = Client.query.filter(
            db.func.lower(Client.name) == name.lower()
        ).first()

        if existing_client:
            return render_template(
                "clients.html",
                clients=all_clients,
                error="Client Company name already exists. Please use a different name.",
                search=search,
            )

        new_client = Client(
            name=name,
            office_phone=office_phone,
            address=address,
            is_active=True,
        )

        db.session.add(new_client)
        db.session.commit()

        return redirect(url_for("clients"))

    if search:
        all_clients = (
            Client.query.filter(
                db.or_(
                    Client.name.ilike(f"%{search}%"),
                    Client.office_phone.ilike(f"%{search}%"),
                    Client.address.ilike(f"%{search}%"),
                )
            )
            .order_by(Client.name.asc())
            .all()
        )
    else:
        all_clients = Client.query.order_by(Client.name.asc()).all()

    return render_template(
        "clients.html",
        clients=all_clients,
        error=None,
        search=search,
    )


# =========================
# QUICK ADD CLIENT CONTACT
# =========================


@app.route("/quick_add_client_contact", methods=["POST"])
@login_required
def quick_add_client_contact():
    client_id = request.form.get("client_id", "").strip()
    contact_name = request.form.get("contact_name", "").strip()
    role = request.form.get("role", "").strip()
    email = request.form.get("email", "").strip()
    mobile = request.form.get("mobile", "").strip()
    office_phone = request.form.get("office_phone", "").strip()
    intercom = request.form.get("intercom", "").strip()

    if not client_id:
        return {"success": False, "message": "Please select a client first."}, 400

    if not contact_name:
        return {"success": False, "message": "Contact name is required."}, 400

    existing_contact = ClientContact.query.filter_by(
        client_id=client_id, contact_name=contact_name
    ).first()

    if existing_contact:
        return {
            "success": False,
            "message": "This contact already exists for the selected client.",
        }, 400

    new_contact = ClientContact(
        client_id=client_id,
        contact_name=contact_name,
        role=role,
        email=email,
        mobile=mobile,
        office_phone=office_phone,
        intercom=intercom,
        is_active=True,
    )

    db.session.add(new_contact)
    db.session.commit()

    label = (
        f"{new_contact.contact_name} ({new_contact.role})"
        if new_contact.role
        else new_contact.contact_name
    )

    return {
        "success": True,
        "message": "Contact added successfully.",
        "contact": {
            "id": new_contact.id,
            "name": new_contact.contact_name,
            "role": new_contact.role if new_contact.role else "",
            "label": label,
        },
    }


# =========================
# CLIENT CONTACTS
# =========================


@app.route("/client_contacts", methods=["GET", "POST"])
@login_required
def client_contacts():
    search = request.args.get("search", "").strip()

    clients = Client.query.filter_by(is_active=True).order_by(Client.name.asc()).all()

    if request.method == "POST":
        client_id = request.form.get("client_id", "").strip()
        contact_name = request.form.get("contact_name", "").strip()
        role = request.form.get("role", "").strip()
        email = request.form.get("email", "").strip()
        mobile = request.form.get("mobile", "").strip()
        office_phone = request.form.get("office_phone", "").strip()
        intercom = request.form.get("intercom", "").strip()

        contacts_query = ClientContact.query.join(Client)

        if search:
            contacts_query = contacts_query.filter(
                db.or_(
                    Client.name.ilike(f"%{search}%"),
                    ClientContact.contact_name.ilike(f"%{search}%"),
                    ClientContact.role.ilike(f"%{search}%"),
                    ClientContact.email.ilike(f"%{search}%"),
                    ClientContact.mobile.ilike(f"%{search}%"),
                    ClientContact.office_phone.ilike(f"%{search}%"),
                    ClientContact.intercom.ilike(f"%{search}%"),
                )
            )

        contacts = contacts_query.order_by(
            Client.name.asc(), ClientContact.contact_name.asc()
        ).all()

        if not client_id or not contact_name:
            return render_template(
                "client_contacts.html",
                clients=clients,
                contacts=contacts,
                error="Client and Contact Name are required.",
                search=search,
            )

        client = Client.query.get(client_id)

        if not client:
            return render_template(
                "client_contacts.html",
                clients=clients,
                contacts=contacts,
                error="Selected client was not found.",
                search=search,
            )

        existing_contact = ClientContact.query.filter_by(
            client_id=client.id, contact_name=contact_name
        ).first()

        if existing_contact:
            return render_template(
                "client_contacts.html",
                clients=clients,
                contacts=contacts,
                error="This contact already exists for the selected client.",
                search=search,
            )

        new_contact = ClientContact(
            client_id=client.id,
            contact_name=contact_name,
            role=role,
            email=email,
            mobile=mobile,
            office_phone=office_phone,
            intercom=intercom,
            is_active=True,
        )

        db.session.add(new_contact)
        db.session.commit()

        return redirect("/client_contacts")

    contacts_query = ClientContact.query.join(Client)

    if search:
        contacts_query = contacts_query.filter(
            db.or_(
                Client.name.ilike(f"%{search}%"),
                ClientContact.contact_name.ilike(f"%{search}%"),
                ClientContact.role.ilike(f"%{search}%"),
                ClientContact.email.ilike(f"%{search}%"),
                ClientContact.mobile.ilike(f"%{search}%"),
                ClientContact.office_phone.ilike(f"%{search}%"),
                ClientContact.intercom.ilike(f"%{search}%"),
            )
        )

    contacts = contacts_query.order_by(
        Client.name.asc(), ClientContact.contact_name.asc()
    ).all()

    return render_template(
        "client_contacts.html",
        clients=clients,
        contacts=contacts,
        error=None,
        search=search,
    )


# =========================
# EDIT CLIENT
# =========================


@app.route("/edit_client_contact/<int:contact_id>", methods=["GET", "POST"])
@login_required
def edit_client_contact(contact_id):
    user = get_current_user()

    if not user or user.role != "admin":
        return render_template(
            "error.html",
            message="Only admin can edit client contacts.",
        )
    contact = ClientContact.query.get_or_404(contact_id)
    clients = Client.query.filter_by(is_active=True).order_by(Client.name.asc()).all()

    if request.method == "POST":
        new_client_id = request.form["client_id"]
        new_contact_name = request.form["contact_name"].strip()
        new_role = request.form["role"].strip()
        new_email = request.form["email"].strip()
        new_mobile = request.form["mobile"].strip()
        new_office_phone = request.form["office_phone"].strip()
        new_intercom = request.form["intercom"].strip()

        changes = []

        old_client = Client.query.get(contact.client_id)
        new_client = Client.query.get(new_client_id)

        old_client_name = old_client.name if old_client else str(contact.client_id)
        new_client_name = new_client.name if new_client else str(new_client_id)

        if str(contact.client_id) != str(new_client_id):
            changes.append(f"Client: {old_client_name} → {new_client_name}")

        if contact.contact_name != new_contact_name:
            changes.append(
                f"Contact Name: {contact.contact_name if contact.contact_name else '-'} → {new_contact_name if new_contact_name else '-'}"
            )

        if contact.role != new_role:
            changes.append(
                f"Role: {contact.role if contact.role else '-'} → {new_role if new_role else '-'}"
            )

        if contact.email != new_email:
            changes.append(
                f"Email: {contact.email if contact.email else '-'} → {new_email if new_email else '-'}"
            )

        if contact.mobile != new_mobile:
            changes.append(
                f"Mobile: {contact.mobile if contact.mobile else '-'} → {new_mobile if new_mobile else '-'}"
            )

        if contact.office_phone != new_office_phone:
            changes.append(
                f"Office Phone: {contact.office_phone if contact.office_phone else '-'} → {new_office_phone if new_office_phone else '-'}"
            )

        if contact.intercom != new_intercom:
            changes.append(
                f"Intercom: {contact.intercom if contact.intercom else '-'} → {new_intercom if new_intercom else '-'}"
            )

        contact.client_id = new_client_id
        contact.contact_name = new_contact_name
        contact.role = new_role
        contact.email = new_email
        contact.mobile = new_mobile
        contact.office_phone = new_office_phone
        contact.intercom = new_intercom

        db.session.commit()

        change_details = ", ".join(changes) if changes else "No changes"

        create_audit_log(
            action="edit_client_contact",
            item_type="client_contact",
            item_id=contact.id,
            details=f"{contact.contact_name} → {change_details}",
        )

        return redirect(url_for("client_contacts"))

    return render_template(
        "edit_client_contact.html",
        contact=contact,
        clients=clients,
    )


# =========================
# EDIT CLIENT COMPANY
# =========================


@app.route("/edit_client/<int:client_id>", methods=["GET", "POST"])
@login_required
def edit_client(client_id):
    user = get_current_user()

    if not user or user.role != "admin":
        return render_template(
            "error.html",
            message="Only admin can edit client companies.",
        )
    client = Client.query.get_or_404(client_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        office_phone = request.form.get("office_phone", "").strip()
        address = request.form.get("address", "").strip()
        is_active = True if request.form.get("is_active") == "yes" else False

        if not name:
            return render_template(
                "edit_client_company.html",
                client=client,
                error="Client Company Name is required.",
            )

        existing_client = Client.query.filter(
            db.func.lower(Client.name) == name.lower(), Client.id != client.id
        ).first()

        if existing_client:
            return render_template(
                "edit_client_company.html",
                client=client,
                error="Client Company name already exists. Please use a different name.",
            )

        changes = []

        if client.name != name:
            changes.append(
                f"Client Name: {client.name if client.name else '-'} → {name if name else '-'}"
            )

        if client.office_phone != office_phone:
            changes.append(
                f"Office Phone: {client.office_phone if client.office_phone else '-'} → {office_phone if office_phone else '-'}"
            )

        if client.address != address:
            changes.append(
                f"Address: {client.address if client.address else '-'} → {address if address else '-'}"
            )

        if client.is_active != is_active:
            old_status = "Active" if client.is_active else "Inactive"
            new_status = "Active" if is_active else "Inactive"
            changes.append(f"Status: {old_status} → {new_status}")

        client.name = name
        client.office_phone = office_phone
        client.address = address
        client.is_active = is_active

        db.session.commit()

        change_details = ", ".join(changes) if changes else "No changes"

        create_audit_log(
            action="edit_client",
            item_type="client",
            item_id=client.id,
            details=f"{client.name} → {change_details}",
        )
        return redirect(url_for("clients"))

    return render_template(
        "edit_client_company.html",
        client=client,
        error=None,
    )


# =========================
# DELETE CLIENT CONTACT
# =========================


@app.route("/delete_client_contact/<int:contact_id>", methods=["POST"])
@login_required
def delete_client_contact(contact_id):
    user = get_current_user()

    if user.role == "admin":
        success, message = perform_actual_delete("client_contact", contact_id)

        if not success:
            return render_template("error.html", message=message)

        flash("Client contact deleted successfully.")
        return redirect(url_for("client_contacts"))

    reason = request.form.get("delete_reason", "").strip()

    if not reason:
        return render_template(
            "error.html",
            message="Delete reason is required before submitting for admin approval.",
        )

    success, message = create_delete_request("client_contact", contact_id, reason)

    if not success:
        return render_template("error.html", message=message)

    flash(message)
    return redirect(url_for("client_contacts"))


# =========================
# DELETE CLIENT
# =========================


@app.route("/delete_client/<int:client_id>", methods=["POST"])
@login_required
def delete_client(client_id):
    user = get_current_user()

    if user.role == "admin":
        success, message = perform_actual_delete("client", client_id)

        if not success:
            clients = Client.query.order_by(Client.name.asc()).all()
            return render_template(
                "clients.html",
                clients=clients,
                error=message,
                search="",
            )

        flash("Client company deleted successfully.")
        return redirect(url_for("clients"))

    reason = request.form.get("delete_reason", "").strip()

    if not reason:
        clients = Client.query.order_by(Client.name.asc()).all()
        return render_template(
            "clients.html",
            clients=clients,
            error="Delete reason is required before submitting for admin approval.",
            search="",
        )

    success, message = create_delete_request("client", client_id, reason)

    if not success:
        clients = Client.query.order_by(Client.name.asc()).all()
        return render_template(
            "clients.html",
            clients=clients,
            error=message,
            search="",
        )

    flash(message)
    return redirect(url_for("clients"))


# =========================
# CREATE JOB
# =========================


@app.route("/create_job", methods=["GET", "POST"])
@login_required
def create_job():
    companies = Company.query.filter_by(is_active=True).all()
    clients = Client.query.filter_by(is_active=True).all()
    contacts = ClientContact.query.filter_by(is_active=True).all()

    if request.method == "POST":
        company_id = request.form["company_id"]
        job_type = request.form["job_type"]
        workflow_template = request.form["workflow_template"]
        client_id = request.form["client_id"]
        description = request.form["description"]

        created_date = request.form.get("created_date", "").strip()
        etd = request.form.get("etd", "").strip()
        eta = request.form.get("eta", "").strip()
        delivery_date = request.form.get("delivery_date", "").strip()

        date_received = request.form.get("date_received", "").strip()
        customer_name = request.form.get("customer_name", "").strip()
        customer_po = request.form.get("customer_po", "").strip()
        product_name = request.form.get("product_name", "").strip()
        quantity = request.form.get("quantity", "").strip()
        packaging_type = request.form.get("packaging_type", "").strip()
        destination_country = request.form.get("destination_country", "").strip()
        incoterm = request.form.get("incoterm", "").strip()
        vessel_flight = request.form.get("vessel_flight", "").strip()
        requested_ship_date = request.form.get("requested_ship_date", "").strip()
        pic = request.form.get("pic", "").strip()

        company = Company.query.get(company_id)

        type_code = "IM" if job_type == "Import" else "EX"
        next_numeric = generate_next_numeric(
            company.company_prefix, company.number_lead_digit
        )
        job_number = f"{company.company_prefix}{type_code}{next_numeric}"

        current_user = get_current_user()

        job = Job(
            job_number=job_number,
            company_id=company_id,
            job_type=job_type,
            workflow_template=workflow_template,
            client_id=client_id,
            description=description,
            created_date=(
                datetime.strptime(created_date, "%Y-%m-%d").date()
                if created_date
                else None
            ),
            etd=datetime.strptime(etd, "%Y-%m-%d").date() if etd else None,
            eta=datetime.strptime(eta, "%Y-%m-%d").date() if eta else None,
            delivery_date=(
                datetime.strptime(delivery_date, "%Y-%m-%d").date()
                if delivery_date
                else None
            ),
            date_received=(
                datetime.strptime(date_received, "%Y-%m-%d").date()
                if date_received
                else None
            ),
            customer_name=customer_name,
            customer_po=customer_po,
            product_name=product_name,
            quantity=quantity,
            packaging_type=packaging_type,
            destination_country=destination_country,
            incoterm=incoterm,
            vessel_flight=vessel_flight,
            requested_ship_date=(
                datetime.strptime(requested_ship_date, "%Y-%m-%d").date()
                if requested_ship_date
                else None
            ),
            pic=pic,
            last_updated_by=current_user.username if current_user else "System",
            last_updated_at=datetime.now(),
        )

        db.session.add(job)
        db.session.commit()

        create_audit_log(
            action="create_job",
            item_type="job",
            item_id=job.id,
            details=f"Job {job.job_number} created",
        )

        steps = WORKFLOW_TEMPLATES.get(workflow_template, [])
        for index, step_name in enumerate(steps, start=1):
            step = JobStep(
                job_id=job.id,
                step_order=index,
                step_name=step_name,
                completed=False,
            )
            db.session.add(step)

        db.session.commit()
        return redirect(url_for("dashboard"))

    return render_template(
        "create_job.html",
        companies=companies,
        clients=clients,
        contacts=contacts,
        workflow_templates=WORKFLOW_TEMPLATES.keys(),
    )


# =========================
# GET CLIENT CONTACTS (AJAX)
# =========================


@app.route("/get_client_contacts/<int:client_id>")
def get_client_contacts(client_id):
    contacts = (
        ClientContact.query.filter_by(client_id=client_id, is_active=True)
        .order_by(ClientContact.contact_name.asc())
        .all()
    )

    contact_list = []

    for contact in contacts:
        if contact.role and contact.role.strip():
            label = f"{contact.contact_name} ({contact.role})"
        else:
            label = contact.contact_name

        contact_list.append(
            {
                "id": contact.id,
                "name": contact.contact_name,
                "role": contact.role if contact.role else "",
                "label": label,
            }
        )

    return {"contacts": contact_list}


# =========================
# PREVIEW JOB
# =========================


@app.route("/preview_job_number")
@login_required
def preview_job_number():
    company_id = request.args.get("company_id")
    job_type = request.args.get("job_type")

    if not company_id or not job_type:
        return {"job_number": ""}

    company = Company.query.get(company_id)
    if not company:
        return {"job_number": ""}

    type_code = "IM" if job_type == "Import" else "EX"
    next_numeric = generate_next_numeric(
        company.company_prefix, company.number_lead_digit
    )
    job_number = f"{company.company_prefix}{type_code}{next_numeric}"

    return {"job_number": job_number}


# =========================
# JOB DETAIL
# =========================


@app.route("/job/<int:job_id>")
@login_required
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    steps = (
        JobStep.query.filter_by(job_id=job.id).order_by(JobStep.step_order.asc()).all()
    )
    notes = (
        JobNote.query.filter_by(job_id=job.id).order_by(JobNote.created_at.desc()).all()
    )

    total_steps = len(steps)
    completed_steps = len([step for step in steps if step.completed])
    remaining_steps = total_steps - completed_steps

    if total_steps == 0:
        status = "No workflow"
        status_icon = "⚫"
    elif completed_steps == 0:
        status = "Not started"
        status_icon = "🔴"
    elif completed_steps == total_steps:
        status = "Completed"
        status_icon = "🟢"
    else:
        status = "In progress"
        status_icon = "🟡"

    return render_template(
        "job_detail.html",
        job=job,
        steps=steps,
        notes=notes,
        total_steps=total_steps,
        completed_steps=completed_steps,
        remaining_steps=remaining_steps,
        status=status,
        status_icon=status_icon,
        job_files=job.files,
    )


@app.route("/toggle_step/<int:step_id>", methods=["POST"])
@login_required
def toggle_step(step_id):
    step = JobStep.query.get_or_404(step_id)

    if step.completed:
        step.completed = False
        step.completed_at = None
    else:
        step.completed = True
        step.completed_at = datetime.now()

    update_job_last_updated(step.job)

    db.session.commit()
    return redirect(url_for("job_detail", job_id=step.job_id) + "#Workflow")


# =========================
# UPDATE SHIPMENT DATES
# =========================


@app.route("/update_job_dates/<int:job_id>", methods=["POST"])
@login_required
def update_job_dates(job_id):
    job = Job.query.get_or_404(job_id)

    created_date = request.form.get("created_date", "").strip()
    etd = request.form.get("etd", "").strip()
    eta = request.form.get("eta", "").strip()
    delivery_date = request.form.get("delivery_date", "").strip()

    changes = []

    def track_change(field_name, old, new):
        if str(old) != str(new):
            changes.append(
                f"{field_name}: {old if old else '-'} → {new if new else '-'}"
            )

    track_change("Created Date", job.created_date, created_date)
    track_change("ETD", job.etd, etd)
    track_change("ETA", job.eta, eta)
    track_change("Delivery Date", job.delivery_date, delivery_date)

    job.created_date = (
        datetime.strptime(created_date, "%Y-%m-%d").date() if created_date else None
    )
    job.etd = datetime.strptime(etd, "%Y-%m-%d").date() if etd else None
    job.eta = datetime.strptime(eta, "%Y-%m-%d").date() if eta else None
    job.delivery_date = (
        datetime.strptime(delivery_date, "%Y-%m-%d").date() if delivery_date else None
    )

    update_job_last_updated(job)

    db.session.commit()

    change_details = ", ".join(changes) if changes else "No changes"

    create_audit_log(
        action="update_job_dates",
        item_type="job",
        item_id=job.id,
        details=f"{job.job_number} → {change_details}",
    )

    flash("Shipment dates updated successfully.", "success")
    return redirect(url_for("job_detail", job_id=job.id) + "#ShipmentDates")


# =========================
# ADD JOB NOTE
# =========================


@app.route("/add_job_note/<int:job_id>", methods=["POST"])
@login_required
def add_job_note(job_id):
    job = Job.query.get_or_404(job_id)

    note_text = request.form["note_text"].strip()

    if not note_text:
        return redirect(url_for("job_detail", job_id=job.id) + "#notes")

    new_note = JobNote(job_id=job.id, note_text=note_text)

    db.session.add(new_note)
    update_job_last_updated(job)
    db.session.commit()

    return redirect(url_for("job_detail", job_id=job.id) + "#notes")


# =========================
# EDIT JOB
# =========================


@app.route("/edit_job/<int:job_id>", methods=["GET", "POST"])
@login_required
def edit_job(job_id):
    job = Job.query.get_or_404(job_id)
    companies = Company.query.filter_by(is_active=True).all()
    clients = Client.query.filter_by(is_active=True).all()

    if request.method == "POST":
        changes = []

        def track_change(field_name, old, new):
            if str(old) != str(new):
                changes.append(
                    f"{field_name}: {old if old else '-'} → {new if new else '-'}"
                )

        track_change("Company", job.company_id, request.form["company_id"])
        track_change("Job Type", job.job_type, request.form["job_type"])
        track_change(
            "Workflow", job.workflow_template, request.form["workflow_template"]
        )
        track_change("Client", job.client_id, request.form["client_id"])
        track_change("Description", job.description, request.form["description"])

        job.company_id = request.form["company_id"]
        job.job_type = request.form["job_type"]
        job.workflow_template = request.form["workflow_template"]
        job.client_id = request.form["client_id"]
        job.description = request.form["description"]

        created_date = request.form.get("created_date", "").strip()
        etd = request.form.get("etd", "").strip()
        eta = request.form.get("eta", "").strip()
        delivery_date = request.form.get("delivery_date", "").strip()

        date_received = request.form.get("date_received", "").strip()
        customer_name = request.form.get("customer_name", "").strip()
        customer_po = request.form.get("customer_po", "").strip()
        product_name = request.form.get("product_name", "").strip()
        quantity = request.form.get("quantity", "").strip()
        packaging_type = request.form.get("packaging_type", "").strip()
        destination_country = request.form.get("destination_country", "").strip()
        incoterm = request.form.get("incoterm", "").strip()
        vessel_flight = request.form.get("vessel_flight", "").strip()
        requested_ship_date = request.form.get("requested_ship_date", "").strip()
        pic = request.form.get("pic", "").strip()

        track_change("Created Date", job.created_date, created_date)
        track_change("ETD", job.etd, etd)
        track_change("ETA", job.eta, eta)
        track_change("Delivery Date", job.delivery_date, delivery_date)
        track_change("Date Received", job.date_received, date_received)
        track_change("Customer Name", job.customer_name, customer_name)
        track_change("Customer PO", job.customer_po, customer_po)
        track_change("Product Name", job.product_name, product_name)
        track_change("Quantity", job.quantity, quantity)
        track_change("Packaging Type", job.packaging_type, packaging_type)
        track_change(
            "Destination Country", job.destination_country, destination_country
        )
        track_change("Incoterm", job.incoterm, incoterm)
        track_change("Vessel / Flight", job.vessel_flight, vessel_flight)
        track_change(
            "Requested Shipment Date", job.requested_ship_date, requested_ship_date
        )
        track_change("PIC", job.pic, pic)

        job.created_date = (
            datetime.strptime(created_date, "%Y-%m-%d").date() if created_date else None
        )
        job.etd = datetime.strptime(etd, "%Y-%m-%d").date() if etd else None
        job.eta = datetime.strptime(eta, "%Y-%m-%d").date() if eta else None
        job.delivery_date = (
            datetime.strptime(delivery_date, "%Y-%m-%d").date()
            if delivery_date
            else None
        )

        job.date_received = (
            datetime.strptime(date_received, "%Y-%m-%d").date()
            if date_received
            else None
        )
        job.customer_name = customer_name
        job.customer_po = customer_po
        job.product_name = product_name
        job.quantity = quantity
        job.packaging_type = packaging_type
        job.destination_country = destination_country
        job.incoterm = incoterm
        job.vessel_flight = vessel_flight
        job.requested_ship_date = (
            datetime.strptime(requested_ship_date, "%Y-%m-%d").date()
            if requested_ship_date
            else None
        )
        job.pic = pic

        update_job_last_updated(job)

        db.session.commit()

        change_details = ", ".join(changes) if changes else "No changes"

        create_audit_log(
            action="edit_job",
            item_type="job",
            item_id=job.id,
            details=f"{job.job_number} → {change_details}",
        )

        return redirect(url_for("job_detail", job_id=job.id))

    return render_template(
        "edit_job.html",
        job=job,
        companies=companies,
        clients=clients,
        workflow_templates=WORKFLOW_TEMPLATES.keys(),
    )


# =========================
# DELETE JOB
# =========================


@app.route("/delete_job/<int:job_id>", methods=["POST"])
def delete_job(job_id):
    job = Job.query.get_or_404(job_id)

    JobStep.query.filter_by(job_id=job.id).delete()
    JobNote.query.filter_by(job_id=job.id).delete()
    db.session.delete(job)
    db.session.commit()

    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        run_safe_migrations()

    app.run(debug=True)
