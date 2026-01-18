from src.utils.db import get_db_connection, get_cursor

class PromptManager:
    def __init__(self):
        self.conn = get_db_connection()

    def get_prompt(self, use_case, language='cs'):
        """Získá prompt z DB"""
        with get_cursor(self.conn) as cur:
            cur.execute("""
                SELECT prompt_template, system_prompt, model, max_tokens, temperature, id
                FROM llm_prompts
                WHERE use_case = %s AND language = %s AND is_active = TRUE
            """, (use_case, language))

            result = cur.fetchone()

            if not result:
                # Fallback na EN
                cur.execute("""
                    SELECT prompt_template, system_prompt, model, max_tokens, temperature, id
                    FROM llm_prompts
                    WHERE use_case = %s AND language = 'en' AND is_active = TRUE
                """, (use_case,))
                result = cur.fetchone()

            if not result:
                raise ValueError(f"No prompt for {use_case}/{language}")

            return dict(result)

    def render(self, use_case, language, **variables):
        """Získá a vyrendruje prompt"""
        config = self.get_prompt(use_case, language)

        return {
            'prompt': config['prompt_template'].format(**variables),
            'system': config['system_prompt'],
            'model': config['model'],
            'max_tokens': config['max_tokens'],
            'temperature': config['temperature'],
            'prompt_id': config['id']
        }

    def log_execution(self, prompt_id, success=True, tokens=0):
        """Log usage stats"""
        with get_cursor(self.conn, dict_cursor=False) as cur:
            cur.execute("""
                INSERT INTO prompt_stats (prompt_id, executions, successes, avg_tokens)
                VALUES (%s, 1, %s, %s)
                ON CONFLICT (prompt_id, date) DO UPDATE SET
                    executions = prompt_stats.executions + 1,
                    successes = prompt_stats.successes + EXCLUDED.successes,
                    avg_tokens = (prompt_stats.avg_tokens * prompt_stats.executions + %s)
                                 / (prompt_stats.executions + 1)
            """, (prompt_id, 1 if success else 0, tokens, tokens))

            self.conn.commit()
