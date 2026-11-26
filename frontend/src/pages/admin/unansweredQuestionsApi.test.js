import assert from 'node:assert/strict';
import test from 'node:test';
import { buildUnansweredQuestionParams, loadUnansweredQuestions } from './unansweredQuestionsApi.js';

test('builds selected unanswered language and minimum-frequency parameters', () => {
  assert.deepEqual(
    buildUnansweredQuestionParams({ language: 'pa_latn', min_frequency: '4' }),
    { language: 'pa_latn', min_frequency: 4 },
  );
  assert.deepEqual(buildUnansweredQuestionParams({ language: '', min_frequency: '0' }), { min_frequency: 1 });
});

test('requests unanswered questions with filters and returns API rows unchanged', async () => {
  const rows = [{ id: 7, question: 'test query', language: 'hi', frequency: 3 }];
  let request;
  const apiClient = {
    async get(path, options) {
      request = { path, options };
      return { data: rows };
    },
  };

  const result = await loadUnansweredQuestions(apiClient, { language: 'hi', min_frequency: '3' });

  assert.deepEqual(request, {
    path: '/assistant/admin/unanswered',
    options: { params: { language: 'hi', min_frequency: 3 } },
  });
  assert.equal(result, rows);
});
