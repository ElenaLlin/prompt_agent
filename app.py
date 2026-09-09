import os 
import uuid
import json
import hmac
from flask import Flask, flash, redirect, render_template, request, send_from_directory, session, url_for
from flask_babel import Babel
from supabase import create_client, Client
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

from backend.agent_service import generate_reply, make_thread_id, warmup_agent

load_dotenv()

app = Flask(__name__, template_folder="web", static_folder="web")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.environ.get(
    "OPENAI_API_KEY", "dev-secret-key"
    ))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

app.config['BABEL_DEFAULT_LOCALE'] = 'en'
app.config['LANGUAGES'] = {
    'en': 'English',
    'es': 'Español',
}

def _study_languages(config):
    """Return a locale-code map, accepting old display-name-only configs."""
    languages = {}
    for language in config.get("language_options", []):
        if isinstance(language, dict):
            code = language.get("code", "").strip().lower()
            name = language.get("name", "").strip()
        else:
            name = str(language).strip()
            code = {"English": "en", "Spanish": "es", "Español": "es"}.get(name, "")
        if code and name:
            languages[code] = name
    return languages or {"en": "English"}

def _active_languages():
    study_id = request.view_args.get("study_id") if request.view_args else None
    if study_id:
        study_file = os.path.join(os.path.dirname(__file__), study_id, f"{study_id}.json")
        if os.path.isfile(study_file):
            with open(study_file, "r", encoding="utf-8") as file:
                return _study_languages(json.load(file))
    return app.config["LANGUAGES"]

def get_locale():
    languages = _active_languages()
    # 1. If the user picked a language via ?lang=xx, store and use it.
    requested_language = request.args.get('lang', '').lower()
    if requested_language in languages:
        session['lang'] = requested_language
        return session['lang']
    # 2. Otherwise reuse their stored choice.
    if session.get('lang') in languages:
        return session['lang']
    # 3. Otherwise fall back to the browser's preferred language.
    return request.accept_languages.best_match(languages.keys()) or next(iter(languages))

babel = Babel(app, locale_selector=get_locale)

supabase: Client = create_client(
    os.environ.get("SUPABASE_URL"),
    os.environ.get("SUPABASE_KEY")
)

# Initialize the agent once when the app starts.
warmup_agent()

#study = "south_asia" # study goes here - this will be set by home page - edit

""" selection_path = os.path.join(os.path.dirname(__file__), "choices.json")
with open(selection_path, "r", encoding="utf-8") as f:
    selection = json.load(f) """

# User id for examples is the second entry in the user_id_list of the study config, if available

# make choices the first message from user
usecase_choice = ''
scenario_choice = ''
usecase_questions = {}
scenarios = []
userMessage = usecase_choice + '\n' + scenario_choice
#userMessage = userData["usecase"] + '\n' + userData["scenario"]
#scenario = userData["scenario"]
#usecase = userData["usecase"]

# make machine have first output message - will be generated when a session starts
hide = "panel hidden"
view = "panel"

def load_study_config(study_id):
    study_file = os.path.join(os.path.dirname(__file__), study_id, f"{study_id}.json")
    if not os.path.isfile(study_file):
        return None
    with open(study_file, "r", encoding="utf-8") as file:
        return json.load(file)

def list_studies():
    studies = []
    root = os.path.dirname(__file__)
    for name in sorted(os.listdir(root)):
        config = load_study_config(name)
        if config is not None:
            studies.append({
                "id": name,
                "header": config.get("header", name),
                "url": url_for("survey", study_id=name),
            })
    return studies

