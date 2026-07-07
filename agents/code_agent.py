import json
from agents.base_agent import BaseAgent
from services.code_sandbox.executor import execute_code


SYSTEM_PROMPT = """You are a code generation agent for theTwoCubes Learning.
Generate real, runnable, beginner-friendly code examples.

Rules:
- Code must be complete and runnable as-is.
- Include only stdlib (no external packages unless the topic requires it).
- Add SHORT inline comments on key lines only (not every line).
- Keep examples under 30 lines where possible.
- Output strictly valid JSON. No markdown."""

USER_TEMPLATE = """
Lesson: {lesson_title}
Language: {language}
Concept to demonstrate: {concept}
Complexity: {complexity}

Generate a code example as JSON:
{{
  "id": "{code_id}",
  "language": "{language}",
  "source_code": "the complete code as a string",
  "expected_output": "what stdout should show",
  "annotations": [
    {{"line": 1, "note": "explanation of this line"}}
  ]
}}
"""


class CodeAgent(BaseAgent):
    MAX_RETRIES = 3

    def run(self, state: dict) -> dict:
        print("[CodeAgent] Generating and validating code examples...")

        script = state.get("script", {})
        segments = script.get("segments", [])
        lesson_title = state["lesson_title"]
        lesson_plan = state.get("lesson_plan", {})

        # determine primary language from topic tags
        tags = state.get("topic_tags", [])
        language = self._detect_language(tags)

        # find all code_demo segments
        code_refs = {}
        for seg in segments:
            if seg.get("type") == "code_demo" and seg.get("code_ref"):
                code_refs[seg["code_ref"]] = seg.get("text", "")

        if not code_refs:
            # generate at least one example from lesson plan
            code_refs["code_001"] = f"Basic example of {lesson_title}"

        code_examples = []

        for code_id, concept in code_refs.items():
            print(f"  Generating {code_id}: {concept[:60]}")
            example = self._generate_and_validate(
                code_id=code_id,
                lesson_title=lesson_title,
                language=language,
                concept=concept,
            )
            code_examples.append(example)

        state["code_examples"] = code_examples
        validated = sum(1 for e in code_examples if e["is_validated"])
        print(f"  {validated}/{len(code_examples)} examples validated.")
        return state

    def _detect_language(self, tags: list[str]) -> str:
        lang_map = {
            "c": "c", "c++": "cpp", "cpp": "cpp",
            "python": "python", "java": "java",
            "javascript": "javascript", "bash": "bash",
        }
        for tag in tags:
            if tag.lower() in lang_map:
                return lang_map[tag.lower()]
        return "python"

    def _generate_and_validate(
        self, code_id: str, lesson_title: str, language: str, concept: str
    ) -> dict:
        complexity = "beginner"

        for attempt in range(self.MAX_RETRIES):
            user_msg = USER_TEMPLATE.format(
                lesson_title=lesson_title,
                language=language,
                concept=concept[:300],
                complexity=complexity,
                code_id=code_id,
            )

            try:
                result = self.llm.complete_json(SYSTEM_PROMPT, user_msg)
            except Exception as e:
                print(f"  LLM error on attempt {attempt+1}: {e}")
                continue

            source_code = result.get("source_code", "")
            if not source_code:
                continue

            # execute to verify
            exec_result = execute_code(language, source_code)
            result["actual_output"] = exec_result.stdout
            result["is_validated"] = exec_result.success
            result["id"] = code_id

            if exec_result.success:
                print(f"  Validated: {code_id}")
                return result
            else:
                print(f"  Attempt {attempt+1} failed: {exec_result.stderr[:100]}")
                concept = f"Fix this code (error: {exec_result.stderr[:200]})\n\nPrevious attempt:\n{source_code}"

        # all attempts failed: return unvalidated
        result["is_validated"] = False
        return result
