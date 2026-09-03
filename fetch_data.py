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
    "user_ids",
    # "employee_id",  ← tohle pole na project.task neexistuje, odstraněno
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
for col in ["project_id", "company_id", "employee_id", "activity_user_id"]:
    if col in df_tasks.columns:
        df_tasks[col] = df_tasks[col].apply(extract_name)

df_tasks.to_json("tasks.json", orient="records")
print("tasks.json saved")


# =========================
# 2️⃣ ANALYTIC LINES (account.analytic.line)
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
for col in ["account_id", "company_id", "general_account_id",
            "journal_id", "x_plan2_id", "x_plan4_id",
            "partner_id", "move_line_id"]:
    if col in df_al.columns:
        df_al[col] = df_al[col].apply(extract_name)

df_al.to_json("analytic_lines.json", orient="records")
print("analytic_lines.json saved")
