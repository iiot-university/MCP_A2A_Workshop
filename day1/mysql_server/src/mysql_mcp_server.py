#!/usr/bin/env python3
"""
MySQL MCP Server - Database Query Interface

This MCP server connects to MySQL databases and exposes query tools to Claude Desktop
for exploring and querying industrial data from the Virtual Factory.

Tools:
    - list_schemas: List available database schemas
    - list_tables: List tables within a schema with row counts
    - describe_table: Get column definitions for a table
    - execute_query: Run read-only SELECT queries
"""

import asyncio
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

import mysql.connector
from mysql.connector import Error as MySQLError
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Add project root to path for shared module imports
_project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_project_root))

try:
    from shared.agent_telemetry import AgentTelemetry
    TELEMETRY_AVAILABLE = True
except ImportError as e:
    TELEMETRY_AVAILABLE = False
    AgentTelemetry = None
    # Will log warning after logger is configured

# Configure logging to stderr (stdout reserved for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("mysql-mcp-server")

# Log telemetry availability
if TELEMETRY_AVAILABLE:
    logger.info("AgentTelemetry module loaded successfully")
else:
    logger.warning("AgentTelemetry module not available - agent state will not be published to UNS")

# Load environment variables from .env file (two directories up from src/)
env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(env_path)
logger.info(f"Loading environment from: {env_path}")

# MySQL Configuration
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USERNAME = os.getenv("MYSQL_USERNAME", "")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_SCHEMAS_STR = os.getenv("MYSQL_SCHEMAS", "")

# Parse allowed schemas from comma-separated string
ALLOWED_SCHEMAS = [s.strip() for s in MYSQL_SCHEMAS_STR.split(",") if s.strip()]

# Safety limits
MAX_ROWS = 1000  # Maximum rows returned per query

# Schema descriptions for list_schemas tool
SCHEMA_DESCRIPTIONS = {
    "hivemq_ese_db": "HiveMQ Enterprise Security - User accounts and permissions for the MQTT broker",
    "mes_custom": "Custom MES extensions - Custom attributes, user-defined fields, configurations",
    "mes_lite": "Core MES data - Work orders, production runs, equipment, operators, materials",
    "proveitdb": "ProveIt! demo data - Batch records, quality checks, recipes, process parameters",
}


