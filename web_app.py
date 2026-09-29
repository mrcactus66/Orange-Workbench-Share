"""Windows 本地工作台：项目、备忘录、LP、交易、代币合约与聪明钱地址库。"""
import os
import secrets
import sys

from flask import Flask, redirect, request, send_from_directory

ROOT = os.path.dirname(__file__)
sys.path.insert(0, ROOT)

app = Flask(__name__, static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("WORKBENCH_SECRET_KEY", secrets.token_hex(32))


@app.route("/")
def index():
    return redirect("/projects")


@app.route("/projects")
def projects_page():
    from routes.projects import projects_page
    return projects_page()


@app.route("/proj/add", methods=["GET", "POST"])
def proj_add():
    from routes.proj_add import proj_add_page
    return proj_add_page()


@app.route("/proj/detail/<proj_id>")
def proj_detail(proj_id):
    from routes.proj_detail import proj_detail_page
    return proj_detail_page(proj_id)


@app.route("/proj/detail/<proj_id>/edit", methods=["GET", "POST"])
def proj_edit(proj_id):
    from routes.proj_edit import proj_detail_edit
    return proj_detail_edit(proj_id)


@app.route("/proj/detail/<proj_id>/delete")
def proj_delete(proj_id):
    from routes.proj_edit import proj_detail_delete
    return proj_detail_delete(proj_id)


@app.route("/task/<task_id>/done")
def task_done(task_id):
    from routes.tasks import task_done
    return task_done(task_id)


@app.route("/task/<task_id>/edit", methods=["GET", "POST"])
def task_edit(task_id):
    from routes.tasks import task_edit
    return task_edit(task_id)


@app.route("/lp")
def lp_dashboard():
    from routes.lp import lp_dashboard_page
    return lp_dashboard_page()


@app.route("/lp/action", methods=["POST"])
def lp_action():
    from routes.lp import lp_action
    return lp_action()


@app.route("/memos")
def memos_page():
    from routes.memos import memos_page
    return memos_page()


@app.route("/memos/save", methods=["POST"])
def memos_save():
    from routes.memos import memos_save
    return memos_save()


@app.route("/memos/del", methods=["POST"])
def memos_delete():
    from routes.memos import memos_del
    return memos_del()


@app.route("/trade-log")
def trade_log():
    from routes.trade_log_ui import trade_log_page
    return trade_log_page()


@app.route("/trade-log/add", methods=["POST"])
def trade_add():
    from routes.trade_log import trade_add
    return trade_add()


@app.route("/trade-log/close", methods=["POST"])
def trade_close():
    from routes.trade_log import trade_close
    return trade_close()


@app.route("/trade-log/adjust", methods=["POST"])
def trade_adjust():
    from routes.trade_log import trade_adjust_position
    return trade_adjust_position()


@app.route("/trade-log/api/prices")
def trade_prices():
    from routes.trade_log import trade_prices_api
    return trade_prices_api()


@app.route("/token-contracts")
def token_contracts():
    from routes.token_contracts import token_contracts_page
    return token_contracts_page()


@app.route("/token-contracts/add", methods=["POST"])
def token_add():
    from routes.token_contracts import token_add
    return token_add()


@app.route("/token-contracts/del", methods=["POST"])
def token_delete():
    from routes.token_contracts import token_del
    return token_del()


@app.route("/token-contracts/add-category", methods=["POST"])
def token_category_add():
    from routes.token_contracts import add_category
    return add_category()


@app.route("/token-contracts/del-category", methods=["POST"])
def token_category_delete():
    from routes.token_contracts import del_category
    return del_category()


@app.route("/token-contracts/rename-category", methods=["POST"])
def token_category_rename():
    from routes.token_contracts import rename_category
    return rename_category()


@app.route("/token-contracts/api/prices")
def token_prices():
    from routes.token_contracts import api_prices
    return api_prices()


@app.route("/smart-money")
def smart_money():
    from routes.smart_money import smart_money_page
    return smart_money_page()


@app.route("/smart-money/save", methods=["POST"])
def smart_money_save():
    from routes.smart_money import smart_money_save
    return smart_money_save()


@app.route("/smart-money/delete", methods=["POST"])
def smart_money_delete():
    from routes.smart_money import smart_money_delete
    return smart_money_delete()


@app.route("/smart-money/sync/<wallet_id>", methods=["POST"])
def smart_money_sync(wallet_id):
    from routes.smart_money import smart_money_sync
    return smart_money_sync(wallet_id)


@app.route("/static/<path:filename>")
def static_file(filename):
    return send_from_directory(app.static_folder, filename)


if __name__ == "__main__":
    port = int(os.environ.get("WORKTABLE_PORT", "8084"))
    print(f"工作台已启动：http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
