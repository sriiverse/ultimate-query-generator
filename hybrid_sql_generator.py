#!/usr/bin/env python3
"""
Hybrid SQL Generator - Best of Both Worlds
Combines AI-powered natural language understanding with rule-based validation and optimization
"""

import re
import os
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from sql_optimizer_engine import SQLOptimizerEngine, OptimizationLevel

class GenerationStatus(Enum):
    SUCCESS = "success"
    VALIDATION_FAILED = "validation_failed"
    AI_UNAVAILABLE = "ai_unavailable"
    FALLBACK_USED = "fallback_used"

@dataclass
class HybridGenerationResult:
    """Result from the hybrid SQL generation process"""
    query: str
    status: GenerationStatus
    validation_errors: List[str]
    optimization_suggestions: List[str]
    performance_score: int
    generation_method: str
    confidence_score: float

class QueryValidator:
    """Robust validation layer for AI-generated SQL queries"""
    
    def __init__(self, schema_info: Dict = None):
        self.schema_info = schema_info or {}
    
    def validate_query(self, query: str) -> Tuple[bool, List[str]]:
        """Comprehensive validation of generated SQL query"""
        errors = []
        
        # 1. Syntax validation
        syntax_errors = self._validate_syntax(query)
        errors.extend(syntax_errors)
        
        # 2. Schema compliance
        schema_errors = self._validate_schema_compliance(query)
        errors.extend(schema_errors)
        
        # 3. Security checks
        security_errors = self._validate_security(query)
        errors.extend(security_errors)
        
        # 4. Performance red flags
        performance_errors = self._validate_performance_basics(query)
        errors.extend(performance_errors)
        
        return len(errors) == 0, errors
    
    def _validate_syntax(self, query: str) -> List[str]:
        """Basic syntax validation"""
        errors = []
        query_lower = query.lower().strip()
        
        # Check for basic SQL structure
        if not any(keyword in query_lower for keyword in ['select', 'insert', 'update', 'delete']):
            errors.append("Query does not contain a valid SQL command")
        
        # Check for balanced parentheses
        if query.count('(') != query.count(')'):
            errors.append("Unbalanced parentheses in query")
        
        # Check for basic SELECT structure
        if 'select' in query_lower:
            if 'from' not in query_lower:
                errors.append("SELECT query missing FROM clause")
        
        return errors
    
    def _validate_schema_compliance(self, query: str) -> List[str]:
        """Validate query against known schema"""
        errors = []
        
        if not self.schema_info or 'tables' not in self.schema_info:
            return errors  # Skip if no schema info available
        
        query_lower = query.lower()
        available_tables = set(self.schema_info['tables'].keys())
        
        # Extract table references (basic pattern matching)
        table_patterns = [
            r'from\s+(\w+)',
            r'join\s+(\w+)',
            r'update\s+(\w+)',
            r'insert\s+into\s+(\w+)'
        ]
        
        referenced_tables = set()
        for pattern in table_patterns:
            matches = re.findall(pattern, query_lower)
            referenced_tables.update(matches)
        
        # Check if referenced tables exist
        unknown_tables = referenced_tables - available_tables
        if unknown_tables:
            errors.append(f"Unknown tables referenced: {', '.join(unknown_tables)}")
        
        return errors
    
    def _validate_security(self, query: str) -> List[str]:
        """Check for potentially dangerous SQL patterns"""
        errors = []
        query_lower = query.lower()
        
        # Dangerous operations
        dangerous_keywords = ['drop', 'truncate', 'delete', 'alter', 'create', 'grant', 'revoke']
        found_dangerous = [kw for kw in dangerous_keywords if kw in query_lower]
        
        if found_dangerous:
            errors.append(f"Potentially dangerous operations detected: {', '.join(found_dangerous)}")
        
        # SQL injection patterns
        injection_patterns = [
            r';\s*drop\s+table',
            r'union\s+select.*from',
            r'--\s*$',
            r'/\*.*\*/'
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, query_lower):
                errors.append("Potential SQL injection pattern detected")
                break
        
        return errors
    
    def _validate_performance_basics(self, query: str) -> List[str]:
        """Check for basic performance issues"""
        errors = []
        query_lower = query.lower()
        
        # Check for SELECT * on potentially large tables
        if 'select *' in query_lower and 'limit' not in query_lower:
            errors.append("SELECT * without LIMIT may impact performance")
        
        # Check for missing WHERE clause on SELECT
        if 'select' in query_lower and 'where' not in query_lower and 'limit' not in query_lower:
            errors.append("SELECT without WHERE clause may return too many rows")
        
        return errors

