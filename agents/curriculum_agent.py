import json
import math
from agents.base_agent import BaseAgent
from services.knowledge.ingestion import KnowledgeIngestionService


MODULES_PROMPT = """You are a curriculum designer for theTwoCubes Learning.
Your first task is to divide the requested course into high-level MODULES.

Use the provided knowledge base context as a SUPPLEMENTARY REFERENCE only — it helps you understand the structure and scope of the material, but your primary source is your own expert knowledge of the subject. If the context contradicts established facts, trust your own knowledge.

Output strictly valid JSON matching this schema:
{
  "course_title": "string",
  "course_description": "string (2-3 sentences)",
  "modules": [
    {
      "module_name": "string",
      "description": "string"
    }
  ]
}"""

LESSONS_PROMPT = """You are a curriculum designer for theTwoCubes Learning.
Your task is to generate the specific lessons for the module "{module_name}".
The entire course has a target of at least {min_lessons} lessons. We need you to generate approximately {target_lessons_for_module} lessons for this module to meet that target.
Do not combine topics too densely. Break complex topics into multiple smaller lessons.

The knowledge base context provided is a SUPPLEMENTARY REFERENCE — use it to understand the scope and depth of what is covered in this course's material. Your primary knowledge comes from your own expertise; the reference is a guide, not a constraint. Do not blindly reproduce text from it.

Rules:
- Each lesson must be self-contained and teachable in 10-15 minutes.
- Assign difficulty: beginner, intermediate, or advanced.
- Provide 5-8 topic_tags per lesson.
- Estimate duration_minutes between 10 and 15.

Output strictly valid JSON matching this schema:
{
  "lessons": [
    {
      "title": "string",
      "topic_tags": ["string"],
      "difficulty": "beginner|intermediate|advanced",
      "estimated_duration_minutes": number,
      "prerequisites": ["lesson title or empty list"]
    }
  ]
}"""


class CurriculumAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.ingestion = KnowledgeIngestionService()

    def run(self, state: dict) -> dict:
        print("[CurriculumAgent] Generating curriculum...")

        source_ids = state.get("source_ids", [])
        topic = state.get("topic", "Programming")
        audience = state.get("target_audience", "beginners")
        source_name = state.get("source_name", topic)
        min_lessons = state.get("min_lessons", 30)

        # 1. Grab the Table of Contents (first 20 chunks should cover it + intro)
        toc_chunks = self.ingestion.get_first_chunks(source_ids, n_chunks=20)
        
        # 2. Grab some general overview chunks via RAG
        overview_chunks = self.ingestion.query(
            source_ids,
            f"table of contents, chapters, topics covered in {topic}",
            n_results=10,
        )
        
        # Combine context but avoid exact duplicates
        unique_chunks = list(dict.fromkeys(toc_chunks + overview_chunks))
        rag_context = "\n\n---\n\n".join(unique_chunks)[:60000] # Safe ~15k token limit

        print("  Generating high-level modules...")
        user_msg_modules = f"Knowledge Source: {source_name}\nTopic: {topic}\nTarget audience: {audience}\nContext:\n{rag_context}"
        
        modules_res = self.llm.complete_json(MODULES_PROMPT, user_msg_modules)
        modules = modules_res.get("modules", [])
        
        if not modules:
            modules = [{"module_name": "Core Concepts", "description": "Fundamentals"}]

        # Distribute the target lessons across the modules
        target_per_module = max(3, math.ceil(min_lessons / len(modules)))
        
        all_lessons = []
        global_position = 1

        print(f"  Generating lessons for {len(modules)} modules (target ~{target_per_module} each)...")
        for idx, mod in enumerate(modules):
            print(f"    -> Module: {mod.get('module_name')}")
            sys_prompt = LESSONS_PROMPT.format(
                module_name=mod.get("module_name"),
                min_lessons=min_lessons,
                target_lessons_for_module=target_per_module
            )
            
            user_msg = f"Knowledge Source Context:\n{rag_context}\n\nModule Description: {mod.get('description')}"
            res = self.llm.complete_json(sys_prompt, user_msg)
            
            for lesson in res.get("lessons", []):
                lesson["position"] = global_position
                lesson["module"] = mod.get("module_name")
                all_lessons.append(lesson)
                global_position += 1

        curriculum = {
            "course_title": modules_res.get("course_title", topic),
            "course_description": modules_res.get("course_description", ""),
            "total_lessons": len(all_lessons),
            "lessons": all_lessons
        }
        
        state["curriculum"] = curriculum
        print(f"  Generated {len(all_lessons)} lessons total.")
        return state