class MySQLClientWrapper:
    """Wrapper class for MySQL connections with connection pooling."""

    def __init__(self):
        """Initialize MySQL client configuration."""
        self.config = {
            "host": MYSQL_HOST,
            "port": MYSQL_PORT,
            "user": MYSQL_USERNAME,
            "password": MYSQL_PASSWORD,
            "autocommit": True,
            "connection_timeout": 30,
        }
        self._connection = None

    def _get_connection(self):
        """Get a database connection, creating one if needed."""
        try:
            if self._connection is None or not self._connection.is_connected():
                logger.info(f"Connecting to MySQL at {MYSQL_HOST}:{MYSQL_PORT}...")
                self._connection = mysql.connector.connect(**self.config)
                logger.info("Connected to MySQL successfully")
            return self._connection
        except MySQLError as e:
            logger.error(f"Failed to connect to MySQL: {e}")
            raise

    def close(self):
        """Close the database connection."""
        if self._connection and self._connection.is_connected():
            self._connection.close()
            logger.info("Disconnected from MySQL")

    def _validate_schema(self, schema: str) -> bool:
        """Validate that a schema is in the allowed list."""
        return schema in ALLOWED_SCHEMAS

    def _validate_identifier(self, identifier: str) -> bool:
        """Validate that an identifier (schema/table name) is safe."""
        # Only allow alphanumeric characters and underscores
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier))

    def list_schemas(self) -> list[dict[str, str]]:
        """List all allowed schemas with their descriptions."""
        schemas = []
        for schema in ALLOWED_SCHEMAS:
            description = SCHEMA_DESCRIPTIONS.get(schema, "No description available")
            schemas.append({
                "schema": schema,
                "description": description,
            })
        return schemas

    def list_tables(self, schema: str) -> list[dict[str, Any]]:
        """List all tables in a schema with row counts."""
        if not self._validate_schema(schema):
            raise ValueError(f"Schema '{schema}' is not in the allowed list: {ALLOWED_SCHEMAS}")

        if not self._validate_identifier(schema):
            raise ValueError(f"Invalid schema name: {schema}")

        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            # Get tables with row counts from information_schema
            query = """
                SELECT 
                    TABLE_NAME as table_name,
                    TABLE_ROWS as row_count,
                    TABLE_COMMENT as comment
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s
                AND TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """
            cursor.execute(query, (schema,))
            tables = cursor.fetchall()

            # Convert row_count to int (can be None for some table types)
            for table in tables:
                table['row_count'] = int(table['row_count']) if table['row_count'] else 0

            return tables

        finally:
            cursor.close()

    def describe_table(self, schema: str, table: str) -> list[dict[str, Any]]:
        """Get column definitions for a table."""
        if not self._validate_schema(schema):
            raise ValueError(f"Schema '{schema}' is not in the allowed list: {ALLOWED_SCHEMAS}")

        if not self._validate_identifier(schema) or not self._validate_identifier(table):
            raise ValueError(f"Invalid schema or table name: {schema}.{table}")

        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            # Get column information from information_schema
            query = """
                SELECT 
                    COLUMN_NAME as column_name,
                    DATA_TYPE as data_type,
                    COLUMN_TYPE as column_type,
                    IS_NULLABLE as nullable,
                    COLUMN_KEY as key_type,
                    COLUMN_DEFAULT as default_value,
                    EXTRA as extra,
                    COLUMN_COMMENT as comment
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
            """
            cursor.execute(query, (schema, table))
            columns = cursor.fetchall()

            if not columns:
                raise ValueError(f"Table '{schema}.{table}' not found or has no columns")

            return columns

        finally:
            cursor.close()

    def execute_query(self, query: str) -> dict[str, Any]:
        """Execute a read-only SELECT query."""
        # Validate query is SELECT only
        normalized_query = query.strip().upper()
        if not normalized_query.startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")

        # Check for dangerous keywords
        dangerous_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", 
                            "TRUNCATE", "GRANT", "REVOKE", "EXECUTE", "CALL"]
        for keyword in dangerous_keywords:
            if keyword in normalized_query:
                raise ValueError(f"Query contains forbidden keyword: {keyword}")

        # Log the query for audit
        logger.info(f"Executing query: {query[:200]}{'...' if len(query) > 200 else ''}")

        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            cursor.execute(query)
            rows = cursor.fetchmany(MAX_ROWS + 1)  # Fetch one extra to detect truncation

            truncated = len(rows) > MAX_ROWS
            if truncated:
                rows = rows[:MAX_ROWS]

            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            return {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "truncated": truncated,
                "max_rows": MAX_ROWS,
            }

        finally:
            cursor.close()


# Create global MySQL client instance
mysql_client = MySQLClientWrapper()

# Create MCP server instance
server = Server("mysql-mes")

# Telemetry for UNS visibility
if TELEMETRY_AVAILABLE:
    telemetry = AgentTelemetry(
        agent_id="mysql-mes",
        agent_type="mcp",
        name="MySQL MCP Server - MES Database",
        version="1.0.0",
        description="Read-only MySQL access for MES database schemas",
        tools=["list_schemas", "list_tables", "describe_table", "execute_query"],
        capabilities=["mysql"],
    )
