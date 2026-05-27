import requests
import time
import sys
from rich.console import Console
from rich.prompt import Prompt
from rich.live import Live
from rich.spinner import Spinner
from rich.rule import Rule
from rich.align import Align
from rich.panel import Panel

console = Console()

BANNER = """
[bold green]
  _   ___ ___ ___      _  ___  ___ _  _ ___ ___ 
 /_\\ / __|_ _| __|___ | |/ _ \\|_ _| \\| | __| _ \\
/ _ \\\\__ \\| || _|___  | | (_) || || .` | _||   /
/_/ \\_\\___/___|_|     |_|\\___/___|_|\\_|___|_|_\\ 
[/bold green]
[bold white]          Asif-Joiner — Discord Server Joiner[/bold white]
[dim]          by jakason  |  made by asif[/dim]
"""

BASE = "https://discord.com/api/v10"
CAPSOLVER_API = "https://api.capsolver.com"


def make_headers(token):
    return {
        "Authorization": token.strip().replace("\n", "").replace("\r", ""),
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    }


def api_get(path, token):
    try:
        return requests.get(BASE + path, headers=make_headers(token), timeout=15)
    except requests.exceptions.ConnectionError:
        return None


def api_post(path, token, body=None):
    try:
        return requests.post(BASE + path, headers=make_headers(token), json=body or {}, timeout=15)
    except requests.exceptions.ConnectionError:
        return None


def err(r):
    if r is None:
        return "No response (connection error)"
    try:
        data = r.json()
        return f"{r.status_code} — {data.get('message', r.text)}"
    except Exception:
        return f"{r.status_code} — {r.text}"


def parse_code(invite):
    return invite.strip().rstrip("/").split("/")[-1].split("?")[0]


def verify_capsolver(capsolver_key):
    try:
        r = requests.post(f"{CAPSOLVER_API}/getBalance",
                          json={"clientKey": capsolver_key}, timeout=10)
        data = r.json()
        if data.get("errorId") == 0:
            return True, data.get("balance", "?")
        return False, data.get("errorDescription", "Invalid key")
    except Exception as e:
        return False, str(e)



    payload = {
        "clientKey": capsolver_key,
        "task": {
            "type": "HCaptchaTaskProxyLess",
            "websiteURL": "https://discord.com",
            "websiteKey": sitekey,
            "enterprisePayload": {"rqdata": rqdata},
            "isInvisible": False,
        }
    }
    try:
        r = requests.post(f"{CAPSOLVER_API}/createTask", json=payload, timeout=30)
        data = r.json()
    except Exception as e:
        console.print(f"[red]CapSolver request error: {e}[/red]")
        return None

    if data.get("errorId"):
        console.print(f"[red]CapSolver error: {data.get('errorDescription')}[/red]")
        return None

    task_id = data.get("taskId")
    console.print(f"[dim]Solving captcha (task {task_id})...[/dim]")

    for _ in range(30):
        time.sleep(3)
        try:
            r2 = requests.post(
                f"{CAPSOLVER_API}/getTaskResult",
                json={"clientKey": capsolver_key, "taskId": task_id},
                timeout=30
            )
            result = r2.json()
        except Exception:
            continue

        if result.get("status") == "ready":
            return result.get("solution", {}).get("gRecaptchaResponse")
        if result.get("errorId"):
            console.print(f"[red]CapSolver solve error: {result.get('errorDescription')}[/red]")
            return None

    console.print("[red]CapSolver timed out.[/red]")
    return None


def join_one(code, token, capsolver_key):
    r = api_post(f"/invites/{code}", token)

    if r is None:
        return False, "No response (connection error)"

    if r.status_code == 200:
        guild = r.json().get("guild", {})
        return True, guild.get("name", code)

    if r.status_code == 429:
        try:
            wait = r.json().get("retry_after", 5)
        except Exception:
            wait = 5
        return "ratelimit", wait

    if r.status_code == 400:
        try:
            body = r.json()
        except Exception:
            return False, err(r)

        if "captcha_sitekey" in body:
            if not capsolver_key:
                return False, "Captcha required — enter a CapSolver API key to bypass"

            sitekey = body.get("captcha_sitekey", "")
            rqdata  = body.get("captcha_rqdata", "")
            rqtoken = body.get("captcha_rqtoken", "")

            console.print(f"[yellow]Captcha required for [bold]{code}[/bold] — solving...[/yellow]")
            captcha_key = solve_hcaptcha(capsolver_key, sitekey, rqdata, rqtoken)

            if not captcha_key:
                return False, "Captcha solve failed"

            r2 = api_post(f"/invites/{code}", token, {
                "captcha_key": captcha_key,
                "captcha_rqtoken": rqtoken,
            })
            if r2 and r2.status_code == 200:
                guild = r2.json().get("guild", {})
                return True, guild.get("name", code)
            return False, err(r2)

    return False, err(r)


def main():
    console.clear()
    console.print(Align.center(BANNER))
    console.print(Rule(style="green"))

    token = Prompt.ask("[bold green]Discord token[/bold green]").strip()
    token = token.replace("\n", "").replace("\r", "")

    with Live(Spinner("dots", text="[cyan]Verifying token...[/cyan]"), console=console, transient=True):
        r = api_get("/users/@me", token)

    if not r or r.status_code != 200:
        console.print(f"[red]Invalid token: {err(r)}[/red]")
        sys.exit(1)

    user = r.json()
    console.print(f"[green]✓ Logged in as [bold]{user.get('username')}#{user.get('discriminator', '0')}[/bold][/green]")

    capsolver_key = Prompt.ask(
        "\n[cyan]CapSolver API key (captcha bypass, leave blank to skip)[/cyan]",
        default=""
    ).strip() or None

    if capsolver_key:
        ok, info = verify_capsolver(capsolver_key)
        if ok:
            console.print(f"[green]✓ CapSolver enabled — balance: ${info}[/green]")
        else:
            console.print(f"[red]✗ CapSolver key invalid: {info}[/red]")
            capsolver_key = None
    else:
        console.print("[yellow]⚠  No CapSolver key — captcha-protected servers will fail[/yellow]")

    console.print("\n[dim]Paste invite links or codes one per line. Blank line = done.[/dim]\n")

    invites = []
    while True:
        line = Prompt.ask("[green]Invite[/green]", default="").strip()
        if not line:
            break
        invites.append(line)

    if not invites:
        console.print("[yellow]No invites entered.[/yellow]")
        sys.exit(0)

    delay = float(Prompt.ask("[cyan]Delay between joins (seconds)[/cyan]", default="1.5"))

    console.print()
    joined = 0
    failed = 0

    for invite in invites:
        code = parse_code(invite)

        status, data = join_one(code, token, capsolver_key)

        if status == "ratelimit":
            console.print(f"[yellow]Rate limited — waiting {data}s...[/yellow]")
            time.sleep(float(data))
            status, data = join_one(code, token, capsolver_key)

        if status is True:
            joined += 1
            console.print(f"[green]✓ Joined[/green] [bold white]{data}[/bold white]")
        else:
            failed += 1
            console.print(f"[red]✗ Failed[/red] [dim]{code}[/dim]: {data}")

        time.sleep(delay)

    console.print()
    console.print(Panel(
        f"[green]Joined: {joined}[/green]  |  [red]Failed: {failed}[/red]",
        title="[bold]Done[/bold]",
        border_style="green"
    ))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
