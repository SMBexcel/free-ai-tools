// Hand-rolled Anthropic Messages-API loop (no agent framework). One turn:
//   - up to MAX_ITERATIONS tool round-trips
//   - tool_choice: auto
//   - two cache_control breakpoints (system text + last tool schema)
//   - tool errors come back as tool_result { is_error: true } so the model
//     recovers; only loop-runaway / unknown stop_reason throw out.

import type { Anthropic } from '../lib/anthropic.js';
import { cachedSystem, getAnthropic } from '../lib/anthropic.js';
import type { Env } from '../env.js';
import { log } from '../lib/log.js';
import systemPromptText from '../prompts/agent-system.md';
import type { MemoryMessage } from './memory.js';
import { findTool, getToolRegistry } from './tools/index.js';
import type { AgentCtx } from './tools/index.js';

export const MAX_ITERATIONS = 12;
export const DEFAULT_MAX_TOKENS = 1024;
export const DEFAULT_MODEL = 'claude-sonnet-4-6';

/** Raw system-prompt text (with {{BUSINESS_NAME}} tokens, rendered per-request). */
export const SYSTEM_PROMPT: string = systemPromptText;

export interface IntermediateStep {
  action: { tool: string; toolInput: unknown };
  observation: unknown;
}

export interface AgentUsageTotals {
  input_tokens: number;
  output_tokens: number;
  cache_creation_input_tokens: number;
  cache_read_input_tokens: number;
}

export interface AgentResult {
  output: string;
  intermediateSteps: IntermediateStep[];
  stopReason: Anthropic.Messages.StopReason | null;
  usage: AgentUsageTotals;
}

export interface RunAgentInput {
  env: Env;
  ctx: AgentCtx;
  contextString: string;
  history: MemoryMessage[];
}

export class AgentRunawayError extends Error {
  override readonly name = 'AgentRunawayError';
  constructor(readonly iterations: number) {
    super(`agent loop exceeded ${iterations} tool-use iterations`);
  }
}

export class AgentUnexpectedStopError extends Error {
  override readonly name = 'AgentUnexpectedStopError';
  constructor(readonly stopReason: Anthropic.Messages.StopReason | null) {
    super(`unexpected stop_reason: ${stopReason ?? 'null'}`);
  }
}

export async function runAgent(input: RunAgentInput): Promise<AgentResult> {
  const { env, ctx, contextString, history } = input;
  const client = getAnthropic(env);
  const model = env.ANTHROPIC_MODEL_AGENT || DEFAULT_MODEL;

  const tools = buildToolsParam(env);
  const system: Anthropic.Messages.TextBlockParam[] = [cachedSystem(renderSystemPrompt(env))];

  let messages: Anthropic.Messages.MessageParam[] = [
    ...history.map((m) => ({ role: m.role, content: m.content })),
    { role: 'user' as const, content: contextString },
  ];

  const intermediateSteps: IntermediateStep[] = [];
  const usage: AgentUsageTotals = {
    input_tokens: 0,
    output_tokens: 0,
    cache_creation_input_tokens: 0,
    cache_read_input_tokens: 0,
  };

  for (let iter = 0; iter < MAX_ITERATIONS; iter++) {
    const resp = await client.messages.create({
      model,
      max_tokens: DEFAULT_MAX_TOKENS,
      system,
      tools,
      tool_choice: { type: 'auto' },
      messages,
    });

    const u = resp.usage;
    usage.input_tokens += u?.input_tokens ?? 0;
    usage.output_tokens += u?.output_tokens ?? 0;
    usage.cache_creation_input_tokens += u?.cache_creation_input_tokens ?? 0;
    usage.cache_read_input_tokens += u?.cache_read_input_tokens ?? 0;

    messages = [
      ...messages,
      {
        role: 'assistant',
        content: resp.content as unknown as Anthropic.Messages.ContentBlockParam[],
      },
    ];

    if (resp.stop_reason === 'end_turn') {
      return { output: textOf(resp.content), intermediateSteps, stopReason: resp.stop_reason, usage };
    }

    if (resp.stop_reason !== 'tool_use') {
      log.error('agent.unexpected_stop', { phone: ctx.phone, stop_reason: resp.stop_reason, iteration: iter });
      throw new AgentUnexpectedStopError(resp.stop_reason);
    }

    const toolUses = resp.content.filter(
      (b): b is Anthropic.Messages.ToolUseBlock => b.type === 'tool_use',
    );
    const dispatched = await Promise.all(toolUses.map((t) => dispatchToolUse(t, ctx)));
    for (const d of dispatched) intermediateSteps.push(d.step);
    messages = [...messages, { role: 'user', content: dispatched.map((d) => d.toolResult) }];
  }

  log.error('agent.runaway', { phone: ctx.phone, iterations: MAX_ITERATIONS });
  throw new AgentRunawayError(MAX_ITERATIONS);
}

// ── Helpers ──────────────────────────────────────────────────────────────

function renderSystemPrompt(env: Env): string {
  return SYSTEM_PROMPT.replace(/\{\{\s*BUSINESS_NAME\s*\}\}/g, env.BUSINESS_NAME || 'our team');
}

function buildToolsParam(env: Env): Anthropic.Messages.Tool[] {
  const tools: Anthropic.Messages.Tool[] = getToolRegistry(env).map((t) => ({
    name: t.name,
    description: t.description,
    input_schema: t.input_schema as Anthropic.Messages.Tool.InputSchema,
  }));
  const last = tools[tools.length - 1];
  if (last) tools[tools.length - 1] = { ...last, cache_control: { type: 'ephemeral' } };
  return tools;
}

interface DispatchedTool {
  step: IntermediateStep;
  toolResult: Anthropic.Messages.ToolResultBlockParam;
}

async function dispatchToolUse(use: Anthropic.Messages.ToolUseBlock, ctx: AgentCtx): Promise<DispatchedTool> {
  const tool = findTool(use.name, ctx.env);
  let observation: unknown;
  let isError = false;

  if (!tool) {
    observation = { ok: false, error: `unknown tool: ${use.name}` };
    isError = true;
    log.warn('agent.unknown_tool', { phone: ctx.phone, name: use.name });
  } else {
    try {
      observation = await tool.handler(use.input as never, ctx);
    } catch (e) {
      observation = { ok: false, error: e instanceof Error ? e.message : String(e) };
      isError = true;
      log.error('agent.tool_threw', { phone: ctx.phone, name: use.name });
    }
  }

  return {
    step: { action: { tool: use.name, toolInput: use.input }, observation },
    toolResult: {
      type: 'tool_result',
      tool_use_id: use.id,
      content: JSON.stringify(observation ?? null),
      is_error: isError,
    },
  };
}

function textOf(content: Anthropic.Messages.ContentBlock[]): string {
  return content
    .filter((b): b is Anthropic.Messages.TextBlock => b.type === 'text')
    .map((b) => b.text)
    .join('\n')
    .trim();
}
