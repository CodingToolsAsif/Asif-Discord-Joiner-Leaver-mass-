import requests
import time
import sys
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.live import Live
from rich.spinner import Spinner
from rich.rule import Rule
from rich.align import Align
from rich import box

console = Console()

BANNER = """
[bold red]
 _     _____    ___   _   _____     _     _     _     
| |   | ____|  / _ \\ | | | ____|   / \\   | |   | |    
| |   |  _|   | | | || | |  _|    / _ \\  | |   | |    
| |___| |___  | |_| || |_| |___  / ___ \\ | |___| |___ 
|_____|_____|  \\___/ |___|_____|/_/   \\_\\|_____|_____|
[/bold red]
[bold white]       Discord — Leave All Servers[/bold white]
[dim]       by jakason  |  made by asif[/dim]
"""

BASE = "https://discord.com/api/v10"


def api(method, path, token, **kwargs):
    headers = {
        "Authorization": token.strip().replace("\n","").replace("\r",""),
    }
    if kwargs.get("json") is not None:
        headers["Content-Type"] = "application/json"
    try:
        return requests.request(method, BASE + path, headers=headers, **kwargs)
    except requests.exceptions.ConnectionError:
        return None


def err(r):
    if r is None:
        return "No response (connection error)"
    try:
        return f"{r.status_code} — {r.json().get('message', r.text)}"
    except Exception:
        return f"{r.status_code} — {r.text}"


def main():
    console.clear()
    console.print(Align.center(BANNER))
    console.print(Rule(style="red"))

    token = Prompt.ask("[bold red]Enter your Discord token[/bold red]").strip()

    # verify token
    with Live(Spinner("dots", text="[cyan]Verifying token...[/cyan]"), console=console, transient=True):
        r = api("GET", "/users/@me", token)

    if not r or r.status_code != 200:
        console.print(f"[red]Invalid token: {err(r)}[/red]")
        sys.exit(1)

    user = r.json()
    console.print(f"[green]✓ Logged in as [bold]{user.get('username')}#{user.get('discriminator','0')}[/bold][/green]\n")

    # fetch all guilds
    with Live(Spinner("dots", text="[cyan]Fetching servers...[/cyan]"), console=console, transient=True):
        r = api("GET", "/users/@me/guilds", token)

    if not r or r.status_code != 200:
        console.print(f"[red]Failed to fetch servers: {err(r)}[/red]")
        sys.exit(1)

    all_guilds = r.json()
    leavable = [g for g in all_guilds if not g.get("owner")]
    owned = [g for g in all_guilds if g.get("owner")]

    if not leavable:
        console.print("[yellow]No servers to leave (you own all of them or you're in none).[/yellow]")
        sys.exit(0)

    # show table
    table = Table(title=f"[bold red]Servers to Leave ({len(leavable)})[/bold red]", box=box.ROUNDED, border_style="red")
    table.add_column("#", style="dim", width=4)
    table.add_column("Server Name", style="bold white")
    table.add_column("ID", style="green")
    for i, g in enumerate(leavable, 1):
        table.add_row(str(i), g.get("name", "?"), g.get("id", "?"))
    console.print(table)

    if owned:
        console.print(f"[dim]Skipping {len(owned)} server(s) you own.[/dim]\n")

    delay = float(Prompt.ask("[cyan]Delay between leaves (seconds)[/cyan]", default="1"))

    if not Confirm.ask(f"[bold red]Leave all {len(leavable)} servers?[/bold red]"):
        console.print("[yellow]Cancelled.[/yellow]")
        sys.exit(0)

    console.print()
    left = 0
    failed = 0
    for g in leavable:
        r2 = api("DELETE", f"/users/@me/guilds/{g['id']}", token)
        if r2 and r2.status_code == 204:
            left += 1
            console.print(f"[green]✓ Left[/green] [white]{g.get('name','?')}[/white]")
        elif r2 and r2.status_code == 429:
            wait = r2.json().get("retry_after", delay)
            console.print(f"[yellow]Rate limited, waiting {wait}s...[/yellow]")
            time.sleep(float(wait))
            # retry once
            r3 = api("DELETE", f"/users/@me/guilds/{g['id']}", token)
            if r3 and r3.status_code == 204:
                left += 1
                console.print(f"[green]✓ Left[/green] [white]{g.get('name','?')}[/white] [dim](retry)[/dim]")
            else:
                failed += 1
                console.print(f"[red]✗ Failed[/red] [white]{g.get('name','?')}[/white]: {err(r3)}")
        else:
            failed += 1
            console.print(f"[red]✗ Failed[/red] [white]{g.get('name','?')}[/white]: {err(r2)}")
        time.sleep(delay)

    console.print()
    console.print(Panel(
        f"[green]Left: {left}[/green]  |  [red]Failed: {failed}[/red]  |  [dim]Skipped (owned): {len(owned)}[/dim]",
        title="[bold]Done[/bold]",
        border_style="red"
    ))


if __name__ == "__main__":
    main()