class HybridSQLGenerator:
    """Hybrid SQL Generator combining AI and Rule-based approaches"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.gemini_available = GEMINI_AVAILABLE and api_key
        
        # Initialize components
        self.optimizer = SQLOptimizerEngine()
        self.validator = QueryValidator()
        
        # Initialize Gemini if available
        if self.gemini_available:
            try:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                print("✅ Gemini API initialized successfully")
            except Exception as e:
                print(f"❌ Failed to initialize Gemini: {e}")
                self.gemini_available = False
        
        # Fallback patterns (simplified version of ultimate patterns)
        self.fallback_patterns = self._load_fallback_patterns()
    
    def set_schema(self, schema_ddl: str):
        """Set database schema for all components"""
        schema_info = self._parse_schema(schema_ddl)
        self.optimizer.set_schema(schema_ddl)
        self.validator = QueryValidator(schema_info)
        self.schema_ddl = schema_ddl
    
    def generate_query(self, description: str) -> HybridGenerationResult:
        """Generate SQL query using hybrid approach"""
        
        # Step 1: Try AI generation first
        if self.gemini_available:
            try:
                ai_query = self._generate_with_ai(description)
                if ai_query:
                    # Validate AI-generated query
                    is_valid, validation_errors = self.validator.validate_query(ai_query)
                    
                    if is_valid:
                        # Apply optimization
                        optimized_query = self.optimizer.generate_optimized_query(ai_query)
                        analysis = self.optimizer.analyze_query(optimized_query)
                        
                        return HybridGenerationResult(
                            query=optimized_query,
                            status=GenerationStatus.SUCCESS,
                            validation_errors=[],
                            optimization_suggestions=[s.suggestion for s in analysis.suggestions],
                            performance_score=analysis.performance_score,
                            generation_method="AI + Rule-based Optimization",
                            confidence_score=0.95
                        )
                    else:
                        # AI query failed validation, try fallback
                        return self._generate_with_fallback(description, validation_errors)
            except Exception as e:
                print(f"AI generation failed: {e}")
                return self._generate_with_fallback(description, [f"AI error: {str(e)}"])
        
        # Step 2: Use rule-based fallback
        return self._generate_with_fallback(description, ["AI not available"])
    
    def _generate_with_ai(self, description: str) -> Optional[str]:
        """Generate SQL using Gemini API"""
        
        # Create comprehensive prompt
        prompt = self._create_ai_prompt(description)
        
        try:
            response = self.model.generate_content(prompt)
            
            if response.text:
                # Extract SQL from response (handle markdown formatting)
                sql_query = self._extract_sql_from_response(response.text)
                return sql_query
        except Exception as e:
            print(f"Gemini API error: {e}")
            return None
        
        return None
    
    def _create_ai_prompt(self, description: str) -> str:
        """Create a comprehensive prompt for AI generation"""
        
        base_prompt = f"""
You are an expert SQL developer. Generate a syntactically correct SQL query based on the user's request.

Database Schema:
{getattr(self, 'schema_ddl', 'No schema provided')}

User Request: {description}

Requirements:
1. Generate only valid SQL syntax
2. Use proper table and column names from the schema
3. Include appropriate WHERE clauses for performance
4. Use proper JOINs when multiple tables are needed
5. Include LIMIT clause if requesting "top" results
6. Use appropriate aggregate functions when needed

