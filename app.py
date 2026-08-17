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
study = "example" # number or area goes here
study_path = os.path.join(os.path.dirname(__file__), f"study_{study}.json")
with open(study_path, "r", encoding="utf-8") as f:
    study_config = json.load(f)

selection_path = os.path.join(os.path.dirname(__file__), "choices.json")
with open(selection_path, "r", encoding="utf-8") as f:
    selection = json.load(f)

# User id for example
userId = "hay1-flour2"
supabase.table("answers").update(selection).eq("user_id",userId).execute()

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
# make machine have first output message - will be generated when a session starts


def chat_init():
    '''
    Initialises conversation state
    '''
    # Ensure session seed exists before generating an initial assistant message
    if "session_seed" not in session:
        session["session_seed"] = str(uuid.uuid4())

    thread_id = make_thread_id(session["session_seed"])

    if "chat_history" not in session:
        # Ask the agent to produce the first message (assistant-initiated)
        initial_text, initial_json = generate_reply([], thread_id)
        # If parsed JSON returned, save it in session and show only the thank-you text
        if isinstance(initial_text, str) and initial_text.startswith("⚠️ Error"):
            # Error: fall back to previous behavior
            session["chat_history"] = [{"role": "user", "content": userMessage}]
            history = session["chat_history"]
            initial_text, initial_json = generate_reply(history, thread_id)
        else:
            if initial_json is not None:
                session["responses_summary"] = initial_json
            session["chat_history"] = [{"role": "assistant", "content": initial_text}]

    return thread_id

@app.route(f"/study_{study}", methods=["GET", "POST"])
def chat():

    thread_id = chat_init()

    # ── Render existing messages ──────────────────────────────────────────────────
    if request.method == "POST":
        # New user input
        message = (request.form.get("message") or "").strip()
        if message:
            # Show and store user and agent message
            history = session["chat_history"]
            history.append({"role": "user", "content": message})
            # Invoke graph
            response_text, response_json = generate_reply(history, thread_id)
            # If the agent returned structured JSON, store it separately instead of showing raw JSON
            if response_json is not None:
                session["responses_summary"] = response_json
                supabase.table("answers").update(
                    {"chatbot_summary": response_json}
                    ).eq("user_id", userId).execute()
            if response_text:
                display_text = response_text
            else:
                display_text = ""
            history.append({"role": "assistant", "content": display_text})
            session["chat_history"] = history

    return render_template(
        "index.html",
        chat_history=session["chat_history"],
        thread_id=thread_id,
    )

@app.route("/clear", methods=["POST"])
def clear_chat():
    chat_init()
    session.pop("chat_history", None)
    session.pop("session_seed", None)
    session.pop("responses_summary", None)
    return redirect(url_for("chat"))


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico", mimetype="image/vnd.microsoft.icon")

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
