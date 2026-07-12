from agents.base_agent import BaseAgent
from config.settings import settings


SYSTEM_PROMPT = """
You are an expert programming instructor and code generation agent for "theTwoCubes Learning".
Your task is to generate high-quality educational code examples that clearly demonstrate a single programming concept.

The generated code will later be used for:
- YouTube lectures
- Slide generation
- Voice narration
- Line-by-line explanation
- Interactive visualizations

Therefore, prioritize clarity and teaching quality over clever or optimized code.

========================
OBJECTIVE
========================

Generate ONE complete, runnable code example that teaches the requested concept.
The example should help a beginner understand WHY the concept exists, HOW it works, and WHAT it produces.

========================
CODE REQUIREMENTS
========================

The code must be:
- Complete and runnable without modification.
- Self-contained.
- Readable.
- Beginner-friendly.
- Properly formatted.
- Idiomatic for the requested language.

Unless the lesson specifically requires otherwise:
- Use only the language's standard library.
- Do not require installation of external packages.
- Avoid unnecessary abstractions.
- Avoid advanced syntax when a simpler alternative exists.

========================
TEACHING PRINCIPLES
========================

The example should:
- Focus on ONE primary concept.
- Avoid introducing unrelated ideas.
- Use meaningful variable names.
- Keep logic straightforward.
- Demonstrate the requested concept clearly.
- Produce deterministic output whenever possible.

If input is required, hardcode example values instead of asking the user for input unless interactive input is itself the concept being taught.

========================
COMMENTS
========================

Include only SHORT inline comments.
Comment only important lines.
Do NOT comment every line.
Avoid long explanations inside the source code.

========================
SIZE
========================

Prefer examples under 30 lines.
Slightly exceed this only if required for correctness or clarity.

========================
EXPECTED OUTPUT
========================

expected_output must exactly match the program's stdout.
Do not include prompts unless they are intentionally printed.

========================
ANNOTATIONS
========================

Provide annotations only for important lines.
Each annotation should briefly explain:
- what the line does
- why it exists
- or what concept it demonstrates

Do not annotate every line.
Keep notes concise.

========================
OUTPUT REQUIREMENTS
========================

Return STRICTLY valid JSON.
Do NOT return:
- Markdown fences (e.g. ```json)
- Markdown formatting symbols (like **, *, `) inside the code comments. Code is syntax-highlighted directly.
- Explanations outside JSON
- Notes or Commentary
- Extra text

Return ONLY the JSON object.
"""

USER_TEMPLATE = """
Lesson: {lesson_title}
Language: {language}
Concept to demonstrate: {concept}
Complexity: {complexity}

NARRATION SCRIPT:
"{narration}"

CRITICAL SYNCHRONIZATION REQUIREMENT:
You MUST generate code that exactly matches the above narration script. If the script mentions specific variable names, function names, error messages, or logical flows, you MUST use those exact names and flows in your code. Do not invent contradictory variables.

Generate a code example as JSON:

Generate a code example as JSON:

{{
  "id": "{code_id}",
  "language": "{language}",
  "source_code": "the complete code as a string",
  "expected_output": "what stdout should show",
  "annotations": [
    {{
      "line": 1,
      "note": "explanation of this line"
    }}
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

        # determine primary language from topic tags
        tags = state.get("topic_tags", [])
        language = self._detect_language(tags)

        # Extract code requirements directly from the lesson plan
        code_refs = {}
        lesson_plan = state.get("lesson_plan", {})
        script = state.get("script", {})
        segments = script.get("segments", [])
        
        for sec in lesson_plan.get("sections", []):
            if sec.get("needs_code") and sec.get("id"):
                code_id = f"code_{sec['id']}"
                concept = sec.get("title", "") + ": " + " ".join(sec.get("key_points", []))
                
                narrations = [s.get("text", "") for s in segments if s.get("code_ref") == code_id]
                narration = " ".join(narrations)
                
                code_refs[code_id] = {"concept": concept, "narration": narration}

        if not code_refs:
            # generate at least one example from lesson plan
            code_refs["code_001"] = {"concept": f"Basic example of {lesson_title}", "narration": ""}

        code_examples = []

        for code_id, data in code_refs.items():
            concept = data["concept"]
            narration = data["narration"]
            print(f"  Generating {code_id}: {concept[:60]}")
            example = self._generate_and_validate(
                code_id=code_id,
                lesson_title=lesson_title,
                language=language,
                concept=concept,
                narration=narration,
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
        self, code_id: str, lesson_title: str, language: str, concept: str, narration: str
    ) -> dict:
        complexity = "beginner"

        for attempt in range(self.MAX_RETRIES):
            user_msg = USER_TEMPLATE.format(
                lesson_title=lesson_title,
                language=language,
                concept=concept[:300],
                narration=narration,
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

            result["id"] = code_id

            if settings.ENABLE_CODE_EXECUTION:
                # Opt-in: actually run the generated code in a sandboxed subprocess and record REAL output. 
                exec_result = self._execute(language, source_code)
                if exec_result is None:
                    # language unsupported / toolchain missing - can't validate, but don't fabricate output. Ship it flagged unvalidated.
                    result["actual_output"] = ""
                    result["is_validated"] = False
                    print(f"  Generated (unvalidated - no runner for {language}): {code_id}")
                    return result
                if not exec_result.success:
                    print(f"  Attempt {attempt+1}: code failed to run, regenerating...\n"
                          f"    {exec_result.stderr[:160]}")
                    continue
                result["actual_output"] = exec_result.stdout.strip()
                result["is_validated"] = True
                print(f"  Validated by execution: {code_id}")
                return result

            result["actual_output"] = ""
            result["is_validated"] = False
            print(f"  Generated (execution disabled - unvalidated): {code_id}")
            return result

        # all attempts failed
        return {"id": code_id, "is_validated": False}

    def _execute(self, language: str, source_code: str):
        """Run code via the sandbox executor. Returns an ExecutionResult, or
        None if the language/toolchain isn't available."""
        try:
            from services.code_sandbox.executor import execute_code, LANGUAGE_CONFIGS
            if language.lower() not in LANGUAGE_CONFIGS:
                return None
            res = execute_code(language, source_code)
            # A missing compiler/runtime surfaces as exit 127 - treat as "no runner", not as a code defect worth regenerating over.
            if res.exit_code == 127:
                return None
            return res
        except Exception as e:
            print(f"  Sandbox unavailable ({e}); shipping unvalidated.")
            return None
