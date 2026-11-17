import { defineConfig } from 'vitest/config'

// Testes unitários (Node). Os testes de ponta a ponta ficam em tests/e2e (Playwright)
// e o teste do motor da demonstração em tests/schedule-engine.test.mjs (node --test).
export default defineConfig({
  test: {
    include: ['tests/unit/**/*.test.ts'],
    environment: 'node',
  },
})