def study_form_values(study_id, config):
    values = {
        "study_id": study_id,
        "header": config.get("header", ""),
        "future_city": config.get("future_city", ""),
        "text": config.get("text", ""),
        "language_options": "\n".join(
            f"{language['code']}: {language['name']}"
            if isinstance(language, dict) else str(language)
            for language in config.get("language_options", [])
        ),
        "user_id_list": "\n".join(config.get("user_id_list", [])),
        "communities": "\n".join(config.get("communities", [])),
    }
    for usecase_number, usecase_key in ((1, "usecase_one"), (2, "usecase_two")):
        usecase_name = next(iter(config.get(usecase_key, {})), "")
        usecase = config.get(usecase_key, {}).get(usecase_name, {})
        values[f"usecase_{usecase_number}_name"] = usecase_name
        values[f"usecase_{usecase_number}_description"] = usecase.get("description", "")
        questions = usecase.get("questions", {})
        for question in ("initial", "context", "final"):
            values[f"usecase_{usecase_number}_question_{question}"] = questions.get(question, "")
        scenarios = usecase.get("scenarios", {})
        for scenario_number, (scenario_name, scenario_values) in enumerate(scenarios.items(), 1):
            values[f"scenario_{usecase_number}_{scenario_number}_name"] = scenario_name
            values[f"scenario_{usecase_number}_{scenario_number}_short"] = scenario_values[0]
            values[f"scenario_{usecase_number}_{scenario_number}_detail"] = scenario_values[1]
            values[f"scenario_{usecase_number}_{scenario_number}_imagine"] = scenario_values[2]
    return values

def update_choices(current_user_id, study_id, agent_language=None):
    # add user info into supabase and choices.json - homepage
    data = supabase.table('answers').select(
        "user_id",
        "agent_language",
        "usecase",
        "scenario",
        "initial",
        "context",
        "final"
    ).eq("user_id",current_user_id).eq("study", study_id).execute()
    print(data.data)
    user_data = data.data[0] if data.data else {"user_id": current_user_id}
    if agent_language:
        user_data["agent_language"] = agent_language
    selection_path = os.path.join(os.path.dirname(__file__), "choices.json")
    with open(selection_path, "w", encoding="utf-8") as j:
        # update json with supabase retrieval
        json.dump(user_data, j)
    #print(userData)

def ensure_answer_row(current_user_id, study_id=None):
    """Ensure a study user has a row before update() is used for their answers."""
    existing = supabase.table("answers").select("user_id").eq(
        "user_id", current_user_id
    ).eq("study", study_id).limit(1).execute()
    if not existing.data:
        supabase.table("answers").insert({
            "user_id": current_user_id,
            "study": study_id,
            }).execute()

def sync_agent_language(current_user_id, study_id):
    locale = get_locale()
    agent_language = _active_languages().get(locale, locale)
    supabase.table("answers").update(
        {"agent_language": agent_language}
    ).eq("user_id", current_user_id).eq("study", study_id).execute()
    return agent_language

def chat_init(current_user_id, study_id, agent_language=None):
    '''
    Initialises conversation state
    '''
    update_choices(current_user_id, study_id, agent_language) # inputs into choices.json
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

def _split_lines(value):
    return [line.strip() for line in value.splitlines() if line.strip()]

def _parse_languages(value):
    languages = []
    for line in _split_lines(value):
        code, separator, name = line.partition(":")
        code = code.strip().lower()
        name = name.strip()
        if not separator or len(code) != 2 or not code.isalpha() or not name:
            raise ValueError("Languages must use the format 'xx: Language name'.")
        languages.append({"code": code, "name": name})
    if not languages:
        raise ValueError("At least one language is required.")
    if len({language["code"] for language in languages}) != len(languages):
        raise ValueError("Language codes must be unique.")
    return languages

def _study_form_data(form):
    usecases = {}
    for usecase_number in (1, 2):
        scenarios = {}
        for scenario_number in (1, 2, 3):
            scenarios[form[f"scenario_{usecase_number}_{scenario_number}_name"]] = [
                form[f"scenario_{usecase_number}_{scenario_number}_short"].strip(),
                form[f"scenario_{usecase_number}_{scenario_number}_detail"].strip(),
                form[f"scenario_{usecase_number}_{scenario_number}_imagine"].strip(),
            ]
        usecases[form[f"usecase_{usecase_number}_name"]] = {
            form[f"usecase_{usecase_number}_name"]: {
                "description": form[f"usecase_{usecase_number}_description"].strip(),
                "scenarios": scenarios,
                "questions": {
                    "initial": form[f"usecase_{usecase_number}_question_initial"].strip(),
                    "context": form[f"usecase_{usecase_number}_question_context"].strip(),
                    "final": form[f"usecase_{usecase_number}_question_final"].strip(),
                },
            }
        }

    return {
        "header": form["header"].strip(),
        "future_city": form["future_city"].strip(),
        "text": form["text"].strip(),
        "language_options": _parse_languages(form["language_options"]),
        "user_id_list": _split_lines(form["user_id_list"]),
        "communities": _split_lines(form["communities"]),
        "usecase_one": usecases[form["usecase_1_name"]],
        "usecase_two": usecases[form["usecase_2_name"]],
    }