else:
    telemetry = None


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="list_schemas",
            description=(
                "List all available database schemas that can be queried. "
                "Use this first to discover what databases are available. "
                "Returns schema names and descriptions of their contents."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="list_tables",
            description=(
                "List all tables within a specific database schema. "
                "Use this to explore what tables exist before querying. "
                "Returns table names with approximate row counts."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "schema": {
                        "type": "string",
                        "description": (
                            "Database schema name (e.g., 'mes_lite', 'proveitdb'). "
                            "Use list_schemas first to see available schemas."
                        ),
                    },
                },
                "required": ["schema"],
            },
        ),
        Tool(
            name="describe_table",
            description=(
                "Get column definitions for a specific table. "
                "Use this to understand table structure before writing queries. "
                "Returns column names, data types, nullability, and key information."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "schema": {
                        "type": "string",
                        "description": "Database schema name (e.g., 'mes_lite')",
                    },
                    "table": {
                        "type": "string",
                        "description": "Table name to describe",
                    },
                },
                "required": ["schema", "table"],
            },
        ),
        Tool(
            name="execute_query",
            description=(
                "Execute a read-only SQL SELECT query against the database. "
                "Use this to retrieve specific data after exploring schemas and tables. "
                "Only SELECT statements are allowed. Results are limited to 1000 rows. "
                "Always specify the schema in the FROM clause (e.g., FROM mes_lite.work_orders)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "SQL SELECT query to execute. Must include schema prefix in table names "
                            "(e.g., 'SELECT * FROM mes_lite.work_orders LIMIT 10'). "
                            "Only SELECT queries are allowed."
                        ),
                    },
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls with telemetry tracking."""
    if telemetry:
        with telemetry.track_tool(name, arguments):
            return await _route_tool(name, arguments)
    else:
        return await _route_tool(name, arguments)


async def _route_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Route tool calls to handlers."""
    if name == "list_schemas":
        return await handle_list_schemas(arguments)
    elif name == "list_tables":
        return await handle_list_tables(arguments)
    elif name == "describe_table":
        return await handle_describe_table(arguments)
    elif name == "execute_query":
        return await handle_execute_query(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def handle_list_schemas(arguments: dict[str, Any]) -> list[TextContent]:
    """List all available database schemas."""
    try:
        schemas = mysql_client.list_schemas()

        if not schemas:
            return [
                TextContent(
                    type="text",
                    text="No schemas configured. Check MYSQL_SCHEMAS in .env file.",
                )
            ]

        # Format the results
        result_lines = [f"Available schemas ({len(schemas)}):\n"]
        for schema_info in schemas:
            result_lines.append(f"  • {schema_info['schema']}")
            result_lines.append(f"    {schema_info['description']}")
            result_lines.append("")

        return [TextContent(type="text", text="\n".join(result_lines))]

    except Exception as e:
        logger.exception("Error in list_schemas")
        return [TextContent(type="text", text=f"Error listing schemas: {e}")]


async def handle_list_tables(arguments: dict[str, Any]) -> list[TextContent]:
    """List tables in a schema."""
    schema = arguments.get("schema")
    if not schema:
        return [TextContent(type="text", text="Error: 'schema' parameter is required")]

    try:
        tables = mysql_client.list_tables(schema)

        if not tables:
            return [
                TextContent(
                    type="text",
                    text=f"No tables found in schema '{schema}'.",
                )
            ]

        # Format the results
        result_lines = [f"Tables in '{schema}' ({len(tables)}):\n"]
        for table in tables:
            name = table['table_name']
            rows = table['row_count']
            comment = table.get('comment', '')
            
            row_str = f"~{rows:,} rows" if rows else "empty"
            if comment:
                result_lines.append(f"  • {name} ({row_str}) - {comment}")
            else:
                result_lines.append(f"  • {name} ({row_str})")

        return [TextContent(type="text", text="\n".join(result_lines))]

    except ValueError as e:
        return [TextContent(type="text", text=f"Validation error: {e}")]
    except MySQLError as e:
        logger.exception("MySQL error in list_tables")
        return [TextContent(type="text", text=f"Database error: {e}")]
    except Exception as e:
        logger.exception("Error in list_tables")
        return [TextContent(type="text", text=f"Error listing tables: {e}")]


async def handle_describe_table(arguments: dict[str, Any]) -> list[TextContent]:
    """Describe a table's columns."""
    schema = arguments.get("schema")
    table = arguments.get("table")

    if not schema:
        return [TextContent(type="text", text="Error: 'schema' parameter is required")]
    if not table:
        return [TextContent(type="text", text="Error: 'table' parameter is required")]

    try:
        columns = mysql_client.describe_table(schema, table)

        # Format the results
        result_lines = [f"Columns in '{schema}.{table}' ({len(columns)}):\n"]
        
        for col in columns:
            name = col['column_name']
            col_type = col['column_type']
            nullable = "NULL" if col['nullable'] == "YES" else "NOT NULL"
            key = col['key_type']
            
            # Build key indicator
            key_str = ""
            if key == "PRI":
                key_str = " [PRIMARY KEY]"
            elif key == "UNI":
                key_str = " [UNIQUE]"
            elif key == "MUL":
                key_str = " [INDEX]"

            result_lines.append(f"  • {name}: {col_type} {nullable}{key_str}")
            
            # Add comment if present
            comment = col.get('comment', '')
            if comment:
                result_lines.append(f"      {comment}")

        return [TextContent(type="text", text="\n".join(result_lines))]

    except ValueError as e:
        return [TextContent(type="text", text=f"Validation error: {e}")]
    except MySQLError as e:
        logger.exception("MySQL error in describe_table")
        return [TextContent(type="text", text=f"Database error: {e}")]
    except Exception as e:
        logger.exception("Error in describe_table")
        return [TextContent(type="text", text=f"Error describing table: {e}")]


async def handle_execute_query(arguments: dict[str, Any]) -> list[TextContent]:
    """Execute a SELECT query."""
    query = arguments.get("query")
    if not query:
        return [TextContent(type="text", text="Error: 'query' parameter is required")]

    try:
        result = mysql_client.execute_query(query)

        columns = result['columns']
        rows = result['rows']
        row_count = result['row_count']
        truncated = result['truncated']

        if row_count == 0:
            return [TextContent(type="text", text="Query returned no results.")]

        # Format results as a table
        result_lines = []

        # Header
        if truncated:
            result_lines.append(f"⚠️ Results truncated to {MAX_ROWS} rows\n")
        result_lines.append(f"Query returned {row_count} row(s):\n")

        # Column headers
        result_lines.append(" | ".join(columns))
        result_lines.append("-" * len(result_lines[-1]))

        # Data rows
        for row in rows:
            row_values = []
            for col in columns:
                value = row.get(col)
                if value is None:
                    row_values.append("NULL")
                else:
                    # Truncate long values for display
                    str_val = str(value)
                    if len(str_val) > 50:
                        str_val = str_val[:47] + "..."
                    row_values.append(str_val)
            result_lines.append(" | ".join(row_values))

        return [TextContent(type="text", text="\n".join(result_lines))]

    except ValueError as e:
        return [TextContent(type="text", text=f"Query validation error: {e}")]
    except MySQLError as e:
        logger.exception("MySQL error in execute_query")
        return [TextContent(type="text", text=f"Database error: {e}")]
    except Exception as e:
        logger.exception("Error in execute_query")
        return [TextContent(type="text", text=f"Error executing query: {e}")]


async def main():
    """Main entry point for the MCP server."""
    logger.info("Starting MySQL MCP Server...")
    logger.info(f"MySQL Host: {MYSQL_HOST}:{MYSQL_PORT}")
    logger.info(f"Allowed schemas: {ALLOWED_SCHEMAS}")

    if not ALLOWED_SCHEMAS:
        logger.warning("No schemas configured! Set MYSQL_SCHEMAS in .env file.")

    # Test MySQL connection for telemetry status
    mysql_connected = False
    try:
        mysql_client._get_connection()
        mysql_connected = True
    except Exception as e:
        logger.warning(f"Initial MySQL connection test failed: {e}")

    # Start telemetry (publishes to UNS)
    if telemetry:
        telemetry.start()
        telemetry.update_status(mysql=mysql_connected)
        logger.info("Telemetry started and publishing to UNS")
    else:
        logger.warning("Telemetry not available - agent state will not be published to UNS")

    try:
        # Run the MCP server with stdio transport
        async with stdio_server() as (read_stream, write_stream):
            logger.info("MCP server running with stdio transport")
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        # Clean up
        if telemetry:
            telemetry.stop()
        mysql_client.close()


if __name__ == "__main__":
    asyncio.run(main())
