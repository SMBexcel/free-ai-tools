// Lets `import systemPrompt from '../prompts/agent-system.md'` typecheck.
// At build time wrangler's Text rule (wrangler.toml) inlines the file as a string.
declare module '*.md' {
  const content: string;
  export default content;
}
