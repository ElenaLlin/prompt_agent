import os
import uuid

from flask import Flask, redirect, render_template, request, send_from_directory, session, url_for

from backend.agent_service import generate_reply, make_thread_id

app = Flask(__name__, template_folder="web", static_folder="web")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.environ.get(
    "OPENAI_API_KEY", "dev-secret-key"
    ))


@app.route("/", methods=["GET", "POST"])
def chat():
    # ── Conversation state ────────────────────────────────────────────────────────
    if "chat_history" not in session:
        session["chat_history"] = []

    # ── Session seed (stable per browser session) ────────────────────────────────
    if "session_seed" not in session:
        session["session_seed"] = str(uuid.uuid4())

    thread_id = make_thread_id(session["session_seed"])

    # ── Render existing messages ──────────────────────────────────────────────────
    if request.method == "POST":
        # New user input
        message = (request.form.get("message") or "").strip()
        if message:
            # Show and store user and agent message
            history = session["chat_history"]
            history.append({"role": "user", "content": message})
            # Invoke graph
            response = generate_reply(history, thread_id)
            history.append({"role": "assistant", "content": response})
            session["chat_history"] = history

    return render_template(
        "index.html",
        chat_history=session["chat_history"],
        thread_id=thread_id,
    )


@app.route("/clear", methods=["POST"])
def clear_chat():
    session["chat_history"] = []
    return redirect(url_for("chat"))


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico", mimetype="image/vnd.microsoft.icon")


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