@app.context_processor
def inject_languages():
    # Makes `languages` and `current_language` available in every template.
    return {
        'languages': _active_languages(),
        'current_language': get_locale(),
    }

@app.route("/", methods=["GET"])
def consent():
    return render_template("index.html")

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if not ADMIN_PASSWORD:
        return "Admin password is not configured.", 503
    if request.method == "POST":
        password = request.form.get("password", "")
        if hmac.compare_digest(password, ADMIN_PASSWORD):
            session["admin_authenticated"] = True
            return redirect(url_for("admin"))
        flash("Incorrect password.", "error")
    return render_template("admin_login.html")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not ADMIN_PASSWORD:
        return "Admin password is not configured.", 503
    if not session.get("admin_authenticated"):
        return redirect(url_for("admin_login"))
    if request.method == "GET":
        edit_study_id = secure_filename(request.args.get("edit", "").strip().lower())
        edit_config = load_study_config(edit_study_id) if edit_study_id else None
        form = study_form_values(edit_study_id, edit_config) if edit_config else None
        return render_template(
            "admin.html",
            form=form,
            editing_study=edit_study_id if edit_config else None,
            studies=list_studies(),
        )

    original_study_id = secure_filename(request.form.get("original_study_id", "").strip().lower())
    study_id = original_study_id or secure_filename(request.form.get("study_id", "").strip().lower())
    existing_config = load_study_config(study_id)
    if not study_id or not request.form.get("header", "").strip():
        flash("Study ID and header are required.", "error")
        return render_template("admin.html", form=request.form), 400

    required_fields = [
        "future_city", "text", "language_options", "user_id_list", "communities",
    ]
    for usecase_number in (1, 2):
        required_fields += [
            f"usecase_{usecase_number}_name", f"usecase_{usecase_number}_description",
            f"usecase_{usecase_number}_question_initial",
            f"usecase_{usecase_number}_question_context",
            f"usecase_{usecase_number}_question_final",
        ]
        for scenario_number in (1, 2, 3):
            required_fields += [
                f"scenario_{usecase_number}_{scenario_number}_name",
                f"scenario_{usecase_number}_{scenario_number}_short",
                f"scenario_{usecase_number}_{scenario_number}_detail",
                f"scenario_{usecase_number}_{scenario_number}_imagine",
            ]

    missing = [field for field in required_fields if not request.form.get(field, "").strip()]
    image_fields = ["city_image", "usecase_one_image", "usecase_two_image"] + [
        f"scenario_{number}_image" for number in (1, 2, 3)
    ]
    missing_images = [] if existing_config else [
        field for field in image_fields if not request.files.get(field)
        or not request.files[field].filename
    ]
    if missing or missing_images:
        flash("Complete every field and upload all six study images.", "error")
        return render_template(
            "admin.html", form=request.form, editing_study=original_study_id or None,
            studies=list_studies(),
        ), 400

    study_directory = os.path.join(os.path.dirname(__file__), study_id)
    os.makedirs(study_directory, exist_ok=True)
    try:
        study_config = _study_form_data(request.form)
    except ValueError as error:
        flash(str(error), "error")
        return render_template(
            "admin.html", form=request.form, editing_study=original_study_id or None,
            studies=list_studies(),
        ), 400
    with open(os.path.join(study_directory, f"{study_id}.json"), "w", encoding="utf-8") as file:
        json.dump(study_config, file, indent=2, ensure_ascii=False)

    image_names = {
        "city_image": "city.jpg",
        "usecase_one_image": "usecase-one.jpg",
        "usecase_two_image": "usecase-two.jpg",
        "scenario_1_image": "scenario-one.jpg",
        "scenario_2_image": "scenario-two.jpg",
        "scenario_3_image": "scenario-three.jpg",
    }
    for field, filename in image_names.items():
        uploaded_file = request.files.get(field)
        if uploaded_file and uploaded_file.filename:
            uploaded_file.save(os.path.join(study_directory, filename))

    action = "updated" if existing_config else "created"
    flash(f"Study '{study_id}' was {action} in the {study_id}/ folder.", "success")
    return render_template(
        "admin.html", created_study=study_id, studies=list_studies(),
    )

