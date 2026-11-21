"""CLI entry point for IRONCLAD with Rich terminal formatting."""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ironclad import __version__
from ironclad.config import get_settings
from ironclad.errors import (
    KnowledgeBaseNotFoundError,
)
from ironclad.logging import setup_logging
from ironclad.services.status import get_status, run_diagnostics

app = typer.Typer(
    name="ironclad",
    help="IRONCLAD: A minimal, reliable, production-minded Retrieval-Augmented Generation CLI.",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()
err_console = Console(stderr=True)


def output_json(data: object) -> None:
    """Output machine-readable JSON without Rich terminal wrapping."""
    if isinstance(data, str):
        sys.stdout.write(data + "\n")
    else:
        sys.stdout.write(json.dumps(data, indent=2) + "\n")
    sys.stdout.flush()


def version_callback(value: bool):
    if value:
        console.print(f"[bold cyan]IRONCLAD[/bold cyan] version [bold green]{__version__}[/bold green]")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", help="Show the application version and exit.", callback=version_callback
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose debug logging."),
):
    """Production-minded RAG developer CLI."""
    setup_logging(verbose=verbose)


@app.command()
def init(
    path: Path = typer.Argument(
        Path("."),
        help="Path to project directory to initialize knowledge base for.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON."),
):
    """Create or initialize an Ironclad knowledge base in the target project."""
    try:
        settings = get_settings(path)
        kb_dir = settings.ironclad_path
        kb_dir.mkdir(parents=True, exist_ok=True)
        (kb_dir / "vectors").mkdir(parents=True, exist_ok=True)

        # Initialize SQLite metadata database
        db_path = settings.metadata_db_path
        created = not db_path.exists()

        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata_info (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    file_path TEXT PRIMARY KEY,
                    file_hash TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    mtime REAL NOT NULL,
                    doc_type TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    indexed_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    content TEXT NOT NULL,
                    token_count INTEGER NOT NULL,
                    char_count INTEGER NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    heading TEXT,
                    file_hash TEXT NOT NULL,
                    doc_type TEXT NOT NULL,
                    FOREIGN KEY (file_path) REFERENCES documents(file_path) ON DELETE CASCADE
                );
                """
            )
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT OR IGNORE INTO metadata_info (key, value) VALUES ('schema_version', '1');"
            )
            conn.execute(
                "INSERT OR IGNORE INTO metadata_info (key, value) VALUES ('created_at', ?);",
                (now,),
            )
            conn.execute(
                "INSERT OR REPLACE INTO metadata_info (key, value) VALUES ('embedding_model', ?);",
                (settings.embedding_model,),
            )
            conn.commit()

        if json_output:
            output_json(
                {
                    "status": "success",
                    "initialized": True,
                    "created": created,
                    "project_root": str(settings.project_root),
                    "knowledge_base_path": str(kb_dir),
                }
            )
        else:
            action = "Initialized new" if created else "Re-verified existing"
            console.print(
                Panel.fit(
                    f"[bold green]✔[/bold green] {action} Ironclad knowledge base.\n\n"
                    f"[dim]Project Root:[/dim] [cyan]{settings.project_root}[/cyan]\n"
                    f"[dim]Knowledge Base:[/dim] [cyan]{kb_dir}[/cyan]\n"
                    f"[dim]Metadata DB:[/dim] [cyan]{db_path}[/cyan]\n"
                    f"[dim]Embedding Model:[/dim] [cyan]{settings.embedding_model}[/cyan]\n\n"
                    f"Next step: Run [bold white]ironclad ingest {path}[/bold white] to index documents.",
                    title="[bold cyan]IRONCLAD INIT[/bold cyan]",
                    border_style="green",
                )
            )
    except Exception as e:
        err_console.print(f"[bold red]Initialization failed:[/bold red] {e}")
        raise typer.Exit(code=getattr(e, "exit_code", 1)) from e


@app.command()
def ingest(
    path: Path = typer.Argument(
        Path("."),
        help="Path to project directory containing documents and code.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    update: bool = typer.Option(
        False, "--update", help="Incrementally update changed files and remove stale entries."
    ),
    reindex: bool = typer.Option(
        False, "--reindex", help="Wipe existing index and re-ingest all documents from scratch."
    ),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON."),
):
    """Ingest documents and build or update the knowledge base index."""
    settings = get_settings(path)
    if not settings.is_initialized():
        err_console.print(
            f"[bold red]Error:[/bold red] Knowledge base not initialized at '{settings.project_root}'.\n"
            f"[yellow]Run `ironclad init {path}` first.[/yellow]"
        )
        raise typer.Exit(code=KnowledgeBaseNotFoundError.exit_code)

    from ironclad.services.ingest import run_ingestion

    try:
        summary = run_ingestion(settings=settings, target_path=path, update=update, reindex=reindex)
    except KeyboardInterrupt:
        err_console.print("\n[yellow]Ingestion interrupted. Knowledge base remains intact.[/yellow]")
        raise typer.Exit(code=130) from None
    except Exception as e:
        err_console.print(f"[bold red]Ingestion failed:[/bold red] {e}")
        raise typer.Exit(code=getattr(e, "exit_code", 1)) from e

    if json_output:
        output_json(summary.to_dict())
        return

    table = Table(
        title="IRONCLAD Ingestion Summary",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Metric", style="dim", width=25)
    table.add_column("Value")

    table.add_row("Mode", "[bold cyan]Incremental Update[/bold cyan]" if update else "[bold green]Full Ingestion[/bold green]")
    table.add_row("Target Directory", summary.target_path)
    table.add_row("Files Added", str(summary.files_added))
    table.add_row("Files Updated", str(summary.files_updated))
    table.add_row("Files Deleted", str(summary.files_deleted))
    table.add_row("Files Skipped (Unchanged)", str(summary.files_skipped))
    table.add_row("Total Indexed Documents", f"[bold green]{summary.total_files}[/bold green]")
    table.add_row("Total Chunks Created", f"[bold green]{summary.total_chunks}[/bold green]")
    table.add_row("Duration", f"{summary.duration_seconds}s")

    console.print(table)

    if summary.errors:
        console.print("\n[bold red]Ingestion Warnings / Errors:[/bold red]")
        for err in summary.errors:
            console.print(f"  • [yellow]{err}[/yellow]")
    else:
        console.print(
            "\n[bold green]✔ Ingestion complete.[/bold green] Knowledge base ready for queries."
        )


@app.command()
def ask(
    query: str = typer.Argument(..., help="Question to answer using grounded retrieved context."),
    limit: int = typer.Option(5, "--limit", "-n", help="Maximum evidence passages to retrieve."),
    path: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Target project path (defaults to current working directory)."
    ),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON."),
):
    """Retrieve evidence and generate a grounded answer using Gemma."""
    settings = get_settings(path)
    if not settings.is_initialized():
        err_console.print(
            "[bold red]Error:[/bold red] Knowledge base not found.\n"
            "[yellow]Run `ironclad init` and `ironclad ingest` first.[/yellow]"
        )
        raise typer.Exit(code=KnowledgeBaseNotFoundError.exit_code)

    from ironclad.generation.gemma import generate_grounded_answer
    from ironclad.generation.provider import get_inference_provider
    from ironclad.services.query import execute_hybrid_search

    # 1. Retrieve hybrid evidence
    try:
        selected_evidence, all_fused, total_tokens = execute_hybrid_search(
            settings=settings,
            query=query,
            top_k=limit,
        )
    except Exception as e:
        err_console.print(f"[bold red]Retrieval failed:[/bold red] {e}")
        raise typer.Exit(code=getattr(e, "exit_code", 1)) from e

    # 2. Privacy notification for remote hosted inference
    if not json_output and settings.inference_provider == "openrouter" and selected_evidence:
        err_console.print(
            f"[dim]Notice: Transmitting {len(selected_evidence)} retrieved evidence blocks "
            f"(~{total_tokens} tokens) to OpenRouter ({settings.openrouter_model}).[/dim]"
        )

    # 3. Call generation pipeline
    try:
        provider = get_inference_provider(settings)
        rag_response = generate_grounded_answer(
            query=query,
            evidence=selected_evidence,
            provider=provider,
        )
    except Exception as e:
        err_console.print(f"[bold red]Generation failed:[/bold red] {e}")
        raise typer.Exit(code=getattr(e, "exit_code", 1)) from e

    if json_output:
        output_json(rag_response.model_dump(mode="json"))
        return

    # 4. Display formatted CLI output
    meta_info = (
        f"[dim]Model: {rag_response.model_used} | "
        f"Latency: {rag_response.latency_ms}ms | "
        f"Evidence Chunks: {rag_response.retrieved_chunks_count}[/dim]"
    )

    if rag_response.insufficient_evidence:
        console.print(
            Panel(
                f"{rag_response.answer}\n\n{meta_info}",
                title="[bold yellow]⚠ Insufficient Evidence[/bold yellow]",
                border_style="yellow",
            )
        )
        return

    console.print(
        Panel(
            f"{rag_response.answer}\n\n{meta_info}",
            title="[bold green]IRONCLAD Answer[/bold green]",
            border_style="green",
        )
    )

    if rag_response.citations:
        cit_table = Table(
            title="Verified Ground-Truth Citations",
            show_header=True,
            header_style="bold cyan",
        )
        cit_table.add_column("#", style="bold", width=4)
        cit_table.add_column("Source File", style="cyan", width=30)
        cit_table.add_column("Lines", style="green", width=12)
        cit_table.add_column("Excerpt", style="dim")

        for cit in rag_response.citations:
            cit_table.add_row(
                f"[{cit.citation_index}]",
                cit.file_path,
                f"L{cit.start_line}-L{cit.end_line}",
                cit.excerpt.replace("\n", " ").strip()[:100],
            )

        console.print(cit_table)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search term or phrase to retrieve matching excerpts."),
    limit: int = typer.Option(5, "--limit", "-n", help="Maximum number of search results to return."),
    path: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Target project path (defaults to current working directory)."
    ),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON."),
):
    """Display matching excerpts, relevance information, and source locations without invoking LLM."""
    settings = get_settings(path)
    if not settings.is_initialized():
        err_console.print(
            "[bold red]Error:[/bold red] Knowledge base not found.\n"
            "[yellow]Run `ironclad init` and `ironclad ingest` first.[/yellow]"
        )
        raise typer.Exit(code=KnowledgeBaseNotFoundError.exit_code)

    from ironclad.services.query import execute_hybrid_search

    try:
        selected_context, all_fused, total_tokens = execute_hybrid_search(
            settings=settings,
            query=query,
            top_k=limit,
        )
    except Exception as e:
        err_console.print(f"[bold red]Search failed:[/bold red] {e}")
        raise typer.Exit(code=getattr(e, "exit_code", 1)) from e

    if json_output:
        output_json(
            {
                "query": query,
                "total_results": len(selected_context),
                "total_tokens": total_tokens,
                "results": [r.model_dump(mode="json") for r in selected_context],
            }
        )
        return

    if not selected_context:
        console.print(f"\n[yellow]No matching results found for:[/yellow] [bold white]{query}[/bold white]\n")
        return

    console.print(
        f"\n[bold cyan]Found {len(selected_context)} matching passages[/bold cyan] "
        f"[dim](Context: ~{total_tokens} tokens)[/dim] for [bold white]\"{query}\"[/bold white]:\n"
    )

    for idx, res in enumerate(selected_context, start=1):
        dense_str = f"#{res.vector_rank}" if res.vector_rank else "—"
        sparse_str = f"#{res.lexical_rank}" if res.lexical_rank else "—"

        panel_content = (
            f"[dim]Source:[/dim] [bold cyan]{res.file_path}:{res.start_line}-{res.end_line}[/bold cyan]  "
            f"[dim]| Type:[/dim] [yellow]{res.doc_type}[/yellow]  "
            f"[dim]| RRF Score:[/dim] [green]{res.score:.4f}[/green]  "
            f"[dim]| Dense Rank:[/dim] {dense_str}  "
            f"[dim]| Sparse Rank:[/dim] {sparse_str}\n\n"
            f"{res.content.strip()}"
        )
        console.print(
            Panel(
                panel_content,
                title=f"[bold green]Result [{idx}][/bold green]",
                border_style="cyan" if idx == 1 else "dim",
                expand=False,
            )
        )


@app.command()
def status(
    path: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Target project path (defaults to current working directory)."
    ),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON."),
):
    """Display index statistics, configuration status, embedding model, and provider status."""
    settings = get_settings(path)
    stat = get_status(settings)

    if json_output:
        output_json(stat.model_dump(mode="json"))
        return

    table = Table(title="IRONCLAD Knowledge Base Status", show_header=True, header_style="bold cyan")
    table.add_column("Property", style="dim", width=25)
    table.add_column("Value")

    table.add_row(
        "Status",
        "[bold green]Initialized[/bold green]" if stat.initialized else "[bold red]Not Initialized[/bold red]",
    )
    table.add_row("Knowledge Base Path", str(stat.knowledge_base_path))
    table.add_row("Total Documents", str(stat.total_files))
    table.add_row("Total Chunks", str(stat.total_chunks))
    table.add_row("Schema Version", str(stat.index_version))
    table.add_row("Last Ingested", stat.last_ingested_at or "(never)")
    table.add_row("Embedding Model", stat.embedding_model or "(not set)")
    table.add_row("Inference Provider", stat.inference_provider)
    table.add_row("Inference Model", stat.inference_model)
    table.add_row(
        "Integrity",
        "[bold green]Consistent[/bold green]" if stat.is_consistent else "[bold red]Inconsistencies Detected[/bold red]",
    )

    console.print(table)

    if stat.inconsistencies:
        console.print("\n[bold red]Inconsistencies / Warnings:[/bold red]")
        for inc in stat.inconsistencies:
            console.print(f"  • [yellow]{inc}[/yellow]")


@app.command()
def doctor(
    path: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Target project path (defaults to current working directory)."
    ),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON."),
):
    """Diagnose configuration, permissions, storage, embedding-runtime, and inference connectivity."""
    settings = get_settings(path)
    report = run_diagnostics(settings)

    if json_output:
        output_json(report.model_dump(mode="json"))
        if not report.all_passed:
            raise typer.Exit(code=1)
        return

    table = Table(title="IRONCLAD System Doctor Diagnostics", show_header=True, header_style="bold cyan")
    table.add_column("Category", style="dim", width=15)
    table.add_column("Check", style="bold", width=30)
    table.add_column("Status", width=10)
    table.add_column("Details")

    for check in report.checks:
        status_text = "[bold green]PASS[/bold green]" if check.passed else "[bold red]FAIL[/bold red]"
        msg = check.message
        if check.hint and not check.passed:
            msg += f"\n[dim yellow]Hint: {check.hint}[/dim yellow]"
        table.add_row(check.category, check.name, status_text, msg)

    console.print(table)

    if report.all_passed:
        console.print("\n[bold green]✔ All diagnostic checks passed![/bold green]")
    else:
        console.print("\n[bold red]✖ Some diagnostic checks failed. Review hints above.[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def config(
    path: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Target project path (defaults to current working directory)."
    ),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON."),
):
    """Show configuration guidance and safe provider configuration without exposing secrets."""
    settings = get_settings(path)
    cfg_data = settings.safe_dict()

    if json_output:
        output_json(cfg_data)
        return

    table = Table(title="IRONCLAD Configuration", show_header=True, header_style="bold cyan")
    table.add_column("Key", style="dim", width=25)
    table.add_column("Value")

    for k, v in cfg_data.items():
        table.add_row(k, str(v))

    console.print(table)
    console.print(
        "\n[dim]To modify configuration, edit .env or set environment variables prefixed with IRONCLAD_.[/dim]"
    )


# ============================================================================
# Personalized Learning CLI Sub-Commands
# ============================================================================

from ironclad.learning.engine import PersonalizedLearningEngine
from ironclad.learning.graph import ConceptGraph, get_available_curricula
from ironclad.learning.models import LearningModality, LearningPace, StruggleType
from ironclad.learning.storage import LearningStorage
from ironclad.learning.teacher import TeacherDashboardService
from ironclad.learning.web import _seed_demo_classroom, run_dashboard_server

learn_app = typer.Typer(name="learn", help="Personalized adaptive learning & Socratic sessions.")
student_app = typer.Typer(name="student", help="Manage dynamic student profiles and mastery vectors.")
teacher_app = typer.Typer(name="teacher", help="Teacher analytics, explainable interventions, and web dashboard.")

app.add_typer(learn_app, name="learn")
app.add_typer(student_app, name="student")
app.add_typer(teacher_app, name="teacher")


def _get_learning_context(path: Optional[Path] = None, domain: str = "python_programming"):
    settings = get_settings(path)
    learning_db = settings.ironclad_path / "learning.db"
    storage = LearningStorage(learning_db)

    # Seed demo students if brand new
    if not storage.list_students():
        _seed_demo_classroom(storage)

    raw_curricula = get_available_curricula()
    curr = raw_curricula.get(domain, raw_curricula.get("python_programming"))
    graph = ConceptGraph(curr)
    return settings, storage, graph


@learn_app.command("session")
def learn_session(
    student_id: str = typer.Option("s_alex", "--student", "-s", help="Student ID."),
    concept_id: Optional[str] = typer.Option(None, "--concept", "-c", help="Concept ID."),
    domain: str = typer.Option("python_programming", "--domain", "-d", help="Curriculum domain."),
    modality: Optional[str] = typer.Option(None, "--modality", "-m", help="Preferred modality (worked_examples, visual, simulation, real_world, practice_questions)."),
    answer: Optional[str] = typer.Option(None, "--answer", "-a", help="Pre-fill assessment answer (or runs interactively)."),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON."),
):
    """Run an adaptive Socratic learning session with grounded lesson generation."""
    from ironclad.learning.engine import PersonalizedLearningEngine
    from ironclad.learning.models import LearningModality

    settings, storage, graph = _get_learning_context(domain=domain)
    engine = PersonalizedLearningEngine(settings, storage, graph)

    student = storage.get_or_create_student(student_id, name=student_id, domain=domain)
    target_cid = concept_id or list(graph.concepts.keys())[0]

    chosen_mod = None
    if modality:
        try:
            chosen_mod = LearningModality(modality)
        except ValueError:
            console.print(f"[yellow]Unknown modality '{modality}'; defaulting to learner preference.[/yellow]")

    lesson = engine.create_lesson_plan(student_id, target_cid, requested_modality=chosen_mod)

    if json_output:
        output_json(lesson.model_dump())
        return

    console.print(Panel(
        f"[bold cyan]{lesson.concept_name}[/bold cyan]  [dim]• Modality: {lesson.modality.value.upper()}[/dim]\n"
        f"Learner: [bold green]{student.name}[/bold green] (Pace: {student.learning_pace.value})\n"
        f"{lesson.socratic_scaffolding or ''}",
        title="🎓 IRONCLAD Socratic Lesson",
        border_style="cyan"
    ))

    console.print(f"\n[bold]{lesson.explanation}[/bold]")
    console.print(f"\n{lesson.worked_example}")
    console.print(f"\n[bold yellow]Guided Practice:[/bold yellow] {lesson.guided_exercise}")

    if lesson.citations:
        console.print(f"\n[dim green]Grounded References: {', '.join(lesson.citations[:2])}[/dim green]")

    if lesson.assessment_items:
        q = lesson.assessment_items[0]
        console.print(Panel(
            f"[bold]{q.question}[/bold]\n"
            + ("\n".join(f"  • {opt}" for opt in q.options) if q.options else ""),
            title=f"Assessment Challenge ({q.id})",
            border_style="magenta"
        ))

        student_ans = answer
        if not student_ans:
            student_ans = typer.prompt("Your Answer")

        result = engine.evaluate_submission(
            student_id=student_id,
            concept_id=target_cid,
            item_id=q.id,
            student_answer=student_ans,
            latency_sec=6.0,
        )

        feedback_style = "bold green" if result.is_correct else "bold yellow"
        console.print(Panel(
            f"[{feedback_style}]{result.socratic_feedback}[/{feedback_style}]\n"
            f"[dim]Updated Mastery: {storage.get_student(student_id).concept_mastery.get(target_cid, 0.0) * 100:.1f}%[/dim]",
            title="Socratic Evaluation",
            border_style="green" if result.is_correct else "yellow"
        ))


@learn_app.command("diagnose")
def learn_diagnose(
    student_id: str = typer.Option(..., "--student", "-s", help="Student ID."),
    concept_id: str = typer.Option(..., "--concept", "-c", help="Target Concept ID."),
    domain: str = typer.Option("python_programming", "--domain", "-d", help="Curriculum domain."),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON."),
):
    """Diagnose upstream prerequisite root causes for student struggle."""
    settings, storage, graph = _get_learning_context(domain=domain)
    student = storage.get_student(student_id)
    if not student:
        err_console.print(f"[bold red]Student '{student_id}' not found.[/bold red]")
        raise typer.Exit(code=1)

    diag = graph.diagnose_root_cause(concept_id, student.concept_mastery)
    if json_output:
        if diag:
            output_json({
                "student_id": student_id,
                "target_concept": concept_id,
                "root_prerequisite": diag[0].id,
                "root_prerequisite_name": diag[0].name,
                "mastery_score": diag[1],
                "explanation": diag[2],
            })
        else:
            output_json({"student_id": student_id, "target_concept": concept_id, "root_prerequisite": None, "explanation": "Prerequisites sound."})
        return

    if diag:
        console.print(Panel(
            f"[bold red]Root-Cause Prerequisite Gap Detected![/bold red]\n\n"
            f"Prerequisite: [bold cyan]{diag[0].name}[/bold cyan] (ID: {diag[0].id})\n"
            f"Current Mastery: [bold yellow]{diag[1] * 100:.1f}%[/bold yellow]\n\n"
            f"{diag[2]}",
            title="Prerequisite Diagnostic Result",
            border_style="red"
        ))
    else:
        console.print(Panel(
            f"[bold green]No upstream prerequisite deficiency detected for '{concept_id}'.[/bold green]\n"
            f"Foundations are sound. Difficulty stems from current topic complexity or pacing.",
            title="Prerequisite Diagnostic Result",
            border_style="green"
        ))


@student_app.command("profile")
def student_profile(
    student_id: str = typer.Argument(..., help="Student identifier to inspect."),
    domain: str = typer.Option("python_programming", "--domain", "-d", help="Curriculum domain."),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON."),
):
    """Display dynamic student profile, learning pace, and concept mastery vector."""
    settings, storage, graph = _get_learning_context(domain=domain)
    student = storage.get_student(student_id)
    if not student:
        err_console.print(f"[bold red]Student '{student_id}' not found.[/bold red]")
        raise typer.Exit(code=1)

    if json_output:
        output_json(student.model_dump())
        return

    console.print(Panel(
        f"Student: [bold white]{student.name}[/bold white] [dim]({student.student_id})[/dim]\n"
        f"Domain: [cyan]{student.domain}[/cyan] | Learning Pace: [bold]{student.learning_pace.value}[/bold]\n"
        f"Preferred Modality: [green]{student.preferred_modality.value}[/green]\n"
        f"Assessments Completed: {student.correct_assessments}/{student.total_assessments} "
        f"({(student.correct_assessments/student.total_assessments*100) if student.total_assessments else 0:.0f}% accuracy)\n"
        f"Active Struggle Status: [{ 'red' if student.active_struggle else 'green' }]{student.active_struggle.value if student.active_struggle else 'Nominal'}[/]",
        title="🎓 Dynamic Learner Profile",
        border_style="cyan"
    ))

    table = Table(title=f"Concept Mastery Vector ({graph.title})", show_header=True, header_style="bold cyan")
    table.add_column("Concept ID", style="dim")
    table.add_column("Concept Name", style="bold")
    table.add_column("Difficulty", justify="center")
    table.add_column("Mastery", justify="right")
    table.add_column("Status")

    for node in graph.topological_order():
        score = student.concept_mastery.get(node.id, 0.0)
        pct = f"{score * 100:.1f}%"
        if score >= 0.8:
            status = "[bold green]Mastered[/bold green]"
        elif score >= 0.5:
            status = "[yellow]Developing[/yellow]"
        else:
            status = "[bold red]Prerequisite Gap[/bold red]"
        table.add_row(node.id, node.name, str(node.difficulty), pct, status)

    console.print(table)


@student_app.command("list")
def student_list(
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Filter by curriculum domain."),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON."),
):
    """List all registered learners and summary metrics."""
    settings, storage, _ = _get_learning_context()
    students = storage.list_students(domain=domain)

    if json_output:
        output_json([s.model_dump() for s in students])
        return

    table = Table(title="Registered Students Roster", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Domain")
    table.add_column("Pace")
    table.add_column("Modality")
    table.add_column("Accuracy", justify="right")
    table.add_column("Struggle Status")

    for s in students:
        acc = f"{(s.correct_assessments/s.total_assessments*100):.0f}%" if s.total_assessments else "N/A"
        st = f"[bold red]{s.active_struggle.value}[/bold red]" if s.active_struggle else "[green]Optimal[/green]"
        table.add_row(s.student_id, s.name, s.domain, s.learning_pace.value, s.preferred_modality.value, acc, st)

    console.print(table)


@student_app.command("create")
def student_create(
    student_id: str = typer.Option(..., "--id", "-i", help="Unique student ID."),
    name: str = typer.Option(..., "--name", "-n", help="Full student name."),
    domain: str = typer.Option("python_programming", "--domain", "-d", help="Curriculum domain."),
):
    """Enroll a new learner into the Personalized Learning Engine."""
    settings, storage, _ = _get_learning_context(domain=domain)
    profile = storage.get_or_create_student(student_id, name=name, domain=domain)
    console.print(f"[bold green]Enrolled learner '{profile.name}' ({profile.student_id}) in '{profile.domain}'.[/bold green]")


@teacher_app.command("dashboard")
def teacher_dashboard(
    domain: str = typer.Option("python_programming", "--domain", "-d", help="Curriculum domain."),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON."),
):
    """Display classroom-level analytics, weak concepts, and intervention alerts."""
    settings, storage, graph = _get_learning_context(domain=domain)
    service = TeacherDashboardService(storage, graph)
    summary = service.get_class_summary(domain)

    if json_output:
        output_json(summary.model_dump())
        return

    console.print(Panel(
        f"Domain: [bold cyan]{summary.domain}[/bold cyan] ({graph.title})\n"
        f"Enrolled Students: [bold]{summary.total_students}[/bold] | Class Average Mastery: [bold green]{summary.average_mastery_pct}%[/bold green]\n"
        f"Students Requiring Intervention: [bold red]{summary.students_requiring_intervention}[/bold red]\n"
        f"Primary Weak Concept: [bold yellow]{summary.main_weak_concept_name}[/bold yellow]\n\n"
        f"[bold white]Recommended Pedagogical Action:[/bold white]\n[cyan]{summary.top_recommended_intervention}[/cyan]",
        title="👨‍🏫 Teacher Intelligence Dashboard",
        border_style="blue"
    ))

    # Active alerts table
    if summary.active_alerts:
        alert_table = Table(title="🚨 Active Diagnostic Alerts", show_header=True, header_style="bold red")
        alert_table.add_column("Alert ID", style="dim")
        alert_table.add_column("Student", style="bold")
        alert_table.add_column("Concept")
        alert_table.add_column("Severity")
        alert_table.add_column("Diagnosis")

        for a in summary.active_alerts:
            sev_style = "bold red" if a.severity == "high" else "yellow"
            alert_table.add_row(a.alert_id, a.student_name, a.concept_id, f"[{sev_style}]{a.severity.upper()}[/{sev_style}]", a.message)
        console.print(alert_table)
    else:
        console.print("[dim green]✔ No active alerts. All students are progressing within expected bounds.[/dim green]")


@teacher_app.command("explain")
def teacher_explain(
    student_id: str = typer.Option(..., "--student", "-s", help="Student ID to explain intervention for."),
    concept_id: Optional[str] = typer.Option(None, "--concept", "-c", help="Optional concept ID."),
    domain: str = typer.Option("python_programming", "--domain", "-d", help="Curriculum domain."),
    json_output: bool = typer.Option(False, "--json", help="Output machine-readable JSON."),
):
    """Generate evidence-backed explainability rationale answering 'Why was this intervention recommended?'"""
    settings, storage, graph = _get_learning_context(domain=domain)
    service = TeacherDashboardService(storage, graph)
    try:
        expl = service.explain_intervention(student_id, concept_id)
    except Exception as e:
        err_console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)

    if json_output:
        output_json(expl.model_dump())
        return

    evidence_text = "\n".join(f"  • {e}" for e in expl.evidence_points)
    console.print(Panel(
        f"Student: [bold white]{expl.student_name}[/bold white] [dim]({expl.student_id})[/dim]\n"
        f"Target Concept: [cyan]{expl.target_concept}[/cyan] | Struggle Classification: [bold red]{expl.struggle_type.value}[/bold red]\n\n"
        f"[bold yellow]Recommended Action:[/bold yellow]\n{expl.recommended_action}\n\n"
        f"[bold]Diagnostic Evidence Points:[/bold]\n{evidence_text}\n\n"
        f"[bold green]Suggested Teaching Strategy:[/bold green]\n{expl.suggested_teaching_strategy}",
        title="🔍 Explainable AI: Why Was This Intervention Recommended?",
        border_style="magenta"
    ))


@teacher_app.command("serve")
@learn_app.command("serve")
def serve_dashboard(
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind dashboard server."),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host interface to bind."),
    path: Optional[Path] = typer.Option(None, "--path", help="Project path."),
):
    """Launch the interactive local Web Dashboard (Mastery Graph, Teacher Analytics, Student Studio)."""
    from ironclad.learning.web import run_dashboard_server

    settings = get_settings(path)
    console.print(Panel(
        f"[bold green]Starting IRONCLAD Personalized Learning Web Dashboard[/bold green]\n\n"
        f"URL: [bold cyan]http://{host}:{port}[/bold cyan]\n"
        f"Knowledge Base: [dim]{settings.ironclad_path}[/dim]\n\n"
        f"Press [bold red]Ctrl+C[/bold red] to stop the server.",
        title="🌐 Interactive Web Server",
        border_style="green"
    ))

    server = run_dashboard_server(settings, host=host, port=port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down dashboard server...[/yellow]")
        server.shutdown()


if __name__ == "__main__":
    app()

