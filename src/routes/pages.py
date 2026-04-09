"""Page routes for rendering templates"""
from flask import Blueprint, render_template, redirect, url_for

pages_bp = Blueprint('pages', __name__)

@pages_bp.route("/")
def index():
    """Redirect to dashboard"""
    return redirect(url_for("pages.dashboard"))

@pages_bp.route("/chatbot")
def chatbot_page():
    """Render chatbot page"""
    return render_template("chat.html")

@pages_bp.route("/dashboard")
def dashboard():
    """Render dashboard page"""
    return render_template("dashboard.html")