Return ONLY the SQL query, no explanations or markdown formatting.
"""
        return base_prompt
    
    def _extract_sql_from_response(self, response_text: str) -> str:
        """Extract SQL query from AI response"""
        # Remove markdown formatting
        cleaned = re.sub(r'```sql\s*', '', response_text)
        cleaned = re.sub(r'```', '', cleaned)
        
        # Remove extra whitespace and comments
        cleaned = re.sub(r'--.*$', '', cleaned, flags=re.MULTILINE)
        cleaned = cleaned.strip()
        
        return cleaned
    
    def _generate_with_fallback(self, description: str, errors: List[str]) -> HybridGenerationResult:
        """Generate using rule-based fallback system"""
        
        # Try pattern matching
        for pattern_info in self.fallback_patterns:
            match = re.search(pattern_info['pattern'], description, re.IGNORECASE)
            if match:
                query = self._apply_pattern_template(pattern_info, match, description)
                
                # Optimize with rule-based system
                optimized_query = self.optimizer.generate_optimized_query(query)
                analysis = self.optimizer.analyze_query(optimized_query)
                
                return HybridGenerationResult(
                    query=optimized_query,
                    status=GenerationStatus.FALLBACK_USED,
                    validation_errors=errors,
                    optimization_suggestions=[s.suggestion for s in analysis.suggestions],
                    performance_score=analysis.performance_score,
                    generation_method="Rule-based Pattern Matching",
                    confidence_score=0.75
                )
        
        # Generic fallback
        generic_query = self._create_generic_query(description)
        return HybridGenerationResult(
            query=generic_query,
            status=GenerationStatus.FALLBACK_USED,
            validation_errors=errors,
            optimization_suggestions=["Consider refining your query description"],
            performance_score=50,
            generation_method="Generic Fallback",
            confidence_score=0.3
        )
    
    def _load_fallback_patterns(self) -> List[Dict]:
        """Load simplified patterns for fallback generation"""
        return [
            {
                'id': 'top_records',
                'pattern': r'(?:show|get|find).*?top\s+(\d+).*?(\w+)',
                'template': 'SELECT * FROM {table} ORDER BY {column} DESC LIMIT {limit}'
            },
            {
                'id': 'count_records',
                'pattern': r'(?:count|how many).*?(\w+)',
                'template': 'SELECT COUNT(*) FROM {table}'
            },
            {
                'id': 'filter_by_value',
                'pattern': r'(?:show|find).*?(\w+).*?where.*?(\w+).*?=.*?[\'"]?(\w+)[\'"]?',
                'template': 'SELECT * FROM {table} WHERE {column} = \'{value}\''
            }
        ]
    
    def _apply_pattern_template(self, pattern_info: Dict, match, description: str) -> str:
        """Apply pattern template with extracted parameters"""
        template = pattern_info['template']
        groups = match.groups()
        
        # Basic parameter extraction (can be enhanced)
        replacements = {}
        if groups:
            replacements['limit'] = groups[0] if groups and groups[0].isdigit() else '10'
            replacements['table'] = groups[1] if len(groups) > 1 else 'users'
            replacements['column'] = groups[2] if len(groups) > 2 else 'id'
            replacements['value'] = groups[2] if len(groups) > 2 else 'unknown'
        
        # Apply replacements
        for key, value in replacements.items():
            template = template.replace(f'{{{key}}}', value)
        
        return template
    
    def _create_generic_query(self, description: str) -> str:
        """Create a basic generic query when all else fails"""
        return "SELECT * FROM users LIMIT 10; -- Generic query: please refine your request"
    
    def _parse_schema(self, schema_ddl: str) -> Dict:
        """Parse schema DDL (reused from optimizer)"""
        schema_info = {'tables': {}, 'indexes': []}
        
        # Simple regex-based parsing for CREATE TABLE statements
        table_pattern = r'CREATE TABLE\s+(\w+)\s*\((.*?)\)'
        
        for match in re.finditer(table_pattern, schema_ddl, re.DOTALL | re.IGNORECASE):
            table_name = match.group(1).lower()
            columns_str = match.group(2)
            
            columns = []
            # Extract column definitions
            column_lines = [line.strip() for line in columns_str.split(',')]
            for line in column_lines:
                if line:
                    parts = line.split()
                    if parts:
                        column_name = parts[0].lower()
                        column_type = parts[1] if len(parts) > 1 else 'unknown'
                        is_primary = 'primary' in line.lower() and 'key' in line.lower()
                        columns.append({
                            'name': column_name,
                            'type': column_type,
                            'is_primary': is_primary
                        })
            
            schema_info['tables'][table_name] = {'columns': columns}
        
        return schema_info

# Usage example and testing
if __name__ == "__main__":
    # Test the hybrid system
    api_key = os.getenv('GEMINI_API_KEY')  # Set this in your environment
    
    generator = HybridSQLGenerator(api_key=api_key)
    
    # Set sample schema
    sample_schema = """
    CREATE TABLE users (
        user_id INT PRIMARY KEY,
        username VARCHAR(50),
        email VARCHAR(100),
        status VARCHAR(20),
        created_date DATE
    );
    
    CREATE TABLE orders (
        order_id INT PRIMARY KEY,
        user_id INT,
        amount DECIMAL(10,2),
        order_date DATE,
        status VARCHAR(20)
    );
    
    CREATE TABLE products (
        product_id INT PRIMARY KEY,
        name VARCHAR(100),
        price DECIMAL(10,2),
        category VARCHAR(50)
    );
    """
    
    generator.set_schema(sample_schema)
    
    # Test queries
    test_queries = [
        "Show me the top 5 customers who spent the most money",
        "Find users from New York who ordered more than $1000",
        "Count how many orders each user made"
    ]
    
    print("🧪 Testing Hybrid SQL Generator")
    print("=" * 50)
    
    for i, query_desc in enumerate(test_queries, 1):
        print(f"\n{i}. {query_desc}")
        result = generator.generate_query(query_desc)
        
        print(f"Status: {result.status.value}")
        print(f"Method: {result.generation_method}")
        print(f"Confidence: {result.confidence_score:.2f}")
        print(f"Performance Score: {result.performance_score}/100")
        print(f"Query:\n{result.query}")
        
        if result.optimization_suggestions:
            print(f"Optimizations: {len(result.optimization_suggestions)} suggestions available")