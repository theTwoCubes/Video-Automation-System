"""
QuizAgent

Generates 3-5 multiple-choice quiz questions per lesson from the script content.
Runs after QAAgent. Questions are saved to output/<lesson>/quiz.json and
stored in state["quiz_questions"].
"""
import json
from pathlib import Path
from agents.base_agent import BaseAgent


SYSTEM_PROMPT = """
You are an educational assessment designer for "theTwoCubes Learning".
Generate multiple-choice quiz questions from a technical lesson script.

RULES:
- Questions must test SPECIFIC facts from the script (numbers, syntax, behavior).
- Never ask "What is the main topic of this lesson?" or similarly vague questions.
- Each question has exactly 4 options labeled A, B, C, D.
- Exactly one option is correct.
- The explanation must reference a concrete fact from the script.
- Difficulty: 60% recall, 40% application.

Output strictly valid JSON. No markdown."""

USER_TEMPLATE = """
Lesson: {lesson_title}

Script segments (source of truth - only ask about facts stated here):
{script_text}

Generate {n_questions} quiz questions as JSON:
{{
  "lesson_id": "{lesson_id}",
  "questions": [
    {{
      "id": "q001",
      "question": "What does sizeof(int) return on a 64-bit system?",
      "options": {{
        "A": "2",
        "B": "4",
        "C": "8",
        "D": "16"
      }},
      "correct": "B",
      "explanation": "int is always 4 bytes on both 32-bit and 64-bit systems per the C++ standard."
    }},
    {{
      "id": "q002",
      "question": "What is the time complexity of list.insert(0, x) in Python?",
      "options": {{
        "A": "O(1)",
        "B": "O(log n)",
        "C": "O(n)",
        "D": "O(n log n)"
      }},
      "correct": "C",
      "explanation": "Inserting at index 0 requires shifting all existing elements one position to the right, making it O(n)."
    }},
    {{
      "id": "q003",
      "question": "In Java, what does the == operator compare when used with two String variables?",
      "options": {{
        "A": "The content of the strings character by character",
        "B": "The length of both strings",
        "C": "The memory address (reference) of the objects",
        "D": "The hash code of the strings"
      }},
      "correct": "C",
      "explanation": "== compares object references in Java, not content. Use .equals() to compare string content."
    }}
  ]
}}
"""


class QuizAgent(BaseAgent):
    def run(self, state: dict) -> dict:
        print("[QuizAgent] Generating quiz questions...")

        script = state.get("script", {})
        segments = script.get("segments", [])

        if not segments:
            print("  No script segments - skipping quiz generation.")
            state["quiz_questions"] = []
            return state

        lesson_id    = state["lesson_id"]
        lesson_title = state["lesson_title"]
        output_dir   = state["output_dir"]

        # build a condensed text from narration segments
        narration_texts = [
            s.get("text", "") for s in segments
            if s.get("type") in ("narration", "code_demo") and s.get("text")
        ]
        script_text = "\n".join(narration_texts)[:4000]

        # aim for 3-5 questions based on content length
        n_questions = min(5, max(3, len(narration_texts) // 2))

        user_msg = USER_TEMPLATE.format(
            lesson_id=lesson_id,
            lesson_title=lesson_title,
            script_text=script_text,
            n_questions=n_questions,
        )

        try:
            # Mechanical extraction from provided text - no reasoning needed.
            result = self.llm.complete_json(SYSTEM_PROMPT, user_msg, thinking_budget=0)
            questions = result.get("questions", [])
        except Exception as e:
            print(f"  Quiz LLM error: {e}")
            questions = []

        # save to disk
        if questions:
            quiz_path = Path(output_dir) / "quiz.json"
            quiz_path.write_text(
                json.dumps({"lesson_id": lesson_id, "questions": questions}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"  Quiz: {len(questions)} questions → {quiz_path}")
        else:
            print("  Quiz: no questions generated.")

        state["quiz_questions"] = questions
        return state
