"""Tests for the skill implementations (no LLM required)."""
import pytest

from app.skills.calculator import CalculatorInput, CalculatorSkill
from app.skills.system_time import SystemTimeInput, SystemTimeSkill


class TestCalculatorSkill:
    def setup_method(self):
        self.skill = CalculatorSkill()

    def test_basic_addition(self):
        result = self.skill.execute(CalculatorInput(expression="2 + 2"))
        assert "= 4" in result

    def test_multiplication(self):
        result = self.skill.execute(CalculatorInput(expression="6 * 7"))
        assert "= 42" in result

    def test_float_division(self):
        result = self.skill.execute(CalculatorInput(expression="10 / 3"))
        assert "10 / 3 =" in result

    def test_integer_result_no_decimal(self):
        result = self.skill.execute(CalculatorInput(expression="sqrt(144)"))
        assert "= 12" in result

    def test_power(self):
        result = self.skill.execute(CalculatorInput(expression="2 ** 10"))
        assert "= 1024" in result

    def test_parentheses(self):
        result = self.skill.execute(CalculatorInput(expression="(3 + 5) * 2"))
        assert "= 16" in result

    def test_constants_pi(self):
        result = self.skill.execute(CalculatorInput(expression="pi"))
        assert "3.14" in result

    def test_division_by_zero(self):
        result = self.skill.execute(CalculatorInput(expression="1 / 0"))
        assert "zero" in result.lower()

    def test_invalid_expression(self):
        result = self.skill.execute(CalculatorInput(expression="import os"))
        assert "Could not evaluate" in result or "Unsupported" in result

    def test_string_injection_blocked(self):
        """Ensure string literals can't sneak through."""
        result = self.skill.execute(CalculatorInput(expression="'hello'"))
        assert "Could not evaluate" in result or "Unsupported" in result

    def test_modulo(self):
        result = self.skill.execute(CalculatorInput(expression="17 % 5"))
        assert "= 2" in result

    def test_schema_generated(self):
        schema = CalculatorSkill.get_ollama_tool_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "calculate"
        assert "parameters" in schema["function"]


class TestSystemTimeSkill:
    def test_returns_datetime_string(self):
        skill = SystemTimeSkill()
        result = skill.execute(SystemTimeInput())
        assert "Current date and time:" in result
        # Should contain AM or PM
        assert "AM" in result or "PM" in result

    def test_schema_generated(self):
        schema = SystemTimeSkill.get_ollama_tool_schema()
        assert schema["function"]["name"] == "get_system_time"


class TestSkillSchemas:
    """Verify all discovered skills expose valid Ollama schemas."""

    def test_all_skill_schemas_valid(self):
        from app.core.tool_registry import ToolRegistry
        registry = ToolRegistry()
        registry.discover_skills()

        assert len(registry.tools) > 0, "No skills were discovered."

        for name, cls in registry.tools.items():
            schema = cls.get_ollama_tool_schema()
            assert schema["type"] == "function", f"{name}: missing 'type'"
            assert "name" in schema["function"], f"{name}: missing function.name"
            assert "description" in schema["function"], f"{name}: missing function.description"
            assert "parameters" in schema["function"], f"{name}: missing function.parameters"

    def test_filtered_schemas(self):
        from app.core.tool_registry import ToolRegistry
        registry = ToolRegistry()
        registry.discover_skills()

        # Filter to just 'calculate'
        schemas = registry.get_filtered_schemas(["calculate"])
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "calculate"

    def test_empty_filter_returns_all(self):
        from app.core.tool_registry import ToolRegistry
        registry = ToolRegistry()
        registry.discover_skills()

        all_schemas = registry.get_all_tool_schemas()
        filtered = registry.get_filtered_schemas([])
        assert len(filtered) == len(all_schemas)
