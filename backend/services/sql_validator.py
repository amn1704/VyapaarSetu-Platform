import re
from typing import Tuple

class SQLValidator:
    """
    Security layer for LLM-generated SQL queries.
    Prevents injection, data mutation, and unauthorized table access.
    """
    
    ALLOWED_TABLES = {
        "ubid_registry", 
        "source_records", 
        "activity_events", 
        "review_queue", 
        "audit_log"
    }
    
    UNSAFE_KEYWORDS = {
        "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", 
        "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE", "PRAGMA",
        "ATTACH", "DETACH", "VACUUM", "REINDEX", "REPLACE"
    }

    def validate(self, sql: str) -> Tuple[bool, str]:
        """
        Returns (is_valid, reason).
        Performs sequential safety checks on the generated SQL.
        """
        if not sql:
            return False, "Empty SQL query"
            
        sql_upper = sql.strip().upper()
        
        # 1. Must start with SELECT or a read-only CTE.
        if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
            return False, "Query must start with SELECT or WITH"
            
        # 2. Must contain FROM
        if "FROM" not in sql_upper:
            return False, "Query must contain FROM clause"
            
        # 3. Check for unsafe keywords
        for word in self.UNSAFE_KEYWORDS:
            if re.search(rf"\b{word}\b", sql_upper):
                return False, f"Unsafe keyword detected: {word}"
        
        if "--" in sql:
            return False, "SQL comments (--) are not allowed"
            
        # 4. Allowed tables only
        # Simple extraction of table names after FROM or JOIN
        # Note: This is a basic check. Complex subqueries might need a real parser, 
        # but for this platform's scope, regex is usually sufficient.
        tables_found = re.findall(r"FROM\s+([A-Z_][A-Z0-9_]*)|JOIN\s+([A-Z_][A-Z0-9_]*)", sql_upper)
        for group in tables_found:
            for table in group:
                if table and table.lower() not in self.ALLOWED_TABLES:
                    return False, f"Unauthorized table access: {table}"
                    
        # 5. Semicolon check
        if ";" in sql.strip()[:-1]: # Check if semicolon exists anywhere but the very end
            return False, "Semicolons are only allowed at the end of the query"
            
        # 6. Length check
        if len(sql) > 2000:
            return False, "Query exceeds maximum length of 2000 characters"
            
        return True, "OK"

    def ensure_limit(self, sql: str, default_limit: int = 100) -> str:
        """Adds a conservative LIMIT to non-aggregate queries that forgot one."""
        cleaned = self.sanitise(sql)
        if re.search(r"\bLIMIT\s+\d+\b", cleaned, flags=re.IGNORECASE):
            return cleaned
        if re.search(r"\bCOUNT\s*\(|\bGROUP\s+BY\b", cleaned, flags=re.IGNORECASE):
            return cleaned
        return f"{cleaned} LIMIT {default_limit}"

    def sanitise(self, sql: str) -> str:
        """
        Cleans the SQL string for safe execution.
        """
        # Strip whitespace
        cleaned = sql.strip()
        
        # Remove trailing semicolon
        cleaned = cleaned.rstrip(";")
        
        # Normalise multiple spaces
        cleaned = re.sub(r"\s+", " ", cleaned)
        
        return cleaned.strip()

# Global singleton
sql_validator = SQLValidator()
