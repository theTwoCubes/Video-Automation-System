import json
from agents.base_agent import BaseAgent
from services.knowledge.ingestion import KnowledgeIngestionService


SYSTEM_PROMPT = """You are a curriculum designer for theTwoCubes Learning, a technical YouTube channel.
Your task: given a knowledge source, generate a complete, pedagogically sound course curriculum.

Rules:
- Sequence lessons from fundamentals to advanced topics.
- Each lesson must be self-contained and teachable in 10-15 minutes.
- Detect prerequisite dependencies between topics.
- Assign difficulty: beginner, intermediate, or advanced.
- Provide 5-8 topic_tags per lesson (lowercase, specific).
- Estimate duration_minutes between 10 and 15.
- Keep lesson titles concise and specific (e.g. "Pointers in C", not "Learning about Pointers").

Output strictly valid JSON. No markdown. No commentary."""

USER_TEMPLATE = """
Knowledge Source: {source_name}
Topic: {topic}
Target audience: {audience}
RAG context (table of contents / key topics discovered):

{rag_context}

Generate a course curriculum as JSON matching this exact schema:
{{
  "course_title": "string",
  "course_description": "string (2-3 sentences)",
  "total_lessons": number,
  "lessons": [
    {{
      "position": number,
      "title": "string",
      "topic_tags": ["string"],
      "difficulty": "beginner|intermediate|advanced",
      "estimated_duration_minutes": number,
      "prerequisites": ["lesson title or empty list"]
    }}
  ]
}}
"""


class CurriculumAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.ingestion = KnowledgeIngestionService()

    def run(self, state: dict) -> dict:
        print("[CurriculumAgent] Generating curriculum...")

        source_id = state["source_id"]
        topic = state.get("topic", "Programming")
        audience = state.get("target_audience", "beginners")
        source_name = state.get("source_name", topic)

        # RAG: get high-level overview of the source
        overview_chunks = self.ingestion.query(
            source_id,
            f"table of contents, chapters, topics covered in {topic}",
            n_results=8,
        )
        rag_context = "\n\n---\n\n".join(overview_chunks) if overview_chunks else "No context available."

        user_msg = USER_TEMPLATE.format(
            source_name=source_name,
            topic=topic,
            audience=audience,
            rag_context=rag_context[:4000],  # token budget
        )

        curriculum = self.llm.complete_json(SYSTEM_PROMPT, user_msg)
        state["curriculum"] = curriculum
        print(f"  Generated {curriculum.get('total_lessons', '?')} lessons.")
        return state
