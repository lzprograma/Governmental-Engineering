from __future__ import annotations
import argparse
import json
import sys
from .core.contracts import Task, RiskLevel
from .core.config import settings
from .service import ACIAService


def main() -> None:
    argv = list(sys.argv[1:])
    if len(argv) >= 2 and argv[0].casefold() == "on" and argv[1].casefold() == "server":
        argv = ["on-server", *argv[2:]]
    parser = argparse.ArgumentParser(prog="lrg-acia", description="LUNZ — infraestrutura nacional ACIA")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("dashboard", help="Mostra o estado do protótipo")
    task_parser = sub.add_parser("task", help="Executa uma tarefa no baseline local")
    task_parser.add_argument("prompt")
    task_parser.add_argument("--domain", default="general")
    task_parser.add_argument("--risk", choices=[e.value for e in RiskLevel], default="low")
    task_parser.add_argument("--requires-evidence", action="store_true")
    server_parser = sub.add_parser("on-server", help="Abre o painel web local de Lunz")
    server_parser.add_argument("--host", default="127.0.0.1")
    server_parser.add_argument("--port", type=int, default=8765)
    server_parser.add_argument("--no-browser", action="store_true", help="Não abrir o navegador automaticamente")
    api_parser = sub.add_parser("api", help="Inicia a API opcional em loopback")
    api_parser.add_argument("--host", default=settings.api_host)
    api_parser.add_argument("--port", type=int, default=settings.api_port)
    args = parser.parse_args(argv)

    if args.command == "on-server":
        try:
            from .on_server import run_server
            run_server(host=args.host, port=args.port, open_browser=not args.no_browser)
        except ImportError as exc:
            raise SystemExit("Instale as dependências do painel: pip install -e '.[server]'") from exc
        return

    if args.command == "api":
        try:
            import uvicorn
        except ImportError as exc:
            raise SystemExit("Instale a dependência opcional: pip install -e '.[api]'") from exc
        if args.host not in {"127.0.0.1", "localhost", "::1"}:
            raise SystemExit("O protótipo só pode iniciar em loopback; exposição em rede não está habilitada.")
        uvicorn.run("lrg_acia.interfaces.api:app", host=args.host, port=args.port, reload=False)
        return

    service = ACIAService()
    if args.command == "dashboard":
        print(json.dumps(service.dashboard(), ensure_ascii=False, indent=2))
    elif args.command == "task":
        task = Task(prompt=args.prompt, domain=args.domain, risk_level=RiskLevel(args.risk),
                    required_evidence=args.requires_evidence)
        result = service.execute_task(task)
        print(json.dumps({
            "task_id": result.task_id, "status": result.status.value,
            "answer": result.answer, "selected_models": result.selected_models,
            "confidence": result.confidence, "cost": result.cost,
            "trace_id": result.trace_id, "limitations": result.limitations,
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