@app.route("/<study_id>", methods=["GET", "POST"])
def survey(study_id):
    current_study_config = load_study_config(study_id)
    if current_study_config is None:
        return "Study not found", 404
    current_usecase_one = next(iter(current_study_config["usecase_one"]))
    current_usecase_two = next(iter(current_study_config["usecase_two"]))
    current_user_id = current_study_config["user_id_list"][1]
    current_communities = current_study_config["communities"]
    current_header = current_study_config["header"]
    current_city = current_study_config["future_city"]
    current_text = current_study_config["text"]
    selected_scenarios = []
    ensure_answer_row(current_user_id, study_id)
    sync_agent_language(current_user_id, study_id)
    current_view = request.args.get("view", "entry")

    entry_status = view if current_view == "entry" else hide
    usecase_status = view if current_view == "usecases" else hide
    scenario_status = view if current_view == "scenario" else hide

    if request.method == "POST" and current_view == "entry":
        return  render_template(
            "index.html",
            study = study_id,
            header = current_header,
            future_city = current_city,
            text = current_text,
            entry_status = entry_status,
            usecase_status = usecase_status,
            scenario_status = scenario_status,
            communities = current_communities
        )

    elif request.method == "POST" and current_view == "usecases":
        name = request.form['name']
        age = int(request.form['age'])
        gender = request.form['gender']
        community = request.form['community']

        supabase.table("answers").update(
            {"name": name,
            "Age": age,
            "Gender": gender,
            "Community": community}
        ).eq("user_id",current_user_id).eq("study", study_id).execute()

        return  render_template(
                    "index.html",
                    study = study_id,
                    header = current_header,
                    future_city = current_city,
                    text = current_text,
                    entry_status = entry_status,
                    usecase_status = usecase_status,
                    scenario_status = scenario_status,
                    usecase_one = current_usecase_one,
                    description_one = current_study_config["usecase_one"][current_usecase_one]["description"],
                    usecase_two = current_usecase_two,
                    description_two = current_study_config["usecase_two"][current_usecase_two]["description"]
                )

    elif request.method == "POST" and current_view == "scenario":
        for k in request.form:
            if k == 'one':
                usecase_choice = current_usecase_one
                usecase_questions = current_study_config["usecase_one"][current_usecase_one]["questions"]
                session["usecase_questions"] = usecase_questions
                session["usecase_choice"] = current_usecase_one
                selected_scenarios = list(current_study_config["usecase_one"][current_usecase_one]["scenarios"])
                session["scenarios"] = selected_scenarios

                supabase.table("answers").update(
                    {"usecase": usecase_choice}
                ).eq("user_id",current_user_id).eq("study", study_id).execute()
                
                return  render_template(
                    "index.html",
                    study = study_id,
                    header = current_header,
                    future_city = current_city,
                    text = current_text,
                    entry_status = entry_status,
                    usecase_status = usecase_status,
                    scenario_status = scenario_status,
                    scenario_one = selected_scenarios[0],
                    description_one = current_study_config["usecase_one"][current_usecase_one]["scenarios"][
                        selected_scenarios[0]][2],
                    scenario_two = selected_scenarios[1],
                    description_two = current_study_config["usecase_one"][current_usecase_one]["scenarios"][
                        selected_scenarios[1]][2],
                    scenario_three = selected_scenarios[2],
                    description_three = current_study_config["usecase_one"][current_usecase_one]["scenarios"][
                        selected_scenarios[2]][2]
                )
            elif k == 'two':
                usecase_choice = current_usecase_two
                usecase_questions = current_study_config["usecase_two"][current_usecase_two]["questions"]
                session["usecase_questions"] = usecase_questions
                session["usecase_choice"] = current_usecase_two
                print(usecase_questions)
                selected_scenarios = list(current_study_config["usecase_two"][current_usecase_two]["scenarios"])
                session["scenarios"] = selected_scenarios

                supabase.table("answers").update(
                    {"usecase": usecase_choice}
                ).eq("user_id",current_user_id).eq("study", study_id).execute()

                return  render_template(
                    "index.html",
                    study = study_id,
                    header = current_header,
                    future_city = current_city,
                    text = current_text,
                    entry_status = entry_status,
                    usecase_status = usecase_status,
                    scenario_status = scenario_status,
                    scenario_one = selected_scenarios[0],
                    description_one = current_study_config["usecase_two"][current_usecase_two]["scenarios"][
                        selected_scenarios[0]][2],
                    scenario_two = selected_scenarios[1],
                    description_two = current_study_config["usecase_two"][current_usecase_two]["scenarios"][
                        selected_scenarios[1]][2],
                    scenario_three = selected_scenarios[2],
                    description_three = current_study_config["usecase_two"][current_usecase_two]["scenarios"][
                        selected_scenarios[2]][2]
                )

    return render_template(
        "index.html",
        study = study_id,
        header = current_header,
        future_city = current_city,
        text = current_text,
        entry_status = entry_status,
        usecase_status = usecase_status,
        scenario_status = scenario_status,
        communities = current_communities,
        usecase_one = current_usecase_one,
        description_one = current_study_config["usecase_one"][current_usecase_one]["description"],
        usecase_two = current_usecase_two,
        description_two = current_study_config["usecase_two"][current_usecase_two]["description"]
    )

