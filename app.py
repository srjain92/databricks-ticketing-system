"""
Databricks Ticketing System App:
- Serves a Flask web UI for creating and managing support tickets
- Stores tickets and messages in Lakebase (Databricks-managed Postgres)
- Uses the current user's email for ticket/message authorship

Run locally:
    python app.py
Deploy as a Databricks App using app.yaml.
"""

import logging
import os

from databricks.sdk import WorkspaceClient
from flask import Flask, jsonify, render_template, request, redirect, url_for

import lakebase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ticketing-app")

app = Flask(__name__)
_w = WorkspaceClient()


def ensure_tables():
    """Create the tickets and ticket_messages tables in Lakebase if they don't exist yet."""
    lakebase.ensure_tickets_table()
    lakebase.ensure_ticket_messages_table()


def _current_user_email() -> str:
    """
    Resolve the current user's email so the watchlist can be personalized.

    Databricks Apps inject the logged-in user's identity via the
    X-Forwarded-Email header on every request. Fall back to the Databricks
    SDK's current_user API for local development where that header isn't set.
    """
    header_email = request.headers.get("X-Forwarded-Email")
    if header_email:
        return header_email
    return _w.current_user.me().user_name


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.errorhandler(Exception)
def handle_exception(err):
    """Ensure all unhandled errors return JSON (not an HTML error page),
    so the frontend's resp.json() call never chokes on HTML."""
    logger.exception("Unhandled exception while processing request")
    status_code = getattr(err, "code", 500)
    if not isinstance(status_code, int):
        status_code = 500
    return jsonify({"error": str(err)}), status_code


@app.route("/")
def index():
    """Main page showing all tickets."""
    ensure_tables()
    
    # Get all tickets
    tickets = lakebase.run_query(
        "SELECT ticket_id, title, status, created_by, created_at "
        "FROM tickets ORDER BY created_at DESC"
    )
    
    return render_template(
        "tickets.html",
        tickets=tickets,
        selected_ticket=None,
        messages=[],
    )


@app.route("/tickets", methods=["POST"])
def create_ticket():
    """Create a new ticket."""
    ensure_tables()
    title = request.form.get("title", "").strip()
    
    if not title:
        return jsonify({"error": "Title is required"}), 400
    
    email = _current_user_email()
    lakebase.run_write(
        "INSERT INTO tickets (title, status, created_by) VALUES (%s, %s, %s)",
        (title, "open", email),
    )
    
    return redirect(url_for("index"))


@app.route("/tickets/<int:ticket_id>")
def view_ticket(ticket_id):
    """View a specific ticket with all its messages."""
    ensure_tables()
    
    # Get all tickets for the sidebar
    tickets = lakebase.run_query(
        "SELECT ticket_id, title, status, created_by, created_at "
        "FROM tickets ORDER BY created_at DESC"
    )
    
    # Get the selected ticket
    selected_ticket_rows = lakebase.run_query(
        "SELECT ticket_id, title, status, created_by, created_at "
        "FROM tickets WHERE ticket_id = %s",
        (ticket_id,),
    )
    
    if not selected_ticket_rows:
        return "Ticket not found", 404
    
    selected_ticket = selected_ticket_rows[0]
    
    # Get all messages for this ticket
    messages = lakebase.run_query(
        "SELECT message_id, message_text, author, created_at "
        "FROM ticket_messages WHERE ticket_id = %s ORDER BY created_at ASC",
        (ticket_id,),
    )
    
    return render_template(
        "tickets.html",
        tickets=tickets,
        selected_ticket=selected_ticket,
        messages=messages,
    )


@app.route("/tickets/<int:ticket_id>/messages", methods=["POST"])
def add_message(ticket_id):
    """Add a message to a ticket."""
    ensure_tables()
    message_text = request.form.get("message_text", "").strip()
    
    if not message_text:
        return jsonify({"error": "Message text is required"}), 400
    
    email = _current_user_email()
    lakebase.run_write(
        "INSERT INTO ticket_messages (ticket_id, message_text, author) VALUES (%s, %s, %s)",
        (ticket_id, message_text, email),
    )
    
    return redirect(url_for("view_ticket", ticket_id=ticket_id))


@app.route("/tickets/<int:ticket_id>/status", methods=["POST"])
def update_status(ticket_id):
    """Update the status of a ticket."""
    ensure_tables()
    new_status = request.form.get("status", "").strip()
    
    valid_statuses = ["open", "in_progress", "resolved", "closed"]
    if new_status not in valid_statuses:
        return jsonify({"error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}), 400
    
    lakebase.run_write(
        "UPDATE tickets SET status = %s WHERE ticket_id = %s",
        (new_status, ticket_id),
    )
    
    return redirect(url_for("view_ticket", ticket_id=ticket_id))


if __name__ == '__main__':
    host = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_RUN_PORT', 8000))
    app.run(debug=True, host=host, port=port)
    print(f"Flask app running on http://{host}:{port}")