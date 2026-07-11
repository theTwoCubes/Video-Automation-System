// Shared UI primitives - the single source for the studio's design tokens and
// the pipeline stage model. Previously the `S` token object and `cx` helper
// were copy-pasted into every page (guaranteed drift); they live here now.

export const cx = (...a) => a.filter(Boolean).join(' ');

// Design tokens (Tailwind class strings). One definition, imported everywhere.
export const S = {
  label: 'text-[10px] font-bold text-teal-400 uppercase tracking-[0.15em] mb-1.5 block',
  card:  'bg-[#0d0d0d] border border-[#1a1a1a] rounded-xl',
  input: 'w-full bg-[#111] border border-[#222] rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-teal-500 transition-colors',
  pill:  'inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full',
};

// The eleven pipeline agents, in order. Each `tags` entry is a substring that
// appears in a log line when that stage is running (the agent banner) or was
// loaded from a checkpoint. Used to turn the raw SSE log into a live stepper -
// the "live production monitor" from the blueprint (§14/§23), replacing a
// coarse pending/processing/done status with real per-stage progress.
export const STAGES = [
  { key: 'plan',      label: 'Plan',      tags: ['LessonPlannerAgent', 'plan_lesson'] },
  { key: 'script',    label: 'Script',    tags: ['ScriptAgent', 'write_script'] },
  { key: 'code',      label: 'Code',      tags: ['CodeAgent', 'generate_code'] },
  { key: 'diagrams',  label: 'Diagrams',  tags: ['DiagramAgent', 'generate_diagrams'] },
  { key: 'slides',    label: 'Slides',    tags: ['SlideAgent', 'generate_slides'] },
  { key: 'voice',     label: 'Voice',     tags: ['VoiceAgent', 'synthesize_voice'] },
  { key: 'compose',   label: 'Compose',   tags: ['VideoAgent', 'compose_video'] },
  { key: 'thumbnail', label: 'Thumbnail', tags: ['ThumbnailAgent', 'generate_thumbnail'] },
  { key: 'qa',        label: 'QA',        tags: ['QAAgent', 'qa_check'] },
  { key: 'seo',       label: 'SEO',       tags: ['SEOAgent', 'generate_seo'] },
  { key: 'quiz',      label: 'Quiz',      tags: ['QuizAgent', 'generate_quiz'] },
];

// Return the STAGES index a single log line belongs to, or -1 if none.
export function parseStage(line) {
  if (!line) return -1;
  for (let i = 0; i < STAGES.length; i++) {
    if (STAGES[i].tags.some(t => line.includes(t))) return i;
  }
  return -1;
}

// Given the accumulated log lines, return {index, done}. `index` is the
// furthest stage seen; `done` is true once the pipeline prints its completion
// banner.
export function pipelineProgress(logs) {
  let index = -1;
  let done = false;
  for (const line of logs) {
    const s = parseStage(line);
    if (s > index) index = s;
    if (line.includes('Pipeline finished') || line.includes('[Pipeline] Done')) done = true;
  }
  return { index, done };
}
