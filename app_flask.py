import os 
import uuid
import json
from flask import Flask, redirect, render_template, request, send_from_directory, session, url_for
from supabase import create_client, Client
from dotenv import load_dotenv

from backend.agent_service import generate_reply, make_thread_id, warmup_agent

load_dotenv()

app = Flask(__name__, template_folder="web", static_folder="web")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.environ.get(
    "OPENAI_API_KEY", "dev-secret-key"
    ))

supabase: Client = create_client(
    os.environ.get("SUPABASE_URL"),
    os.environ.get("SUPABASE_KEY")
)

# Initialize the agent once when the app starts.
warmup_agent()
selection_path = os.path.join(os.path.dirname(__file__), "choices.json")
with open(selection_path, "r", encoding="utf-8") as f:
    selection = json.load(f)

userId = "hay1-flour2"
#supabase.table("answers").insert({"user_id": userId}).execute()

supabase.table("answers").insert(selection).execute()

Data = supabase.table('answers').select(
    "user_id",
    "agent_language",
    "usecase",
    "scenario",
    "initial",
    "context",
    "final"
    ).eq("user_id",userId).execute()
userData = Data.data[0]
print(userData)
# make choices the first message from user
userMessage = userData["usecase"] + '\n' + userData["scenario"]
# make machine have first output message


@app.route("/", methods=["GET", "POST"])
def chat():
    # ── Conversation state ────────────────────────────────────────────────────────
    if "chat_history" not in session:
        session["chat_history"] = [
            {"role": "user", "content": userMessage}
            ]

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
            render_template(
                "index.html",
                chat_history=session["chat_history"],
                thread_id=thread_id,
            )
            # Invoke graph
            response = generate_reply(history, thread_id)
            if "{" in response:
                print(response) 
                #supabase.table("answers").select("chabotanswers")
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
    session["session_seed"] = str(uuid.uuid4())
    return redirect(url_for("chat"))


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico", mimetype="image/vnd.microsoft.icon")

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
