"""A trivial wrapper of openai.Completion.create (for now).

Handles initialization of a default request config with optional override by
config file and/or arbitrary kwargs to generate_query.py.
"""

import os
import typing as t

import openai
import yaml
from pglast.parser import parse_sql, ParseError

from pg_text_query.errors import EnvVarError, QueryGenError


# Initialize default OpenAI completion config w/ optional user config file path
# from env var PGTQ_OPENAI_CONFIG
PGTQ_OPENAI_CONFIG = os.getenv(
    "PGTQ_OPENAI_CONFIG",
    os.path.join(os.path.dirname(__file__), "default_openai_config.yaml"),
)
with open(PGTQ_OPENAI_CONFIG, "rb") as f:
    DEFAULT_COMPLETION_CONFIG = yaml.safe_load(f)["completion_create"]


def generate_query(prompt: str, validate_sql: bool = False, **kwargs: t.Any) -> str:
    """Generate a raw Postgres query string from a prompt.

    If validate_sql is True, raises QueryGenError when OpenAI returns a 
    completion that fails validation using the Postgres parser. This ensures a
    non-empty and syntactically valid query but NOT necessarily a correct one.
    
    Completion.create is called with default config from PGTQ_OPENAI_CONFIG
    with any provided kwargs serving as parameter overrides. 

    TODO: Later, add error handling.
    """
    # 
    if getattr(openai, "api_key") is None:
        # Initialize OpenAI API Key
        openai.api_key = os.getenv("OPENAI_API_KEY")
        if openai.api_key is None:
            raise EnvVarError("OPENAI_API_KEY not found in environment")


    response = openai.Completion.create(
        prompt=prompt,
        **{**DEFAULT_COMPLETION_CONFIG, **kwargs},
    )

    generated_query = response["choices"][0]["text"]

    if validate_sql:
        raise_if_invalid_query(generated_query)
    
    return generated_query


def raise_if_invalid_query(query: str) -> None:
    """Raised QueryGenError if query is invalid.
    
    Note: in this context, "invalid" includes a query that is empty or only a
    SQL comment, which is different from the typical sense of "valid Postgres".
    """
    try:
        parse_result = parse_sql(query)
    except ParseError as e:
        raise QueryGenError("Generated query is not valid PostgreSQL") from e
    else:
        # Check for any empty result (occurs if completion is a comment)
        if not parse_result:
            raise QueryGenError("Generated query is empty or a SQL comment")