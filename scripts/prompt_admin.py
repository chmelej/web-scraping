import sys
import os
sys.path.append(os.getcwd())

import click
from src.llm.prompts import PromptManager
from src.utils.db import get_db_connection

@click.group()
def cli():
    """LLM prompt management"""
    pass

@cli.command()
@click.argument('use_case')
@click.argument('language')
def show(use_case, language):
    """Zobraz prompt"""
    try:
        pm = PromptManager()
        config = pm.get_prompt(use_case, language)

        click.echo(f"Use case: {use_case}/{language}")
        click.echo(f"Model: {config['model']}")
        click.echo(f"Max tokens: {config['max_tokens']}")
        click.echo("\nTemplate:")
        click.echo(config['prompt_template'])
    except Exception as e:
        click.echo(f"Error: {e}")

@cli.command()
@click.argument('use_case')
@click.argument('language')
def edit(use_case, language):
    """Edit prompt v $EDITOR"""
    try:
        pm = PromptManager()
        conn = get_db_connection()

        # Get current
        try:
            config = pm.get_prompt(use_case, language)
            current = config['prompt_template']
        except:
            current = ""

        # Edit
        new_text = click.edit(current)
        if not new_text:
            click.echo("Aborted")
            return

        # Save
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO llm_prompts (use_case, language, prompt_template)
            VALUES (%s, %s, %s)
            ON CONFLICT (use_case, language) DO UPDATE
            SET prompt_template = EXCLUDED.prompt_template
        """, (use_case, language, new_text))
        conn.commit()

        click.echo("✓ Saved")
    except Exception as e:
        click.echo(f"Error: {e}")

@cli.command()
def stats():
    """Usage statistics"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT p.use_case, p.language,
                   SUM(s.executions) as total,
                   ROUND(AVG(s.successes::float/NULLIF(s.executions,0)) * 100, 1) as success_rate
            FROM llm_prompts p
            LEFT JOIN prompt_stats s ON p.id = s.prompt_id
            WHERE s.date > CURRENT_DATE - 7
            GROUP BY p.use_case, p.language
            ORDER BY total DESC NULLS LAST
        """)

        click.echo(f"{'Use Case':<20} {'Lang':<6} {'Calls':>8} {'Success':>8}")
        click.echo("-" * 50)

        for row in cur.fetchall():
            calls = row[2] or 0
            success = row[3] or 0
            click.echo(f"{row[0]:<20} {row[1]:<6} {calls:>8} {success:>7}%")
    except Exception as e:
        click.echo(f"Error: {e}")

@cli.command()
def list_all():
    """Seznam všech promptů"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT use_case, language, model, is_active
            FROM llm_prompts
            ORDER BY use_case, language
        """)

        for row in cur.fetchall():
            active = "✓" if row[3] else "✗"
            click.echo(f"{active} {row[0]}/{row[1]} ({row[2]})")
    except Exception as e:
        click.echo(f"Error: {e}")

if __name__ == '__main__':
    cli()