@app.route("/<study_id>/chat", methods=["GET", "POST"])
def chat(study_id):
    """ needs to correspond to html """

    usecase_questions = session.get("usecase_questions", {})
    scenario_choice = session.get("scenario_choice", "")
    current_scenarios = session.get("scenarios", [])  #scenarios if [] fails
    current_chat_study = load_study_config(study_id)
    if current_chat_study is None:
        return "Study not found", 404
    current_user_id = current_chat_study["user_id_list"][1]
    current_header = current_chat_study["header"]
    current_city = current_chat_study["future_city"]
    current_text = current_chat_study["text"]
    current_communities = current_chat_study["communities"]
    ensure_answer_row(current_user_id, study_id)
    agent_language = sync_agent_language(current_user_id,study_id)
    thread_id = chat_init(current_user_id, study_id, agent_language)

    # ── Render existing messages ──────────────────────────────────────────────────
    if request.method == "POST":
        for choice in request.form:
            if choice == 'one':
                scenario_choice = current_scenarios[0]
            elif choice == 'two':
                scenario_choice = current_scenarios[1]
            elif choice == 'three':
                scenario_choice = current_scenarios[2]
        if scenario_choice:
            session["scenario_choice"] = scenario_choice
        supabase.table("answers").update({
            "scenario": scenario_choice,
            "initial": usecase_questions['initial'],
            "context": usecase_questions['context'],
            "final" : usecase_questions['final']
            }
        ).eq("user_id",current_user_id).eq("study", study_id).execute() # questions as well

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
                    ).eq("user_id", current_user_id).eq("study", study_id).execute()
            if response_text:
                display_text = response_text
            else:
                display_text = ""
            history.append({"role": "assistant", "content": display_text})
            session["chat_history"] = history

    return render_template(
        "chat.html",
        chat_history=session["chat_history"],
        thread_id=thread_id,
        study = study_id,
        header = current_header,
        future_city = current_city,
        text = current_text,
        scenario = session.get("scenario_choice", ""),
        usecase = session.get("usecase_choice", ""),
        communities = current_communities
    )

@app.route("/clear", methods=["POST"])
def clear_chat():
    study_id = request.args.get("study_id", "")
    current_study_config = load_study_config(study_id)
    if current_study_config is None:
        return "Study not found", 404
    agent_language = sync_agent_language(current_study_config["user_id_list"][1], study_id)
    chat_init(current_study_config["user_id_list"][1], study_id, agent_language)
    session.pop("chat_history", None)
    session.pop("session_seed", None)
    session.pop("responses_summary", None)
    return redirect(url_for("chat", study_id=study_id))


@app.route("/<study_id>/<path:filename>")
def study_asset(study_id, filename):
    study_directory = os.path.join(os.path.dirname(__file__), study_id)
    if not os.path.isfile(os.path.join(study_directory, f"{study_id}.json")):
        return "Study not found", 404
    return send_from_directory(study_directory, filename)



@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico", mimetype="image/vnd.microsoft.icon")

if __name__ == "__main__":
    app.run( use_reloader=False) #debug=True,
