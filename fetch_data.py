import ssl
import os
import xmlrpc.client
import pandas as pd

odoo_url = os.environ["ODOO_URL"]
odoo_db = os.environ["ODOO_DB"]
odoo_user = os.environ["ODOO_USER"]
odoo_password = os.environ["ODOO_PASSWORD"]

ssl_context = ssl._create_unverified_context()

common = xmlrpc.client.ServerProxy(
    f"{odoo_url}/xmlrpc/2/common",
    context=ssl_context
)
uid = common.authenticate(odoo_db, odoo_user, odoo_password, {})

models = xmlrpc.client.ServerProxy(
    f"{odoo_url}/xmlrpc/2/object",
    context=ssl_context
)


def extract_name(val):
    return val[1] if isinstance(val, list) else None


def extract_id(val):
    return val[0] if isinstance(val, list) else None


def read_lookup(model, ids, fields):
    """Načte doplňková pole pro daný seznam ID (obdoba SQL LEFT JOIN)."""
    ids = [i for i in set(ids) if i]
    if not ids:
        return {}
    records = models.execute_kw(
        odoo_db, uid, odoo_password,
        model, "read",
        [ids],
        {"fields": fields}
    )
    return {r["id"]: r for r in records}


BATCH_SIZE = 1000


# =========================
# 1️⃣ TASKS (project.task)
# =========================
task_fields = [
    "id",
    "display_name",
    "create_date",
    "project_id",
    "tag_ids",
    "activity_user_id",
    "company_id",
    "effective_hours",
    "user_ids"
]

task_ids = models.execute_kw(
    odoo_db, uid, odoo_password,
    "project.task", "search",
    [[]]
)

print(f"Found {len(task_ids)} tasks")

tasks = []
for i in range(0, len(task_ids), BATCH_SIZE):
    batch = models.execute_kw(
        odoo_db, uid, odoo_password,
        "project.task", "read",
        [task_ids[i:i + BATCH_SIZE]],
        {"fields": task_fields}
    )
    tasks.extend(batch)

df_tasks = pd.DataFrame(tasks)
for col in ["project_id", "company_id", "activity_user_id"]:
    if col in df_tasks.columns:
        df_tasks[col] = df_tasks[col].apply(extract_name)

df_tasks.to_json("tasks.json", orient="records")
print("tasks.json saved")


# =========================
# 2️⃣ PROJECTS (project.project)
# =========================
project_fields = [
    "id",
    "x_studio_dppo_v_paulu",
    "x_studio_poet_doklad",
    "x_studio_poet_mezd",
    "x_studio_pltce_dph",
    "x_studio_country",
    "x_studio_accounting_software",
    "x_studio_zakzka_pl_id",
    "x_studio_skupina"
]

project_ids = models.execute_kw(
    odoo_db, uid, odoo_password,
    "project.project", "search",
    [[]]
)

print(f"Found {len(project_ids)} projects")

projects = []
for i in range(0, len(project_ids), BATCH_SIZE):
    batch = models.execute_kw(
        odoo_db, uid, odoo_password,
        "project.project", "read",
        [project_ids[i:i + BATCH_SIZE]],
        {"fields": project_fields}
    )
    projects.extend(batch)

df_projects = pd.DataFrame(projects)
df_projects.to_json("projects.json", orient="records")
print("projects.json saved")


# =========================
# 3️⃣ ANALYTIC LINES (account.analytic.line) + JOINy podle SQL
# =========================
al_fields = [
    "id",
    "account_id",
    "amount",
    "company_id",
    "date",
    "general_account_id",
    "journal_id",
    "x_plan2_id",
    "x_plan4_id",
    "partner_id",
    "x_studio_related_field_2cp_1j0d5m2o0",
    "x_studio_typ_finannho_tu",
    "x_studio_skupina_projekt_1",
    "move_line_id"
]

domain = [("amount", "!=", 0)]

al_ids = models.execute_kw(
    odoo_db, uid, odoo_password,
    "account.analytic.line", "search",
    [domain]
)

print(f"Found {len(al_ids)} analytic lines")

lines = []
for i in range(0, len(al_ids), BATCH_SIZE):
    batch = models.execute_kw(
        odoo_db, uid, odoo_password,
        "account.analytic.line", "read",
        [al_ids[i:i + BATCH_SIZE]],
        {"fields": al_fields}
    )
    lines.extend(batch)

df_al = pd.DataFrame(lines)

# --- ponecháme RAW ID jako čísla ve všech many2one sloupcích (jako ve tvém SQL) ---
raw_id_cols = [
    "account_id", "company_id", "general_account_id", "journal_id",
    "x_plan2_id", "x_plan4_id", "partner_id", "move_line_id"
]
for col in raw_id_cols:
    if col in df_al.columns:
        df_al[col] = df_al[col].apply(extract_id)

# --- JOIN 1: account.account (podle general_account_id) → "Účet" + "Název účtu" ---
account_lookup = read_lookup(
    "account.account",
    df_al["general_account_id"].tolist(),
    ["code", "name"]
)
df_al["Účet"] = df_al["general_account_id"].map(
    lambda x: account_lookup.get(x, {}).get("code")
)
df_al["Název účtu"] = df_al["general_account_id"].map(
    lambda x: account_lookup.get(x, {}).get("name")
)

# --- JOIN 2: project.project (podle account_id) → "Zakázka - P&L_id" ---
analytic_lookup = read_lookup(
    "project.project",
    df_al["account_id"].tolist(),
    ["name"]
)
df_al["Zakázka - P&L_id"] = df_al["account_id"].map(
    lambda x: analytic_lookup.get(x, {}).get("name")
)

# --- JOIN 3: res.partner (podle partner_id) → "partner_id" (název) ---
partner_lookup = read_lookup(
    "res.partner",
    df_al["partner_id"].tolist(),
    ["name"]
)
df_al["partner_id_name"] = df_al["partner_id"].map(
    lambda x: partner_lookup.get(x, {}).get("name")
)

df_al.to_json("analytic_lines.json", orient="records")
print("analytic_lines.json saved")
