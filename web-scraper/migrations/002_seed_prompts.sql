-- Seed Prompts

INSERT INTO scr_llm_prompts (use_case, language, prompt_template, system_prompt, model, notes) VALUES

('opening_hours', 'cs',
'Převeď následující text otevírací doby do JSON formátu.
Výstup musí být POUZE validní JSON, bez jakéhokoliv jiného textu.

Formát výstupu:
{"days": [{"day": "monday", "open": "09:00", "close": "17:00"}]}

Pokud je zavřeno, použij: {"day": "monday", "closed": true}

Text k parsování:
{text}',
'Jsi precizní parser otevírací doby. Odpovídáš pouze validním JSON.',
'claude-3-5-haiku-20241022',
'Fallback když regex selže'),

('opening_hours', 'de',
'Konvertiere die folgenden Öffnungszeiten in JSON-Format.
Ausgabe NUR gültiges JSON.

Format: {"days": [{"day": "monday", "open": "09:00", "close": "17:00"}]}

Text: {text}',
'Du bist ein Parser. Nur JSON.',
'claude-3-5-haiku-20241022',
NULL),

('opening_hours', 'en',
'Convert opening hours to JSON.
Output ONLY valid JSON.

Format: {"days": [{"day": "monday", "open": "09:00", "close": "17:00"}]}

Text: {text}',
'You are a parser. JSON only.',
'llama3.2:3b',
'Local model fallback');
